#!/usr/bin/env python3
"""Compile all Northstar Retail mesh pipelines from mesh-registry.yaml."""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent


def main() -> int:
    sys.path.insert(0, str(ROOT.parents[1] / "src"))

    from serverless_data_mesh.compile.emit import compile_pipeline
    from serverless_data_mesh.compile.loader import load_contract
    from serverless_data_mesh.compile.validate import validate_contract

    contracts = sorted((ROOT / "contracts").glob("*.mesh.pipeline.yaml"))
    if not contracts:
        print("No contracts found", file=sys.stderr)
        return 1

    out = ROOT / "generated"
    errors = 0
    for path in contracts:
        contract = load_contract(path)
        validation = validate_contract(contract)
        if validation:
            print(f"FAIL {path.name}: {validation}", file=sys.stderr)
            errors += 1
            continue
        result = compile_pipeline(contract, output_dir=out)
        engine = contract.runtime.engine
        mem = contract.runtime.lambda_memory_mb
        print(f"OK   {path.name} -> {result.output_root} [{engine}, {mem}MB]")

    print(f"\nCompiled {len(contracts) - errors}/{len(contracts)} pipelines to {out}/")
    print("Mesh transaction (daily-close): see mesh-transactions/daily-close.yaml")
    return 1 if errors else 0


if __name__ == "__main__":
    raise SystemExit(main())
