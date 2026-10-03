#!/usr/bin/env python3
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

"""
SEGA GITLAB RUNNER MANAGER
=============================================================================
Manages GitLab runner registration, configuration, and lifecycle on VPN nodes.
"""

import logging
import subprocess
from typing import Dict, List, Optional, Any
from pathlib import Path

logger = logging.getLogger(__name__)


class RunnerManager:
    """Manages GitLab runners across VPN infrastructure."""

    def __init__(self, gitlab_url: str = "https://gitlab.com/"):
        self.gitlab_url = gitlab_url
        self.runners = {}

    def register_runner(
        self,
        name: str,
        token: str,
        executor: str = "docker",
        tags: Optional[List[str]] = None,
        host: Optional[str] = None,
        **kwargs,
    ) -> Dict[str, Any]:
        """
        Register a new GitLab runner.

        Args:
            name: Runner name
            token: Registration token
            executor: Executor type (docker, shell, kubernetes)
            tags: Runner tags
            host: Remote host to register on (None for local)
            **kwargs: Additional runner configuration

        Returns:
            Registration result
        """
        logger.info(f"Registering GitLab runner: {name}")

        # Build registration command
        cmd = [
            "gitlab-runner",
            "register",
            "--non-interactive",
            "--url",
            self.gitlab_url,
            "--registration-token",
            token,
            "--name",
            name,
            "--executor",
            executor,
        ]

        if tags:
            cmd.extend(["--tag-list", ",".join(tags)])

        # Add executor-specific options
        if executor == "docker":
            cmd.extend(
                [
                    "--docker-image",
                    kwargs.get("docker_image", "alpine:latest"),
                    "--docker-network-mode",
                    "host",  # Access VPN network
                ]
            )
        elif executor == "kubernetes":
            cmd.extend(
                [
                    "--kubernetes-namespace",
                    kwargs.get("namespace", "gitlab-runner"),
                ]
            )

        # Add environment variables
        env_vars = kwargs.get("environment", [])
        for var in env_vars:
            cmd.extend(["--env", var])

        # Execute registration
        try:
            if host:
                # Remote registration
                ssh_cmd = ["ssh", f"root@{host}", " ".join(cmd)]
                result = subprocess.run(
                    ssh_cmd, capture_output=True, text=True
                )
            else:
                # Local registration
                result = subprocess.run(cmd, capture_output=True, text=True)

            if result.returncode == 0:
                runner_info = {
                    "name": name,
                    "executor": executor,
                    "tags": tags or [],
                    "host": host or "localhost",
                    "status": "registered",
                }
                self.runners[name] = runner_info

                logger.info(f"Runner {name} registered successfully")
                return {"status": "success", "runner": runner_info}
            else:
                logger.error(f"Runner registration failed: {result.stderr}")
                return {"status": "failed", "error": result.stderr}

        except Exception as e:
            logger.error(f"Runner registration error: {e}")
            return {"status": "error", "error": str(e)}

    def unregister_runner(self, name: str, host: Optional[str] = None) -> bool:
        """Unregister a GitLab runner."""
        logger.info(f"Unregistering runner: {name}")

        cmd = ["gitlab-runner", "unregister", "--name", name]

        try:
            if host:
                ssh_cmd = ["ssh", f"root@{host}", " ".join(cmd)]
                subprocess.run(ssh_cmd, check=True)
            else:
                subprocess.run(cmd, check=True)

            if name in self.runners:
                del self.runners[name]

            logger.info(f"Runner {name} unregistered")
            return True

        except Exception as e:
            logger.error(f"Failed to unregister runner: {e}")
            return False

    def configure_runner(
        self, name: str, config: Dict[str, Any], host: Optional[str] = None
    ) -> bool:
        """Update runner configuration."""
        logger.info(f"Configuring runner: {name}")

        # Generate config.toml content
        config_content = self._generate_runner_config(name, config)

        try:
            if host:
                # Remote configuration
                ssh_cmd = [
                    "ssh",
                    f"root@{host}",
                    f"echo '{config_content}' > /etc/gitlab-runner/config.toml",
                ]
                subprocess.run(ssh_cmd, check=True)
            else:
                # Local configuration
                config_path = Path("/etc/gitlab-runner/config.toml")
                config_path.write_text(config_content)

            # Restart runner
            restart_cmd = ["gitlab-runner", "restart"]
            if host:
                subprocess.run(
                    ["ssh", f"root@{host}", " ".join(restart_cmd)], check=True
                )
            else:
                subprocess.run(restart_cmd, check=True)

            logger.info(f"Runner {name} configured")
            return True

        except Exception as e:
            logger.error(f"Failed to configure runner: {e}")
            return False

    def list_runners(self, host: Optional[str] = None) -> List[Dict[str, Any]]:
        """List all registered runners."""
        cmd = ["gitlab-runner", "list"]

        try:
            if host:
                result = subprocess.run(
                    ["ssh", f"root@{host}", " ".join(cmd)],
                    capture_output=True,
                    text=True,
                )
            else:
                result = subprocess.run(cmd, capture_output=True, text=True)

            # Parse runner list
            runners = self._parse_runner_list(result.stdout)
            return runners

        except Exception as e:
            logger.error(f"Failed to list runners: {e}")
            return []

    def get_runner_status(
        self, name: str, host: Optional[str] = None
    ) -> Dict[str, Any]:
        """Get runner status and metrics."""
        cmd = ["gitlab-runner", "verify", "--name", name]

        try:
            if host:
                result = subprocess.run(
                    ["ssh", f"root@{host}", " ".join(cmd)],
                    capture_output=True,
                    text=True,
                )
            else:
                result = subprocess.run(cmd, capture_output=True, text=True)

            is_alive = result.returncode == 0

            return {
                "name": name,
                "status": "alive" if is_alive else "dead",
                "host": host or "localhost",
                "output": result.stdout,
            }

        except Exception as e:
            return {"name": name, "status": "error", "error": str(e)}

    def deploy_runner_cluster(
        self,
        cluster_name: str,
        token: str,
        hosts: List[str],
        executor: str = "docker",
        replicas_per_host: int = 1,
    ) -> Dict[str, Any]:
        """Deploy a cluster of runners across multiple hosts."""
        logger.info(f"Deploying runner cluster: {cluster_name}")

        results = []

        for host in hosts:
            for i in range(replicas_per_host):
                runner_name = f"{cluster_name}-{host.replace('.', '-')}-{i}"

                result = self.register_runner(
                    name=runner_name,
                    token=token,
                    executor=executor,
                    tags=[cluster_name, "vpn", "distributed"],
                    host=host,
                    environment=[
                        "SEGA_ENDPOINT=http://10.0.2.10:8000",
                        f"RUNNER_CLUSTER={cluster_name}",
                    ],
                )

                results.append(
                    {"runner": runner_name, "host": host, "result": result}
                )

        successful = [r for r in results if r["result"]["status"] == "success"]

        return {
            "status": "success"
            if len(successful) == len(results)
            else "partial",
            "cluster": cluster_name,
            "total_runners": len(results),
            "successful": len(successful),
            "results": results,
        }

    def scale_runner_cluster(
        self, cluster_name: str, target_replicas: int
    ) -> Dict[str, Any]:
        """Scale a runner cluster up or down."""
        # Get current runners in cluster
        current_runners = [
            (name, info)
            for name, info in self.runners.items()
            if cluster_name in info.get("tags", [])
        ]

        current_count = len(current_runners)

        if target_replicas > current_count:
            # Scale up - would need cluster info to add more
            return {
                "status": "not_implemented",
                "message": "Scale up requires cluster configuration",
            }

        elif target_replicas < current_count:
            # Scale down
            to_remove = current_count - target_replicas
            removed = []

            for i in range(to_remove):
                name, info = current_runners[i]
                if self.unregister_runner(name, info.get("host")):
                    removed.append(name)

            return {
                "status": "success",
                "scaled_to": target_replicas,
                "removed": removed,
            }

        return {"status": "no_change", "current_replicas": current_count}

    def _generate_runner_config(
        self, name: str, config: Dict[str, Any]
    ) -> str:
        """Generate GitLab runner config.toml content."""
        # This is a simplified version - in production use proper TOML library
        return f"""concurrent = {config.get('concurrent', 10)}
check_interval = {config.get('check_interval', 3)}
log_level = "{config.get('log_level', 'info')}"

[session_server]
  session_timeout = {config.get('session_timeout', 1800)}

[[runners]]
  name = "{name}"
  url = "{self.gitlab_url}"
  token = "{config.get('token', 'TOKEN_PLACEHOLDER')}"
  executor = "{config.get('executor', 'docker')}"
  environment = {config.get('environment', [])}
  
  [runners.docker]
    image = "{config.get('docker_image', 'alpine:latest')}"
    network_mode = "host"
    privileged = {str(config.get('privileged', False)).lower()}
    volumes = {config.get('volumes', [])}"""

    def _parse_runner_list(self, output: str) -> List[Dict[str, Any]]:
        """Parse gitlab-runner list output."""
        runners = []
        lines = output.strip().split("\n")

        for line in lines:
            if "=" in line and "Executor" in line:
                # Parse runner info line
                parts = line.split()
                if len(parts) >= 2:
                    name = parts[0]
                    executor = None
                    status = "unknown"

                    # Extract executor
                    if "Executor=" in line:
                        executor = line.split("Executor=")[1].split()[0]

                    # Extract status
                    if "status=" in line:
                        status = line.split("status=")[1].split()[0]

                    runners.append(
                        {"name": name, "executor": executor, "status": status}
                    )

        return runners
