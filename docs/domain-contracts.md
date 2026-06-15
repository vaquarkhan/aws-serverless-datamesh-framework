# Domain Contracts

## Transaction boundary

Each domain declares a `DomainTransactionBoundary`:

```python
DomainTransactionBoundary(
    domain_id="orders-domain",
    source_namespace="raw_orders",
    target_table="orders_curated",
    partition_spec={"dt": "2026-06-14"},
    quality_policy_id="strict-zero-drop",
    max_chunk_records=5000,
)
```

## Event schema

| Field | Required | Description |
|-------|----------|-------------|
| `workload_id` | yes | Unique idempotency key for the backfill/copy |
| `total_records` | yes | Records to process in `[0, total_records)` |
| `domain_id` | no | Owning domain (default: `orders-domain`) |
| `source_uri` | no | Opaque source locator for VRP `source_ref` |
| `target_uri` | no | Lakehouse prefix for Parquet output |
| `partition_spec` | no | Partition key/value map |
| `content_fields` | no | VRP content hash fields |
| `identity_fields` | no | VRP identity rule fields |

## Quality policies

The `quality_policy_id` is carried in workload metadata for audit. Enforcement is
via veridata-recon tolerances (zero drops, zero mutations, no duplicates by default).

## Multi-domain coordination

Domains operate independently but share the coordinator contract:

1. Publish a `DataProductContract` (or `DomainTransactionBoundary`) to the mesh registry
2. Register Glue namespace/table via REST catalog (`GlueCatalogConnector`)
3. Invoke durable Lambda handler
4. Store VRP proofs in `VRP_PROOF_BUCKET` under `{domain_id}/{workload_id}/`

See [data-mesh-patterns.md](data-mesh-patterns.md) for the full concept coverage matrix.

Cross-domain consumers verify proofs offline with `veridata-recon verify_proof`.
