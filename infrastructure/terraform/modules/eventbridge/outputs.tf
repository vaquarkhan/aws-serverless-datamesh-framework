output "schedule_rule_name" {
  value = aws_cloudwatch_event_rule.backfill_schedule.name
}
