output "checkpoint_bucket_name" {
  value = aws_s3_bucket.mesh["checkpoint"].id
}

output "checkpoint_bucket_arn" {
  value = aws_s3_bucket.mesh["checkpoint"].arn
}

output "proof_bucket_name" {
  value = aws_s3_bucket.mesh["proof"].id
}

output "proof_bucket_arn" {
  value = aws_s3_bucket.mesh["proof"].arn
}

output "lakehouse_bucket_name" {
  value = aws_s3_bucket.mesh["lakehouse"].id
}

output "lakehouse_bucket_arn" {
  value = aws_s3_bucket.mesh["lakehouse"].arn
}
