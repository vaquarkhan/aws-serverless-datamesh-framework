"""Payments domain writer stub for multi-domain atomicity demo."""

from __future__ import annotations

from typing import Any


def run(
    *,
    record_count: int = 500,
    corrupt: bool = False,
    proof_generator: Any = None,
    runtime: Any,
    defer_snapshot: bool = False,
) -> dict[str, Any]:
    return runtime.run_write(
        workload_id="payments-chunk",
        record_count=record_count,
        corrupt_sink=corrupt,
        proof_generator=proof_generator,
        defer_snapshot=defer_snapshot,
    ).to_dict()
