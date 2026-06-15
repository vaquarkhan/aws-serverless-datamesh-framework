"""Zero-friction mesh wizard: templates, validate, doctor, apply."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from importlib import resources
from pathlib import Path
from typing import Any

from serverless_data_mesh.compile.emit import compile_pipeline
from serverless_data_mesh.compile.loader import load_contract_document
from serverless_data_mesh.compile.medallion import MedallionMeshContract
from serverless_data_mesh.compile.medallion_emit import compile_medallion_mesh
from serverless_data_mesh.compile.medallion_validate import validate_medallion_contract
from serverless_data_mesh.compile.validate import validate_contract

_TEMPLATE_ALIASES = {
    "medallion": "medallion-starter.mesh.yaml",
    "starter": "medallion-starter.mesh.yaml",
    "single": "single-pipeline.mesh.yaml",
    "pipeline": "single-pipeline.mesh.yaml",
}

_NOT_IMPLEMENTED = re.compile(r"raise\s+NotImplementedError", re.MULTILINE)


@dataclass(frozen=True, slots=True)
class NewMeshResult:
    contract_path: Path
    template: str
    output_dir: Path


@dataclass(frozen=True, slots=True)
class DoctorReport:
    root: Path
    readers_total: int
    readers_done: int
    readers_pending: list[str]
    has_orchestrator: bool
    pipeline_count: int
    ready_to_deploy: bool


@dataclass(frozen=True, slots=True)
class ApplyResult:
    contract_path: Path
    output_root: Path
    pipeline_count: int
    doctor: DoctorReport
    getting_started_path: Path


def list_templates() -> dict[str, str]:
    """Available `mesh new` template names."""
    return {
        "medallion": "Bronze/silver/gold starter (one domain)",
        "single": "Single DataProductPipeline",
        "northstar": "Full retail medallion example (orders + payments)",
    }


def _template_text(name: str) -> str:
    if name == "northstar":
        repo_root = Path(__file__).resolve().parents[3]
        northstar = repo_root / "examples" / "medallion-e2e" / "northstar.mesh.yaml"
        if northstar.is_file():
            return northstar.read_text(encoding="utf-8")
        raise FileNotFoundError(
            "northstar template requires examples/medallion-e2e/northstar.mesh.yaml in repo"
        )

    filename = _TEMPLATE_ALIASES.get(name, name)
    if not filename.endswith((".yaml", ".yml")):
        filename = f"{filename}.mesh.yaml" if name in _TEMPLATE_ALIASES else name

    pkg = resources.files("serverless_data_mesh").joinpath("templates", filename)
    return pkg.read_text(encoding="utf-8")


def scaffold_new(
    template: str,
    *,
    output_dir: str | Path = "my-mesh",
    producer_account: str = "123456789012",
    steward_account: str = "234567890123",
    publisher_account: str = "345678901234",
    domain: str = "orders",
    table: str = "curated_table",
    contract_name: str = "mesh.yaml",
) -> NewMeshResult:
    """Copy a starter YAML template; user edits then runs `apply`."""
    out = Path(output_dir)
    out.mkdir(parents=True, exist_ok=True)

    text = _template_text(template)
    text = (
        text.replace("{{PRODUCER_ACCOUNT}}", producer_account)
        .replace("{{STEWARD_ACCOUNT}}", steward_account)
        .replace("{{PUBLISHER_ACCOUNT}}", publisher_account)
        .replace("{{DOMAIN}}", domain)
        .replace("{{TABLE}}", table)
    )

    contract_path = out / contract_name
    contract_path.write_text(text, encoding="utf-8")

    (out / "README.txt").write_text(
        f"""Your mesh contract: {contract_name}

Next (one command):
  serverless-data-mesh apply --contract {contract_path} --output {out / "generated"}

Or step by step:
  serverless-data-mesh validate --contract {contract_path}
  serverless-data-mesh compile --contract {contract_path} --output {out / "generated"}
  serverless-data-mesh doctor --path {out / "generated"}

Docs: docs/metadata-driven-pipeline.md
""",
        encoding="utf-8",
    )

    return NewMeshResult(
        contract_path=contract_path.resolve(),
        template=template,
        output_dir=out.resolve(),
    )


def validate_contract_file(path: str | Path) -> list[str]:
    """Validate YAML without compiling. Empty list = valid."""
    doc = load_contract_document(path)
    if isinstance(doc, MedallionMeshContract):
        return validate_medallion_contract(doc)
    return validate_contract(doc)


def _count_pipelines(root: Path) -> int:
    manifest = root / "mesh.manifest.json"
    if manifest.is_file():
        data = json.loads(manifest.read_text(encoding="utf-8"))
        return int(data.get("pipeline_count", 0))
    manifests = list(root.rglob("pipeline.manifest.json"))
    if manifests:
        return len(manifests)
    return len(list(root.rglob("mesh.pipeline.yaml")))


def doctor_generated(root: str | Path) -> DoctorReport:
    """Check generated mesh: which readers.py still need implementation."""
    base = Path(root)
    if not base.is_dir():
        raise FileNotFoundError(f"Generated path not found: {base}")

    readers = list(base.rglob("readers.py"))
    pending: list[str] = []
    done = 0
    for reader in readers:
        text = reader.read_text(encoding="utf-8")
        if _NOT_IMPLEMENTED.search(text):
            pending.append(str(reader.relative_to(base)))
        else:
            done += 1

    orch = (base / "mesh.orchestrator.asl.json").is_file() or any(
        base.rglob("orchestrator.asl.json")
    )
    pipeline_count = _count_pipelines(base)

    return DoctorReport(
        root=base.resolve(),
        readers_total=len(readers),
        readers_done=done,
        readers_pending=pending,
        has_orchestrator=orch,
        pipeline_count=pipeline_count,
        ready_to_deploy=bool(readers) and not pending and pipeline_count > 0,
    )


def _emit_getting_started(
    *,
    contract_path: Path,
    output_root: Path,
    doctor: DoctorReport,
    pipeline_count: int,
) -> Path:
    path = output_root / "GETTING_STARTED.md"
    pending_lines = "\n".join(f"- [ ] Implement `{p}`" for p in doctor.readers_pending)
    if not pending_lines:
        pending_lines = "- [x] All readers.py implemented"

    path.write_text(
        f"""# Getting started — generated mesh

Contract: `{contract_path}`
Generated: `{output_root}`
Pipelines: **{pipeline_count}**

## Checklist

- [x] YAML validated
- [x] Pipelines compiled
{pending_lines}
- [ ] Package Lambda: `SDM_EXTRAS=spark ./infrastructure/terraform/scripts/package_lambda.sh`
- [ ] Deploy terraform per layer under `{output_root}/`
- [ ] Create Step Functions from `orchestrator.asl.json` / `mesh.orchestrator.asl.json`
- [ ] Run `serverless-data-mesh demo` locally to verify VRP gate

## One-liner re-apply after YAML edits

```bash
serverless-data-mesh apply --contract {contract_path} --output {output_root}
```

## Doctor

```bash
serverless-data-mesh doctor --path {output_root}
```

Ready to deploy: **{doctor.ready_to_deploy}**
""",
        encoding="utf-8",
    )
    return path.resolve()


def apply_mesh(
    contract_path: str | Path,
    *,
    output_dir: str | Path = "generated",
) -> ApplyResult:
    """Validate + compile + doctor + GETTING_STARTED — the one-shot workflow."""
    path = Path(contract_path)
    errors = validate_contract_file(path)
    if errors:
        raise ValueError("Contract validation failed: " + "; ".join(errors))

    doc = load_contract_document(path)
    out = Path(output_dir)

    if isinstance(doc, MedallionMeshContract):
        result = compile_medallion_mesh(doc, output_dir=out, source_contract_path=path)
        output_root = result.mesh_root
        pipeline_count = result.pipeline_count
    else:
        result = compile_pipeline(doc, output_dir=out)
        output_root = result.output_root
        pipeline_count = 1

    doctor = doctor_generated(output_root)
    getting_started = _emit_getting_started(
        contract_path=path.resolve(),
        output_root=output_root,
        doctor=doctor,
        pipeline_count=pipeline_count,
    )

    return ApplyResult(
        contract_path=path.resolve(),
        output_root=output_root,
        pipeline_count=pipeline_count,
        doctor=doctor,
        getting_started_path=getting_started,
    )
