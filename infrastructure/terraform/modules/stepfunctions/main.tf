locals {
  invoke_mode = lower(var.sfn_lambda_invoke_mode)
  template_name = (
    local.invoke_mode == "async_callback"
    ? "state_machine_async_callback.asl.json.tpl"
    : "state_machine_sync.asl.json.tpl"
  )
  heartbeat_seconds = max(60, min(var.lambda_invoke_timeout_seconds - 30, 3600))
  state_machine_definition = templatefile("${path.module}/${local.template_name}", {
    lambda_qualified_arn          = var.lambda_qualified_arn
    max_resume_attempts           = var.max_resume_attempts
    resume_wait_seconds           = var.resume_wait_seconds
    lambda_invoke_timeout_seconds = var.lambda_invoke_timeout_seconds
    heartbeat_seconds             = local.heartbeat_seconds
  })
}

check "sfn_invoke_mode" {
  assert {
    condition     = contains(["sync", "async_callback"], local.invoke_mode)
    error_message = "sfn_lambda_invoke_mode must be sync or async_callback."
  }
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
    Component       = "backfill-orchestrator"
    SfnInvokeMode   = local.invoke_mode
  })
}
