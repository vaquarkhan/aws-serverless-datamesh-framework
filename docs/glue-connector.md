# Glue Catalog Connector: Lambda, Spark, and What Glue Does *Not* Do Here

Serverless Data Mesh separates **compute** (Lambda) from **catalog** (Glue Data Catalog).
This guide explains the **Glue Catalog Connector**, why **AWS Glue ETL jobs cannot run on Lambda**,
how **Spark on Lambda** fits the physical layer, and where mermaid diagrams map to production.

---

## Table of contents

1. [The core distinction](#1-the-core-distinction)
2. [Architecture: two planes](#2-architecture-two-planes)
3. [Glue Catalog Connector API](#3-glue-catalog-connector-api)
4. [Spark on Lambda (physical layer)](#4-spark-on-lambda-physical-layer)
5. [End-to-end sequence](#5-end-to-end-sequence)
6. [What runs in each AWS service](#6-what-runs-in-each-aws-service)
7. [Environment variables](#7-environment-variables)
8. [Multi-account Steward catalog](#8-multi-account-steward-catalog)
9. [Anti-patterns](#9-anti-patterns)
10. [Related docs](#10-related-docs)

---

## 1. The core distinction

| Capability | Runs on Lambda? | Used by this framework? |
|------------|-----------------|-------------------------|
| **PySpark / Spark-on-Lambda** (physical Parquet writes) | Yes (with JVM layer/container) | Yes: domain `batch_writer` |
| **Polars / PyArrow / DuckDB** (physical writes) | Yes | Yes: lighter alternative to Spark |
| **AWS Glue ETL job** (managed Spark runner) | **No** | **No**: separate service |
| **Glue Interactive Sessions** | **No** | **No** |
| **Glue Data Catalog** (table metadata) | N/A (API only) | **Yes**: via Glue Catalog Connector |
| **Glue Iceberg REST** (`add_files` 2PC) | N/A (HTTPS + SigV4) | **Yes**: metadata commit |

```mermaid
flowchart TB
    subgraph lambda [Lambda Domain Writer: COMPUTE]
        SPARK[PySpark / Polars / PyArrow]
        IG[IceGuard SafeWriter]
        VRP[veridata-recon VRP]
        DE[Durable Execution]
        SPARK --> IG
        IG --> VRP
    end

    subgraph glue_api [Glue Data Catalog: METADATA ONLY]
        REST[Glue Iceberg REST API]
        CAT[Table / Snapshot Registry]
        REST --> CAT
    end

    subgraph glue_etl [AWS Glue ETL Jobs: NOT USED HERE]
        JOB[Glue Job Runner]
        STUDIO[Glue Studio]
        JOB -.-x lambda
    end

    VRP -->|PASS| CONN[GlueCatalogConnector]
    DE --> CONN
    CONN -->|HTTPS SigV4| REST
    IG -->|Parquet files| S3[(Publisher S3)]
    CONN -->|register files| S3
```

**Key insight:** Glue in this framework means **catalog connector**, not **Glue job engine**.
You get Iceberg table registration in the Steward Glue catalog without ever starting a Glue ETL job.

---

## 2. Architecture: two planes

```mermaid
flowchart LR
    subgraph physical [Physical Plane: Lambda]
        direction TB
        READ[Read source chunk]
        TRANS[Transform / aggregate]
        WRITE[Write Parquet to S3]
        READ --> TRANS --> WRITE
    end

    subgraph metadata [Metadata Plane: Glue REST]
        direction TB
        PREP[prepare_commit paths]
        TX[Iceberg transaction]
        SNAP[Publish snapshot]
        PREP --> TX --> SNAP
    end

    subgraph verify [Verification Plane: Steward S3]
        PROOF[VRP proof JSON]
    end

    WRITE --> PROOF
    PROOF -->|validate_then_commit PASS| PREP
    WRITE -.->|file URIs| PREP
```

| Plane | Technology | Runs where |
|-------|------------|------------|
| Physical | Spark-on-Lambda, Polars, demo `io.py` | Lambda container |
| Verification | veridata-recon | Lambda container |
| Orchestration | IceGuard + Durable SDK + Step Functions | Lambda + AWS control plane |
| Metadata | `GlueCatalogConnector` (PyIceberg REST) | Lambda → HTTPS → Glue API |

---

## 3. Glue Catalog Connector API

The connector is `GlueCatalogConnector` (alias of `GlueRestCatalogAdapter`).

```python
from serverless_data_mesh import GlueCatalogConnector

connector = GlueCatalogConnector.from_environment(
    namespace="raw_orders",       # Glue database
    table_name="orders_curated",  # Iceberg table
)

# Phase 1: stage data file paths (already on S3 from Spark/PyArrow)
connector.prepare_commit(parquet_paths)

# Phase 2: publish snapshot (only after VRP PASS)
snapshot_id = connector.commit(snapshot_properties={"app-id": "orders-domain"})
```

### Connector internals

```mermaid
sequenceDiagram
    participant H as Lambda Handler
    participant C as GlueCatalogConnector
    participant P as PyIceberg REST client
    participant G as glue.{region}.amazonaws.com/iceberg
    participant LF as Lake Formation

    H->>C: prepare_commit([s3://.../part-0001.parquet])
    Note over C: Stage paths in memory (2PC phase 1)

    H->>C: commit() after VRP PASS
    C->>P: load_catalog(rest + sigv4)
    P->>G: SigV4 signed HTTPS
    G->>LF: Credential / access check
    G-->>P: Iceberg REST response
    P-->>C: snapshot_id
    C-->>H: committed metadata
```

### REST properties (automatic)

| Property | Value |
|----------|-------|
| `type` | `rest` |
| `uri` | `https://glue.{region}.amazonaws.com/iceberg` |
| `warehouse` | `{account_id}:s3tablescatalog/{bucket}` |
| `rest.sigv4-enabled` | `true` |
| `rest.signing-name` | `glue` |

No `spark.hadoop.*`, no Glue job `JobRunId`, no DPUs.

---

## 4. Spark on Lambda (physical layer)

Glue ETL cannot replace this: if you need Spark transforms, run **PySpark inside Lambda**
(or use Polars/PyArrow for smaller chunks).

```mermaid
flowchart TB
    subgraph handler [domain_writer.handler]
        COORD[IceGuardDurableCoordinator]
        BW["batch_writer(start, end)"]
        SR["source_reader(start, end)"]
        COORD --> BW
        COORD --> SR
    end

    subgraph spark_impl [Your domain code: pick one]
        DEMO[examples/domain_writer/io.py demo]
        SPARK[examples/domain_writer/spark_io.py]
        POLARS[Polars / PyArrow]
    end

    subgraph connector [Metadata: always framework]
        GCC[GlueCatalogConnector]
    end

    BW --> SPARK
    SR --> SPARK
    COORD --> GCC
```

### Wiring Spark into the handler

```python
from serverless_data_mesh import IceGuardDurableCoordinator, GlueCatalogConnector

# Inside handler: Spark session created once per cold start (domain code):
# spark = create_spark_session()  # JVM layer required

coordinator = IceGuardDurableCoordinator(
    durable_context=context,
    lambda_context=context,
    proof_generator=proofs,
    catalog_adapter=GlueCatalogConnector.from_environment(
        namespace=workload.boundary.source_namespace,
        table_name=workload.boundary.target_table,
    ),
)

result = coordinator.execute_workload(
    workload,
    batch_writer=lambda s, e: write_parquet_chunk_spark(spark, workload.target_uri, ...),
    source_reader=lambda s, e: records_from_source_spark(spark, workload.source_uri, s, e),
)
```

### Lambda packaging notes for Spark

| Approach | Pros | Cons |
|----------|------|------|
| **Lambda container image** | Full JVM + Spark control | Larger image, slower cold start |
| **Lambda layer (Spark)** | Zip deploy | Size limits, version pinning |
| **Polars / PyArrow** | Small package, fast cold start | Not full Spark SQL |

Install optional Spark deps:

```bash
pip install "serverless-data-mesh[spark]"
```

See `examples/domain_writer/spark_io.py` for the integration stub.

---

## 5. End-to-end sequence

One chunk, from Lambda through Glue catalog (no Glue job):

```mermaid
sequenceDiagram
    participant SFN as Step Functions
    participant L as Lambda
    participant Spark as PySpark / Polars
    participant S3 as Publisher S3
    participant VRP as veridata-recon
    participant CHK as Steward Checkpoints
    participant GCC as GlueCatalogConnector
    participant Glue as Glue Iceberg REST

    SFN->>L: Invoke workload
    L->>Spark: Read + transform chunk
    Spark->>S3: Write Parquet
    L->>VRP: build_proof(source, sink)
    VRP-->>L: PASS
    L->>CHK: IceGuard checkpoint
    L->>GCC: prepare_commit(paths)
    L->>GCC: commit()
    GCC->>Glue: add_files (SigV4 REST)
    Glue-->>GCC: snapshot_id
    L-->>SFN: outcome=committed
```

If IceGuard rolls back near 15 minutes, **Spark and connector split cleanly**:

- Spark may have written partial Parquet → IceGuard rolls back uncommitted files
- `GlueCatalogConnector.abort()`: no snapshot published
- Next segment resumes from S3 checkpoint: **no duplicate metadata**

---

## 6. What runs in each AWS service

```mermaid
flowchart TB
    subgraph producer [Producer Account]
        L[Lambda Domain Writer]
        SFN[Step Functions]
        SFN --> L
    end

    subgraph steward [Steward Account]
        GLUE[Glue Data Catalog API]
        CHK[Checkpoint S3]
        PRF[Proof S3]
    end

    subgraph publisher [Publisher Account]
        DATA[Lakehouse S3 Parquet]
    end

    subgraph consumers [Consumption: any compute]
        ATH[Athena]
        EMR[EMR / Glue ETL read]
        BI[BI tools]
    end

    L -->|Spark write| DATA
    L -->|GlueCatalogConnector| GLUE
    L --> CHK
    L --> PRF
    GLUE -.->|metadata pointer| DATA
    ATH --> DATA
    EMR --> DATA
    BI --> DATA
```

**Downstream Glue ETL jobs** may *read* curated tables for further aggregation: that is
normal consumption. The **domain writer** that lands the mesh product does **not** invoke them.

---

## 7. Environment variables

| Variable | Connector use |
|----------|-----------------|
| `AWS_REGION` | Glue REST endpoint region |
| `AWS_ACCOUNT_ID` | Warehouse ARN (Steward account in multi-account) |
| `ICEBERG_WAREHOUSE` | `{account}:s3tablescatalog/{bucket}` |
| `ICEBERG_TABLE_BUCKET` | Default warehouse bucket name |

IAM (Lambda role in Producer, catalog in Steward):

```json
{
  "Action": [
    "glue:GetDatabase", "glue:GetTable", "glue:UpdateTable",
    "glue:GetPartition", "glue:GetPartitions"
  ],
  "Resource": "arn:aws:glue:REGION:STEWARD_ACCOUNT:table/NAMESPACE/TABLE"
}
```

Plus `lakeformation:GetDataAccess` when Lake Formation governs the table.

---

## 8. Multi-account Steward catalog

```mermaid
sequenceDiagram
    participant L as Producer Lambda
    participant GCC as GlueCatalogConnector
    participant G as Steward Glue REST
    participant P as Publisher S3

    Note over L: Physical write cross-account
    L->>P: PutObject Parquet (LF grant)

    Note over L,GCC: Metadata commit to Steward catalog
    L->>GCC: commit()
    GCC->>G: SigV4 as Producer role
    Note over G: LF validates Producer may ALTER table
    G-->>GCC: snapshot references Publisher paths
```

Set `ICEBERG_WAREHOUSE` to the **Steward** account warehouse string even when Parquet
lands in **Publisher** S3.

---

## 9. Anti-patterns

| Anti-pattern | Why it fails | Correct approach |
|--------------|--------------|------------------|
| Start a Glue ETL job from Lambda to write mesh data | Glue jobs are async managed runners, not Lambda subprocesses | Spark-on-Lambda or Polars in `batch_writer` |
| `spark.catalog` JVM commit inside Lambda | Heavy, fragile, wrong catalog session | `GlueCatalogConnector.commit()` |
| Commit metadata before VRP PASS | Silent data loss / audit gap | `validate_then_commit` gate in coordinator |
| Skip `prepare_commit` / `commit` 2PC | Orphan Parquet invisible to Athena | Always run connector after PASS |
| Invoke Lambda without `:live` alias | Durable + catalog replay breaks | Qualified ARN from Terraform |

---

## 10. Related docs

| Document | Topic |
|----------|-------|
| [Data mesh end-to-end](data-mesh-end-to-end.md) | Producer / Steward / Publisher journey |
| [Architecture](architecture.md) | Four-phase transaction boundary |
| [Getting started: Step 8](getting-started.md) | Connector setup in tutorial |
| [Domain contracts](domain-contracts.md) | `source_namespace` / `target_table` |
| `examples/domain_writer/spark_io.py` | Spark physical layer stub |

```python
# Public exports
from serverless_data_mesh import GlueCatalogConnector, GlueRestCatalogAdapter
```

Both names refer to the same metadata-only Glue Iceberg REST connector.
