variable "name_prefix" {
  type = string
}

variable "role_arn" {
  type = string
}

variable "package_path" {
  description = "Path to the zipped Lambda deployment package."
  type        = string
}

variable "handler" {
  type        = string
  default     = "handler.lambda_handler"
  description = "Lambda handler. Platform demo zip: examples.domain_writer.handler.lambda_handler"
}

variable "runtime" {
  type    = string
  default = "python3.12"
}

variable "memory_size" {
  type    = number
  default = 4096
}

variable "enable_lambda_managed_instances" {
  description = <<-EOT
    Attach Lambda Managed Instances (LMI) capacity so per-invoke timeout may be
    set up to 5400s (90 min) for async / ESM / durable async segments.
    Classic on-demand Lambda remains capped at 900s (15 min).
    Requires lambda_managed_instances_capacity_provider_arn when true.
    See: https://aws.amazon.com/blogs/compute/announcing-90-minute-function-timeout-on-aws-lambda-managed-instances/
  EOT
  type        = bool
  default     = false
}

variable "lambda_managed_instances_capacity_provider_arn" {
  description = "ARN of an aws_lambda_capacity_provider for LMI. Required when enable_lambda_managed_instances is true."
  type        = string
  default     = null
}

variable "timeout" {
  description = <<-EOT
    Per-invocation Lambda timeout in seconds (segment clock).
    - On-demand Lambda: 1–900 (AWS hard max 15 minutes).
    - Lambda Managed Instances (async/ESM): 1–5400 (up to 90 minutes).
    This is NOT the total backfill duration. Longer jobs use Durable Execution
    + IceGuard rollback + Step Functions resume up to durable_execution_timeout
    so incomplete Parquet never becomes a corrupt Iceberg snapshot.
  EOT
  type        = number
  default     = 900

  validation {
    condition     = var.timeout >= 1 && var.timeout <= 5400
    error_message = "Lambda per-invocation timeout must be between 1 and 5400 seconds."
  }
}

variable "enable_durable_execution" {
  description = "Enable Lambda Durable Functions durable_config block."
  type        = bool
  default     = true
}

variable "durable_execution_timeout" {
  description = <<-EOT
    Total durable execution budget in seconds across all platform-managed replays
    within one execution (workload clock). Set this to your expected backfill
    wall-clock time — the framework chains Lambda segments until this budget is
    exhausted. AWS allows up to 31622400 seconds (~366 days). Default 5400.
  EOT
  type        = number
  default     = 5400

  validation {
    condition     = var.durable_execution_timeout >= 60 && var.durable_execution_timeout <= 31622400
    error_message = "durable_execution_timeout must be between 60 and 31622400 seconds."
  }
}

variable "durable_retention_days" {
  type    = number
  default = 14
}

variable "environment_variables" {
  type    = map(string)
  default = {}
}

variable "dlq_arn" {
  description = "SQS DLQ ARN for async failure routing."
  type        = string
  default     = null
}

variable "log_retention_days" {
  type    = number
  default = 30
}

variable "tags" {
  type    = map(string)
  default = {}
}

check "lmi_timeout_coherence" {
  assert {
    condition = (
      var.enable_lambda_managed_instances
      ? var.timeout <= 5400
      : var.timeout <= 900
    )
    error_message = "On-demand Lambda timeout max is 900s; enable_lambda_managed_instances allows up to 5400s (90 min)."
  }
}

check "lmi_capacity_provider_required" {
  assert {
    condition = (
      !var.enable_lambda_managed_instances
      || (
        var.lambda_managed_instances_capacity_provider_arn != null
        && var.lambda_managed_instances_capacity_provider_arn != ""
      )
    )
    error_message = "enable_lambda_managed_instances=true requires lambda_managed_instances_capacity_provider_arn."
  }
}
