"""Build a mesh contract from init CLI arguments."""

from __future__ import annotations

from serverless_data_mesh.compile.contract import MeshPipelineContract


def contract_from_init(
    *,
    domain: str,
    table: str,
    account_id: str,
    owner_team: str | None = None,
) -> MeshPipelineContract:
    """Minimal sdm/v1 contract for `mesh init` / quick scaffold."""
    return MeshPipelineContract.from_dict(
        {
            "apiVersion": "sdm/v1",
            "kind": "DataProductPipeline",
            "metadata": {
                "domain_id": domain,
                "product_id": f"{domain}-{table}",
                "owner_team": owner_team or f"{domain}-platform",
                "description": f"Scaffolded pipeline for {domain} -> {table}",
            },
            "spec": {
                "accounts": {"producer": account_id},
                "boundary": {
                    "source_namespace": f"raw_{domain}",
                    "target_table": table,
                },
                "triggers": [{"type": "manual"}],
            },
        }
    )
