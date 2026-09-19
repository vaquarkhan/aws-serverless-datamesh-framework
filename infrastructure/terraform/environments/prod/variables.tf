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

variable "lambda_handler" {
  description = "Lambda handler. Platform zip: examples.domain_writer.handler.lambda_handler; compiled pipeline: handler.lambda_handler"
  type        = string
  default     = "examples.domain_writer.handler.lambda_handler"
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
  description = "Extra existing SNS topic ARNs for CloudWatch alarms (merged with created ops topic)."
  type        = list(string)
  default     = []
}

variable "create_ops_sns_topic" {
  description = "Create {name_prefix}-ops-alerts SNS topic and wire alarms + Lambda app alerts."
  type        = bool
  default     = true
}

variable "ops_alert_emails" {
  description = "Email addresses subscribed to ops SNS (confirm the AWS subscription email)."
  type        = list(string)
  default     = []
}

variable "ops_alert_https_endpoints" {
  description = "HTTPS webhook endpoints (e.g. Slack incoming webhooks) subscribed to ops SNS."
  type        = list(string)
  default     = []
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

variable "enable_lambda_managed_instances" {
  description = <<-EOT
    Use Lambda Managed Instances so segment timeout may be 15–90 minutes (async/ESM).
    Default false = classic on-demand Lambda (max 15 min per invoke).
    IceGuard + Durable + VRP still gate Iceberg metadata either way.
  EOT
  type        = bool
  default     = false
}

variable "lambda_managed_instances_capacity_provider_arn" {
  description = "ARN of aws_lambda_capacity_provider when enable_lambda_managed_instances is true."
  type        = string
  default     = null
}

variable "lambda_timeout_seconds" {
  description = <<-EOT
    Per-invocation segment timeout in seconds.
    On-demand: 1–900 (15 min). With LMI enabled: 1–5400 (90 min) for async/ESM.
  EOT
  type        = number
  default     = 900

  validation {
    condition     = var.lambda_timeout_seconds >= 1 && var.lambda_timeout_seconds <= 5400
    error_message = "lambda_timeout_seconds must be between 1 and 5400."
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
  description = <<-EOT
    Total durable execution budget in seconds (workload clock).
    Set to your backfill wall-clock — segments chain until this budget is used.
    IceGuard rolls back incomplete writes so Iceberg metadata is never committed
    without VRP PASS. AWS max ~31622400 (~1 year).
  EOT
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

variable "sfn_lambda_invoke_mode" {
  description = <<-EOT
    Step Functions → Lambda invoke mode:
    - sync (default): lambda:invoke RequestResponse. AWS sync cap = 15 minutes.
    - async_callback: waitForTaskToken + InvocationType=Event. Use with LMI for
      segments up to 90 minutes. Handler SendTaskSuccess/Failure is wired in.
  EOT
  type        = string
  default     = "sync"

  validation {
    condition     = contains(["sync", "async_callback"], lower(var.sfn_lambda_invoke_mode))
    error_message = "sfn_lambda_invoke_mode must be sync or async_callback."
  }
}

variable "sfn_invoke_timeout_buffer_seconds" {
  description = "Added to the effective SFN segment wait (sync capped at 900s; async_callback uses full lambda timeout)."
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

variable "lambda_subnet_ids" {
  description = <<-EOT
    Optional subnet IDs for Lambda VPC attachment.
    Default [] = no VPC (Lambda on AWS-managed network — NOT your account default VPC).
    Set with lambda_security_group_ids when writers must reach private endpoints.
  EOT
  type        = list(string)
  default     = []
}

variable "lambda_security_group_ids" {
  description = "Security group IDs required when lambda_subnet_ids is non-empty."
  type        = list(string)
  default     = []
}
