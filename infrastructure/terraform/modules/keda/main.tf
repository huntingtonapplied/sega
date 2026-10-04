# KEDA Module for Simulation Orchestration
#
# Kubernetes Event-Driven Autoscaling for simulation engine pods
# Scales pods from 0 based on Redis queue depth
#
# Architecture Reference:
#   /docs/architecture/orchestration/KUBERNETES_AUTOSCALING_ARCHITECTURE.md
#   /docs/architecture/orchestration/DISTRIBUTED_JOB_ORCHESTRATION.md
#
# Usage:
#   KEDA monitors Redis queues and scales engine deployments
#   Projects use the shared common/simulation/orchestrator/ library to submit jobs

terraform {
  required_version = ">= 1.0"
  required_providers {
    helm = {
      source  = "hashicorp/helm"
      version = ">= 2.0"
    }
    kubernetes = {
      source  = "hashicorp/kubernetes"
      version = ">= 2.0"
    }
  }
}

# KEDA Operator
resource "helm_release" "keda" {
  name             = "keda"
  repository       = "https://kedacore.github.io/charts"
  chart            = "keda"
  namespace        = var.namespace
  create_namespace = true
  version          = var.keda_version

  set {
    name  = "serviceAccount.create"
    value = "true"
  }

  set {
    name  = "serviceAccount.name"
    value = "keda-operator"
  }

  # Resource limits for KEDA operator
  set {
    name  = "resources.limits.cpu"
    value = var.operator_cpu_limit
  }

  set {
    name  = "resources.limits.memory"
    value = var.operator_memory_limit
  }

  set {
    name  = "resources.requests.cpu"
    value = var.operator_cpu_request
  }

  set {
    name  = "resources.requests.memory"
    value = var.operator_memory_request
  }

  # Prometheus metrics for monitoring
  set {
    name  = "prometheus.metricServer.enabled"
    value = var.enable_prometheus_metrics
  }

  set {
    name  = "prometheus.operator.enabled"
    value = var.enable_prometheus_operator
  }
}

# Redis credentials for KEDA to read queue depth
resource "kubernetes_secret" "redis_credentials" {
  count = var.create_redis_secret ? 1 : 0

  metadata {
    name      = "redis-credentials"
    namespace = var.simulations_namespace
  }

  data = {
    password = var.redis_password
    url      = var.redis_url
  }
}

# TriggerAuthentication for Redis
resource "kubernetes_manifest" "redis_auth" {
  count = var.create_redis_secret ? 1 : 0

  manifest = {
    apiVersion = "keda.sh/v1alpha1"
    kind       = "TriggerAuthentication"
    metadata = {
      name      = "redis-auth"
      namespace = var.simulations_namespace
    }
    spec = {
      secretTargetRef = [
        {
          parameter = "password"
          name      = "redis-credentials"
          key       = "password"
        }
      ]
    }
  }

  depends_on = [helm_release.keda, kubernetes_secret.redis_credentials]
}

# Simulations namespace
resource "kubernetes_namespace" "simulations" {
  count = var.create_simulations_namespace ? 1 : 0

  metadata {
    name = var.simulations_namespace

    labels = {
      "app.kubernetes.io/managed-by" = "sega"
      "purpose"                       = "simulation-orchestration"
    }
  }
}
