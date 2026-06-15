"""Shared types for multi-domain write coordination and contract enforcement."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Any, Callable


class WriteOutcome(str, Enum):
    """Terminal state of a domain write transaction."""

    COMMITTED = "committed"
    ROLLED_BACK = "rolled_back"
    RESUMED = "resumed"
    VERIFICATION_FAILED = "verification_failed"


@dataclass(frozen=True, slots=True)
class DomainTransactionBoundary:
    """Declarative contract for a single domain team's write scope.

    In a federated data mesh, each domain owns its tables and publishes
    consumption contracts. This boundary encodes the partition scope and
    quality gates that the central coordinator enforces before metadata commit.
    """

    domain_id: str
    source_namespace: str
    target_table: str
    partition_spec: dict[str, str]
    quality_policy_id: str = "default:strict"
    max_chunk_records: int = 5000


@dataclass(frozen=True, slots=True)
class DataWriteWorkload:
    """Description of a large backfill or cross-account copy job.

    The durable orchestrator shards ``total_records`` into checkpoint-sized
    chunks. Each chunk is an independently resumable unit guarded by IceGuard.
    """

    workload_id: str
    boundary: DomainTransactionBoundary
    source_uri: str
    target_uri: str
    total_records: int
    checkpoint_bucket: str
    proof_bucket: str
    content_fields: tuple[str, ...] = ("id", "payload_hash")
    identity_fields: tuple[str, ...] = ("id",)


@dataclass(frozen=True, slots=True)
class DataProductContract:
    """Published data product contract for the federated mesh registry.

    Extends ``DomainTransactionBoundary`` with ownership and SLA metadata that
    Steward governance and Publisher consumers rely on for discovery and audit.
    """

    product_id: str
    owner_team: str
    boundary: DomainTransactionBoundary
    sla_freshness_hours: int = 24
    schema_version: str = "1.0"
    description: str = ""

    def to_registry_entry(self) -> dict[str, str | int | dict[str, str]]:
        """Serialize for mesh catalog / Backstage / internal registry APIs."""
        return {
            "product_id": self.product_id,
            "owner_team": self.owner_team,
            "domain_id": self.boundary.domain_id,
            "target_table": self.boundary.target_table,
            "quality_policy_id": self.boundary.quality_policy_id,
            "sla_freshness_hours": self.sla_freshness_hours,
            "schema_version": self.schema_version,
            "description": self.description,
            "partition_spec": dict(self.boundary.partition_spec),
        }


@dataclass(slots=True)
class ChunkWriteResult:
    """Outcome of one durable chunk step."""

    chunk_index: int
    record_offset: int
    record_end: int
    parquet_paths: list[str]
    proof_s3_uri: str | None = None
    verification_passed: bool = False


BatchWriterFn = Callable[[int, int], list[str]]
"""Write records ``[start, end)`` and return newly created Parquet S3 URIs."""

SourceReaderFn = Callable[[int, int], list[dict[str, Any]]]
"""Read source records ``[start, end)`` for VRP fingerprinting."""
