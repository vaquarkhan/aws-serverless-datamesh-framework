"""Fetch live VRP trust rows from CloudWatch metrics."""

from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone
from typing import Any

logger = logging.getLogger(__name__)

NAMESPACE = "ServerlessDataMesh/Trust"


def fetch_cloudwatch_trust_rows(
    *,
    hours: int = 24,
    region: str | None = None,
    cloudwatch_client: Any | None = None,
) -> list[dict[str, Any]]:
    """Pull latest VRPTrustScore per domain from CloudWatch for dashboard rendering."""
    try:
        import boto3
    except ImportError:
        logger.debug("boto3 unavailable for CloudWatch dashboard")
        return []

    client = cloudwatch_client or boto3.client("cloudwatch", region_name=region)
    end = datetime.now(timezone.utc)
    start = end - timedelta(hours=hours)

    response = client.list_metrics(Namespace=NAMESPACE, MetricName="VRPTrustScore")
    domains = sorted(
        {
            dim["Value"]
            for metric in response.get("Metrics", [])
            for dim in metric.get("Dimensions", [])
            if dim.get("Name") == "Domain"
        }
    )

    rows: list[dict[str, Any]] = []
    for domain in domains:
        trust = client.get_metric_statistics(
            Namespace=NAMESPACE,
            MetricName="VRPTrustScore",
            Dimensions=[{"Name": "Domain", "Value": domain}],
            StartTime=start,
            EndTime=end,
            Period=3600,
            Statistics=["Maximum"],
        )
        count = client.get_metric_statistics(
            Namespace=NAMESPACE,
            MetricName="VRPRowCount",
            Dimensions=[{"Name": "Domain", "Value": domain}],
            StartTime=start,
            EndTime=end,
            Period=3600,
            Statistics=["Maximum"],
        )
        trust_points = trust.get("Datapoints", [])
        count_points = count.get("Datapoints", [])
        latest_trust = max(trust_points, key=lambda p: p["Timestamp"]) if trust_points else None
        latest_count = max(count_points, key=lambda p: p["Timestamp"]) if count_points else None

        score = latest_trust["Maximum"] if latest_trust else 0.0
        rows.append(
            {
                "domain": domain,
                "last_vrp": (
                    latest_trust["Timestamp"].strftime("%I:%M %p")
                    if latest_trust
                    else "no data"
                ),
                "status": "PASS" if score >= 1.0 else "FAIL",
                "rows": str(int(latest_count["Maximum"])) if latest_count else "?",
                "detail": "" if score >= 1.0 else "VRP trust score below 1.0",
            }
        )
    return rows
