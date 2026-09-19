output "function_name" {
  value = aws_lambda_function.domain_writer.function_name
}

output "function_arn" {
  value = aws_lambda_function.domain_writer.arn
}

output "qualified_invoke_arn" {
  description = "Use this ARN for Step Functions and durable invocations."
  value       = aws_lambda_alias.live.arn
}

output "alias_name" {
  value = aws_lambda_alias.live.name
}

output "durable_execution_timeout" {
  description = "Total durable execution budget in seconds (workload clock; set to your backfill needs)."
  value       = var.enable_durable_execution ? var.durable_execution_timeout : null
}

output "per_invocation_timeout" {
  description = "Lambda per-container timeout in seconds (900 on-demand; up to 5400 with LMI)."
  value       = var.timeout
}

output "lambda_managed_instances_enabled" {
  description = "True when Lambda Managed Instances capacity is attached."
  value       = var.enable_lambda_managed_instances
}

output "log_group_name" {
  value = aws_cloudwatch_log_group.domain_writer.name
}
