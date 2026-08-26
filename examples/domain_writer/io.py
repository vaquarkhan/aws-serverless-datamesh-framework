"""I/O helpers for the domain writer example (replace with Spark/SoAL in production)."""

from __future__ import annotations

import hashlib
import json
import logging
import os
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


def _staging_root(target_uri: str) -> Path:
    """Local staging directory for demo writes (file digests + sink re-read)."""
    if target_uri.startswith("s3://"):
        base = Path(os.environ.get("SDM_LOCAL_STAGING", "/tmp/sdm-staging"))
        safe = target_uri.replace("s3://", "").replace("/", "_")
        return base / safe
    return Path(target_uri.removeprefix("file://"))


def records_from_source(source_uri: str, start: int, end: int) -> list[dict[str, Any]]:
    """Load source records for VRP fingerprinting (demo: deterministic synthetic rows)."""
    records: list[dict[str, Any]] = []
    for offset in range(start, end):
        payload = f"{source_uri}:{offset}"
        records.append(
            {
                "id": str(offset),
                "payload_hash": hashlib.sha256(payload.encode()).hexdigest(),
            }
        )
    return records


def write_parquet_chunk(
    target_uri: str,
    start: int,
    end: int,
    *,
    source_uri: str | None = None,
) -> list[str]:
    """Materialize one chunk as JSONL staging files (demo stand-in for Parquet)."""
    partition = os.environ.get("TARGET_PARTITION", "dt=2026-06-14")
    root = _staging_root(target_uri) / partition
    root.mkdir(parents=True, exist_ok=True)
    intent_uri = source_uri or os.environ.get("SOURCE_URI", target_uri)
    records = records_from_source(intent_uri, start, end)
    path = root / f"part-{start:08d}-{end:08d}.jsonl"
    with path.open("w", encoding="utf-8") as handle:
        for row in records:
            handle.write(json.dumps(row, sort_keys=True) + "\n")
    uri = str(path.resolve())
    logger.info("Wrote %d staging rows to %s", len(records), uri)
    return [uri]


def sink_reader(target_uri: str, start: int, end: int) -> list[dict[str, Any]]:
    """Re-read staged chunk bytes for VRP (source≠sink compare)."""
    partition = os.environ.get("TARGET_PARTITION", "dt=2026-06-14")
    path = _staging_root(target_uri) / partition / f"part-{start:08d}-{end:08d}.jsonl"
    if not path.exists():
        return []
    rows: list[dict[str, Any]] = []
    with path.open(encoding="utf-8") as handle:
        for line in handle:
            line = line.strip()
            if line:
                rows.append(json.loads(line))
    return rows
