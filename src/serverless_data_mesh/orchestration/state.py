"""Durable orchestration state models."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(slots=True)
class OrchestrationState:
    """Checkpointed progress for a multi-chunk domain write."""

    workload_id: str
    next_offset: int = 0
    committed_chunks: int = 0
    last_proof_hash: str | None = None
    all_parquet_paths: list[str] = field(default_factory=list)
    all_file_digests: list[dict[str, str]] = field(default_factory=list)
    all_chunks_verified: bool = True
    all_proofs: list[dict[str, Any]] = field(default_factory=list)
    target_uri: str | None = None
    proof_bucket: str | None = None
