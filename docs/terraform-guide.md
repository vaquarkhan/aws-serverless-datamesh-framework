# Terraform Deployment — Step by Step

Each step explains **what it is** and **what we achieve** before commands.

---

## Step 1 — Understand the stack

### What is this?

Seven Terraform modules wired in `environments/prod/main.tf`: storage, IAM, Lambda, Step Functions, EventBridge, messaging (DLQ), monitoring.

### What we try to achieve

One `terraform apply` provisions the full production mesh: encrypted S3, durable Lambda, orchestrated backfills with automatic resume after IceGuard rollback, and operational alarms.

---

## Step 2 — Choose region

### What is this?

AWS region for all resources. Lambda Durable Functions have regional availability constraints.

### What we try to achieve

Deploy where durable execution is supported (commonly `us-east-2` at launch). Set in `terraform.tfvars`:

```hcl
aws_region = "us-east-2"
```

---

## Step 3 — Build the Lambda package

### What is this?

A zip containing `serverless_data_mesh`, dependencies (iceguard, veridata-recon, pyiceberg, durable SDK), and `examples/`.

### What we try to achieve

Produce `infrastructure/terraform/build/domain-writer.zip` referenced by the Lambda module.

```bash
./infrastructure/terraform/scripts/package_lambda.sh
```

Windows:

```powershell
.\infrastructure\terraform\scripts\package_lambda.ps1
```

---

## Step 4 — Configure tfvars

### What is this?

Environment-specific variables: bucket names, Glue identifiers, feature flags.

### What we try to achieve

Globally unique S3 names and explicit control over Step Functions / EventBridge / alarms.

```bash
cd infrastructure/terraform/environments/prod
cp terraform.tfvars.example terraform.tfvars
```

Edit:

```hcl
name_prefix            = "sdm-prod"
checkpoint_bucket_name = "sdm-prod-chk-123456789012"
proof_bucket_name      = "sdm-prod-vrp-123456789012"
lakehouse_bucket_name  = "sdm-prod-lake-123456789012"

enable_step_functions       = true
enable_eventbridge_schedule = false   # set true for nightly cron backfill
enable_monitoring_alarms    = true

# Long backfills: configure all timeout knobs in terraform.tfvars
lambda_timeout_seconds            = 900
durable_execution_timeout_seconds = 5400
lambda_memory_mb                  = 4096
durable_retention_days            = 14
max_resume_attempts               = 10
sfn_invoke_timeout_buffer_seconds = 60
resume_wait_seconds               = 60
# iceguard_rollback_threshold_ms  = null  # auto-derived from lambda_timeout_seconds
```

### 90-minute backfills (two clocks)

| Setting | Meaning |
|---------|---------|
| `lambda_timeout_seconds = 900` | AWS hard max per container (15 min) |
| `durable_execution_timeout_seconds = 5400` | Total durable execution budget (90 min) |
| `lambda_memory_mb` | Chunk throughput — raise if p99 duration nears timeout |
| `sfn_invoke_timeout_buffer_seconds` | SFN `TimeoutSeconds` = lambda + buffer |
| `max_resume_attempts` | Resume loops after `rolled_back`; prod auto-bumps to `ceil(durable/lambda)+2` |
| `iceguard_rollback_threshold_ms` | Null = auto (~33ms × lambda timeout, clamped 10s–60s) |

Step Functions waits **~960s per invoke** (one segment), not 90 minutes. A 90-minute job typically needs ~6 segment invocations plus resume buffer.

After apply, verify:

```bash
terraform output execution_timeouts
```

---

## Step 5 — Initialize and plan

### What is this?

Terraform downloads providers (AWS >= 6.25 for `durable_config`) and builds the dependency graph.

### What we try to achieve

Review every resource before apply — catch IAM/bucket naming issues early.

```bash
terraform init
terraform plan -out=prod.tfplan
```

---

## Step 6 — Apply infrastructure

### What is this?

Creates S3 buckets, IAM roles, Lambda Durable Function with `live` alias, Step Functions state machine, SQS DLQ, CloudWatch alarms.

### What we try to achieve

Live production environment ready to accept backfill workloads.

```bash
terraform apply prod.tfplan
```

Capture outputs:

```bash
terraform output domain_writer_qualified_arn
terraform output step_functions_arn
terraform output example_stepfunctions_input
```

---

## Step 7 — Run backfill via Step Functions (recommended)

### What is this?

The **backfill orchestrator** state machine invokes the domain writer and loops on `rolled_back` until `committed` or max attempts.

### What we try to achieve

Hands-free long backfills: IceGuard timeout rollbacks are automatically resumed without duplicating committed chunks. Each Step Functions invocation runs at most one 15-minute Lambda segment; the resume loop stitches segments until `committed` or `max_resume_attempts`.

```bash
aws stepfunctions start-execution \
  --state-machine-arn "$(terraform output -raw step_functions_arn)" \
  --name "backfill-$(date +%Y%m%d-%H%M%S)" \
  --input '{
    "workload_id": "backfill-2026q2-orders",
    "total_records": 250000,
    "domain_id": "orders-domain",
    "source_uri": "s3://YOUR_LAKEHOUSE/source/orders/",
    "target_uri": "s3://YOUR_LAKEHOUSE/curated/orders/",
    "partition_spec": {"dt": "2026-06-14"}
  }'
```

Monitor:

```bash
aws stepfunctions describe-execution --execution-arn <arn>
```

---

## Step 8 — Direct Lambda invoke (debug)

### What is this?

Bypass Step Functions and invoke the durable function directly via the **`live` alias** (required for durable execution).

### What we try to achieve

Fast iteration during handler development.

```bash
aws lambda invoke \
  --function-name "$(terraform output -raw domain_writer_function_name):live" \
  --payload '{"workload_id":"debug-001","total_records":100,"domain_id":"orders-domain"}' \
  response.json

type response.json   # Windows
cat response.json    # Linux/macOS
```

---

## Step 9 — Enable scheduled backfills

### What is this?

EventBridge rule → Step Functions with a default nightly payload.

### What we try to achieve

Unattended recurring materialization (disabled by default for safety).

In `terraform.tfvars`:

```hcl
enable_eventbridge_schedule = true
```

Re-apply. Default schedule: `cron(0 2 * * ? *)` (02:00 UTC daily). Customize in `modules/eventbridge/variables.tf`.

---

## Step 10 — Monitor operations

### What is this?

CloudWatch alarms on Lambda errors, throttles, p99 duration, and IceGuard rollback log pattern.

### What we try to achieve

Leading indicator of near-timeout pressure before silent data loss occurs.

Optional SNS wiring in `terraform.tfvars`:

```hcl
alarm_sns_topic_arns = ["arn:aws:sns:us-east-2:123456789012:platform-alerts"]
```

Inspect proofs after each chunk:

```
s3://{proof_bucket}/{domain_id}/{workload_id}/proofs/chunk-000000.vrp.json
```

---

## Step 11 — Glue prerequisites

### What is this?

Glue database + Iceberg table that the REST catalog adapter commits to.

### What we try to achieve

Metadata target exists before first `committed` outcome. This stack does **not** create Glue tables — provision separately:

- Database: `raw_orders`
- Table: `orders_curated`
- Lake Formation grants for the Lambda IAM role

---

## Module map

| Path | Deploys |
|------|---------|
| `modules/storage` | checkpoint + proof + lakehouse S3 |
| `modules/iam` | Lambda + Step Functions IAM |
| `modules/lambda` | Durable Function + alias + DLQ hook |
| `modules/stepfunctions` | Resume orchestrator |
| `modules/eventbridge` | Optional cron trigger |
| `modules/messaging` | SQS DLQ |
| `modules/monitoring` | CloudWatch alarms |

Full reference: [infrastructure/terraform/README.md](../infrastructure/terraform/README.md)
