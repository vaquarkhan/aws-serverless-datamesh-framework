"""Observability: structured logs and S3 proof persistence."""

from __future__ import annotations

import json
import logging
from unittest.mock import MagicMock

import pytest

from serverless_data_mesh.local.runtime import LocalPVDMRuntime
from serverless_data_mesh.observability.structured import log_pvdm_outcome


def test_log_pvdm_outcome_emits_json(caplog: pytest.LogCaptureFixture) -> None:
    with caplog.at_level(logging.INFO):
        log_pvdm_outcome(outcome="committed", rows=100, workload_id="w1")
    assert any("pvdm_outcome" in r.message for r in caplog.records)
    payload = json.loads(caplog.records[-1].message)
    assert payload["event"] == "pvdm_outcome"
    assert payload["outcome"] == "committed"


def test_local_runtime_persists_proof_to_s3(monkeypatch: pytest.MonkeyPatch) -> None:
    put = MagicMock()
    client = MagicMock()
    client.put_object = put

    def fake_client(service: str, **_kwargs: object) -> MagicMock:
        assert service == "s3"
        return client

    import boto3

    monkeypatch.setattr(boto3, "client", fake_client)
    monkeypatch.setenv("VRP_PROOF_BUCKET", "sdm-test-proofs")

    runtime = LocalPVDMRuntime()
    from serverless_data_mesh.local.runtime import _default_workload

    workload = _default_workload(runtime.root, workload_id="s3-test", total_records=10)
    proof = {"proof_id": "p1", "reconciliation": {"verdict": "PASS"}}
    uri = runtime._persist_proof(proof, workload=workload, chunk_index=0)
    assert str(uri).startswith("s3://sdm-test-proofs/")
    put.assert_called_once()
