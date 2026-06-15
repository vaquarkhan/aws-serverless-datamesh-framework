variable "name_prefix" {
  type = string
}

variable "mesh_generated_path" {
  description = "Path to serverless-data-mesh apply output (mesh.orchestrator.asl.json and per-domain orchestrators)."
  type        = string
}

variable "domain_ids" {
  description = "Domain folders under mesh_generated_path (e.g. orders, payments)."
  type        = list(string)
}

variable "layer_lambda_arns" {
  description = "Map of Step Functions template keys to Lambda ARNs (e.g. orders_bronze_writer_arn)."
  type        = map(string)
}

variable "mesh_leader_lambda_arn" {
  description = "Lambda ARN for mesh leader commit step."
  type        = string
}

variable "role_arn" {
  description = "Step Functions execution role ARN."
  type        = string
}

variable "tags" {
  type    = map(string)
  default = {}
}

locals {
  sfn_runtime_vars = {
    partition_dt = "$${partition_dt}"
    domain_id    = "$${domain_id}"
  }

  domain_orchestrator_definitions = {
    for domain in var.domain_ids :
    domain => templatefile(
      "${var.mesh_generated_path}/${domain}/orchestrator.asl.json",
      merge(local.sfn_runtime_vars, var.layer_lambda_arns)
    )
  }

  mesh_orchestrator_arns = {
    for domain in var.domain_ids :
    "${domain}_medallion_orchestrator_arn" => aws_sfn_state_machine.domain_medallion[domain].arn
  }

  mesh_orchestrator_definition = templatefile(
    "${var.mesh_generated_path}/mesh.orchestrator.asl.json",
    merge(
      local.sfn_runtime_vars,
      local.mesh_orchestrator_arns,
      { mesh_leader_commit_arn = var.mesh_leader_lambda_arn }
    )
  )
}

resource "aws_sfn_state_machine" "domain_medallion" {
  for_each = local.domain_orchestrator_definitions

  name       = "${var.name_prefix}-${each.key}-medallion"
  role_arn   = var.role_arn
  definition = each.value

  tags = merge(var.tags, {
    Component = "medallion-domain"
    Domain    = each.key
  })
}

resource "aws_sfn_state_machine" "mesh" {
  name       = "${var.name_prefix}-mesh-orchestrator"
  role_arn   = var.role_arn
  definition = local.mesh_orchestrator_definition

  tags = merge(var.tags, {
    Component = "medallion-mesh"
  })
}
