locals {
  state_machine_definition = templatefile("${path.module}/state_machine.asl.json.tpl", {
    lambda_qualified_arn        = var.lambda_qualified_arn
    max_resume_attempts         = var.max_resume_attempts
    resume_wait_seconds         = var.resume_wait_seconds
    lambda_invoke_timeout_seconds = var.lambda_invoke_timeout_seconds
  })
}

resource "aws_cloudwatch_log_group" "sfn" {
  name              = "/aws/vendedlogs/states/${var.name_prefix}-backfill"
  retention_in_days = var.log_retention_days
  tags              = var.tags
}

resource "aws_sfn_state_machine" "backfill" {
  name     = "${var.name_prefix}-backfill-orchestrator"
  role_arn = var.role_arn

  definition = local.state_machine_definition

  logging_configuration {
    log_destination        = "${aws_cloudwatch_log_group.sfn.arn}:*"
    include_execution_data = true
    level                  = "ALL"
  }

  tags = merge(var.tags, {
    Component = "backfill-orchestrator"
  })
}
