variable "aws_region" {
  type    = string
  default = "us-east-2"
}

variable "environment" {
  type    = string
  default = "medallion"
}

variable "name_prefix" {
  type = string
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

variable "lambda_package_path" {
  type    = string
  default = "../../build/domain-writer.zip"
}

variable "mesh_generated_path" {
  description = "Output of: serverless-data-mesh apply --contract <mesh.yaml> --output <dir>"
  type        = string
}

variable "layer_lambda_manifest_path" {
  description = "layer_lambda.manifest.json from apply output (per-layer Lambda sizing)"
  type        = string
  default     = ""
}

variable "domain_ids" {
  description = "Deprecated: domains inferred from layer_lambda.manifest.json"
  type        = list(string)
  default     = []
}

variable "enable_durable_execution" {
  type    = bool
  default = true
}

variable "enable_monitoring_alarms" {
  type    = bool
  default = true
}

variable "trust_dashboard_domains" {
  type    = list(string)
  default = []
}

variable "lambda_timeout_seconds" {
  type    = number
  default = 900
}

variable "lambda_memory_mb" {
  type    = number
  default = 4096
}

variable "durable_execution_timeout_seconds" {
  # Workload clock: set to your backfill wall-clock. Segments chain past the
  # 15-minute Lambda limit until this budget is used.
  type    = number
  default = 5400
}

variable "durable_retention_days" {
  type    = number
  default = 14
}

variable "alarm_sns_topic_arns" {
  description = "Extra existing SNS topic ARNs for alarms (merged with created ops topic)."
  type        = list(string)
  default     = []
}

variable "create_ops_sns_topic" {
  description = "Create {name_prefix}-ops-alerts SNS topic for alarms + Lambda alerts."
  type        = bool
  default     = true
}

variable "ops_alert_emails" {
  description = "Email addresses subscribed to ops SNS (confirm AWS subscription email)."
  type        = list(string)
  default     = []
}

variable "ops_alert_https_endpoints" {
  description = "HTTPS webhook endpoints subscribed to ops SNS."
  type        = list(string)
  default     = []
}

variable "enable_lake_formation_governance" {
  type    = bool
  default = false
}

variable "consumer_principal_arn" {
  type    = string
  default = ""
}

variable "glue_database_name" {
  type    = string
  default = "mesh_lakehouse"
}

variable "glue_table_name" {
  type    = string
  default = "gold_products"
}
