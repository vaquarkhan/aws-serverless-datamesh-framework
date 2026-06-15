# Deployment Guide

## Python runtime

**Python 3.12+** is required (`veridata-recon` ships cp312 wheels).

## Install

```bash
pip install -e ".[dev]"
```

## Environment variables

| Variable | Required | Default |
|----------|----------|---------|
| `ICEGUARD_CHECKPOINT_BUCKET` | yes | — |
| `VRP_PROOF_BUCKET` | no | checkpoint bucket |
| `ICEBERG_TABLE_BUCKET` | yes | `default` |
| `ICEBERG_WAREHOUSE` | no | `{account}:s3tablescatalog/{bucket}` |
| `VRP_SIGNING_KEY_B64` | no | ephemeral key per invocation |
| `ICEGUARD_CHECKPOINT_INTERVAL` | no | `5000` |
| `ICEGUARD_ROLLBACK_THRESHOLD_MS` | no | `30000` |

## Lambda Durable Functions

Enable durable execution on the Lambda function (AWS Console or IaC). The handler
must use `@durable_execution` and receive `DurableContext`.

## IAM minimum permissions

- S3: `PutObject`, `GetObject`, `DeleteObject` on checkpoint + proof buckets
- Glue: `GetTable`, `GetDatabase`, `UpdateTable`
- Lake Formation: `GetDataAccess` (when using LF credential vending)

## SAM

See [infrastructure/sam/README.md](../infrastructure/sam/README.md).

## Terraform (production)

See [infrastructure/terraform/README.md](../infrastructure/terraform/README.md) for the full production stack including Step Functions.
