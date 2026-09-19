"""API helpers for the mesh designer (drag-drop → save contract → apply pipelines)."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import yaml

from serverless_data_mesh.compile.loader import load_contract_document
from serverless_data_mesh.compile.medallion import MedallionMeshContract
from serverless_data_mesh.compile.medallion_validate import validate_medallion_contract
from serverless_data_mesh.compile.wizard import apply_mesh


def mesh_project_root(generated_root: Path) -> Path:
    """Directory that owns the contract + generated/ folder."""
    return generated_root.resolve().parent


def contract_paths(generated_root: Path) -> dict[str, Path]:
    root = mesh_project_root(generated_root)
    return {
        "yaml": root / "mesh.yaml",
        "json": root / "mesh.json",
        "generated": generated_root.resolve(),
        "project": root,
        "terraform_hint": root / "terraform.contract.txt",
    }


def contract_to_yaml(contract: dict[str, Any]) -> str:
    return yaml.safe_dump(contract, sort_keys=False, default_flow_style=False)


def validate_designer_contract(contract: dict[str, Any]) -> dict[str, Any]:
    tmp = Path.cwd() / ".sdm-designer-validate.json"
    try:
        tmp.write_text(json.dumps(contract), encoding="utf-8")
        doc = load_contract_document(tmp)
        if not isinstance(doc, MedallionMeshContract):
            return {
                "ok": False,
                "errors": ["Contract kind must be MedallionMesh"],
            }
        errors = validate_medallion_contract(doc)
        if errors:
            return {"ok": False, "errors": errors}
        layer_n = sum(len(d.layers) for d in doc.domains)
        return {
            "ok": True,
            "errors": [],
            "domains": len(doc.domains),
            "pipeline_estimate": layer_n,
        }
    except Exception as exc:  # noqa: BLE001 — surface to UI
        return {"ok": False, "errors": [str(exc)]}
    finally:
        if tmp.exists():
            tmp.unlink(missing_ok=True)


def save_designer_contract(
    *,
    generated_root: Path,
    contract: dict[str, Any],
    fmt: str = "both",
) -> dict[str, Any]:
    """Write canonical mesh.yaml / mesh.json next to generated/ for apply + Terraform."""
    paths = contract_paths(generated_root)
    paths["project"].mkdir(parents=True, exist_ok=True)
    written: list[str] = []
    fmt_l = (fmt or "both").lower()

    if fmt_l in ("json", "both"):
        paths["json"].write_text(json.dumps(contract, indent=2) + "\n", encoding="utf-8")
        written.append(str(paths["json"]))
    if fmt_l in ("yaml", "yml", "both"):
        paths["yaml"].write_text(contract_to_yaml(contract), encoding="utf-8")
        written.append(str(paths["yaml"]))

    # Pointer Terraform / CI can read without guessing filenames
    net = (contract.get("spec") or {}).get("networking") or {}
    net_mode = str(net.get("mode") or "none").lower()
    region = str((contract.get("spec") or {}).get("aws_region") or "us-east-2")
    accounts = (contract.get("spec") or {}).get("accounts") or {}
    prefix = str((contract.get("spec") or {}).get("name_prefix") or "sdm")

    if net_mode == "existing":
        subs = ", ".join(f'"{s}"' for s in (net.get("subnet_ids") or []))
        sgs = ", ".join(f'"{s}"' for s in (net.get("security_group_ids") or []))
        vpc_line = (
            "\nvpc_mode = \"existing\"\n"
            f"lambda_subnet_ids         = [{subs}]\n"
            f"lambda_security_group_ids = [{sgs}]\n"
        )
        if net.get("vpc_id"):
            vpc_line += f"# existing vpc_id note: {net.get('vpc_id')}\n"
    elif net_mode == "create":
        cidr = net.get("cidr_block") or "10.80.0.0/16"
        azs = int(net.get("az_count") or 2)
        vpc_line = (
            "\nvpc_mode = \"create\"\n"
            f'vpc_cidr_block = "{cidr}"\n'
            f"vpc_az_count   = {azs}\n"
        )
    else:
        vpc_line = (
            "\nvpc_mode = \"none\"\n"
            "# No VPC — AWS-managed Lambda network (NOT account default VPC)\n"
        )

    hint = (
        "# Canonical mesh contract written by control UI — Create data mesh\n"
        f"MESH_CONTRACT={paths['yaml'].as_posix()}\n"
        f"MESH_GENERATED={paths['generated'].as_posix()}\n"
        f"aws_region   = \"{region}\"\n"
        f"name_prefix  = \"{prefix}\"\n"
        f"# accounts: producer={accounts.get('producer')} "
        f"steward={accounts.get('steward')} publisher={accounts.get('publisher')}\n"
        "# IAM: Terraform creates *-domain-writer + Step Functions + EventBridge "
        "(do not paste role ARNs)\n"
        f"{vpc_line}"
        "# Next: serverless-data-mesh apply --contract $MESH_CONTRACT --output $MESH_GENERATED\n"
        "# Then: package Lambda zip + terraform apply "
        "(infrastructure/terraform/environments/prod)\n"
    )
    paths["terraform_hint"].write_text(hint, encoding="utf-8")
    written.append(str(paths["terraform_hint"]))

    return {
        "ok": True,
        "paths": written,
        "contract_yaml": str(paths["yaml"]),
        "contract_json": str(paths["json"]),
        "directory": str(paths["project"]),
        "generated": str(paths["generated"]),
        "apply_command": (
            f'serverless-data-mesh apply --contract "{paths["yaml"]}" '
            f'--output "{paths["generated"]}"'
        ),
    }


def save_and_apply_designer_contract(
    *,
    generated_root: Path,
    contract: dict[str, Any],
) -> dict[str, Any]:
    """Save mesh.yaml into the project dir, then compile pipelines into generated/."""
    saved = save_designer_contract(
        generated_root=generated_root,
        contract=contract,
        fmt="both",
    )
    contract_yaml = Path(saved["contract_yaml"])
    result = apply_mesh(contract_yaml, output_dir=generated_root)
    return {
        "ok": True,
        "saved": saved,
        "contract_path": str(result.contract_path),
        "generated": str(result.output_root),
        "pipeline_count": result.pipeline_count,
        "readers_done": result.doctor.readers_done,
        "readers_total": result.doctor.readers_total,
        "readers_pending": result.doctor.readers_pending,
        "ready_to_deploy": result.doctor.ready_to_deploy,
        "getting_started": str(result.getting_started_path),
        "next": [
            "Implement any pending readers.py under the generated folder",
            "Package Lambda: ./infrastructure/terraform/scripts/package_lambda.sh",
            "terraform apply in infrastructure/terraform/environments/prod "
            "(point lambda_package_path at the zip; contract is mesh.yaml beside generated/)",
        ],
    }
