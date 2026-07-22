"""Optional pre-physical rules gate (SparkRules) before VRP.

Not a fifth PVDM phase — runs before Physical when enabled via env or explicit connector.
"""

from __future__ import annotations

import logging
import os
from collections.abc import Callable
from typing import Any

from serverless_data_mesh.exceptions import RuleEvaluationError

logger = logging.getLogger(__name__)

RulesGateFn = Callable[[list[dict[str, Any]]], list[dict[str, Any]]]


def rules_gate_enabled() -> bool:
    flag = os.environ.get("SDM_RULES_GATE", "").strip().lower()
    if flag in ("1", "true", "yes", "on"):
        return True
    # Auto-enable when SparkRules DRL is configured
    return bool(os.environ.get("SPARKRULES_DRL") or os.environ.get("SPARKRULES_DRL_S3_URI"))


def apply_rules_gate(
    records: list[dict[str, Any]],
    *,
    connector: Any | None = None,
    require_any_rule_fired: bool = False,
) -> tuple[list[dict[str, Any]], list[Any]]:
    """Apply SparkRules to chunk records; raise RuleEvaluationError on quality fail.

    Returns (enriched_records, audit_summaries).
    """
    if connector is None:
        if not rules_gate_enabled():
            return records, []
        from serverless_data_mesh.rules import SparkRulesConnector

        connector = SparkRulesConnector.from_environment()

    enriched, audit = connector.apply_chunk(records)
    if hasattr(connector, "quality_gate"):
        passed = connector.quality_gate(
            enriched,
            require_any_rule_fired=require_any_rule_fired,
        )
        if not passed:
            policy = getattr(connector, "policy_id", "?")
            raise RuleEvaluationError(f"SparkRules quality gate rejected chunk (policy={policy})")
    logger.info(
        "Rules gate applied policy=%s records=%s audit=%s",
        getattr(connector, "policy_id", None),
        len(enriched),
        len(audit),
    )
    return enriched, audit
