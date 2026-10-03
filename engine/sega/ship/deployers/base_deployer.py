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
# SEGA MODULE - Base Deployer
# ===============================================================
# File: src/sega/deployers/base_deployer.py
# Purpose: Provides base class and common patterns for all deployers
#
# Description: Abstract base class defining the common interface and
# functionality for all SEGA deployers. Includes project detection,
# resource management, and standardized deployment lifecycle methods.
#
# Dependencies:
# - External: abc, typing, time
# - Internal: sega.core.deployment_result, sega.detectors.project_detector, sega.utils.resource_manager
#
# Used by: All specific deployers (K8s, ECS, Ansible, FPGA)
#

import time
from abc import ABC, abstractmethod
from typing import Dict, Any, Optional
from ...core.deployment_result import DeploymentResult
from ...project.project_detector import ProjectDetector
from ...utils.resource_manager import ResourceManager


class BaseDeployer(ABC):
    """Base class for all deployers with common functionality."""

    def __init__(self):
        self.project_detector = ProjectDetector()
        self.resource_manager = ResourceManager()

    @abstractmethod
    def deploy(
        self,
        target: str,
        strategy: str = "rolling",
        image_tag: str = "latest",
        force: bool = False,
        dry_run: bool = False,
    ) -> DeploymentResult:
        """Deploy to target environment."""
        pass

    @abstractmethod
    def get_deployment_status(self, target: str) -> Dict[str, Any]:
        """Get deployment status."""
        pass

    def rollback(
        self, target: str, to_version: Optional[str] = None
    ) -> DeploymentResult:
        """Rollback deployment (default implementation)."""
        return DeploymentResult(
            success=False, error="Rollback not implemented for this deployer"
        )

    def _create_deployment_result(
        self,
        success: bool,
        message: str,
        deployment_id: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
        error: Optional[str] = None,
    ) -> DeploymentResult:
        """Create a deployment result with common fields."""
        if not deployment_id:
            deployment_id = (
                f"{self.__class__.__name__.lower()}-{int(time.time())}"
            )

        return DeploymentResult(
            success=success,
            message=message,
            deployment_id=deployment_id,
            start_time=time.time(),
            metadata=metadata or {},
            error=error if not success else None,
        )

    def _validate_target(self, target: str) -> bool:
        """Validate deployment target."""
        valid_targets = ["development", "staging", "production", "prod"]
        return target.lower() in valid_targets

    def _validate_strategy(self, strategy: str) -> bool:
        """Validate deployment strategy."""
        valid_strategies = ["rolling", "blue-green", "canary", "recreate"]
        return strategy.lower() in valid_strategies

    def _get_project_config(
        self, project_path: Optional[str] = None
    ) -> Dict[str, Any]:
        """Get project configuration for deployment."""
        if project_path:
            detector = ProjectDetector(project_path)
        else:
            detector = self.project_detector

        project_type = detector.detect()
        config = detector.get_build_config()

        return {
            "project_type": project_type,
            "build_config": config,
            "components": detector.get_components(),
            "metadata": detector.get_fleet_metadata(),
        }

    def _prepare_deployment_environment(
        self, target: str, config: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Prepare deployment environment variables and settings."""
        env_vars = {
            "ENVIRONMENT": target.upper(),
            "PROJECT_TYPE": config.get("project_type", "unknown"),
            "DEPLOYMENT_ID": f"deploy-{int(time.time())}",
            "DEPLOYMENT_TIME": time.strftime(
                "%Y-%m-%d %H:%M:%S UTC", time.gmtime()
            ),
        }

        # Add project-specific environment variables
        if config.get("build_config", {}).get("environment"):
            env_vars.update(config["build_config"]["environment"])

        return env_vars

    def _handle_pre_deployment_hooks(self, config: Dict[str, Any]) -> bool:
        """Execute pre-deployment hooks."""
        hooks = config.get("build_config", {}).get("pre_deploy_hooks", [])

        for hook in hooks:
            result = self.resource_manager.run_subprocess(
                hook if isinstance(hook, list) else hook.split(), timeout=300
            )

            if result.returncode != 0:
                return False

        return True

    def _handle_post_deployment_hooks(
        self, config: Dict[str, Any], deployment_result: DeploymentResult
    ) -> bool:
        """Execute post-deployment hooks."""
        hooks = config.get("build_config", {}).get("post_deploy_hooks", [])

        for hook in hooks:
            # Replace deployment variables in hooks
            if isinstance(hook, str):
                hook = hook.replace(
                    "${DEPLOYMENT_ID}", deployment_result.deployment_id
                )
                hook = hook.replace(
                    "${DEPLOYMENT_SUCCESS}", str(deployment_result.success)
                )
                hook_cmd = hook.split()
            else:
                hook_cmd = hook

            result = self.resource_manager.run_subprocess(
                hook_cmd, timeout=300
            )

            if result.returncode != 0:
                return False

        return True

    def _wait_for_health_check(
        self, health_check_url: str, timeout: int = 300, interval: int = 10
    ) -> bool:
        """Wait for service to pass health checks."""
        import requests

        start_time = time.time()

        while time.time() - start_time < timeout:
            try:
                response = requests.get(health_check_url, timeout=5)
                if response.status_code == 200:
                    return True
            except requests.RequestException:
                pass

            time.sleep(interval)

        return False

    def _get_image_tag(self, strategy: str = "latest") -> str:
        """Generate or determine image tag for deployment."""
        if strategy == "latest":
            return "latest"
        elif strategy == "timestamp":
            return f"deploy-{int(time.time())}"
        elif strategy == "git":
            # Try to get git commit hash
            result = self.resource_manager.run_subprocess(
                ["git", "rev-parse", "--short", "HEAD"], timeout=10
            )
            if result.returncode == 0 and result.stdout.strip():
                return result.stdout.strip()
            return "latest"
        else:
            return strategy  # Assume it's already a tag

    def _log_deployment_event(self, event: str, details: Dict[str, Any]):
        """Log deployment events for audit trail."""
        # This could be extended to send to centralized logging
        import logging

        logger = logging.getLogger(
            f"{self.__class__.__module__}.{self.__class__.__name__}"
        )
        logger.info(f"Deployment event: {event}", extra=details)

    def _cleanup_deployment_resources(self):
        """Clean up any resources created during deployment."""
        self.resource_manager.cleanup_all()


class ContainerBaseDeployer(BaseDeployer):
    """Base class for container-based deployers (ECS, Kubernetes, etc.)."""

    def _build_container_image(
        self,
        image_name: str,
        image_tag: str,
        dockerfile_path: str = "Dockerfile",
    ) -> bool:
        """Build container image."""
        build_cmd = [
            "docker",
            "build",
            "-t",
            f"{image_name}:{image_tag}",
            "-f",
            dockerfile_path,
            ".",
        ]

        result = self.resource_manager.run_subprocess(build_cmd, timeout=1200)
        return result.returncode == 0

    def _push_container_image(self, image_name: str, image_tag: str) -> bool:
        """Push container image to registry."""
        push_cmd = ["docker", "push", f"{image_name}:{image_tag}"]

        result = self.resource_manager.run_subprocess(push_cmd, timeout=600)
        return result.returncode == 0

    def _get_container_logs(self, container_id: str, lines: int = 100) -> str:
        """Get container logs."""
        logs_cmd = ["docker", "logs", "--tail", str(lines), container_id]

        result = self.resource_manager.run_subprocess(logs_cmd, timeout=30)
        return result.stdout if result.returncode == 0 else ""


class ServerlessBaseDeployer(BaseDeployer):
    """Base class for serverless deployers (Lambda, etc.)."""

    def _package_function(self, function_path: str, package_name: str) -> str:
        """Package function for serverless deployment."""
        import zipfile
        import os

        package_path = f"{package_name}.zip"

        with zipfile.ZipFile(package_path, "w", zipfile.ZIP_DEFLATED) as zipf:
            for root, dirs, files in os.walk(function_path):
                for file in files:
                    file_path = os.path.join(root, file)
                    arcname = os.path.relpath(file_path, function_path)
                    zipf.write(file_path, arcname)

        return package_path

    def _upload_function_package(
        self, package_path: str, function_name: str
    ) -> bool:
        """Upload function package (implementation depends on provider)."""
        # This would be implemented by specific serverless deployers
        raise NotImplementedError("Subclasses must implement package upload")
