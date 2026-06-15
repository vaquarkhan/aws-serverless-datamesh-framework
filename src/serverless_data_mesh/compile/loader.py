"""Load mesh.pipeline.yaml or .json contract files."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from serverless_data_mesh.compile.contract import MeshPipelineContract
from serverless_data_mesh.compile.medallion import MedallionMeshContract

ContractDocument = MeshPipelineContract | MedallionMeshContract


def _parse_text(path: Path, text: str) -> dict[str, Any]:
    suffix = path.suffix.lower()
    if suffix in (".yaml", ".yml"):
        try:
            import yaml
        except ImportError as exc:
            msg = (
                "PyYAML is required to load YAML contracts. "
                "Install with: pip install pyyaml"
            )
            raise ImportError(msg) from exc
        data = yaml.safe_load(text)
    elif suffix == ".json":
        data = json.loads(text)
    else:
        try:
            import yaml

            data = yaml.safe_load(text)
        except Exception:
            data = json.loads(text)
    if not isinstance(data, dict):
        raise ValueError(f"Contract root must be a mapping: {path}")
    return data


def load_contract_document(path: str | Path) -> ContractDocument:
    """Load DataProductPipeline or MedallionMesh contract from YAML/JSON."""
    contract_path = Path(path)
    if not contract_path.is_file():
        raise FileNotFoundError(f"Contract not found: {contract_path}")
    raw = _parse_text(contract_path, contract_path.read_text(encoding="utf-8"))
    kind = str(raw.get("kind", "DataProductPipeline"))
    if kind == "MedallionMesh":
        return MedallionMeshContract.from_dict(raw)
    return MeshPipelineContract.from_dict(raw)


def load_contract(path: str | Path) -> MeshPipelineContract:
    """Load a single DataProductPipeline contract."""
    doc = load_contract_document(path)
    if isinstance(doc, MedallionMeshContract):
        raise ValueError(
            f"{path} is a MedallionMesh contract; use compile with --mesh or load_contract_document"
        )
    return doc
