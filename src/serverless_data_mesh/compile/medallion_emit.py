"""Compile full bronze / silver / gold mesh from one YAML file."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from serverless_data_mesh.compile.emit import _yaml_dump, compile_pipeline
from serverless_data_mesh.compile.medallion import MedallionMeshContract


@dataclass(frozen=True, slots=True)
class MedallionCompileResult:
    mesh_root: Path
    domain_paths: dict[str, Path]
    layer_paths: dict[str, Path]
    pipeline_count: int
    files_written: tuple[str, ...]


def _emit_domain_orchestrator(domain_id: str, layers: list[str]) -> str:
    states: dict[str, Any] = {}
    prev = None
    for i, layer in enumerate(layers):
        state_name = f"Run{layer.capitalize()}"
        next_name = (
            f"Run{layers[i + 1].capitalize()}" if i + 1 < len(layers) else None
        )
        states[state_name] = {
            "Type": "Task",
            "Resource": "arn:aws:states:::lambda:invoke",
            "Parameters": {
                "FunctionName": f"${{{domain_id}_{layer}_writer_arn}}",
                "Payload": {
                    "workload_id": f"${{domain_id}}-{layer}-${{partition_dt}}",
                    "domain_id": domain_id,
                    "medallion_layer": layer,
                    "partition_spec": {"dt": "${partition_dt}"},
                    "total_records": 1000000,
                },
            },
            "Retry": [
                {
                    "ErrorEquals": ["VerificationRejectedError"],
                    "IntervalSeconds": 30,
                    "MaxAttempts": 2,
                    "BackoffRate": 2.0,
                }
            ],
            "Next": next_name,
        }
        if next_name is None:
            states[state_name]["End"] = True
            del states[state_name]["Next"]
        prev = state_name

    return json.dumps(
        {
            "Comment": f"Medallion bronze→silver→gold for {domain_id}",
            "StartAt": f"Run{layers[0].capitalize()}",
            "States": states,
        },
        indent=2,
    )


def _emit_mesh_orchestrator(contract: MedallionMeshContract) -> str:
    branches = []
    for domain in contract.domains:
        layer_names = [layer.layer for layer in domain.layers]
        branches.append(
            {
                "StartAt": f"Domain_{domain.domain_id}",
                "States": {
                    f"Domain_{domain.domain_id}": {
                        "Type": "Task",
                        "Resource": "arn:aws:states:::states:startExecution.sync:2",
                        "Parameters": {
                            "StateMachineArn": f"${{{domain.domain_id}_medallion_orchestrator_arn}}",
                            "Input": {"partition_dt": "${partition_dt}"},
                        },
                        "End": True,
                    }
                },
            }
        )

    return json.dumps(
        {
            "Comment": f"Medallion mesh: {contract.organization}",
            "StartAt": "RunAllDomains",
            "States": {
                "RunAllDomains": {
                    "Type": "Parallel",
                    "Branches": branches,
                    "Next": "MeshLeaderCommit",
                },
                "MeshLeaderCommit": {
                    "Type": "Task",
                    "Resource": "arn:aws:states:::lambda:invoke",
                    "Parameters": {
                        "FunctionName": "${mesh_leader_commit_arn}",
                        "Payload": {"partition_dt": "${partition_dt}"},
                    },
                    "End": True,
                },
            },
        },
        indent=2,
    )


def _emit_domain_readers_stub(
    domain_id: str,
    layer_name: str,
    layer_table: str,
    upstream: str | None,
    transforms: tuple[str, ...],
    engine: str,
) -> str:
    upstream_note = (
        f"Read from upstream {upstream} Iceberg table in Publisher lakehouse."
        if upstream
        else "Read from external landing zone (S3, API, CDC)."
    )
    transform_note = ", ".join(transforms) if transforms else "pass-through"
    return f'''"""GENERATED readers for {domain_id}/{layer_name} — implement business I/O.

Layer: {layer_name} · Table: {layer_table} · Engine: {engine}
Upstream: {upstream or "external"}
Transforms (metadata): {transform_note}
"""

from __future__ import annotations

from typing import Any

# TODO: {upstream_note}
# TODO: Apply transforms: {transform_note}


def source_reader(start: int, end: int) -> list[dict[str, Any]]:
    raise NotImplementedError("Implement {domain_id}/{layer_name} source_reader")


def sink_reader(start: int, end: int) -> list[dict[str, Any]]:
    raise NotImplementedError("Implement {domain_id}/{layer_name} sink_reader")


def batch_writer(start: int, end: int) -> list[str]:
    raise NotImplementedError("Implement {domain_id}/{layer_name} batch_writer")
'''


def _emit_mesh_readme(contract: MedallionMeshContract, pipeline_count: int) -> str:
    domain_rows = []
    for d in contract.domains:
        layers = " → ".join(layer.layer for layer in d.layers)
        domain_rows.append(f"| {d.domain_id} | {layers} | {d.schedule_cron or 'manual'} |")

    return f"""# {contract.organization} — medallion mesh (generated)

**{pipeline_count} PVDM pipelines** generated from one YAML metadata file.

## Domains

| Domain | Layers | Bronze schedule |
|--------|--------|-----------------|
{chr(10).join(domain_rows)}

## Layout

```
<mesh-root>/
├── northstar.mesh.yaml       # source metadata (edit this only)
├── mesh.orchestrator.asl.json
├── orders/
│   ├── orchestrator.asl.json # bronze → silver → gold
│   ├── bronze/               # full Lambda pipeline
│   ├── silver/
│   └── gold/                 # consumer SLAs + LF gates
└── payments/
    └── ...
```

## User workflow

1. Edit `northstar.mesh.yaml` (accounts, layers, transforms, SLAs)
2. `serverless-data-mesh compile --contract northstar.mesh.yaml`
3. Implement `readers.py` in each layer (only hand-written code)
4. Deploy terraform/ per layer + mesh orchestrator

## Vaquar Pattern

Each layer run: Physical → VRP → Durable → Metadata. Gold layer consumer_slas gate Lake Formation reads.
"""


def compile_medallion_mesh(
    contract: MedallionMeshContract,
    *,
    output_dir: str | Path = "generated-mesh",
    source_contract_path: Path | None = None,
) -> MedallionCompileResult:
    """Generate all bronze/silver/gold pipelines and mesh orchestrators."""
    mesh_root = Path(output_dir)
    mesh_root.mkdir(parents=True, exist_ok=True)

    all_written: list[str] = []
    domain_paths: dict[str, Path] = {}
    layer_paths: dict[str, Path] = {}
    pipeline_count = 0

    if source_contract_path and source_contract_path.is_file():
        rel = "northstar.mesh.yaml" if "northstar" in source_contract_path.name else source_contract_path.name
        dest = mesh_root / rel
        dest.write_text(source_contract_path.read_text(encoding="utf-8"), encoding="utf-8")
        all_written.append(rel)

    for domain in contract.domains:
        domain_root = mesh_root / domain.domain_id
        domain_root.mkdir(parents=True, exist_ok=True)
        domain_paths[domain.domain_id] = domain_root.resolve()

        layer_names = [layer.layer for layer in domain.layers]
        orch_path = domain_root / "orchestrator.asl.json"
        orch_path.write_text(_emit_domain_orchestrator(domain.domain_id, layer_names), encoding="utf-8")
        all_written.append(f"{domain.domain_id}/orchestrator.asl.json")

        domain_manifest_layers: list[str] = []

        for layer in domain.layers:
            pipeline_count += 1
            pipe_contract = contract.layer_pipeline_contract(domain, layer)
            layer_out = domain_root / layer.layer
            result = compile_pipeline(
                pipe_contract,
                output_dir=mesh_root,
                relative_root=f"{domain.domain_id}/{layer.layer}",
                write_canonical_contract=True,
            )
            layer_paths[f"{domain.domain_id}/{layer.layer}"] = result.output_root
            domain_manifest_layers.append(layer.layer)

            readers_stub = _emit_domain_readers_stub(
                domain.domain_id,
                layer.layer,
                layer.target_table,
                layer.upstream_layer,
                layer.transforms,
                layer.runtime_engine,
            )
            readers_path = domain_root / layer.layer / "readers.py"
            readers_path.write_text(readers_stub, encoding="utf-8")

        domain_slice = {
            "domain_id": domain.domain_id,
            "layers": domain_manifest_layers,
            "orchestrator": "orchestrator.asl.json",
        }
        (domain_root / "domain.manifest.json").write_text(
            json.dumps(domain_slice, indent=2),
            encoding="utf-8",
        )
        all_written.append(f"{domain.domain_id}/domain.manifest.json")

    mesh_orch = mesh_root / "mesh.orchestrator.asl.json"
    mesh_orch.write_text(_emit_mesh_orchestrator(contract), encoding="utf-8")
    all_written.append("mesh.orchestrator.asl.json")

    mesh_manifest = {
        "generator": "serverless-data-mesh compile (MedallionMesh)",
        "organization": contract.organization,
        "pipeline_count": pipeline_count,
        "domains": list(domain_paths.keys()),
        "layers_per_domain": {
            d.domain_id: [layer.layer for layer in d.layers] for d in contract.domains
        },
        "mesh_transactions": list(contract.mesh_transactions),
    }
    (mesh_root / "mesh.manifest.json").write_text(
        json.dumps(mesh_manifest, indent=2),
        encoding="utf-8",
    )
    all_written.append("mesh.manifest.json")

    readme = mesh_root / "README.md"
    readme.write_text(_emit_mesh_readme(contract, pipeline_count), encoding="utf-8")
    all_written.append("README.md")

    canonical = mesh_root / "mesh.medallion.yaml"
    canonical.write_text(_yaml_dump(contract.to_dict()), encoding="utf-8")
    all_written.append("mesh.medallion.yaml")

    return MedallionCompileResult(
        mesh_root=mesh_root.resolve(),
        domain_paths=domain_paths,
        layer_paths=layer_paths,
        pipeline_count=pipeline_count,
        files_written=tuple(all_written),
    )
