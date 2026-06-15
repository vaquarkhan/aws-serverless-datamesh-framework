# Serverless Data Mesh

**Federated data mesh lakehouse publication on AWS Lambda - with cryptographic proof, not just green job logs.**

An open Python framework for **domain-oriented**, **federated data mesh** teams on AWS. Implements **data as a product**, **self-serve write infrastructure**, and **federated computational governance** at the Iceberg lakehouse layer.

- **Producer** domains publish governed **data products**
- **Steward** notaries enforce mesh contracts with VRP proofs
- **Publisher** zones expose consumer-ready **Iceberg data products**

Introduces the **[Vaquar Pattern](https://github.com/vaquarkhan/aws-serverless-datamesh-framework/blob/main/docs/vaquar-pattern.md)** (PVDM): Physical → Verify → Durable → Metadata. Invariant: `commit_metadata ⟹ VRP = PASS`.

## Install

```bash
pip install serverless-data-mesh
serverless-data-mesh demo    # <60s local PVDM demo, no AWS
serverless-data-mesh new --template medallion --output my-mesh
serverless-data-mesh apply --contract my-mesh/mesh.yaml --output my-mesh/generated
pip install "serverless-data-mesh[rules]"   # + SparkRules on Lambda
pip install "serverless-data-mesh[spark]"   # + PySpark + SparkRules
pip install "serverless-data-mesh[all]"     # rules + spark
pip install "serverless-data-mesh[dev]"     # pytest, ruff, pre-commit
```

**Works on **Windows, Mac, and Linux**. Uses veridata-recon cryptographic VRP when wheels are available; **pure-Python fallback** otherwise (same PASS/FAIL gate).**

## What it solves

| Problem | Answer |
|---------|--------|
| Silent data loss on backfill | VRP `FAIL` blocks Iceberg snapshot |
| "Job succeeded" is not proof | Cryptographic multiset proof per chunk |
| Lambda 15-minute limit | Durable Execution + Step Functions (90+ min) |
| Retry duplicates data | IceGuard rollback + `workload_id` checkpoints |
| Central ETL bottleneck | Per-domain Lambda writer + transaction boundary |
| Federated blast radius | Producer · Steward · Publisher accounts |

## Building blocks

| Package | Role |
|---------|------|
| [iceguard](https://pypi.org/project/iceguard/) | Physical SafeWriter, timeout rollback, S3 resume |
| [veridata-recon](https://pypi.org/project/veridata-recon/) | VRP proof generation and validation |
| [aws-durable-execution-sdk-python](https://pypi.org/project/aws-durable-execution-sdk-python/) | Cross-invocation step replay |
| [pyiceberg](https://pypi.org/project/pyiceberg/) | Glue Iceberg REST metadata via `GlueCatalogConnector` |
| [sparkrules](https://pypi.org/project/sparkrules/) | Optional DRL business rules (`[rules]` extra) |

## Quick example

```python
from serverless_data_mesh import (
    IceGuardDurableCoordinator,
    DomainTransactionBoundary,
    VRPProofGenerator,
)

boundary = DomainTransactionBoundary(
    domain_id="orders-domain",
    source_namespace="raw_orders",
    target_table="orders_curated",
    partition_spec={"dt": "2026-06-14"},
)

coordinator = IceGuardDurableCoordinator(
    durable_context=durable_ctx,
    lambda_context=lambda_ctx,
    proof_generator=VRPProofGenerator(),
    catalog_adapter=glue_adapter,
)
outcome = coordinator.run_workload(workload)
```

## Optional extras

| Extra | Adds |
|-------|------|
| `rules` | SparkRules DRL on Lambda |
| `spark` | PySpark + SparkRules |
| `all` | `rules` + `spark` |
| `dev` | pytest, ruff, mypy, pre-commit |
| `publish` | build, twine |

## Documentation

- [GitHub README](https://github.com/vaquarkhan/aws-serverless-datamesh-framework#readme)
- [Vaquar Pattern](https://github.com/vaquarkhan/aws-serverless-datamesh-framework/blob/main/docs/vaquar-pattern.md)
- [Getting started](https://github.com/vaquarkhan/aws-serverless-datamesh-framework/blob/main/docs/getting-started.md)
- [PyPI guide](https://github.com/vaquarkhan/aws-serverless-datamesh-framework/blob/main/docs/pypi.md)
- [Full documentation](https://github.com/vaquarkhan/aws-serverless-datamesh-framework/tree/main/docs)

## License

Apache-2.0
