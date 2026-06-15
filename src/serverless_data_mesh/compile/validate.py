"""Validate mesh pipeline contracts before code generation."""

from __future__ import annotations

import re

from serverless_data_mesh.compile.contract import MeshPipelineContract

_ACCOUNT_RE = re.compile(r"^\d{12}$")


def validate_contract(contract: MeshPipelineContract) -> list[str]:
    """Return human-readable validation errors (empty if valid)."""
    errors: list[str] = []

    if contract.api_version != "sdm/v1":
        errors.append(f"apiVersion must be 'sdm/v1', got {contract.api_version!r}")
    if contract.kind != "DataProductPipeline":
        errors.append(f"kind must be 'DataProductPipeline', got {contract.kind!r}")

    if not contract.domain_id:
        errors.append("metadata.domain_id is required")
    if not contract.boundary.target_table:
        errors.append("spec.boundary.target_table is required")
    if not contract.boundary.source_namespace:
        errors.append("spec.boundary.source_namespace is required")

    if not _ACCOUNT_RE.match(contract.accounts.producer):
        errors.append("spec.accounts.producer must be a 12-digit AWS account ID")

    for trigger in contract.triggers:
        if trigger.type == "schedule" and not trigger.cron:
            errors.append("schedule trigger requires spec.triggers[].cron")

    for sla in contract.consumer_slas:
        if not sla.consumer_id:
            errors.append("consumer_slas[].consumer_id is required")

    if contract.governance.canary_max_divergence_pct < 0:
        errors.append("governance.canary_max_divergence_pct must be >= 0")

    return errors
