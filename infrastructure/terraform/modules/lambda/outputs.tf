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
  description = "Total durable execution budget in seconds (e.g. 5400 = 90 min)."
  value       = var.enable_durable_execution ? var.durable_execution_timeout : null
}

output "per_invocation_timeout" {
  description = "Lambda per-container timeout in seconds (max 900)."
  value       = var.timeout
}

output "log_group_name" {
  value = aws_cloudwatch_log_group.domain_writer.name
}
