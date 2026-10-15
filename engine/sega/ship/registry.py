#!/usr/bin/env python3
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

"""
SEGA Registry Deployer Module
==============================================================================
File: src/sega/deployment/registry_deployer.py
Project: SEGA (Scalable Engineering & Growth Automation)
Copyright: 2022-2025 FLEET
License: Apache-2.0

SEGA MODULE: Deployment/RegistryDeployer
COMPONENT: Docker Registry Deployment Manager
PURPOSE: Deploy FLEET projects from GitLab Container Registry or any Docker registry
DEPENDENCIES: subprocess, pathlib, logging

Consolidated from scripts/deploy/gitlab_registry_deploy.sh
==============================================================================
"""

import subprocess
import logging
import time
from pathlib import Path
from typing import Optional, Dict, List, Any
from dataclasses import dataclass

logger = logging.getLogger(__name__)


# Default project list for registry deployment.
#
# Curated subset of the portfolio (not a config predicate); sourced from the
# `[fleet] registry_projects` config list. Ships empty for new installs.
def _registry_projects() -> List[str]:
    from sega.core.config import get_config
    return list(get_config().fleet.registry_projects)


FLEET_PROJECTS = _registry_projects()

# Default port mappings per the Port Allocation Standards.
# AUTHORITATIVE: /docs/standards/infrastructure/PORT_ALLOCATION_STANDARDS.md
#
# The API port for each configured registry project is read from the central
# config (`config.get_project(name).ports.api`), i.e. the standardized
# `8000 + project_id`; the key set is the `[fleet] registry_projects` list so
# that the port fallback behaviour in `_get_project_port` is preserved exactly.
def _default_ports() -> Dict[str, int]:
    from sega.core.config import get_config
    c = get_config()
    ports: Dict[str, int] = {}
    for _name in FLEET_PROJECTS:
        _proj = c.get_project(_name)
        if _proj is not None:
            ports[_name] = _proj.ports.api
    return ports


DEFAULT_PORTS = _default_ports()


@dataclass
class DeploymentConfig:
    """Configuration for registry deployment."""
    registry: str = "registry.example.com/fleet"
    version: str = "latest"
    environment: str = "production"
    network: str = "fleet-network"
    data_root: str = "/opt/fleet/data"
    config_root: str = "/opt/fleet/config"


class RegistryDeployer:
    """Deploy FLEET projects from Docker registries."""

    def __init__(self, config: Optional[DeploymentConfig] = None):
        self.config = config or DeploymentConfig()

    def _run_command(self, cmd: List[str], capture: bool = True) -> subprocess.CompletedProcess:
        """Run a shell command with proper error handling."""
        logger.debug(f"Running: {' '.join(cmd)}")
        return subprocess.run(
            cmd,
            capture_output=capture,
            text=True
        )

    def _ensure_network(self) -> bool:
        """Ensure Docker network exists."""
        result = self._run_command(["docker", "network", "ls", "--format", "{{.Name}}"])
        if self.config.network not in result.stdout:
            logger.info(f"Creating Docker network: {self.config.network}")
            create_result = self._run_command(["docker", "network", "create", self.config.network])
            return create_result.returncode == 0
        return True

    def _ensure_directories(self) -> None:
        """Ensure data and config directories exist."""
        Path(self.config.data_root).mkdir(parents=True, exist_ok=True)
        Path(self.config.config_root).mkdir(parents=True, exist_ok=True)

    def _get_project_port(self, project: str, env_file: Optional[Path] = None) -> int:
        """Get port for project from env file or defaults."""
        # Try to read from env file
        if env_file and env_file.exists():
            try:
                content = env_file.read_text()
                for line in content.splitlines():
                    if line.startswith("API_PORT="):
                        return int(line.split("=")[1].strip())
            except (ValueError, IOError):
                pass

        # Fall back to default
        return DEFAULT_PORTS.get(project, 3000)

    def _get_env_file(self, project: str) -> Optional[Path]:
        """Get environment file path for project."""
        paths = [
            Path(self.config.config_root) / project / ".env",
            Path(f"/opt/fleet/{project}/.env"),
        ]
        for path in paths:
            if path.exists():
                return path
        return None

    def pull_image(self, project: str, version: Optional[str] = None) -> bool:
        """Pull Docker image from registry."""
        ver = version or self.config.version
        image = f"{self.config.registry}/{project}:{ver}"

        logger.info(f"Pulling image: {image}")
        result = self._run_command(["docker", "pull", image])

        if result.returncode != 0:
            logger.error(f"Failed to pull {image}: {result.stderr}")
            return False

        logger.info(f"Successfully pulled {image}")
        return True

    def stop_container(self, project: str) -> bool:
        """Stop and remove existing container."""
        container_name = f"fleet-{project}"

        # Check if container exists
        result = self._run_command(
            ["docker", "ps", "-q", "-f", f"name={container_name}"]
        )

        if result.stdout.strip():
            logger.info(f"Stopping container: {container_name}")
            self._run_command(["docker", "stop", container_name])
            self._run_command(["docker", "rm", container_name])

        return True

    def deploy_project(
        self,
        project: str,
        version: Optional[str] = None,
        dry_run: bool = False
    ) -> Dict[str, Any]:
        """Deploy a single project from registry."""
        ver = version or self.config.version
        image = f"{self.config.registry}/{project}:{ver}"
        container_name = f"fleet-{project}"

        result = {
            "project": project,
            "version": ver,
            "image": image,
            "success": False,
            "message": "",
        }

        if dry_run:
            result["success"] = True
            result["message"] = f"DRY RUN: Would deploy {image}"
            return result

        # Pull image
        if not self.pull_image(project, ver):
            result["message"] = f"Failed to pull image {image}"
            return result

        # Stop existing container
        self.stop_container(project)

        # Get configuration
        env_file = self._get_env_file(project)
        port = self._get_project_port(project, env_file)
        data_dir = Path(self.config.data_root) / project
        data_dir.mkdir(parents=True, exist_ok=True)

        # Build run command
        run_cmd = [
            "docker", "run", "-d",
            "--name", container_name,
            "--restart", "unless-stopped",
            "--network", self.config.network,
            "-p", f"{port}:{port}",
            "-v", f"{data_dir}:/app/data",
        ]

        # Add env file if exists
        if env_file:
            run_cmd.extend(["--env-file", str(env_file)])

        run_cmd.append(image)

        logger.info(f"Starting {project} on port {port}")
        run_result = self._run_command(run_cmd)

        if run_result.returncode != 0:
            result["message"] = f"Failed to start container: {run_result.stderr}"
            return result

        # Health check
        time.sleep(5)
        if self.health_check(project, port):
            result["success"] = True
            result["message"] = f"Successfully deployed {project}"
            result["port"] = port
        else:
            result["success"] = True  # Container started, but health check failed
            result["message"] = f"Deployed {project} but health check failed"
            result["port"] = port
            result["warning"] = "Health check failed"

        return result

    def health_check(self, project: str, port: int) -> bool:
        """Check if deployed container is healthy."""
        try:
            import urllib.request
            url = f"http://localhost:{port}/health"
            with urllib.request.urlopen(url, timeout=5) as response:
                return response.status == 200
        except Exception:
            return False

    def deploy_all(
        self,
        version: Optional[str] = None,
        projects: Optional[List[str]] = None,
        dry_run: bool = False
    ) -> Dict[str, Dict[str, Any]]:
        """Deploy all or specified fleet projects."""
        self._ensure_network()
        self._ensure_directories()

        project_list = projects or FLEET_PROJECTS
        results = {}

        for project in project_list:
            logger.info(f"Deploying {project}...")
            results[project] = self.deploy_project(project, version, dry_run)
            if not dry_run:
                time.sleep(2)  # Brief pause between deployments

        return results

    def get_status(self) -> Dict[str, Dict[str, Any]]:
        """Get status of all FLEET containers."""
        result = self._run_command([
            "docker", "ps",
            "--filter", "name=fleet-",
            "--format", "{{.Names}}\t{{.Status}}\t{{.Ports}}"
        ])

        status = {}
        for line in result.stdout.strip().splitlines():
            if line:
                parts = line.split("\t")
                name = parts[0].replace("fleet-", "")
                status[name] = {
                    "running": True,
                    "status": parts[1] if len(parts) > 1 else "unknown",
                    "ports": parts[2] if len(parts) > 2 else "",
                }

        # Add projects not running
        for project in FLEET_PROJECTS:
            if project not in status:
                status[project] = {
                    "running": False,
                    "status": "not running",
                    "ports": "",
                }

        return status


def deploy_from_registry(
    project: str,
    version: str = "latest",
    registry: str = "registry.example.com/fleet",
    environment: str = "production",
    dry_run: bool = False
) -> Dict[str, Any]:
    """Convenience function for single project deployment."""
    config = DeploymentConfig(
        registry=registry,
        version=version,
        environment=environment
    )
    deployer = RegistryDeployer(config)
    return deployer.deploy_project(project, version, dry_run)


def deploy_all_from_registry(
    version: str = "latest",
    registry: str = "registry.example.com/fleet",
    projects: Optional[List[str]] = None,
    dry_run: bool = False
) -> Dict[str, Dict[str, Any]]:
    """Convenience function for multi-project deployment."""
    config = DeploymentConfig(registry=registry, version=version)
    deployer = RegistryDeployer(config)
    return deployer.deploy_all(version, projects, dry_run)
