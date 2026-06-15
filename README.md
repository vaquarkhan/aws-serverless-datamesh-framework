# Serverless Data Mesh

<p align="center">
  <img src="docs/images/serverless-data-mesh-hero.png" alt="Serverless Data Mesh — exactly-once lakehouse writes on AWS Lambda" width="900" />
</p>

**A new open framework for governed, exactly-once lakehouse writes on AWS Lambda.**

Serverless Data Mesh coordinates **cross-domain data products** across a federated mesh: domain teams **produce** data, platform stewards **verify and govern** it, and a publish zone **exposes** curated Iceberg tables to the organization—with cryptographic proofs, not just logs.

Combines [IceGuard](https://pypi.org/project/iceguard/), [veridata-recon](https://pypi.org/project/veridata-recon/), [AWS Durable Execution](https://docs.aws.amazon.com/durable-execution/), and [PyIceberg Glue REST](https://py.iceberg.apache.org/) into one transaction boundary for the world's data mesh teams.

---

## Why this framework exists

| Problem | Serverless Data Mesh answer |
|---------|----------------------------|
| Domain teams need autonomy | Each domain ships a small Lambda handler |
| Consumers need trust | veridata-recon VRP proof per chunk |
| Lambda times out at 15 min | Durable Execution + Step Functions resume (90+ min) |
| Silent data loss on backfill | `validate_then_commit` blocks metadata on FAIL |
| Federated AWS accounts | Producer · Steward · Publisher separation |
| Tunable Lambda timeouts | Terraform `lambda_timeout_seconds` + derived SFN/rollback |

**[Framework concepts & patterns →](docs/data-mesh-patterns.md)** · **[Full end-to-end guide →](docs/data-mesh-end-to-end.md)**

---

## Three-account data mesh

Production federated meshes use **three AWS accounts** with clear ownership:

<p align="center">
  <img src="docs/images/three-account-data-mesh.png" alt="Producer, Steward, and Publisher accounts in a federated data mesh" width="900" />
</p>

| Account | Owner | Responsibility |
|---------|-------|----------------|
| **Producer** | Domain team (Orders, Payments, …) | Source data, Step Functions, domain writer Lambda |
| **Steward** | Platform / governance | Glue catalog, Lake Formation, checkpoints, VRP proofs |
| **Publisher** | Analytics / data products | Curated lakehouse S3, Iceberg tables, consumer access |

**Flow:** Producer Lambda reads source → writes Parquet to Publisher → stores proofs in Steward → commits metadata via Steward Glue REST → consumers query Publisher.

Details, IAM, and deploy order: **[docs/data-mesh-end-to-end.md](docs/data-mesh-end-to-end.md)**

---

## How Lambda runs the mesh

<p align="center">
  <img src="docs/images/lambda-execution-flow.png" alt="Lambda durable execution flow — IceGuard, VRP, Durable SDK, Glue REST" width="900" />
</p>

**Compute on Lambda. Catalog via Glue connector. No Glue ETL jobs.**

| Layer | Runs on Lambda? | Component |
|-------|-----------------|-----------|
| Physical transforms | Yes | PySpark-on-Lambda, Polars, PyArrow |
| AWS Glue ETL jobs | **No** | Not used — separate managed service |
| Glue Data Catalog metadata | API only | `GlueCatalogConnector` (HTTPS + SigV4) |

See **[Glue Catalog Connector guide](docs/glue-connector.md)** for diagrams and Spark wiring.

Each domain writer is an AWS Lambda function (Python 3.12+) with **Durable Execution** enabled:

```
Event / Step Functions
        │
        ▼
Lambda :live  (15-min segments, up to 90+ min total)
        │
        ├── Spark / Polars    → physical Parquet writes (NOT Glue ETL)
        ├── IceGuard        → chunked writes + S3 checkpoints + rollback
        ├── veridata-recon  → VRP proof per chunk
        ├── Durable SDK     → replay completed steps on resume
        └── GlueCatalogConnector → Glue Iceberg REST metadata commit (2PC)
        │
        ▼
   committed | rolled_back → resume | verification_failed
```

| Package | Role |
|---------|------|
| **iceguard** | Timeout watchdog, S3 checkpoint resume, orphan cleanup |
| **veridata-recon** | Rust-backed VRP proofs (`pip install veridata-recon`) |
| **aws-durable-execution-sdk-python** | Checkpoint/replay beyond Lambda's 15-minute ceiling |
| **pyiceberg[glue,rest-sigv4]** | Glue Catalog Connector — metadata over REST (not Glue ETL) |
| **[sparkrules](https://pypi.org/project/sparkrules/)** | Optional `[rules]` — DRL business rules on Lambda |

---

## Quick start

**Requires Python 3.12+**

```bash
make install
# with SparkRules rules engine:
pip install -e ".[rules,dev]"
make test
```

### PyPI

```bash
pip install serverless-data-mesh
pip install "serverless-data-mesh[rules]"   # + SparkRules on Lambda
pip install "serverless-data-mesh[spark]"   # + PySpark + SparkRules
```

See **[PyPI guide](docs/pypi.md)** for publishing and Lambda packaging.

### Consumer safety benchmark

Quantitative proof that **corrupt data never reaches consumers** (metadata commit blocked):

```bash
make benchmark
```

Runs drop, mutation, and duplicate attack scenarios — all must return VRP `FAIL`.

### Governance

| Artifact | Purpose |
|----------|---------|
| `VERSION` | Single source of truth (synced to PyPI package) |
| `.pre-commit-config.yaml` | Ruff + version check hooks |
| `.github/dependabot.yml` | Automated dependency PRs |
| `SECURITY.md` | Vulnerability reporting |
| `eval/validate_then_commit_benchmark.py` | Trust boundary metrics |

```bash
make walkthrough      # 12-step local tutorial (no AWS)
make version-check
make pre-commit
```

```python
from serverless_data_mesh import (
    IceGuardDurableCoordinator,
    GlueCatalogConnector,
    SparkRulesConnector,       # pip install serverless-data-mesh[rules]
    DataProductContract,
    DomainTransactionBoundary,
    VRPProofGenerator,
    DataWriteWorkload,
)
```

Run the interactive tutorial:

```bash
python examples/tutorials/walkthrough.py
```

---

## Project layout

```
serverless-data-mesh/
├── docs/
│   ├── data-mesh-end-to-end.md  # ★ Full Producer/Steward/Publisher guide
│   ├── data-mesh-patterns.md    # ★ Concepts, coverage matrix, named patterns
│   ├── sparkrules-connector.md # SparkRules DRL on Lambda
│   ├── pypi.md                  # PyPI install & publish
│   ├── data-mesh-end-to-end.md  # Producer / Steward / Publisher guide
│   ├── getting-started.md       # Step-by-step developer tutorial
│   ├── architecture.md          # Components + 90-min execution model
│   ├── terraform-guide.md       # Production Terraform walkthrough
│   ├── deployment.md            # Lambda / IAM / env vars
│   ├── domain-contracts.md      # Event schema + boundary contracts
│   └── images/                  # Product & architecture diagrams
├── examples/
│   ├── tutorials/               # Runnable walkthrough
│   └── domain_writer/           # Reference Lambda handler
├── infrastructure/
│   ├── terraform/               # Step Functions + Durable Lambda + alarms
│   └── sam/                     # AWS SAM alternative
├── src/serverless_data_mesh/    # Library source
└── tests/
```

---

## Deploy

| Path | Use when |
|------|----------|
| **[Terraform (production)](infrastructure/terraform/README.md)** | Step Functions orchestrator, DLQ, monitoring |
| [SAM alternative](infrastructure/sam/README.md) | SAM-native teams |
| [Deployment guide](docs/deployment.md) | Manual Lambda / IAM setup |

```bash
./infrastructure/terraform/scripts/package_lambda.sh
cd infrastructure/terraform/environments/prod
terraform init && terraform apply
```

---

## Documentation

| Document | Audience |
|----------|----------|
| **[Data mesh patterns & concepts](docs/data-mesh-patterns.md)** | Coverage matrix, 12 patterns, roadmap |
| **[SparkRules connector](docs/sparkrules-connector.md)** | DRL business rules on Lambda (`[rules]` extra) |
| **[PyPI install & publish](docs/pypi.md)** | pip install, Lambda zip, maintainer publish |
| **[Data mesh end-to-end](docs/data-mesh-end-to-end.md)** | Architects, platform leads, auditors |
| [Developer getting started](docs/getting-started.md) | Domain engineers (13-step tutorial) |
| [Architecture](docs/architecture.md) | Component design + long-running Lambda |
| [Terraform step-by-step](docs/terraform-guide.md) | Infrastructure engineers |
| [Domain contracts](docs/domain-contracts.md) | Event schema + boundaries |
| [Interactive walkthrough](examples/tutorials/walkthrough.py) | Hands-on local demo |

---

## Transaction boundary (four phases)

1. **Physical** — IceGuard chunks Parquet writes with S3 checkpoints
2. **Verify** — veridata-recon proof per chunk; FAIL blocks commit
3. **Durable** — AWS Durable Execution replays completed steps on resume
4. **Metadata** — `GlueCatalogConnector` → Glue Iceberg REST 2PC via SigV4 (not Glue ETL)

---

## License

Apache-2.0 — see [LICENSE](LICENSE).
