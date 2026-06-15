output "layer_qualified_arns" {
  description = "Step Functions template keys -> Lambda qualified ARNs"
  value       = local.qualified_arns
}

output "layer_function_names" {
  value = { for key, mod in module.layer_lambda : key => mod.function_name }
}

output "primary_function_name" {
  description = "First layer Lambda (monitoring default)"
  value       = values(module.layer_lambda)[0].function_name
}

output "primary_log_group_name" {
  value = values(module.layer_lambda)[0].log_group_name
}

output "mesh_leader_arn" {
  description = "Gold-layer or first available writer for mesh leader commit"
  value = try(
    module.layer_lambda[keys(var.layers)[length(keys(var.layers)) - 1]].qualified_invoke_arn,
    values(module.layer_lambda)[0].qualified_invoke_arn,
  )
}
