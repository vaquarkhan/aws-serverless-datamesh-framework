variable "aws_region" {
  type    = string
  default = "us-east-2"
}

variable "name_prefix" {
  type    = string
  default = "sdm-publisher"
}

variable "lakehouse_bucket_name" {
  type = string
}

variable "producer_account_id" {
  description = "Domain writer account allowed to write curated Parquet."
  type        = string
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
      Project   = "serverless-data-mesh"
      MeshRole  = "publisher"
      ManagedBy = "terraform"
    }
  }
}

module "storage" {
  source = "../../../modules/storage"

  name_prefix            = var.name_prefix
  checkpoint_bucket_name = "${var.lakehouse_bucket_name}-unused-chk"
  proof_bucket_name      = "${var.lakehouse_bucket_name}-unused-prf"
  lakehouse_bucket_name  = var.lakehouse_bucket_name
}

resource "aws_s3_bucket_policy" "lakehouse_producer" {
  bucket = module.storage.lakehouse_bucket_name
  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Sid       = "ProducerWriteLakehouse"
      Effect    = "Allow"
      Principal = { AWS = "arn:aws:iam::${var.producer_account_id}:root" }
      Action    = ["s3:GetObject", "s3:PutObject", "s3:DeleteObject", "s3:ListBucket"]
      Resource = [
        module.storage.lakehouse_bucket_arn,
        "${module.storage.lakehouse_bucket_arn}/*",
      ]
    }]
  })
}

output "lakehouse_bucket" {
  value = module.storage.lakehouse_bucket_name
}

output "publisher_account_id" {
  value = data.aws_caller_identity.current.account_id
}

data "aws_caller_identity" "current" {}
