"""Aggregate mesh UI dashboard data from generated output + local demos."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from serverless_data_mesh.pvdm_copyright import ATTRIBUTION, NOTICE_SHORT


def _read_json(path: Path) -> dict[str, Any] | list[Any] | None:
    if not path.is_file():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return None


def _pipeline_rows(generated: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for domain_dir in sorted(p for p in generated.iterdir() if p.is_dir()):
        for layer_dir in sorted(p for p in domain_dir.iterdir() if p.is_dir()):
            readers = layer_dir / "readers.py"
            handler = layer_dir / "handler.py"
            readers_ok = readers.is_file() and "NotImplementedError" not in readers.read_text(
                encoding="utf-8", errors="ignore"
            )
            # Prefer contract yaml as text sniff
            engine = "—"
            product = layer_dir.name
            yaml_path = layer_dir / "mesh.pipeline.yaml"
            if yaml_path.is_file():
                text = yaml_path.read_text(encoding="utf-8", errors="ignore")
                for line in text.splitlines():
                    if line.strip().startswith("engine:"):
                        engine = line.split(":", 1)[1].strip()
                    if line.strip().startswith("product_id:"):
                        product = line.split(":", 1)[1].strip()
            rows.append(
                {
                    "domain": domain_dir.name,
                    "layer": layer_dir.name,
                    "product_id": product,
                    "engine": engine,
                    "has_handler": handler.is_file(),
                    "readers_ready": readers_ok,
                    "path": str(layer_dir.relative_to(generated)).replace("\\", "/"),
                }
            )
    return rows


def _trust_from_proofs(search_roots: list[Path]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for root in search_roots:
        if not root.exists():
            continue
        for proof_file in sorted(root.rglob("*.vrp.json")):
            data = _read_json(proof_file)
            if not isinstance(data, dict):
                continue
            recon = data.get("reconciliation", {})
            verdict = recon.get("verdict", "UNKNOWN")
            parts = proof_file.parts
            domain = parts[-3] if len(parts) >= 3 else "unknown"
            rows.append(
                {
                    "domain": domain,
                    "status": verdict,
                    "rows": recon.get("sink_count", recon.get("source_count", "?")),
                    "proof_id": (data.get("proof_id") or "")[:16],
                    "created_at": data.get("created_at", ""),
                    "path": str(proof_file),
                }
            )
    return rows


def _attestations(search_roots: list[Path]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for root in search_roots:
        if not root.exists():
            continue
        for path in sorted(root.rglob("*.pvdma.json")):
            data = _read_json(path)
            if not isinstance(data, dict):
                continue
            rows.append(
                {
                    "attestation_id": data.get("attestation_id"),
                    "decision": data.get("decision"),
                    "vrp_verdict": data.get("vrp_verdict"),
                    "domain_id": data.get("domain_id"),
                    "agent_id": data.get("agent_id"),
                    "path": str(path),
                }
            )
    return rows


def build_dashboard(generated_path: Path) -> dict[str, Any]:
    """Full payload for the mesh control UI."""
    from serverless_data_mesh.compile.wizard import doctor_generated

    root = generated_path.resolve()
    doctor = doctor_generated(root)
    manifest = _read_json(root / "mesh.manifest.json") or {}
    layer_manifest = _read_json(root / "layer_lambda.manifest.json") or {}
    pipelines = _pipeline_rows(root)

    proof_roots = [
        root / "proofs",
        Path.home() / ".sdm" / "proofs",
    ]
    # Also scan temp demo roots listed in a marker if present
    marker = root / ".ui-demo-root"
    if marker.is_file():
        proof_roots.insert(0, Path(marker.read_text(encoding="utf-8").strip()))

    trust = _trust_from_proofs(proof_roots)
    attests = _attestations(proof_roots)

    pass_n = sum(1 for r in trust if r.get("status") == "PASS")
    fail_n = sum(1 for r in trust if r.get("status") == "FAIL")

    # Demo trust rows if no proofs yet
    trust_mode = "live-proofs" if trust else "demo"
    if not trust:
        trust = [
            {
                "domain": "orders",
                "status": "PASS",
                "rows": 5200,
                "proof_id": "demo",
                "created_at": "",
                "path": "",
            },
            {
                "domain": "payments",
                "status": "PASS",
                "rows": 1100,
                "proof_id": "demo",
                "created_at": "",
                "path": "",
            },
            {
                "domain": "inventory",
                "status": "FAIL",
                "rows": 0,
                "proof_id": "demo",
                "created_at": "",
                "path": "",
                "detail": "3 drops (demo)",
            },
        ]
        pass_n, fail_n = 2, 1

    layers = layer_manifest.get("layers") if isinstance(layer_manifest, dict) else None
    if not isinstance(layers, list):
        layers = []

    return {
        "generated_at": datetime.now(UTC).isoformat(),
        "root": str(root),
        "organization": manifest.get("organization") if isinstance(manifest, dict) else None,
        "domains": manifest.get("domains", []) if isinstance(manifest, dict) else [],
        "doctor": {
            "pipeline_count": doctor.pipeline_count,
            "readers_done": doctor.readers_done,
            "readers_total": doctor.readers_total,
            "readers_pending": doctor.readers_pending,
            "ready_to_deploy": doctor.ready_to_deploy,
            "has_orchestrator": doctor.has_orchestrator,
        },
        "kpis": {
            "pipelines": doctor.pipeline_count,
            "domains": len(manifest.get("domains", []) if isinstance(manifest, dict) else []),
            "readers_pct": (
                round(100 * doctor.readers_done / doctor.readers_total)
                if doctor.readers_total
                else 0
            ),
            "trust_pass": pass_n,
            "trust_fail": fail_n,
            "attestations": len(attests),
            "deploy_ready": doctor.ready_to_deploy,
        },
        "pipelines": pipelines,
        "layer_lambdas": layers,
        "trust": {"mode": trust_mode, "rows": trust},
        "attestations": attests[:50],
        "pvdm": {
            "phases": [
                {
                    "id": "P",
                    "name": "Physical",
                    "status": "ready",
                    "detail": "IceGuard SafeWriter + checkpoints",
                },
                {
                    "id": "V",
                    "name": "Verify",
                    "status": "ready",
                    "detail": "VRP validate_then_commit",
                },
                {
                    "id": "D",
                    "name": "Durable",
                    "status": "ready",
                    "detail": "Durable Lambda + SFN resume",
                },
                {
                    "id": "M",
                    "name": "Metadata",
                    "status": "ready",
                    "detail": "Proof-gated Iceberg commit",
                },
            ],
            "invariant": "commit_metadata ⟹ VRP = PASS",
            "method": ATTRIBUTION,
            "copyright": NOTICE_SHORT,
        },
        "durable": {
            "lambda_timeout_seconds": 900,
            "durable_execution_timeout_seconds": 5400,
            "microvm": "Firecracker (AWS-managed)",
            "compute": "On-demand Lambda (scale to zero)",
            "enable_durable_execution": True,
        },
        "tutorial": _tutorial_steps(),
    }


def _tutorial_steps() -> list[dict[str, str]]:
    return [
        {
            "id": "1",
            "title": "Install & prove the gate",
            "command": "pip install serverless-data-mesh && serverless-data-mesh demo",
            "image": "/tutorial/step-01-install-demo.png",
            "gif": "/tutorial/step-01-install-demo.gif",
            "do": "Install the package, then run the local demo once.",
            "benefit": "Clean commit + corrupt blocked in <60s — no AWS. Proves the VRP gate.",
            "blurb": "Fastest way to feel the Vaquar Pattern (PVDM) invariant.",
        },
        {
            "id": "2",
            "title": "Create mesh YAML",
            "command": "serverless-data-mesh new --template medallion --output my-mesh",
            "image": "/tutorial/step-02-new-mesh.png",
            "gif": "/tutorial/step-02-new-mesh.gif",
            "do": "Scaffold a medallion starter contract.",
            "benefit": "Domain-owned YAML instead of a central Glue ticket.",
            "blurb": "Metadata-first mesh blueprint.",
        },
        {
            "id": "3",
            "title": "Apply (compile)",
            "command": (
                "serverless-data-mesh apply --contract my-mesh/mesh.yaml --output my-mesh/generated"
            ),
            "image": "/tutorial/step-03-apply.png",
            "gif": "/tutorial/step-03-apply.gif",
            "do": "Generate handlers, Step Functions, VRP config, manifests.",
            "benefit": "One YAML → bronze/silver/gold proof-gated pipelines.",
            "blurb": "Compiler does the busywork.",
        },
        {
            "id": "4",
            "title": "Start control UI",
            "command": "serverless-data-mesh ui --path my-mesh/generated --open",
            "image": "/tutorial/step-04-ui.png",
            "gif": "/tutorial/step-04-ui.gif",
            "do": "Open http://127.0.0.1:8765/ (or /walkthrough for video-style demo).",
            "benefit": "KPIs, trust, PVDM, durable clocks before you spend AWS $.",
            "blurb": "Human review surface for the mesh.",
        },
        {
            "id": "5",
            "title": "Deploy Durable Lambda",
            "command": "package_lambda.sh && terraform apply  # dual clocks in tfvars",
            "image": "/tutorial/step-05-deploy.png",
            "gif": "/tutorial/step-05-deploy.gif",
            "do": "Package zip + terraform apply with lambda_timeout + durable budget.",
            "benefit": "Firecracker on-demand Lambda; 90+ min backfills; no idle clusters.",
            "blurb": "Production compute without EMR sprawl.",
        },
        {
            "id": "6",
            "title": "Observe & attest",
            "command": "serverless-data-mesh attest demo --json",
            "image": "/tutorial/step-06-observe.png",
            "gif": "/tutorial/step-06-observe.gif",
            "do": "Emit PVDM-A attestations; check trust dashboard / CloudWatch.",
            "benefit": "Auditable proofs; consumers only see VRP PASS snapshots.",
            "blurb": "From green logs to cryptographic evidence.",
        },
    ]


def run_local_demo(generated: Path) -> dict[str, Any]:
    """Execute LocalPVDMRuntime demo and record proof root for the UI."""
    from serverless_data_mesh.local.runtime import LocalPVDMRuntime

    runtime = LocalPVDMRuntime()
    result = runtime.run_demo_sequence()
    marker = generated / ".ui-demo-root"
    marker.write_text(str(runtime.root), encoding="utf-8")
    return {
        "ok": True,
        "root": str(runtime.root),
        "summary": result.get("summary"),
        "consumer": result.get("consumer"),
        "phases": result.get("phases"),
        "elapsed_ms": result.get("elapsed_ms"),
    }
