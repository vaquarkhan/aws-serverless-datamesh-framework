data "aws_caller_identity" "current" {}
data "aws_region" "current" {}

resource "aws_iam_role" "domain_writer" {
  name = "${var.name_prefix}-domain-writer"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect = "Allow"
      Principal = {
        Service = "lambda.amazonaws.com"
      }
      Action = "sts:AssumeRole"
    }]
  })

  tags = var.tags
}

resource "aws_iam_role_policy_attachment" "lambda_basic" {
  role       = aws_iam_role.domain_writer.name
  policy_arn = "arn:aws:iam::aws:policy/service-role/AWSLambdaBasicExecutionRolePolicy"
}

# Durable execution checkpoint permissions (required for Lambda Durable Functions).
resource "aws_iam_role_policy_attachment" "lambda_durable" {
  role       = aws_iam_role.domain_writer.name
  policy_arn = "arn:aws:iam::aws:policy/service-role/AWSLambdaBasicDurableExecutionRolePolicy"
}

resource "aws_iam_role_policy" "domain_writer_data" {
  name = "${var.name_prefix}-domain-writer-data"
  role = aws_iam_role.domain_writer.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = concat(
      [
        {
          Sid    = "S3MeshBuckets"
          Effect = "Allow"
          Action = [
            "s3:GetObject",
            "s3:PutObject",
            "s3:DeleteObject",
            "s3:ListBucket",
            "s3:GetBucketLocation",
          ]
          Resource = [
            var.checkpoint_bucket_arn,
            "${var.checkpoint_bucket_arn}/*",
            var.proof_bucket_arn,
            "${var.proof_bucket_arn}/*",
            var.lakehouse_bucket_arn,
            "${var.lakehouse_bucket_arn}/*",
          ]
        },
        {
          Sid    = "GlueIcebergRest"
          Effect = "Allow"
          Action = [
            "glue:GetDatabase",
            "glue:GetDatabases",
            "glue:GetTable",
            "glue:GetTables",
            "glue:UpdateTable",
            "glue:GetPartition",
            "glue:GetPartitions",
          ]
          Resource = [
            "arn:aws:glue:${data.aws_region.current.name}:${data.aws_caller_identity.current.account_id}:catalog",
            "arn:aws:glue:${data.aws_region.current.name}:${data.aws_caller_identity.current.account_id}:database/${var.glue_database_name}",
            "arn:aws:glue:${data.aws_region.current.name}:${data.aws_caller_identity.current.account_id}:table/${var.glue_database_name}/${var.glue_table_name}",
          ]
        },
      ],
      var.enable_lakeformation ? [
        {
          Sid      = "LakeFormationDataAccess"
          Effect   = "Allow"
          Action   = ["lakeformation:GetDataAccess"]
          Resource = "*"
        }
      ] : []
    )
  })
}

resource "aws_iam_role_policy" "domain_writer_metrics" {
  name = "${var.name_prefix}-cloudwatch-metrics"
  role = aws_iam_role.domain_writer.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Sid    = "PutVRPTrustMetrics"
      Effect = "Allow"
      Action = ["cloudwatch:PutMetricData"]
      Resource = "*"
      Condition = {
        StringLike = {
          "cloudwatch:namespace" = "ServerlessDataMesh*"
        }
      }
    }]
  })
}

resource "aws_iam_role_policy" "domain_writer_vrp_kms" {
  count = var.vrp_kms_key_arn != "" ? 1 : 0
  name  = "${var.name_prefix}-vrp-kms"
  role  = aws_iam_role.domain_writer.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Sid    = "VRPKmsSignAndEncrypt"
      Effect = "Allow"
      Action = [
        "kms:Sign",
        "kms:Verify",
        "kms:Encrypt",
        "kms:Decrypt",
        "kms:DescribeKey",
        "kms:GetPublicKey",
      ]
      Resource = [var.vrp_kms_key_arn]
    }]
  })
}

resource "aws_iam_role_policy" "domain_writer_dlq" {
  count = var.dlq_queue_arn != "" ? 1 : 0
  name  = "${var.name_prefix}-dlq-send"
  role  = aws_iam_role.domain_writer.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Sid    = "SendToAsyncFailureDlq"
      Effect = "Allow"
      Action = [
        "sqs:SendMessage",
        "sqs:GetQueueAttributes",
        "sqs:GetQueueUrl",
      ]
      Resource = [var.dlq_queue_arn]
    }]
  })
}

resource "aws_iam_role_policy" "domain_writer_sns" {
  count = var.sns_topic_arn != "" ? 1 : 0
  name  = "${var.name_prefix}-sns-publish"
  role  = aws_iam_role.domain_writer.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Sid      = "PublishOpsAlerts"
      Effect   = "Allow"
      Action   = ["sns:Publish"]
      Resource = [var.sns_topic_arn]
    }]
  })
}

resource "aws_iam_role" "stepfunctions" {
  name = "${var.name_prefix}-backfill-orchestrator"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect = "Allow"
      Principal = {
        Service = "states.amazonaws.com"
      }
      Action = "sts:AssumeRole"
    }]
  })

  tags = var.tags
}

resource "aws_iam_role_policy" "stepfunctions_invoke" {
  name = "${var.name_prefix}-sfn-invoke-lambda"
  role = aws_iam_role.stepfunctions.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Action = [
          "lambda:InvokeFunction",
        ]
        Resource = "*"
      },
      {
        Effect = "Allow"
        Action = [
          "logs:CreateLogDelivery",
          "logs:GetLogDelivery",
          "logs:UpdateLogDelivery",
          "logs:DeleteLogDelivery",
          "logs:ListLogDeliveries",
          "logs:PutResourcePolicy",
          "logs:DescribeResourcePolicies",
          "logs:DescribeLogGroups",
        ]
        Resource = "*"
      },
    ]
  })
}
