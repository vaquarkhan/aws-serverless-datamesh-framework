# Lambda Managed Instances (15–90 min segments)

Industry-standard segment clock for domain writers: **15 minutes on classic on-demand Lambda**, or **up to 90 minutes** on [AWS Lambda Managed Instances](https://aws.amazon.com/blogs/compute/announcing-90-minute-function-timeout-on-aws-lambda-managed-instances/) for async / ESM / durable-async invocations.

This framework does **not** replace IceGuard or Durable Execution with a longer timeout. Longer segments reduce resume churn; **IceGuard + VRP + Durable** still prevent corrupt Iceberg publication.

## What changes vs what stays

| Layer | On-demand (default) | Managed Instances (opt-in) |
|-------|---------------------|----------------------------|
| Segment timeout | 1–**900** s (15 min) | 1–**5400** s (90 min) async/ESM |
| Sync invoke (incl. Step Functions `lambda:invoke`) | ≤ 15 min | Still ≤ **15 min** (AWS sync cap) |
| Durable total budget | Configurable (any duration) | Same |
| IceGuard rollback before hard kill | Required | Required |
| VRP before Glue/Iceberg metadata | Required | Required |

Invariant unchanged:

```
commit_metadata ⟹ VRP = PASS
```

## Terraform knobs

```hcl
# Classic on-demand (default)
enable_lambda_managed_instances = false
lambda_timeout_seconds          = 900   # max 15 min

# Optional LMI — longer continuous async segments
enable_lambda_managed_instances                    = true
lambda_managed_instances_capacity_provider_arn     = "arn:aws:lambda:REGION:ACCOUNT:capacity-provider:NAME"
lambda_timeout_seconds                             = 5400  # up to 90 min for async/ESM

# Always: workload clock + IceGuard (any job length)
enable_durable_execution              = true
durable_execution_timeout_seconds     = 10800  # set to your backfill wall-clock
iceguard_rollback_threshold_ms        = 30000  # yield before hard timeout
```

Create the capacity provider in your account (VPC + operator role) via [`aws_lambda_capacity_provider`](https://registry.terraform.io/providers/hashicorp/aws/latest/docs/resources/lambda_capacity_provider), then pass its ARN. This repo attaches it to the domain-writer function; it does not invent a full VPC for you.

## How Iceberg stays uncorrupted

1. **Physical** — IceGuard writes Parquet with checkpoints; near timeout → `rolled_back` (partial files discarded).
2. **Verify** — veridata-recon VRP; FAIL blocks metadata.
3. **Durable** — completed steps replay; no duplicate committed chunks.
4. **Metadata** — Glue/Iceberg snapshot only after VRP PASS.

A 90-minute segment can do more work per invoke, but a mid-segment kill still rolls back — consumers never see a half-written snapshot.

## When to use which path

| Workload | Recommendation |
|----------|----------------|
| Spiky / scale-to-zero domains | On-demand Lambda, 15 min segments + durable resume |
| Steady async backfills that benefit from longer continuous runs | LMI + up to 90 min segments + durable + IceGuard |
| Jobs longer than one segment | Always set `durable_execution_timeout_seconds` to the full wall-clock |

## References

- [AWS Compute Blog — 90-minute timeout on LMI](https://aws.amazon.com/blogs/compute/announcing-90-minute-function-timeout-on-aws-lambda-managed-instances/)
- [Architecture — durable compute](architecture.md#durable-lambda-compute-model)
- [Terraform guide](terraform-guide.md)
- [Durable compute example](../examples/durable-compute/)
