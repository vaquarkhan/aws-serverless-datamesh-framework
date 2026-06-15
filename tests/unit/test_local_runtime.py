"""Tests for local PVDM runtime (no AWS)."""

from __future__ import annotations

import pytest

veridata = pytest.importorskip("veridata_recon")

from serverless_data_mesh.local.runtime import LocalPVDMRuntime


@pytest.mark.eval
def test_local_demo_blocks_corrupt_data() -> None:
    runtime = LocalPVDMRuntime()
    result = runtime.run_demo_sequence()
    assert result["consumer"]["gate_blocked_bad_data"] is True
    assert result["phases"]["clean_write"]["outcome"] == "committed"
    assert result["phases"]["corrupt_write"]["outcome"] == "verification_failed"


@pytest.mark.eval
def test_mesh_atomicity_on_payments_fail() -> None:
    runtime = LocalPVDMRuntime()
    import veridata_recon as vr
    from serverless_data_mesh.verification.vrp import VRPProofGenerator

    keys = vr.generate_keypair()
    gen = VRPProofGenerator(
        private_key_b64=keys["private_key"],
        public_key_b64=keys["public_key"],
        salt_hex=vr.generate_salt(),
    )
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
