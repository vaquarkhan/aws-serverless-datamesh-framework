"""AWS Durable Execution step functions for mesh writes."""

from __future__ import annotations

from typing import Any

from aws_durable_execution_sdk_python import StepContext, durable_step

from serverless_data_mesh.catalog.glue_rest import GlueRestCatalogAdapter
from serverless_data_mesh.exceptions import VerificationRejectedError
from serverless_data_mesh.orchestration.state import OrchestrationState
from serverless_data_mesh.types.workload import ChunkWriteResult
from serverless_data_mesh.verification.commit_gate import metadata_commit_gate


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
    file_digests: list[dict[str, str]] | None = None,
    proof: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Checkpoint one successfully verified chunk (idempotent on replay)."""
    _ = step_context
    _ = workload_payload
    result = ChunkWriteResult(
        chunk_index=chunk_index,
        record_offset=chunk_start,
        record_end=chunk_end,
        parquet_paths=parquet_paths,
        proof_s3_uri=proof_s3_uri,
        verification_passed=verification_passed,
    )
    state = OrchestrationState(
        workload_id=state_payload["workload_id"],
        next_offset=state_payload.get("next_offset", 0),
        committed_chunks=state_payload.get("committed_chunks", 0),
        last_proof_hash=state_payload.get("last_proof_hash"),
        all_parquet_paths=list(state_payload.get("all_parquet_paths") or []),
        all_file_digests=list(state_payload.get("all_file_digests") or []),
        all_chunks_verified=bool(state_payload.get("all_chunks_verified", True)),
        all_proofs=list(state_payload.get("all_proofs") or []),
        target_uri=state_payload.get("target_uri"),
        proof_bucket=state_payload.get("proof_bucket"),
    )
    state.next_offset = chunk_end
    state.committed_chunks += 1
    state.all_parquet_paths.extend(parquet_paths)
    if file_digests:
        state.all_file_digests.extend(file_digests)
    if proof is not None:
        state.all_proofs.append(proof)
    state.all_chunks_verified = state.all_chunks_verified and verification_passed
    return {
        "chunk": {
            "chunk_index": result.chunk_index,
            "record_offset": result.record_offset,
            "record_end": result.record_end,
            "parquet_paths": result.parquet_paths,
            "proof_s3_uri": result.proof_s3_uri,
            "verification_passed": result.verification_passed,
            "file_digests": list(file_digests or []),
        },
        "state": {
            "workload_id": state.workload_id,
            "next_offset": state.next_offset,
            "committed_chunks": state.committed_chunks,
            "last_proof_hash": state.last_proof_hash,
            "all_parquet_paths": state.all_parquet_paths,
            "all_file_digests": state.all_file_digests,
            "all_chunks_verified": state.all_chunks_verified,
            "all_proofs": state.all_proofs,
            "target_uri": state.target_uri,
            "proof_bucket": state.proof_bucket,
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
    verification_passed: bool = False,
    file_digests: list[dict[str, str]] | None = None,
    proofs: list[dict[str, Any]] | None = None,
    expected_target: str | None = None,
    proof_bucket: str | None = None,
) -> dict[str, Any]:
    """Checkpoint the Iceberg REST metadata commit (2PC phase-2), proof-gated."""
    _ = step_context
    gate = metadata_commit_gate(
        verification_passed=verification_passed,
        parquet_paths=parquet_paths,
        bound_digests=file_digests,
        proofs=proofs,
        expected_target=expected_target,
        proof_bucket=proof_bucket,
    )
    if gate.outcome != "PASS":
        raise VerificationRejectedError(
            f"Metadata commit gate blocked catalog commit: {gate.reason}"
        )
    adapter = GlueRestCatalogAdapter.from_environment(namespace=namespace, table_name=table_name)
    adapter.prepare_commit(parquet_paths)
    snapshot_id = adapter.commit(snapshot_properties=snapshot_properties)
    return {"snapshot_id": snapshot_id, "file_count": len(parquet_paths)}
