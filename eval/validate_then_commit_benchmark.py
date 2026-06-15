#!/usr/bin/env python3
"""
Consumer safety benchmark: quantify validate-then-commit guarantees.

Demonstrates that corrupt data (drops, mutations) never receives a PASS verdict,
so metadata commit would be blocked in production.

Usage:
    python eval/validate_then_commit_benchmark.py
    python eval/validate_then_commit_benchmark.py --json

Requires: Python 3.12+. Uses veridata-recon when available; pure-Python fallback otherwise.
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from dataclasses import asdict, dataclass
from pathlib import Path

# Repo root on path
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

try:
    import veridata_recon as vr  # noqa: F401
except ImportError:
    vr = None

from serverless_data_mesh.types.workload import DataWriteWorkload, DomainTransactionBoundary
from serverless_data_mesh.verification.backend import create_proof_generator
from serverless_data_mesh.verification.vrp import validate_then_commit


@dataclass(frozen=True, slots=True)
class ScenarioResult:
    name: str
    expected: str
    actual: str
    passed: bool
    latency_ms: float


def _workload() -> DataWriteWorkload:
    boundary = DomainTransactionBoundary(
        domain_id="benchmark-domain",
        source_namespace="raw_orders",
        target_table="orders_curated",
        partition_spec={"dt": "2026-06-14"},
    )
    return DataWriteWorkload(
        workload_id="benchmark-001",
        boundary=boundary,
        source_uri="s3://bench/source/",
        target_uri="s3://bench/target/",
        total_records=1000,
        checkpoint_bucket="bench-chk",
        proof_bucket="bench-prf",
    )


def _records(n: int, *, mutate_last: bool = False) -> list[dict[str, str]]:
    rows = [{"id": str(i), "payload_hash": f"h{i}"} for i in range(n)]
    if mutate_last and rows:
        rows[-1] = {"id": rows[-1]["id"], "payload_hash": "CORRUPT"}
    return rows


def run_benchmark() -> list[ScenarioResult]:
    gen, backend = create_proof_generator()
    workload = _workload()
    scenarios: list[tuple[str, list[dict[str, str]], list[dict[str, str]], str]] = [
        ("identical_source_sink", _records(500), _records(500), "PASS"),
        ("record_drop_attack", _records(500), _records(499), "FAIL"),
        ("duplicate_injection", _records(500), _records(500) + [_records(1)[0]], "FAIL"),
        ("mutation_attack", _records(500), _records(500, mutate_last=True), "FAIL"),
        ("empty_sink", _records(100), [], "FAIL"),
    ]
    results: list[ScenarioResult] = []
    for name, source, sink, expected in scenarios:
        t0 = time.perf_counter()
        proof = gen.build_proof(
            source_records=source,
            sink_records=sink,
            workload=workload,
            chunk_start=0,
            chunk_end=len(source),
        )
        outcome = validate_then_commit(proof).outcome
        elapsed_ms = (time.perf_counter() - t0) * 1000
        results.append(
            ScenarioResult(
                name=name,
                expected=expected,
                actual=outcome,
                passed=outcome == expected,
                latency_ms=round(elapsed_ms, 2),
            )
        )
    return results


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--json", action="store_true", help="Emit JSON report")
    args = parser.parse_args()

    results = run_benchmark()
    all_passed = all(r.passed for r in results)
    corrupt_blocked = all(
        r.passed for r in results if r.name != "identical_source_sink"
    )

    if args.json:
        report = {
            "benchmark": "validate_then_commit_consumer_safety",
            "verifier_backend": backend,
            "all_scenarios_passed": all_passed,
            "corrupt_data_never_passes": corrupt_blocked,
            "scenarios": [asdict(r) for r in results],
        }
        print(json.dumps(report, indent=2))
    else:
        print("=" * 72)
        print("Consumer Safety Benchmark: validate-then-commit")
        print("=" * 72)
        print(f"{'Scenario':<28} {'Expected':<8} {'Actual':<8} {'OK':<4} {'ms':>8}")
        print("-" * 72)
        for r in results:
            mark = "yes" if r.passed else "NO"
            print(f"{r.name:<28} {r.expected:<8} {r.actual:<8} {mark:<4} {r.latency_ms:>8.1f}")
        print("-" * 72)
        print(f"All scenarios passed:        {all_passed}")
        print(f"Corrupt data never PASSes:   {corrupt_blocked}")
        print("=" * 72)
        if all_passed:
            print("RESULT: Corrupt data cannot reach consumers (metadata commit blocked).")
        else:
            print("RESULT: FAILED: trust boundary regression detected.")

    return 0 if all_passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
