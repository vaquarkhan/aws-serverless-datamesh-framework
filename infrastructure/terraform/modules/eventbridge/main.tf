resource "aws_iam_role" "events" {
  name = "${var.name_prefix}-events-sfn"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect = "Allow"
      Principal = {
        Service = "events.amazonaws.com"
      }
      Action = "sts:AssumeRole"
    }]
  })

  tags = var.tags
}

resource "aws_iam_role_policy" "events_start_sfn" {
  name = "${var.name_prefix}-events-start-sfn"
  role = aws_iam_role.events.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect   = "Allow"
      Action   = ["states:StartExecution"]
      Resource = var.state_machine_arn
    }]
  })
}

resource "aws_cloudwatch_event_rule" "backfill_schedule" {
  name                = "${var.name_prefix}-backfill-schedule"
  description         = "Triggers Step Functions backfill orchestrator"
  schedule_expression = var.schedule_expression
  state               = var.schedule_enabled ? "ENABLED" : "DISABLED"
  tags                = var.tags
}

resource "aws_cloudwatch_event_target" "backfill_sfn" {
  rule     = aws_cloudwatch_event_rule.backfill_schedule.name
  arn      = var.state_machine_arn
  role_arn = aws_iam_role.events.arn

  input = var.default_workload_payload
}
