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

variable "certificate_arn" {
  description = "ACM certificate ARN for api.<domain>. Empty disables HTTPS."
  type        = string
  default     = ""
}

variable "api_domain" {
  description = "Public API domain, e.g. api.draftly.example.com. Empty disables the Route53 record."
  type        = string
  default     = ""
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

module "ecs" {
  source = "./ecs-service"

  environment        = var.environment
  vpc_id             = module.vpc.vpc_id
  public_subnet_ids  = module.vpc.public_subnet_ids
  subnet_ids         = module.vpc.private_subnet_ids
  ecr_repository_url = module.ecr.ecr_repository_url
  cockroachdb_url    = var.cockroachdb_url
  certificate_arn    = var.certificate_arn
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

data "aws_route53_zone" "api" {
  count = var.api_domain != "" ? 1 : 0
  name  = var.api_domain
}

resource "aws_route53_record" "api" {
  count   = var.api_domain != "" ? 1 : 0
  zone_id = data.aws_route53_zone.api[0].zone_id
  name    = "api.${var.api_domain}"
  type    = "A"
  alias {
    name                   = module.ecs.alb_dns_name
    zone_id                = module.ecs.alb_zone_id
    evaluate_target_health = true
  }
}
