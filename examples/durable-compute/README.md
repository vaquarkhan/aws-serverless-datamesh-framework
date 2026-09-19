# Durable compute example — 15–90 min segments + IceGuard

Configure **Durable Lambda**, Firecracker isolation, **on-demand or Managed Instances**, and a **configurable workload clock**. IceGuard rolls back before hard timeout so incomplete Parquet never becomes a corrupt Iceberg snapshot.

<p align="center">
  <img src="../../docs/images/durable-lambda-compute-model.png" alt="Durable Lambda compute model: Firecracker, dual clocks, configurable durable budget" width="920" />
</p>

## What this demonstrates

| Topic | Answer in this framework |
|-------|--------------------------|
| Durable Lambda? | **Yes** — `enable_durable_execution = true` |
| MicroVM? | **Firecracker** under Lambda (AWS-managed) |
| Segment length? | **15 min** on-demand · **up to 90 min** with LMI (async/ESM) |
| Iceberg corruption? | **Avoided** — IceGuard rollback + VRP before metadata |
| Longer than one segment? | Durable budget + resume — any wall-clock you set |

## Sample `terraform.tfvars` (on-demand, 15 min segments)

```hcl
enable_durable_execution          = true
lambda_timeout_seconds            = 900     # classic on-demand max
durable_execution_timeout_seconds = 10800   # set to your backfill wall-clock
durable_retention_days            = 14
lambda_memory_mb                  = 4096
iceguard_rollback_threshold_ms    = 30000   # rollback before hard timeout
max_resume_attempts               = 14
resume_wait_seconds               = 60
sfn_invoke_timeout_buffer_seconds = 60
```

## Optional: Lambda Managed Instances (up to 90 min async segments)

```hcl
enable_lambda_managed_instances                = true
lambda_managed_instances_capacity_provider_arn = "arn:aws:lambda:us-east-2:123456789012:capacity-provider:sdm-lmi"
lambda_timeout_seconds                         = 5400  # up to 90 min for async/ESM
enable_durable_execution                       = true
durable_execution_timeout_seconds              = 21600 # still set full job budget
iceguard_rollback_threshold_ms                 = 60000
```

Create the capacity provider in your account first, then pass the ARN. See [docs/lambda-managed-instances.md](../../docs/lambda-managed-instances.md).

**Note:** Step Functions `lambda:invoke` is synchronous — AWS still caps sync at 15 minutes. Use LMI 90-minute segments for async durable / ESM paths; IceGuard + durable resume cover the rest.

## Related

- [LMI 15–90 min guide](../../docs/lambda-managed-instances.md)
- [Architecture — dual clocks](../../docs/architecture.md#durable-lambda-compute-model)
- [Terraform guide](../../docs/terraform-guide.md)
- [Vaquar Pattern / proprietary PVDM](../../docs/vaquar-pattern.md)
