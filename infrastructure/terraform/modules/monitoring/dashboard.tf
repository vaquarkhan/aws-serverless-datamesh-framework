resource "aws_cloudwatch_log_metric_filter" "vrp_pass" {
  name           = "${var.name_prefix}-vrp-pass"
  log_group_name = var.lambda_log_group_name
  pattern        = "{ $.event = \"pvdm_outcome\" && $.outcome = \"committed\" }"

  metric_transformation {
    name          = "VRPPass"
    namespace     = "ServerlessDataMesh/Trust"
    value         = "1"
    default_value = "0"
  }
}

resource "aws_cloudwatch_log_metric_filter" "vrp_fail" {
  name           = "${var.name_prefix}-vrp-fail"
  log_group_name = var.lambda_log_group_name
  pattern        = "{ $.event = \"pvdm_outcome\" && $.outcome = \"verification_failed\" }"

  metric_transformation {
    name          = "VRPFail"
    namespace     = "ServerlessDataMesh/Trust"
    value         = "1"
    default_value = "0"
  }
}

resource "aws_cloudwatch_log_metric_filter" "metadata_committed" {
  name           = "${var.name_prefix}-metadata-committed"
  log_group_name = var.lambda_log_group_name
  pattern        = "{ $.event = \"pvdm_outcome\" && $.outcome = \"committed\" && $.snapshot_id = * }"

  metric_transformation {
    name          = "MetadataCommitted"
    namespace     = "ServerlessDataMesh/Trust"
    value         = "1"
    default_value = "0"
  }
}

resource "aws_cloudwatch_metric_alarm" "dlq_depth" {
  count = var.dlq_queue_name != "" ? 1 : 0

  alarm_name          = "${var.name_prefix}-dlq-messages"
  comparison_operator = "GreaterThanThreshold"
  evaluation_periods  = 1
  metric_name         = "ApproximateNumberOfMessagesVisible"
  namespace           = "AWS/SQS"
  period              = 300
  statistic           = "Sum"
  threshold           = 0
  treat_missing_data  = "notBreaching"
  alarm_description   = "Failed async Lambda invocations landed in DLQ."
  alarm_actions       = var.alarm_actions

  dimensions = {
    QueueName = var.dlq_queue_name
  }

  tags = var.tags
}

resource "aws_cloudwatch_dashboard" "mesh_trust" {
  dashboard_name = "${var.name_prefix}-mesh-trust"

  dashboard_body = jsonencode({
    widgets = [
      {
        type   = "metric"
        x      = 0
        y      = 0
        width  = 12
        height = 6
        properties = {
          title  = "VRP Trust Score by Domain"
          region = var.aws_region
          metrics = [
            for domain in var.trust_dashboard_domains : [
              "ServerlessDataMesh/Trust",
              "VRPTrustScore",
              "Domain",
              domain,
            ]
          ]
          stat   = "Average"
          period = 300
          view   = "timeSeries"
          stacked = false
          yAxis = {
            left = { min = 0, max = 1 }
          }
        }
      },
      {
        type   = "metric"
        x      = 12
        y      = 0
        width  = 12
        height = 6
        properties = {
          title  = "VRP Row Count by Domain"
          region = var.aws_region
          metrics = [
            for domain in var.trust_dashboard_domains : [
              "ServerlessDataMesh/Trust",
              "VRPRowCount",
              "Domain",
              domain,
            ]
          ]
          stat   = "Maximum"
          period = 300
          view   = "timeSeries"
        }
      },
      {
        type   = "metric"
        x      = 0
        y      = 6
        width  = 12
        height = 6
        properties = {
          title  = "VRP Failures (log-derived)"
          region = var.aws_region
          metrics = [
            ["ServerlessDataMesh/Trust", "VRPFail"],
          ]
          stat   = "Sum"
          period = 300
          view   = "timeSeries"
        }
      },
      {
        type   = "metric"
        x      = 12
        y      = 6
        width  = 12
        height = 6
        properties = {
          title  = "Metadata Commits (VRP PASS)"
          region = var.aws_region
          metrics = [
            ["ServerlessDataMesh/Trust", "MetadataCommitted"],
          ]
          stat   = "Sum"
          period = 300
          view   = "timeSeries"
        }
      },
      {
        type   = "metric"
        x      = 0
        y      = 12
        width  = 8
        height = 6
        properties = {
          title  = "Lambda Invocations"
          region = var.aws_region
          metrics = [
            ["AWS/Lambda", "Invocations", "FunctionName", var.lambda_function_name],
          ]
          stat   = "Sum"
          period = 300
          view   = "timeSeries"
        }
      },
      {
        type   = "metric"
        x      = 8
        y      = 12
        width  = 8
        height = 6
        properties = {
          title  = "Lambda Errors"
          region = var.aws_region
          metrics = [
            ["AWS/Lambda", "Errors", "FunctionName", var.lambda_function_name],
          ]
          stat   = "Sum"
          period = 300
          view   = "timeSeries"
        }
      },
      {
        type   = "metric"
        x      = 16
        y      = 12
        width  = 8
        height = 6
        properties = {
          title  = "Lambda Duration (avg ms)"
          region = var.aws_region
          metrics = [
            ["AWS/Lambda", "Duration", "FunctionName", var.lambda_function_name],
          ]
          stat   = "Average"
          period = 300
          view   = "timeSeries"
        }
      },
      {
        type   = "metric"
        x      = 0
        y      = 18
        width  = 12
        height = 6
        properties = {
          title  = "DLQ Depth"
          region = var.aws_region
          metrics = var.dlq_queue_name != "" ? [
            ["AWS/SQS", "ApproximateNumberOfMessagesVisible", "QueueName", var.dlq_queue_name],
          ] : [
            ["ServerlessDataMesh/Trust", "VRPFail"],
          ]
          stat   = "Maximum"
          period = 300
          view   = "timeSeries"
        }
      },
      {
        type   = "metric"
        x      = 12
        y      = 18
        width  = 12
        height = 6
        properties = {
          title  = "VRP PASS vs FAIL (log-derived)"
          region = var.aws_region
          metrics = [
            ["ServerlessDataMesh/Trust", "VRPPass"],
            [".", "VRPFail"],
          ]
          stat   = "Sum"
          period = 300
          view   = "timeSeries"
        }
      },
    ]
  })
}

resource "aws_cloudwatch_metric_alarm" "vrp_trust_breach" {
  count = length(var.trust_dashboard_domains)

  alarm_name          = "${var.name_prefix}-vrp-trust-${var.trust_dashboard_domains[count.index]}"
  comparison_operator = "LessThanThreshold"
  evaluation_periods  = 1
  metric_name         = "VRPTrustScore"
  namespace           = "ServerlessDataMesh/Trust"
  period              = 300
  statistic           = "Average"
  threshold           = 1
  treat_missing_data  = "breaching"
  alarm_description   = "VRP trust score dropped below PASS for ${var.trust_dashboard_domains[count.index]}."
  alarm_actions       = var.alarm_actions

  dimensions = {
    Domain = var.trust_dashboard_domains[count.index]
  }

  tags = var.tags
}
