"""Structured JSON logs for CloudWatch Insights."""

from __future__ import annotations

import json
import logging
from typing import Any

logger = logging.getLogger(__name__)


def log_pvdm_outcome(**fields: Any) -> None:
    """Emit one JSON line per pipeline outcome (queryable in CloudWatch Logs Insights)."""
    payload = {"event": "pvdm_outcome", **fields}
    logger.info("%s", json.dumps(payload, default=str, sort_keys=True))
