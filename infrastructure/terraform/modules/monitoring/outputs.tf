output "alarm_names" {
  value = concat(
    [
      aws_cloudwatch_metric_alarm.lambda_errors.alarm_name,
      aws_cloudwatch_metric_alarm.lambda_throttles.alarm_name,
      aws_cloudwatch_metric_alarm.lambda_duration_p99.alarm_name,
      aws_cloudwatch_metric_alarm.rollback_near_timeout.alarm_name,
    ],
    [for a in aws_cloudwatch_metric_alarm.vrp_trust_breach : a.alarm_name],
  )
}

output "mesh_trust_dashboard_name" {
  value = aws_cloudwatch_dashboard.mesh_trust.dashboard_name
}

output "mesh_trust_dashboard_arn" {
  value = aws_cloudwatch_dashboard.mesh_trust.dashboard_arn
}
