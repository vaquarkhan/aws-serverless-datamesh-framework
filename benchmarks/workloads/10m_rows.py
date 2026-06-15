"""10M row Iceberg write benchmark workload (M)."""

WORKLOAD_ID = "bench-10m"
ROW_COUNT = 10_000_000
CHUNK_SIZE = 25_000

SCHEMA = {"id": "string", "payload_hash": "string"}
