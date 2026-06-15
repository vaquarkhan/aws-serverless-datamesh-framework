"""Backstage catalog export tests."""

from __future__ import annotations

from pathlib import Path

from serverless_data_mesh.catalog_export.backstage import export_backstage_catalog


def test_export_medallion_entities(tmp_path: Path) -> None:
    contract = (
        Path(__file__).resolve().parents[2]
        / "examples"
        / "medallion-e2e"
        / "northstar.mesh.yaml"
    )
    paths = export_backstage_catalog(contract, output_dir=tmp_path)
    assert len(paths) >= 7  # 6 layers + 1 system
    assert any(p.name == "mesh-system-catalog-info.yaml" for p in paths)
    text = paths[0].read_text(encoding="utf-8")
    assert "backstage.io/v1alpha1" in text
    assert "serverless-data-mesh" in text


def test_export_single_pipeline(tmp_path: Path) -> None:
    contract = (
        Path(__file__).resolve().parents[2]
        / "examples"
        / "contracts"
        / "payments.mesh.pipeline.yaml"
    )
    paths = export_backstage_catalog(contract, output_dir=tmp_path)
    assert len(paths) == 1
    assert "payments" in paths[0].name
