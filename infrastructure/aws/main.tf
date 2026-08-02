terraform {
  required_version = ">= 1.0.0"

  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.0"
    }
  }
}

provider "aws" {
  region = var.aws_region
}

variable "aws_region" {
  description = "AWS region"
  default     = "us-east-1"
}

variable "environment" {
  description = "Environment name (production, staging)"
  default     = "production"
}

variable "cockroachdb_url" {
  description = "CockroachDB connection URL"
  type        = string
  sensitive   = true
}

variable "api_domain" {
  description = "Public API domain served by Caddy (Let's Encrypt via HTTP-01)"
  type        = string
  default     = "draftly.dpdns.org"
}

terraform {
  backend "s3" {
    bucket         = "draftly-terraform-state"
    key            = "production/terraform.tfstate"
    region         = "us-east-1"
    dynamodb_table = "terraform-locks"
    encrypt        = true
  }
}

module "vpc" {
  source = "./vpc"

  environment = var.environment
}

module "ecr" {
  source = "./ecr-repository"
}

resource "aws_eip" "alb" {
  count  = length(module.vpc.public_subnet_ids)
  domain = "vpc"

  tags = {
    Name        = "draftly-${var.environment}-nlb-eip-${count.index}"
    Environment = var.environment
  }
}

module "ecs" {
  source = "./ecs-service"

  environment        = var.environment
  vpc_id             = module.vpc.vpc_id
  public_subnet_ids  = module.vpc.public_subnet_ids
  subnet_ids         = module.vpc.private_subnet_ids
  eip_allocation_ids = aws_eip.alb[*].id
  ecr_repository_url = module.ecr.ecr_repository_url
  cockroachdb_url    = var.cockroachdb_url
  api_domain         = var.api_domain
}

output "ecs_cluster_name" {
  value = module.ecs.ecs_cluster_name
}

output "ecs_service_name" {
  value = module.ecs.ecs_service_name
}

output "alb_dns_name" {
  value = module.ecs.alb_dns_name
}

output "ecr_repository_url" {
  value = module.ecr.ecr_repository_url
}

output "nat_eip" {
  description = "Public EIP used by the NAT gateway; allowlist this in CockroachDB Cloud"
  value       = module.vpc.nat_eip
}

output "alb_eip_ips" {
  description = "Public EIPs for the NLB; point the domain's A record at these"
  value       = aws_eip.alb[*].public_ip
}
