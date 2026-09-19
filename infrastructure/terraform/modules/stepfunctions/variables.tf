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

variable "sfn_lambda_invoke_mode" {
  description = <<-EOT
    How Step Functions invokes the domain writer:
    - sync: lambda:invoke (RequestResponse). AWS sync cap = 15 minutes.
    - async_callback: lambda:invoke.waitForTaskToken + InvocationType=Event.
      Use with Lambda Managed Instances for segments up to 90 minutes.
      Handler must SendTaskSuccess/Failure (framework helper does this).
  EOT
  type        = string
  default     = "sync"

  validation {
    condition     = contains(["sync", "async_callback"], lower(var.sfn_lambda_invoke_mode))
    error_message = "sfn_lambda_invoke_mode must be sync or async_callback."
  }
}

variable "lambda_invoke_timeout_seconds" {
  description = <<-EOT
    How long Step Functions waits for ONE Lambda segment.
    sync: typically min(lambda_timeout, 900) + buffer.
    async_callback: lambda_timeout + buffer (may be up to ~5460 with LMI 90 min).
  EOT
  type        = number
  default     = 960
}

variable "max_resume_attempts" {
  description = <<-EOT
    Max Step Functions resume loops after IceGuard rolled_back.
    Size as ceil(durable_execution_timeout / lambda_timeout) + buffer so the
    resume loop can cover your configured durable budget. Prod auto-bumps if too low.
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
