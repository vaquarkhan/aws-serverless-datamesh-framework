#!/usr/bin/env python3
"""CLI entry points for Serverless Data Mesh."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


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
    print(f"\n  Metadata-driven pipeline created: {root}\n")
    print("  Next steps:")
    print(f"    1. Edit {root}/mesh.pipeline.yaml (source of truth)")
    print(f"    2. Implement {root}/readers.py")
    print(f"    3. Deploy {root}/terraform/")
    print(f"    4. Run tests: pytest {root}/tests/\n")
    return 0


def _cmd_compile(args: argparse.Namespace) -> int:
    from serverless_data_mesh.compile.emit import compile_pipeline
    from serverless_data_mesh.compile.loader import load_contract_document
    from serverless_data_mesh.compile.medallion import MedallionMeshContract
    from serverless_data_mesh.compile.medallion_emit import compile_medallion_mesh
    from serverless_data_mesh.compile.medallion_validate import validate_medallion_contract
    from serverless_data_mesh.compile.validate import validate_contract

    doc = load_contract_document(args.contract)

    if isinstance(doc, MedallionMeshContract):
        errors = validate_medallion_contract(doc)
        if errors:
            print("Medallion mesh validation failed:", file=sys.stderr)
            for err in errors:
                print(f"  - {err}", file=sys.stderr)
            return 1
        result = compile_medallion_mesh(
            doc,
            output_dir=args.output,
            source_contract_path=Path(args.contract),
        )
        if args.json:
            print(
                json.dumps(
                    {
                        "mesh_root": str(result.mesh_root),
                        "pipeline_count": result.pipeline_count,
                        "domains": list(result.domain_paths.keys()),
                        "layer_paths": {k: str(v) for k, v in result.layer_paths.items()},
                        "files_written": list(result.files_written),
                    },
                    indent=2,
                )
            )
        else:
            print(f"\n  Medallion mesh compiled: {result.mesh_root}\n")
            print(f"  Pipelines generated: {result.pipeline_count}")
            print(f"  Domains: {', '.join(result.domain_paths.keys())}")
            for key, path in sorted(result.layer_paths.items()):
                print(f"    {key} -> {path}")
            print("\n  Edit only your YAML metadata; implement readers.py per layer.")
            print("  Deploy mesh.orchestrator.asl.json + per-domain orchestrators.\n")
        return 0

    errors = validate_contract(doc)
    if errors:
        print("Contract validation failed:", file=sys.stderr)
        for err in errors:
            print(f"  - {err}", file=sys.stderr)
        return 1

    result = compile_pipeline(
        doc,
        output_dir=args.output,
        write_canonical_contract=not args.no_write_contract,
    )

    if args.json:
        print(
            json.dumps(
                {
                    "output_root": str(result.output_root),
                    "contract_path": str(result.contract_path),
                    "files_written": list(result.files_written),
                },
                indent=2,
            )
        )
    else:
        print(f"\n  Pipeline compiled: {result.output_root}\n")
        print(f"  Contract: {result.contract_path}")
        print(f"  Files ({len(result.files_written)}):")
        for name in result.files_written:
            print(f"    - {name}")
        print("\n  Next: implement readers.py, deploy terraform/, pytest tests/\n")
    return 0


def _cmd_dashboard(args: argparse.Namespace) -> int:
    from serverless_data_mesh.dashboard.trust import render_trust_dashboard

    path = render_trust_dashboard(
        proofs_dir=args.proofs_dir,
        output=args.output,
        demo=not args.proofs_dir and not args.cloudwatch,
        cloudwatch=args.cloudwatch,
        cloudwatch_region=args.region,
    )
    print(f"Trust dashboard written: {path}")
    if args.open_browser:
        import webbrowser

        webbrowser.open(f"file://{path}")
    return 0


def _cmd_canary(args: argparse.Namespace) -> int:
    from serverless_data_mesh.orchestration.canary import run_canary

    result = run_canary(
        record_count=args.records,
        inject_canary_drift=args.drift,
        max_divergence_pct=args.max_divergence,
    )
    if args.json:
        print(json.dumps(result, indent=2))
    else:
        print(f"\n  Canary outcome: {result['outcome']}")
        print(f"  Production VRP: {result['production_verdict']}")
        print(f"  Canary VRP:     {result['canary_verdict']}")
        print(f"  Divergence:     {result['divergence_pct']}%")
        print(f"  Promote:        {result['promote']}\n")
        print(f"  {result['message']}\n")
    return 0 if result["promote"] else 1


def _cmd_reprocess_demo(args: argparse.Namespace) -> int:
    from serverless_data_mesh.local.runtime import LocalPVDMRuntime

    runtime = LocalPVDMRuntime()
    result = runtime.run_write_with_auto_repair(
        record_count=args.records,
        drop_count=args.drop,
    )
    if args.json:
        print(json.dumps(result, indent=2, default=str))
    else:
        print("\n  Auto VRP reprocessing demo\n")
        print(f"  Outcome:          {result['outcome']}")
        repair = result.get("repair", {})
        print(f"  Missing before:   {repair.get('missing_before', '?')}")
        print(f"  Repair attempts:  {repair.get('attempts', '?')}")
        print(f"  Consumer rows:    {result.get('consumer_row_count', 0)}\n")
    return 0 if result.get("outcome") == "repaired_and_committed" else 1


def _cmd_new(args: argparse.Namespace) -> int:
    from serverless_data_mesh.compile.wizard import list_templates, scaffold_new

    if args.list_templates:
        print("\n  Available templates:\n")
        for name, desc in list_templates().items():
            print(f"    {name:12} {desc}")
        print()
        return 0

    result = scaffold_new(
        args.template,
        output_dir=args.output,
        producer_account=args.producer,
        steward_account=args.steward,
        publisher_account=args.publisher,
        domain=args.domain,
        table=args.table,
        contract_name=args.contract_name,
    )
    print(f"\n  Starter mesh created: {result.contract_path}\n")
    print("  One command to generate all pipelines:")
    print(f"    serverless-data-mesh apply --contract {result.contract_path}\n")
    return 0


def _cmd_validate(args: argparse.Namespace) -> int:
    from serverless_data_mesh.compile.wizard import validate_contract_file

    errors = validate_contract_file(args.contract)
    if args.json:
        print(json.dumps({"valid": not errors, "errors": errors}, indent=2))
    elif errors:
        print("Invalid contract:", file=sys.stderr)
        for err in errors:
            print(f"  - {err}", file=sys.stderr)
        return 1
    print(f"Valid: {args.contract}")
    return 0


def _cmd_doctor(args: argparse.Namespace) -> int:
    from serverless_data_mesh.compile.wizard import doctor_generated

    report = doctor_generated(args.path)
    if args.json:
        print(
            json.dumps(
                {
                    "root": str(report.root),
                    "pipeline_count": report.pipeline_count,
                    "readers_total": report.readers_total,
                    "readers_done": report.readers_done,
                    "readers_pending": report.readers_pending,
                    "ready_to_deploy": report.ready_to_deploy,
                },
                indent=2,
            )
        )
    else:
        print(f"\n  Mesh doctor: {report.root}\n")
        print(f"  Pipelines:     {report.pipeline_count}")
        print(f"  Readers done:  {report.readers_done}/{report.readers_total}")
        if report.readers_pending:
            print("  Pending readers.py:")
            for p in report.readers_pending:
                print(f"    - {p}")
        print(f"  Orchestrator:  {report.has_orchestrator}")
        print(f"  Deploy ready:  {report.ready_to_deploy}\n")
    return 0 if report.ready_to_deploy or not report.readers_pending else 1


def _cmd_apply(args: argparse.Namespace) -> int:
    from serverless_data_mesh.compile.wizard import apply_mesh

    try:
        result = apply_mesh(args.contract, output_dir=args.output)
    except ValueError as exc:
        print(str(exc), file=sys.stderr)
        return 1

    if args.json:
        print(
            json.dumps(
                {
                    "contract": str(result.contract_path),
                    "output_root": str(result.output_root),
                    "pipeline_count": result.pipeline_count,
                    "getting_started": str(result.getting_started_path),
                    "readers_pending": result.doctor.readers_pending,
                    "ready_to_deploy": result.doctor.ready_to_deploy,
                },
                indent=2,
            )
        )
    else:
        print("\n  Mesh apply complete\n")
        print(f"  Contract:   {result.contract_path}")
        print(f"  Generated:  {result.output_root}")
        print(f"  Pipelines:  {result.pipeline_count}")
        print(f"  Guide:      {result.getting_started_path}")
        print(f"  Readers:    {result.doctor.readers_done}/{result.doctor.readers_total} done")
        if result.doctor.readers_pending:
            print("\n  Implement these readers.py files, then run doctor again:")
            for p in result.doctor.readers_pending:
                print(f"    {result.output_root / p}")
        else:
            print("\n  All readers implemented — ready for terraform + Step Functions deploy.")
        print()
    return 0


def _cmd_deploy(args: argparse.Namespace) -> int:
    from serverless_data_mesh.deploy.runner import deploy_mesh, result_to_dict

    try:
        result = deploy_mesh(
            contract=args.contract,
            output=args.output,
            terraform_dir=args.terraform_dir,
            partition_dt=args.partition_dt,
            skip_apply=args.skip_apply,
            skip_terraform=args.skip_terraform,
            terraform_auto_approve=args.auto_approve,
            start_execution=args.start_execution,
            dry_run=args.dry_run,
        )
    except (FileNotFoundError, RuntimeError) as exc:
        print(str(exc), file=sys.stderr)
        return 1

    if args.json:
        print(json.dumps(result_to_dict(result), indent=2))
    else:
        print("\n  Deploy complete\n")
        print(f"  Contract:   {result.contract_path}")
        print(f"  Generated:  {result.generated_path}")
        print(f"  Terraform:  {result.terraform_dir}")
        print(f"  TF applied: {result.terraform_applied}")
        if result.mesh_execution_arn:
            print(f"  SFN started: {result.mesh_execution_arn}")
        print()
    return 0


def _cmd_catalog(args: argparse.Namespace) -> int:
    from serverless_data_mesh.catalog_export.backstage import export_backstage_catalog

    paths = export_backstage_catalog(args.contract, output_dir=args.output)
    if args.json:
        print(json.dumps({"entities": [str(p) for p in paths]}, indent=2))
    else:
        print(f"\n  Backstage entities ({len(paths)}):\n")
        for p in paths:
            print(f"    {p}")
        print()
    return 0


def _cmd_ui(args: argparse.Namespace) -> int:
    from serverless_data_mesh.ui.server import serve_ui

    serve_ui(
        generated_path=args.path,
        host=args.host,
        port=args.port,
        open_browser=args.open_browser,
    )
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

    init_p = sub.add_parser("init", help="Scaffold a metadata-driven PVDM pipeline")
    init_p.add_argument("--domain", required=True, help="Domain id (e.g. payments)")
    init_p.add_argument("--table", required=True, help="Target Iceberg table")
    init_p.add_argument("--account", required=True, help="Producer AWS account ID")
    init_p.add_argument("--output", default="domains", help="Output parent directory")
    init_p.set_defaults(func=_cmd_init)

    compile_p = sub.add_parser(
        "compile",
        help="Generate pipeline(s) from YAML (DataProductPipeline or MedallionMesh)",
    )
    compile_p.add_argument(
        "--contract",
        required=True,
        help="Path to mesh.pipeline.yaml or MedallionMesh YAML (bronze/silver/gold)",
    )
    compile_p.add_argument("--output", default="domains", help="Output parent directory")
    compile_p.add_argument(
        "--no-write-contract",
        action="store_true",
        help="Do not copy contract YAML into output (already present)",
    )
    compile_p.add_argument("--json", action="store_true")
    compile_p.set_defaults(func=_cmd_compile)

    dash = sub.add_parser("dashboard", help="Generate mesh trust dashboard HTML")
    dash.add_argument("--proofs-dir", help="Steward proofs directory (local or mounted S3)")
    dash.add_argument("--cloudwatch", action="store_true", help="Pull live metrics from CloudWatch")
    dash.add_argument("--region", help="AWS region for CloudWatch")
    dash.add_argument("--output", default="mesh-trust-dashboard.html")
    dash.add_argument("--open", dest="open_browser", action="store_true")
    dash.set_defaults(func=_cmd_dashboard)

    canary = sub.add_parser("canary", help="Run VRP canary comparison before promotion")
    canary.add_argument("--records", type=int, default=1000)
    canary.add_argument("--drift", action="store_true", help="Inject canary row-count drift")
    canary.add_argument("--max-divergence", type=float, default=1.0)
    canary.add_argument("--json", action="store_true")
    canary.set_defaults(func=_cmd_canary)

    repro = sub.add_parser("reprocess-demo", help="Demo auto VRP repair after dropped records")
    repro.add_argument("--records", type=int, default=100)
    repro.add_argument("--drop", type=int, default=5)
    repro.add_argument("--json", action="store_true")
    repro.set_defaults(func=_cmd_reprocess_demo)

    new_p = sub.add_parser("new", help="Create starter mesh YAML from template")
    new_p.add_argument(
        "--template",
        default="medallion",
        choices=["medallion", "single", "northstar", "starter", "pipeline"],
        help="Template: medallion (default), single, or northstar retail",
    )
    new_p.add_argument("--output", default="my-mesh", help="Directory for mesh.yaml")
    new_p.add_argument("--producer", default="123456789012")
    new_p.add_argument("--steward", default="234567890123")
    new_p.add_argument("--publisher", default="345678901234")
    new_p.add_argument("--domain", default="orders")
    new_p.add_argument("--table", default="curated_table")
    new_p.add_argument("--contract-name", default="mesh.yaml")
    new_p.add_argument("--list-templates", action="store_true")
    new_p.set_defaults(func=_cmd_new)

    val_p = sub.add_parser("validate", help="Validate mesh YAML without compiling")
    val_p.add_argument("--contract", required=True)
    val_p.add_argument("--json", action="store_true")
    val_p.set_defaults(func=_cmd_validate)

    doc_p = sub.add_parser("doctor", help="Check generated mesh readiness")
    doc_p.add_argument("--path", required=True, help="Generated mesh directory")
    doc_p.add_argument("--json", action="store_true")
    doc_p.set_defaults(func=_cmd_doctor)

    apply_p = sub.add_parser(
        "apply",
        help="Validate + compile + doctor + GETTING_STARTED (one-shot)",
    )
    apply_p.add_argument("--contract", required=True, help="mesh.yaml or northstar.mesh.yaml")
    apply_p.add_argument("--output", default="generated", help="Output directory")
    apply_p.add_argument("--json", action="store_true")
    apply_p.set_defaults(func=_cmd_apply)

    dep_p = sub.add_parser("deploy", help="Apply + Terraform + optional Step Functions start")
    dep_p.add_argument("--contract", required=True)
    dep_p.add_argument("--output", default="generated")
    dep_p.add_argument(
        "--terraform-dir",
        help="Terraform env dir (default: infrastructure/terraform/environments/medallion)",
    )
    dep_p.add_argument("--partition-dt", default="2026-06-14")
    dep_p.add_argument("--skip-apply", action="store_true")
    dep_p.add_argument("--skip-terraform", action="store_true")
    dep_p.add_argument("--auto-approve", action="store_true", help="terraform apply -auto-approve")
    dep_p.add_argument("--start-execution", action="store_true", help="Start mesh SFN after apply")
    dep_p.add_argument("--dry-run", action="store_true")
    dep_p.add_argument("--json", action="store_true")
    dep_p.set_defaults(func=_cmd_deploy)

    cat_p = sub.add_parser("catalog", help="Export Backstage catalog-info.yaml entities")
    cat_sub = cat_p.add_subparsers(dest="catalog_cmd", required=True)
    cat_exp = cat_sub.add_parser("export", help="Generate catalog entities from mesh YAML")
    cat_exp.add_argument("--contract", required=True)
    cat_exp.add_argument("--output", default="integrations/backstage/entities")
    cat_exp.add_argument("--json", action="store_true")
    cat_exp.set_defaults(func=_cmd_catalog)

    ui_p = sub.add_parser("ui", help="Mesh control panel (local HTTP UI)")
    ui_p.add_argument("--path", default="generated", help="Generated mesh directory")
    ui_p.add_argument("--host", default="127.0.0.1")
    ui_p.add_argument("--port", type=int, default=8765)
    ui_p.add_argument("--open", dest="open_browser", action="store_true")
    ui_p.set_defaults(func=_cmd_ui)

    args = parser.parse_args(argv)
    return int(args.func(args))


if __name__ == "__main__":
    raise SystemExit(main())
