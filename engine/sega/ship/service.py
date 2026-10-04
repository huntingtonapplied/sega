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
# SEGA MODULE - DEPLOYMENT SERVICE
# ===============================================================
# File: engine/sega/ship/service.py
# Purpose: Deployment service for orchestrating deployments across different platforms
#
# Description: High-level service that coordinates project detection and
# deployment routing. Manages the deployment workflow from project analysis
# to execution, handling both single and multi-project deployment scenarios.
#
# Dependencies:
# - External: pathlib
# - Internal: core.deployment_result, project.project_detector, ship.deployers.deployment_router
#
# Used by: API endpoints, CLI commands, enterprise_orchestrator
#

"""Deployment service for orchestrating deployments across different platforms."""

from typing import Dict, Any, Optional, List
from pathlib import Path
from ..core.deployment_result import DeploymentResult
from ..project.project_detector import ProjectDetector
from .deployers.deployment_router import DeploymentRouter


class DeploymentService:
    """Service for handling deployment operations."""

    def __init__(self):
        self.project_detector = ProjectDetector()
        self.deployment_router = DeploymentRouter()

    def _validate_and_resolve_path(self, path: str) -> Path:
        """Validate and resolve project path to prevent directory traversal."""
        try:
            # Convert to Path object and resolve
            project_path = Path(path).resolve()

            # Ensure the path is absolute
            if not project_path.is_absolute():
                project_path = Path.cwd() / project_path
                project_path = project_path.resolve()

            # Check for directory traversal patterns in original path
            if ".." in str(Path(path)):
                raise ValueError(
                    f"Directory traversal not allowed in path: {path}"
                )

            # Ensure the resolved path exists
            if not project_path.exists():
                raise ValueError(f"Project path does not exist: {path}")

            # Ensure the resolved path is within reasonable bounds
            # (not allowing access to system directories)
            import platform

            if platform.system() == "Windows":
                # Windows system directories
                system_dirs = {
                    "C:\\Windows",
                    "C:\\Program Files",
                    "C:\\Program Files (x86)",
                    "C:\\ProgramData",
                    "C:\\System",
                }
                path_str = str(
                    project_path
                ).upper()  # CBase-insensitive comparison
                for sys_dir in system_dirs:
                    if path_str.startswith(sys_dir.upper()):
                        raise ValueError(
                            f"Access to system directory not allowed: {path}"
                        )
            else:
                # Unix-like system directories (Linux, macOS, BSD)
                system_dirs = {
                    "/etc",
                    "/usr",
                    "/var",
                    "/proc",
                    "/sys",
                    "/dev",
                    "/root",
                    "/bin",
                    "/sbin",
                    "/lib",
                    "/lib64",
                    "/boot",
                }
                # Also check macOS-specific directories
                if platform.system() == "Darwin":
                    system_dirs.update(
                        {"/System", "/Library", "/AApplications"}
                    )

                path_str = str(project_path)
                for sys_dir in system_dirs:
                    if path_str.startswith(sys_dir):
                        raise ValueError(
                            f"Access to system directory not allowed: {path}"
                        )

            return project_path

        except (OSError, ValueError) as e:
            raise ValueError(f"Invalid project path: {e}")

    def deploy_project(
        self,
        project_path: str,
        target: str,
        strategy: str = "rolling",
        force: bool = False,
        dry_run: bool = False,
        domains: list = None,
    ) -> DeploymentResult:
        """Deploy a single project."""
        try:
            # Validate and resolve project path
            try:
                project_dir = self._validate_and_resolve_path(project_path)
            except ValueError as e:
                return DeploymentResult(
                    success=False, error=f"Invalid project path: {str(e)}"
                )

            # Detect project type using a detector instance for this project
            detector = ProjectDetector(str(project_dir))
            project_type = detector.detect()

            # Check if deployment should proceed based on domain filtering
            if domains:
                domain_mapping = {
                    'software': ['web_app', 'service_app', 'api_server'],
                    'embedded': ['firmware_edge', 'embedded_system'],
                    'fpga': ['hdl_fpga', 'fpga_bitstream'],
                    'bare-metal': ['bare_metal', 'hardware_controller']
                }

                # Find which domains this project belongs to
                project_domains = []
                for domain, types in domain_mapping.items():
                    if project_type in types:
                        project_domains.append(domain)

                # Check if any requested domain matches
                if not any(d in domains for d in project_domains):
                    return DeploymentResult(
                        success=True,  # Not an error, just skipped
                        metadata={
                            "project_path": project_path,
                            "project_type": project_type,
                            "skipped": True,
                            "reason": f"Project type '{project_type}' not in requested domains: {domains}"
                        }
                    )

            # Route to appropriate deployer
            result = self.deployment_router.deploy(
                target=target,
                strategy=strategy,
                project_type=project_type,
                force=force,
                dry_run=dry_run,
            )

            # Add project context to result
            result.metadata = result.metadata or {}
            result.metadata.update(
                {
                    "project_path": project_path,
                    "project_type": project_type,
                    "target": target,
                    "strategy": strategy,
                }
            )

            return result

        except Exception as e:
            return DeploymentResult(
                success=False,
                error=f"Deployment failed: {str(e)}",
                metadata={"project_path": project_path},
            )

    def deploy_multiple_projects(
        self,
        projects: List[Dict[str, Any]],
        target: str,
        strategy: str = "rolling",
        parallel: bool = False,
    ) -> Dict[str, DeploymentResult]:
        """Deploy multiple projects."""
        results = {}

        if parallel:
            # Use ThreadPoolExecutor for parallel deployments
            from concurrent.futures import ThreadPoolExecutor
            import concurrent.futures
            import os

            # Configure thread pool size based on system resources
            try:
                max_workers_env = os.getenv("SEGA_MAX_WORKERS")
                if max_workers_env:
                    max_workers_config = int(max_workers_env)
                    if max_workers_config < 1:
                        raise ValueError("Max workers must be at least 1")
                else:
                    max_workers_config = os.cpu_count() or 4
            except (ValueError, TypeError):
                max_workers_config = os.cpu_count() or 4

            max_workers = min(
                len(projects),  # Don't exceed number of projects
                max_workers_config,  # Validated configurable value
                8,  # Cap at 8 to prevent resource exhaustion
            )

            with ThreadPoolExecutor(max_workers=max_workers) as executor:
                future_to_project = {}

                for project in projects:
                    project_key = f"{project['team']}/{project['name']}"
                    future = executor.submit(
                        self.deploy_project,
                        str(project["path"]),
                        target,
                        strategy,
                    )
                    future_to_project[future] = project_key

                # Get timeout from environment or use default
                try:
                    timeout_env = os.getenv("SEGA_DEPLOYMENT_TIMEOUT", "600")
                    timeout_seconds = int(timeout_env)
                    if timeout_seconds < 1:
                        raise ValueError("Timeout must be at least 1 second")
                except (ValueError, TypeError):
                    timeout_seconds = 600  # 10 minutes default

                for future in future_to_project:
                    project_key = future_to_project[future]
                    try:
                        results[project_key] = future.result(
                            timeout=timeout_seconds
                        )
                    except concurrent.futures.TimeoutError:
                        results[project_key] = DeploymentResult(
                            success=False,
                            error=f"Deployment timed out after {timeout_seconds} seconds",
                            metadata={
                                "project_key": project_key,
                                "timeout": timeout_seconds,
                            },
                        )
        else:
            # Sequential deployment
            for project in projects:
                project_key = f"{project['team']}/{project['name']}"
                results[project_key] = self.deploy_project(
                    str(project["path"]), target, strategy
                )

        return results

    def rollback_project(
        self, project_path: str, target: str, to_version: Optional[str] = None
    ) -> DeploymentResult:
        """Rollback a project deployment."""
        try:
            try:
                project_dir = self._validate_and_resolve_path(project_path)
            except ValueError as e:
                return DeploymentResult(
                    success=False, error=f"Invalid project path: {str(e)}"
                )

            # Detect project type without changing directory
            detector = ProjectDetector(str(project_dir))
            project_type = detector.detect()

            # Route to appropriate deployer for rollback with project directory
            result = self.deployment_router.rollback(
                target=target,
                project_type=project_type,
                to_version=to_version,
                project_dir=str(project_dir),
            )

            result.metadata = result.metadata or {}
            result.metadata.update(
                {
                    "project_path": project_path,
                    "project_type": project_type,
                    "target": target,
                    "rollback_version": to_version,
                }
            )

            return result

        except Exception as e:
            return DeploymentResult(
                success=False,
                error=f"Rollback failed: {str(e)}",
                metadata={"project_path": project_path},
            )

    def get_deployment_status(
        self, project_path: str, target: str
    ) -> Dict[str, Any]:
        """Get deployment status for a project."""
        try:
            try:
                project_dir = self._validate_and_resolve_path(project_path)
            except ValueError as e:
                return {"error": f"Invalid project path: {str(e)}"}

            # Detect project type without changing directory
            detector = ProjectDetector(str(project_dir))
            project_type = detector.detect()

            # Get status from deployer with project directory
            return self.deployment_router.get_status(target, project_type, project_dir=str(project_dir))

        except Exception as e:
            return {"error": f"Status check failed: {str(e)}"}


# Global deployment service instance
deployment_service = DeploymentService()
