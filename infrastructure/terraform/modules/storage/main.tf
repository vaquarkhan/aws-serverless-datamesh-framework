locals {
  buckets = {
    checkpoint = var.checkpoint_bucket_name
    proof      = var.proof_bucket_name
    lakehouse  = var.lakehouse_bucket_name
  }
}

resource "aws_s3_bucket" "mesh" {
  for_each = local.buckets

  bucket = each.value
  tags = merge(var.tags, {
    Name    = each.value
    Purpose = each.key
  })
}

resource "aws_s3_bucket_public_access_block" "mesh" {
  for_each = aws_s3_bucket.mesh

  bucket = each.value.id

  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}

resource "aws_s3_bucket_versioning" "mesh" {
  for_each = aws_s3_bucket.mesh

  bucket = each.value.id
  versioning_configuration {
    status = "Enabled"
  }
}

resource "aws_s3_bucket_server_side_encryption_configuration" "mesh" {
  for_each = aws_s3_bucket.mesh

  bucket = each.value.id

  rule {
    apply_server_side_encryption_by_default {
      sse_algorithm     = var.kms_key_arn == null ? "AES256" : "aws:kms"
      kms_master_key_id = var.kms_key_arn
    }
    bucket_key_enabled = var.kms_key_arn != null
  }
}

resource "aws_s3_bucket_lifecycle_configuration" "mesh" {
  for_each = {
    checkpoint = {
      bucket     = aws_s3_bucket.mesh["checkpoint"].id
      expiration = var.checkpoint_retention_days
    }
    proof = {
      bucket     = aws_s3_bucket.mesh["proof"].id
      expiration = var.proof_retention_days
    }
  }

  bucket = each.value.bucket

  rule {
    id     = "expire-objects"
    status = "Enabled"

    expiration {
      days = each.value.expiration
    }

    noncurrent_version_expiration {
      noncurrent_days = 7
    }
  }
}
