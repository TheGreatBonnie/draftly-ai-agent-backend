# Staging stack disabled (production-only deployment for now).
# Enable once a staging CockroachDB URL and separate cert/domain are available.
#
# module "staging" {
#   source = "./ecs-service"
#
#   environment        = "staging"
#   project_name       = "draftly"
#   vpc_id             = module.vpc.vpc_id
#   public_subnet_ids  = module.vpc.public_subnet_ids
#   subnet_ids         = module.vpc.private_subnet_ids
#   ecr_repository_url = module.ecr.ecr_repository_url
#   cockroachdb_url    = var.cockroachdb_url_staging
#   certificate_arn    = var.certificate_arn
#   api_domain         = var.api_domain
#   desired_count      = 1
#   cpu                = 256
#   memory             = 512
# }

# variable "cockroachdb_url_staging" {
#   description = "CockroachDB connection URL for staging"
#   type        = string
#   sensitive   = true
# }

# output "staging_ecs_cluster_name" {
#   value = module.staging.ecs_cluster_name
# }

# output "staging_ecs_service_name" {
#   value = module.staging.ecs_service_name
# }

# output "staging_alb_dns_name" {
#   value = module.staging.alb_dns_name
# }
