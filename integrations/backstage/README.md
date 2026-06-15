# Backstage integration

Register generated `catalog-info.yaml` files with your Backstage app.

## Export from mesh YAML

```bash
serverless-data-mesh catalog export \
  --contract examples/medallion-e2e/northstar.mesh.yaml \
  --output integrations/backstage/entities
```

## Register in `app-config.yaml`

```yaml
catalog:
  locations:
    - type: file
      target: ../../integrations/backstage/entities/*.yaml
      rules:
        - allow: [Component, System]
```

Each entity includes annotations:

- `serverless-data-mesh/domain`
- `serverless-data-mesh/layer`
- `serverless-data-mesh/table`
- `aws.amazon.com/account-id`

Use **owner** (`group:orders-platform`) for Backstage ownership graphs.
