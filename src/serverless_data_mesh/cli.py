#!/usr/bin/env python3
"""CLI entry points for Serverless Data Mesh."""

from __future__ import annotations

import argparse
import json
import sys


def _cmd_demo(args: argparse.Namespace) -> int:
    try:
        import veridata_recon  # noqa: F401
    except ImportError:
        print(
            "ERROR: veridata-recon required for local demo.\n"
            "       pip install serverless-data-mesh  # includes veridata-recon\n"
            "       Requires Python 3.12+",
            file=sys.stderr,
        )
        return 2

    from serverless_data_mesh.local.runtime import LocalPVDMRuntime

    runtime = LocalPVDMRuntime()
    result = runtime.run_demo_sequence()

    if args.json:
        print(json.dumps(result, indent=2))
    else:
        print("\n  Serverless Data Mesh - local PVDM demo (no AWS)\n")
        print(f"  Workspace: {result['root']}")
        print(f"  Elapsed:   {result['elapsed_ms']} ms\n")
        clean = result["phases"]["clean_write"]
        corrupt = result["phases"]["corrupt_write"]
        consumer = result["consumer"]
        print(f"  Phase 1 - clean write:    {clean['outcome']} ({clean['records_written']} rows)")
        print(f"  Phase 2 - corrupt write:  {corrupt['outcome']} (VRP {corrupt['proof_verdict']})")
        print(f"  Consumer visible rows:      {consumer['visible_row_count']}")
        print(f"  Gate blocked bad data:      {consumer['gate_blocked_bad_data']}\n")
        print(f"  {result['summary']}\n")
        print("  Vaquar Pattern (PVDM): Physical → Verify → Durable → Metadata")
        print("  Docs: docs/vaquar-pattern.md\n")

    return 0 if result["consumer"]["gate_blocked_bad_data"] else 1


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="serverless-data-mesh",
        description="Serverless Data Mesh - federated lakehouse writes on AWS Lambda",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    demo = sub.add_parser(
        "demo",
        help="Run local PVDM demo in <60s without AWS credentials",
    )
    demo.add_argument("--json", action="store_true", help="Emit machine-readable JSON")
    demo.set_defaults(func=_cmd_demo)

    args = parser.parse_args(argv)
    return int(args.func(args))


if __name__ == "__main__":
    raise SystemExit(main())
