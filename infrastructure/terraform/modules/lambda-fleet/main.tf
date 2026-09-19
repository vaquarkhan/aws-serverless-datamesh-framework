variable "name_prefix" {
  type = string
}

variable "layers" {
  description = "Map of layer key -> { memory_mb, engine, domain_id, layer }"
  type = map(object({
    memory_mb = number
    engine    = string
    domain_id = string
    layer     = string
  }))
}

variable "role_arn" {
  type = string
}

variable "lambda_handler" {
  type    = string
  default = "handler.lambda_handler"
}

variable "package_path" {
  type = string
}

variable "timeout" {
  type    = number
  default = 900
}

variable "enable_lambda_managed_instances" {
  type    = bool
  default = false
}

variable "lambda_managed_instances_capacity_provider_arn" {
  type    = string
  default = null
}

variable "enable_durable_execution" {
  type    = bool
  default = true
}

variable "durable_execution_timeout" {
  # Workload clock: set to your backfill wall-clock. IceGuard + Durable protect Iceberg.
  type    = number
  default = 5400
}

variable "durable_retention_days" {
  type    = number
  default = 14
}

variable "base_environment_variables" {
  type    = map(string)
  default = {}
}

variable "dlq_arn" {
  type    = string
  default = null
}

variable "tags" {
  type    = map(string)
  default = {}
}

variable "subnet_ids" {
  type    = list(string)
  default = []
}

variable "security_group_ids" {
  type    = list(string)
  default = []
}

module "layer_lambda" {
  for_each = var.layers
  source   = "../lambda"

  name_prefix               = "${var.name_prefix}-${each.key}"
  role_arn                  = var.role_arn
  package_path              = var.package_path
  handler                   = var.lambda_handler
  memory_size               = each.value.memory_mb
  timeout                   = var.timeout
  enable_durable_execution  = var.enable_durable_execution
  durable_execution_timeout = var.durable_execution_timeout
  durable_retention_days    = var.durable_retention_days
  dlq_arn                   = var.dlq_arn
  enable_lambda_managed_instances = var.enable_lambda_managed_instances
  lambda_managed_instances_capacity_provider_arn = var.lambda_managed_instances_capacity_provider_arn
  subnet_ids         = var.subnet_ids
  security_group_ids = var.security_group_ids

  environment_variables = merge(var.base_environment_variables, {
    MEDALLION_DOMAIN = each.value.domain_id
    MEDALLION_LAYER  = each.value.layer
    RUNTIME_ENGINE   = each.value.engine
    TARGET_TABLE     = "${each.value.domain_id}_${each.value.layer}"
  })

  tags = merge(var.tags, {
  Component = "medallion-layer-writer"
  Domain    = each.value.domain_id
  Layer     = each.value.layer
  })
}

locals {
  qualified_arns = {
    for key, mod in module.layer_lambda :
    "${key}_writer_arn" => mod.qualified_invoke_arn
  }
}
