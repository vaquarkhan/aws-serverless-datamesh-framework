#!/usr/bin/env python3
"""CLI entry points for Serverless Data Mesh."""

from __future__ import annotations

import argparse
import json
import sys


def _cmd_demo(args: argparse.Namespace) -> int:
    from serverless_data_mesh.local.runtime import LocalPVDMRuntime
    from serverless_data_mesh.verification.backend import veridata_available

    runtime = LocalPVDMRuntime()
    result = runtime.run_demo_sequence()

    if args.json:
        print(json.dumps(result, indent=2))
    else:
        backend = result.get("verifier_backend", "unknown")
        fallback_note = ""
        if backend == "pure-python-fallback":
            fallback_note = "  (pure-Python verifier - no Rust wheel needed)\n"
        print("\n  Serverless Data Mesh - local PVDM demo (no AWS)\n")
        print(f"  Verifier:  {backend}{fallback_note}")
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
        print("  Vaquar Pattern (PVDM): Physical -> Verify -> Durable -> Metadata")
        if not veridata_available():
            print("  Tip: pip install veridata-recon on Linux for cryptographic VRP proofs.")
        print("  Docs: docs/vaquar-pattern.md\n")

    return 0 if result["consumer"]["gate_blocked_bad_data"] else 1


def _cmd_init(args: argparse.Namespace) -> int:
    from serverless_data_mesh.scaffold.init_domain import scaffold_domain

    root = scaffold_domain(
        domain=args.domain,
        table=args.table,
        account_id=args.account,
        output_dir=args.output,
    )
    print(f"\n  Domain scaffold created: {root}\n")
    print("  Next steps:")
    print(f"    1. Edit {root}/handler.py")
    print(f"    2. Review {root}/contract.yaml")
    print(f"    3. Deploy {root}/terraform/ (copy tfvars.example -> tfvars)")
    print(f"    4. Run tests: pytest {root}/tests/\n")
    return 0


def _cmd_dashboard(args: argparse.Namespace) -> int:
    from serverless_data_mesh.dashboard.trust import render_trust_dashboard

    path = render_trust_dashboard(
        proofs_dir=args.proofs_dir,
        output=args.output,
        demo=not args.proofs_dir,
    )
    print(f"Trust dashboard written: {path}")
    if args.open_browser:
        import webbrowser

        webbrowser.open(f"file://{path}")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="serverless-data-mesh",
        description="Serverless Data Mesh - federated lakehouse writes on AWS Lambda",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    demo = sub.add_parser("demo", help="Run local PVDM demo in <60s without AWS")
    demo.add_argument("--json", action="store_true", help="Emit machine-readable JSON")
    demo.set_defaults(func=_cmd_demo)

    init_p = sub.add_parser("init", help="Scaffold a new proof-gated domain writer")
    init_p.add_argument("--domain", required=True, help="Domain id (e.g. payments)")
    init_p.add_argument("--table", required=True, help="Target Iceberg table")
    init_p.add_argument("--account", required=True, help="Producer AWS account ID")
    init_p.add_argument("--output", default="domains", help="Output parent directory")
    init_p.set_defaults(func=_cmd_init)

    dash = sub.add_parser("dashboard", help="Generate mesh trust dashboard HTML")
    dash.add_argument("--proofs-dir", help="Steward proofs directory (local or mounted S3)")
    dash.add_argument("--output", default="mesh-trust-dashboard.html")
    dash.add_argument("--open", dest="open_browser", action="store_true")
    dash.set_defaults(func=_cmd_dashboard)

    args = parser.parse_args(argv)
    return int(args.func(args))


if __name__ == "__main__":
    raise SystemExit(main())
