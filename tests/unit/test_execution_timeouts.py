"""Unit tests for 15–90 min segment + durable timeout profile."""

from __future__ import annotations

from pathlib import Path

import pytest

from serverless_data_mesh.execution_timeouts import (
    LMI_SEGMENT_MAX_SECONDS,
    ON_DEMAND_SEGMENT_MAX_SECONDS,
    SYNC_INVOKE_MAX_SECONDS,
    build_execution_timeout_profile,
    resolve_lambda_timeout,
    resolve_sfn_invoke_timeout,
    validate_lmi_capacity_provider,
)


def test_on_demand_accepts_15_min_segment() -> None:
    profile = build_execution_timeout_profile(lambda_timeout_seconds=900)
    assert profile.lambda_timeout_seconds == 900
    assert profile.segment_timeout_max == ON_DEMAND_SEGMENT_MAX_SECONDS
    assert profile.enable_lambda_managed_instances is False


def test_on_demand_rejects_90_min_segment() -> None:
    with pytest.raises(ValueError, match="on-demand"):
        build_execution_timeout_profile(lambda_timeout_seconds=5400)


def test_lmi_accepts_90_min_segment() -> None:
    profile = build_execution_timeout_profile(
        lambda_timeout_seconds=5400,
        durable_execution_timeout_seconds=10_800,
        enable_lambda_managed_instances=True,
        lambda_managed_instances_capacity_provider_arn=(
            "arn:aws:lambda:us-east-2:123456789012:capacity-provider:sdm"
        ),
    )
    assert profile.lambda_timeout_seconds == LMI_SEGMENT_MAX_SECONDS
    assert profile.segment_timeout_max == LMI_SEGMENT_MAX_SECONDS
    assert profile.enable_lambda_managed_instances is True


def test_lmi_requires_capacity_provider_arn() -> None:
    with pytest.raises(ValueError, match="capacity_provider"):
        build_execution_timeout_profile(
            lambda_timeout_seconds=5400,
            enable_lambda_managed_instances=True,
            lambda_managed_instances_capacity_provider_arn=None,
        )


def test_sfn_sync_invoke_capped_at_15_min_even_with_lmi() -> None:
    profile = build_execution_timeout_profile(
        lambda_timeout_seconds=5400,
        durable_execution_timeout_seconds=10_800,
        enable_lambda_managed_instances=True,
        lambda_managed_instances_capacity_provider_arn=(
            "arn:aws:lambda:us-east-2:123456789012:capacity-provider:sdm"
        ),
        sfn_invoke_timeout_buffer_seconds=60,
    )
    assert profile.sfn_invoke_timeout_seconds == SYNC_INVOKE_MAX_SECONDS + 60
    assert resolve_sfn_invoke_timeout(5400, buffer_seconds=60) == 960


def test_durable_budget_must_cover_segment() -> None:
    with pytest.raises(ValueError, match="durable_execution_timeout_seconds"):
        build_execution_timeout_profile(
            lambda_timeout_seconds=900,
            durable_execution_timeout_seconds=600,
        )


def test_iceguard_rollback_scales_with_segment() -> None:
    short = build_execution_timeout_profile(lambda_timeout_seconds=300)
    long = build_execution_timeout_profile(
        lambda_timeout_seconds=5400,
        durable_execution_timeout_seconds=10_800,
        enable_lambda_managed_instances=True,
        lambda_managed_instances_capacity_provider_arn=(
            "arn:aws:lambda:us-east-2:123456789012:capacity-provider:sdm"
        ),
    )
    assert short.iceguard_rollback_threshold_ms == 10_000  # floor
    assert long.iceguard_rollback_threshold_ms == 60_000  # ceiling


def test_min_resume_attempts_auto_bumped_for_long_budget() -> None:
    profile = build_execution_timeout_profile(
        lambda_timeout_seconds=900,
        durable_execution_timeout_seconds=10_800,
        max_resume_attempts=3,
    )
    # ceil(10800/900)+2 = 12+2 = 14
    assert profile.min_resume_attempts == 14


def test_validate_lmi_noop_when_disabled() -> None:
    validate_lmi_capacity_provider(
        enable_lambda_managed_instances=False,
        capacity_provider_arn=None,
    )


def test_resolve_lambda_timeout_rejects_zero() -> None:
    with pytest.raises(ValueError, match=">= 1"):
        resolve_lambda_timeout(0)


def test_terraform_lambda_module_wires_lmi() -> None:
    """Guardrail: Terraform module must expose LMI knobs used by docs/examples."""
    root = Path(__file__).resolve().parents[2]
    variables = (root / "infrastructure/terraform/modules/lambda/variables.tf").read_text(
        encoding="utf-8"
    )
    main = (root / "infrastructure/terraform/modules/lambda/main.tf").read_text(encoding="utf-8")
    prod_vars = (
        root / "infrastructure/terraform/environments/prod/variables.tf"
    ).read_text(encoding="utf-8")

    assert "enable_lambda_managed_instances" in variables
    assert "lambda_managed_instances_capacity_provider_arn" in variables
    assert "capacity_provider_config" in main
    assert "5400" in variables
    assert "enable_lambda_managed_instances" in prod_vars


def test_docs_cover_lmi_and_iceberg_safety() -> None:
    root = Path(__file__).resolve().parents[2]
    guide = (root / "docs/lambda-managed-instances.md").read_text(encoding="utf-8")
    assert "5400" in guide
    assert "IceGuard" in guide
    assert "VRP" in guide or "validate_then_commit" in guide
    assert "commit_metadata" in guide or "Iceberg" in guide
