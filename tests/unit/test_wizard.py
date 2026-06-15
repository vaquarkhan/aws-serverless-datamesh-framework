"""Tests for mesh wizard (new, validate, doctor, apply)."""

from __future__ import annotations

from pathlib import Path

import pytest

from serverless_data_mesh.compile.wizard import (
    apply_mesh,
    doctor_generated,
    scaffold_new,
    validate_contract_file,
)


def test_scaffold_medallion_starter(tmp_path: Path) -> None:
    result = scaffold_new("medallion", output_dir=tmp_path / "mesh")
    assert result.contract_path.is_file()
    assert "MedallionMesh" in result.contract_path.read_text(encoding="utf-8")
    assert not validate_contract_file(result.contract_path)


def test_apply_medallion_starter(tmp_path: Path) -> None:
    result = scaffold_new("medallion", output_dir=tmp_path / "mesh")
    applied = apply_mesh(result.contract_path, output_dir=tmp_path / "mesh" / "generated")
    assert applied.pipeline_count == 3
    assert (applied.output_root / "GETTING_STARTED.md").exists()
    assert applied.doctor.readers_total == 3
    assert len(applied.doctor.readers_pending) == 3


def test_doctor_detects_pending_readers(tmp_path: Path) -> None:
    result = scaffold_new("medallion", output_dir=tmp_path / "m")
    applied = apply_mesh(result.contract_path, output_dir=tmp_path / "gen")
    report = doctor_generated(applied.output_root)
    assert report.ready_to_deploy is False
    assert report.pipeline_count == 3


def test_validate_northstar() -> None:
    path = (
        Path(__file__).resolve().parents[2]
        / "examples"
        / "medallion-e2e"
        / "northstar.mesh.yaml"
    )
    if not path.is_file():
        pytest.skip("northstar example not present")
    assert not validate_contract_file(path)
