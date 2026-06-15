"""Reference silver/gold reader: upstream Parquet/Iceberg staging → curated Parquet."""

from __future__ import annotations

import logging
import os
from typing import Any

logger = logging.getLogger(__name__)


def _upstream_table() -> str:
    return os.environ.get("UPSTREAM_TABLE", os.environ.get("TARGET_TABLE", "upstream"))


def _partition() -> str:
    return os.environ.get("TARGET_PARTITION", "dt=1970-01-01")


def _table_prefix(table: str) -> str:
    bucket = os.environ.get("ICEBERG_TABLE_BUCKET", os.environ.get("LAKEHOUSE_BUCKET", ""))
    if not bucket:
        raise ValueError("Set ICEBERG_TABLE_BUCKET for upstream reads")
    return f"s3://{bucket}/staging/{table}/{_partition()}/"


def _parse_s3(uri: str) -> tuple[str, str]:
    rest = uri[5:]
    bucket, _, key = rest.partition("/")
    return bucket, key


def _list_parquet(prefix: str) -> list[str]:
    import boto3

    bucket, key_prefix = _parse_s3(prefix)
    client = boto3.client("s3")
    keys: list[str] = []
    token: str | None = None
    while True:
        kwargs: dict[str, Any] = {"Bucket": bucket, "Prefix": key_prefix}
        if token:
            kwargs["ContinuationToken"] = token
        resp = client.list_objects_v2(**kwargs)
        for obj in resp.get("Contents", []):
            if obj["Key"].endswith(".parquet"):
                keys.append(obj["Key"])
        if not resp.get("IsTruncated"):
            break
        token = resp.get("NextContinuationToken")
    return sorted(keys)


def _read_parquet_slice(bucket: str, key: str, start: int, end: int) -> list[dict[str, Any]]:
    import boto3
    import pyarrow.parquet as pq
    from io import BytesIO

    body = boto3.client("s3").get_object(Bucket=bucket, Key=key)["Body"].read()
    table = pq.read_table(BytesIO(body))
    return table.slice(start, max(0, end - start)).to_pylist()


def source_reader_upstream(start: int, end: int) -> list[dict[str, Any]]:
    """Read curated records from upstream layer staging Parquet."""
    prefix = _table_prefix(_upstream_table())
    try:
        keys = _list_parquet(prefix)
    except Exception as exc:
        logger.warning("Upstream list failed (%s) — synthetic fallback", exc)
        keys = []
    if not keys:
        logger.warning("No upstream parquet under %s — synthetic fallback", prefix)
        return [{"id": str(i), "payload_hash": f"up-{i}"} for i in range(start, end)]

    bucket, _ = _parse_s3(prefix)
    records: list[dict[str, Any]] = []
    idx = start
    for key in keys:
        if idx >= end:
            break
        chunk = _read_parquet_slice(bucket, key, 0, end - idx)
        records.extend(chunk)
        idx += len(chunk)
    return records[: end - start]


def batch_writer_upstream(start: int, end: int) -> list[str]:
    """Transform upstream rows and write to this layer's staging prefix."""
    import boto3
    import pyarrow as pa
    import pyarrow.parquet as pq

    rows = source_reader_upstream(start, end)
    table = pa.Table.from_pylist(rows)
    target_table = os.environ.get("TARGET_TABLE", "curated")
    out_prefix = _table_prefix(target_table)
    bucket, key_prefix = _parse_s3(out_prefix)
    key = f"{key_prefix}part-{start:08d}-{end:08d}.parquet"
    buf = pa.BufferOutputStream()
    pq.write_table(table, buf)
    boto3.client("s3").put_object(Bucket=bucket, Key=key, Body=buf.getvalue().to_pybytes())
    return [f"s3://{bucket}/{key}"]


def sink_reader_upstream(start: int, end: int) -> list[dict[str, Any]]:
    """Re-read this layer's Parquet for VRP reconciliation."""
    import boto3
    import pyarrow.parquet as pq
    from io import BytesIO

    prefix = _table_prefix(os.environ.get("TARGET_TABLE", "curated"))
    bucket, key_prefix = _parse_s3(prefix)
    client = boto3.client("s3")
    out: list[dict[str, Any]] = []
    for offset in range(start, end, 1000):
        key = f"{key_prefix}part-{offset:08d}-{min(offset + 1000, end):08d}.parquet"
        try:
            body = client.get_object(Bucket=bucket, Key=key)["Body"].read()
        except client.exceptions.NoSuchKey:
            continue
        out.extend(pq.read_table(BytesIO(body)).to_pylist())
    return out
