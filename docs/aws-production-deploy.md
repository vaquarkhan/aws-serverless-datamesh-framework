# Production-grade AWS deploy (SNS + observability)

**Audience:** platform / domain teams deploying Serverless Data Mesh to a real AWS account.

This guide covers a **prod-safe** path: package → Terraform → SNS paging → smoke checks → first mesh run.

Canonical Terraform: [`infrastructure/terraform/`](../infrastructure/terraform/README.md)  
Observability deep dive: [`observability-production.md`](observability-production.md)

---

## What you get in production

| Capability | Default (prod / medallion) | Why it matters |
|------------|----------------------------|----------------|
| **SNS ops topic** `{prefix}-ops-alerts` | Created (`create_ops_sns_topic=true`) | Email/Slack paging when something breaks |
| **CloudWatch alarms** | Lambda errors/throttles/p99, IceGuard rollback, DLQ depth, VRP trust, **SFN failed/timed-out** | Covers sync Step Functions path (DLQ alone is not enough) |
| **SQS DLQ** + IAM `sqs:SendMessage` | Wired | Async Lambda failures land in DLQ **and** can actually send |
| **App SNS alerts** | `SDM_SNS_TOPIC_ARN` on Lambda | VRP FAIL / IceGuard rollback publish JSON alerts (non-fatal) |
| **Trust dashboard** | CloudWatch dashboard | VRP PASS/FAIL by domain |
| **Structured logs** | `pvdm_outcome` JSON | Insights queries + metric filters |

**PVDM** (Physical · Verify · Durable · Metadata) © Vaquar Khan — proprietary method. Code is Apache-2.0.

---

## Prerequisites checklist

1. AWS account with Durable Lambda region support (e.g. `us-east-2`).
2. CLI: `aws`, `terraform` ≥ 1.5, Python 3.12+, Docker (optional for packaging).
3. Glue database + Iceberg table already exist (Terraform does **not** create table schemas).
4. Globally unique S3 bucket names for checkpoints, proofs, lakehouse.
5. An ops email (or Slack HTTPS webhook) ready to **confirm** the SNS subscription.

---

## Path A — Single-domain prod (fastest full stack)

### 1. Package Lambda

```bash
# Linux/macOS
SDM_EXTRAS=spark ./infrastructure/terraform/scripts/package_lambda.sh

# Windows PowerShell
.\infrastructure\terraform\scripts\package_lambda.ps1
```

Output: `infrastructure/terraform/build/domain-writer.zip`

### 2. Configure Terraform

```bash
cd infrastructure/terraform/environments/prod
cp terraform.tfvars.example terraform.tfvars
```

Edit `terraform.tfvars`:

```hcl
aws_region   = "us-east-2"
name_prefix  = "sdm-prod"
checkpoint_bucket_name = "sdm-prod-checkpoints-<ACCOUNT_ID>"
proof_bucket_name      = "sdm-prod-proofs-<ACCOUNT_ID>"
lakehouse_bucket_name  = "sdm-prod-lakehouse-<ACCOUNT_ID>"

create_ops_sns_topic = true
ops_alert_emails     = ["you@company.com"]
# ops_alert_https_endpoints = ["https://hooks.slack.com/services/..."]

enable_monitoring_alarms = true
enable_step_functions    = true
enable_durable_execution = true

# Production clocks
lambda_timeout_seconds            = 900
durable_execution_timeout_seconds = 5400
lambda_memory_mb                  = 4096
```

### 3. Apply

```bash
terraform init
terraform plan
terraform apply
```

### 4. Confirm SNS (required)

AWS emails a **Confirm subscription** link. Until you click it, alarms will not reach inbox.

```bash
terraform output ops_sns_topic_arn
aws sns list-subscriptions-by-topic --topic-arn "$(terraform output -raw ops_sns_topic_arn)"
```

### 5. Smoke checks

```bash
# From repo root
./scripts/aws_observability_smoke.sh
./scripts/aws_dlq_smoke_test.sh   # async DLQ path
```

### 6. First execution

```bash
aws stepfunctions start-execution \
  --state-machine-arn "$(terraform output -raw step_functions_arn)" \
  --input "$(terraform output -raw example_stepfunctions_input)"
```

Watch:

- Step Functions console (sync failures → **SFN alarms** → SNS)
- CloudWatch dashboard: `terraform output mesh_trust_dashboard_name`
- SNS for VRP FAIL / rollback / Lambda Errors

---

## Path B — Medallion mesh (multi-domain bronze→silver→gold)

```bash
serverless-data-mesh apply \
  --contract examples/medallion-e2e/northstar.mesh.yaml \
  --output examples/medallion-e2e/generated

# package zip (same as Path A)
cd infrastructure/terraform/environments/medallion
cp terraform.tfvars.example terraform.tfvars
# set buckets + mesh_generated_path + ops_alert_emails
terraform init && terraform apply
```

Start the mesh orchestrator with `partition_dt` (see medallion outputs / README).

---

## Alarm → action map (ops runbook)

| Alarm | Meaning | First action |
|-------|---------|--------------|
| `*-domain-writer-errors` | Lambda threw | CloudWatch Logs Insights: `event = "pvdm_outcome"` |
| `*-sfn-executions-failed` | Orchestration failed (sync path) | SFN execution history → failed state |
| `*-sfn-executions-timed-out` | Budget too low | Raise `durable_execution_timeout_seconds` / resume attempts |
| `*-dlq-messages` | Async failure destination | Read DLQ message; fix IAM/handler; redrive |
| `*-iceguard-rollback-detected` | Near Lambda timeout | Lower chunk size / raise memory / shorten segments |
| `*-vrp-trust-*` | VRP score &lt; PASS | Inspect Steward proofs bucket; block consumers |

App SNS (same topic): JSON body with `event` = `vrp_verification_failed` or `iceguard_rollback`.

---

## Best-practice defaults (do not skip)

1. **Always set `ops_alert_emails` or HTTPS** before go-live — empty subscriptions = silent alarms.
2. **Confirm SNS** before the first production backfill.
3. **Create Glue/Iceberg tables first** — apply succeeds without them; first commit fails.
4. **Prefer SFN alarms over DLQ alone** — production path is Durable Lambda via Step Functions sync invoke.
5. **Keep `create_ops_sns_topic=true`** unless you already pass `alarm_sns_topic_arns`.
6. Opt out of app SNS with `SDM_SNS_ENABLED=false` only in ephemeral sandboxes.
7. Use remote state + locking for prod (`backend "s3"`).

---

## Tear-down

```bash
terraform destroy
# Empty/delete S3 buckets if retention policies block destroy
```

---

## Related

- [terraform-guide.md](terraform-guide.md) — detailed variables / dual clocks  
- [first-mesh-on-aws.md](first-mesh-on-aws.md) — medallion 5-minute path  
- [observability-production.md](observability-production.md) — Insights queries  
- [NOTICE](../NOTICE) — PVDM proprietary method attribution  
