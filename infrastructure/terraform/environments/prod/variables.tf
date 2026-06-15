variable "aws_region" {
  description = "AWS region. Durable Lambda may require specific regions (e.g. us-east-2)."
  type        = string
  default     = "us-east-2"
}

variable "environment" {
  type    = string
  default = "prod"
}

variable "name_prefix" {
  description = "Resource name prefix."
  type        = string
}

variable "checkpoint_bucket_name" {
  type = string
}

variable "proof_bucket_name" {
  type = string
}

variable "lakehouse_bucket_name" {
  type = string
}

variable "glue_database_name" {
  type    = string
  default = "raw_orders"
}

variable "glue_table_name" {
  type    = string
  default = "orders_curated"
}

variable "lambda_package_path" {
  description = "Path to domain-writer.zip (build with scripts/package_lambda.sh)."
  type        = string
  default     = "../../build/domain-writer.zip"
}

variable "enable_durable_execution" {
  type    = bool
  default = true
}

variable "enable_step_functions" {
  description = "Deploy Step Functions backfill orchestrator with resume loop."
  type        = bool
  default     = true
}

variable "enable_eventbridge_schedule" {
  description = "Enable scheduled backfill via EventBridge → Step Functions."
  type        = bool
  default     = false
}

variable "enable_monitoring_alarms" {
  type    = bool
  default = true
}

variable "alarm_sns_topic_arns" {
  type    = list(string)
  default = []
}

variable "domain_id" {
  type    = string
  default = "orders-domain"
}

variable "iceberg_checkpoint_interval" {
  type    = string
  default = "5000"
}

# --- Lambda timeout & execution tuning (all configurable via terraform.tfvars) ---

variable "lambda_timeout_seconds" {
  description = "Per-invocation Lambda timeout in seconds (AWS hard max 900 = 15 min)."
  type        = number
  default     = 900

  validation {
    condition     = var.lambda_timeout_seconds >= 1 && var.lambda_timeout_seconds <= 900
    error_message = "lambda_timeout_seconds must be between 1 and 900."
  }
}

variable "lambda_per_invocation_timeout_seconds" {
  description = "Deprecated alias for lambda_timeout_seconds. Prefer lambda_timeout_seconds."
  type        = number
  default     = null
}

variable "lambda_memory_mb" {
  description = "Lambda memory size in MB (affects CPU and chunk throughput)."
  type        = number
  default     = 4096
}

variable "durable_execution_timeout_seconds" {
  description = "Total durable execution budget in seconds (default 5400 = 90 minutes)."
  type        = number
  default     = 5400

  validation {
    condition     = var.durable_execution_timeout_seconds >= 60 && var.durable_execution_timeout_seconds <= 31622400
    error_message = "durable_execution_timeout_seconds must be between 60 and 31622400."
  }
}

variable "durable_retention_days" {
  description = "Durable execution checkpoint retention in Lambda (days)."
  type        = number
  default     = 14
}

variable "max_resume_attempts" {
  description = "Step Functions resume loops after IceGuard rolled_back. Auto-bumped if too low for durable budget."
  type        = number
  default     = 10
}

variable "sfn_invoke_timeout_buffer_seconds" {
  description = "Added to lambda_timeout_seconds for Step Functions lambda:invoke TimeoutSeconds."
  type        = number
  default     = 60
}

variable "resume_wait_seconds" {
  description = "Step Functions pause between rolled_back resume attempts."
  type        = number
  default     = 60
}

variable "iceguard_rollback_threshold_ms" {
  description = "IceGuard rollback lead time before Lambda timeout (ms). Null = auto from lambda_timeout_seconds."
  type        = number
  default     = null
}

variable "trust_dashboard_domains" {
  description = "Domain IDs on the mesh trust CloudWatch dashboard."
  type        = list(string)
  default     = ["orders", "payments", "inventory"]
}

variable "enable_lake_formation_governance" {
  description = "Deploy Lake Formation consumer SLA grant hooks (requires consumer_principal_arn)."
  type        = bool
  default     = false
}

variable "consumer_principal_arn" {
  description = "IAM principal ARN for analytics consumers (Athena role). Required when enable_lake_formation_governance is true."
  type        = string
  default     = ""
}
