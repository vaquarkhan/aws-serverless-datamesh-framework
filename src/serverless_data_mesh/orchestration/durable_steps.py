"""AWS Durable Execution step functions for mesh writes."""

from __future__ import annotations

from typing import Any

from aws_durable_execution_sdk_python import StepContext, durable_step

from serverless_data_mesh.catalog.glue_rest import GlueRestCatalogAdapter
from serverless_data_mesh.orchestration.state import OrchestrationState
from serverless_data_mesh.types.workload import ChunkWriteResult


@durable_step
def durable_write_chunk(
    step_context: StepContext,
    *,
    workload_payload: dict[str, Any],
    state_payload: dict[str, Any],
    chunk_index: int,
    chunk_start: int,
    chunk_end: int,
    parquet_paths: list[str],
    proof_s3_uri: str,
    verification_passed: bool,
) -> dict[str, Any]:
    """Checkpoint one successfully verified chunk (idempotent on replay)."""
    _ = step_context
    result = ChunkWriteResult(
        chunk_index=chunk_index,
        record_offset=chunk_start,
        record_end=chunk_end,
        parquet_paths=parquet_paths,
        proof_s3_uri=proof_s3_uri,
        verification_passed=verification_passed,
    )
    state = OrchestrationState(**state_payload)
    state.next_offset = chunk_end
    state.committed_chunks += 1
    state.all_parquet_paths.extend(parquet_paths)
    return {
        "chunk": {
            "chunk_index": result.chunk_index,
            "record_offset": result.record_offset,
            "record_end": result.record_end,
            "parquet_paths": result.parquet_paths,
            "proof_s3_uri": result.proof_s3_uri,
            "verification_passed": result.verification_passed,
        },
        "state": {
            "workload_id": state.workload_id,
            "next_offset": state.next_offset,
            "committed_chunks": state.committed_chunks,
            "last_proof_hash": state.last_proof_hash,
            "all_parquet_paths": state.all_parquet_paths,
        },
    }


@durable_step
def durable_commit_metadata(
    step_context: StepContext,
    *,
    namespace: str,
    table_name: str,
    parquet_paths: list[str],
    snapshot_properties: dict[str, str] | None = None,
) -> dict[str, Any]:
    """Checkpoint the Iceberg REST metadata commit (2PC phase-2)."""
    _ = step_context
    adapter = GlueRestCatalogAdapter.from_environment(namespace=namespace, table_name=table_name)
    adapter.prepare_commit(parquet_paths)
    snapshot_id = adapter.commit(snapshot_properties=snapshot_properties)
    return {"snapshot_id": snapshot_id, "file_count": len(parquet_paths)}
