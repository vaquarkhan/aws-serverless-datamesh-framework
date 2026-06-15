"""100k row Iceberg write benchmark workload (XS)."""

WORKLOAD_ID = "bench-100k"
ROW_COUNT = 100_000
CHUNK_SIZE = 5_000

SCHEMA = {"id": "string", "payload_hash": "string"}
