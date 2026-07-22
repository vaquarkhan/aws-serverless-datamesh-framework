"""Shared pytest fixtures."""

from __future__ import annotations

import os

import pytest

from serverless_data_mesh.types.workload import DataWriteWorkload, DomainTransactionBoundary

# Avoid botocore NoRegionError when optional AWS clients are constructed in demos.
os.environ.setdefault("AWS_DEFAULT_REGION", "us-east-1")
os.environ.setdefault("AWS_REGION", "us-east-1")


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
