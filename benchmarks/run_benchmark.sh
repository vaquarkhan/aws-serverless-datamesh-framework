#!/usr/bin/env bash
# Run cost comparison benchmark on AWS (Lambda vs Glue vs EMR Serverless).
set -euo pipefail

PROFILE="${AWS_PROFILE:-}"
REGION="${AWS_REGION:-us-east-2}"
RUN_ID="sdm-bench-$(date +%Y%m%d-%H%M%S)"
OUT="benchmarks/results/$(date +%Y-%m)-baseline.json"

echo "Serverless Data Mesh cost benchmark"
echo "  run_id=$RUN_ID region=$REGION"
echo ""
echo "TODO: deploy benchmark stacks and execute workloads:"
echo "  - benchmarks/workloads/100k_rows.py"
echo "  - benchmarks/workloads/1m_rows.py"
echo "  - benchmarks/workloads/10m_rows.py"
echo ""
echo "Capture: wall_clock_seconds, billed_usd, platform (lambda|glue|emr)"
echo "Write results to: $OUT"
echo ""
echo "See benchmarks/README.md for full methodology."
