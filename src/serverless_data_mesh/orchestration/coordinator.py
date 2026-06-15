"""IceGuard + Durable Execution coordinator for cross-domain lakehouse writes."""

from __future__ import annotations

import logging
from typing import Any

from aws_durable_execution_sdk_python import DurableContext
from iceguard import protect
from iceguard.exceptions import IceGuardRollbackError

from serverless_data_mesh.catalog.glue_rest import GlueRestCatalogAdapter
from serverless_data_mesh.exceptions import VerificationRejectedError
from serverless_data_mesh.orchestration.durable_steps import (
    durable_commit_metadata,
    durable_write_chunk,
)
from serverless_data_mesh.orchestration.state import OrchestrationState
from serverless_data_mesh.types.workload import (
    BatchWriterFn,
    DataWriteWorkload,
    SourceReaderFn,
    WriteOutcome,
)
from serverless_data_mesh.metrics.mesh_trust import publish_vrp_metric
from serverless_data_mesh.orchestration.reprocess import attempt_vrp_repair
from serverless_data_mesh.verification.vrp import VRPProofGenerator, validate_then_commit

logger = logging.getLogger(__name__)


def _missing_from_repair(
    source: list[dict[str, Any]],
    sink: list[dict[str, Any]],
    identity_fields: tuple[str, ...],
) -> list[dict[str, Any]]:
    sink_ids = {"|".join(str(r.get(f, "")) for f in identity_fields) for r in sink}
    return [
        r
        for r in source
        if "|".join(str(r.get(f, "")) for f in identity_fields) not in sink_ids
    ]


class IceGuardDurableCoordinator:
    """Coordinate large lakehouse writes across chained durable steps.

    Composes IceGuard SafeWriter, AWS Durable Execution, veridata-recon proofs,
    and Glue REST catalog commits into a single governed transaction boundary.
    """

    def __init__(
        self,
        *,
        durable_context: DurableContext,
        lambda_context: Any,
        proof_generator: VRPProofGenerator,
        catalog_adapter: GlueRestCatalogAdapter | None = None,
        checkpoint_interval: int = 5000,
        rollback_threshold_ms: int = 30_000,
    ) -> None:
        self._durable = durable_context
        self._lambda = lambda_context
        self._proofs = proof_generator
        self._catalog = catalog_adapter
        self._checkpoint_interval = checkpoint_interval
        self._rollback_threshold_ms = rollback_threshold_ms

    def _initial_state(self, workload: DataWriteWorkload) -> OrchestrationState:
        return OrchestrationState(workload_id=workload.workload_id)

    def _state_dict(self, state: OrchestrationState) -> dict[str, Any]:
        return {
            "workload_id": state.workload_id,
            "next_offset": state.next_offset,
            "committed_chunks": state.committed_chunks,
            "last_proof_hash": state.last_proof_hash,
            "all_parquet_paths": state.all_parquet_paths,
        }

    def _workload_dict(self, workload: DataWriteWorkload) -> dict[str, Any]:
        return {
            "workload_id": workload.workload_id,
            "source_uri": workload.source_uri,
            "target_uri": workload.target_uri,
            "total_records": workload.total_records,
            "checkpoint_bucket": workload.checkpoint_bucket,
            "proof_bucket": workload.proof_bucket,
            "content_fields": list(workload.content_fields),
            "identity_fields": list(workload.identity_fields),
            "boundary": {
                "domain_id": workload.boundary.domain_id,
                "source_namespace": workload.boundary.source_namespace,
                "target_table": workload.boundary.target_table,
                "partition_spec": workload.boundary.partition_spec,
                "quality_policy_id": workload.boundary.quality_policy_id,
                "max_chunk_records": workload.boundary.max_chunk_records,
            },
        }

    def execute_workload(
        self,
        workload: DataWriteWorkload,
        *,
        batch_writer: BatchWriterFn,
        source_reader: SourceReaderFn,
        resume_state: OrchestrationState | None = None,
        sink_reader: SourceReaderFn | None = None,
        enable_auto_repair: bool = False,
    ) -> dict[str, Any]:
        """Run a large write as durable, resumable chunks under IceGuard protection."""
        state = resume_state or self._initial_state(workload)
        outcome = WriteOutcome.RESUMED if state.next_offset > 0 else WriteOutcome.COMMITTED

        adapter = self._catalog or GlueRestCatalogAdapter.from_environment(
            namespace=workload.boundary.source_namespace,
            table_name=workload.boundary.target_table,
        )
        adapter.connect()

        chunk_paths_by_batch: dict[tuple[int, int], list[str]] = {}
        chunk_index = state.committed_chunks

        try:
            with protect(
                self._lambda,
                table_format="iceberg",
                s3_bucket=workload.checkpoint_bucket,
                coordinator_id=workload.workload_id,
                durable_context=self._durable,
                rollback_threshold_ms=self._rollback_threshold_ms,
                checkpoint_interval=self._checkpoint_interval,
                catalog=adapter.catalog,
                table_identifier=(
                    f"{workload.boundary.source_namespace}.{workload.boundary.target_table}"
                ),
            ) as writer:

                def guarded_batch_writer(start: int, end: int) -> None:
                    nonlocal chunk_index, state

                    paths = batch_writer(start, end)
                    chunk_paths_by_batch[(start, end)] = paths

                    source_records = source_reader(start, end)
                    sink_records = sink_reader(start, end) if sink_reader else source_records
                    proof = self._proofs.build_proof(
                        source_records=source_records,
                        sink_records=sink_records,
                        workload=workload,
                        chunk_start=start,
                        chunk_end=end,
                        prev_proof_hash=state.last_proof_hash,
                    )
                    verification = validate_then_commit(proof)
                    if verification.outcome != "PASS" and enable_auto_repair and sink_reader:

                        def _repair_write(missing: list[dict[str, Any]]) -> list[dict[str, Any]]:
                            batch_writer(start, start + len(missing))
                            return sink_records + missing

                        repair = attempt_vrp_repair(
                            source_records=source_records,
                            sink_records=sink_records,
                            workload=workload,
                            chunk_start=start,
                            chunk_end=end,
                            proof_generator=self._proofs,
                            write_repair_fn=_repair_write,
                        )
                        if repair.outcome == "repaired_pass" and repair.proof is not None:
                            proof = repair.proof
                            verification = validate_then_commit(proof)
                            sink_records = sink_records + _missing_from_repair(
                                source_records, sink_records, workload.identity_fields
                            )

                    publish_vrp_metric(
                        domain_id=workload.boundary.domain_id,
                        verdict=proof["reconciliation"]["verdict"],
                        row_count=len(sink_records),
                        workload_id=workload.workload_id,
                    )
                    if verification.outcome != "PASS":
                        raise VerificationRejectedError(
                            f"VRP blocked chunk [{start}, {end}): {verification.reason}"
                        )

                    proof_uri = self._proofs.persist_proof(
                        proof,
                        bucket=workload.proof_bucket,
                        key_prefix=f"{workload.boundary.domain_id}/{workload.workload_id}",
                        chunk_index=chunk_index,
                    )
                    state.last_proof_hash = proof["proof_id"]

                    step_result = self._durable.step(
                        durable_write_chunk(
                            workload_payload=self._workload_dict(workload),
                            state_payload=self._state_dict(state),
                            chunk_index=chunk_index,
                            chunk_start=start,
                            chunk_end=end,
                            parquet_paths=paths,
                            proof_s3_uri=proof_uri,
                            verification_passed=True,
                        )
                    )
                    state = OrchestrationState(**step_result["state"])
                    chunk_index += 1

                writer.write(
                    path=workload.target_uri,
                    total_records=workload.total_records,
                    batch_writer=guarded_batch_writer,
                    track_paths=lambda start, end: chunk_paths_by_batch.get((start, end), []),
                )

            commit_result = self._durable.step(
                durable_commit_metadata(
                    namespace=workload.boundary.source_namespace,
                    table_name=workload.boundary.target_table,
                    parquet_paths=state.all_parquet_paths,
                    snapshot_properties={
                        "app-id": "serverless-data-mesh",
                        "workload-id": workload.workload_id,
                        "domain-id": workload.boundary.domain_id,
                    },
                )
            )
            return {
                "outcome": outcome.value,
                "workload_id": workload.workload_id,
                "records_written": state.next_offset,
                "chunks": state.committed_chunks,
                "snapshot_id": commit_result["snapshot_id"],
                "proof_chain_tail": state.last_proof_hash,
            }

        except VerificationRejectedError as exc:
            logger.error("Data quality gate failed for %s: %s", workload.workload_id, exc)
            adapter.abort()
            return {
                "outcome": WriteOutcome.VERIFICATION_FAILED.value,
                "workload_id": workload.workload_id,
                "resume_offset": state.next_offset,
                "message": str(exc),
            }

        except IceGuardRollbackError as exc:
            logger.warning(
                "IceGuard rollback for workload %s near timeout (remaining=%sms)",
                workload.workload_id,
                exc.remaining_time_ms,
            )
            adapter.abort()
            return {
                "outcome": WriteOutcome.ROLLED_BACK.value,
                "workload_id": workload.workload_id,
                "resume_offset": state.next_offset,
                "message": (
                    "Physical files rolled back; re-invoke Lambda to resume "
                    "from durable checkpoint without duplicating committed chunks."
                ),
            }
