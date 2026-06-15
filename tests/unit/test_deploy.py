"""Tests for deploy CLI orchestration."""

from __future__ import annotations

from pathlib import Path

from serverless_data_mesh.deploy.runner import deploy_mesh, result_to_dict


def test_deploy_dry_run_skips_terraform(tmp_path: Path) -> None:
    contract = (
        Path(__file__).resolve().parents[2]
        / "examples"
        / "medallion-e2e"
        / "northstar.mesh.yaml"
    )
    out = tmp_path / "generated"
    result = deploy_mesh(
        contract=contract,
        output=out,
        skip_terraform=True,
        dry_run=True,
    )
    assert result.generated_path == out.resolve()
    assert (out / "layer_lambda.manifest.json").is_file()
    d = result_to_dict(result)
    assert d["terraform_applied"] is False
