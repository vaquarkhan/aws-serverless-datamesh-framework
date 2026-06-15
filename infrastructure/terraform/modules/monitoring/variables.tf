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
