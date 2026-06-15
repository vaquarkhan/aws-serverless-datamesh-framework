"""Emit pipeline artifacts from a validated MeshPipelineContract."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from serverless_data_mesh.compile.contract import MeshPipelineContract


@dataclass(frozen=True, slots=True)
class CompileResult:
    """Paths written by the metadata-driven pipeline compiler."""

    output_root: Path
    contract_path: Path
    files_written: tuple[str, ...]


def _yaml_dump(data: dict[str, Any]) -> str:
    try:
        import yaml
    except ImportError as exc:
        raise ImportError("PyYAML required: pip install pyyaml") from exc
    return yaml.safe_dump(data, sort_keys=False, default_flow_style=False)


def _schedule_triggers(contract: MeshPipelineContract) -> list[Any]:
    return [t for t in contract.triggers if t.type == "schedule" and t.cron]


def _emit_readers_py(contract: MeshPipelineContract) -> str:
    if contract.runtime.engine == "pyspark":
        return _emit_readers_spark_py(contract)
    return _emit_readers_default_py(contract)


def _emit_readers_default_py(contract: MeshPipelineContract) -> str:
    id_field = contract.workload.identity_fields[0]
    other_fields = [f for f in contract.workload.content_fields if f != id_field]
    extra = ", ".join(f'"{f}": f"{f}_{{i}}"' for f in other_fields)
    if extra:
        record_body = f'"{id_field}": str(i), {extra}'
    else:
        record_body = f'"{id_field}": str(i)'
    return f'''"""Domain I/O hooks for {contract.domain_id} — implement for your source system."""

from __future__ import annotations

from typing import Any


def source_reader(start: int, end: int) -> list[dict[str, Any]]:
    """Read source records [start, end) for VRP fingerprinting."""
    # TODO: replace with JDBC, S3, API, or streaming reader
    return [{{{record_body}}} for i in range(start, end)]


def sink_reader(start: int, end: int) -> list[dict[str, Any]]:
    """Read physical sink Parquet/JSON for VRP (required when auto_repair is enabled)."""
    return source_reader(start, end)


def batch_writer(start: int, end: int) -> list[str]:
    """Write [start, end) to lakehouse; return new Parquet S3 URIs."""
    base = "s3://publisher-lakehouse/{contract.boundary.target_table}/dt=PARTITION"
    return [f"{{base}}/part-{{i:08d}}.parquet" for i in range(start, end)]
'''


def _emit_readers_spark_py(contract: MeshPipelineContract) -> str:
    rules_note = ""
    if contract.runtime.spark_rules_enabled:
        rules_note = """
    if os.environ.get("SPARKRULES_DRL") or os.environ.get("SPARKRULES_DRL_S3_URI"):
        from serverless_data_mesh.rules import SparkRulesConnector
        connector = SparkRulesConnector.from_environment()
        records, _ = connector.apply_chunk(records)
"""
    return f'''"""PySpark-on-Lambda I/O for {contract.domain_id} (physical layer only).

Package Lambda with: SDM_EXTRAS={contract.runtime.package_extras or "spark"} package_lambda.sh
Requires JVM + PySpark Lambda layer or container image ({contract.runtime.lambda_memory_mb} MB).
"""

from __future__ import annotations

import os
from typing import Any

_SPARK: Any | None = None


def _spark_session() -> Any:
    global _SPARK
    if _SPARK is None:
        from pyspark.sql import SparkSession

        _SPARK = (
            SparkSession.builder.appName("{contract.product_id}")
            .config("spark.sql.shuffle.partitions", "{contract.runtime.spark_shuffle_partitions}")
            .getOrCreate()
        )
    return _SPARK


def source_reader(start: int, end: int) -> list[dict[str, Any]]:
    """Read source via Spark; return rows for VRP fingerprinting."""
    spark = _spark_session()
    # TODO: spark.read.parquet("s3://...").filter(...).limit(end).collect()
    records = [{{"{contract.workload.identity_fields[0]}": str(i)}} for i in range(start, end)]
{rules_note}
    return records


def sink_reader(start: int, end: int) -> list[dict[str, Any]]:
    spark = _spark_session()
    # TODO: read written Parquet paths for VRP reconciliation
    return source_reader(start, end)


def batch_writer(start: int, end: int) -> list[str]:
    spark = _spark_session()
    records = source_reader(start, end)
    # TODO: df.write.parquet("s3://publisher/{contract.boundary.target_table}/dt=...")
    base = "s3://publisher-lakehouse/{contract.boundary.target_table}/dt=PARTITION"
    return [f"{{base}}/part-{{i:08d}}.parquet" for i in range(start, end)]
'''


def _emit_lambda_tf(contract: MeshPipelineContract) -> str:
    extras = contract.runtime.package_extras or "core"
    return f'''# GENERATED Lambda wiring for {contract.domain_id}
# Build compiled pipeline zip:
#   SDM_PIPELINE_SRC={contract.domain_id} SDM_EXTRAS={extras} \\
#     ./infrastructure/terraform/scripts/package_lambda.sh

variable "lambda_handler" {{
  default     = "handler.lambda_handler"
  description = "Flat handler from compile output (handler.py at zip root)"
}}

variable "lambda_memory_mb" {{
  default = {contract.runtime.lambda_memory_mb}
}}

variable "lambda_timeout_seconds" {{
  default = {contract.runtime.lambda_timeout_seconds}
}}

variable "lambda_package_extras" {{
  default     = "{extras}"
  description = "pip extra for domain writer zip: rules | spark | all"
}}

# module "lambda" {{
#   handler = var.lambda_handler
#   memory_size = var.lambda_memory_mb
#   timeout = var.lambda_timeout_seconds
# }}

# runtime.engine = {contract.runtime.engine}
# Use container image when engine=pyspark (JVM + PySpark exceed zip limits)
'''


def _emit_pipeline_config(contract: MeshPipelineContract) -> str:
    payload = json.dumps(contract.to_dict(), indent=4)
    return f'''"""GENERATED by serverless-data-mesh compile — do not edit."""

from __future__ import annotations

CONTRACT: dict = {payload}
'''


def _emit_handler(contract: MeshPipelineContract) -> str:
    return f'''"""GENERATED PVDM handler for {contract.domain_id} -> {contract.boundary.target_table}."""

from __future__ import annotations

import json
import logging
from typing import Any

from aws_durable_execution_sdk_python import DurableContext, durable_execution

from pipeline_config import CONTRACT
from readers import batch_writer, sink_reader, source_reader
from serverless_data_mesh.compile.runtime import run_metadata_pipeline

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)


@durable_execution
def handler(event: dict[str, Any], context: DurableContext) -> dict[str, Any]:
    result = run_metadata_pipeline(
        event,
        context,
        CONTRACT,
        source_reader=source_reader,
        batch_writer=batch_writer,
        sink_reader=sink_reader,
    )
    logger.info("Pipeline finished: %s", json.dumps(result, default=str))
    return result


lambda_handler = handler
'''


def _emit_step_function(contract: MeshPipelineContract) -> str:
    return json.dumps(
        {
            "Comment": f"PVDM durable write for {contract.domain_id} -> {contract.boundary.target_table}",
            "StartAt": "WriteChunk",
            "States": {
                "WriteChunk": {
                    "Type": "Task",
                    "Resource": "arn:aws:states:::lambda:invoke",
                    "Parameters": {
                        "FunctionName": "${DomainWriterArn}",
                        "Payload.$": "$",
                    },
                    "Retry": [
                        {
                            "ErrorEquals": ["VerificationRejectedError"],
                            "IntervalSeconds": 30,
                            "MaxAttempts": 2,
                            "BackoffRate": 2.0,
                        }
                    ],
                    "Next": "CommitMetadata",
                },
                "CommitMetadata": {
                    "Type": "Task",
                    "Resource": "arn:aws:states:::lambda:invoke",
                    "Parameters": {
                        "FunctionName": "${CatalogCommitArn}",
                        "Payload.$": "$",
                    },
                    "End": True,
                },
            },
        },
        indent=2,
    )


def _emit_consumer_sla_yaml(contract: MeshPipelineContract) -> str:
    if contract.consumer_slas:
        blocks = []
        for sla in contract.consumer_slas:
            cols = "\n".join(f"  - {c}" for c in sla.required_columns) or "  - id"
            blocks.append(
                f"""consumer_id: {sla.consumer_id}
target_table: {sla.target_table}
max_freshness_minutes: {sla.max_freshness_minutes}
min_completeness_pct: {sla.min_completeness_pct}
required_columns:
{cols}
enforcement: {sla.enforcement}
"""
            )
        return "\n---\n".join(blocks)
    cols = "\n".join(f"  - {c}" for c in contract.workload.content_fields)
    return f"""consumer_id: analytics-team
target_table: {contract.boundary.target_table}
max_freshness_minutes: 60
min_completeness_pct: 99.9
required_columns:
{cols}
enforcement: vrp_backed
"""


def _emit_terraform_main(contract: MeshPipelineContract) -> str:
    schedules = _schedule_triggers(contract)
    schedule_note = ""
    if schedules:
        schedule_note = "\n# EventBridge schedule: see eventbridge.tf"
    return f"""# GENERATED producer Terraform for domain: {contract.domain_id}
variable "producer_account_id" {{
  default = "{contract.accounts.producer}"
}}

variable "domain_id" {{
  default = "{contract.domain_id}"
}}

variable "name_prefix" {{
  default = "{contract.name_prefix or f'sdm-{contract.domain_id}'}"
}}

variable "aws_region" {{
  default = "{contract.aws_region}"
}}

# Wire modules from infrastructure/terraform/environments/multi-account/producer/
# Monitoring: add "{contract.domain_id}" to trust_dashboard_domains in monitoring module
{schedule_note}
"""


def _emit_eventbridge_tf(contract: MeshPipelineContract) -> str | None:
    schedules = _schedule_triggers(contract)
    if not schedules:
        return None
    trigger = schedules[0]
    return f'''resource "aws_cloudwatch_event_rule" "{contract.domain_id}_schedule" {{
  name                = "${{var.name_prefix}}-{contract.domain_id}-schedule"
  description         = "PVDM pipeline schedule for {contract.product_id}"
  schedule_expression = "cron({trigger.cron})"
}}

resource "aws_cloudwatch_event_target" "{contract.domain_id}_step_function" {{
  rule      = aws_cloudwatch_event_rule.{contract.domain_id}_schedule.name
  target_id = "pvdm-{contract.domain_id}"
  arn       = aws_sfn_state_machine.domain_writer.arn
  role_arn  = aws_iam_role.eventbridge_sfn.arn

  input = jsonencode({{
    workload_id     = "{contract.product_id}-${{formatdate("YYYYMMDD", timestamp())}}"
    total_records   = 1000000
    domain_id       = "{contract.domain_id}"
    target_table    = "{contract.boundary.target_table}"
    source_namespace = "{contract.boundary.source_namespace}"
    partition_spec  = {{ "{contract.boundary.partition_key}" = "REPLACE_AT_RUNTIME" }}
  }})
}}
'''


def _emit_tfvars(contract: MeshPipelineContract) -> str:
    lines = [
        f'aws_region = "{contract.aws_region}"',
        f'name_prefix = "{contract.name_prefix or f"sdm-{contract.domain_id}"}"',
        f'producer_account_id = "{contract.accounts.producer}"',
    ]
    if contract.accounts.steward:
        lines.append(f'steward_account_id = "{contract.accounts.steward}"')
    if contract.accounts.publisher:
        lines.append(f'publisher_account_id = "{contract.accounts.publisher}"')
    return "\n".join(lines) + "\n"


def _emit_test(contract: MeshPipelineContract) -> str:
    pk = contract.boundary.partition_key
    return f'''"""GENERATED tests for {contract.domain_id} metadata pipeline."""

from __future__ import annotations

from pipeline_config import CONTRACT
from serverless_data_mesh.compile.contract import MeshPipelineContract
from serverless_data_mesh.compile.runtime import build_workload_from_contract


def test_contract_parses() -> None:
    parsed = MeshPipelineContract.from_dict(CONTRACT)
    assert parsed.domain_id == "{contract.domain_id}"
    assert parsed.boundary.target_table == "{contract.boundary.target_table}"


def test_workload_from_contract() -> None:
    parsed = MeshPipelineContract.from_dict(CONTRACT)
    workload = build_workload_from_contract(
        {{
            "workload_id": "test-001",
            "total_records": 100,
            "partition_spec": {{"{pk}": "2026-06-14"}},
        }},
        parsed,
    )
    assert workload.boundary.domain_id == "{contract.domain_id}"
    assert workload.identity_fields == {contract.workload.identity_fields!r}
'''


def _emit_readme(contract: MeshPipelineContract) -> str:
    return f"""# {contract.domain_id} — metadata-driven PVDM pipeline

**Product:** `{contract.product_id}` · **Table:** `{contract.boundary.target_table}`

Generated by:

```bash
serverless-data-mesh compile --contract mesh.pipeline.yaml --output domains/
```

## Edit (domain team)

1. **`readers.py`** — implement `source_reader`, `sink_reader`, `batch_writer`
2. **`terraform/`** — wire producer modules and deploy
3. Re-run compile after changing `mesh.pipeline.yaml` (do not hand-edit generated files)

## Generated artifacts

| File | Purpose |
|------|---------|
| `mesh.pipeline.yaml` | Source-of-truth contract |
| `pipeline_config.py` | Frozen contract for runtime |
| `handler.py` | Durable Lambda entry |
| `step_function.asl.json` | Step Functions ASL |
| `consumer_sla.yaml` | Lake Formation read gates |
| `terraform/` | IaC stubs + schedule |

## Run locally

```bash
pytest tests/
serverless-data-mesh demo
```
"""


def compile_pipeline(
    contract: MeshPipelineContract,
    *,
    output_dir: str | Path = "domains",
    relative_root: str | None = None,
    write_canonical_contract: bool = True,
) -> CompileResult:
    """Generate a full PVDM pipeline directory from contract metadata."""
    root = Path(output_dir) / (relative_root or contract.output_domain_dir)
    root.mkdir(parents=True, exist_ok=True)
    (root / "tests").mkdir(exist_ok=True)
    (root / "terraform").mkdir(exist_ok=True)

    written: list[str] = []

    def write(rel: str, content: str) -> None:
        path = root / rel
        path.write_text(content, encoding="utf-8")
        written.append(rel)

    if write_canonical_contract:
        write("mesh.pipeline.yaml", _yaml_dump(contract.to_dict()))

    write("pipeline_config.py", _emit_pipeline_config(contract))
    write("readers.py", _emit_readers_py(contract))
    write("handler.py", _emit_handler(contract))
    write("step_function.asl.json", _emit_step_function(contract))
    write("consumer_sla.yaml", _emit_consumer_sla_yaml(contract))
    write("terraform/main.tf", _emit_terraform_main(contract))
    write("terraform/lambda.tf", _emit_lambda_tf(contract))
    write("terraform/terraform.tfvars.example", _emit_tfvars(contract))
    eb = _emit_eventbridge_tf(contract)
    if eb:
        write("terraform/eventbridge.tf", eb)
    write(f"tests/test_{contract.domain_id}_pipeline.py", _emit_test(contract))
    write("README.md", _emit_readme(contract))

    manifest = {
        "generator": "serverless-data-mesh compile",
        "api_version": contract.api_version,
        "domain_id": contract.domain_id,
        "product_id": contract.product_id,
        "lambda_handler": "handler.lambda_handler",
        "package_env": {
            "SDM_PIPELINE_SRC": "<path-to-this-directory>",
            "SDM_EXTRAS": contract.runtime.package_extras or "",
        },
        "files": written,
    }
    write("pipeline.manifest.json", json.dumps(manifest, indent=2))

    contract_path = root / "mesh.pipeline.yaml"
    return CompileResult(
        output_root=root.resolve(),
        contract_path=contract_path.resolve(),
        files_written=tuple(written),
    )
