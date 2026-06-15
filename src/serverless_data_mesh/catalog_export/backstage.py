"""Export mesh contracts to Backstage catalog-info.yaml entities."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import yaml

from serverless_data_mesh.compile.loader import load_contract_document
from serverless_data_mesh.compile.medallion import MedallionMeshContract


def export_backstage_catalog(
    contract_path: str | Path,
    *,
    output_dir: str | Path = "catalog/backstage",
) -> list[Path]:
    """Generate Backstage Component + Resource entities from mesh YAML."""
    doc = load_contract_document(contract_path)
    out = Path(output_dir)
    out.mkdir(parents=True, exist_ok=True)
    written: list[Path] = []

    if isinstance(doc, MedallionMeshContract):
        for domain in doc.domains:
            for layer in domain.layers:
                entity = _component_entity(
                    name=f"{doc.name_prefix}-{domain.domain_id}-{layer.layer}",
                    title=f"{domain.domain_id} {layer.layer} data product",
                    owner=domain.owner_team or "data-platform",
                    description=layer.description or domain.description,
                    tags=["medallion", layer.layer, domain.domain_id, "serverless-data-mesh"],
                    annotations={
                        "serverless-data-mesh/domain": domain.domain_id,
                        "serverless-data-mesh/layer": layer.layer,
                        "serverless-data-mesh/table": layer.target_table,
                        "aws.amazon.com/account-id": doc.accounts.producer,
                    },
                )
                path = out / f"{domain.domain_id}-{layer.layer}-catalog-info.yaml"
                path.write_text(yaml.safe_dump(entity, sort_keys=False), encoding="utf-8")
                written.append(path.resolve())

        mesh_entity = _system_entity(
            name=doc.name_prefix,
            title=doc.organization,
            description=doc.description,
            owner=doc.domains[0].owner_team if doc.domains else "data-platform",
            domains=[d.domain_id for d in doc.domains],
        )
        mesh_path = out / "mesh-system-catalog-info.yaml"
        mesh_path.write_text(yaml.safe_dump(mesh_entity, sort_keys=False), encoding="utf-8")
        written.append(mesh_path.resolve())
        return written

    from serverless_data_mesh.compile.contract import MeshPipelineContract

    if isinstance(doc, MeshPipelineContract):
        entity = _component_entity(
            name=f"{doc.name_prefix or doc.domain_id}-{doc.boundary.target_table}",
            title=doc.product_id,
            owner=doc.owner_team or "data-platform",
            description=doc.description,
            tags=["data-product", doc.domain_id, "serverless-data-mesh"],
            annotations={
                "serverless-data-mesh/domain": doc.domain_id,
                "serverless-data-mesh/table": doc.boundary.target_table,
                "aws.amazon.com/account-id": doc.accounts.producer,
            },
        )
        path = out / f"{doc.domain_id}-catalog-info.yaml"
        path.write_text(yaml.safe_dump(entity, sort_keys=False), encoding="utf-8")
        return [path.resolve()]

    raise TypeError(f"Unsupported contract type: {type(doc)}")


def _component_entity(
    *,
    name: str,
    title: str,
    owner: str,
    description: str,
    tags: list[str],
    annotations: dict[str, str],
) -> dict[str, Any]:
    return {
        "apiVersion": "backstage.io/v1alpha1",
        "kind": "Component",
        "metadata": {
            "name": name,
            "title": title,
            "description": description,
            "tags": tags,
            "annotations": annotations,
        },
        "spec": {
            "type": "data-product",
            "lifecycle": "production",
            "owner": f"group:{owner}",
            "system": "serverless-data-mesh",
        },
    }


def _system_entity(
    *,
    name: str,
    title: str,
    description: str,
    owner: str,
    domains: list[str],
) -> dict[str, Any]:
    return {
        "apiVersion": "backstage.io/v1alpha1",
        "kind": "System",
        "metadata": {
            "name": name,
            "title": title,
            "description": description,
            "tags": ["medallion-mesh", "serverless-data-mesh"],
            "annotations": {
                "serverless-data-mesh/domains": json.dumps(domains),
            },
        },
        "spec": {
            "owner": f"group:{owner}",
            "domain": "data-mesh",
        },
    }
