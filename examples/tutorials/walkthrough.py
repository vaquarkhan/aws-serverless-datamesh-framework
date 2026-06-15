#!/usr/bin/env python3
"""
Interactive walkthrough — run each step locally without AWS.

Usage:
    python examples/tutorials/walkthrough.py
    python examples/tutorials/walkthrough.py --step 7
"""

from __future__ import annotations

import argparse
import os
import sys
from typing import Any


def _header(step: int, title: str, what: str, goal: str) -> None:
    bar = "=" * 72
    print(f"\n{bar}")
    print(f"STEP {step}: {title}")
    print(bar)
    print(f"What is this?   {what}")
    print(f"What we achieve: {goal}")
    print("-" * 72)


def step_1_install() -> None:
    _header(
        1,
        "Install the framework",
        "The Python library and its dependencies.",
        "Confirm imports work in your dev environment.",
    )
    import serverless_data_mesh as sdm

    print(f"serverless-data-mesh version: {sdm.__version__}")


def step_2_boundary() -> Any:
    _header(
        2,
        "Declare domain transaction boundary",
        "The contract that scopes your domain's write in the data mesh.",
        "Make ownership, partition scope, and quality policy explicit.",
    )
    from serverless_data_mesh import DomainTransactionBoundary

    boundary = DomainTransactionBoundary(
        domain_id="orders-domain",
        source_namespace="raw_orders",
        target_table="orders_curated",
        partition_spec={"dt": "2026-06-14"},
    )
    print(f"domain_id={boundary.domain_id}, table={boundary.target_table}")
    return boundary


def step_3_workload(boundary: Any) -> Any:
    _header(
        3,
        "Describe the workload",
        "A single backfill/copy job with record count and S3 locations.",
        "Give the orchestrator enough context to shard and tag proofs.",
    )
    from serverless_data_mesh import DataWriteWorkload

    workload = DataWriteWorkload(
        workload_id="tutorial-backfill-001",
        boundary=boundary,
        source_uri="s3://source/orders/",
        target_uri="s3://lakehouse/orders_curated/",
        total_records=10,
        checkpoint_bucket="tutorial-checkpoints",
        proof_bucket="tutorial-proofs",
    )
    print(f"workload_id={workload.workload_id}, records={workload.total_records}")
    return workload


def step_4_source_reader() -> list[dict[str, Any]]:
    _header(
        4,
        "Implement source reader",
        "Returns logical records for VRP fingerprinting.",
        "Enable cryptographic proof that sink matches source.",
    )

    def source_reader(start: int, end: int) -> list[dict[str, Any]]:
        return [{"id": str(i), "payload_hash": f"hash-{i}"} for i in range(start, end)]

    records = source_reader(0, 3)
    print(f"sample records: {records}")
    return records


def step_5_batch_writer() -> list[str]:
    _header(
        5,
        "Implement batch writer",
        "Writes Parquet to S3 and returns URIs (stubbed here).",
        "Decouple physical write mechanics from framework coordination.",
    )

    def batch_writer(start: int, end: int) -> list[str]:
        base = "s3://lakehouse/orders_curated/dt=2026-06-14"
        return [f"{base}/part-{i:08d}.parquet" for i in range(start, end)]

    paths = batch_writer(0, 3)
    print(f"parquet paths: {paths}")
    return paths


def step_6_settings() -> Any:
    _header(
        6,
        "Configure runtime settings",
        "MeshSettings from environment variables.",
        "Keep infrastructure names out of handler code.",
    )
    os.environ.setdefault("ICEGUARD_CHECKPOINT_BUCKET", "tutorial-checkpoints")
    os.environ.setdefault("VRP_PROOF_BUCKET", "tutorial-proofs")
    os.environ.setdefault("ICEBERG_TABLE_BUCKET", "tutorial-lakehouse")

    from serverless_data_mesh import MeshSettings

    settings = MeshSettings.from_environment()
    print(f"checkpoint_interval={settings.checkpoint_interval}")
    print(f"rollback_threshold_ms={settings.rollback_threshold_ms}")
    return settings


def step_7_vrp(workload: Any, records: list[dict[str, Any]]) -> Any:
    _header(
        7,
        "Cryptographic verification (VRP)",
        "veridata-recon fingerprints and reconciles source vs sink.",
        "Block metadata commit unless reconciliation PASSes.",
    )
    try:
        import veridata_recon  # noqa: F401
    except ImportError:
        print("SKIP: veridata-recon not installed (requires Python 3.12+).")
        print("      pip install veridata-recon")
        return None

    from serverless_data_mesh import VRPProofGenerator, validate_then_commit

    proofs = VRPProofGenerator.from_env()
    proof = proofs.build_proof(
        source_records=records,
        sink_records=records,
        workload=workload,
        chunk_start=0,
        chunk_end=len(records),
    )
    result = validate_then_commit(proof)
    print(f"verdict={proof['reconciliation']['verdict']}, validate={result.outcome}")
    print(f"proof_id={proof['proof_id'][:16]}...")
    return proof


def step_8_catalog() -> None:
    _header(
        8,
        "Glue REST catalog adapter",
        "PyIceberg + SigV4 REST for Iceberg metadata commits.",
        "Replace JVM catalog with lightweight HTTPS 2PC.",
    )
    from serverless_data_mesh.catalog.glue_rest import GlueRestCatalogAdapter

    adapter = GlueRestCatalogAdapter(
        catalog_name="glue_rest",
        namespace="raw_orders",
        table_name="orders_curated",
        region="us-east-1",
        warehouse="123456789012:s3tablescatalog/tutorial-lakehouse",
    )
    props = adapter._rest_properties()
    print(f"REST URI: {props['uri']}")
    print(f"SigV4 enabled: {props['rest.sigv4-enabled']}")
    print("(connect() requires live AWS credentials — skipped in tutorial)")


def step_9_coordinator() -> None:
    _header(
        9,
        "Compose the durable coordinator",
        "IceGuardDurableCoordinator chains all four pillars.",
        "One API for physical safety, verification, durability, and metadata.",
    )
    print("Production wiring:")
    print("  coordinator = IceGuardDurableCoordinator(")
    print("      durable_context=context,")
    print("      lambda_context=context,")
    print("      proof_generator=VRPProofGenerator.from_env(),")
    print("      catalog_adapter=GlueRestCatalogAdapter.from_environment(...),")
    print("  )")
    print("  result = coordinator.execute_workload(workload, batch_writer=..., source_reader=...)")


def step_10_handler() -> None:
    _header(
        10,
        "Lambda handler",
        "@durable_execution entry point for domain teams.",
        "Thin handler that delegates to the coordinator.",
    )
    print("See: examples/domain_writer/handler.py")
    print("Handler path for SAM: examples.domain_writer.handler.lambda_handler")


def step_11_deploy() -> None:
    _header(
        11,
        "Deploy to AWS",
        "SAM template packages Lambda Durable Function + IAM.",
        "Production deployment with checkpoint and proof buckets.",
    )
    print("  make sam-build")
    print("  sam deploy --guided --parameter-overrides CheckpointBucketName=...")


def step_12_outcomes() -> None:
    _header(
        12,
        "Interpret outcomes",
        "Handler JSON response describes transaction terminal state.",
        "Clear operator signals: committed, rolled_back, verification_failed.",
    )
    outcomes = {
        "committed": "All chunks verified; Iceberg snapshot published.",
        "resumed": "Continued from durable checkpoint (normal for long jobs).",
        "verification_failed": "VRP blocked commit — fix data drift and re-invoke.",
        "rolled_back": "IceGuard timeout rollback — re-invoke to resume safely.",
    }
    for name, desc in outcomes.items():
        print(f"  {name:22s} → {desc}")


STEPS = {
    1: ("install", step_1_install, []),
    2: ("boundary", step_2_boundary, []),
    3: ("workload", step_3_workload, ["boundary"]),
    4: ("source_reader", step_4_source_reader, []),
    5: ("batch_writer", step_5_batch_writer, []),
    6: ("settings", step_6_settings, []),
    7: ("vrp", step_7_vrp, ["workload", "records"]),
    8: ("catalog", step_8_catalog, []),
    9: ("coordinator", step_9_coordinator, []),
    10: ("handler", step_10_handler, []),
    11: ("deploy", step_11_deploy, []),
    12: ("outcomes", step_12_outcomes, []),
}


def main() -> int:
    parser = argparse.ArgumentParser(description="serverless-data-mesh tutorial walkthrough")
    parser.add_argument("--step", type=int, help="Run a single step (1-12)")
    parser.add_argument("--list", action="store_true", help="List available steps")
    args = parser.parse_args()

    if args.list:
        for num, (name, _, _) in STEPS.items():
            print(f"  {num:2d}. {name}")
        return 0

    # Ensure src is on path when run from repo root
    repo_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
    src = os.path.join(repo_root, "src")
    if src not in sys.path:
        sys.path.insert(0, src)

    ctx: dict[str, Any] = {}

    selected = [args.step] if args.step else range(1, 13)
    for num in selected:
        if num not in STEPS:
            print(f"Unknown step: {num}", file=sys.stderr)
            return 1
        _, fn, deps = STEPS[num]
        fn_args = [ctx[d] for d in deps]
        result = fn(*fn_args)
        if num == 2:
            ctx["boundary"] = result
        elif num == 3:
            ctx["workload"] = result
        elif num == 4:
            ctx["records"] = result

    print("\nDone. Full guide: docs/getting-started.md")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
