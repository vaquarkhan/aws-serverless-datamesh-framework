output "checkpoint_bucket" {
  value = module.storage.checkpoint_bucket_name
}

output "proof_bucket" {
  value = module.storage.proof_bucket_name
}

output "lakehouse_bucket" {
  value = module.storage.lakehouse_bucket_name
}

output "domain_writer_function_name" {
  value = module.lambda.function_name
}

output "domain_writer_qualified_arn" {
  description = "Invoke via this ARN (alias) for durable execution."
  value       = module.lambda.qualified_invoke_arn
}

output "step_functions_arn" {
  value = var.enable_step_functions ? module.stepfunctions[0].state_machine_arn : null
}

output "dlq_url" {
  value = module.messaging.dlq_url
}

output "example_stepfunctions_input" {
  description = "Paste into Step Functions → Start execution."
  value = jsonencode({
    workload_id    = "backfill-2026q2-orders"
    total_records  = 250000
    domain_id      = var.domain_id
    source_uri     = "s3://${var.lakehouse_bucket_name}/source/orders/"
    target_uri     = "s3://${var.lakehouse_bucket_name}/curated/orders/"
    partition_spec = { dt = "2026-06-14" }
  })
}

output "example_cli_invoke" {
  description = "Direct Lambda invoke (qualified ARN required for durable)."
  value       = "aws lambda invoke --function-name ${module.lambda.function_name}:live --payload file://payload.json out.json"
}

output "execution_timeouts" {
  description = "Two-layer timeout model for long backfills (all Terraform-configurable)."
  value = {
    lambda_timeout_seconds          = local.lambda_per_invocation_timeout
    lambda_memory_mb                = var.lambda_memory_mb
    durable_execution_seconds       = local.durable_execution_timeout
    durable_retention_days          = var.durable_retention_days
    iceguard_rollback_threshold_ms  = local.iceguard_rollback_ms
    step_functions_invoke_seconds   = local.sfn_lambda_invoke_timeout
    step_functions_invoke_buffer_s  = var.sfn_invoke_timeout_buffer_seconds
    resume_wait_seconds             = var.resume_wait_seconds
    max_resume_attempts             = local.effective_max_resume_attempts
    min_resume_attempts_required    = local.min_resume_attempts
  }
}
