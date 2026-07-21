# Deployment Guide

**Production-grade path (SNS + alarms + smoke):** see **[aws-production-deploy.md](aws-production-deploy.md)**.

## Python runtime

**Python 3.12+** is required (`veridata-recon` ships cp312 wheels).

## Install

```bash
pip install serverless-data-mesh
# or from source
pip install -e ".[dev]"
```

## Environment variables

| Variable | Required | Default | Notes |
|----------|----------|---------|-------|
| `ICEGUARD_CHECKPOINT_BUCKET` | yes | — | IceGuard checkpoints |
| `VRP_PROOF_BUCKET` | no | checkpoint bucket | VRP / PVDM-A proofs |
| `ICEBERG_TABLE_BUCKET` | yes | `default` | Lakehouse |
| `ICEBERG_WAREHOUSE` | no | `{account}:s3tablescatalog/{bucket}` | Glue REST |
| `VRP_SIGNING_KEY_B64` | no | ephemeral | Prefer KMS in prod |
| `VRP_KMS_KEY_ID` | no | — | Optional KMS Sign envelopes |
| `ICEGUARD_CHECKPOINT_INTERVAL` | no | `5000` | |
| `ICEGUARD_ROLLBACK_THRESHOLD_MS` | no | `30000` | |
| `SDM_SNS_TOPIC_ARN` | no | — | Ops alerts (VRP FAIL / rollback) |
| `SDM_SNS_ENABLED` | no | `true` | Set `false` to mute app SNS |
| `SDM_DISABLE_METRICS` | no | — | Skip CloudWatch PutMetricData |
| `SDM_ATTESTATION_ENABLED` | no | `1` | PVDM-A decision records |

## Lambda Durable Functions

Enable durable execution on the Lambda function (AWS Console or IaC). The handler
must use `@durable_execution` and receive `DurableContext`.

## IAM minimum permissions

- S3: `PutObject`, `GetObject`, `DeleteObject` on checkpoint + proof buckets
- Glue: `GetTable`, `GetDatabase`, `UpdateTable`
- Lake Formation: `GetDataAccess` (when using LF credential vending)
- SQS: `SendMessage` on the domain-writer DLQ (async on_failure)
- SNS: `Publish` on the ops alerts topic
- CloudWatch: `PutMetricData` for `ServerlessDataMesh*` namespaces

## Observability (prod)

Terraform creates:

1. SNS topic `{name_prefix}-ops-alerts` (confirm email subscriptions)
2. CloudWatch alarms → SNS (Lambda, DLQ, VRP trust, Step Functions failed/timed-out)
3. Mesh trust dashboard
4. Lambda env `SDM_SNS_TOPIC_ARN` for in-process VRP/rollback alerts

See [aws-production-deploy.md](aws-production-deploy.md) and [observability-production.md](observability-production.md).

## SAM

See [infrastructure/sam/README.md](../infrastructure/sam/README.md).

## Terraform (production)

See [infrastructure/terraform/README.md](../infrastructure/terraform/README.md) for the full production stack including Step Functions, SNS, and monitoring.
