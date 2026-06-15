"""1M row Iceberg write benchmark workload (S)."""

WORKLOAD_ID = "bench-1m"
ROW_COUNT = 1_000_000
CHUNK_SIZE = 10_000

SCHEMA = {"id": "string", "payload_hash": "string"}
