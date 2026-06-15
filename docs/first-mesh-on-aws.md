# First mesh on AWS in 5 minutes

End-to-end: YAML → generated pipelines → Terraform → Step Functions run.

## Prerequisites

- Python 3.12+, AWS CLI, Terraform 1.5+
- AWS account with Lambda Durable Execution (e.g. `us-east-2`)

## 1. Install

```bash
pip install serverless-data-mesh==1.1.0
```

## 2. Create and compile mesh

```bash
serverless-data-mesh new --template northstar --output my-mesh
serverless-data-mesh apply --contract my-mesh/mesh.yaml --output my-mesh/generated
```

Reference `readers.py` files are generated for bronze (S3 landing) and silver/gold (upstream Parquet).

## 3. Package Lambda

**Platform demo** (`examples.domain_writer.handler.lambda_handler`):

```bash
./infrastructure/terraform/scripts/package_lambda.sh
# Windows: .\infrastructure\terraform\scripts\package_lambda.ps1
```

**Compiled pipeline layer** (`handler.lambda_handler` at zip root):

```bash
SDM_PIPELINE_SRC=my-mesh/generated/orders/bronze ./infrastructure/terraform/scripts/package_lambda.sh
```

Medallion Terraform `lambda-fleet` defaults to `handler.lambda_handler`. Build one zip per layer or share a zip when readers differ.

## 4. Configure Terraform

```bash
cd infrastructure/terraform/environments/medallion
cp terraform.tfvars.example terraform.tfvars
```

Edit bucket names (globally unique) and paths:

```hcl
mesh_generated_path         = "/absolute/path/to/my-mesh/generated"
layer_lambda_manifest_path  = "/absolute/path/to/my-mesh/generated/layer_lambda.manifest.json"
```

## 5. Deploy (one command)

```bash
serverless-data-mesh deploy \
  --contract my-mesh/mesh.yaml \
  --output my-mesh/generated \
  --auto-approve \
  --start-execution \
  --partition-dt 2026-06-14
```

Or step by step:

```bash
terraform init
terraform apply -auto-approve \
  -var="mesh_generated_path=..." \
  -var="layer_lambda_manifest_path=.../layer_lambda.manifest.json"

aws stepfunctions start-execution \
  --state-machine-arn "$(terraform output -raw mesh_orchestrator_arn)" \
  --input '{"partition_dt":"2026-06-14"}'
```

## 6. Verify

```bash
serverless-data-mesh doctor --path my-mesh/generated
serverless-data-mesh ui --path my-mesh/generated --open
serverless-data-mesh dashboard --cloudwatch --region us-east-2 --open
```

## What gets created

| Resource | Count (northstar) |
|----------|-------------------|
| Lambda writers | 6 (per layer, sized from YAML) |
| Domain Step Functions | 2 (bronze→silver→gold each) |
| Mesh orchestrator | 1 (parallel domains + leader commit) |
| S3 buckets | 3 (checkpoints, proofs, lakehouse) |

## Next

- [Metadata-driven pipeline guide](metadata-driven-pipeline.md)
- [Terraform README](../infrastructure/terraform/README.md)
- [Backstage catalog](../integrations/backstage/README.md)
