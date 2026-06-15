"""Scaffold new domain writers for the Vaquar Pattern."""

from __future__ import annotations

from pathlib import Path


def scaffold_domain(
    *,
    domain: str,
    table: str,
    account_id: str,
    output_dir: str = "domains",
) -> Path:
    """Create handler, contract, terraform stub, and tests for a new domain."""
    root = Path(output_dir) / domain
    root.mkdir(parents=True, exist_ok=True)

    (root / "tests").mkdir(exist_ok=True)
    (root / "terraform").mkdir(exist_ok=True)

    handler = root / "handler.py"
    handler.write_text(
        HANDLER_TEMPLATE.format(domain=domain, table=table),
        encoding="utf-8",
    )

    contract = root / "contract.yaml"
    contract.write_text(
        CONTRACT_TEMPLATE.format(domain=domain, table=table, account_id=account_id),
        encoding="utf-8",
    )

    (root / "terraform" / "main.tf").write_text(
        TERRAFORM_TEMPLATE.format(domain=domain, account_id=account_id),
        encoding="utf-8",
    )
    (root / "terraform" / "terraform.tfvars.example").write_text(
        TFVARS_TEMPLATE.format(domain=domain, account_id=account_id),
        encoding="utf-8",
    )

    (root / "tests" / f"test_{domain}.py").write_text(
        TEST_TEMPLATE.format(domain=domain, table=table),
        encoding="utf-8",
    )

    (root / "consumer_sla.yaml").write_text(
        CONSUMER_SLA_TEMPLATE.format(domain=domain, table=table),
        encoding="utf-8",
    )

    (root / "step_function.asl.json").write_text(
        STEP_FUNCTION_TEMPLATE.format(domain=domain, table=table),
        encoding="utf-8",
    )

    (root / "README.md").write_text(
        README_TEMPLATE.format(domain=domain, table=table),
        encoding="utf-8",
    )

    return root


HANDLER_TEMPLATE = '''"""Domain writer: {domain} -> {table} (Vaquar Pattern PVDM)."""

from __future__ import annotations

from typing import Any

from serverless_data_mesh.governance.consumer_sla import enforce_consumer_sla
from serverless_data_mesh.metrics.mesh_trust import publish_vrp_metric
from serverless_data_mesh.orchestration.reprocess import attempt_vrp_repair
from serverless_data_mesh.types.workload import ConsumerSLAContract, DataWriteWorkload
from serverless_data_mesh.verification.backend import create_proof_generator
from serverless_data_mesh.verification.vrp import validate_then_commit


def source_reader(start: int, end: int) -> list[dict[str, Any]]:
    return [{{"id": str(i), "payload_hash": f"h{{i}}"}} for i in range(start, end)]


def sink_reader(start: int, end: int) -> list[dict[str, Any]]:
    """Read physical sink for VRP; replace with Parquet reader in production."""
    return source_reader(start, end)


def batch_writer(start: int, end: int) -> list[str]:
    base = "s3://publisher-lakehouse/{table}/dt=PARTITION"
    return [f"{{base}}/part-{{i:08d}}.parquet" for i in range(start, end)]


def lambda_handler(event: dict[str, Any], context: Any) -> dict[str, Any]:
    """Wire IceGuardDurableCoordinator with auto-repair and consumer SLA gate."""
    raise NotImplementedError("Copy wiring from examples/domain_writer/handler.py")
'''

CONTRACT_TEMPLATE = """# Data product contract: {domain}
product_id: {domain}-{table}
owner_team: {domain}-platform
domain_id: {domain}
target_table: {table}
source_namespace: raw_{domain}
producer_account_id: \"{account_id}\"
sla_freshness_hours: 2
schema_version: \"1.0.0\"
quality_policy_id: strict-zero-drop
vaquar_pattern: PVDM
"""

TERRAFORM_TEMPLATE = """# Producer Terraform stub for domain: {domain}
variable "producer_account_id" {{
  default = "{account_id}"
}}

variable "domain_id" {{
  default = "{domain}"
}}

# Copy modules from infrastructure/terraform/environments/multi-account/producer/
"""

TFVARS_TEMPLATE = """aws_region = \"us-east-2\"
name_prefix = \"sdm-{domain}\"
producer_account_id = \"{account_id}\"
# steward_account_id = \"STEWARD_ACCOUNT\"
# publisher_account_id = \"PUBLISHER_ACCOUNT\"
"""

TEST_TEMPLATE = '''"""Tests for {domain} domain writer."""

from __future__ import annotations


def test_boundary_declared() -> None:
    from serverless_data_mesh import DomainTransactionBoundary

    boundary = DomainTransactionBoundary(
        domain_id="{domain}",
        source_namespace="raw_{domain}",
        target_table="{table}",
        partition_spec={{"dt": "2026-06-14"}},
    )
    assert boundary.domain_id == "{domain}"
'''

README_TEMPLATE = """# {domain} domain writer

Target table: `{table}`

## Scaffolded by

```bash
serverless-data-mesh init --domain {domain} --table {table} --account YOUR_ACCOUNT_ID
```

## Next steps

1. Implement `handler.py` (copy from `examples/domain_writer/handler.py`)
2. Review `consumer_sla.yaml` for Lake Formation read gates
3. Deploy `step_function.asl.json` durable workflow
4. Deploy Terraform in `terraform/`
5. Run `make demo` locally to verify PVDM gate
"""

CONSUMER_SLA_TEMPLATE = """# Consumer SLA for {table} (VRP-backed Lake Formation gate)
consumer_id: analytics-team
target_table: {table}
max_freshness_minutes: 60
min_completeness_pct: 99.9
required_columns:
  - id
  - payload_hash
enforcement: vrp_backed
"""

STEP_FUNCTION_TEMPLATE = """{{
  "Comment": "PVDM durable write for {domain} -> {table}",
  "StartAt": "WriteChunk",
  "States": {{
    "WriteChunk": {{
      "Type": "Task",
      "Resource": "arn:aws:states:::lambda:invoke",
      "Parameters": {{
        "FunctionName": "${{DomainWriterArn}}",
        "Payload.$": "$"
      }},
      "Retry": [
        {{
          "ErrorEquals": ["VerificationRejectedError"],
          "IntervalSeconds": 30,
          "MaxAttempts": 2,
          "BackoffRate": 2.0
        }}
      ],
      "Next": "CommitMetadata"
    }},
    "CommitMetadata": {{
      "Type": "Task",
      "Resource": "arn:aws:states:::lambda:invoke",
      "Parameters": {{
        "FunctionName": "${{CatalogCommitArn}}",
        "Payload.$": "$"
      }},
      "End": true
    }}
  }}
}}
"""
