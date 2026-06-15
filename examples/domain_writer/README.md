# Domain Writer Example

Reference Lambda handler for a data mesh domain team.

## Layout

```
examples/domain_writer/
  handler.py    # @durable_execution entry point
  workload.py   # Event → DataWriteWorkload mapping
  io.py         # Demo source reader / Parquet writer (lightweight stub)
  spark_io.py   # Spark-on-Lambda physical layer stub (optional)
  rules_io.py   # SparkRules DRL enrichment (pip install serverless-data-mesh[rules])
```

## Physical vs metadata

| Layer | Module | Runs on Lambda? |
|-------|--------|-----------------|
| Physical Parquet writes | `io.py` or `spark_io.py` | Yes |
| Business rules (DRL) | `rules_io.py` + `SparkRulesConnector` | Yes: `[rules]` extra |
| Glue metadata commit | `GlueCatalogConnector` in handler | Yes (REST client only) |
| AWS Glue ETL jobs |: | **No** |

See [docs/glue-connector.md](../../docs/glue-connector.md) and [docs/sparkrules-connector.md](../../docs/sparkrules-connector.md).

## Deploy

Point your SAM/CDK/Terraform Lambda handler at:

```
examples.domain_writer.handler.lambda_handler
```

## Required environment

| Variable | Description |
|----------|-------------|
| `ICEGUARD_CHECKPOINT_BUCKET` | S3 bucket for IceGuard checkpoints |
| `VRP_PROOF_BUCKET` | S3 bucket for VRP proof artifacts (optional, defaults to checkpoint bucket) |
| `ICEBERG_TABLE_BUCKET` | Glue/S3 Tables bucket name |
| `ICEBERG_WAREHOUSE` | `{account_id}:s3tablescatalog/{bucket}` for Glue REST |
| `AWS_REGION` | AWS region for Glue REST SigV4 |

## Spark on Lambda (optional)

```bash
pip install "serverless-data-mesh[spark]"
```

Implement `spark_io.py` and wire into `handler.py` `batch_writer` / `source_reader` callables.

## Sample event

```json
{
  "workload_id": "backfill-2026q2-orders",
  "total_records": 250000,
  "domain_id": "orders-domain",
  "partition_spec": {"dt": "2026-06-14"}
}
```
