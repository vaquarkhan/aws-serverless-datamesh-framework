"""Reference bronze reader: S3 landing zone → Parquet chunks (PyArrow + boto3)."""

from __future__ import annotations

import json
import logging
import os
from typing import Any

logger = logging.getLogger(__name__)


def _landing_prefix() -> str:
    prefix = os.environ.get("BRONZE_LANDING_PREFIX", "")
    if not prefix:
        bucket = os.environ.get("BRONZE_LANDING_BUCKET", os.environ.get("ICEBERG_TABLE_BUCKET", ""))
        key = os.environ.get("BRONZE_LANDING_KEY", "landing/")
        if not bucket:
            raise ValueError("Set BRONZE_LANDING_PREFIX or BRONZE_LANDING_BUCKET + BRONZE_LANDING_KEY")
        prefix = f"s3://{bucket}/{key.lstrip('/')}"
    return prefix.rstrip("/") + "/"


def _staging_prefix() -> str:
    bucket = os.environ.get("ICEBERG_TABLE_BUCKET", os.environ.get("LAKEHOUSE_BUCKET", ""))
    table = os.environ.get("TARGET_TABLE", "bronze_table")
    partition = os.environ.get("TARGET_PARTITION", "dt=1970-01-01")
    if not bucket:
        raise ValueError("Set ICEBERG_TABLE_BUCKET or LAKEHOUSE_BUCKET for bronze staging writes")
    return f"s3://{bucket}/staging/{table}/{partition}/"


def _parse_s3(uri: str) -> tuple[str, str]:
    if not uri.startswith("s3://"):
        raise ValueError(f"Expected s3:// URI, got {uri!r}")
    rest = uri[5:]
    bucket, _, key = rest.partition("/")
    return bucket, key


def _list_landing_keys(prefix: str) -> list[str]:
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
            name = obj["Key"]
            if name.endswith((".json", ".jsonl", ".parquet", ".csv")):
                keys.append(name)
        if not resp.get("IsTruncated"):
            break
        token = resp.get("NextContinuationToken")
    return sorted(keys)


def _read_object_records(bucket: str, key: str, start: int, end: int) -> list[dict[str, Any]]:
    import boto3

    body = boto3.client("s3").get_object(Bucket=bucket, Key=key)["Body"].read()
    if key.endswith(".jsonl"):
        lines = body.decode("utf-8").splitlines()
        return [json.loads(line) for line in lines[start:end]]
    if key.endswith(".json"):
        payload = json.loads(body.decode("utf-8"))
        if isinstance(payload, list):
            return payload[start:end]
        return [payload]
    if key.endswith(".parquet"):
        import pyarrow.parquet as pq
        from io import BytesIO

        table = pq.read_table(BytesIO(body))
        rows = table.slice(start, end - start).to_pylist()
        return rows
    if key.endswith(".csv"):
        import pyarrow.csv as pacsv
        from io import BytesIO

        table = pacsv.read_csv(BytesIO(body))
        return table.slice(start, end - start).to_pylist()
    raise ValueError(f"Unsupported landing format: {key}")


def source_reader_s3_landing(start: int, end: int) -> list[dict[str, Any]]:
    """Read records [start, end) from S3 landing files (round-robin across keys)."""
    prefix = _landing_prefix()
    try:
        keys = _list_landing_keys(prefix)
    except Exception as exc:
        logger.warning("S3 landing list failed (%s) — synthetic fallback", exc)
        keys = []
    if not keys:
        logger.warning("No landing objects under %s — returning synthetic rows for demo", prefix)
        return [{"id": str(i), "payload": f"demo-{i}"} for i in range(start, end)]

    bucket, _ = _parse_s3(prefix)
    records: list[dict[str, Any]] = []
    idx = start
    while idx < end:
        key = keys[idx % len(keys)]
        chunk = _read_object_records(bucket, key, 0, min(end - idx, 1000))
        if not chunk:
            break
        take = min(len(chunk), end - idx)
        records.extend(chunk[:take])
        idx += take
    return records


def batch_writer_s3_parquet(start: int, end: int) -> list[str]:
    """Write one Parquet chunk to lakehouse staging prefix."""
    import pyarrow as pa
    import pyarrow.parquet as pq
    import boto3

    rows = source_reader_s3_landing(start, end)
    if not rows:
        return []
    table = pa.Table.from_pylist(rows)
    staging = _staging_prefix()
    bucket, key_prefix = _parse_s3(staging)
    key = f"{key_prefix}part-{start:08d}-{end:08d}.parquet"
    buf = pa.BufferOutputStream()
    pq.write_table(table, buf)
    boto3.client("s3").put_object(Bucket=bucket, Key=key, Body=buf.getvalue().to_pybytes())
    uri = f"s3://{bucket}/{key}"
    logger.info("Wrote bronze chunk %s (%d rows)", uri, len(rows))
    return [uri]


def sink_reader_s3_parquet(start: int, end: int) -> list[dict[str, Any]]:
    """Re-read written Parquet for VRP sink reconciliation."""
    import boto3
    import pyarrow.parquet as pq
    from io import BytesIO

    staging = _staging_prefix()
    bucket, key_prefix = _parse_s3(staging)
    client = boto3.client("s3")
    records: list[dict[str, Any]] = []
    for offset in range(start, end, 1000):
        key = f"{key_prefix}part-{offset:08d}-{min(offset + 1000, end):08d}.parquet"
        try:
            body = client.get_object(Bucket=bucket, Key=key)["Body"].read()
        except client.exceptions.NoSuchKey:
            continue
        table = pq.read_table(BytesIO(body))
        records.extend(table.to_pylist())
    return records
