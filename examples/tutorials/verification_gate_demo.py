#!/usr/bin/env python3
"""
Verification gate demo: show VRP blocking corrupt data before consumers see it.

Usage:
    python examples/tutorials/verification_gate_demo.py
    python examples/tutorials/verification_gate_demo.py --json

No AWS credentials required. Requires Python 3.12+ and veridata-recon.
"""

from __future__ import annotations

import argparse
import json
import os
import sys


def main() -> int:
    parser = argparse.ArgumentParser(description="VRP gate demo: PASS then FAIL")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()

    repo_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
    src = os.path.join(repo_root, "src")
    if src not in sys.path:
        sys.path.insert(0, src)

    try:
        import veridata_recon  # noqa: F401
    except ImportError:
        print("ERROR: pip install veridata-recon (Python 3.12+)", file=sys.stderr)
        return 2

    from serverless_data_mesh.local.runtime import LocalPVDMRuntime

    print("\n" + "=" * 72)
    print("VERIFICATION GATE DEMO")
    print("=" * 72)
    print("Thesis: if VRP FAIL, consumers never see corrupt data.\n")

    runtime = LocalPVDMRuntime()
    result = runtime.run_demo_sequence()

    if args.json:
        print(json.dumps(result, indent=2))
        return 0

    clean = result["phases"]["clean_write"]
    corrupt = result["phases"]["corrupt_write"]

    print("Step 1: Write 1000 rows correctly")
    print(f"         outcome={clean['outcome']}, snapshot={clean['snapshot_id']}")
    print(f"         consumer rows={clean['consumer_row_count']}\n")

    print("Step 2: Inject 1 corrupted row (payload mutation)")
    print(f"         outcome={corrupt['outcome']}, VRP={corrupt['proof_verdict']}")
    print(f"         metadata commit blocked: {corrupt['snapshot_id'] is None}\n")

    print("Step 3: Consumer query")
    print(f"         visible rows={result['consumer']['visible_row_count']}")
    print(f"         corrupt data visible={result['consumer']['corrupt_data_visible']}\n")

    print(result["summary"])
    print(f"\nProof artifacts: {result['root']}")
    print("=" * 72 + "\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
