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

variable "domain_ids" {
  description = "Domains from the medallion mesh contract."
  type        = list(string)
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
  type    = number
  default = 5400
}

variable "durable_retention_days" {
  type    = number
  default = 14
}

variable "alarm_sns_topic_arns" {
  type    = list(string)
  default = []
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
