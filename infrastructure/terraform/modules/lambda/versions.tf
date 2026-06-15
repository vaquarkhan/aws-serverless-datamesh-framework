terraform {
  required_version = ">= 1.5.0"
  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = ">= 6.25.0" # durable_config on aws_lambda_function
    }
  }
}
