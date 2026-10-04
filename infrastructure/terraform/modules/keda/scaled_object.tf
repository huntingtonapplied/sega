# ScaledObject Templates for Simulation Engines
#
# This file provides reusable ScaledObject configurations for each project
# Copy and customize for project-specific deployments
#
# Architecture Reference:
#   /docs/architecture/orchestration/KUBERNETES_AUTOSCALING_ARCHITECTURE.md

# Example ScaledObject for the atlas engine
# Uncomment and customize for deployment
#
# resource "kubernetes_manifest" "atlas_scaler" {
#   count = var.deploy_atlas_scaler ? 1 : 0
#
#   manifest = {
#     apiVersion = "keda.sh/v1alpha1"
#     kind       = "ScaledObject"
#     metadata = {
#       name      = "atlas-engine-scaler"
#       namespace = var.simulations_namespace
#     }
#     spec = {
#       scaleTargetRef = {
#         name = "atlas-engine"
#       }
#       minReplicaCount = 0
#       maxReplicaCount = 10
#       pollingInterval = 15        # Check queue every 15 seconds
#       cooldownPeriod  = 300       # 5 minutes before scale down
#       triggers = [
#         {
#           type = "redis"
#           metadata = {
#             address              = var.redis_url
#             listName             = "simulations:atlas:normal"
#             listLength           = "1"    # 1 job per pod
#             activationListLength = "0"    # Scale from 0 when any job arrives
#           }
#           authenticationRef = {
#             name = "redis-auth"
#           }
#         }
#       ]
#     }
#   }
#
#   depends_on = [helm_release.keda]
# }

# Project-specific ScaledObject configuration
# Each simulation project (atlas, hermes, orion, etc.) needs:
# 1. A Kubernetes Deployment with replicas: 0
# 2. A ScaledObject pointing to that deployment
# 3. A Redis queue (simulations:{project}:{priority})
#
# See /docs/architecture/orchestration/KUBERNETES_AUTOSCALING_ARCHITECTURE.md
# for complete Kubernetes manifests and scaling configurations.
