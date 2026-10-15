# EKS Module Outputs
#
# These outputs are used by other modules (e.g., KEDA) and deployments

output "cluster_name" {
  description = "Name of the EKS cluster"
  value       = module.eks.cluster_name
}

output "cluster_endpoint" {
  description = "Endpoint for the EKS cluster API"
  value       = module.eks.cluster_endpoint
}

output "cluster_certificate_authority_data" {
  description = "Base64 encoded certificate data for the cluster"
  value       = module.eks.cluster_certificate_authority_data
}

output "cluster_arn" {
  description = "ARN of the EKS cluster"
  value       = module.eks.cluster_arn
}

output "cluster_oidc_issuer_url" {
  description = "OIDC issuer URL for the cluster (for IRSA)"
  value       = module.eks.cluster_oidc_issuer_url
}

output "cluster_oidc_provider_arn" {
  description = "ARN of the OIDC provider for the cluster"
  value       = module.eks.oidc_provider_arn
}

output "cluster_security_group_id" {
  description = "Security group ID attached to the EKS cluster"
  value       = module.eks.cluster_security_group_id
}

output "node_security_group_id" {
  description = "Security group ID attached to the EKS nodes"
  value       = module.eks.node_security_group_id
}

# Kubernetes provider configuration
output "cluster_auth_token" {
  description = "Token for authenticating with the cluster"
  value       = data.aws_eks_cluster_auth.cluster.token
  sensitive   = true
}

# Node group outputs
output "general_node_group_arn" {
  description = "ARN of the general purpose node group"
  value       = module.eks.eks_managed_node_groups["general"].node_group_arn
}

output "gpu_node_group_arn" {
  description = "ARN of the GPU node group"
  value       = module.eks.eks_managed_node_groups["gpu"].node_group_arn
}
