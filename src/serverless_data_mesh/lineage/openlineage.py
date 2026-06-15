"""Emit OpenLineage RunEvent after successful Vaquar Pattern commits."""

from __future__ import annotations

import json
import logging
import os
import urllib.error
import urllib.request
import uuid
from datetime import datetime, timezone
from typing import Any

logger = logging.getLogger(__name__)

OPENLINEAGE_PRODUCER = "https://github.com/vaquarkhan/aws-serverless-datamesh-framework"


def _dataset(name: str, namespace: str = "s3") -> dict[str, str]:
    return {"namespace": namespace, "name": name}


def emit_openlineage_event(
    *,
    job_name: str,
    run_id: str | None = None,
    inputs: list[str],
    outputs: list[str],
    facets: dict[str, Any] | None = None,
    event_type: str = "COMPLETE",
    endpoint: str | None = None,
) -> dict[str, Any]:
    """Build and optionally POST an OpenLineage RunEvent.

    Set ``OPENLINEAGE_URL`` (or pass ``endpoint``) to POST JSON to Marquez/DataHub.
    Without an endpoint, returns the event dict for logging or local persistence.
    """
    run_id = run_id or str(uuid.uuid4())
    now = datetime.now(timezone.utc).replace(microsecond=0).isoformat()

    event: dict[str, Any] = {
        "eventType": event_type,
        "eventTime": now,
        "producer": OPENLINEAGE_PRODUCER,
        "schemaURL": "https://openlineage.io/spec/1-0-5/OpenLineage.json",
        "run": {"runId": run_id},
        "job": {"namespace": "serverless-data-mesh", "name": job_name},
        "inputs": [_dataset(name) for name in inputs],
        "outputs": [_dataset(name) for name in outputs],
        "facets": facets or {},
    }

    url = endpoint or os.environ.get("OPENLINEAGE_URL")
    if url:
        body = json.dumps(event).encode("utf-8")
        request = urllib.request.Request(
            url.rstrip("/") + "/api/v1/lineage",
            data=body,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        try:
            with urllib.request.urlopen(request, timeout=10) as response:
                logger.info("OpenLineage event posted (%s)", response.status)
        except urllib.error.URLError as exc:
            logger.warning("OpenLineage POST failed: %s", exc)

    return event


def emit_from_commit_result(
    *,
    domain_id: str,
    target_table: str,
    source_namespace: str,
    commit_result: dict[str, Any],
    proof_id: str | None = None,
    checkpoint_path: str | None = None,
) -> dict[str, Any]:
    """Convenience wrapper after ``coordinator.execute_workload()`` returns committed."""
    if commit_result.get("outcome") != "committed":
        return {}

    return emit_openlineage_event(
        job_name=f"{domain_id}.{target_table}",
        run_id=commit_result.get("workload_id"),
        inputs=[source_namespace],
        outputs=[target_table],
        facets={
            "vrp_proof_id": proof_id or commit_result.get("proof_chain_tail"),
            "iceguard_checkpoint": checkpoint_path,
            "row_count": commit_result.get("records_written"),
            "snapshot_id": commit_result.get("snapshot_id"),
            "vaquar_pattern": "PVDM",
        },
    )
