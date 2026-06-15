"""Domain contracts and workload types."""

from serverless_data_mesh.types.workload import (
    BatchWriterFn,
    ChunkWriteResult,
    DataProductContract,
    DataWriteWorkload,
    DomainTransactionBoundary,
    SourceReaderFn,
    WriteOutcome,
)

__all__ = [
    "BatchWriterFn",
    "ChunkWriteResult",
    "DataProductContract",
    "DataWriteWorkload",
    "DomainTransactionBoundary",
    "SourceReaderFn",
    "WriteOutcome",
]
