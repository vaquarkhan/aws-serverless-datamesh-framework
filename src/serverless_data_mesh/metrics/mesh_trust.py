"""Publish VRP trust metrics to CloudWatch for live dashboards."""

from __future__ import annotations

import logging
import os
from typing import Any

logger = logging.getLogger(__name__)

NAMESPACE = "ServerlessDataMesh/Trust"


def publish_vrp_metric(
    *,
    domain_id: str,
    verdict: str,
    row_count: int = 0,
    workload_id: str | None = None,
    cloudwatch_client: Any | None = None,
) -> None:
    """Emit VRP PASS/FAIL metric for CloudWatch / Grafana dashboards."""
    if os.environ.get("SDM_DISABLE_METRICS", "").lower() in ("1", "true", "yes"):
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
