variable "aws_region" {
  type    = string
  default = "us-east-2"
}

variable "name_prefix" {
  type    = string
  default = "sdm-steward"
}

variable "checkpoint_bucket_name" {
  type = string
}

variable "proof_bucket_name" {
  type = string
}

variable "producer_account_id" {
  description = "AWS account ID allowed to write checkpoints and proofs."
  type        = string
}

variable "durable_retention_days" {
  type    = number
  default = 14
}

terraform {
  required_version = ">= 1.5.0"
  required_providers {
    aws = { source = "hashicorp/aws", version = ">= 6.25.0" }
  }
}

provider "aws" {
  region = var.aws_region
  default_tags {
    tags = {
      Project     = "serverless-data-mesh"
      MeshRole    = "steward"
      ManagedBy   = "terraform"
    }
  }
}

module "storage" {
  source = "../../../modules/storage"

  name_prefix              = var.name_prefix
  checkpoint_bucket_name   = var.checkpoint_bucket_name
  proof_bucket_name        = var.proof_bucket_name
  lakehouse_bucket_name    = "${var.name_prefix}-internal-${data.aws_caller_identity.current.account_id}"
  checkpoint_retention_days = var.durable_retention_days
  proof_retention_days      = 90
}

# Allow Producer Lambda role cross-account writes to checkpoint and proof buckets.
resource "aws_s3_bucket_policy" "checkpoints_producer" {
  bucket = module.storage.checkpoint_bucket_name
  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Sid       = "ProducerWriteCheckpoints"
      Effect    = "Allow"
      Principal = { AWS = "arn:aws:iam::${var.producer_account_id}:root" }
      Action    = ["s3:GetObject", "s3:PutObject", "s3:DeleteObject", "s3:ListBucket"]
      Resource = [
        module.storage.checkpoint_bucket_arn,
        "${module.storage.checkpoint_bucket_arn}/*",
      ]
    }]
  })
}

resource "aws_s3_bucket_policy" "proofs_producer" {
  bucket = module.storage.proof_bucket_name
  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Sid       = "ProducerWriteProofs"
      Effect    = "Allow"
      Principal = { AWS = "arn:aws:iam::${var.producer_account_id}:root" }
      Action    = ["s3:GetObject", "s3:PutObject", "s3:ListBucket"]
      Resource = [
        module.storage.proof_bucket_arn,
        "${module.storage.proof_bucket_arn}/*",
      ]
    }]
  })
}

output "checkpoint_bucket" {
  value = module.storage.checkpoint_bucket_name
}

output "proof_bucket" {
  value = module.storage.proof_bucket_name
}

output "steward_account_id" {
  value = data.aws_caller_identity.current.account_id
}

data "aws_caller_identity" "current" {}
