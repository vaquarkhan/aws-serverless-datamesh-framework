output "domain_writer_role_arn" {
  value = aws_iam_role.domain_writer.arn
}

output "domain_writer_role_name" {
  value = aws_iam_role.domain_writer.name
}

output "stepfunctions_role_arn" {
  value = aws_iam_role.stepfunctions.arn
}
