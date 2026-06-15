"""Durable orchestration bridging IceGuard and AWS Lambda Durable Execution."""

from __future__ import annotations

from typing import Any

__all__ = [
    "IceGuardDurableCoordinator",
    "OrchestrationState",
    "durable_commit_metadata",
    "durable_write_chunk",
]


def __getattr__(name: str) -> Any:
    if name == "IceGuardDurableCoordinator":
        from serverless_data_mesh.orchestration.coordinator import IceGuardDurableCoordinator

        return IceGuardDurableCoordinator
    if name == "OrchestrationState":
        from serverless_data_mesh.orchestration.state import OrchestrationState

        return OrchestrationState
    if name in ("durable_commit_metadata", "durable_write_chunk"):
        from serverless_data_mesh.orchestration import durable_steps

        return getattr(durable_steps, name)
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
