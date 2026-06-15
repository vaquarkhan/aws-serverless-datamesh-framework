locals {
  account_id = data.aws_caller_identity.current.account_id
  tags = {
    Domain = var.domain_id
  }
  iceberg_warehouse = "${local.account_id}:s3tablescatalog/${var.lakehouse_bucket_name}"

  # Two-layer timeout model (all knobs in terraform.tfvars):
  # - lambda_timeout_seconds: per-container cap (max 900)
  # - durable_execution_timeout_seconds: total durable budget (e.g. 5400 = 90 min)
  # - sfn_invoke_timeout_buffer_seconds: Step Functions wait = lambda + buffer
  lambda_per_invocation_timeout = min(
    coalesce(var.lambda_per_invocation_timeout_seconds, var.lambda_timeout_seconds),
    900
  )
  durable_execution_timeout       = var.durable_execution_timeout_seconds
  sfn_lambda_invoke_timeout       = local.lambda_per_invocation_timeout + var.sfn_invoke_timeout_buffer_seconds
  iceguard_rollback_ms            = coalesce(
    var.iceguard_rollback_threshold_ms,
    min(60000, max(10000, floor(local.lambda_per_invocation_timeout * 33)))
  )
  checkpoint_retention_days       = max(7, var.durable_retention_days)
  min_resume_attempts             = ceil(var.durable_execution_timeout_seconds / local.lambda_per_invocation_timeout) + 2
  effective_max_resume_attempts   = max(var.max_resume_attempts, local.min_resume_attempts)
}

check "timeout_coherence" {
  assert {
    condition     = local.durable_execution_timeout >= local.lambda_per_invocation_timeout
    error_message = "durable_execution_timeout_seconds must be >= lambda_timeout_seconds."
  }
}

module "storage" {
  source = "../../modules/storage"

  name_prefix             = var.name_prefix
  checkpoint_bucket_name  = var.checkpoint_bucket_name
  proof_bucket_name       = var.proof_bucket_name
  lakehouse_bucket_name   = var.lakehouse_bucket_name
  checkpoint_retention_days = local.checkpoint_retention_days
  proof_retention_days      = 90
  tags                    = local.tags
}

module "messaging" {
  source = "../../modules/messaging"

  name_prefix = var.name_prefix
  tags        = local.tags
}

module "iam" {
  source = "../../modules/iam"

  name_prefix           = var.name_prefix
  checkpoint_bucket_arn = module.storage.checkpoint_bucket_arn
  proof_bucket_arn      = module.storage.proof_bucket_arn
  lakehouse_bucket_arn  = module.storage.lakehouse_bucket_arn
  glue_database_name    = var.glue_database_name
  glue_table_name       = var.glue_table_name
  tags                  = local.tags
}

module "lambda" {
  source = "../../modules/lambda"

  name_prefix              = var.name_prefix
  role_arn                 = module.iam.domain_writer_role_arn
  package_path             = var.lambda_package_path
  enable_durable_execution = var.enable_durable_execution
  durable_execution_timeout = local.durable_execution_timeout
  durable_retention_days    = var.durable_retention_days
  timeout                   = local.lambda_per_invocation_timeout
  memory_size               = var.lambda_memory_mb
  dlq_arn                  = module.messaging.dlq_arn

  environment_variables = {
    ICEGUARD_CHECKPOINT_BUCKET      = module.storage.checkpoint_bucket_name
    VRP_PROOF_BUCKET               = module.storage.proof_bucket_name
    ICEBERG_TABLE_BUCKET           = var.lakehouse_bucket_name
    ICEBERG_WAREHOUSE              = local.iceberg_warehouse
    AWS_ACCOUNT_ID                 = local.account_id
    LAMBDA_TIMEOUT_SECONDS         = tostring(local.lambda_per_invocation_timeout)
    ICEGUARD_CHECKPOINT_INTERVAL   = var.iceberg_checkpoint_interval
    ICEGUARD_ROLLBACK_THRESHOLD_MS = tostring(local.iceguard_rollback_ms)
  }

  tags = local.tags
}

module "stepfunctions" {
  count  = var.enable_step_functions ? 1 : 0
  source = "../../modules/stepfunctions"

  name_prefix          = var.name_prefix
  role_arn             = module.iam.stepfunctions_role_arn
  lambda_qualified_arn = module.lambda.qualified_invoke_arn
  max_resume_attempts  = local.effective_max_resume_attempts
  lambda_invoke_timeout_seconds = local.sfn_lambda_invoke_timeout
  resume_wait_seconds  = var.resume_wait_seconds
  tags                 = local.tags
}

module "eventbridge" {
  count  = var.enable_step_functions && var.enable_eventbridge_schedule ? 1 : 0
  source = "../../modules/eventbridge"

  name_prefix       = var.name_prefix
  state_machine_arn = module.stepfunctions[0].state_machine_arn
  schedule_enabled  = var.enable_eventbridge_schedule
  tags              = local.tags
}

module "monitoring" {
  count  = var.enable_monitoring_alarms ? 1 : 0
  source = "../../modules/monitoring"

  name_prefix          = var.name_prefix
  lambda_function_name = module.lambda.function_name
  lambda_log_group_name = module.lambda.log_group_name
  alarm_actions        = var.alarm_sns_topic_arns
  tags                 = local.tags
}
