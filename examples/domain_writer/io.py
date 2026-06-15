"""I/O helpers for the domain writer example (replace with Spark/SoAL in production)."""

from __future__ import annotations

import hashlib
import logging
import os
from typing import Any

logger = logging.getLogger(__name__)


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


def write_parquet_chunk(target_uri: str, start: int, end: int) -> list[str]:
    """Simulate Parquet materialization for one chunk."""
    partition = os.environ.get("TARGET_PARTITION", "dt=2026-06-14")
    base = target_uri.rstrip("/")
    paths = [f"{base}/{partition}/part-{offset:08d}.parquet" for offset in range(start, end)]
    logger.info("Wrote %d Parquet objects under %s", len(paths), base)
    return paths
