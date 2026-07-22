# SNS topic for CloudWatch alarm and application notifications.

variable "name_prefix" {
  type = string
}

variable "create_topic" {
  description = "Create an SNS topic for mesh ops alerts (recommended for prod)."
  type        = bool
  default     = true
}

variable "topic_name" {
  description = "Override topic name (default: {name_prefix}-ops-alerts)."
  type        = string
  default     = ""
}

variable "email_subscriptions" {
  description = "Email addresses to subscribe (must confirm via AWS email)."
  type        = list(string)
  default     = []
}

variable "https_subscriptions" {
  description = "HTTPS/Slack webhook endpoints to subscribe."
  type        = list(string)
  default     = []
}

variable "kms_master_key_id" {
  description = "Optional CMK for SNS encryption (alias or ARN)."
  type        = string
  default     = ""
}

variable "tags" {
  type    = map(string)
  default = {}
}
