"""Step Functions task-token callback helpers (async LMI path up to 90 min).

Two supported orchestration modes:

1. **sync** — ``lambda:invoke`` (RequestResponse). AWS caps sync at 15 minutes.
2. **async_callback** — ``lambda:invoke.waitForTaskToken`` + ``InvocationType=Event``.
   On Lambda Managed Instances the segment may run up to 90 minutes; the handler
   must call ``SendTaskSuccess`` / ``SendTaskFailure`` with the task token.
"""

from __future__ import annotations

import json
import logging
from typing import Any

import boto3

logger = logging.getLogger(__name__)

SFN_INVOKE_MODE_SYNC = "sync"
SFN_INVOKE_MODE_ASYNC_CALLBACK = "async_callback"
VALID_SFN_INVOKE_MODES = frozenset({SFN_INVOKE_MODE_SYNC, SFN_INVOKE_MODE_ASYNC_CALLBACK})


def extract_task_token(event: dict[str, Any]) -> str | None:
    """Return Step Functions task token if present on the event."""
    token = event.get("task_token") or event.get("TaskToken")
    if isinstance(token, str) and token.strip():
        return token.strip()
    return None


def unwrap_workload_event(event: dict[str, Any]) -> dict[str, Any]:
    """Normalize SFN payloads so the domain writer always sees a workload dict.

    Sync mode: event is the workload itself.
    Async callback mode: event is ``{task_token, workload, resume_attempt?}``.
    """
    if isinstance(event.get("workload"), dict):
        workload = dict(event["workload"])
        if "resume_attempt" in event and "resume_attempt" not in workload:
            workload["resume_attempt"] = event["resume_attempt"]
        return workload
    return event


def complete_task_token(
    *,
    task_token: str | None,
    result: dict[str, Any],
    error: str | None = None,
    cause: str | None = None,
    sfn_client: Any | None = None,
) -> None:
    """Best-effort Step Functions callback when running the async LMI path."""
    if not task_token:
        return
    client = sfn_client or boto3.client("stepfunctions")
    if error:
        client.send_task_failure(
            taskToken=task_token,
            error=(error or "DomainWriterFailed")[:256],
            cause=(cause or json.dumps(result, default=str))[:32768],
        )
        logger.info("Sent Step Functions SendTaskFailure for async callback path")
        return
    client.send_task_success(
        taskToken=task_token,
        output=json.dumps(result, default=str),
    )
    logger.info("Sent Step Functions SendTaskSuccess for async callback path")
