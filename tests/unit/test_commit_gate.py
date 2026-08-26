"""Unit tests for PVDM Metadata commit gate and paper primitives."""

from __future__ import annotations

from pathlib import Path

import pytest

from serverless_data_mesh.verification.commit_gate import (
    bind_file_digests,
    digest_bytes,
    metadata_commit_gate,
    source_as_sink_allowed,
)
from serverless_data_mesh.verification.pvdm_primitives import (
    build_pvdm_binding,
    multiset_hash,
    require_steward_keys,
)


def test_digest_bytes_stable() -> None:
    assert digest_bytes(b"abc") == digest_bytes(b"abc")
    assert digest_bytes(b"abc") != digest_bytes(b"abd")


def test_keyed_mset_detects_drop_and_duplicate() -> None:
    key, _ = require_steward_keys()
    base = [{"id": "1", "v": "a"}, {"id": "2", "v": "b"}]
    dropped = [{"id": "1", "v": "a"}]
    duped = base + [{"id": "1", "v": "a"}]
    h0 = multiset_hash(base, key)
    assert h0 != multiset_hash(dropped, key)
    assert h0 != multiset_hash(duped, key)
    assert h0 == multiset_hash(list(reversed(base)), key)


def test_bind_and_metadata_gate_pass(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("SDM_ALLOW_UNREADABLE_STAGING", raising=False)
    monkeypatch.setenv("SDM_FILE_DIGEST_GATE", "1")
    monkeypatch.setenv("SDM_NONCE_LEDGER_DIR", str(tmp_path / "nonces"))
    path = tmp_path / "part-000.jsonl"
    path.write_text('{"id":"1"}\n', encoding="utf-8")
    uri = str(path.resolve())
    digests = bind_file_digests([uri])
    vrp_key, steward_key = require_steward_keys()
    rows = [{"id": "1"}]
    binding = build_pvdm_binding(
        workload_id="w1",
        chunk_id="0-1",
        target="s3://lake/t",
        partition="dt=1",
        intended_rows=rows,
        written_rows=rows,
        identity_fields=("id",),
        file_digests=digests,
        vrp_key=vrp_key,
        steward_key=steward_key,
    )
    proof = {
        "reconciliation": {"verdict": "PASS"},
        "physical_file_digests": digests,
        "pvdm_binding": binding.to_dict(),
    }
    result = metadata_commit_gate(
        verification_passed=True,
        parquet_paths=[uri],
        proofs=[proof],
        expected_target="s3://lake/t",
    )
    assert result.outcome == "PASS"


def test_metadata_gate_blocks_without_pass(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("SDM_FILE_DIGEST_GATE", "1")
    path = tmp_path / "part.jsonl"
    path.write_bytes(b"x")
    uri = str(path.resolve())
    digests = bind_file_digests([uri])
    result = metadata_commit_gate(
        verification_passed=False,
        parquet_paths=[uri],
        bound_digests=digests,
    )
    assert result.outcome == "FAIL"


def test_metadata_gate_detects_toctou_tamper(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("SDM_FILE_DIGEST_GATE", "1")
    monkeypatch.setenv("SDM_NONCE_LEDGER_DIR", str(tmp_path / "nonces"))
    path = tmp_path / "part.jsonl"
    path.write_bytes(b"clean")
    uri = str(path.resolve())
    digests = bind_file_digests([uri])
    vrp_key, steward_key = require_steward_keys()
    rows = [{"id": "1"}]
    binding = build_pvdm_binding(
        workload_id="w1",
        chunk_id="0-1",
        target="s3://lake/t",
        partition="dt=1",
        intended_rows=rows,
        written_rows=rows,
        identity_fields=("id",),
        file_digests=digests,
        vrp_key=vrp_key,
        steward_key=steward_key,
    )
    proof = {
        "reconciliation": {"verdict": "PASS"},
        "physical_file_digests": digests,
        "pvdm_binding": binding.to_dict(),
    }
    path.write_bytes(b"tampered")
    result = metadata_commit_gate(
        verification_passed=True,
        parquet_paths=[uri],
        proofs=[proof],
        expected_target="s3://lake/t",
        burn_nonces=False,
    )
    assert result.outcome == "FAIL"
    assert result.reason and "TOCTOU" in result.reason


def test_metadata_gate_blocks_target_misdirection(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("SDM_FILE_DIGEST_GATE", "1")
    monkeypatch.setenv("SDM_NONCE_LEDGER_DIR", str(tmp_path / "nonces2"))
    path = tmp_path / "part.jsonl"
    path.write_bytes(b"x")
    uri = str(path.resolve())
    digests = bind_file_digests([uri])
    vrp_key, steward_key = require_steward_keys()
    rows = [{"id": "1"}]
    binding = build_pvdm_binding(
        workload_id="w1",
        chunk_id="0-1",
        target="s3://lake/other",
        partition="dt=1",
        intended_rows=rows,
        written_rows=rows,
        identity_fields=("id",),
        file_digests=digests,
        vrp_key=vrp_key,
        steward_key=steward_key,
    )
    proof = {
        "reconciliation": {"verdict": "PASS"},
        "physical_file_digests": digests,
        "pvdm_binding": binding.to_dict(),
    }
    result = metadata_commit_gate(
        verification_passed=True,
        parquet_paths=[uri],
        proofs=[proof],
        expected_target="s3://lake/t",
        burn_nonces=False,
    )
    assert result.outcome == "FAIL"
    assert result.reason and "target mismatch" in result.reason


def test_metadata_gate_blocks_missing_digests(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("SDM_ALLOW_UNREADABLE_STAGING", raising=False)
    monkeypatch.setenv("SDM_FILE_DIGEST_GATE", "1")
    monkeypatch.setenv("SDM_ALLOW_UNSIGNED_PROOF", "1")
    result = metadata_commit_gate(
        verification_passed=True,
        parquet_paths=["/tmp/missing.parquet"],
        bound_digests=[],
        proofs=[{"reconciliation": {"verdict": "PASS"}}],
        burn_nonces=False,
    )
    assert result.outcome == "FAIL"


def test_source_as_sink_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("SDM_ALLOW_SOURCE_AS_SINK", raising=False)
    assert source_as_sink_allowed() is False
    monkeypatch.setenv("SDM_ALLOW_SOURCE_AS_SINK", "1")
    assert source_as_sink_allowed() is True
