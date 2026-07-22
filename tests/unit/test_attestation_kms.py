"""Unit tests for PVDM-A attestation and optional KMS signing."""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from serverless_data_mesh.attestation import (
    create_attestation,
    persist_attestation,
    verify_attestation,
)
from serverless_data_mesh.verification.kms_sign import attach_kms_signature, verify_kms_signature


def test_create_and_verify_attestation(tmp_path) -> None:
    att = create_attestation(
        domain_id="orders",
        workload_id="wl-1",
        decision="allow_commit",
        vrp_verdict="PASS",
        agent_id="agent/demo",
        vrp_proof_uri="s3://proofs/x.vrp.json",
        vrp_proof_id="abc123",
        prompt="commit orders partition",
        tool_args={"table": "orders_curated"},
        chunk_index=0,
    )
    assert att.attestation_id.startswith("pvdma-")
    assert att.content_hash and att.content_hash.startswith("sha256:")
    assert verify_attestation(att) is True

    path = persist_attestation(att, local_dir=str(tmp_path))
    assert path.endswith(".pvdma.json")
    data = __import__("json").loads(__import__("pathlib").Path(path).read_text(encoding="utf-8"))
    assert verify_attestation(data) is True


def test_tampered_attestation_fails_verify() -> None:
    att = create_attestation(
        domain_id="orders",
        workload_id="wl-2",
        decision="deny",
        vrp_verdict="FAIL",
    )
    payload = att.to_dict()
    payload["decision"] = "allow_commit"
    assert verify_attestation(payload) is False


def test_invalid_decision_rejected() -> None:
    with pytest.raises(ValueError):
        create_attestation(
            domain_id="orders",
            workload_id="wl-3",
            decision="maybe",
            vrp_verdict="PASS",
        )


def test_kms_sign_noop_without_key(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("VRP_KMS_KEY_ID", raising=False)
    monkeypatch.delenv("VRP_KMS_KEY_ARN", raising=False)
    proof = {"proof_id": "p1", "reconciliation": {"verdict": "PASS"}}
    out = attach_kms_signature(proof)
    assert "kms_signature" not in out


def test_kms_sign_attaches_signature(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("VRP_KMS_KEY_ID", "alias/sdm-vrp")
    client = MagicMock()
    client.sign.return_value = {
        "KeyId": "arn:aws:kms:us-east-1:123:key/abc",
        "Signature": b"sig-bytes",
        "SigningAlgorithm": "RSASSA_PSS_SHA_256",
    }
    proof = {"proof_id": "p1", "reconciliation": {"verdict": "PASS"}, "salt": "abc"}
    out = attach_kms_signature(proof, kms_client=client)
    assert out["kms_signature"]["mode"] == "sign"
    assert out["kms_signature"]["signature_b64"]
    client.verify.return_value = {"SignatureValid": True}
    assert verify_kms_signature(out, kms_client=client) is True


def test_kms_encrypt_digest_fallback(monkeypatch: pytest.MonkeyPatch) -> None:
    from botocore.exceptions import ClientError

    monkeypatch.setenv("VRP_KMS_KEY_ID", "alias/sdm-symmetric")
    client = MagicMock()
    err = ClientError(
        {"Error": {"Code": "InvalidKeyUsageException", "Message": "not for sign"}},
        "Sign",
    )
    client.sign.side_effect = err
    client.encrypt.return_value = {"CiphertextBlob": b"cipher"}
    proof = {"proof_id": "p2", "reconciliation": {"verdict": "PASS"}}
    out = attach_kms_signature(proof, kms_client=client)
    assert out["kms_signature"]["mode"] == "encrypt_digest"
    assert verify_kms_signature(out, kms_client=client) is True
