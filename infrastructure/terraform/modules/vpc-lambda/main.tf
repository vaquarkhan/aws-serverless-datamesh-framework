variable "name_prefix" {
  type = string
}

variable "cidr_block" {
  description = "IPv4 CIDR for the new mesh VPC."
  type        = string
  default     = "10.80.0.0/16"
}

variable "az_count" {
  description = "Number of AZs / private subnets (2 or 3)."
  type        = number
  default     = 2

  validation {
    condition     = contains([2, 3], var.az_count)
    error_message = "az_count must be 2 or 3."
  }
}

variable "tags" {
  type    = map(string)
  default = {}
}

data "aws_availability_zones" "available" {
  state = "available"
}

locals {
  azs = slice(data.aws_availability_zones.available.names, 0, var.az_count)
  # /20 slices inside the /16 for private Lambda subnets
  subnet_cidrs = [
    for i in range(var.az_count) : cidrsubnet(var.cidr_block, 4, i)
  ]
}

resource "aws_vpc" "mesh" {
  cidr_block           = var.cidr_block
  enable_dns_support   = true
  enable_dns_hostnames = true

  tags = merge(var.tags, {
    Name      = "${var.name_prefix}-mesh-vpc"
    Component = "mesh-vpc"
  })
}

resource "aws_subnet" "private" {
  count = var.az_count

  vpc_id                  = aws_vpc.mesh.id
  cidr_block              = local.subnet_cidrs[count.index]
  availability_zone       = local.azs[count.index]
  map_public_ip_on_launch = false

  tags = merge(var.tags, {
    Name = "${var.name_prefix}-mesh-private-${count.index + 1}"
    Tier = "private"
  })
}

resource "aws_security_group" "lambda" {
  name        = "${var.name_prefix}-lambda-eni"
  description = "Egress for Serverless Data Mesh Lambda ENIs"
  vpc_id      = aws_vpc.mesh.id

  egress {
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }

  tags = merge(var.tags, {
    Name = "${var.name_prefix}-lambda-eni"
  })
}

output "vpc_id" {
  value = aws_vpc.mesh.id
}

output "subnet_ids" {
  value = aws_subnet.private[*].id
}

output "security_group_ids" {
  value = [aws_security_group.lambda.id]
}
