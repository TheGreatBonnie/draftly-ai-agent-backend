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
