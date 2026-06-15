# Multi-Account Data Mesh — Terraform Layout

Deploy **Producer**, **Steward**, and **Publisher** across separate AWS accounts.

## Account mapping

| Account | Terraform root | Modules |
|---------|----------------|---------|
| **Steward** | `steward/` | `storage` (checkpoints, proofs), Glue catalog refs, LF admin |
| **Publisher** | `publisher/` | `storage` (lakehouse), consumer read roles |
| **Producer** | `producer/` | `lambda`, `stepfunctions`, `eventbridge`, `monitoring` |

## Deploy order

1. **Steward** — checkpoint + proof buckets, Glue database (or import existing)
2. **Publisher** — lakehouse bucket, register with Lake Formation in Steward
3. **Producer** — domain writer Lambda with cross-account env vars:

```hcl
ICEGUARD_CHECKPOINT_BUCKET = "steward-checkpoints-ACCOUNT_ID"
VRP_PROOF_BUCKET           = "steward-proofs-ACCOUNT_ID"
ICEBERG_TABLE_BUCKET       = "publisher-lakehouse-ACCOUNT_ID"
ICEBERG_WAREHOUSE          = "STEWARD_ACCOUNT_ID:s3tablescatalog/publisher-lakehouse-ACCOUNT_ID"
AWS_ACCOUNT_ID             = "STEWARD_ACCOUNT_ID"
```

## Cross-account IAM

Producer Lambda role needs:

- S3 write to Steward checkpoints/proofs (bucket policies trust Producer role ARN)
- S3 write to Publisher lakehouse prefix (Lake Formation grant)
- `glue:*` read/update on Steward catalog table (for `GlueCatalogConnector`)

See [docs/data-mesh-end-to-end.md](../../../docs/data-mesh-end-to-end.md) § IAM.

## Usage

Each folder is a standalone Terraform root. Copy `terraform.tfvars.example` → `terraform.tfvars` per account.

```bash
cd steward && terraform init && terraform apply
cd ../publisher && terraform init && terraform apply
cd ../producer && terraform init && terraform apply
```

Producer `terraform.tfvars` must include Steward and Publisher account IDs and bucket names from prior applies.
