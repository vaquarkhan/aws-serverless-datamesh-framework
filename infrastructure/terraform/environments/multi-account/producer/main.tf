variable "aws_region" {
  type    = string
  default = "us-east-2"
}

variable "name_prefix" {
  type    = string
  default = "sdm-producer"
}

variable "lambda_package_path" {
  type    = string
  default = "../../../build/domain-writer.zip"
}

variable "lambda_handler" {
  type    = string
  default = "examples.domain_writer.handler.lambda_handler"
}

variable "steward_account_id" {
  type = string
}

variable "publisher_account_id" {
  type = string
}

variable "checkpoint_bucket" {
  type = string
}

variable "proof_bucket" {
  type = string
}

variable "lakehouse_bucket" {
  type = string
}

variable "glue_database_name" {
  type    = string
  default = "raw_orders"
}

variable "glue_table_name" {
  type    = string
  default = "orders_curated"
}

variable "lambda_timeout_seconds" {
  type    = number
  default = 900
}

variable "durable_execution_timeout_seconds" {
  type    = number
  default = 5400
}

terraform {
  required_version = ">= 1.5.0"
  required_providers {
    aws = { source = "hashicorp/aws", version = ">= 6.25.0" }
  }
}

provider "aws" {
  region = var.aws_region
  default_tags {
    tags = {
      Project   = "serverless-data-mesh"
      MeshRole  = "producer"
      ManagedBy = "terraform"
    }
  }
}

data "aws_caller_identity" "current" {}

locals {
  iceberg_warehouse = "${var.steward_account_id}:s3tablescatalog/${var.lakehouse_bucket}"
  lambda_timeout    = min(var.lambda_timeout_seconds, 900)
}

module "messaging" {
  source      = "../../../modules/messaging"
  name_prefix = var.name_prefix
}

module "iam" {
  source = "../../../modules/iam"

  name_prefix           = var.name_prefix
  checkpoint_bucket_arn = "arn:aws:s3:::${var.checkpoint_bucket}"
  proof_bucket_arn      = "arn:aws:s3:::${var.proof_bucket}"
  lakehouse_bucket_arn  = "arn:aws:s3:::${var.lakehouse_bucket}"
  glue_database_name    = var.glue_database_name
  glue_table_name       = var.glue_table_name
}

module "lambda" {
  source = "../../../modules/lambda"

  name_prefix               = var.name_prefix
  role_arn                  = module.iam.domain_writer_role_arn
  package_path              = var.lambda_package_path
  handler                   = var.lambda_handler
  timeout                   = local.lambda_timeout
  durable_execution_timeout = var.durable_execution_timeout_seconds
  dlq_arn                   = module.messaging.dlq_arn

  environment_variables = {
    ICEGUARD_CHECKPOINT_BUCKET      = var.checkpoint_bucket
    VRP_PROOF_BUCKET               = var.proof_bucket
    ICEBERG_TABLE_BUCKET           = var.lakehouse_bucket
    ICEBERG_WAREHOUSE              = local.iceberg_warehouse
    AWS_ACCOUNT_ID                 = var.steward_account_id
    LAMBDA_TIMEOUT_SECONDS         = tostring(local.lambda_timeout)
    ICEGUARD_ROLLBACK_THRESHOLD_MS = "30000"
  }
}

module "stepfunctions" {
  source = "../../../modules/stepfunctions"

  name_prefix                   = var.name_prefix
  role_arn                      = module.iam.stepfunctions_role_arn
  lambda_qualified_arn          = module.lambda.qualified_invoke_arn
  lambda_invoke_timeout_seconds = local.lambda_timeout + 60
}

output "producer_account_id" {
  value = data.aws_caller_identity.current.account_id
}

output "domain_writer_qualified_arn" {
  value = module.lambda.qualified_invoke_arn
}

output "step_functions_arn" {
  value = module.stepfunctions.state_machine_arn
}
