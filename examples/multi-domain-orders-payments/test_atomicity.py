#!/usr/bin/env python3
"""
Multi-domain atomicity demo: orders PASS + payments FAIL -> no consumer snapshot.
"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))


def evaluate_mesh_transaction(*, payments_corrupt: bool) -> dict:
    from serverless_data_mesh.local.runtime import LocalPVDMRuntime
    from serverless_data_mesh.verification.backend import create_proof_generator

    run_orders, run_payments = _import_handlers()
    runtime = LocalPVDMRuntime()
    gen, _backend = create_proof_generator()

    orders = run_orders(
        record_count=500,
        corrupt=False,
        proof_generator=gen,
        runtime=runtime,
        defer_snapshot=True,
    )
    payments = run_payments(
        record_count=500,
        corrupt=payments_corrupt,
        proof_generator=gen,
        runtime=runtime,
        defer_snapshot=True,
    )

    from serverless_data_mesh.local.runtime import LocalWriteResult

    mesh = runtime.finalize_mesh_transaction(
        [
            LocalWriteResult(**{k: orders[k] for k in LocalWriteResult.__dataclass_fields__}),
            LocalWriteResult(**{k: payments[k] for k in LocalWriteResult.__dataclass_fields__}),
        ]
    )

    return {
        "transaction_id": "mesh-txn-2026-06-14-001",
        "mesh_outcome": mesh["mesh_outcome"],
        "domains": {"orders": orders, "payments": payments},
        "consumer_row_count": mesh["consumer_row_count"],
        "atomicity_preserved": mesh["mesh_outcome"] == "committed"
        or mesh["consumer_row_count"] == 0,
    }


def _import_handlers():
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    from domains.orders.handler import run as run_orders
    from domains.payments.handler import run as run_payments

    return run_orders, run_payments


def main() -> int:
    print("\n=== Multi-domain atomicity: both domains PASS ===")
    ok = evaluate_mesh_transaction(payments_corrupt=False)
    print(f"mesh_outcome={ok['mesh_outcome']}, consumer_rows={ok['consumer_row_count']}")

    print("\n=== Multi-domain atomicity: payments FAIL (corrupt row) ===")
    fail = evaluate_mesh_transaction(payments_corrupt=True)
    print(f"mesh_outcome={fail['mesh_outcome']}")
    print(f"orders={fail['domains']['orders']['outcome']}")
    print(f"payments={fail['domains']['payments']['outcome']}")
    print(f"consumer_rows={fail['consumer_row_count']} (no partial publish)")
    print(f"atomicity_preserved={fail['atomicity_preserved']}\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
