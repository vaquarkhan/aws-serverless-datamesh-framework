variable "name_prefix" {
  type = string
}

variable "steward_account_id" {
  type = string
}

variable "consumer_principal_arn" {
  description = "IAM principal ARN for the analytics consumer (e.g. Athena workgroup role)."
  type        = string
}

variable "database_name" {
  type = string
}

variable "table_name" {
  type = string
}

variable "steward_lambda_role_name" {
  description = "IAM role name for Steward Lambda that grants LF read after consumer SLA validation."
  type        = string
}

variable "tags" {
  type    = map(string)
  default = {}
}

resource "aws_lakeformation_resource" "consumer_table" {
  arn = "arn:aws:glue:${data.aws_region.current.name}:${data.aws_caller_identity.current.account_id}:table/${var.database_name}/${var.table_name}"
}

data "aws_region" "current" {}
data "aws_caller_identity" "current" {}

resource "aws_lakeformation_permissions" "consumer_read_gated" {
  principal   = var.consumer_principal_arn
  permissions = ["SELECT"]

  table {
    database_name = var.database_name
    name          = var.table_name
  }

  lifecycle {
    precondition {
      condition     = length(var.consumer_principal_arn) > 0
      error_message = "consumer_principal_arn is required for LF consumer SLA enforcement."
    }
  }
}

resource "aws_iam_role_policy" "steward_lf_grant" {
  name = "${var.name_prefix}-steward-lf-consumer-sla"
  role = var.steward_lambda_role_name

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Sid    = "GrantConsumerOnSLAPass"
        Effect = "Allow"
        Action = [
          "lakeformation:GrantPermissions",
          "lakeformation:RevokePermissions",
          "lakeformation:GetDataAccess",
        ]
        Resource = "*"
        Condition = {
          StringEquals = {
            "lakeformation:GrantTagKey"   = "vrp_enforcement"
            "lakeformation:GrantTagValue" = "consumer_sla"
          }
        }
      },
      {
        Sid    = "ReadProofsForSLA"
        Effect = "Allow"
        Action = ["s3:GetObject", "s3:ListBucket"]
        Resource = [
          "arn:aws:s3:::${var.name_prefix}-steward-proofs",
          "arn:aws:s3:::${var.name_prefix}-steward-proofs/*",
        ]
      },
    ]
  })
}

output "lf_table_arn" {
  value = aws_lakeformation_resource.consumer_table.arn
}

output "consumer_principal_arn" {
  value = var.consumer_principal_arn
}
