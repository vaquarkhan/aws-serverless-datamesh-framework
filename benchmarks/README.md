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

## Results (baseline placeholder)

> Replace with measured `results/2026-06-baseline.json` after first AWS run.

| Workload | Lambda+PVDM | Glue ETL | EMR Serverless | VRP blocked corrupt? |
|----------|-------------|----------|----------------|----------------------|
| 100k | TBD | TBD | TBD | Yes |
| 1M | TBD | TBD | TBD | Yes |
| 10M | TBD | TBD | TBD | Yes |

**Hypothesis:** Lambda wins on **intermittent** workloads (scale to zero between runs);
Glue/EMR win on **sustained** high-throughput if amortized over long runs.

## Related

- Consumer safety: `eval/validate_then_commit_benchmark.py`
- Local try-before-AWS: `serverless-data-mesh demo`
