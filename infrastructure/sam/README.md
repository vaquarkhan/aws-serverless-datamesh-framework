# SAM deployment

Deploy the domain writer as an AWS Lambda Durable Function.

## Prerequisites

- AWS SAM CLI
- Python 3.12 build environment
- S3 checkpoint bucket created out-of-band

## Deploy

```bash
sam build -t infrastructure/sam/template.yaml
sam deploy --guided \
  --parameter-overrides \
    CheckpointBucketName=my-iceguard-checkpoints \
    IcebergTableBucket=my-lakehouse-bucket
```

## Handler

The template points at `examples.domain_writer.handler.lambda_handler`.
Package dependencies via `sam build` so `serverless_data_mesh` and `veridata-recon`
are included in the deployment artifact.
