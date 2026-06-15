"""AWS Lambda handler — domain team entry point for governed lakehouse writes."""

from __future__ import annotations

import json
import logging
import os
from typing import Any

from aws_durable_execution_sdk_python import DurableContext, durable_execution

from .io import records_from_source, write_parquet_chunk
from .rules_io import enrich_records_with_rules
from .workload import build_workload
from serverless_data_mesh.catalog import GlueRestCatalogAdapter
from serverless_data_mesh.config import MeshSettings
from serverless_data_mesh.orchestration import IceGuardDurableCoordinator
from serverless_data_mesh.verification import VRPProofGenerator

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)


@durable_execution
def handler(event: dict[str, Any], context: DurableContext) -> dict[str, Any]:
    """Compose durable orchestration, IceGuard, Glue REST, and veridata-recon proofs."""
    settings = MeshSettings.from_environment()
    workload = build_workload(event, settings)

    catalog = GlueRestCatalogAdapter.from_environment(
        namespace=workload.boundary.source_namespace,
        table_name=workload.boundary.target_table,
        aws_account_id=settings.aws_account_id,
        warehouse=settings.iceberg_warehouse,
    )
    proofs = VRPProofGenerator.from_env()

    coordinator = IceGuardDurableCoordinator(
        durable_context=context,
        lambda_context=context,
        proof_generator=proofs,
        catalog_adapter=catalog,
        checkpoint_interval=settings.checkpoint_interval,
        rollback_threshold_ms=settings.rollback_threshold_ms,
    )

    def source_reader(start: int, end: int) -> list[dict[str, Any]]:
        records = records_from_source(workload.source_uri, start, end)
        if os.environ.get("SPARKRULES_DRL") or os.environ.get("SPARKRULES_DRL_S3_URI"):
            return enrich_records_with_rules(records)
        return records

    result = coordinator.execute_workload(
        workload,
        batch_writer=lambda start, end: write_parquet_chunk(workload.target_uri, start, end),
        source_reader=source_reader,
    )

    logger.info("Domain write finished: %s", json.dumps(result, default=str))
    return result


lambda_handler = handler
