"""Anti-replay nonce ledger for PVDM Metadata (paper L7 / N5)."""

from __future__ import annotations

import logging
import os
import threading
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

logger = logging.getLogger(__name__)

_lock = threading.Lock()
_memory: set[str] = set()


class NonceReplayError(Exception):
    """Raised when a proof nonce was already consumed."""


def _local_root() -> Path:
    raw = os.environ.get("SDM_NONCE_LEDGER_DIR")
    if raw:
        path = Path(raw)
    else:
        path = Path(os.environ.get("TMPDIR") or os.environ.get("TEMP") or "/tmp") / "sdm-nonce-ledger"
    path.mkdir(parents=True, exist_ok=True)
    return path


def _claim_local(nonce: str) -> bool:
    path = _local_root() / f"{nonce}.claimed"
    try:
        fd = os.open(str(path), os.O_CREAT | os.O_EXCL | os.O_WRONLY)
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            handle.write("1")
        return True
    except FileExistsError:
        return False


def _claim_s3(nonce: str, bucket: str, *, s3_client: Any | None = None) -> bool:
    import boto3
    from botocore.exceptions import ClientError

    client = s3_client or boto3.client("s3")
    key = f"pvdm-nonces/{nonce}"
    try:
        client.head_object(Bucket=bucket, Key=key)
        return False
    except ClientError as exc:
        code = exc.response.get("Error", {}).get("Code", "")
        if code not in ("404", "NoSuchKey", "NotFound"):
            raise
    try:
        client.put_object(
            Bucket=bucket,
            Key=key,
            Body=b"1",
            ContentType="text/plain",
        )
        return True
    except ClientError:
        # Another writer won the race.
        return False


def claim_nonce(
    nonce: str,
    *,
    proof_bucket: str | None = None,
    s3_client: Any | None = None,
) -> None:
    """Burn a nonce. Raises NonceReplayError if already used."""
    if not nonce:
        raise NonceReplayError("empty nonce")

    with _lock:
        if nonce in _memory:
            raise NonceReplayError(f"nonce already used (memory): {nonce}")
        _memory.add(nonce)

    if not _claim_local(nonce):
        raise NonceReplayError(f"nonce already used (local ledger): {nonce}")

    bucket = proof_bucket or os.environ.get("VRP_PROOF_BUCKET") or os.environ.get("SDM_PROOF_BUCKET")
    if bucket and not bucket.startswith("/") and "://" not in bucket:
        if not _claim_s3(nonce, bucket, s3_client=s3_client):
            raise NonceReplayError(f"nonce already used (s3 ledger): {nonce}")
    elif bucket and bucket.startswith("s3://"):
        parsed = urlparse(bucket)
        if not _claim_s3(nonce, parsed.netloc, s3_client=s3_client):
            raise NonceReplayError(f"nonce already used (s3 ledger): {nonce}")
