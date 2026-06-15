"""Spark-on-Lambda I/O pattern (physical layer only).

Use this module when your domain writer runs PySpark inside Lambda for Parquet
materialization. Metadata commits still go through ``GlueCatalogConnector``  - 
never through a Glue ETL job.

Install optional deps: ``pip install serverless-data-mesh[spark]``

Requires a Lambda layer or container image with JVM + PySpark sized for your
chunk (see docs/glue-connector.md).
"""

from __future__ import annotations

import logging
from typing import Any

logger = logging.getLogger(__name__)


def records_from_source_spark(
    spark: Any,
    source_uri: str,
    start: int,
    end: int,
) -> list[dict[str, Any]]:
    """Read source rows for VRP fingerprinting via Spark (replace SQL for production)."""
    # Example: spark.read.parquet(source_uri).filter(...).collect()
    raise NotImplementedError(
        "Implement domain-specific Spark read; return list[dict] for VRP hashing."
    )


def write_parquet_chunk_spark(
    spark: Any,
    target_uri: str,
    records: list[dict[str, Any]],
    *,
    partition_cols: dict[str, str] | None = None,
) -> list[str]:
    """Write one chunk to S3 Parquet via Spark; return data file URIs for 2PC commit."""
    # Example:
    #   df = spark.createDataFrame(records)
    #   out = f"{target_uri.rstrip('/')}/dt={partition_cols['dt']}"
    #   df.write.mode("append").parquet(out)
    #   return list_output_paths(out)
    raise NotImplementedError(
        "Implement Spark write; return S3 URIs passed to GlueCatalogConnector.prepare_commit()."
    )
