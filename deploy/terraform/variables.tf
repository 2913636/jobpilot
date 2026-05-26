variable "aws_region" {
  description = "AWS region for deployment"
  type        = string
  default     = "us-east-1"
}

variable "environment" {
  description = "Deployment environment"
  type        = string
  default     = "staging"
  validation {
    condition     = contains(["staging", "production"], var.environment)
    error_message = "environment must be staging or production"
  }
}

variable "domain" {
  description = "Application domain name"
  type        = string
  default     = "jobpilot.example.com"
}

variable "kubernetes_version" {
  description = "EKS cluster K8s version"
  type        = string
  default     = "1.29"
}

variable "node_instance_types" {
  description = "EKS managed node group instance types"
  type        = list(string)
  default     = ["t3.xlarge"]
}

variable "node_min_size" {
  description = "Min nodes per node group"
  type        = number
  default     = 3
}

variable "node_max_size" {
  description = "Max nodes per node group"
  type        = number
  default     = 20
}

variable "node_desired_size" {
  description = "Desired nodes per node group"
  type        = number
  default     = 3
}

variable "create_rds" {
  description = "Create external RDS PostgreSQL"
  type        = bool
  default     = false
}

variable "rds_instance_class" {
  description = "RDS instance type"
  type        = string
  default     = "db.t3.large"
}

variable "create_elasticache" {
  description = "Create external ElastiCache Redis"
  type        = bool
  default     = false
}

variable "redis_node_type" {
  description = "ElastiCache node type"
  type        = string
  default     = "cache.t3.medium"
}

variable "deploy_helm" {
  description = "Deploy JobPilot via Helm after cluster creation"
  type        = bool
  default     = true
}
