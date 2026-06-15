output "mesh_orchestrator_arn" {
  value = module.medallion_mesh.mesh_state_machine_arn
}

output "domain_medallion_orchestrator_arns" {
  value = module.medallion_mesh.domain_state_machine_arns
}

output "domain_writer_qualified_arn" {
  value = module.lambda.qualified_invoke_arn
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
    3. terraform apply -var mesh_generated_path=my-mesh/generated
    4. aws stepfunctions start-execution --state-machine-arn $(terraform output -raw mesh_orchestrator_arn) --input '{"partition_dt":"2026-06-14"}'
  EOT
}
