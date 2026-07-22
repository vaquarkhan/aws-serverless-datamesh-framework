data "aws_caller_identity" "current" {}

locals {
  sfn_alarm_arn = var.state_machine_arn != "" ? var.state_machine_arn : (
    var.state_machine_name != ""
    ? "arn:aws:states:${var.aws_region}:${data.aws_caller_identity.current.account_id}:stateMachine:${var.state_machine_name}"
    : ""
  )
}

resource "aws_cloudwatch_metric_alarm" "lambda_errors" {
  alarm_name          = "${var.name_prefix}-domain-writer-errors"
  comparison_operator = "GreaterThanThreshold"
  evaluation_periods  = 1
  metric_name         = "Errors"
  namespace           = "AWS/Lambda"
  period              = 300
  statistic           = "Sum"
  threshold           = 0
  treat_missing_data  = "notBreaching"
  alarm_description   = "Domain writer Lambda reported errors."
  alarm_actions       = var.alarm_actions
  ok_actions          = var.ok_actions

  dimensions = {
    FunctionName = var.lambda_function_name
  }

  tags = var.tags
}

resource "aws_cloudwatch_metric_alarm" "lambda_throttles" {
  alarm_name          = "${var.name_prefix}-domain-writer-throttles"
  comparison_operator = "GreaterThanThreshold"
  evaluation_periods  = 1
  metric_name         = "Throttles"
  namespace           = "AWS/Lambda"
  period              = 300
  statistic           = "Sum"
  threshold           = 0
  treat_missing_data  = "notBreaching"
  alarm_description   = "Domain writer Lambda is throttled."
  alarm_actions       = var.alarm_actions
  ok_actions          = var.ok_actions

  dimensions = {
    FunctionName = var.lambda_function_name
  }

  tags = var.tags
}

resource "aws_cloudwatch_metric_alarm" "lambda_duration_p99" {
  alarm_name          = "${var.name_prefix}-domain-writer-duration-p99"
  comparison_operator = "GreaterThanThreshold"
  evaluation_periods  = 2
  metric_name         = "Duration"
  namespace           = "AWS/Lambda"
  period              = 300
  extended_statistic  = "p99"
  threshold           = 840000
  treat_missing_data  = "notBreaching"
  alarm_description   = "Domain writer p99 duration approaching 15-minute Lambda ceiling."
  alarm_actions       = var.alarm_actions
  ok_actions          = var.ok_actions

  dimensions = {
    FunctionName = var.lambda_function_name
  }

  tags = var.tags
}

resource "aws_cloudwatch_log_metric_filter" "iceguard_rollback" {
  name           = "${var.name_prefix}-iceguard-rollback"
  log_group_name = var.lambda_log_group_name
  pattern        = "\"rolled_back\""

  metric_transformation {
    name      = "IceGuardRollback"
    namespace = "ServerlessDataMesh"
    value     = "1"
  }
}

resource "aws_cloudwatch_metric_alarm" "rollback_near_timeout" {
  alarm_name          = "${var.name_prefix}-iceguard-rollback-detected"
  comparison_operator = "GreaterThanThreshold"
  evaluation_periods  = 1
  metric_name         = "IceGuardRollback"
  namespace           = "ServerlessDataMesh"
  period              = 300
  statistic           = "Sum"
  threshold           = 0
  treat_missing_data  = "notBreaching"
  alarm_description   = "IceGuard rollback detected: near-timeout pressure on domain writer."
  alarm_actions       = var.alarm_actions
  ok_actions          = var.ok_actions

  tags = var.tags
}

resource "aws_cloudwatch_metric_alarm" "sfn_executions_failed" {
  count = local.sfn_alarm_arn != "" ? 1 : 0

  alarm_name          = "${var.name_prefix}-sfn-executions-failed"
  comparison_operator = "GreaterThanThreshold"
  evaluation_periods  = 1
  metric_name         = "ExecutionsFailed"
  namespace           = "AWS/States"
  period              = 300
  statistic           = "Sum"
  threshold           = 0
  treat_missing_data  = "notBreaching"
  alarm_description   = "Step Functions execution failed (covers sync Lambda invoke path)."
  alarm_actions       = var.alarm_actions
  ok_actions          = var.ok_actions

  dimensions = {
    StateMachineArn = local.sfn_alarm_arn
  }

  tags = var.tags
}

resource "aws_cloudwatch_metric_alarm" "sfn_executions_timed_out" {
  count = local.sfn_alarm_arn != "" ? 1 : 0

  alarm_name          = "${var.name_prefix}-sfn-executions-timed-out"
  comparison_operator = "GreaterThanThreshold"
  evaluation_periods  = 1
  metric_name         = "ExecutionsTimedOut"
  namespace           = "AWS/States"
  period              = 300
  statistic           = "Sum"
  threshold           = 0
  treat_missing_data  = "notBreaching"
  alarm_description   = "Step Functions execution timed out."
  alarm_actions       = var.alarm_actions
  ok_actions          = var.ok_actions

  dimensions = {
    StateMachineArn = local.sfn_alarm_arn
  }

  tags = var.tags
}
