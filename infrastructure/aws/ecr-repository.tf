variable "project_name" {
  description = "Name of the project"
  default     = "draftly"
}

variable "environment" {
  description = "Environment name"
  default     = "production"
}

resource "aws_ecr_repository" "draftly" {
  name                 = var.project_name
  image_tag_mutability = "MUTABLE"
  force_delete         = false

  image_scanning_configuration {
    scan_on_push = true
  }

  tags = {
    Name        = var.project_name
    Environment = var.environment
  }
}

resource "aws_ecr_lifecycle_policy" "draftly" {
  repository = aws_ecr_repository.draftly.name

  policy = jsonencode({
    rules = [
      {
        rulePriority = 1
        description  = "Keep last 10 images"
        selection = {
          tagStatus   = "any"
          countType   = "imageCountMoreThan"
          countNumber = 10
        }
        action = {
          type = "expire"
        }
      }
    ]
  })
}

output "ecr_repository_url" {
  value = aws_ecr_repository.draftly.repository_url
}
