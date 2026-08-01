module "staging" {
  source = "./ecs-service"

  environment        = "staging"
  project_name       = "draftly"
  vpc_id             = var.vpc_id
  subnet_ids         = var.subnet_ids
  ecr_repository_url = module.ecr.ecr_repository_url
  cockroachdb_url    = var.cockroachdb_url_staging
  desired_count      = 1
  cpu                = 256
  memory             = 512
}

variable "cockroachdb_url_staging" {
  description = "CockroachDB connection URL for staging"
  type        = string
  sensitive   = true
}

output "staging_ecs_cluster_name" {
  value = module.staging.ecs_cluster_name
}

output "staging_ecs_service_name" {
  value = module.staging.ecs_service_name
}

output "staging_alb_dns_name" {
  value = module.staging.alb_dns_name
}
