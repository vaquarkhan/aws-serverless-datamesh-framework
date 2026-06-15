"""Scaffold new domain writers for the Vaquar Pattern."""

from __future__ import annotations

from pathlib import Path

from serverless_data_mesh.compile.emit import compile_pipeline
from serverless_data_mesh.compile.from_init import contract_from_init
from serverless_data_mesh.compile.validate import validate_contract


def scaffold_domain(
    *,
    domain: str,
    table: str,
    account_id: str,
    output_dir: str = "domains",
) -> Path:
    """Create a metadata-driven PVDM pipeline from minimal init arguments."""
    contract = contract_from_init(domain=domain, table=table, account_id=account_id)
    errors = validate_contract(contract)
    if errors:
        raise ValueError("; ".join(errors))
    result = compile_pipeline(contract, output_dir=output_dir)
    return result.output_root
