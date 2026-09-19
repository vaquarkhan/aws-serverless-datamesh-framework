"""AWS Lambda handler: domain team entry point for governed lakehouse writes."""

from __future__ import annotations

import json
import logging
import os
from typing import Any

from aws_durable_execution_sdk_python import DurableContext, durable_execution

from serverless_data_mesh.catalog import GlueRestCatalogAdapter
from serverless_data_mesh.config import MeshSettings
from serverless_data_mesh.orchestration import IceGuardDurableCoordinator
from serverless_data_mesh.orchestration.sfn_callback import (
    complete_task_token,
    extract_task_token,
    unwrap_workload_event,
)
from serverless_data_mesh.verification import VRPProofGenerator

from .io import records_from_source, write_parquet_chunk
from .io import sink_reader as read_staged_sink
from .rules_io import enrich_records_with_rules
from .workload import build_workload

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)


@durable_execution
def handler(event: dict[str, Any], context: DurableContext) -> dict[str, Any]:
    """Compose durable orchestration, IceGuard, Glue REST, and veridata-recon proofs.

    Supports both SFN modes:
    - sync: event is the workload; return value is the Step Functions task result.
    - async_callback: event includes ``task_token`` + ``workload``; result is also
      reported via SendTaskSuccess so LMI segments can exceed the 15-min sync cap.
    """
    task_token = extract_task_token(event)
    workload_event = unwrap_workload_event(event)
    settings = MeshSettings.from_environment()
    workload = build_workload(workload_event, settings)

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

    try:
        result = coordinator.execute_workload(
            workload,
            batch_writer=lambda start, end: write_parquet_chunk(
                workload.target_uri,
                start,
                end,
                source_uri=workload.source_uri,
            ),
            source_reader=source_reader,
            sink_reader=lambda start, end: read_staged_sink(workload.target_uri, start, end),
        )
    except Exception as exc:
        complete_task_token(
            task_token=task_token,
            result={"outcome": "unknown_failure", "message": str(exc)},
            error=type(exc).__name__,
            cause=str(exc),
        )
        raise

    logger.info("Domain write finished: %s", json.dumps(result, default=str))
    complete_task_token(task_token=task_token, result=result)
    return result


lambda_handler = handler
