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

variable "vpc_id" {
  description = "VPC ID"
  type        = string
}

variable "subnet_ids" {
  description = "Subnet IDs"
  type        = list(string)
}

variable "cockroachdb_url" {
  description = "CockroachDB connection URL"
  type        = string
  sensitive   = true
}

variable "certificate_arn" {
  description = "ACM certificate ARN for api.<domain>"
  type        = string
}

variable "api_domain" {
  description = "Public API domain, e.g. api.draftly.example.com"
  type        = string
}

variable "backend_key" {
  description = "Terraform state key"
  default     = "prod/terraform.tfstate"
}

terraform {
  backend "s3" {
    bucket         = "draftly-terraform-state"
    key            = var.backend_key
    region         = "us-east-1"
    dynamodb_table = "terraform-locks"
    encrypt        = true
  }
}

module "ecr" {
  source = "./ecr-repository"
}

module "ecs" {
  source = "./ecs-service"

  environment        = var.environment
  vpc_id             = var.vpc_id
  subnet_ids         = var.subnet_ids
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

data "aws_route53_zone" "api" {
  name = var.api_domain
}

resource "aws_route53_record" "api" {
  zone_id = data.aws_route53_zone.api.zone_id
  name    = "api.${var.api_domain}"
  type    = "A"
  alias {
    name                   = module.ecs.alb_dns_name
    zone_id                = module.ecs.alb_zone_id
    evaluate_target_health = true
  }
}
