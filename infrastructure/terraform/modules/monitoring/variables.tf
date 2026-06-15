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

variable "trust_dashboard_domains" {
  description = "Domain IDs shown on the mesh trust CloudWatch dashboard."
  type        = list(string)
  default     = ["orders", "payments", "inventory"]
}
