# ============================================================
# JobPilot Terraform Module - AWS EKS Cluster
# ============================================================

terraform {
  required_version = ">= 1.5"
  required_providers {
    aws = { source = "hashicorp/aws", version = "~> 5.0" }
    kubernetes = { source = "hashicorp/kubernetes", version = "~> 2.27" }
    helm = { source = "hashicorp/helm", version = "~> 2.13" }
    random = { source = "hashicorp/random", version = "~> 3.6" }
  }

  backend "s3" {
    bucket = "jobpilot-terraform-state"
    key    = "terraform.tfstate"
    region = "us-east-1"
  }
}

provider "aws" {
  region = var.aws_region
}

data "aws_availability_zones" "available" {}
data "aws_caller_identity" "current" {}

locals {
  cluster_name = "jobpilot-${var.environment}"
  vpc_cidr     = "10.0.0.0/16"

  common_tags = {
    Project     = "JobPilot"
    Environment = var.environment
    ManagedBy   = "Terraform"
  }
}

# ── Network ───────────────────────────────────────────────────────

module "vpc" {
  source  = "terraform-aws-modules/vpc/aws"
  version = "5.5.2"

  name = local.cluster_name
  cidr = local.vpc_cidr

  azs             = slice(data.aws_availability_zones.available.names, 0, 3)
  private_subnets = [for i in range(3) : cidrsubnet(local.vpc_cidr, 8, i)]
  public_subnets  = [for i in range(3) : cidrsubnet(local.vpc_cidr, 8, i + 3)]

  enable_nat_gateway     = true
  single_nat_gateway     = var.environment != "production"
  enable_dns_hostnames   = true
  enable_dns_support     = true

  public_subnet_tags  = { "kubernetes.io/role/elb" = "1" }
  private_subnet_tags = { "kubernetes.io/role/internal-elb" = "1" }

  tags = local.common_tags
}

# ── EKS Cluster ───────────────────────────────────────────────────

module "eks" {
  source  = "terraform-aws-modules/eks/aws"
  version = "19.21.0"

  cluster_name    = local.cluster_name
  cluster_version = var.kubernetes_version

  vpc_id     = module.vpc.vpc_id
  subnet_ids = module.vpc.private_subnets

  cluster_endpoint_public_access  = true
  cluster_endpoint_private_access = true

  enable_irsa = true

  cluster_addons = {
    coredns    = { most_recent = true }
    kube-proxy = { most_recent = true }
    vpc-cni    = { most_recent = true }
    aws-ebs-csi-driver = { most_recent = true }
  }

  eks_managed_node_groups = {
    main = {
      name           = "${local.cluster_name}-main"
      instance_types = var.node_instance_types
      min_size       = var.node_min_size
      max_size       = var.node_max_size
      desired_size   = var.node_desired_size

      disk_size = 100
      disk_type = "gp3"

      tags = local.common_tags
    }
    gpu = {
      name           = "${local.cluster_name}-gpu"
      instance_types = ["g5.xlarge"]
      min_size       = var.environment == "production" ? 1 : 0
      max_size       = 4
      desired_size   = var.environment == "production" ? 1 : 0

      labels = { "nvidia.com/gpu" = "true" }
      taints = [{ key = "nvidia.com/gpu", value = "true", effect = "NO_SCHEDULE" }]
      tags   = local.common_tags
    }
  }

  tags = local.common_tags
}

# ── RDS PostgreSQL (optional - external DB) ───────────────────────

resource "aws_db_subnet_group" "postgres" {
  count = var.create_rds ? 1 : 0
  name       = "${local.cluster_name}-postgres"
  subnet_ids = module.vpc.private_subnets
  tags       = local.common_tags
}

resource "aws_db_instance" "postgres" {
  count = var.create_rds ? 1 : 0

  identifier     = "${local.cluster_name}-postgres"
  engine         = "postgres"
  engine_version = "15"
  instance_class = var.rds_instance_class

  db_name  = "jobpilot"
  username = "jobpilot_admin"
  password = random_password.db_password[0].result

  allocated_storage     = 100
  max_allocated_storage = 500
  storage_encrypted     = true
  storage_type          = "gp3"

  db_subnet_group_name   = aws_db_subnet_group.postgres[0].name
  vpc_security_group_ids = [aws_security_group.rds[0].id]

  backup_retention_period = 30
  backup_window           = "03:00-04:00"
  maintenance_window      = "sun:05:00-sun:06:00"

  deletion_protection = var.environment == "production"
  skip_final_snapshot = var.environment != "production"

  tags = local.common_tags
}

resource "random_password" "db_password" {
  count   = var.create_rds ? 1 : 0
  length  = 32
  special = false
}

resource "aws_security_group" "rds" {
  count  = var.create_rds ? 1 : 0
  name   = "${local.cluster_name}-rds"
  vpc_id = module.vpc.vpc_id

  ingress {
    from_port       = 5432
    to_port         = 5432
    protocol        = "tcp"
    security_groups = [module.eks.cluster_primary_security_group_id]
  }

  tags = local.common_tags
}

# ── S3 for MinIO Alternative ──────────────────────────────────────

resource "aws_s3_bucket" "data_lake" {
  bucket = "${local.cluster_name}-datalake-${data.aws_caller_identity.current.account_id}"
  force_destroy = var.environment != "production"
  tags = local.common_tags
}

# ── ElastiCache Redis ─────────────────────────────────────────────

resource "aws_elasticache_cluster" "redis" {
  count = var.create_elasticache ? 1 : 0

  cluster_id      = "${local.cluster_name}-redis"
  engine          = "redis"
  node_type       = var.redis_node_type
  num_cache_nodes = 1
  port            = 6379

  subnet_group_name  = aws_elasticache_subnet_group.redis[0].name
  security_group_ids = [aws_security_group.redis[0].id]

  tags = local.common_tags
}

resource "aws_elasticache_subnet_group" "redis" {
  count      = var.create_elasticache ? 1 : 0
  name       = "${local.cluster_name}-redis"
  subnet_ids = module.vpc.private_subnets
}

resource "aws_security_group" "redis" {
  count  = var.create_elasticache ? 1 : 0
  name   = "${local.cluster_name}-redis"
  vpc_id = module.vpc.vpc_id

  ingress {
    from_port       = 6379
    to_port         = 6379
    protocol        = "tcp"
    security_groups = [module.eks.cluster_primary_security_group_id]
  }

  tags = local.common_tags
}

# ── Enhanced RDS: Multi-AZ + Encryption + Monitoring ──────────────

resource "aws_db_instance" "postgres_ha" {
  count = var.create_rds && var.environment == "production" ? 1 : 0

  identifier     = "${local.cluster_name}-postgres-ha"
  engine         = "postgres"
  engine_version = "15"
  instance_class = var.rds_instance_class

  db_name  = "jobpilot"
  username = "jobpilot_admin"
  password = random_password.db_password_ha[0].result

  allocated_storage     = 200
  max_allocated_storage = 1000
  storage_encrypted     = true
  storage_type          = "gp3"
  multi_az              = true

  db_subnet_group_name   = aws_db_subnet_group.postgres[0].name
  vpc_security_group_ids = [aws_security_group.rds[0].id]

  backup_retention_period = 35
  backup_window           = "03:00-04:00"
  maintenance_window      = "sun:05:00-sun:06:00"
  copy_tags_to_snapshot   = true
  deletion_protection     = true

  enabled_cloudwatch_logs_exports = ["postgresql", "upgrade"]
  performance_insights_enabled    = true
  performance_insights_retention_period = 7
  monitoring_interval              = 60
  monitoring_role_arn              = aws_iam_role.rds_monitoring[0].arn

  tags = local.common_tags
}

resource "random_password" "db_password_ha" {
  count   = var.create_rds && var.environment == "production" ? 1 : 0
  length  = 32
  special = false
}

resource "aws_iam_role" "rds_monitoring" {
  count = var.create_rds && var.environment == "production" ? 1 : 0
  name  = "${local.cluster_name}-rds-monitoring"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect = "Allow"
      Principal = { Service = "monitoring.rds.amazonaws.com" }
      Action = "sts:AssumeRole"
    }]
  })

  managed_policy_arns = ["arn:aws:iam::aws:policy/service-role/AmazonRDSEnhancedMonitoringRole"]
  tags                = local.common_tags
}

# ── Enhanced ElastiCache: Cluster Mode ────────────────────────────

resource "aws_elasticache_replication_group" "redis_cluster" {
  count = var.create_elasticache ? 1 : 0

  replication_group_id = "${local.cluster_name}-redis"
  description          = "JobPilot Redis cluster"
  engine               = "redis"
  engine_version       = "7.1"
  node_type            = var.redis_node_type
  port                 = 6379

  num_cache_clusters         = var.environment == "production" ? 3 : 2
  automatic_failover_enabled = true
  multi_az_enabled           = var.environment == "production"

  subnet_group_name  = aws_elasticache_subnet_group.redis[0].name
  security_group_ids = [aws_security_group.redis[0].id]

  at_rest_encryption_enabled  = true
  transit_encryption_enabled  = true
  auth_token_enabled          = var.environment == "production"

  snapshot_retention_limit = var.environment == "production" ? 7 : 0
  snapshot_window          = "04:00-05:00"
  maintenance_window       = "sun:06:00-sun:07:00"
  auto_minor_version_upgrade = true

  apply_immediately = var.environment != "production"

  tags = local.common_tags
}

resource "random_password" "redis_auth" {
  count   = var.create_elasticache ? 1 : 0
  length  = 32
  special = false
}

# ── S3: Versioning + Encryption + Security Policy ────────────────

resource "aws_s3_bucket_versioning" "data_lake" {
  bucket = aws_s3_bucket.data_lake.id
  versioning_configuration {
    status = "Enabled"
  }
}

resource "aws_s3_bucket_server_side_encryption_configuration" "data_lake" {
  bucket = aws_s3_bucket.data_lake.id
  rule {
    apply_server_side_encryption_by_default {
      sse_algorithm = "aws:kms"
    }
  }
}

resource "aws_s3_bucket_public_access_block" "data_lake" {
  bucket = aws_s3_bucket.data_lake.id

  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}

resource "aws_s3_bucket_lifecycle_configuration" "data_lake" {
  bucket = aws_s3_bucket.data_lake.id
  rule {
    id     = "expire-old-versions"
    status = "Enabled"
    noncurrent_version_expiration {
      noncurrent_days = 90
    }
    abort_incomplete_multipart_upload {
      days_after_initiation = 7
    }
  }
}

resource "aws_s3_bucket_policy" "data_lake" {
  bucket = aws_s3_bucket.data_lake.id
  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect    = "Deny"
        Principal = "*"
        Action    = "s3:*"
        Resource  = ["${aws_s3_bucket.data_lake.arn}/*", aws_s3_bucket.data_lake.arn]
        Condition = {
          Bool = { "aws:SecureTransport": "false" }
        }
      }
    ]
  })
}

# ── Helm Deploy ───────────────────────────────────────────────────

provider "helm" {
  kubernetes {
    host                   = module.eks.cluster_endpoint
    cluster_ca_certificate = base64decode(module.eks.cluster_certificate_authority_data)
    exec {
      api_version = "client.authentication.k8s.io/v1beta1"
      args        = ["eks", "get-token", "--cluster-name", local.cluster_name]
      command     = "aws"
    }
  }
}

resource "helm_release" "jobpilot" {
  count      = var.deploy_helm ? 1 : 0
  name       = "jobpilot"
  chart      = "${path.root}/../helm/jobpilot"
  namespace  = "jobpilot"
  create_namespace = true

  values = [
    templatefile("${path.root}/../helm/jobpilot/values.yaml", {
      environment = var.environment
      domain      = var.domain
    })
  ]

  set {
    name  = "postgres.auth.password"
    value = var.create_rds ? random_password.db_password[0].result : "jobpilot_secret"
  }

  depends_on = [module.eks.eks_managed_node_groups]
}
