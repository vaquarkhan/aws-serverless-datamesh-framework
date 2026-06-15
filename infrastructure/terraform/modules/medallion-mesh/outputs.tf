output "mesh_state_machine_arn" {
  value = aws_sfn_state_machine.mesh.arn
}

output "domain_state_machine_arns" {
  value = { for domain, sm in aws_sfn_state_machine.domain_medallion : domain => sm.arn }
}
