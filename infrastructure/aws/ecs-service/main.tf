variable "project_name" {
  description = "Name of the project"
  default     = "draftly"
}

variable "environment" {
  description = "Environment name (production, staging)"
  default     = "production"
}

variable "vpc_id" {
  description = "VPC ID for the ECS service"
  type        = string
}

variable "subnet_ids" {
  description = "Private subnet IDs for the ECS service tasks"
  type        = list(string)
}

variable "public_subnet_ids" {
  description = "Public subnet IDs for the NLB"
  type        = list(string)
}

variable "eip_allocation_ids" {
  description = "Elastic IP allocation IDs, one per public subnet, for the NLB static IPs"
  type        = list(string)
}

variable "container_port" {
  description = "Port exposed by the container"
  default     = 8000
}

variable "cpu" {
  description = "Fargate task CPU units (1 vCPU = 1024)"
  default     = 512
}

variable "memory" {
  description = "Fargate task memory in MiB"
  default     = 1024
}

variable "desired_count" {
  description = "Number of ECS tasks to run"
  default     = 1
}

variable "ecr_repository_url" {
  description = "ECR repository URL"
  type        = string
}

variable "cockroachdb_url" {
  description = "CockroachDB connection URL"
  type        = string
  sensitive   = true
}

variable "api_domain" {
  description = "Public API domain served by Caddy (Let's Encrypt via HTTP-01), e.g. draftly.dpdns.org"
  type        = string
  default     = ""
}

data "aws_secretsmanager_secret" "draftly_env" {
  name = "draftly/${var.environment}/env"
}

data "aws_secretsmanager_secret_version" "draftly_env" {
  secret_id = data.aws_secretsmanager_secret.draftly_env.id
}

data "aws_secretsmanager_secret" "github_private_key" {
  name = "draftly/${var.environment}/github-private-key"
}

data "aws_secretsmanager_secret_version" "github_private_key" {
  secret_id = data.aws_secretsmanager_secret.github_private_key.id
}

resource "aws_ecs_cluster" "draftly" {
  name = "${var.project_name}-${var.environment}-cluster"

  setting {
    name  = "containerInsights"
    value = "enabled"
  }

  tags = {
    Name        = "${var.project_name}-${var.environment}-cluster"
    Environment = var.environment
  }
}

resource "aws_ecs_task_definition" "draftly" {
  family                   = "${var.project_name}-${var.environment}"
  requires_compatibilities = ["FARGATE"]
  network_mode             = "awsvpc"
  cpu                      = var.cpu
  memory                   = var.memory
  execution_role_arn       = aws_iam_role.ecs_execution_role.arn
  task_role_arn            = aws_iam_role.ecs_task_role.arn

  container_definitions = jsonencode([
    {
      name      = var.project_name
      image     = "${var.ecr_repository_url}:latest"
      essential = true

      portMappings = [
        {
          containerPort = var.container_port
          hostPort      = var.container_port
          protocol      = "tcp"
        }
      ]

      environment = [
        {
          name  = "COCKROACHDB_URL"
          value = var.cockroachdb_url
        }
      ]

      secrets = [
        {
          name      = "DRAFTLY_ENV_JSON"
          valueFrom = data.aws_secretsmanager_secret_version.draftly_env.arn
        },
        {
          name      = "GITHUB_PRIVATE_KEY_B64"
          valueFrom = data.aws_secretsmanager_secret_version.github_private_key.arn
        }
      ]

      logConfiguration = {
        logDriver = "awslogs"
        options = {
          "awslogs-group"         = "/ecs/${var.project_name}-${var.environment}"
          "awslogs-region"        = data.aws_region.current.name
          "awslogs-stream-prefix" = "ecs"
        }
      }
    },
    {
      name      = "caddy"
      image     = "caddy:2"
      essential = true
      command   = ["caddy", "reverse-proxy", "--from", var.api_domain, "--to", "127.0.0.1:8000"]

      portMappings = [
        {
          containerPort = 80
          hostPort      = 80
          protocol      = "tcp"
        },
        {
          containerPort = 443
          hostPort      = 443
          protocol      = "tcp"
        }
      ]

      dependsOn = [
        {
          containerName = var.project_name
          condition     = "START"
        }
      ]

      logConfiguration = {
        logDriver = "awslogs"
        options = {
          "awslogs-group"         = "/ecs/${var.project_name}-${var.environment}"
          "awslogs-region"        = data.aws_region.current.name
          "awslogs-stream-prefix" = "caddy"
        }
      }
    }
  ])

  tags = {
    Name        = "${var.project_name}-${var.environment}-task"
    Environment = var.environment
  }
}

resource "aws_ecs_service" "draftly" {
  name            = "${var.project_name}-${var.environment}-service"
  cluster         = aws_ecs_cluster.draftly.id
  task_definition = aws_ecs_task_definition.draftly.arn
  desired_count   = var.desired_count
  launch_type     = "FARGATE"

  network_configuration {
    subnets          = var.subnet_ids
    security_groups  = [aws_security_group.ecs_service.id]
    assign_public_ip = false
  }

  load_balancer {
    target_group_arn = aws_lb_target_group.draftly_http.arn
    container_name   = "caddy"
    container_port   = 80
  }

  load_balancer {
    target_group_arn = aws_lb_target_group.draftly_https.arn
    container_name   = "caddy"
    container_port   = 443
  }

  depends_on = [
    aws_lb_listener.draftly_http,
    aws_lb_listener.draftly_https,
  ]

  tags = {
    Name        = "${var.project_name}-${var.environment}-service"
    Environment = var.environment
  }
}

resource "aws_security_group" "ecs_service" {
  name        = "${var.project_name}-${var.environment}-ecs-sg"
  description = "Security group for ECS service"
  vpc_id      = var.vpc_id

  ingress {
    from_port   = 80
    to_port     = 80
    protocol    = "tcp"
    cidr_blocks = ["0.0.0.0/0"]
  }

  ingress {
    from_port   = 443
    to_port     = 443
    protocol    = "tcp"
    cidr_blocks = ["0.0.0.0/0"]
  }

  egress {
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }

  tags = {
    Name        = "${var.project_name}-${var.environment}-ecs-sg"
    Environment = var.environment
  }
}

resource "aws_lb" "draftly" {
  name               = "${var.project_name}-${var.environment}-nlb"
  internal           = false
  load_balancer_type = "network"

  dynamic "subnet_mapping" {
    for_each = zipmap(var.public_subnet_ids, var.eip_allocation_ids)
    content {
      subnet_id     = subnet_mapping.key
      allocation_id = subnet_mapping.value
    }
  }

  tags = {
    Name        = "${var.project_name}-${var.environment}-nlb"
    Environment = var.environment
  }
}

resource "aws_lb_target_group" "draftly_http" {
  name        = "${var.project_name}-${var.environment}-tg-http"
  port        = 80
  protocol    = "TCP"
  vpc_id      = var.vpc_id
  target_type = "ip"

  health_check {
    protocol            = "TCP"
    healthy_threshold   = 2
    unhealthy_threshold = 3
    interval            = 30
  }

  tags = {
    Name        = "${var.project_name}-${var.environment}-tg-http"
    Environment = var.environment
  }
}

resource "aws_lb_target_group" "draftly_https" {
  name        = "${var.project_name}-${var.environment}-tg-https"
  port        = 443
  protocol    = "TCP"
  vpc_id      = var.vpc_id
  target_type = "ip"

  health_check {
    protocol            = "TCP"
    healthy_threshold   = 2
    unhealthy_threshold = 3
    interval            = 30
  }

  tags = {
    Name        = "${var.project_name}-${var.environment}-tg-https"
    Environment = var.environment
  }
}

resource "aws_lb_listener" "draftly_http" {
  load_balancer_arn = aws_lb.draftly.arn
  port              = "80"
  protocol          = "TCP"

  default_action {
    type             = "forward"
    target_group_arn = aws_lb_target_group.draftly_http.arn
  }

  tags = {
    Name        = "${var.project_name}-${var.environment}-http-listener"
    Environment = var.environment
  }
}

resource "aws_lb_listener" "draftly_https" {
  load_balancer_arn = aws_lb.draftly.arn
  port              = "443"
  protocol          = "TCP"

  default_action {
    type             = "forward"
    target_group_arn = aws_lb_target_group.draftly_https.arn
  }

  tags = {
    Name        = "${var.project_name}-${var.environment}-https-listener"
    Environment = var.environment
  }
}

data "aws_region" "current" {}

resource "aws_cloudwatch_log_group" "ecs" {
  name              = "/ecs/${var.project_name}-${var.environment}"
  retention_in_days = var.environment == "production" ? 30 : 7

  tags = {
    Name        = "${var.project_name}-${var.environment}-logs"
    Environment = var.environment
  }
}

resource "aws_iam_role" "ecs_execution_role" {
  name = "${var.project_name}-${var.environment}-ecs-execution-role"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Action = "sts:AssumeRole"
        Effect = "Allow"
        Principal = {
          Service = "ecs-tasks.amazonaws.com"
        }
      }
    ]
  })

  tags = {
    Name        = "${var.project_name}-${var.environment}-ecs-execution-role"
    Environment = var.environment
  }
}

resource "aws_iam_role_policy_attachment" "ecs_execution_role_policy" {
  role       = aws_iam_role.ecs_execution_role.name
  policy_arn = "arn:aws:iam::aws:policy/service-role/AmazonECSTaskExecutionRolePolicy"
}

resource "aws_iam_role" "ecs_task_role" {
  name = "${var.project_name}-${var.environment}-ecs-task-role"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Action = "sts:AssumeRole"
        Effect = "Allow"
        Principal = {
          Service = "ecs-tasks.amazonaws.com"
        }
      }
    ]
  })

  tags = {
    Name        = "${var.project_name}-${var.environment}-ecs-task-role"
    Environment = var.environment
  }
}

output "ecs_cluster_name" {
  value = aws_ecs_cluster.draftly.name
}

output "ecs_service_name" {
  value = aws_ecs_service.draftly.name
}

output "alb_dns_name" {
  value = aws_lb.draftly.dns_name
}

output "alb_zone_id" {
  value = aws_lb.draftly.zone_id
}
