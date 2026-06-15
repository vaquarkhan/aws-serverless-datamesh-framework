"""Publish VRP trust metrics to CloudWatch for live dashboards."""

from __future__ import annotations

import logging
import os
from typing import Any

logger = logging.getLogger(__name__)

NAMESPACE = "ServerlessDataMesh/Trust"


def metrics_enabled() -> bool:
    """Opt-out via SDM_METRICS_ENABLED=false or SDM_DISABLE_METRICS=true."""
    if os.environ.get("SDM_DISABLE_METRICS", "").lower() in ("1", "true", "yes"):
        return False
    return os.environ.get("SDM_METRICS_ENABLED", "true").lower() not in (
        "0",
        "false",
        "no",
        "off",
    )


def publish_vrp_metric(
    *,
    domain_id: str,
    verdict: str,
    row_count: int = 0,
    workload_id: str | None = None,
    cloudwatch_client: Any | None = None,
) -> None:
    """Emit VRP PASS/FAIL metric for CloudWatch / Grafana dashboards."""
    if not metrics_enabled():
        return

    try:
        import boto3
    except ImportError:
        logger.debug("boto3 unavailable; skip CloudWatch metric")
        return

    client = cloudwatch_client or boto3.client("cloudwatch")
    value = 1.0 if verdict == "PASS" else 0.0

    dimensions = [{"Name": "Domain", "Value": domain_id}]
    if workload_id:
        dimensions.append({"Name": "WorkloadId", "Value": workload_id})

    try:
        client.put_metric_data(
            Namespace=NAMESPACE,
            MetricData=[
                {
                    "MetricName": "VRPTrustScore",
                    "Dimensions": dimensions,
                    "Value": value,
                    "Unit": "None",
                },
                {
                    "MetricName": "VRPRowCount",
                    "Dimensions": dimensions,
                    "Value": float(row_count),
                    "Unit": "Count",
                },
            ],
        )
        logger.info("Published VRP metric domain=%s verdict=%s", domain_id, verdict)
    except Exception as exc:
        logger.warning("CloudWatch PutMetricData failed (non-fatal): %s", exc)
