# Developer Getting Started: Step by Step

This guide walks you through building a **domain lakehouse writer** with serverless-data-mesh.
Each step explains **what it is** and **what we are trying to achieve** before showing code.

**Prerequisites:** Python 3.12+, AWS account (for deployment), basic familiarity with Iceberg and Lambda.

---

## Step 1: Install the framework

### What is this?

The Python library and its four runtime dependencies: IceGuard, veridata-recon, AWS Durable Execution SDK, and PyIceberg (Glue REST).

### What we try to achieve

A reproducible local dev environment where you can import `serverless_data_mesh`, run tests, and iterate on your domain handler before deploying to Lambda.

### Commands

```bash
git clone <your-repo-url> serverless-data-mesh
cd serverless-data-mesh

python3.12 -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate

make install                       # pip install -e ".[dev]" + veridata-recon
make test                          # verify your environment
```

### Verify the install

```python
import serverless_data_mesh as sdm

print(sdm.__version__)  # 0.1.0
```

---

## Step 2: Declare your domain transaction boundary

### What is this?

A `DomainTransactionBoundary` is the **contract** your domain publishes to the data mesh. It scopes *which* table, *which* partition, and *which* quality policy apply to this write.

### What we try to achieve

Make cross-domain coordination explicit: other teams and auditors know exactly what data scope you own and what guarantees you enforce (zero drops, zero mutations, etc.).

### Code

```python
from serverless_data_mesh import DomainTransactionBoundary

boundary = DomainTransactionBoundary(
    domain_id="orders-domain",           # your mesh domain identifier
    source_namespace="raw_orders",       # Glue database
    target_table="orders_curated",       # Glue Iceberg table
    partition_spec={"dt": "2026-06-14"}, # partition you are materializing
    quality_policy_id="strict-zero-drop",
    max_chunk_records=5000,              # max records per IceGuard chunk
)
```

**Key idea:** The boundary is not optional metadata: the coordinator refuses to commit metadata outside this declared scope.

---

## Step 3: Describe the workload (backfill / copy job)

### What is this?

A `DataWriteWorkload` describes a single long-running job: how many records, where source and target live, and which S3 buckets store checkpoints and proofs.

### What we try to achieve

Give the orchestrator everything it needs to shard work into resumable chunks and to tag VRP proofs with stable `source_ref` / `sink_ref` locators.

### Code

```python
from serverless_data_mesh import DataWriteWorkload

workload = DataWriteWorkload(
    workload_id="backfill-2026q2-orders",   # idempotency key for the whole job
    boundary=boundary,
    source_uri="s3://source-domain/orders/",
    target_uri="s3://lakehouse-domain/orders_curated/",
    total_records=250_000,
    checkpoint_bucket="my-iceguard-checkpoints",
    proof_bucket="my-vrp-proofs",
    content_fields=("id", "payload_hash"),    # fields hashed by veridata-recon
    identity_fields=("id",),                  # record identity for reconciliation
)
```

### Lambda event equivalent

When deployed, the same structure arrives as JSON:

```json
{
  "workload_id": "backfill-2026q2-orders",
  "total_records": 250000,
  "domain_id": "orders-domain",
  "source_uri": "s3://source-domain/orders/",
  "target_uri": "s3://lakehouse-domain/orders_curated/",
  "partition_spec": {"dt": "2026-06-14"}
}
```

---

## Step 4: Implement your source reader

### What is this?

A `source_reader(start, end)` callable that returns the **logical records** for offsets `[start, end)`. The framework uses these records only for VRP fingerprinting: not for the physical Parquet write.

### What we try to achieve

Produce a deterministic, hashable view of the source payload so veridata-recon can cryptographically prove the sink matches the source: without exposing raw PII in the proof.

### Code (replace the demo stub)

```python
from typing import Any

def source_reader(start: int, end: int) -> list[dict[str, Any]]:
    """
    Read source records for [start, end).

    Production: query Kafka offsets, read staging Parquet, or call your CDC API.
    Return dicts with string-coercible values matching content_fields / identity_fields.
    """
    records = []
    for offset in range(start, end):
        records.append({
            "id": str(offset),
            "payload_hash": "<sha256 of canonical row bytes>",
        })
    return records
```

**Rule:** Field values must be coercible to strings: veridata-recon canonicalizes strings for hashing.

---

## Step 5: Implement your Parquet batch writer

### What is this?

A `batch_writer(start, end)` callable that **materializes** records `[start, end)` into Parquet files on S3 and returns their URIs. This is the physical write IceGuard protects.

### What we try to achieve

Decouple *how* you write Parquet (PySpark on Lambda, Polars, DuckDB, etc.) from *how* the framework coordinates rollback, checkpoints, and metadata commit.

### Code (replace the demo stub)

```python
def batch_writer(start: int, end: int) -> list[str]:
    """
    Write Parquet for [start, end) and return S3 URIs.

    Production: invoke Spark-on-AWS-Lambda, write via PyIceberg, etc.
    IceGuard tracks returned paths for rollback if Lambda times out.
    """
    base = "s3://lakehouse-domain/orders_curated/dt=2026-06-14"
    return [f"{base}/part-{offset:08d}.parquet" for offset in range(start, end)]
```

**Important:** Use `iceguard.protect()` via the coordinator: a bare `df.write.save()` inside the Lambda is **not** protected against the commit-durability gap.

---

## Step 6: Configure runtime settings

### What is this?

`MeshSettings` loads operational knobs from environment variables: checkpoint bucket, proof bucket, chunk interval, and rollback threshold.

### What we try to achieve

Keep domain handler code free of hard-coded infrastructure names so the same code runs in dev, staging, and prod via env vars or SAM/CDK parameters.

### Code

```python
import os
from serverless_data_mesh import MeshSettings

# Required before calling MeshSettings.from_environment():
os.environ["ICEGUARD_CHECKPOINT_BUCKET"] = "my-iceguard-checkpoints"
os.environ["VRP_PROOF_BUCKET"] = "my-vrp-proofs"
os.environ["ICEBERG_TABLE_BUCKET"] = "my-lakehouse-bucket"
os.environ["AWS_REGION"] = "us-east-1"

settings = MeshSettings.from_environment()
print(settings.checkpoint_interval)       # 5000
print(settings.rollback_threshold_ms)     # 30000
```

| Variable | Purpose |
|----------|---------|
| `ICEGUARD_CHECKPOINT_BUCKET` | S3 resume checkpoints (required) |
| `VRP_PROOF_BUCKET` | Signed reconciliation proofs per chunk |
| `ICEBERG_TABLE_BUCKET` | Glue/S3 Tables warehouse bucket |
| `ICEGUARD_CHECKPOINT_INTERVAL` | Records per physical chunk |
| `ICEGUARD_ROLLBACK_THRESHOLD_MS` | Watchdog fires rollback this many ms before timeout |

---

## Step 7: Add cryptographic verification (VRP)

### What is this?

`VRPProofGenerator` uses **veridata-recon** to fingerprint source and sink record sets per chunk and produce a tamper-evident proof. `validate_then_commit()` gates the metadata commit on a `PASS` verdict.

### What we try to achieve

Enforce **validate-then-commit**: bad data never receives an Iceberg snapshot. Auditors can verify proofs offline with only the public key: no access to raw data required.

### Code

```python
from serverless_data_mesh import VRPProofGenerator, validate_then_commit

proofs = VRPProofGenerator.from_env()   # or set VRP_SIGNING_KEY_B64 for stable keys

source = [{"id": "1", "payload_hash": "abc"}, {"id": "2", "payload_hash": "def"}]
sink   = source.copy()                  # after a successful physical write, sink mirrors source

proof = proofs.build_proof(
    source_records=source,
    sink_records=sink,
    workload=workload,
    chunk_start=0,
    chunk_end=2,
)

result = validate_then_commit(proof)
assert result.outcome == "PASS"         # only then may metadata commit proceed

# Persist proof alongside Parquet (done automatically by the coordinator):
uri = proofs.persist_proof(
    proof,
    bucket=workload.proof_bucket,
    key_prefix=f"{workload.boundary.domain_id}/{workload.workload_id}",
    chunk_index=0,
)
print(uri)  # s3://my-vrp-proofs/orders-domain/backfill-.../proofs/chunk-000000.vrp.json
```

---

## Step 8: Connect the Glue Catalog Connector

### What is this?

`GlueCatalogConnector` (alias: `GlueRestCatalogAdapter`) commits Iceberg metadata over **HTTPS + SigV4** via the AWS Glue Iceberg REST endpoint.

**Important:** This is **not** an AWS Glue ETL job. Glue ETL jobs cannot run inside Lambda. Physical Parquet writes use **Spark-on-Lambda**, Polars, or PyArrow in your `batch_writer`; the connector only registers file paths in the Glue Data Catalog.

See **[glue-connector.md](glue-connector.md)** for full mermaid diagrams.

### What we try to achieve

Complete the two-phase commit (2PC): Phase 1 stages Parquet paths from Spark/PyArrow; Phase 2 publishes a new snapshot only after VRP passes. On failure, `abort()` leaves catalog state unchanged.

### Code

```python
from serverless_data_mesh import GlueCatalogConnector

connector = GlueCatalogConnector.from_environment(
    namespace=workload.boundary.source_namespace,
    table_name=workload.boundary.target_table,
)

connector.connect()  # SigV4 auth + load_table via PyIceberg REST

parquet_paths = [
    "s3://lakehouse/orders_curated/dt=2026-06-14/part-00000000.parquet",
]

connector.prepare_commit(parquet_paths)   # Phase 1: stage files
snapshot_id = connector.commit()          # Phase 2: publish snapshot
print(f"Committed snapshot {snapshot_id}")
```

---

## Step 9: Compose the durable coordinator

### What is this?

`IceGuardDurableCoordinator` is the **central coordinator**. It chains IceGuard physical writes, VRP verification, AWS Durable Execution steps, and the Glue REST commit into one governed pipeline.

### What we try to achieve

Run 90+ minute backfills on Lambda without duplicating data: each verified chunk is a durable step; timeouts trigger IceGuard rollback; the next invocation resumes from the last checkpoint.

### Code (local simulation: no Lambda required)

```python
from unittest.mock import MagicMock
from serverless_data_mesh import IceGuardDurableCoordinator, VRPProofGenerator, GlueCatalogConnector

# In production, `context` is DurableContext from @durable_execution.
# For local exploration, mock the interfaces your writer needs.
mock_context = MagicMock()
mock_context.get_remaining_time_in_millis.return_value = 900_000

coordinator = IceGuardDurableCoordinator(
    durable_context=mock_context,
    lambda_context=mock_context,
    proof_generator=VRPProofGenerator.from_env(),
    catalog_adapter=catalog,
    checkpoint_interval=settings.checkpoint_interval,
    rollback_threshold_ms=settings.rollback_threshold_ms,
)

# In production, pass your real batch_writer and source_reader callables.
# result = coordinator.execute_workload(workload, batch_writer=..., source_reader=...)
```

### What happens inside `execute_workload`

```
for each chunk [start, end):
  1. IceGuard writes Parquet        → physical files on S3
  2. veridata-recon builds proof    → validate_then_commit()
  3. durable_write_chunk step       → checkpointed (skipped on replay)
after all chunks:
  4. durable_commit_metadata step   → Glue REST snapshot commit
```

---

## Step 10: Wire the Lambda handler

### What is this?

The `@durable_execution` handler is the **domain team entry point**. It maps the inbound event to a workload and delegates to the coordinator.

### What we try to achieve

Give each domain a thin, auditable handler (~50 lines) that composes framework components without reimplementing rollback, proof, or catalog logic.

### Reference implementation

See `examples/domain_writer/handler.py`:

```python
from aws_durable_execution_sdk_python import DurableContext, durable_execution
from serverless_data_mesh import (
    GlueCatalogConnector,
    IceGuardDurableCoordinator,
    MeshSettings,
    VRPProofGenerator,
)
from examples.domain_writer.workload import build_workload
from examples.domain_writer.io import records_from_source, write_parquet_chunk

@durable_execution
def handler(event: dict, context: DurableContext) -> dict:
    settings = MeshSettings.from_environment()
    workload = build_workload(event, settings)

    coordinator = IceGuardDurableCoordinator(
        durable_context=context,
        lambda_context=context,
        proof_generator=VRPProofGenerator.from_env(),
        catalog_adapter=GlueCatalogConnector.from_environment(
            namespace=workload.boundary.source_namespace,
            table_name=workload.boundary.target_table,
        ),
        checkpoint_interval=settings.checkpoint_interval,
        rollback_threshold_ms=settings.rollback_threshold_ms,
    )

    return coordinator.execute_workload(
        workload,
        batch_writer=lambda s, e: write_parquet_chunk(workload.target_uri, s, e),
        source_reader=lambda s, e: records_from_source(workload.source_uri, s, e),
    )

lambda_handler = handler
```

**Replace** `records_from_source` and `write_parquet_chunk` in `examples/domain_writer/io.py` with your production I/O.

---

## Step 11: Deploy to AWS (Terraform recommended)

### What is this?

Production infrastructure-as-code: S3 buckets, IAM, Lambda Durable Function, Step Functions backfill orchestrator, EventBridge schedule, CloudWatch alarms, and SQS DLQ.

### What we try to achieve

A deployable production stack you can `terraform apply` directly: with a Step Functions resume loop that re-invokes the domain writer after IceGuard `rolled_back` outcomes.

### Terraform (recommended)

```bash
# 1. Build Lambda zip
./infrastructure/terraform/scripts/package_lambda.sh   # or package_lambda.ps1 on Windows

# 2. Configure
cd infrastructure/terraform/environments/prod
cp terraform.tfvars.example terraform.tfvars
# Edit globally-unique bucket names

# 3. Deploy
terraform init
terraform apply

# 4. Start backfill via Step Functions
aws stepfunctions start-execution \
  --state-machine-arn "$(terraform output -raw step_functions_arn)" \
  --input "$(terraform output -json example_stepfunctions_input)"
```

Full reference: [infrastructure/terraform/README.md](../infrastructure/terraform/README.md)

### SAM (alternative)

---

## Step 12: Invoke and interpret outcomes

### What is this?

The JSON response from your handler describing the terminal state of the domain write transaction.

### What we try to achieve

Give operators a clear signal: success, verification failure, or rollback-with-resume: without guessing from CloudWatch exit codes alone.

### Invoke

```bash
aws lambda invoke \
  --function-name <stack-name>-domain-writer \
  --payload '{"workload_id":"backfill-2026q2-orders","total_records":250000}' \
  response.json

cat response.json
```

### Response outcomes

| `outcome` | Meaning | Action |
|-----------|---------|--------|
| `committed` | All chunks verified; snapshot published | Done |
| `resumed` | Continued from a prior durable checkpoint | Normal for long jobs |
| `verification_failed` | VRP blocked a chunk | Fix source/sink mismatch; re-invoke |
| `rolled_back` | IceGuard rolled back near-timeout Parquet | Re-invoke: durable steps resume without duplicating committed chunks |

Example success:

```json
{
  "outcome": "committed",
  "workload_id": "backfill-2026q2-orders",
  "records_written": 250000,
  "chunks": 50,
  "snapshot_id": 12345678901234,
  "proof_chain_tail": "a1b2c3..."
}
```

---

## Step 13: Verify proofs offline (audit trail)

### What is this?

Independent verification of VRP proof files stored in S3: no AWS access required beyond downloading the `.vrp.json` file.

### What we try to achieve

Tamper-evident audit evidence for regulators, consuming domains, or CI gates that proves data completeness for each chunk boundary.

### Code

```python
import veridata_recon as vr

outcome = vr.verify_proof(
    "chunk-000000.vrp.json",
    public_key_b64="<your-public-key-b64>",
)
print(outcome)  # PASS | FAIL | UNVERIFIED
```

Proofs are stored at:

```
s3://{proof_bucket}/{domain_id}/{workload_id}/proofs/chunk-{NNNNNN}.vrp.json
```

---

## Quick reference: component map

| Step | Component | Package |
|------|-----------|---------|
| 2–3 | Domain contract + workload | `serverless_data_mesh.types` |
| 4–5 | Your I/O callbacks | Your code |
| 6 | Runtime config | `serverless_data_mesh.config` |
| 7 | VRP proofs | `veridata-recon` via `serverless_data_mesh.verification` |
| 8 | Metadata 2PC | `serverless_data_mesh.catalog` |
| 9–10 | Coordinator + handler | `serverless_data_mesh.orchestration` |
| Physical safety | Timeout rollback | `iceguard` |
| Long-running | Step replay | `aws-durable-execution-sdk-python` |

## Next steps

- [Architecture deep-dive](architecture.md)
- [Domain event schema](domain-contracts.md)
- [Full example](../examples/domain_writer/README.md)
- Run the interactive tutorial: `python examples/tutorials/walkthrough.py`
