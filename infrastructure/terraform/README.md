# Terraform — Production Infrastructure

Production-grade AWS infrastructure for serverless-data-mesh.

## What gets deployed

| Module | Resources | Purpose |
|--------|-----------|---------|
| **storage** | 3× S3 buckets (encrypted, versioned, lifecycle) | Checkpoints, VRP proofs, lakehouse Parquet |
| **iam** | Lambda + Step Functions roles | Least-privilege Glue/S3/LF access |
| **lambda** | Durable Function + `live` alias + DLQ | Domain writer handler |
| **stepfunctions** | Backfill orchestrator | Resume loop after `rolled_back` |
| **eventbridge** | Optional schedule | Cron → Step Functions |
| **messaging** | SQS DLQ | Failed async invocations |
| **monitoring** | CloudWatch alarms + rollback metric | Ops visibility |

## Architecture

```
EventBridge (optional schedule)
        │
        ▼
Step Functions ──resume loop──► Lambda :live (Durable)
        │                              │
        │                              ├── IceGuard → S3 checkpoints
        │                              ├── veridata-recon → S3 proofs
        │                              └── Glue REST → Iceberg commit
        ▼
   committed | verification_failed | rolled_back → retry
```

## Prerequisites

- Terraform >= 1.5
- AWS CLI configured
- Python 3.12 (to build Lambda package)
- **Region:** Lambda Durable Functions may require specific regions (e.g. `us-east-2`). Verify [AWS documentation](https://docs.aws.amazon.com/lambda/latest/dg/durable-functions.html).

## Quick deploy (prod)

### 1. Build Lambda package

**Linux/macOS:**
```bash
chmod +x infrastructure/terraform/scripts/package_lambda.sh
./infrastructure/terraform/scripts/package_lambda.sh
```

**Windows:**
```powershell
.\infrastructure\terraform\scripts\package_lambda.ps1
```

Output: `infrastructure/terraform/build/domain-writer.zip`

### 2. Configure variables

```bash
cd infrastructure/terraform/environments/prod
cp terraform.tfvars.example terraform.tfvars
# Edit bucket names (globally unique) and region
```

### 3. Deploy

```bash
terraform init
terraform plan
terraform apply
```

### 4. Run a backfill via Step Functions

```bash
# Get example payload from outputs
terraform output example_stepfunctions_input

aws stepfunctions start-execution \
  --state-machine-arn "$(terraform output -raw step_functions_arn)" \
  --input "$(terraform output -json example_stepfunctions_input)"
```

### 5. Or invoke Lambda directly (qualified ARN)

```bash
aws lambda invoke \
  --function-name "$(terraform output -raw domain_writer_function_name):live" \
  --payload '{"workload_id":"manual-001","total_records":1000,"domain_id":"orders-domain"}' \
  response.json

cat response.json
```

## Module reference

### `modules/lambda`

- `timeout` — per-invocation container limit (**max 900s / 15 min**, AWS hard cap)
- `durable_config.execution_timeout` — total durable budget (default **5400s / 90 min**)
- `durable_config.retention_period` — durable checkpoint retention days (default 14)
- Publishes `live` alias (**required** for durable invocation)

### `modules/stepfunctions`

State machine routes on handler `outcome`:

| Outcome | Step Functions action |
|---------|----------------------|
| `committed` / `resumed` | Success |
| `rolled_back` | Wait 60s → re-invoke (up to `max_resume_attempts`) |
| `verification_failed` | Fail (inspect VRP proofs in S3) |

Each `lambda:invoke` task uses `TimeoutSeconds` ≈ Lambda timeout + 60s (waits for **one** 15-min segment, not the full 90 minutes). For a 90-minute backfill you need at least `ceil(5400/900) = 6` resume attempts; prod auto-bumps `max_resume_attempts` if set too low.

Customize in `terraform.tfvars`:

```hcl
lambda_timeout_seconds            = 900
durable_execution_timeout_seconds = 5400
lambda_memory_mb                  = 4096
max_resume_attempts               = 10
```

After apply: `terraform output execution_timeouts`

### `modules/storage`

| Bucket | Lifecycle |
|--------|-----------|
| checkpoints | matches `durable_retention_days` (min 7) |
| proofs | 90 days |
| lakehouse | no auto-expire |

## Remote state (recommended)

Uncomment the `backend "s3"` block in `environments/prod/versions.tf`:

```hcl
backend "s3" {
  bucket         = "my-tf-state"
  key            = "serverless-data-mesh/prod/terraform.tfstate"
  region         = "us-east-1"
  dynamodb_table = "terraform-locks"
  encrypt        = true
}
```

## Dev environment

Lighter stack at `environments/dev/` (smaller Lambda memory, fewer resume attempts):

```bash
cd infrastructure/terraform/environments/dev
cp terraform.tfvars.example terraform.tfvars
terraform init && terraform apply
```

## Glue prerequisites (not created by this stack)

This Terraform assumes the Glue database and Iceberg table already exist:

- Database: `raw_orders` (configurable)
- Table: `orders_curated` (configurable)
- Lake Formation grants for the Lambda role (if using LF credential vending)

Create these via your data platform team or extend Terraform with `aws_glue_catalog_database` / table resources.

## IAM policies attached

| Policy | Role |
|--------|------|
| `AWSLambdaBasicExecutionRolePolicy` | Lambda |
| `AWSLambdaBasicDurableExecutionRolePolicy` | Lambda |
| Custom S3 + Glue + Lake Formation | Lambda |
| `states:StartExecution` | EventBridge |
| `lambda:InvokeFunction` | Step Functions |

## Troubleshooting

| Issue | Fix |
|-------|-----|
| `durable_config` unsupported | Upgrade AWS provider to >= 6.25; check region support |
| Invoke fails without alias | Use `:live` qualified ARN |
| Empty zip on first plan | Run `package_lambda.sh` before apply |
| Step Functions resume loop exhausted | Increase Lambda timeout/memory or reduce chunk size |

## Related docs

- [Developer getting started](../../docs/getting-started.md)
- [Deployment guide](../../docs/deployment.md)
- [SAM alternative](../sam/README.md)
