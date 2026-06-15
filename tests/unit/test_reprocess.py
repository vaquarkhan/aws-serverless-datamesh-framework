"""Tests for VRP auto-reprocessing."""

from __future__ import annotations

from serverless_data_mesh.orchestration.reprocess import attempt_vrp_repair
from serverless_data_mesh.types.workload import DataWriteWorkload, DomainTransactionBoundary
from serverless_data_mesh.verification.backend import create_proof_generator


def _workload() -> DataWriteWorkload:
    boundary = DomainTransactionBoundary(
        domain_id="orders",
        source_namespace="raw_orders",
        target_table="orders_curated",
        partition_spec={"dt": "2026-06-14"},
    )
    return DataWriteWorkload(
        workload_id="repair-test",
        boundary=boundary,
        source_uri="file:///source",
        target_uri="file:///sink",
        total_records=20,
        checkpoint_bucket="/ckpt",
        proof_bucket="/proofs",
    )


def test_auto_repair_fixes_dropped_records() -> None:
    gen, _ = create_proof_generator()
    source = [{"id": str(i), "payload_hash": f"h{i}"} for i in range(20)]
    sink = source[:15]
    sink_copy = list(sink)

    result = attempt_vrp_repair(
        source_records=source,
        sink_records=sink,
        workload=_workload(),
        chunk_start=0,
        chunk_end=20,
        proof_generator=gen,
        write_repair_fn=lambda missing: sink_copy + missing,
    )
    assert result.outcome == "repaired_pass"
    assert result.missing_before == 5
    assert result.final_verdict == "PASS"
    assert result.proof is not None


def test_auto_repair_escalates_on_mutation() -> None:
    gen, _ = create_proof_generator()
    source = [{"id": str(i), "payload_hash": f"h{i}"} for i in range(10)]
    sink = list(source)
    sink[-1] = {"id": sink[-1]["id"], "payload_hash": "CORRUPT"}

    result = attempt_vrp_repair(
        source_records=source,
        sink_records=sink,
        workload=_workload(),
        chunk_start=0,
        chunk_end=10,
        proof_generator=gen,
    )
    assert result.outcome == "escalated"
    assert result.missing_before == 0
