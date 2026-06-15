"""Unit tests for example workload builder."""

from __future__ import annotations

import pytest

from examples.domain_writer.workload import build_workload
from serverless_data_mesh.config import MeshSettings
from serverless_data_mesh.exceptions import WorkloadConfigurationError


def test_build_workload_from_event() -> None:
    settings = MeshSettings(
        checkpoint_bucket="chk",
        proof_bucket="proofs",
        iceberg_table_bucket="lake",
        aws_region="us-east-1",
    )
    workload = build_workload(
        {"workload_id": "w1", "total_records": 500, "domain_id": "finance"},
        settings,
    )
    assert workload.workload_id == "w1"
    assert workload.total_records == 500
    assert workload.boundary.domain_id == "finance"


def test_build_workload_requires_ids() -> None:
    settings = MeshSettings(
        checkpoint_bucket="chk",
        proof_bucket="proofs",
        iceberg_table_bucket="lake",
        aws_region="us-east-1",
    )
    with pytest.raises(WorkloadConfigurationError):
        build_workload({"total_records": 1}, settings)
