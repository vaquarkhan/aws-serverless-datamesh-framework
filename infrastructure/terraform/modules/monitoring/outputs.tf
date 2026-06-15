output "alarm_names" {
  value = [
    aws_cloudwatch_metric_alarm.lambda_errors.alarm_name,
    aws_cloudwatch_metric_alarm.lambda_throttles.alarm_name,
    aws_cloudwatch_metric_alarm.lambda_duration_p99.alarm_name,
    aws_cloudwatch_metric_alarm.rollback_near_timeout.alarm_name,
  ]
}
