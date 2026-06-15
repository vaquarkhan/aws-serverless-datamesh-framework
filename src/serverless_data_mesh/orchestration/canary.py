"""Canary write comparison using VRP proof divergence (roadmap 11/10)."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable

from serverless_data_mesh.verification.backend import create_proof_generator
from serverless_data_mesh.verification.vrp import validate_then_commit


@dataclass(frozen=True, slots=True)
class CanaryResult:
    outcome: str  # canary_approved | canary_diverged
    production_verdict: str
    canary_verdict: str
    divergence_pct: float
    message: str


def run_canary_comparison(
    *,
    production_source: list[dict[str, Any]],
    production_sink: list[dict[str, Any]],
    canary_sink: list[dict[str, Any]],
    workload_factory: Callable[[], Any],
    max_divergence_pct: float = 1.0,
) -> CanaryResult:
    """Compare production vs canary VRP proofs before promoting a schema/logic change."""
    gen, _ = create_proof_generator()
    workload = workload_factory()
    n = len(production_source)

    prod_proof = gen.build_proof(
        source_records=production_source,
        sink_records=production_sink,
        workload=workload,
        chunk_start=0,
        chunk_end=n,
    )
    canary_proof = gen.build_proof(
        source_records=production_source,
        sink_records=canary_sink,
        workload=workload,
        chunk_start=0,
        chunk_end=n,
    )
    prod_v = validate_then_commit(prod_proof).outcome
    canary_v = validate_then_commit(canary_proof).outcome

    if prod_v != "PASS" or canary_v != "PASS":
        return CanaryResult(
            outcome="canary_diverged",
            production_verdict=prod_v,
            canary_verdict=canary_v,
            divergence_pct=100.0,
            message="One or both proofs failed VRP",
        )

    prod_count = prod_proof["reconciliation"].get("sink_count", n)
    canary_count = canary_proof["reconciliation"].get("sink_count", n)
    divergence = abs(canary_count - prod_count) / max(prod_count, 1) * 100

    if divergence > max_divergence_pct:
        return CanaryResult(
            outcome="canary_diverged",
            production_verdict=prod_v,
            canary_verdict=canary_v,
            divergence_pct=round(divergence, 2),
            message=f"Row count divergence {divergence:.2f}% exceeds {max_divergence_pct}%",
        )

    return CanaryResult(
        outcome="canary_approved",
        production_verdict=prod_v,
        canary_verdict=canary_v,
        divergence_pct=round(divergence, 2),
        message="Canary within tolerance",
    )


def run_canary(
    *,
    record_count: int = 1000,
    inject_canary_drift: bool = False,
    max_divergence_pct: float = 1.0,
) -> dict[str, object]:
    """End-to-end canary promotion check with sample production vs canary sinks."""
    from serverless_data_mesh.types.workload import DataWriteWorkload, DomainTransactionBoundary

    source = [{"id": str(i), "payload_hash": f"h{i}"} for i in range(record_count)]
    production_sink = list(source)
    canary_sink = list(source)
    if inject_canary_drift:
        canary_sink = canary_sink[: int(record_count * 0.98)]

    boundary = DomainTransactionBoundary(
        domain_id="canary-demo",
        source_namespace="raw_canary",
        target_table="orders_curated",
        partition_spec={"dt": "2026-06-14"},
    )
    workload = DataWriteWorkload(
        workload_id="canary-001",
        boundary=boundary,
        source_uri="s3://publisher/source/",
        target_uri="s3://publisher/lakehouse/orders_curated/",
        total_records=record_count,
        checkpoint_bucket="s3://steward/checkpoints",
        proof_bucket="s3://steward/proofs",
    )

    result = run_canary_comparison(
        production_source=source,
        production_sink=production_sink,
        canary_sink=canary_sink,
        workload_factory=lambda: workload,
        max_divergence_pct=max_divergence_pct,
    )
    return {
        "outcome": result.outcome,
        "production_verdict": result.production_verdict,
        "canary_verdict": result.canary_verdict,
        "divergence_pct": result.divergence_pct,
        "message": result.message,
        "promote": result.outcome == "canary_approved",
    }
