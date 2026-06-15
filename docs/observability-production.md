# Production observability

Validated on real AWS Lambda (Vaquar assessment). Framework fixes for logs, metrics, proofs, DLQ, and dashboards.

## Structured logs (CloudWatch Insights)

Every pipeline outcome emits one JSON line:

```json
{"event": "pvdm_outcome", "domain_id": "orders", "outcome": "committed", "rows": 1000, "duration_ms": 1234.5, "proof_id": "vrp-...", "snapshot_id": "snap-..."}
```

**Query:**

```
fields @timestamp, outcome, rows, duration_ms, proof_id
| filter event = "pvdm_outcome"
| sort @timestamp desc
```

## VRP proofs in S3

- **Production:** `VRPProofGenerator.persist_proof()` writes to `s3://{VRP_PROOF_BUCKET}/...`
- **Local demo:** when `VRP_PROOF_BUCKET` is set, `LocalPVDMRuntime` uses S3 instead of `/tmp`

## CloudWatch metrics

| Source | Namespace | Metrics |
|--------|-----------|---------|
| `publish_vrp_metric()` | `ServerlessDataMesh/Trust` | `VRPTrustScore`, `VRPRowCount` |
| Log metric filters | `ServerlessDataMesh/Trust` | `VRPPass`, `VRPFail`, `MetadataCommitted` |
| Lambda (dashboard) | `AWS/Lambda` | Invocations, Errors, Duration |
| DLQ (dashboard + alarm) | `AWS/SQS` | `ApproximateNumberOfMessagesVisible` |

Disable metrics: `SDM_METRICS_ENABLED=false` or `SDM_DISABLE_METRICS=true`

## Terraform

- Lambda **log group** name: `/aws/lambda/{name_prefix}-domain-writer` (matches function name)
- Lambda **logging_config**: JSON format
- **Monitoring dashboard**: trust + ops widgets (invocations, errors, duration, DLQ, VRP ratio)
- **DLQ alarm** when `dlq_queue_name` is passed to monitoring module

## Post-deploy smoke (before destroy)

```bash
SDM_NAME_PREFIX=sdm-prod AWS_REGION=us-east-2 ./scripts/aws_observability_smoke.sh
```

Wait **5+ minutes** after invoke before destroying stack — CloudWatch metrics namespaces can lag.

## DLQ test (async failure)

Requires unhandled crash/timeout (not a returned `verification_failed` payload):

```bash
export SDM_LAMBDA_ARN="arn:aws:lambda:...:function:sdm-prod-domain-writer:live"
export SDM_DLQ_URL="https://sqs....amazonaws.com/.../sdm-prod-domain-writer-dlq"
./scripts/aws_dlq_smoke_test.sh
```

See also: [mesh-trust-dashboard.md](mesh-trust-dashboard.md)
