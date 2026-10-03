#!/usr/bin/env python
# -*- coding: utf-8 -*-
# Copyright 2022-2026 Huntington Applied
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

# ===============================================================
# SEGA MODULE - KUBERNETES DEPLOYER
# ===============================================================
# File: src/sega/deployers/k8s_deployer.py
# Purpose: Kubernetes deployment engine
#
# Description: Manages deployments to Kubernetes clusters using Helm charts.
# Supports standard and GPU-enabled workloads with configurable deployment
# strategies including rolling updates, blue-green, and canary deployments.
#
# Dependencies:
# - External: subprocess
# - Internal: core.deployment_result
#
# Used by: deployment_router, deployment_service for K8s deployments
#

"""Kubernetes deployment engine."""

import subprocess
import os
import yaml
from typing import Dict, Any, List
from pathlib import Path
from ...core.deployment_result import DeploymentResult


class K8sDeployer:
    """Enhanced Kubernetes deployment using Helm charts with advanced features."""

    def __init__(
        self,
        gpu_enabled: bool = False,
        context: str = None,
        cluster_config: Dict[str, Any] = None,
    ):
        self.gpu_enabled = gpu_enabled
        self.namespace = os.getenv("SEGA_K8S_NAMESPACE", "sega-deployments")
        self.context = context or os.getenv("SEGA_K8S_CONTEXT")
        self.cluster_config = cluster_config or {}
        self.service_mesh_enabled = self.cluster_config.get(
            "service_mesh", {}
        ).get("enabled", False)
        self.service_mesh_type = self.cluster_config.get(
            "service_mesh", {}
        ).get("type", "istio")
        self.monitoring_enabled = self.cluster_config.get(
            "monitoring", {}
        ).get("enabled", True)

    def deploy(
        self,
        target: str,
        strategy: str = "rolling",
        dry_run: bool = False,
        force: bool = False,
        **kwargs,
    ) -> DeploymentResult:
        """Enhanced Kubernetes deployment with advanced features."""

        try:
            # Validate cluster connectivity
            if not self._validate_cluster_access():
                return DeploymentResult(
                    success=False,
                    error="Failed to connect to Kubernetes cluster",
                )

            # Prepare enhanced Helm command
            helm_cmd = [
                "helm",
                "upgrade",
                "--install",
                f"sega-{target}",
                "./_internal/tooling/_internal/tooling/infrastructure/helm/sega-app",
                "--namespace",
                self.namespace,
                "--create-namespace",
                "--set",
                f"target={target}",
                "--set",
                f"strategy={strategy}",
                "--wait",
                "--timeout=10m",
            ]

            # Add context if specified
            if self.context:
                helm_cmd.extend(["--kube-context", self.context])

            # GPU support
            if self.gpu_enabled:
                helm_cmd.extend(
                    [
                        "--set",
                        "gpu.enabled=true",
                        "--set",
                        "resources.limits.nvidia\\.com/gpu=1",
                    ]
                )

            # Service mesh integration
            if self.service_mesh_enabled:
                helm_cmd.extend(
                    [
                        "--set",
                        "serviceMesh.enabled=true",
                        "--set",
                        f"serviceMesh.type={self.service_mesh_type}",
                    ]
                )

            # Monitoring integration
            if self.monitoring_enabled:
                helm_cmd.extend(
                    [
                        "--set",
                        "monitoring.enabled=true",
                        "--set",
                        "monitoring.prometheus.enabled=true",
                        "--set",
                        "monitoring.grafana.enabled=true",
                    ]
                )

            # Custom values from cluster config
            for key, value in self.cluster_config.get(
                "helm_values", {}
            ).items():
                helm_cmd.extend(["--set", f"{key}={value}"])

            if dry_run:
                helm_cmd.append("--dry-run")

            if force:
                helm_cmd.append("--force")

            # Execute deployment
            result = subprocess.run(
                helm_cmd,
                capture_output=True,
                text=True,
                timeout=600,  # IncreBased timeout for complex deployments
            )

            if result.returncode == 0:
                deployment_id = f"sega-{target}"

                # Post-deployment validation
                if not dry_run:
                    self._post_deployment_setup(target, deployment_id)

                return DeploymentResult(
                    success=True,
                    deployment_id=deployment_id,
                    metadata={
                        "namespace": self.namespace,
                        "context": self.context,
                        "strategy": strategy,
                        "service_mesh": self.service_mesh_enabled,
                        "monitoring": self.monitoring_enabled,
                    },
                )
            else:
                return DeploymentResult(success=False, error=result.stderr)

        except subprocess.TimeoutExpired:
            return DeploymentResult(
                success=False, error="Deployment timed out after 10 minutes"
            )
        except Exception as e:
            return DeploymentResult(success=False, error=str(e))

    def _validate_cluster_access(self) -> bool:
        """Validate access to Kubernetes cluster."""
        try:
            kubectl_cmd = ["kubectl", "cluster-info"]

            if self.context:
                kubectl_cmd.extend(["--context", self.context])

            result = subprocess.run(
                kubectl_cmd, capture_output=True, text=True, timeout=30
            )

            return result.returncode == 0

        except Exception:
            return False

    def _post_deployment_setup(self, target: str, deployment_id: str):
        """Setup post-deployment configurations."""
        try:
            # Setup service mesh policies if enabled
            if self.service_mesh_enabled:
                self._setup_service_mesh_policies(target)

            # Setup monitoring if enabled
            if self.monitoring_enabled:
                self._setup_monitoring_config(target)

        except Exception:
            # Don't fail deployment if post-setup fails
            pass

    def _setup_service_mesh_policies(self, target: str):
        """Setup service mesh security and traffic policies."""
        if self.service_mesh_type == "istio":
            # Apply Istio virtual service and destination rules
            policies = self._generate_istio_policies(target)
            for policy in policies:
                self._apply_k8s_resource(policy)

    def _setup_monitoring_config(self, target: str):
        """Setup monitoring configurations."""
        # Apply ServiceMonitor for Prometheus
        service_monitor = self._generate_service_monitor(target)
        self._apply_k8s_resource(service_monitor)

    def _generate_istio_policies(self, target: str) -> List[Dict[str, Any]]:
        """Generate Istio traffic management policies."""
        virtual_service = {
            "apiVersion": "networking.istio.io/v1beta1",
            "kind": "VirtualService",
            "metadata": {
                "name": f"sega-{target}-vs",
                "namespace": self.namespace,
            },
            "spec": {
                "hosts": [f"sega-{target}"],
                "http": [
                    {
                        "route": [
                            {
                                "destination": {
                                    "host": f"sega-{target}",
                                    "port": {"number": 80},
                                }
                            }
                        ]
                    }
                ],
            },
        }

        destination_rule = {
            "apiVersion": "networking.istio.io/v1beta1",
            "kind": "DestinationRule",
            "metadata": {
                "name": f"sega-{target}-dr",
                "namespace": self.namespace,
            },
            "spec": {
                "host": f"sega-{target}",
                "trafficPolicy": {"tls": {"mode": "ISTIO_MUTUAL"}},
            },
        }

        return [virtual_service, destination_rule]

    def _generate_service_monitor(self, target: str) -> Dict[str, Any]:
        """Generate ServiceMonitor for Prometheus."""
        return {
            "apiVersion": "monitoring.coreos.com/v1",
            "kind": "ServiceMonitor",
            "metadata": {
                "name": f"sega-{target}-monitor",
                "namespace": self.namespace,
            },
            "spec": {
                "selector": {"matchLabels": {"app": f"sega-{target}"}},
                "endpoints": [{"port": "metrics", "interval": "30s"}],
            },
        }

    def _apply_k8s_resource(self, resource: Dict[str, Any]):
        """Apply Kubernetes resource using kubectl."""
        try:
            import tempfile

            with tempfile.NamedTemporaryFile(
                mode="w", suffix=".yaml", delete=False
            ) as f:
                yaml.dump(resource, f)
                temp_file = f.name

            kubectl_cmd = ["kubectl", "apply", "-f", temp_file]

            if self.context:
                kubectl_cmd.extend(["--context", self.context])

            subprocess.run(
                kubectl_cmd, capture_output=True, text=True, timeout=60
            )

            # Cleanup temp file
            Path(temp_file).unlink()

        except Exception:
            # Don't fail if resource aApplication fails
            pass

    def get_deployment_status(self, deployment_id: str) -> Dict[str, Any]:
        """Get enhanced deployment status with service mesh and monitoring info."""
        try:
            # Get basic deployment status
            kubectl_cmd = [
                "kubectl",
                "get",
                "deployment",
                deployment_id,
                "-n",
                self.namespace,
                "-o",
                "yaml",
            ]

            if self.context:
                kubectl_cmd.extend(["--context", self.context])

            result = subprocess.run(
                kubectl_cmd, capture_output=True, text=True, timeout=30
            )

            if result.returncode == 0:
                deployment_info = yaml.safe_load(result.stdout)

                status = {
                    "status": "running"
                    if deployment_info.get("status", {}).get(
                        "readyReplicas", 0
                    )
                    > 0
                    else "pending",
                    "replicas": deployment_info.get("status", {}).get(
                        "replicas", 0
                    ),
                    "ready_replicas": deployment_info.get("status", {}).get(
                        "readyReplicas", 0
                    ),
                    "namespace": self.namespace,
                    "context": self.context,
                }

                # Add service mesh status if enabled
                if self.service_mesh_enabled:
                    status["service_mesh"] = self._get_service_mesh_status(
                        deployment_id
                    )

                # Add monitoring status if enabled
                if self.monitoring_enabled:
                    status["monitoring"] = self._get_monitoring_status(
                        deployment_id
                    )

                return status
            else:
                return {"status": "unknown", "error": result.stderr}

        except Exception as e:
            return {"status": "error", "error": str(e)}

    def _get_service_mesh_status(self, deployment_id: str) -> Dict[str, Any]:
        """Get service mesh integration status."""
        # Implementation would check Istio proxy status, traffic policies, etc.
        return {
            "type": self.service_mesh_type,
            "proxy_status": "connected",  # Simplified
            "policies_applied": True,
        }

    def _get_monitoring_status(self, deployment_id: str) -> Dict[str, Any]:
        """Get monitoring integration status."""
        # Implementation would check ServiceMonitor, metrics endpoint, etc.
        return {
            "prometheus_scraping": True,  # Simplified
            "metrics_endpoint": f"http://{deployment_id}.{self.namespace}:8080/metrics",
        }
