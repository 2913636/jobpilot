output "cluster_endpoint" {
  description = "EKS cluster endpoint"
  value       = module.eks.cluster_endpoint
}

output "cluster_name" {
  description = "EKS cluster name"
  value       = module.eks.cluster_name
}

output "cluster_security_group_id" {
  description = "Security group ID for cluster"
  value       = module.eks.cluster_primary_security_group_id
}

output "configure_kubectl" {
  description = "Command to configure kubectl"
  value       = "aws eks update-kubeconfig --name ${module.eks.cluster_name} --region ${var.aws_region}"
}

output "rds_endpoint" {
  description = "RDS PostgreSQL endpoint"
  value       = var.create_rds ? aws_db_instance.postgres[0].endpoint : null
}

output "redis_endpoint" {
  description = "ElastiCache Redis endpoint"
  value       = var.create_elasticache ? aws_elasticache_cluster.redis[0].cache_nodes[0].address : null
}

output "data_lake_bucket" {
  description = "S3 data lake bucket name"
  value       = aws_s3_bucket.data_lake.id
}

output "vpc_id" {
  description = "VPC ID"
  value       = module.vpc.vpc_id
}

output "helm_deploy_status" {
  description = "Helm release status"
  value       = var.deploy_helm ? helm_release.jobpilot[0].status : "not deployed"
}

output "rds_ha_endpoint" {
  description = "RDS multi-AZ endpoint (production)"
  value       = var.create_rds && var.environment == "production" ? aws_db_instance.postgres_ha[0].endpoint : null
}

output "elasticache_cluster_endpoint" {
  description = "ElastiCache Redis cluster endpoint"
  value       = var.create_elasticache ? aws_elasticache_replication_group.redis_cluster[0].primary_endpoint_address : null
}

output "s3_bucket_versioning" {
  description = "S3 bucket versioning status"
  value       = aws_s3_bucket_versioning.data_lake.versioning_configuration[0].status
}
