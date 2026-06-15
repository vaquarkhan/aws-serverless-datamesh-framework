"""Reference implementation: orders domain PySpark readers for Lambda.

Copy patterns into generated domains/orders/readers.py after compile.
"""

from __future__ import annotations

from typing import Any

_SPARK: Any | None = None


def _spark() -> Any:
    global _SPARK
    if _SPARK is None:
        from pyspark.sql import SparkSession
        from pyspark.sql import functions as F

        _SPARK = (
            SparkSession.builder.appName("orders-curated-nightly")
            .config("spark.sql.shuffle.partitions", "16")
            .config("spark.hadoop.fs.s3a.connection.maximum", "100")
            .getOrCreate()
        )
    return _SPARK


def source_reader(start: int, end: int) -> list[dict[str, Any]]:
    """Read OMS export: join headers + lines, dedup, aggregate."""
    spark = _spark()
    dt = "EVENT_PARTITION"  # injected from Step Functions payload partition_spec.dt
    headers = spark.read.parquet(f"s3://producer-orders/raw/headers/dt={dt}/")
    lines = spark.read.parquet(f"s3://producer-orders/raw/lines/dt={dt}/")

    curated = (
        lines.join(headers, "order_id")
        .filter(F.col("status") != "CANCELLED")
        .groupBy("order_id", "customer_id", "status")
        .agg(
            F.sum("line_amount").alias("order_total"),
            F.count("*").alias("line_count"),
        )
        .orderBy("order_id")
    )

    rows = curated.filter((F.col("order_id") >= start) & (F.col("order_id") < end)).collect()
    return [row.asDict() for row in rows]


def sink_reader(start: int, end: int) -> list[dict[str, Any]]:
    spark = _spark()
    dt = "EVENT_PARTITION"
    df = spark.read.parquet(f"s3://publisher-lakehouse/orders_curated/dt={dt}/")
    rows = df.filter((df.order_id >= start) & (df.order_id < end)).collect()
    return [row.asDict() for row in rows]


def batch_writer(start: int, end: int) -> list[str]:
    spark = _spark()
    records = source_reader(start, end)
    if not records:
        return []
    df = spark.createDataFrame(records)
    dt = "EVENT_PARTITION"
    out = f"s3://publisher-lakehouse/orders_curated/dt={dt}/part-{start:08d}"
    df.write.mode("append").parquet(out)
    return [f"{out}/part-00000.parquet"]
