output "mesh_orchestrator_arn" {
  value = module.medallion_mesh.mesh_state_machine_arn
}

output "domain_medallion_orchestrator_arns" {
  value = module.medallion_mesh.domain_state_machine_arns
}

output "domain_writer_qualified_arns" {
  value = module.lambda_fleet.layer_qualified_arns
}

output "ops_sns_topic_arn" {
  description = "SNS topic for CloudWatch alarms and Lambda VRP/rollback alerts."
  value       = module.sns.topic_arn
}

output "dlq_url" {
  value = module.messaging.dlq_url
}

output "example_mesh_execution_input" {
  description = "Start the full bronze→silver→gold mesh for all domains."
  value = jsonencode({
    partition_dt = "2026-06-14"
  })
}

output "deploy_flow" {
  description = "Zero-friction path from YAML to AWS."
  value       = <<-EOT
    1. serverless-data-mesh new --template medallion --output my-mesh
    2. serverless-data-mesh apply --contract my-mesh/mesh.yaml --output my-mesh/generated
    3. Set ops_alert_emails in terraform.tfvars; terraform apply -var mesh_generated_path=my-mesh/generated
    4. Confirm SNS subscription email, then:
       aws stepfunctions start-execution --state-machine-arn $(terraform output -raw mesh_orchestrator_arn) --input '{"partition_dt":"2026-06-14"}'
    See docs/aws-production-deploy.md
  EOT
}
