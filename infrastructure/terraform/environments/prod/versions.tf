terraform {
  required_version = ">= 1.5.0"

  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = ">= 6.25.0"
    }
  }

  # Uncomment and configure for remote state (recommended for prod):
  #
  # backend "s3" {
  #   bucket         = "my-tf-state-bucket"
  #   key            = "serverless-data-mesh/prod/terraform.tfstate"
  #   region         = "us-east-1"
  #   dynamodb_table = "terraform-locks"
  #   encrypt        = true
  # }
}
