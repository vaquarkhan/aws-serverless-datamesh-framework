#!/usr/bin/env python3
"""Multi-domain atomicity demo with deferred mesh leader commit."""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))


def evaluate_mesh_transaction(*, payments_corrupt: bool) -> dict:
    try:
        import veridata_recon as vr
    except ImportError as exc:
        raise SystemExit("veridata-recon required (Python 3.12+)") from exc

    from serverless_data_mesh.local.runtime import LocalPVDMRuntime
    from serverless_data_mesh.verification.vrp import VRPProofGenerator

    runtime = LocalPVDMRuntime()
    keys = vr.generate_keypair()
    gen = VRPProofGenerator(
        private_key_b64=keys["private_key"],
        public_key_b64=keys["public_key"],
        salt_hex=vr.generate_salt(),
    )

    orders = runtime.run_write(
        workload_id="orders-chunk",
        record_count=500,
        corrupt_sink=False,
        proof_generator=gen,
        defer_snapshot=True,
    )
    payments = runtime.run_write(
        workload_id="payments-chunk",
        record_count=500,
        corrupt_sink=payments_corrupt,
        proof_generator=gen,
        defer_snapshot=True,
    )
    mesh = runtime.finalize_mesh_transaction([orders, payments])

    return {
        "transaction_id": "mesh-txn-2026-06-14-001",
        "mesh_outcome": mesh["mesh_outcome"],
        "domains": {
            "orders": orders.to_dict(),
            "payments": payments.to_dict(),
        },
        "consumer_row_count": mesh["consumer_row_count"],
        "atomicity_preserved": mesh["mesh_outcome"] == "committed"
        or mesh["consumer_row_count"] == 0,
    }


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
