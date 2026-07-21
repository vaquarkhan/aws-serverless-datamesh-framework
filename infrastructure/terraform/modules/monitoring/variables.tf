variable "name_prefix" {
  type = string
}

variable "lambda_function_name" {
  type = string
}

variable "lambda_log_group_name" {
  type = string
}

variable "alarm_actions" {
  description = "SNS topic ARNs for alarm notifications."
  type        = list(string)
  default     = []
}

variable "tags" {
  type    = map(string)
  default = {}
}

variable "aws_region" {
  description = "AWS region for CloudWatch dashboard widgets."
  type        = string
  default     = "us-east-2"
}

variable "dlq_queue_name" {
  description = "SQS DLQ name for depth monitoring (empty to skip)."
  type        = string
  default     = ""
}

variable "trust_dashboard_domains" {
  description = "Domain IDs shown on the mesh trust CloudWatch dashboard."
  type        = list(string)
  default     = ["orders", "payments", "inventory"]
}

variable "state_machine_name" {
  description = "Step Functions state machine name for ExecutionsFailed/TimedOut alarms (empty to skip)."
  type        = string
  default     = ""
}

variable "state_machine_arn" {
  description = "Full Step Functions ARN (preferred over state_machine_name when known)."
  type        = string
  default     = ""
}

variable "ok_actions" {
  description = "SNS ARNs notified when alarms return to OK."
  type        = list(string)
  default     = []
}
