"""Mesh pipeline contract model (sdm/v1 DataProductPipeline)."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True, slots=True)
class PipelineAccounts:
    producer: str
    steward: str | None = None
    publisher: str | None = None


@dataclass(frozen=True, slots=True)
class PipelineBoundary:
    source_namespace: str
    target_table: str
    partition_key: str = "dt"
    quality_policy_id: str = "strict-zero-drop"
    max_chunk_records: int = 5000


@dataclass(frozen=True, slots=True)
class PipelineWorkload:
    identity_fields: tuple[str, ...] = ("id",)
    content_fields: tuple[str, ...] = ("id", "payload_hash")
    checkpoint_interval: int = 5000
    rollback_threshold_ms: int = 30_000


@dataclass(frozen=True, slots=True)
class PipelineRuntime:
    """Physical transform engine and Lambda sizing (metadata for packaging/deploy)."""

    engine: str = "pyarrow"  # pyarrow | polars | pyspark | pure_python
    package_extras: str = ""  # pip extra: rules | spark | all
    lambda_memory_mb: int = 3008
    lambda_timeout_seconds: int = 900
    spark_rules_enabled: bool = False
    spark_shuffle_partitions: int = 8


@dataclass(frozen=True, slots=True)
class PipelineGovernance:
    sla_freshness_hours: int = 2
    auto_repair: bool = True
    canary_max_divergence_pct: float = 1.0
    schema_version: str = "1.0.0"


@dataclass(frozen=True, slots=True)
class PipelineTrigger:
    type: str
    cron: str | None = None
    description: str | None = None


@dataclass(frozen=True, slots=True)
class ConsumerSlaSpec:
    consumer_id: str
    target_table: str
    max_freshness_minutes: int = 60
    min_completeness_pct: float = 99.9
    required_columns: tuple[str, ...] = ()
    enforcement: str = "vrp_backed"


@dataclass(frozen=True, slots=True)
class MeshPipelineContract:
    """Parsed sdm/v1 DataProductPipeline contract."""

    api_version: str
    kind: str
    domain_id: str
    product_id: str
    owner_team: str
    description: str
    accounts: PipelineAccounts
    boundary: PipelineBoundary
    workload: PipelineWorkload
    governance: PipelineGovernance
    runtime: PipelineRuntime = field(default_factory=PipelineRuntime)
    triggers: tuple[PipelineTrigger, ...] = ()
    consumer_slas: tuple[ConsumerSlaSpec, ...] = ()
    aws_region: str = "us-east-2"
    name_prefix: str | None = None

    @property
    def output_domain_dir(self) -> str:
        return self.domain_id

    def to_dict(self) -> dict[str, Any]:
        return {
            "apiVersion": self.api_version,
            "kind": self.kind,
            "metadata": {
                "domain_id": self.domain_id,
                "product_id": self.product_id,
                "owner_team": self.owner_team,
                "description": self.description,
            },
            "spec": {
                "accounts": {
                    "producer": self.accounts.producer,
                    "steward": self.accounts.steward,
                    "publisher": self.accounts.publisher,
                },
                "boundary": {
                    "source_namespace": self.boundary.source_namespace,
                    "target_table": self.boundary.target_table,
                    "partition_key": self.boundary.partition_key,
                    "quality_policy_id": self.boundary.quality_policy_id,
                    "max_chunk_records": self.boundary.max_chunk_records,
                },
                "workload": {
                    "identity_fields": list(self.workload.identity_fields),
                    "content_fields": list(self.workload.content_fields),
                    "checkpoint_interval": self.workload.checkpoint_interval,
                    "rollback_threshold_ms": self.workload.rollback_threshold_ms,
                },
                "governance": {
                    "sla_freshness_hours": self.governance.sla_freshness_hours,
                    "auto_repair": self.governance.auto_repair,
                    "canary_max_divergence_pct": self.governance.canary_max_divergence_pct,
                    "schema_version": self.governance.schema_version,
                },
                "runtime": {
                    "engine": self.runtime.engine,
                    "package_extras": self.runtime.package_extras,
                    "lambda_memory_mb": self.runtime.lambda_memory_mb,
                    "lambda_timeout_seconds": self.runtime.lambda_timeout_seconds,
                    "spark_rules_enabled": self.runtime.spark_rules_enabled,
                    "spark_shuffle_partitions": self.runtime.spark_shuffle_partitions,
                },
                "triggers": [
                    {"type": t.type, "cron": t.cron, "description": t.description}
                    for t in self.triggers
                ],
                "consumer_slas": [
                    {
                        "consumer_id": c.consumer_id,
                        "target_table": c.target_table,
                        "max_freshness_minutes": c.max_freshness_minutes,
                        "min_completeness_pct": c.min_completeness_pct,
                        "required_columns": list(c.required_columns),
                        "enforcement": c.enforcement,
                    }
                    for c in self.consumer_slas
                ],
                "aws_region": self.aws_region,
                "name_prefix": self.name_prefix or f"sdm-{self.domain_id}",
            },
        }

    @classmethod
    def from_dict(cls, raw: dict[str, Any]) -> MeshPipelineContract:
        meta = raw.get("metadata") or {}
        spec = raw.get("spec") or {}
        accounts_raw = spec.get("accounts") or {}
        boundary_raw = spec.get("boundary") or {}
        workload_raw = spec.get("workload") or {}
        governance_raw = spec.get("governance") or {}
        runtime_raw = spec.get("runtime") or {}

        triggers = tuple(
            PipelineTrigger(
                type=str(t.get("type", "manual")),
                cron=t.get("cron"),
                description=t.get("description"),
            )
            for t in (spec.get("triggers") or [])
        )

        consumer_slas = tuple(
            ConsumerSlaSpec(
                consumer_id=str(c["consumer_id"]),
                target_table=str(c.get("target_table") or boundary_raw.get("target_table", "")),
                max_freshness_minutes=int(c.get("max_freshness_minutes", 60)),
                min_completeness_pct=float(c.get("min_completeness_pct", 99.9)),
                required_columns=tuple(c.get("required_columns") or ()),
                enforcement=str(c.get("enforcement", "vrp_backed")),
            )
            for c in (spec.get("consumer_slas") or [])
        )

        domain_id = str(meta.get("domain_id") or boundary_raw.get("domain_id") or "")
        target_table = str(boundary_raw.get("target_table") or "")

        engine = str(runtime_raw.get("engine") or "pyarrow")
        spark_rules = bool(runtime_raw.get("spark_rules_enabled", False))
        package_extras = str(runtime_raw.get("package_extras") or "")
        if not package_extras:
            if engine == "pyspark":
                package_extras = "spark"
            elif spark_rules:
                package_extras = "rules"

        runtime = PipelineRuntime(
            engine=engine,
            package_extras=package_extras,
            lambda_memory_mb=int(runtime_raw.get("lambda_memory_mb") or 3008),
            lambda_timeout_seconds=int(runtime_raw.get("lambda_timeout_seconds") or 900),
            spark_rules_enabled=spark_rules,
            spark_shuffle_partitions=int(runtime_raw.get("spark_shuffle_partitions") or 8),
        )

        return cls(
            api_version=str(raw.get("apiVersion", "")),
            kind=str(raw.get("kind", "")),
            domain_id=domain_id,
            product_id=str(meta.get("product_id") or f"{domain_id}-{target_table}"),
            owner_team=str(meta.get("owner_team") or f"{domain_id}-platform"),
            description=str(meta.get("description") or ""),
            accounts=PipelineAccounts(
                producer=str(accounts_raw.get("producer") or ""),
                steward=accounts_raw.get("steward"),
                publisher=accounts_raw.get("publisher"),
            ),
            boundary=PipelineBoundary(
                source_namespace=str(
                    boundary_raw.get("source_namespace") or f"raw_{domain_id}"
                ),
                target_table=target_table,
                partition_key=str(boundary_raw.get("partition_key") or "dt"),
                quality_policy_id=str(
                    boundary_raw.get("quality_policy_id") or "strict-zero-drop"
                ),
                max_chunk_records=int(boundary_raw.get("max_chunk_records") or 5000),
            ),
            workload=PipelineWorkload(
                identity_fields=tuple(workload_raw.get("identity_fields") or ("id",)),
                content_fields=tuple(
                    workload_raw.get("content_fields") or ("id", "payload_hash")
                ),
                checkpoint_interval=int(workload_raw.get("checkpoint_interval") or 5000),
                rollback_threshold_ms=int(
                    workload_raw.get("rollback_threshold_ms") or 30_000
                ),
            ),
            governance=PipelineGovernance(
                sla_freshness_hours=int(governance_raw.get("sla_freshness_hours") or 2),
                auto_repair=bool(governance_raw.get("auto_repair", True)),
                canary_max_divergence_pct=float(
                    governance_raw.get("canary_max_divergence_pct") or 1.0
                ),
                schema_version=str(governance_raw.get("schema_version") or "1.0.0"),
            ),
            runtime=runtime,
            triggers=triggers,
            consumer_slas=consumer_slas,
            aws_region=str(spec.get("aws_region") or "us-east-2"),
            name_prefix=spec.get("name_prefix"),
        )
