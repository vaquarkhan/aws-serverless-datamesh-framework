"""SparkRules enrichment for domain writer chunks (optional ``[rules]`` extra)."""

from __future__ import annotations

import logging
import os
from typing import Any

logger = logging.getLogger(__name__)

_SAMPLE_DRL = r"""
rule CuratedEligible
when
    $row : Row ( $row.amount > 0 )
then
    result.mesh_curated = true;
end
"""


def enrich_records_with_rules(
    records: list[dict[str, Any]],
    *,
    drl: str | None = None,
) -> list[dict[str, Any]]:
    """Apply SparkRules DRL to a chunk in pure-Python mode (Lambda-safe, no Glue ETL)."""
    from serverless_data_mesh.rules import SparkRulesConnector

    active_drl = drl or os.environ.get("SPARKRULES_DRL") or _SAMPLE_DRL
    connector = SparkRulesConnector.from_drl(active_drl, policy_id="domain-writer-demo")
    enriched, audit = connector.apply_chunk(records)
    if audit:
        logger.info("SparkRules fired %d rule(s) on chunk", len(audit))
    return enriched
