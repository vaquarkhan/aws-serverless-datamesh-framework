locals {
  account_id = data.aws_caller_identity.current.account_id
  tags = {
    Mesh = "medallion"
  }
  iceberg_warehouse = "${local.account_id}:s3tablescatalog/${var.lakehouse_bucket_name}"

  lambda_per_invocation_timeout = min(var.lambda_timeout_seconds, 900)
  durable_execution_timeout     = var.durable_execution_timeout_seconds
  checkpoint_retention_days     = max(7, var.durable_retention_days)

  layer_manifest_path = var.layer_lambda_manifest_path != "" ? var.layer_lambda_manifest_path : "${var.mesh_generated_path}/layer_lambda.manifest.json"
  layer_manifest      = jsondecode(file(local.layer_manifest_path))
  layer_configs = {
    for key, cfg in local.layer_manifest :
    key => {
      memory_mb = cfg.memory_mb
      engine    = cfg.engine
      domain_id = cfg.domain_id
      layer     = cfg.layer
    }
  }

  domain_ids = distinct([for cfg in local.layer_manifest : cfg.domain_id])
  trust_domains = length(var.trust_dashboard_domains) > 0 ? var.trust_dashboard_domains : local.domain_ids
}

module "storage" {
  source = "../../modules/storage"

  name_prefix               = var.name_prefix
  checkpoint_bucket_name    = var.checkpoint_bucket_name
  proof_bucket_name         = var.proof_bucket_name
  lakehouse_bucket_name     = var.lakehouse_bucket_name
  checkpoint_retention_days = local.checkpoint_retention_days
  proof_retention_days      = 90
  tags                      = local.tags
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

module "lambda_fleet" {
  source = "../../modules/lambda-fleet"

  name_prefix               = var.name_prefix
  layers                    = local.layer_configs
  role_arn                  = module.iam.domain_writer_role_arn
  package_path              = var.lambda_package_path
  enable_durable_execution  = var.enable_durable_execution
  durable_execution_timeout = local.durable_execution_timeout
  durable_retention_days    = var.durable_retention_days
  timeout                   = local.lambda_per_invocation_timeout
  dlq_arn                   = module.messaging.dlq_arn

  base_environment_variables = {
    ICEGUARD_CHECKPOINT_BUCKET = module.storage.checkpoint_bucket_name
    VRP_PROOF_BUCKET           = module.storage.proof_bucket_name
    ICEBERG_TABLE_BUCKET       = var.lakehouse_bucket_name
    LAKEHOUSE_BUCKET           = var.lakehouse_bucket_name
    ICEBERG_WAREHOUSE          = local.iceberg_warehouse
    AWS_ACCOUNT_ID             = local.account_id
    LAMBDA_TIMEOUT_SECONDS     = tostring(local.lambda_per_invocation_timeout)
  }

  tags = local.tags
}

module "medallion_mesh" {
  source = "../../modules/medallion-mesh"

  name_prefix            = var.name_prefix
  mesh_generated_path    = var.mesh_generated_path
  domain_ids             = local.domain_ids
  layer_lambda_arns      = module.lambda_fleet.layer_qualified_arns
  mesh_leader_lambda_arn = module.lambda_fleet.mesh_leader_arn
  role_arn               = module.iam.stepfunctions_role_arn
  tags                   = local.tags
}

module "monitoring" {
  count  = var.enable_monitoring_alarms ? 1 : 0
  source = "../../modules/monitoring"

  name_prefix             = var.name_prefix
  lambda_function_name    = module.lambda_fleet.primary_function_name
  lambda_log_group_name   = module.lambda_fleet.primary_log_group_name
  dlq_queue_name          = "${var.name_prefix}-domain-writer-dlq"
  alarm_actions           = var.alarm_sns_topic_arns
  aws_region              = var.aws_region
  trust_dashboard_domains = local.trust_domains
  tags                    = local.tags
}

module "governance" {
  count  = var.enable_lake_formation_governance ? 1 : 0
  source = "../../modules/governance"

  name_prefix              = var.name_prefix
  steward_account_id       = local.account_id
  consumer_principal_arn   = var.consumer_principal_arn
  database_name            = var.glue_database_name
  table_name               = var.glue_table_name
  steward_lambda_role_name = module.iam.domain_writer_role_name
  tags                     = local.tags
}
