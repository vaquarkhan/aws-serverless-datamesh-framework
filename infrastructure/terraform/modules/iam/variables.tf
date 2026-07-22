variable "name_prefix" {
  type = string
}

variable "checkpoint_bucket_arn" {
  type = string
}

variable "proof_bucket_arn" {
  type = string
}

variable "lakehouse_bucket_arn" {
  type = string
}

variable "glue_database_name" {
  type = string
}

variable "glue_table_name" {
  type = string
}

variable "enable_lakeformation" {
  type    = bool
  default = true
}

variable "vrp_kms_key_arn" {
  description = "Optional CMK ARN for VRP KMS Sign/Encrypt envelopes (VRP_KMS_KEY_ID)"
  type        = string
  default     = ""
}

variable "dlq_queue_arn" {
  description = "SQS DLQ ARN for Lambda async on_failure destinations."
  type        = string
  default     = ""
}

variable "sns_topic_arn" {
  description = "SNS topic ARN for application VRP/rollback alerts."
  type        = string
  default     = ""
}

variable "tags" {
  type    = map(string)
  default = {}
}
