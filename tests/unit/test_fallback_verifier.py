"""Tests for pure-Python fallback verifier."""

from __future__ import annotations

from serverless_data_mesh.types.workload import DataWriteWorkload, DomainTransactionBoundary
from serverless_data_mesh.verification.fallback import FallbackProofGenerator, reconcile_multiset
from serverless_data_mesh.verification.vrp import validate_then_commit


def _workload() -> DataWriteWorkload:
    boundary = DomainTransactionBoundary(
        domain_id="test-domain",
        source_namespace="raw_test",
        target_table="test_curated",
        partition_spec={"dt": "2026-06-14"},
    )
    return DataWriteWorkload(
        workload_id="test-001",
        boundary=boundary,
        source_uri="file://source/",
        target_uri="file://target/",
        total_records=10,
        checkpoint_bucket="chk",
        proof_bucket="prf",
    )


def _rows(n: int, *, corrupt: bool = False) -> list[dict[str, str]]:
    rows = [{"id": str(i), "payload_hash": f"h{i}"} for i in range(n)]
    if corrupt and rows:
        rows[-1]["payload_hash"] = "BAD"
    return rows


def test_reconcile_identical_pass() -> None:
    recon = reconcile_multiset(
        source=_rows(5),
        sink=_rows(5),
        identity_fields=("id",),
        content_fields=("id", "payload_hash"),
    )
    assert recon["verdict"] == "PASS"


def test_reconcile_drop_fail() -> None:
    recon = reconcile_multiset(
        source=_rows(5),
        sink=_rows(4),
        identity_fields=("id",),
        content_fields=("id", "payload_hash"),
    )
    assert recon["verdict"] == "FAIL"


def test_fallback_proof_blocks_corrupt() -> None:
    gen = FallbackProofGenerator()
    workload = _workload()
    proof = gen.build_proof(
        source_records=_rows(10),
        sink_records=_rows(10, corrupt=True),
        workload=workload,
        chunk_start=0,
        chunk_end=10,
    )
    assert validate_then_commit(proof).outcome == "FAIL"


def test_local_demo_without_veridata() -> None:
    from serverless_data_mesh.local.runtime import LocalPVDMRuntime

    runtime = LocalPVDMRuntime()
    result = runtime.run_demo_sequence()
    assert result["consumer"]["gate_blocked_bad_data"] is True
