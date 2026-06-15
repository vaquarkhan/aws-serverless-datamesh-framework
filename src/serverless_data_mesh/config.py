"""Runtime configuration loaded from environment variables."""

from __future__ import annotations

import os
from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class MeshSettings:
    """Operational settings for Lambda domain writers."""

    checkpoint_bucket: str
    proof_bucket: str
    iceberg_table_bucket: str
    aws_region: str
    checkpoint_interval: int = 5000
    rollback_threshold_ms: int = 30_000
    lambda_timeout_seconds: int = 900
    iceberg_warehouse: str | None = None
    aws_account_id: str | None = None

    @classmethod
    def from_environment(cls) -> MeshSettings:
        checkpoint = os.environ.get("ICEGUARD_CHECKPOINT_BUCKET")
        if not checkpoint:
            raise ValueError("ICEGUARD_CHECKPOINT_BUCKET is required")

        region = os.environ.get("AWS_REGION", os.environ.get("AWS_DEFAULT_REGION", "us-east-1"))
        table_bucket = os.environ.get("ICEBERG_TABLE_BUCKET", "default")

        return cls(
            checkpoint_bucket=checkpoint,
            proof_bucket=os.environ.get("VRP_PROOF_BUCKET", checkpoint),
            iceberg_table_bucket=table_bucket,
            aws_region=region,
    checkpoint_interval=int(os.environ.get("ICEGUARD_CHECKPOINT_INTERVAL", "5000")),
    rollback_threshold_ms=int(os.environ.get("ICEGUARD_ROLLBACK_THRESHOLD_MS", "30000")),
    lambda_timeout_seconds=int(os.environ.get("LAMBDA_TIMEOUT_SECONDS", "900")),
            iceberg_warehouse=os.environ.get("ICEBERG_WAREHOUSE"),
            aws_account_id=os.environ.get("AWS_ACCOUNT_ID"),
        )
