"""End-to-end deploy: apply → terraform → optional Step Functions start."""

from __future__ import annotations

import json
import os
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any


@dataclass(frozen=True, slots=True)
class DeployResult:
    contract_path: Path
    generated_path: Path
    terraform_dir: Path
    terraform_applied: bool
    mesh_execution_arn: str | None
    partition_dt: str


def _run(cmd: list[str], *, cwd: Path | None = None, dry_run: bool = False) -> subprocess.CompletedProcess[str]:
    if dry_run:
        print(f"[dry-run] {' '.join(cmd)}", file=sys.stderr)
        return subprocess.CompletedProcess(cmd, 0, "", "")
    return subprocess.run(cmd, cwd=cwd, check=False, text=True, capture_output=True)


def deploy_mesh(
    *,
    contract: str | Path,
    output: str | Path = "generated",
    terraform_dir: str | Path | None = None,
    partition_dt: str = "2026-06-14",
    skip_apply: bool = False,
    skip_terraform: bool = False,
    terraform_auto_approve: bool = False,
    start_execution: bool = False,
    dry_run: bool = False,
) -> DeployResult:
    """Validate, compile, terraform apply, and optionally start mesh orchestrator."""
    from serverless_data_mesh.compile.wizard import apply_mesh

    contract_path = Path(contract).resolve()
    generated_path = Path(output).resolve()
    tf_dir = Path(terraform_dir or _default_terraform_dir()).resolve()

    if not skip_apply:
        apply_mesh(contract_path, output_dir=generated_path)

    manifest = generated_path / "layer_lambda.manifest.json"
    if not manifest.is_file():
        raise FileNotFoundError(
            f"Missing {manifest} — run apply first or use a MedallionMesh contract"
        )

    terraform_applied = False
    mesh_arn: str | None = None

    if not skip_terraform:
        init = _run(
            ["terraform", "init", "-input=false"],
            cwd=tf_dir,
            dry_run=dry_run,
        )
        if init.returncode != 0 and not dry_run:
            raise RuntimeError(init.stderr or init.stdout)

        plan_args = [
            "terraform",
            "apply",
            "-input=false",
            f"-var=mesh_generated_path={generated_path.as_posix()}",
            f"-var=layer_lambda_manifest_path={manifest.as_posix()}",
        ]
        if terraform_auto_approve:
            plan_args.append("-auto-approve")
        apply_tf = _run(plan_args, cwd=tf_dir, dry_run=dry_run)
        if apply_tf.returncode != 0 and not dry_run:
            raise RuntimeError(apply_tf.stderr or apply_tf.stdout)
        terraform_applied = True

        if start_execution and not dry_run:
            out = _run(
                ["terraform", "output", "-raw", "mesh_orchestrator_arn"],
                cwd=tf_dir,
            )
            if out.returncode == 0:
                mesh_arn = out.stdout.strip()
                payload = json.dumps({"partition_dt": partition_dt})
                exec_out = _run(
                    [
                        "aws",
                        "stepfunctions",
                        "start-execution",
                        "--state-machine-arn",
                        mesh_arn,
                        "--input",
                        payload,
                    ],
                    dry_run=dry_run,
                )
                if exec_out.returncode != 0:
                    raise RuntimeError(exec_out.stderr or exec_out.stdout)

    return DeployResult(
        contract_path=contract_path,
        generated_path=generated_path,
        terraform_dir=tf_dir,
        terraform_applied=terraform_applied,
        mesh_execution_arn=mesh_arn,
        partition_dt=partition_dt,
    )


def _default_terraform_dir() -> Path:
    env = os.environ.get("SDM_TERRAFORM_MEDALLION_DIR")
    if env:
        return Path(env)
    here = Path(__file__).resolve()
    candidate = here.parents[3] / "infrastructure" / "terraform" / "environments" / "medallion"
    if candidate.is_dir():
        return candidate
    return Path("infrastructure/terraform/environments/medallion")


def result_to_dict(result: DeployResult) -> dict[str, Any]:
    return {
        "contract_path": str(result.contract_path),
        "generated_path": str(result.generated_path),
        "terraform_dir": str(result.terraform_dir),
        "terraform_applied": result.terraform_applied,
        "mesh_execution_arn": result.mesh_execution_arn,
        "partition_dt": result.partition_dt,
    }
