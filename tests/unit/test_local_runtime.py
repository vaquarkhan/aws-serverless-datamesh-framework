"""Tests for local PVDM runtime (no AWS)."""

from __future__ import annotations

from serverless_data_mesh.local.runtime import LocalPVDMRuntime


def test_local_demo_blocks_corrupt_data() -> None:
    runtime = LocalPVDMRuntime()
    result = runtime.run_demo_sequence()
    assert result["consumer"]["gate_blocked_bad_data"] is True
    assert result["phases"]["clean_write"]["outcome"] == "committed"
    assert result["phases"]["corrupt_write"]["outcome"] == "verification_failed"


def test_mesh_atomicity_on_payments_fail() -> None:
    from serverless_data_mesh.verification.backend import create_proof_generator

    runtime = LocalPVDMRuntime()
    gen, _ = create_proof_generator()
    orders = runtime.run_write(
        workload_id="orders",
        record_count=100,
        proof_generator=gen,
        defer_snapshot=True,
    )
    payments = runtime.run_write(
        workload_id="payments",
        record_count=100,
        corrupt_sink=True,
        proof_generator=gen,
        defer_snapshot=True,
    )
    mesh = runtime.finalize_mesh_transaction([orders, payments])
    assert mesh["mesh_outcome"] == "verification_failed"
    assert mesh["consumer_row_count"] == 0
