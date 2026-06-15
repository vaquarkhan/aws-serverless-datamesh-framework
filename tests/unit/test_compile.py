"""Tests for metadata-driven pipeline compile."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from serverless_data_mesh.compile.emit import compile_pipeline
from serverless_data_mesh.compile.loader import load_contract
from serverless_data_mesh.compile.runtime import build_workload_from_contract
from serverless_data_mesh.compile.validate import validate_contract


@pytest.fixture
def payments_contract_path() -> Path:
    root = Path(__file__).resolve().parents[2]
    return root / "examples" / "contracts" / "payments.mesh.pipeline.yaml"


def test_load_and_validate_payments_contract(payments_contract_path: Path) -> None:
    contract = load_contract(payments_contract_path)
    assert contract.domain_id == "payments"
    assert contract.boundary.target_table == "fact_payments"
    assert not validate_contract(contract)


def test_compile_pipeline_writes_artifacts(
    payments_contract_path: Path, tmp_path: Path
) -> None:
    contract = load_contract(payments_contract_path)
    result = compile_pipeline(contract, output_dir=tmp_path)
    root = result.output_root
    assert (root / "mesh.pipeline.yaml").exists()
    assert (root / "handler.py").exists()
    manifest = json.loads((root / "pipeline.manifest.json").read_text(encoding="utf-8"))
    assert manifest["lambda_handler"] == "handler.lambda_handler"
    assert (root / "readers.py").exists()
    assert (root / "pipeline_config.py").exists()
    assert (root / "step_function.asl.json").exists()
    assert (root / "terraform/eventbridge.tf").exists()
    assert (root / "pipeline.manifest.json").exists()
    assert "payments" in result.files_written[0] or "mesh.pipeline.yaml" in result.files_written


def test_build_workload_from_compiled_contract(
    payments_contract_path: Path, tmp_path: Path
) -> None:
    contract = load_contract(payments_contract_path)
    compile_pipeline(contract, output_dir=tmp_path)
    config_text = (tmp_path / "payments" / "pipeline_config.py").read_text(encoding="utf-8")
    assert "payment_id" in config_text
    workload = build_workload_from_contract(
        {
            "workload_id": "w1",
            "total_records": 50,
            "partition_spec": {"dt": "2026-06-14"},
            "checkpoint_bucket": "s3://steward/checkpoints",
            "proof_bucket": "s3://steward/proofs",
        },
        contract,
    )
    assert workload.boundary.target_table == "fact_payments"
    assert workload.identity_fields == ("payment_id",)


def test_validate_rejects_bad_api_version(payments_contract_path: Path) -> None:
    contract = load_contract(payments_contract_path)
    bad = contract.to_dict()
    bad["apiVersion"] = "sdm/v99"
    from serverless_data_mesh.compile.contract import MeshPipelineContract

    parsed = MeshPipelineContract.from_dict(bad)
    errors = validate_contract(parsed)
    assert any("apiVersion" in e for e in errors)
