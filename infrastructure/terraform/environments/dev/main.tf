# Dev environment: lighter defaults, same timeout knobs as prod.

terraform {
  required_version = ">= 1.5.0"
  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = ">= 6.25.0"
    }
  }
}

provider "aws" {
  region = var.aws_region
  default_tags {
    tags = {
      Project     = "serverless-data-mesh"
      Environment = "dev"
      ManagedBy   = "terraform"
    }
  }
}

data "aws_caller_identity" "current" {}

variable "aws_region" { default = "us-east-2" }
variable "name_prefix" { default = "sdm-dev" }
variable "checkpoint_bucket_name" { type = string }
variable "proof_bucket_name" { type = string }
variable "lakehouse_bucket_name" { type = string }
variable "lambda_package_path" { default = "../../build/domain-writer.zip" }

variable "lambda_timeout_seconds" {
  description = "Per-invocation Lambda timeout (1-900)."
  type        = number
  default     = 600
}

variable "durable_execution_timeout_seconds" {
  type    = number
  default = 3600
}

variable "lambda_memory_mb" {
  type    = number
  default = 2048
}

variable "max_resume_attempts" {
  type    = number
  default = 5
}

variable "sfn_invoke_timeout_buffer_seconds" {
  type    = number
  default = 60
}

variable "resume_wait_seconds" {
  type    = number
  default = 30
}

variable "iceguard_rollback_threshold_ms" {
  type    = number
  default = null
}

locals {
  account_id        = data.aws_caller_identity.current.account_id
  iceberg_warehouse = "${local.account_id}:s3tablescatalog/${var.lakehouse_bucket_name}"

  lambda_per_invocation_timeout = min(var.lambda_timeout_seconds, 900)
  durable_execution_timeout     = var.durable_execution_timeout_seconds
  sfn_lambda_invoke_timeout     = local.lambda_per_invocation_timeout + var.sfn_invoke_timeout_buffer_seconds
  iceguard_rollback_ms          = coalesce(
    var.iceguard_rollback_threshold_ms,
    min(60000, max(10000, floor(local.lambda_per_invocation_timeout * 33)))
  )
  min_resume_attempts           = ceil(var.durable_execution_timeout_seconds / local.lambda_per_invocation_timeout) + 2
  effective_max_resume_attempts = max(var.max_resume_attempts, local.min_resume_attempts)
}

check "timeout_coherence" {
  assert {
    condition     = local.durable_execution_timeout >= local.lambda_per_invocation_timeout
    error_message = "durable_execution_timeout_seconds must be >= lambda_timeout_seconds."
  }
}

module "storage" {
  source = "../../modules/storage"
  name_prefix            = var.name_prefix
  checkpoint_bucket_name = var.checkpoint_bucket_name
  proof_bucket_name      = var.proof_bucket_name
  lakehouse_bucket_name  = var.lakehouse_bucket_name
}

module "messaging" {
  source      = "../../modules/messaging"
  name_prefix = var.name_prefix
}

module "iam" {
  source                = "../../modules/iam"
  name_prefix           = var.name_prefix
  checkpoint_bucket_arn = module.storage.checkpoint_bucket_arn
  proof_bucket_arn      = module.storage.proof_bucket_arn
  lakehouse_bucket_arn  = module.storage.lakehouse_bucket_arn
  glue_database_name    = "raw_orders"
  glue_table_name       = "orders_curated"
}

module "lambda" {
  source       = "../../modules/lambda"
  name_prefix  = var.name_prefix
  role_arn     = module.iam.domain_writer_role_arn
  package_path = var.lambda_package_path
  memory_size  = var.lambda_memory_mb
  timeout      = local.lambda_per_invocation_timeout
  durable_execution_timeout = local.durable_execution_timeout
  environment_variables = {
    ICEGUARD_CHECKPOINT_BUCKET      = module.storage.checkpoint_bucket_name
    VRP_PROOF_BUCKET               = module.storage.proof_bucket_name
    ICEBERG_TABLE_BUCKET           = var.lakehouse_bucket_name
    ICEBERG_WAREHOUSE              = local.iceberg_warehouse
    AWS_ACCOUNT_ID                 = local.account_id
    LAMBDA_TIMEOUT_SECONDS         = tostring(local.lambda_per_invocation_timeout)
    ICEGUARD_CHECKPOINT_INTERVAL   = "1000"
    ICEGUARD_ROLLBACK_THRESHOLD_MS = tostring(local.iceguard_rollback_ms)
  }
}

module "stepfunctions" {
  source                        = "../../modules/stepfunctions"
  name_prefix                   = var.name_prefix
  role_arn                      = module.iam.stepfunctions_role_arn
  lambda_qualified_arn          = module.lambda.qualified_invoke_arn
  max_resume_attempts           = local.effective_max_resume_attempts
  lambda_invoke_timeout_seconds = local.sfn_lambda_invoke_timeout
  resume_wait_seconds           = var.resume_wait_seconds
}

output "domain_writer_qualified_arn" {
  value = module.lambda.qualified_invoke_arn
}

output "step_functions_arn" {
  value = module.stepfunctions.state_machine_arn
}

output "execution_timeouts" {
  value = {
    lambda_timeout_seconds         = local.lambda_per_invocation_timeout
    durable_execution_seconds      = local.durable_execution_timeout
    step_functions_invoke_seconds  = local.sfn_lambda_invoke_timeout
    max_resume_attempts            = local.effective_max_resume_attempts
  }
}
