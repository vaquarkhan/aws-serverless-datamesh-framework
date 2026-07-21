"""Coverage-focused tests for attestation, KMS, rules gate, and UI data."""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from botocore.exceptions import ClientError

from serverless_data_mesh.attestation.pvdma import (
    DecisionAttestation,
    create_attestation,
    maybe_attest_outcome,
    persist_attestation,
    verify_attestation,
)
from serverless_data_mesh.rules.gate import apply_rules_gate, rules_gate_enabled
from serverless_data_mesh.ui import data as ui_data
from serverless_data_mesh.verification.kms_sign import (
    attach_kms_signature,
    kms_key_id_from_env,
    verify_kms_signature,
)


def test_attestation_roundtrip_and_s3(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    att = create_attestation(
        domain_id="orders",
        workload_id="w1",
        decision="quarantine",
        vrp_verdict="FAIL",
        agent_id="agent/x",
        session_id="s1",
        tool_name="mesh.run",
        prompt="fix",
        tool_args={"a": 1},
        chunk_index=2,
    )
    assert verify_attestation(att)
    assert DecisionAttestation.from_dict(att.to_dict()).domain_id == "orders"

    put = MagicMock()
    client = MagicMock()
    client.put_object = put
    monkeypatch.delenv("VRP_PROOF_BUCKET", raising=False)
    with pytest.raises(ValueError):
        persist_attestation(att)

    uri = persist_attestation(att, bucket="bkt", s3_client=client)
    assert uri.startswith("s3://bkt/")
    put.assert_called_once()

    local = persist_attestation(att, local_dir=str(tmp_path))
    assert Path(local).is_file()


def test_maybe_attest_disabled_and_persist_error(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("SDM_ATTESTATION_ENABLED", "0")
    assert (
        maybe_attest_outcome(
            domain_id="d",
            workload_id="w",
            decision="allow_commit",
            vrp_verdict="PASS",
            local_dir=str(tmp_path),
        )
        is None
    )
    monkeypatch.setenv("SDM_ATTESTATION_ENABLED", "1")
    monkeypatch.delenv("VRP_PROOF_BUCKET", raising=False)
    # no bucket and no local_dir -> persist error captured
    out = maybe_attest_outcome(
        domain_id="d",
        workload_id="w",
        decision="deny",
        vrp_verdict="FAIL",
        enabled=True,
    )
    assert out is not None
    assert "persist_error" in out or out.get("uri")


def test_kms_env_and_verify_absent(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("VRP_KMS_KEY_ID", raising=False)
    monkeypatch.delenv("VRP_KMS_KEY_ARN", raising=False)
    assert kms_key_id_from_env() is None
    assert verify_kms_signature({"proof_id": "x"}) is True


def test_kms_verify_digest_mismatch(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("VRP_KMS_KEY_ID", "alias/x")
    client = MagicMock()
    client.sign.return_value = {
        "KeyId": "k",
        "Signature": b"sig",
        "SigningAlgorithm": "RSASSA_PSS_SHA_256",
    }
    proof = attach_kms_signature({"proof_id": "p", "a": 1}, kms_client=client)
    proof["a"] = 2  # tamper after sign
    assert verify_kms_signature(proof, kms_client=client) is False


def test_kms_sign_other_client_error(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("VRP_KMS_KEY_ID", "alias/x")
    client = MagicMock()
    client.sign.side_effect = ClientError(
        {"Error": {"Code": "AccessDeniedException", "Message": "no"}},
        "Sign",
    )
    out = attach_kms_signature({"proof_id": "p"}, kms_client=client)
    assert "kms_signature" not in out


def test_rules_gate_enabled_flags(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("SDM_RULES_GATE", raising=False)
    monkeypatch.delenv("SPARKRULES_DRL", raising=False)
    monkeypatch.delenv("SPARKRULES_DRL_S3_URI", raising=False)
    assert rules_gate_enabled() is False
    monkeypatch.setenv("SDM_RULES_GATE", "true")
    assert rules_gate_enabled() is True
    monkeypatch.setenv("SDM_RULES_GATE", "0")
    monkeypatch.setenv("SPARKRULES_DRL", "rule X when then end")
    assert rules_gate_enabled() is True


def test_apply_rules_gate_passthrough_and_connector(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("SDM_RULES_GATE", raising=False)
    monkeypatch.delenv("SPARKRULES_DRL", raising=False)
    monkeypatch.delenv("SPARKRULES_DRL_S3_URI", raising=False)
    rows = [{"id": "1"}]
    out, audit = apply_rules_gate(rows)
    assert out == rows and audit == []

    connector = MagicMock()
    connector.apply_chunk.return_value = ([{"id": "1", "ok": True}], ["a"])
    connector.quality_gate.return_value = True
    connector.policy_id = "p"
    enriched, audit = apply_rules_gate(rows, connector=connector)
    assert enriched[0]["ok"] is True
    assert audit == ["a"]

    connector.quality_gate.return_value = False
    from serverless_data_mesh.exceptions import RuleEvaluationError

    with pytest.raises(RuleEvaluationError):
        apply_rules_gate(rows, connector=connector)


def test_ui_build_dashboard_and_demo(tmp_path: Path) -> None:
    # minimal generated mesh layout
    (tmp_path / "orders" / "bronze").mkdir(parents=True)
    (tmp_path / "orders" / "bronze" / "handler.py").write_text("# h", encoding="utf-8")
    (tmp_path / "orders" / "bronze" / "readers.py").write_text(
        "def source_reader(s,e):\n    return []\n",
        encoding="utf-8",
    )
    (tmp_path / "orders" / "bronze" / "mesh.pipeline.yaml").write_text(
        "product_id: orders_bronze\nruntime:\n  engine: pyarrow\n",
        encoding="utf-8",
    )
    (tmp_path / "mesh.manifest.json").write_text(
        json.dumps({"organization": "demo", "domains": ["orders"], "pipeline_count": 1}),
        encoding="utf-8",
    )
    (tmp_path / "mesh.orchestrator.asl.json").write_text("{}", encoding="utf-8")
    (tmp_path / "layer_lambda.manifest.json").write_text(
        json.dumps({"layers": [{"domain": "orders", "layer": "bronze"}]}),
        encoding="utf-8",
    )

    # seed a proof + attestation under proofs
    proof_dir = tmp_path / "proofs" / "orders" / "wl" / "proofs"
    proof_dir.mkdir(parents=True)
    (proof_dir / "chunk-000000.vrp.json").write_text(
        json.dumps(
            {
                "proof_id": "abc1234567890",
                "created_at": "2026-01-01T00:00:00",
                "reconciliation": {"verdict": "PASS", "sink_count": 10, "missing": []},
            }
        ),
        encoding="utf-8",
    )
    att_dir = tmp_path / "proofs" / "attestations" / "orders" / "wl"
    att_dir.mkdir(parents=True)
    (att_dir / "x.pvdma.json").write_text(
        json.dumps(
            {
                "attestation_id": "pvdma-1",
                "decision": "allow_commit",
                "vrp_verdict": "PASS",
                "domain_id": "orders",
                "agent_id": "human",
            }
        ),
        encoding="utf-8",
    )

    dash = ui_data.build_dashboard(tmp_path)
    assert dash["kpis"]["pipelines"] >= 1
    assert dash["trust"]["mode"] == "live-proofs"
    assert dash["organization"] == "demo"
    assert dash["tutorial"]

    result = ui_data.run_local_demo(tmp_path)
    assert result["ok"] is True
    assert (tmp_path / ".ui-demo-root").is_file()


def test_attestation_missing_hash_and_reseal() -> None:
    att = create_attestation(
        domain_id="d", workload_id="w", decision="allow_commit", vrp_verdict="PASS"
    )
    raw = att.to_dict()
    raw.pop("content_hash", None)
    assert verify_attestation(raw) is False


def test_attestation_reseal_on_persist(tmp_path: Path) -> None:
    att = create_attestation(
        domain_id="d", workload_id="w", decision="allow_commit", vrp_verdict="PASS"
    )
    att.content_hash = None
    path = persist_attestation(att, local_dir=str(tmp_path))
    assert Path(path).is_file()
    assert att.content_hash


def test_kms_generic_exception_and_encrypt_fail(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("VRP_KMS_KEY_ID", "alias/x")
    client = MagicMock()
    client.sign.side_effect = RuntimeError("boom")
    out = attach_kms_signature({"proof_id": "p"}, kms_client=client)
    assert "kms_signature" not in out

    client2 = MagicMock()
    client2.sign.side_effect = ClientError(
        {"Error": {"Code": "InvalidKeyUsageException", "Message": "x"}},
        "Sign",
    )
    client2.encrypt.side_effect = RuntimeError("encrypt fail")
    out2 = attach_kms_signature({"proof_id": "p2"}, kms_client=client2)
    assert "kms_signature" not in out2


def test_kms_verify_exception(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("VRP_KMS_KEY_ID", "alias/x")
    client = MagicMock()
    client.sign.return_value = {
        "KeyId": "k",
        "Signature": b"sig",
        "SigningAlgorithm": "RSASSA_PSS_SHA_256",
    }
    proof = attach_kms_signature({"proof_id": "p"}, kms_client=client)
    client.verify.side_effect = RuntimeError("verify boom")
    assert verify_kms_signature(proof, kms_client=client) is False


def test_rules_gate_from_env_mocked(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("SDM_RULES_GATE", "1")
    fake = MagicMock()
    fake.apply_chunk.return_value = ([{"id": "1"}], [])
    if hasattr(fake, "quality_gate"):
        delattr(fake, "quality_gate")

    with patch(
        "serverless_data_mesh.rules.SparkRulesConnector.from_environment",
        return_value=fake,
    ):
        out, audit = apply_rules_gate([{"id": "1"}])
        assert out == [{"id": "1"}]
        assert audit == []


def test_ui_pipeline_not_implemented_reader(tmp_path: Path) -> None:
    (tmp_path / "payments" / "silver").mkdir(parents=True)
    (tmp_path / "payments" / "silver" / "readers.py").write_text(
        "def source_reader(s, e):\n    raise NotImplementedError\n",
        encoding="utf-8",
    )
    (tmp_path / "mesh.manifest.json").write_text(
        json.dumps({"pipeline_count": 1}),
        encoding="utf-8",
    )
    (tmp_path / "mesh.orchestrator.asl.json").write_text("{}", encoding="utf-8")
    dash = ui_data.build_dashboard(tmp_path)
    assert any(not p["readers_ready"] for p in dash["pipelines"])


def test_ui_trust_fail_detail_and_bad_json(tmp_path: Path) -> None:
    proof_dir = tmp_path / "proofs" / "inv" / "wl" / "proofs"
    proof_dir.mkdir(parents=True)
    (proof_dir / "chunk-000000.vrp.json").write_text(
        json.dumps(
            {
                "proof_id": "failproof123456",
                "created_at": "2026-01-01T00:00:00",
                "reconciliation": {
                    "verdict": "FAIL",
                    "sink_count": 0,
                    "missing": ["a", "b"],
                    "mutated": ["c"],
                    "duplicated": ["d"],
                },
            }
        ),
        encoding="utf-8",
    )
    (proof_dir / "bad.vrp.json").write_text("{not-json", encoding="utf-8")
    (proof_dir / "array.vrp.json").write_text("[]", encoding="utf-8")
    att_dir = tmp_path / "proofs" / "attestations"
    att_dir.mkdir(parents=True)
    (att_dir / "bad.pvdma.json").write_text("[1,2,3]", encoding="utf-8")
    (tmp_path / "mesh.manifest.json").write_text(
        json.dumps({"pipeline_count": 0, "domains": []}),
        encoding="utf-8",
    )
    (tmp_path / "mesh.orchestrator.asl.json").write_text("{}", encoding="utf-8")
    # point search via marker
    (tmp_path / ".ui-demo-root").write_text(str(tmp_path / "proofs"), encoding="utf-8")
    dash = ui_data.build_dashboard(tmp_path)
    assert dash["trust"]["rows"]
    assert any(r["status"] == "FAIL" for r in dash["trust"]["rows"])
