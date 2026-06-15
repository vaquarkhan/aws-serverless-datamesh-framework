"""Tests for canary promotion flow."""

from __future__ import annotations

from serverless_data_mesh.orchestration.canary import run_canary, run_canary_comparison
from serverless_data_mesh.types.workload import DataWriteWorkload, DomainTransactionBoundary


def _workload() -> DataWriteWorkload:
    boundary = DomainTransactionBoundary(
        domain_id="canary",
        source_namespace="raw",
        target_table="orders",
        partition_spec={"dt": "2026-06-14"},
    )
    return DataWriteWorkload(
        workload_id="canary",
        boundary=boundary,
        source_uri="s3://src",
        target_uri="s3://sink",
        total_records=100,
        checkpoint_bucket="s3://ckpt",
        proof_bucket="s3://proofs",
    )


def test_canary_approved_when_aligned() -> None:
    source = [{"id": str(i), "payload_hash": f"h{i}"} for i in range(100)]
    result = run_canary_comparison(
        production_source=source,
        production_sink=source,
        canary_sink=source,
        workload_factory=_workload,
    )
    assert result.outcome == "canary_approved"


def test_canary_diverged_with_drift() -> None:
    result = run_canary(record_count=1000, inject_canary_drift=True)
    assert result["outcome"] == "canary_diverged"
    assert result["promote"] is False


def test_canary_cli_path_clean() -> None:
    result = run_canary(record_count=500, inject_canary_drift=False)
    assert result["promote"] is True
