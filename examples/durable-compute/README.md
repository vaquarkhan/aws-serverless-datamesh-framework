# Durable compute example — Lambda dual clocks

Configure **Durable Lambda**, Firecracker isolation (AWS-managed), **on-demand** scaling, and **tunable run times** for domain writers.

<p align="center">
  <img src="../../docs/images/durable-lambda-compute-model.png" alt="Durable Lambda compute model" width="920" />
</p>

## What this demonstrates

| Topic | Answer in this framework |
|-------|--------------------------|
| Durable Lambda? | **Yes** — `enable_durable_execution = true` |
| MicroVM? | **Firecracker** under Lambda (AWS-managed) |
| On-demand EC2? | **No** — on-demand **Lambda** only |
| Configurable time? | **Yes** — per-invoke + durable budget |

## Sample `terraform.tfvars`

Copy into `infrastructure/terraform/environments/prod/terraform.tfvars` (or medallion):

```hcl
enable_durable_execution          = true
lambda_timeout_seconds            = 900     # segment clock (max 15 min)
# Workload clock — configurable; examples:
#   3600 = 60 min | 5400 = 90 min | 7200 = 120 min | 10800 = 180 min
durable_execution_timeout_seconds = 10800   # e.g. 180 min total budget
durable_retention_days            = 14
lambda_memory_mb                  = 4096
iceguard_rollback_threshold_ms    = 30000   # rollback 30s before hard timeout
max_resume_attempts               = 14      # auto-bumped if too low for durable÷segment
resume_wait_seconds               = 60
sfn_invoke_timeout_buffer_seconds = 60
```

### Shorter segments (cost / blast-radius tuning)

```hcl
lambda_timeout_seconds            = 300     # 5 min segments
durable_execution_timeout_seconds = 3600    # 60 min total
iceguard_rollback_threshold_ms    = 20000
```

### Other common workload budgets

```hcl
durable_execution_timeout_seconds = 5400    # 90 min
# durable_execution_timeout_seconds = 7200  # 120 min
# durable_execution_timeout_seconds = 10800 # 180 min
```

### Longer durable budget (large backfills)

```hcl
lambda_timeout_seconds            = 900
durable_execution_timeout_seconds = 21600   # 6 hours
max_resume_attempts               = 30
```

## Handler (Durable Execution)

Domain writers use the Durable SDK decorator (see `examples/domain_writer/handler.py`):

```python
from aws_durable_execution_sdk_python import DurableContext, durable_execution

@durable_execution
def handler(event: dict, context: DurableContext) -> dict:
    ...
```

Terraform attaches `durable_config` and the alias `:live` required for durable invokes.

## Local UI review

```bash
# From repo root
serverless-data-mesh apply \
  --contract examples/medallion-e2e/northstar.mesh.yaml \
  --output examples/medallion-e2e/generated

serverless-data-mesh ui \
  --path examples/medallion-e2e/generated \
  --host 127.0.0.1 --port 8765 --open
```

## Related

- [Vaquar Pattern / proprietary PVDM](../../docs/vaquar-pattern.md)
- [Architecture — dual clocks](../../docs/architecture.md#durable-lambda-compute-model)
- [Prod Terraform variables](../../infrastructure/terraform/environments/prod/variables.tf)
