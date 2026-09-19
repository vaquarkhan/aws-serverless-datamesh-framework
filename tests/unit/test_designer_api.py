"""Tests for mesh designer contract helpers."""

from __future__ import annotations

from pathlib import Path

from serverless_data_mesh.ui.designer_api import (
    contract_to_yaml,
    save_designer_contract,
    validate_designer_contract,
)


def _sample_contract() -> dict:
    return {
        "apiVersion": "sdm/v1",
        "kind": "MedallionMesh",
        "metadata": {"organization": "xyz-org", "description": "designer test"},
        "spec": {
            "name_prefix": "xyz",
            "aws_region": "us-east-2",
            "accounts": {
                "producer": "111111111111",
                "steward": "222222222222",
                "publisher": "333333333333",
            },
            "domains": [
                {
                    "domain_id": "xyz",
                    "owner_team": "xyz-platform",
                    "description": "xyz medallion",
                    "schedule_cron": "0 2 * * *",
                    "layers": {
                        "bronze": {
                            "target_table": "xyz_bronze",
                            "source_namespace": "bronze_xyz",
                            "identity_fields": ["id"],
                            "content_fields": ["id", "raw_json"],
                            "runtime": {"engine": "pyarrow", "lambda_memory_mb": 3008},
                            "transforms": ["landing_copy"],
                        },
                        "silver": {
                            "target_table": "xyz_silver",
                            "source_namespace": "silver_xyz",
                            "upstream_layer": "bronze",
                            "identity_fields": ["id"],
                            "content_fields": ["id", "payload_hash"],
                            "runtime": {
                                "engine": "pyspark",
                                "package_extras": "spark",
                                "lambda_memory_mb": 10240,
                            },
                            "transforms": ["curate"],
                        },
                        "gold": {
                            "target_table": "xyz_gold_daily",
                            "source_namespace": "gold_xyz",
                            "upstream_layer": "silver",
                            "identity_fields": ["id"],
                            "content_fields": ["id", "payload_hash"],
                            "runtime": {
                                "engine": "pyspark",
                                "package_extras": "spark",
                                "lambda_memory_mb": 10240,
                            },
                            "transforms": ["curate"],
                            "consumer_slas": [
                                {
                                    "consumer_id": "analytics-team",
                                    "target_table": "xyz_gold_daily",
                                    "max_freshness_minutes": 60,
                                    "min_completeness_pct": 99.0,
                                    "required_columns": ["id"],
                                    "enforcement": "vrp_backed",
                                }
                            ],
                        },
                    },
                }
            ],
        },
    }


def test_validate_designer_contract_ok() -> None:
    result = validate_designer_contract(_sample_contract())
    assert result["ok"] is True
    assert result["pipeline_estimate"] == 3


def test_contract_to_yaml_contains_kind() -> None:
    text = contract_to_yaml(_sample_contract())
    assert "MedallionMesh" in text
    assert "domain_id: xyz" in text


def test_save_designer_contract(tmp_path: Path) -> None:
    generated = tmp_path / "generated"
    generated.mkdir()
    result = save_designer_contract(
        generated_root=generated,
        contract=_sample_contract(),
        fmt="both",
    )
    assert result["ok"] is True
    assert Path(result["contract_yaml"]).name == "mesh.yaml"
    assert Path(result["contract_yaml"]).is_file()
    assert Path(result["contract_json"]).is_file()
    assert "apply --contract" in result["apply_command"]


def test_save_and_apply_designer_contract(tmp_path: Path) -> None:
    from serverless_data_mesh.ui.designer_api import save_and_apply_designer_contract

    generated = tmp_path / "generated"
    generated.mkdir()
    result = save_and_apply_designer_contract(
        generated_root=generated,
        contract=_sample_contract(),
    )
    assert result["ok"] is True
    assert result["pipeline_count"] == 3
    assert (tmp_path / "mesh.yaml").is_file()
    assert (generated / "xyz" / "bronze").is_dir()
