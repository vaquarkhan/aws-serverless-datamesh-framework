locals {
  package_hash = filebase64sha256(var.package_path)
}

resource "aws_cloudwatch_log_group" "domain_writer" {
  name              = "/aws/lambda/${var.name_prefix}-domain-writer"
  retention_in_days = var.log_retention_days
  tags              = var.tags
}

resource "aws_lambda_function" "domain_writer" {
  function_name = "${var.name_prefix}-domain-writer"
  role          = var.role_arn
  handler       = var.handler
  runtime       = var.runtime
  memory_size   = var.memory_size
  timeout       = var.timeout

  filename         = var.package_path
  source_code_hash = local.package_hash

  environment {
    variables = var.environment_variables
  }

  dynamic "durable_config" {
    for_each = var.enable_durable_execution ? [1] : []
    content {
      execution_timeout = var.durable_execution_timeout
      retention_period  = var.durable_retention_days
    }
  }

  depends_on = [aws_cloudwatch_log_group.domain_writer]

  tags = merge(var.tags, {
    Component = "domain-writer"
  })

  timeouts {
    delete = "60m"
  }
}

# Durable functions require invocation via qualified ARN (version or alias).
resource "aws_lambda_alias" "live" {
  name             = "live"
  function_name    = aws_lambda_function.domain_writer.function_name
  function_version = aws_lambda_function.domain_writer.version
}

resource "aws_lambda_function_event_invoke_config" "domain_writer" {
  count = var.dlq_arn == null ? 0 : 1

  function_name          = aws_lambda_function.domain_writer.function_name
  qualifier              = aws_lambda_alias.live.name
  maximum_retry_attempts = 0

  destination_config {
    on_failure {
      destination = var.dlq_arn
    }
  }
}
