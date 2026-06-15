"""Durable orchestration state models."""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(slots=True)
class OrchestrationState:
    """Checkpointed progress for a multi-chunk domain write."""

    workload_id: str
    next_offset: int = 0
    committed_chunks: int = 0
    last_proof_hash: str | None = None
    all_parquet_paths: list[str] = field(default_factory=list)
