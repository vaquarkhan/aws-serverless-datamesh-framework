locals {
  topic_name = var.topic_name != "" ? var.topic_name : "${var.name_prefix}-ops-alerts"
}

resource "aws_sns_topic" "ops_alerts" {
  count = var.create_topic ? 1 : 0

  name              = local.topic_name
  kms_master_key_id = var.kms_master_key_id != "" ? var.kms_master_key_id : null
  tags              = merge(var.tags, { Purpose = "mesh-ops-alerts" })
}

resource "aws_sns_topic_subscription" "email" {
  for_each = var.create_topic ? toset(var.email_subscriptions) : toset([])

  topic_arn = aws_sns_topic.ops_alerts[0].arn
  protocol  = "email"
  endpoint  = each.value
}

resource "aws_sns_topic_subscription" "https" {
  for_each = var.create_topic ? toset(var.https_subscriptions) : toset([])

  topic_arn = aws_sns_topic.ops_alerts[0].arn
  protocol  = "https"
  endpoint  = each.value
}
