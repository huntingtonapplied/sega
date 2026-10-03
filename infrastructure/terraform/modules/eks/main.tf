# EKS Module for Simulation Orchestration
#
# This module provisions an EKS cluster with GPU-enabled node groups
# for simulation engine orchestration (atlas, hermes, orion, etc.)
#
# Architecture Reference:
#   /docs/architecture/orchestration/KUBERNETES_AUTOSCALING_ARCHITECTURE.md
#   /docs/architecture/orchestration/DISTRIBUTED_JOB_ORCHESTRATION.md
#
# Usage:
#   Projects contain orchestration code (the shared common/simulation/orchestrator/ library)
#   SEGA provisions the infrastructure that orchestration runs on

terraform {
  required_version = ">= 1.0"
  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = ">= 5.0"
    }
    kubernetes = {
      source  = "hashicorp/kubernetes"
      version = ">= 2.0"
    }
    helm = {
      source  = "hashicorp/helm"
      version = ">= 2.0"
    }
  }
}

# EKS Cluster
module "eks" {
  source  = "terraform-aws-modules/eks/aws"
  version = "~> 19.0"

  cluster_name    = var.cluster_name
  cluster_version = var.cluster_version

  vpc_id     = var.vpc_id
  subnet_ids = var.private_subnet_ids

  # Cluster access
  cluster_endpoint_public_access  = var.cluster_endpoint_public_access
  cluster_endpoint_private_access = true

  # Enable IRSA for service accounts (required for KEDA, Cluster Autoscaler)
  enable_irsa = true

  eks_managed_node_groups = {
    # General purpose nodes for backends, monitoring, Redis, etc.
    general = {
      name           = "general"
      instance_types = var.general_instance_types
      min_size       = var.general_min_size
      max_size       = var.general_max_size
      desired_size   = var.general_desired_size

      labels = {
        role = "general"
      }
    }

    # GPU nodes for simulation engines (scale to zero capable)
    gpu = {
      name           = "gpu"
      instance_types = var.gpu_instance_types
      min_size       = var.gpu_min_size  # 0 for scale-to-zero
      max_size       = var.gpu_max_size
      desired_size   = var.gpu_desired_size

      # GPU nodes require taints to prevent non-GPU workloads
      taints = [{
        key    = "nvidia.com/gpu"
        value  = "true"
        effect = "NO_SCHEDULE"
      }]

      labels = {
        role             = "gpu"
        "nvidia.com/gpu" = "true"
      }

      # Enable GPU support with Amazon Linux 2 GPU AMI
      ami_type = "AL2_x86_64_GPU"
    }
  }

  # Cluster addons
  cluster_addons = {
    coredns = {
      most_recent = true
    }
    kube-proxy = {
      most_recent = true
    }
    vpc-cni = {
      most_recent = true
    }
  }

  tags = merge(var.tags, {
    "karpenter.sh/discovery" = var.cluster_name
  })
}

# Cluster Autoscaler - scales EC2 nodes based on pending pods
resource "helm_release" "cluster_autoscaler" {
  count = var.enable_cluster_autoscaler ? 1 : 0

  name       = "cluster-autoscaler"
  repository = "https://kubernetes.github.io/autoscaler"
  chart      = "cluster-autoscaler"
  namespace  = "kube-system"
  version    = var.cluster_autoscaler_version

  set {
    name  = "autoDiscovery.clusterName"
    value = module.eks.cluster_name
  }

  set {
    name  = "awsRegion"
    value = var.aws_region
  }

  # Scale down unneeded nodes after 10 minutes
  set {
    name  = "extraArgs.scale-down-unneeded-time"
    value = var.scale_down_unneeded_time
  }

  set {
    name  = "extraArgs.scale-down-delay-after-add"
    value = var.scale_down_delay_after_add
  }

  depends_on = [module.eks]
}

# NVIDIA Device Plugin - enables GPU scheduling in Kubernetes
resource "helm_release" "nvidia_device_plugin" {
  count = var.enable_nvidia_device_plugin ? 1 : 0

  name       = "nvidia-device-plugin"
  repository = "https://nvidia.github.io/k8s-device-plugin"
  chart      = "nvidia-device-plugin"
  namespace  = "kube-system"
  version    = var.nvidia_device_plugin_version

  depends_on = [module.eks]
}

# Kubernetes provider configuration
data "aws_eks_cluster_auth" "cluster" {
  name = module.eks.cluster_name
}
