"""Build workloads and run PVDM pipelines from compiled contract metadata."""

from __future__ import annotations

from typing import Any, Callable

from serverless_data_mesh.compile.contract import MeshPipelineContract
from serverless_data_mesh.config import MeshSettings
from serverless_data_mesh.exceptions import WorkloadConfigurationError
from serverless_data_mesh.types.workload import DataWriteWorkload, DomainTransactionBoundary

BatchWriterFn = Callable[[int, int], list[str]]
SourceReaderFn = Callable[[int, int], list[dict[str, Any]]]


def contract_from_mapping(raw: dict[str, Any]) -> MeshPipelineContract:
    """Parse a generated CONTRACT dict into a typed contract."""
    return MeshPipelineContract.from_dict(raw)


def contract_to_boundary(contract: MeshPipelineContract) -> DomainTransactionBoundary:
    partition_spec = {contract.boundary.partition_key: "EVENT_PARTITION"}
    return DomainTransactionBoundary(
        domain_id=contract.domain_id,
        source_namespace=contract.boundary.source_namespace,
        target_table=contract.boundary.target_table,
        partition_spec=partition_spec,
        quality_policy_id=contract.boundary.quality_policy_id,
        max_chunk_records=contract.boundary.max_chunk_records,
    )


def build_workload_from_contract(
    event: dict[str, Any],
    contract: MeshPipelineContract | dict[str, Any],
    *,
    settings: MeshSettings | None = None,
) -> DataWriteWorkload:
    """Map a Lambda/Step Functions event plus contract metadata to a workload."""
    parsed = (
        contract
        if isinstance(contract, MeshPipelineContract)
        else contract_from_mapping(contract)
    )
    if "workload_id" not in event or "total_records" not in event:
        raise WorkloadConfigurationError("event must include workload_id and total_records")

    active = settings
    if active is None and (
        "checkpoint_bucket" not in event or "proof_bucket" not in event
    ):
        active = MeshSettings.from_environment()

    checkpoint_bucket = event.get(
        "checkpoint_bucket",
        active.checkpoint_bucket if active else "",
    )
    proof_bucket = event.get("proof_bucket", active.proof_bucket if active else "")
    partition_key = parsed.boundary.partition_key
    partition_value = (event.get("partition_spec") or {}).get(
        partition_key, event.get(partition_key, "REPLACE_AT_RUNTIME")
    )

    boundary = DomainTransactionBoundary(
        domain_id=parsed.domain_id,
        source_namespace=parsed.boundary.source_namespace,
        target_table=parsed.boundary.target_table,
        partition_spec={partition_key: str(partition_value)},
        quality_policy_id=parsed.boundary.quality_policy_id,
        max_chunk_records=parsed.boundary.max_chunk_records,
    )

    publisher = parsed.accounts.publisher or "PUBLISHER_ACCOUNT"
    producer = parsed.accounts.producer
    table = parsed.boundary.target_table

    return DataWriteWorkload(
        workload_id=str(event["workload_id"]),
        boundary=boundary,
        source_uri=event.get(
            "source_uri",
            f"s3://producer-{producer}/raw/{parsed.domain_id}/",
        ),
        target_uri=event.get(
            "target_uri",
            f"s3://publisher-{publisher}/lakehouse/{table}/",
        ),
        total_records=int(event["total_records"]),
        checkpoint_bucket=checkpoint_bucket,
        proof_bucket=proof_bucket,
        content_fields=parsed.workload.content_fields,
        identity_fields=parsed.workload.identity_fields,
    )


def run_metadata_pipeline(
    event: dict[str, Any],
    context: Any,
    contract: dict[str, Any],
    *,
    source_reader: SourceReaderFn,
    batch_writer: BatchWriterFn,
    sink_reader: SourceReaderFn | None = None,
) -> dict[str, Any]:
    """Execute IceGuardDurableCoordinator using contract-driven metadata."""
    from serverless_data_mesh.catalog import GlueRestCatalogAdapter
    from serverless_data_mesh.orchestration import IceGuardDurableCoordinator
    from serverless_data_mesh.verification import VRPProofGenerator

    parsed = contract_from_mapping(contract)
    settings = MeshSettings.from_environment()
    workload = build_workload_from_contract(event, parsed, settings=settings)

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
        checkpoint_interval=parsed.workload.checkpoint_interval,
        rollback_threshold_ms=parsed.workload.rollback_threshold_ms,
    )

    return coordinator.execute_workload(
        workload,
        batch_writer=batch_writer,
        source_reader=source_reader,
        sink_reader=sink_reader,
        enable_auto_repair=parsed.governance.auto_repair,
    )
