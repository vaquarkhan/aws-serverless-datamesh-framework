"""Segment / durable / SFN timeout profile (mirrors Terraform dual clocks + LMI).

Two Step Functions invoke modes:

- **sync** (default): ``lambda:invoke`` — AWS sync cap **15 minutes** (900s).
- **async_callback**: ``lambda:invoke.waitForTaskToken`` + ``InvocationType=Event`` —
  on Lambda Managed Instances segments may run up to **90 minutes** (5400s); the
  handler callbacks via SendTaskSuccess/Failure.

Direct durable/async invoke (no SFN) also supports up to 90 minutes on LMI.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

from serverless_data_mesh.orchestration.sfn_callback import (
    SFN_INVOKE_MODE_ASYNC_CALLBACK,
    SFN_INVOKE_MODE_SYNC,
    VALID_SFN_INVOKE_MODES,
)

ON_DEMAND_SEGMENT_MAX_SECONDS = 900
LMI_SEGMENT_MAX_SECONDS = 5400
SYNC_INVOKE_MAX_SECONDS = 900
DURABLE_EXECUTION_MAX_SECONDS = 31_622_400


@dataclass(frozen=True, slots=True)
class ExecutionTimeoutProfile:
    """Resolved timeout knobs for one domain-writer deployment."""

    lambda_timeout_seconds: int
    durable_execution_timeout_seconds: int
    enable_lambda_managed_instances: bool
    sfn_invoke_mode: str
    sfn_invoke_timeout_seconds: int
    iceguard_rollback_threshold_ms: int
    min_resume_attempts: int
    segment_timeout_max: int


def segment_timeout_max(*, enable_lambda_managed_instances: bool) -> int:
    return LMI_SEGMENT_MAX_SECONDS if enable_lambda_managed_instances else ON_DEMAND_SEGMENT_MAX_SECONDS


def resolve_lambda_timeout(
    requested: int,
    *,
    enable_lambda_managed_instances: bool = False,
) -> int:
    """Clamp requested segment timeout to the capacity-mode ceiling."""
    if requested < 1:
        raise ValueError("lambda_timeout_seconds must be >= 1")
    ceiling = segment_timeout_max(enable_lambda_managed_instances=enable_lambda_managed_instances)
    if requested > ceiling:
        mode = "managed-instances" if enable_lambda_managed_instances else "on-demand"
        raise ValueError(
            f"lambda_timeout_seconds={requested} exceeds {ceiling}s for {mode} Lambda"
        )
    return requested


def resolve_sfn_invoke_timeout(
    lambda_timeout_seconds: int,
    *,
    buffer_seconds: int = 60,
    sfn_invoke_mode: str = SFN_INVOKE_MODE_SYNC,
) -> int:
    """How long Step Functions waits for one segment.

    Sync mode caps wait at AWS sync limit (900s + buffer).
    Async callback mode waits for the full segment (+ buffer), up to 90 min on LMI.
    """
    if buffer_seconds < 0:
        raise ValueError("sfn_invoke_timeout_buffer_seconds must be >= 0")
    mode = (sfn_invoke_mode or SFN_INVOKE_MODE_SYNC).strip().lower()
    if mode not in VALID_SFN_INVOKE_MODES:
        raise ValueError(
            f"sfn_invoke_mode must be one of {sorted(VALID_SFN_INVOKE_MODES)}, got {sfn_invoke_mode!r}"
        )
    if mode == SFN_INVOKE_MODE_ASYNC_CALLBACK:
        return lambda_timeout_seconds + buffer_seconds
    return min(lambda_timeout_seconds, SYNC_INVOKE_MAX_SECONDS) + buffer_seconds


def resolve_iceguard_rollback_ms(
    lambda_timeout_seconds: int,
    *,
    explicit_ms: int | None = None,
) -> int:
    """IceGuard lead time before hard kill (keeps Iceberg free of partial commits)."""
    if explicit_ms is not None:
        if explicit_ms < 1:
            raise ValueError("iceguard_rollback_threshold_ms must be >= 1")
        return explicit_ms
    return min(60_000, max(10_000, lambda_timeout_seconds * 33))


def resolve_min_resume_attempts(
    durable_execution_timeout_seconds: int,
    lambda_timeout_seconds: int,
    *,
    buffer_attempts: int = 2,
) -> int:
    if lambda_timeout_seconds < 1:
        raise ValueError("lambda_timeout_seconds must be >= 1")
    return math.ceil(durable_execution_timeout_seconds / lambda_timeout_seconds) + buffer_attempts


def validate_lmi_capacity_provider(
    *,
    enable_lambda_managed_instances: bool,
    capacity_provider_arn: str | None,
) -> None:
    if not enable_lambda_managed_instances:
        return
    if not capacity_provider_arn or not capacity_provider_arn.strip():
        raise ValueError(
            "enable_lambda_managed_instances=true requires "
            "lambda_managed_instances_capacity_provider_arn"
        )


def validate_durable_budget(
    durable_execution_timeout_seconds: int,
    lambda_timeout_seconds: int,
) -> None:
    if durable_execution_timeout_seconds < 60:
        raise ValueError("durable_execution_timeout_seconds must be >= 60")
    if durable_execution_timeout_seconds > DURABLE_EXECUTION_MAX_SECONDS:
        raise ValueError(
            f"durable_execution_timeout_seconds must be <= {DURABLE_EXECUTION_MAX_SECONDS}"
        )
    if durable_execution_timeout_seconds < lambda_timeout_seconds:
        raise ValueError(
            "durable_execution_timeout_seconds must be >= lambda_timeout_seconds"
        )


def validate_sfn_mode_for_segment(
    *,
    sfn_invoke_mode: str,
    lambda_timeout_seconds: int,
    enable_lambda_managed_instances: bool,
) -> str:
    """Segments above 15 min require async_callback (+ LMI)."""
    mode = (sfn_invoke_mode or SFN_INVOKE_MODE_SYNC).strip().lower()
    if mode not in VALID_SFN_INVOKE_MODES:
        raise ValueError(
            f"sfn_invoke_mode must be one of {sorted(VALID_SFN_INVOKE_MODES)}, got {sfn_invoke_mode!r}"
        )
    if lambda_timeout_seconds > SYNC_INVOKE_MAX_SECONDS:
        if not enable_lambda_managed_instances:
            raise ValueError(
                "lambda_timeout_seconds > 900 requires enable_lambda_managed_instances=true"
            )
        if mode != SFN_INVOKE_MODE_ASYNC_CALLBACK:
            raise ValueError(
                "lambda_timeout_seconds > 900 with Step Functions requires "
                "sfn_lambda_invoke_mode=async_callback (AWS sync invoke is capped at 15 min)"
            )
    return mode


def build_execution_timeout_profile(
    *,
    lambda_timeout_seconds: int = 900,
    durable_execution_timeout_seconds: int = 5400,
    enable_lambda_managed_instances: bool = False,
    lambda_managed_instances_capacity_provider_arn: str | None = None,
    sfn_invoke_mode: str = SFN_INVOKE_MODE_SYNC,
    sfn_invoke_timeout_buffer_seconds: int = 60,
    iceguard_rollback_threshold_ms: int | None = None,
    max_resume_attempts: int = 10,
) -> ExecutionTimeoutProfile:
    """Validate and resolve the industry-standard dual-clock + dual-SFN-mode profile."""
    validate_lmi_capacity_provider(
        enable_lambda_managed_instances=enable_lambda_managed_instances,
        capacity_provider_arn=lambda_managed_instances_capacity_provider_arn,
    )
    segment = resolve_lambda_timeout(
        lambda_timeout_seconds,
        enable_lambda_managed_instances=enable_lambda_managed_instances,
    )
    mode = validate_sfn_mode_for_segment(
        sfn_invoke_mode=sfn_invoke_mode,
        lambda_timeout_seconds=segment,
        enable_lambda_managed_instances=enable_lambda_managed_instances,
    )
    validate_durable_budget(durable_execution_timeout_seconds, segment)
    min_resumes = resolve_min_resume_attempts(
        durable_execution_timeout_seconds,
        segment,
    )
    return ExecutionTimeoutProfile(
        lambda_timeout_seconds=segment,
        durable_execution_timeout_seconds=durable_execution_timeout_seconds,
        enable_lambda_managed_instances=enable_lambda_managed_instances,
        sfn_invoke_mode=mode,
        sfn_invoke_timeout_seconds=resolve_sfn_invoke_timeout(
            segment,
            buffer_seconds=sfn_invoke_timeout_buffer_seconds,
            sfn_invoke_mode=mode,
        ),
        iceguard_rollback_threshold_ms=resolve_iceguard_rollback_ms(
            segment,
            explicit_ms=iceguard_rollback_threshold_ms,
        ),
        min_resume_attempts=max(max_resume_attempts, min_resumes),
        segment_timeout_max=segment_timeout_max(
            enable_lambda_managed_instances=enable_lambda_managed_instances
        ),
    )
