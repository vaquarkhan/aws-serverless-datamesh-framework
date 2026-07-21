"""Publish mesh ops alerts to SNS (VRP FAIL, rollback, SFN issues).

Opt-in via SDM_SNS_TOPIC_ARN (or VRP_ALERT_SNS_TOPIC_ARN). Failures are
non-fatal so notification outages never block the write path.
"""

from __future__ import annotations

import json
import logging
import os
from typing import Any

logger = logging.getLogger(__name__)


def sns_enabled() -> bool:
    if os.environ.get("SDM_SNS_ENABLED", "true").strip().lower() in (
        "0",
        "false",
        "no",
        "off",
    ):
        return False
    return bool(sns_topic_arn_from_env())


def sns_topic_arn_from_env() -> str | None:
    for key in ("SDM_SNS_TOPIC_ARN", "VRP_ALERT_SNS_TOPIC_ARN", "ALARM_SNS_TOPIC_ARN"):
        value = os.environ.get(key, "").strip()
        if value:
            return value
    return None


def notify_ops(
    *,
    subject: str,
    event: str,
    domain_id: str | None = None,
    workload_id: str | None = None,
    verdict: str | None = None,
    detail: str | None = None,
    extra: dict[str, Any] | None = None,
    sns_client: Any | None = None,
    topic_arn: str | None = None,
) -> bool:
    """Publish a JSON alert. Returns True if publish succeeded."""
    arn = topic_arn or sns_topic_arn_from_env()
    if not arn or not sns_enabled():
        return False

    body: dict[str, Any] = {
        "event": event,
        "domain_id": domain_id,
        "workload_id": workload_id,
        "verdict": verdict,
        "detail": detail,
        "framework": "serverless-data-mesh",
        "method": "PVDM",
    }
    if extra:
        body.update(extra)

    try:
        import boto3
    except ImportError:
        logger.debug("boto3 unavailable; skip SNS notify")
        return False

    try:
        region = os.environ.get("AWS_REGION") or os.environ.get("AWS_DEFAULT_REGION") or "us-east-1"
        client = sns_client or boto3.client("sns", region_name=region)
        client.publish(
            TopicArn=arn,
            Subject=subject[:100],
            Message=json.dumps(body, default=str, indent=2),
        )
        logger.info("SNS alert published event=%s topic=%s", event, arn)
        return True
    except Exception as exc:
        logger.warning("SNS publish failed (non-fatal): %s", exc)
        return False


def notify_vrp_failure(
    *,
    domain_id: str,
    workload_id: str,
    verdict: str,
    reason: str,
    proof_id: str | None = None,
    sns_client: Any | None = None,
) -> bool:
    return notify_ops(
        subject=f"[SDM] VRP {verdict} blocked commit — {domain_id}",
        event="vrp_verification_failed",
        domain_id=domain_id,
        workload_id=workload_id,
        verdict=verdict,
        detail=reason,
        extra={"proof_id": proof_id},
        sns_client=sns_client,
    )


def notify_rollback(
    *,
    domain_id: str,
    workload_id: str,
    detail: str | None = None,
    sns_client: Any | None = None,
) -> bool:
    return notify_ops(
        subject=f"[SDM] IceGuard rollback — {domain_id}",
        event="iceguard_rollback",
        domain_id=domain_id,
        workload_id=workload_id,
        detail=detail,
        sns_client=sns_client,
    )
