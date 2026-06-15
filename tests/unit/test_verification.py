"""Unit tests for VRP verification."""

from __future__ import annotations

import pytest

veridata_recon = pytest.importorskip("veridata_recon")
import veridata_recon as vr  # noqa: E402

from serverless_data_mesh.verification.vrp import VRPProofGenerator, validate_then_commit


@pytest.fixture
def proof_generator() -> VRPProofGenerator:
    keys = vr.generate_keypair()
    return VRPProofGenerator(
        private_key_b64=keys["private_key"],
        public_key_b64=keys["public_key"],
        salt_hex=vr.generate_salt(),
    )


def test_build_proof_passes_for_identical_records(
    proof_generator: VRPProofGenerator,
    sample_workload,
) -> None:
    records = [{"id": "1", "payload_hash": "abc"}, {"id": "2", "payload_hash": "def"}]
    proof = proof_generator.build_proof(
        source_records=records,
        sink_records=records,
        workload=sample_workload,
        chunk_start=0,
        chunk_end=2,
    )
    result = validate_then_commit(proof)
    assert result.outcome == "PASS"
    assert proof["reconciliation"]["verdict"] == "PASS"
    assert proof["proof_id"]


def test_validate_then_commit_blocks_missing_records(
    proof_generator: VRPProofGenerator,
    sample_workload,
) -> None:
    source = [{"id": "1", "payload_hash": "abc"}, {"id": "2", "payload_hash": "def"}]
    sink = [{"id": "1", "payload_hash": "abc"}]
    proof = proof_generator.build_proof(
        source_records=source,
        sink_records=sink,
        workload=sample_workload,
        chunk_start=0,
        chunk_end=2,
    )
    result = validate_then_commit(proof)
    assert result.outcome == "FAIL"
    assert result.reason is not None
