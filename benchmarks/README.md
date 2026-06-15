# Cost comparison benchmark (Lambda vs Glue vs EMR Serverless)

Publish repeatable wall-clock time and **billed USD** for the same Iceberg write workload
at three scale points. One table with real numbers is the strongest enterprise adoption
argument.

## Workloads

| ID | Rows | File | Typical use |
|----|------|------|-------------|
| XS | 100k | `workloads/100k_rows.py` | Canary / nightly small domain |
| S | 1M | `workloads/1m_rows.py` | Standard domain backfill |
| M | 10M | `workloads/10m_rows.py` | Large partition rebuild |

## Run (maintainers)

```bash
# Requires AWS credentials + deployed benchmark stacks
./benchmarks/run_benchmark.sh --profile your-profile --region us-east-2
```

Outputs: `results/YYYY-MM-baseline.json`

## Methodology

1. **Same logical workload**: write N rows to the same Iceberg table schema (id, payload_hash).
2. **Three platforms**:
   - **Lambda + IceGuard + PVDM** (this framework, Step Functions resume if >15 min)
   - **AWS Glue** (Spark ETL job, equivalent DPU sizing)
   - **EMR Serverless** (minimum application capacity)
3. **Metrics captured**:
   - Wall-clock time (cold + warm where applicable)
   - Billed cost from AWS Cost Explorer tags (`BenchmarkRunId`)
   - VRP proof generation overhead (Lambda path only)
4. **Break-even**: row count where Lambda total cost < Glue for intermittent nightly jobs.

## Results (pricing model v0.1.3)

Estimated from AWS public pricing (us-east-2, nightly intermittent backfill). Validate on AWS with `run_benchmark.sh`.

| Workload | Rows | Lambda+PVDM | Glue ETL (2 DPU) | Glue/Lambda ratio | VRP gate |
|----------|------|-------------|------------------|-------------------|----------|
| bench-100k | 100K | **$0.025** | $0.22 | **8.7x** | Yes |
| bench-1m | 1M | **$0.025** | $0.44 | **17.4x** | Yes |
| bench-10m | 10M | **$0.051** | $1.47 | **29.0x** | Yes |

Regenerate: `python benchmarks/run_cost_estimate.py --write`

**Hypothesis validated (estimated):** Lambda wins on intermittent workloads; Glue wins on sustained throughput if amortized.

## Related

- Consumer safety: `eval/validate_then_commit_benchmark.py`
- Local try-before-AWS: `serverless-data-mesh demo`
