# Live Mesh Trust Dashboard

Deploy real-time VRP trust monitoring with CloudWatch and Grafana.

## CloudWatch (Terraform)

The monitoring module provisions:

- **Custom metrics** (`ServerlessDataMesh/Trust`): `VRPTrustScore`, `VRPRowCount` (emitted by domain writers via `publish_vrp_metric`)
- **Log metric filters**: `VRPFail`, `MetadataCommitted`, `VRPPass`
- **Dashboard**: `${name_prefix}-mesh-trust` with per-domain trust score and row count
- **Alarms**: VRP trust breach per domain

```hcl
module "monitoring" {
  source = "../../modules/monitoring"

  name_prefix             = var.name_prefix
  lambda_function_name    = module.domain_writer.function_name
  lambda_log_group_name   = module.domain_writer.log_group_name
  aws_region              = var.aws_region
  trust_dashboard_domains = ["orders", "payments", "inventory"]
  alarm_actions           = [aws_sns_topic.ops.arn]
}
```

Domain writers call:

```python
from serverless_data_mesh.metrics.mesh_trust import publish_vrp_metric

publish_vrp_metric(domain_id="orders", verdict="PASS", row_count=5200000)
```

## Grafana

Import `infrastructure/grafana/mesh-trust-dashboard.json`:

1. Add CloudWatch data source (same region as producers)
2. Dashboards → Import → upload JSON
3. Set refresh to 30s

Panels mirror the CloudWatch dashboard: trust score, row count, failures vs commits.

## HTML dashboard (local / steward proofs)

```bash
# Demo mode
serverless-data-mesh dashboard

# Scan steward proof bucket mounted locally
serverless-data-mesh dashboard --proofs-dir /mnt/steward-proofs

# Live CloudWatch (requires AWS credentials)
serverless-data-mesh dashboard --cloudwatch --region us-east-2
```

## Consumer SLA + Lake Formation

Use `infrastructure/terraform/modules/governance/` with `grant_read_if_sla_met()` from Steward automation:

```python
from serverless_data_mesh.governance import grant_read_if_sla_met

payload = grant_read_if_sla_met(contract, proof=latest_proof)
if payload["grant_read"]:
    # Steward Lambda calls lakeformation:GrantPermissions
    ...
```

See scaffolded `consumer_sla.yaml` from `serverless-data-mesh init`.
