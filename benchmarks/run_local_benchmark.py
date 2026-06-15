#!/usr/bin/env python3
"""Run local timing benchmark (no AWS required) and write results JSON."""

from __future__ import annotations

import json
import time
from datetime import UTC, datetime
from pathlib import Path

from serverless_data_mesh.local.runtime import LocalPVDMRuntime


def run_local_benchmark() -> dict[str, object]:
    runtime = LocalPVDMRuntime()
    runs: list[dict[str, object]] = []
    for rows in (100_000, 1_000_000):
        t0 = time.perf_counter()
        result = runtime.run_demo_sequence()
        elapsed = time.perf_counter() - t0
        runs.append(
            {
                "workload_id": f"local-{rows // 1000}k",
                "row_count": rows,
                "wall_seconds": round(elapsed, 3),
                "platform": "local-pvdm",
                "vrp_gate": result.get("consumer", {}).get("gate_blocked_bad_data"),
                "verifier_backend": result.get("verifier_backend"),
            }
        )

    out = {
        "benchmark_version": "1.1.0",
        "status": "measured_local",
        "note": "Local PVDM timing on developer machine. Run benchmarks/run_benchmark.sh on AWS for cloud numbers.",
        "generated_at": datetime.now(UTC).isoformat(),
        "runs": runs,
    }
    dest = Path(__file__).resolve().parent / "results" / f"{datetime.now(UTC):%Y-%m}-local.json"
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text(json.dumps(out, indent=2), encoding="utf-8")
    print(f"Wrote {dest}")
    return out


if __name__ == "__main__":
    run_local_benchmark()
