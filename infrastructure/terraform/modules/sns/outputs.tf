output "topic_arn" {
  description = "SNS topic ARN (null when create_topic=false)."
  value       = var.create_topic ? aws_sns_topic.ops_alerts[0].arn : null
}

output "topic_name" {
  value = var.create_topic ? aws_sns_topic.ops_alerts[0].name : null
}

output "alarm_actions" {
  description = "List suitable for CloudWatch alarm_actions (empty when disabled)."
  value       = var.create_topic ? [aws_sns_topic.ops_alerts[0].arn] : []
}
