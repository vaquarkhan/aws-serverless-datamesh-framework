"""JSON Schema presence and medallion compile manifest tests."""

from __future__ import annotations

import json
from pathlib import Path


def test_schema_files_exist() -> None:
    root = Path(__file__).resolve().parents[2]
    dp = root / "schemas" / "sdm-v1-dataproductpipeline.json"
    mm = root / "schemas" / "sdm-v1-medallionmesh.json"
    assert dp.is_file() and mm.is_file()
    assert json.loads(dp.read_text())["kind"] == "DataProductPipeline" or "const" in str(dp.read_text())


def test_medallion_emits_layer_lambda_manifest(tmp_path: Path) -> None:
    from serverless_data_mesh.compile.loader import load_contract_document
    from serverless_data_mesh.compile.medallion import MedallionMeshContract
    from serverless_data_mesh.compile.medallion_emit import compile_medallion_mesh

    contract_path = (
        Path(__file__).resolve().parents[2]
        / "examples"
        / "medallion-e2e"
        / "northstar.mesh.yaml"
    )
    doc = load_contract_document(contract_path)
    assert isinstance(doc, MedallionMeshContract)
    result = compile_medallion_mesh(doc, output_dir=tmp_path)
    manifest = tmp_path / "layer_lambda.manifest.json"
    assert manifest.is_file()
    data = json.loads(manifest.read_text())
    assert "orders_bronze" in data
    assert data["orders_bronze"]["memory_mb"] >= 128
    assert result.pipeline_count == 6
