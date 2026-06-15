resource "aws_sqs_queue" "dlq" {
  name                      = "${var.name_prefix}-domain-writer-dlq"
  message_retention_seconds = 1209600
  sqs_managed_sse_enabled   = true
  tags                      = var.tags
}
