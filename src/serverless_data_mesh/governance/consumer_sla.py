"""Consumer SLA contracts backed by VRP proofs before read access."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

from serverless_data_mesh.types.workload import ConsumerSLAContract

logger = logging.getLogger(__name__)


@dataclass(frozen=True, slots=True)
class ConsumerAccessDecision:
    """Whether a consumer may read a table given proof + SLA."""

    granted: bool
    consumer_id: str
    target_table: str
    reason: str
    checks: dict[str, bool]


def enforce_consumer_sla(
    contract: ConsumerSLAContract,
    *,
    proof: dict[str, Any],
    snapshot_committed_at: datetime | None = None,
) -> ConsumerAccessDecision:
    """Verify producer VRP proof meets consumer SLA before granting read access."""
    checks: dict[str, bool] = {}
    recon = proof.get("reconciliation", {})
    verdict = recon.get("verdict", "FAIL")

    checks["vrp_pass"] = verdict == "PASS"
    if not checks["vrp_pass"]:
        return ConsumerAccessDecision(
            granted=False,
            consumer_id=contract.consumer_id,
            target_table=contract.target_table,
            reason="VRP verdict is not PASS",
            checks=checks,
        )

    source_count = int(recon.get("source_count", 0))
    sink_count = int(recon.get("sink_count", 0))
    if source_count > 0:
        completeness = (sink_count / source_count) * 100.0
    else:
        completeness = 0.0
    checks["completeness"] = completeness >= contract.min_completeness_pct

    content_fields = set(proof.get("content_fields", []))
    checks["required_columns"] = all(col in content_fields for col in contract.required_columns)

    committed_at = snapshot_committed_at
    if committed_at is None and proof.get("created_at"):
        committed_at = datetime.fromisoformat(proof["created_at"].replace("Z", "+00:00"))
    freshness_ok = True
    if committed_at is not None:
        age_min = (datetime.now(timezone.utc) - committed_at).total_seconds() / 60.0
        freshness_ok = age_min <= contract.max_freshness_minutes
    checks["freshness"] = freshness_ok

    granted = all(checks.values())
    failed = [k for k, v in checks.items() if not v]
    reason = "All SLA checks passed" if granted else f"SLA failed: {', '.join(failed)}"

    logger.info(
        "Consumer SLA %s for %s: granted=%s checks=%s",
        contract.consumer_id,
        contract.target_table,
        granted,
        checks,
    )

    return ConsumerAccessDecision(
        granted=granted,
        consumer_id=contract.consumer_id,
        target_table=contract.target_table,
        reason=reason,
        checks=checks,
    )


def grant_read_if_sla_met(
    contract: ConsumerSLAContract,
    *,
    proof: dict[str, Any],
    snapshot_committed_at: datetime | None = None,
) -> dict[str, Any]:
    """Lake Formation / steward automation hook: return grant payload or denial."""
    decision = enforce_consumer_sla(
        contract,
        proof=proof,
        snapshot_committed_at=snapshot_committed_at,
    )
    return {
        "consumer_id": decision.consumer_id,
        "target_table": decision.target_table,
        "grant_read": decision.granted,
        "enforcement": contract.enforcement,
        "reason": decision.reason,
        "checks": decision.checks,
        "lf_action": "GrantPermissions" if decision.granted else "Deny",
        "proof_id": proof.get("proof_id"),
    }
