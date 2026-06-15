"""Workload builders for the domain writer Lambda example."""

from __future__ import annotations

import os
from typing import Any

from serverless_data_mesh.config import MeshSettings
from serverless_data_mesh.exceptions import WorkloadConfigurationError
from serverless_data_mesh.types import DataWriteWorkload, DomainTransactionBoundary


def build_workload(event: dict[str, Any], settings: MeshSettings | None = None) -> DataWriteWorkload:
    """Map the Lambda event into a typed workload with domain contract metadata."""
    if "workload_id" not in event or "total_records" not in event:
        raise WorkloadConfigurationError("event must include workload_id and total_records")

    active_settings = settings or MeshSettings.from_environment()
    boundary = DomainTransactionBoundary(
        domain_id=event.get("domain_id", "orders-domain"),
        source_namespace=event.get("source_namespace", "raw_orders"),
        target_table=event.get("target_table", "orders_curated"),
        partition_spec=event.get("partition_spec", {"dt": "2026-06-14"}),
        quality_policy_id=event.get("quality_policy_id", "strict-zero-drop"),
        max_chunk_records=int(event.get("max_chunk_records", 5000)),
    )
    return DataWriteWorkload(
        workload_id=event["workload_id"],
        boundary=boundary,
        source_uri=event.get("source_uri", "s3://source-domain/orders/"),
        target_uri=event.get("target_uri", "s3://lakehouse-domain/orders_curated/"),
        total_records=int(event["total_records"]),
        checkpoint_bucket=event.get("checkpoint_bucket", active_settings.checkpoint_bucket),
        proof_bucket=event.get("proof_bucket", active_settings.proof_bucket),
        content_fields=tuple(event.get("content_fields", ("id", "payload_hash"))),
        identity_fields=tuple(event.get("identity_fields", ("id",))),
    )
