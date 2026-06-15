"""Validate medallion mesh contracts."""

from __future__ import annotations

import re

from serverless_data_mesh.compile.medallion import MEDALLION_LAYERS, MedallionMeshContract

_ACCOUNT_RE = re.compile(r"^\d{12}$")


def validate_medallion_contract(contract: MedallionMeshContract) -> list[str]:
    errors: list[str] = []

    if contract.api_version != "sdm/v1":
        errors.append(f"apiVersion must be 'sdm/v1', got {contract.api_version!r}")
    if contract.kind != "MedallionMesh":
        errors.append(f"kind must be 'MedallionMesh', got {contract.kind!r}")

    if not _ACCOUNT_RE.match(contract.accounts.producer):
        errors.append("spec.accounts.producer must be a 12-digit AWS account ID")

    if not contract.domains:
        errors.append("spec.domains must include at least one domain")

    for domain in contract.domains:
        if not domain.domain_id:
            errors.append("domains[].domain_id is required")
        layer_names = {layer.layer for layer in domain.layers}
        if "bronze" not in layer_names:
            errors.append(f"domain {domain.domain_id}: bronze layer is required")

        for layer in domain.layers:
            if layer.layer == "silver" and layer.upstream_layer != "bronze":
                errors.append(
                    f"domain {domain.domain_id}: silver must set upstream_layer: bronze"
                )
            if layer.layer == "gold" and layer.upstream_layer != "silver":
                errors.append(
                    f"domain {domain.domain_id}: gold must set upstream_layer: silver"
                )
            if layer.layer not in MEDALLION_LAYERS:
                errors.append(f"unknown layer {layer.layer!r}; use bronze|silver|gold")

        if "gold" in layer_names and not domain.schedule_cron:
            has_gold_sla = any(
                layer.consumer_slas for layer in domain.layers if layer.layer == "gold"
            )
            if not has_gold_sla:
                errors.append(
                    f"domain {domain.domain_id}: gold layer should define consumer_slas"
                )

    return errors
