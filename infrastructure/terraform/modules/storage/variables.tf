variable "name_prefix" {
  description = "Prefix for all resource names."
  type        = string
}

variable "checkpoint_bucket_name" {
  description = "Globally unique S3 bucket for IceGuard checkpoints."
  type        = string
}

variable "proof_bucket_name" {
  description = "Globally unique S3 bucket for VRP proofs."
  type        = string
}

variable "lakehouse_bucket_name" {
  description = "S3 bucket for lakehouse Parquet data (physical writes)."
  type        = string
}

variable "kms_key_arn" {
  description = "Optional KMS key ARN for SSE-KMS. Leave null for SSE-S3."
  type        = string
  default     = null
}

variable "checkpoint_retention_days" {
  description = "Lifecycle expiration for checkpoint objects."
  type        = number
  default     = 7
}

variable "proof_retention_days" {
  description = "Lifecycle expiration for VRP proof objects."
  type        = number
  default     = 90
}

variable "tags" {
  description = "Tags applied to all storage resources."
  type        = map(string)
  default     = {}
}
