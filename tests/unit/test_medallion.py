"""Tests for medallion mesh compilation."""

from __future__ import annotations

from pathlib import Path

import pytest

from serverless_data_mesh.compile.loader import load_contract_document
from serverless_data_mesh.compile.medallion import MedallionMeshContract
from serverless_data_mesh.compile.medallion_emit import compile_medallion_mesh
from serverless_data_mesh.compile.medallion_validate import validate_medallion_contract


@pytest.fixture
def northstar_path() -> Path:
    return (
        Path(__file__).resolve().parents[2]
        / "examples"
        / "medallion-e2e"
        / "northstar.mesh.yaml"
    )


def test_load_northstar_medallion_mesh(northstar_path: Path) -> None:
    doc = load_contract_document(northstar_path)
    assert isinstance(doc, MedallionMeshContract)
    assert doc.organization == "northstar-retail"
    assert len(doc.domains) == 2
    assert not validate_medallion_contract(doc)


def test_compile_northstar_generates_six_pipelines(
    northstar_path: Path, tmp_path: Path
) -> None:
    doc = load_contract_document(northstar_path)
    assert isinstance(doc, MedallionMeshContract)
    result = compile_medallion_mesh(doc, output_dir=tmp_path, source_contract_path=northstar_path)

    assert result.pipeline_count == 6
    assert (tmp_path / "mesh.orchestrator.asl.json").exists()
    assert (tmp_path / "orders" / "orchestrator.asl.json").exists()
    assert (tmp_path / "orders" / "bronze" / "handler.py").exists()
    assert (tmp_path / "orders" / "silver" / "handler.py").exists()
    assert (tmp_path / "orders" / "gold" / "consumer_sla.yaml").exists()
    assert (tmp_path / "payments" / "gold" / "consumer_sla.yaml").exists()

    silver_readers = (tmp_path / "orders" / "silver" / "readers.py").read_text(encoding="utf-8")
    assert "upstream_parquet" in silver_readers
    assert "join_lines" in silver_readers or "batch_writer_upstream" in silver_readers
    bronze_readers = (tmp_path / "orders" / "bronze" / "readers.py").read_text(encoding="utf-8")
    assert "source_reader_s3_landing" in bronze_readers
    assert (tmp_path / "layer_lambda.manifest.json").exists()
