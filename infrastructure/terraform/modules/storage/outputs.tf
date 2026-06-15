output "checkpoint_bucket_name" {
  value = try(aws_s3_bucket.mesh["checkpoint"].id, null)
}

output "checkpoint_bucket_arn" {
  value = try(aws_s3_bucket.mesh["checkpoint"].arn, null)
}

output "proof_bucket_name" {
  value = try(aws_s3_bucket.mesh["proof"].id, null)
}

output "proof_bucket_arn" {
  value = try(aws_s3_bucket.mesh["proof"].arn, null)
}

output "lakehouse_bucket_name" {
  value = try(aws_s3_bucket.mesh["lakehouse"].id, null)
}

output "lakehouse_bucket_arn" {
  value = try(aws_s3_bucket.mesh["lakehouse"].arn, null)
}
