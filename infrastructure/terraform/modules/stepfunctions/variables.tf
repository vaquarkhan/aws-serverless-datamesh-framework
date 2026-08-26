variable "name_prefix" {
  type = string
}

variable "role_arn" {
  type = string
}

variable "lambda_qualified_arn" {
  description = "Qualified Lambda ARN (alias) for durable invocation."
  type        = string
}

variable "lambda_invoke_timeout_seconds" {
  description = <<-EOT
    How long Step Functions waits for ONE Lambda segment to return.
    Must exceed per-invocation Lambda timeout (900s) but is NOT the full
    durable workload budget: use max_resume_attempts for multi-segment backfills.
  EOT
  type        = number
  default     = 960
}

variable "max_resume_attempts" {
  description = <<-EOT
    Max Step Functions resume loops after IceGuard rolled_back.
    Size as ceil(durable_execution_timeout / lambda_timeout) + buffer
    (e.g. 180-min / 15-min ≈ 12+2). Prod environments auto-bump if too low.
  EOT
  type        = number
  default     = 10
}

variable "resume_wait_seconds" {
  description = "Wait between resume attempts after rolled_back."
  type        = number
  default     = 60
}

variable "log_retention_days" {
  type    = number
  default = 30
}

variable "tags" {
  type    = map(string)
  default = {}
}
