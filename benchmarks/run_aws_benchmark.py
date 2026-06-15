#!/usr/bin/env python3
"""AWS live benchmark: invoke domain writer Lambda when deployed."""

from __future__ import annotations

import json
import os
import subprocess
import sys
import time
from datetime import UTC, datetime
from pathlib import Path


def main() -> int:
    fn = os.environ.get("SDM_BENCHMARK_LAMBDA_ARN")
    if not fn:
        print("SDM_BENCHMARK_LAMBDA_ARN not set — skipping AWS benchmark", file=sys.stderr)
        return 0

    rows = int(os.environ.get("SDM_BENCHMARK_ROWS", "100000"))
    payload = {
        "workload_id": f"bench-{rows}",
        "total_records": rows,
        "domain_id": "benchmark",
        "partition_spec": {"dt": datetime.now(UTC).strftime("%Y-%m-%d")},
    }
    t0 = time.perf_counter()
    proc = subprocess.run(
        [
            "aws",
            "lambda",
            "invoke",
            "--function-name",
            fn,
            "--payload",
            json.dumps(payload),
            "/tmp/sdm-bench-out.json",
        ],
        capture_output=True,
        text=True,
    )
    elapsed = time.perf_counter() - t0
    if proc.returncode != 0:
        print(proc.stderr, file=sys.stderr)
        return proc.returncode

    out = {
        "benchmark_version": "1.1.0",
        "status": "measured_aws",
        "generated_at": datetime.now(UTC).isoformat(),
        "lambda_arn": fn,
        "runs": [
            {
                "workload_id": f"aws-{rows // 1000}k",
                "row_count": rows,
                "wall_seconds": round(elapsed, 3),
                "platform": "lambda",
            }
        ],
    }
    dest = Path("benchmarks/results") / f"{datetime.now(UTC):%Y-%m}-aws-live.json"
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text(json.dumps(out, indent=2), encoding="utf-8")
    print(f"AWS benchmark written: {dest}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
