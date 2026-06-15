"""SparkRules engine connector for Lambda domain writers.

SparkRules runs on Lambda in two modes:

1. **Pure Python (default)** — ``LocalRuleExecutor`` evaluates DRL per chunk without
   a Spark cluster or Glue ETL job. Ideal for enrichment and quality gates before VRP.

2. **Spark-on-Lambda (optional)** — ``apply_drl`` when PySpark is bundled in the
   Lambda layer/container.

Install: ``pip install serverless-data-mesh[rules]`` or ``[spark]`` for PySpark path.
"""

from __future__ import annotations

import json
import logging
import os
from dataclasses import dataclass, field
from typing import Any

from serverless_data_mesh.exceptions import RuleEvaluationError

logger = logging.getLogger(__name__)


def _require_sparkrules() -> Any:
    try:
        import sparkrules  # noqa: F401
    except ImportError as exc:
        raise ImportError(
            "sparkrules is required for SparkRulesConnector. "
            "Install with: pip install serverless-data-mesh[rules]"
        ) from exc
    return sparkrules


@dataclass(frozen=True, slots=True)
class RuleFireSummary:
    """Audit-friendly summary of one rule evaluation on a fact."""

    fact_index: int
    rule_name: str
    fired: bool
    reason_codes: tuple[str, ...]
    action_output: dict[str, Any]


@dataclass(slots=True)
class SparkRulesConnector:
    """Lambda-native business rules connector using SparkRules ``LocalRuleExecutor``.

    Use between ``source_reader`` and ``batch_writer`` to enrich or filter records
    with Drools-style DRL before VRP verification and Iceberg commit.
    """

    drl: str
    policy_id: str = "mesh-default"
    _executor: Any = field(default=None, repr=False)

    @classmethod
    def from_drl(cls, drl: str, *, policy_id: str = "mesh-default") -> SparkRulesConnector:
        """Compile DRL and build a pure-Python executor (no JVM, no Glue ETL)."""
        _require_sparkrules()
        from sparkrules.executor.local_executor import LocalRuleExecutor

        connector = cls(drl=drl, policy_id=policy_id)
        connector._executor = LocalRuleExecutor.from_drl(drl)
        return connector

    @classmethod
    def from_environment(cls) -> SparkRulesConnector:
        """Load DRL from ``SPARKRULES_DRL`` (inline) or ``SPARKRULES_DRL_S3_URI``."""
        inline = os.environ.get("SPARKRULES_DRL")
        if inline:
            return cls.from_drl(inline, policy_id=os.environ.get("SPARKRULES_POLICY_ID", "mesh-default"))

        s3_uri = os.environ.get("SPARKRULES_DRL_S3_URI")
        if s3_uri:
            return cls.from_s3(s3_uri, policy_id=os.environ.get("SPARKRULES_POLICY_ID", "mesh-default"))

        raise ValueError("Set SPARKRULES_DRL or SPARKRULES_DRL_S3_URI for SparkRulesConnector")

    @classmethod
    def from_s3(cls, s3_uri: str, *, policy_id: str = "mesh-default") -> SparkRulesConnector:
        """Load rule pack DRL from S3 (Steward governance bucket pattern)."""
        import boto3

        if not s3_uri.startswith("s3://"):
            raise ValueError(f"Expected s3:// URI, got {s3_uri!r}")
        path = s3_uri[5:]
        bucket, _, key = path.partition("/")
        body = boto3.client("s3").get_object(Bucket=bucket, Key=key)["Body"].read()
        return cls.from_drl(body.decode("utf-8"), policy_id=policy_id)

    def _ensure_executor(self) -> Any:
        if self._executor is None:
            _require_sparkrules()
            from sparkrules.executor.local_executor import LocalRuleExecutor

            self._executor = LocalRuleExecutor.from_drl(self.drl)
        return self._executor

    def apply_chunk(
        self,
        records: list[dict[str, Any]],
        *,
        fact_binding: str = "row",
    ) -> tuple[list[dict[str, Any]], list[RuleFireSummary]]:
        """Evaluate DRL against each record; merge rule actions into enriched rows.

        Each record is wrapped as ``{fact_binding: record}`` for DRL binding, e.g.
        ``$row : Row ( $row.amount > 0 )``.
        """
        executor = self._ensure_executor()
        enriched: list[dict[str, Any]] = []
        audit: list[RuleFireSummary] = []

        for idx, record in enumerate(records):
            fact: dict[str, Any] = {fact_binding: dict(record)}
            result = executor.score(fact)
            merged = dict(record)
            merged.update(result.merged_actions)
            merged["_sparkrules_fired"] = result.fired_any
            enriched.append(merged)

            for fire in result.fires:
                if fire.fired:
                    audit.append(
                        RuleFireSummary(
                            fact_index=idx,
                            rule_name=fire.rule_name,
                            fired=True,
                            reason_codes=fire.reason_codes,
                            action_output=dict(fire.action_output),
                        )
                    )
        return enriched, audit

    def quality_gate(
        self,
        records: list[dict[str, Any]],
        *,
        require_any_rule_fired: bool = False,
        reject_field: str = "_mesh_reject",
    ) -> list[dict[str, Any]]:
        """Filter or mark records that fail the rules policy before physical write."""
        enriched, audit = self.apply_chunk(records)
        if not require_any_rule_fired:
            return enriched

        fired_indices = {a.fact_index for a in audit if a.fired}
        passed: list[dict[str, Any]] = []
        for idx, row in enumerate(enriched):
            if idx in fired_indices:
                passed.append(row)
            else:
                logger.warning("SparkRules quality gate rejected record index=%d", idx)
        if not passed:
            raise RuleEvaluationError(
                f"No records passed SparkRules policy {self.policy_id!r} "
                f"(require_any_rule_fired=True, chunk_size={len(records)})"
            )
        return passed

    def audit_json(self, audit: list[RuleFireSummary]) -> str:
        """Serialize rule fires for Steward proof / lineage buckets."""
        payload = [
            {
                "fact_index": a.fact_index,
                "rule_name": a.rule_name,
                "fired": a.fired,
                "reason_codes": list(a.reason_codes),
                "action_output": a.action_output,
                "policy_id": self.policy_id,
            }
            for a in audit
        ]
        return json.dumps(payload, default=str)

    @staticmethod
    def apply_drl_spark(
        spark: Any,
        dataframe: Any,
        drl: str,
        *,
        fact_id_field: str = "id",
    ) -> Any:
        """Spark-on-Lambda path: distributed ``apply_drl`` over a DataFrame."""
        _require_sparkrules()
        from sparkrules.spark.dataframe import apply_drl

        return apply_drl(dataframe, drl, fact_id_field=fact_id_field)
