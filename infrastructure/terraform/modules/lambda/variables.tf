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
  type    = string
  default = "examples.domain_writer.handler.lambda_handler"
}

variable "runtime" {
  type    = string
  default = "python3.12"
}

variable "memory_size" {
  type    = number
  default = 4096
}

variable "timeout" {
  description = <<-EOT
    Per-invocation Lambda timeout in seconds (AWS hard max: 900 / 15 minutes).
    This is NOT the total backfill duration. Long jobs use durable execution
    replay + Step Functions resume loops up to durable_execution_timeout.
  EOT
  type        = number
  default     = 900

  validation {
    condition     = var.timeout >= 1 && var.timeout <= 900
    error_message = "Lambda per-invocation timeout must be between 1 and 900 seconds."
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
    within one execution (default 5400 = 90 minutes). AWS allows up to 31622400 (366 days).
    Set >= expected backfill wall-clock time when invoking via qualified ARN directly.
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
