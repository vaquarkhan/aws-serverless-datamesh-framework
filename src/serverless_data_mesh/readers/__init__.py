"""Reference reader implementations for generated pipelines."""

from serverless_data_mesh.readers.s3_bronze import (
    batch_writer_s3_parquet,
    sink_reader_s3_parquet,
    source_reader_s3_landing,
)
from serverless_data_mesh.readers.upstream_parquet import (
    batch_writer_upstream,
    sink_reader_upstream,
    source_reader_upstream,
)

__all__ = [
    "batch_writer_s3_parquet",
    "batch_writer_upstream",
    "sink_reader_s3_parquet",
    "sink_reader_upstream",
    "source_reader_s3_landing",
    "source_reader_upstream",
]
