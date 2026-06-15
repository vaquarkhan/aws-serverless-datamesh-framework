"""Shared pytest fixtures."""

from __future__ import annotations

import pytest

from serverless_data_mesh.types.workload import DataWriteWorkload, DomainTransactionBoundary


@pytest.fixture
def sample_boundary() -> DomainTransactionBoundary:
    return DomainTransactionBoundary(
        domain_id="orders-domain",
        source_namespace="raw_orders",
        target_table="orders_curated",
        partition_spec={"dt": "2026-06-14"},
    )


@pytest.fixture
def sample_workload(sample_boundary: DomainTransactionBoundary) -> DataWriteWorkload:
    return DataWriteWorkload(
        workload_id="test-workload-001",
        boundary=sample_boundary,
        source_uri="s3://source/orders/",
        target_uri="s3://lakehouse/orders/",
        total_records=100,
        checkpoint_bucket="test-checkpoints",
        proof_bucket="test-proofs",
    )
