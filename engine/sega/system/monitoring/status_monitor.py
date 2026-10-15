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
SEGA CROSS-INFRASTRUCTURE STATUS MONITOR
==============================================================================
File: src/sega/monitoring/status_monitor.py
Project: SEGA (Scalable Engineering & Growth Automation)
Copyright: 2022-2025 FLEET
License: Apache-2.0

SEGA MODULE: Monitoring/StatusMonitoring
COMPONENT: Multi-Infrastructure Deployment Health Monitor
PURPOSE: Monitor deployment status across all infrastructure types
DEPENDENCIES: subprocess, json, logging, dataclasses, datetime
USAGE: monitor = StatusMonitor(); deployments = monitor.get_deployments()

This monitor provides comprehensive deployment health checking across Kubernetes,
Ansible nodes, and FPGA targets with structured status reporting.
==============================================================================
"""

import subprocess
import json
import logging
from dataclasses import dataclass
from typing import List, Optional
from datetime import datetime

logger = logging.getLogger(__name__)


@dataclass
class DeploymentStatus:
    name: str
    target: str
    project_type: str
    status: str
    healthy: bool
    health_summary: str
    last_updated: datetime


class StatusMonitor:
    """Monitor deployment status across all infrastructure types."""

    def __init__(self):
        self.monitors = {
            "kubernetes": self._check_k8s_deployments,
            "ansible": self._check_ansible_deployments,
            "fpga": self._check_fpga_deployments,
        }

    def get_deployments(
        self, target_filter: Optional[str] = None
    ) -> List[DeploymentStatus]:
        """Get status of all deployments across infrastructure."""
        all_deployments = []

        for monitor_type, monitor_func in self.monitors.items():
            try:
                deployments = monitor_func()
                if target_filter:
                    deployments = [
                        d for d in deployments if d.target == target_filter
                    ]
                all_deployments.extend(deployments)
            except (
                subprocess.SubprocessError,
                subprocess.TimeoutExpired,
            ) as e:
                logger.error(
                    f"Subprocess error monitoring {monitor_type} deployments: {e}"
                )
                continue
            except (json.JSONDecodeError, KeyError, ValueError) as e:
                logger.error(
                    f"Data parsing error monitoring {monitor_type} deployments: {e}"
                )
                continue
            except (FileNotFoundError, PermissionError) as e:
                logger.error(
                    f"File system error monitoring {monitor_type} deployments: {e}"
                )
                continue
            except (RuntimeError, ValueError, KeyError) as e:
                logger.error(
                    f"Data processing error monitoring {monitor_type} deployments: {e}"
                )
                continue
            except Exception as e:
                logger.error(
                    f"Unexpected error monitoring {monitor_type} deployments: {e}"
                )
                continue

        return sorted(
            all_deployments, key=lambda x: x.last_updated, reverse=True
        )

    def _check_k8s_deployments(self) -> List[DeploymentStatus]:
        """Check Kubernetes deployment status via kubectl."""
        try:
            # Get all deployments in sega namespace
            result = subprocess.run(
                [
                    "kubectl",
                    "get",
                    "deployments",
                    "-n",
                    "sega-deployments",
                    "-o",
                    "json",
                ],
                capture_output=True,
                text=True,
                timeout=30,
            )

            if result.returncode != 0:
                return []

            data = json.loads(result.stdout)
            deployments = []

            for item in data.get("items", []):
                name = item["metadata"]["name"]
                status = item["status"]

                # Extract target from deployment name (sega-{target})
                target = (
                    name.replace("sega-", "")
                    if name.startswith("sega-")
                    else "unknown"
                )

                ready_replicas = status.get("readyReplicas", 0)
                desired_replicas = status.get("replicas", 0)
                healthy = (
                    ready_replicas == desired_replicas and desired_replicas > 0
                )

                deployment_status = DeploymentStatus(
                    name=name,
                    target=target,
                    project_type="kubernetes",
                    status="running" if healthy else "degraded",
                    healthy=healthy,
                    health_summary=f"{ready_replicas}/{desired_replicas} replicas ready",
                    last_updated=datetime.now(),
                )
                deployments.append(deployment_status)

            return deployments

        except (subprocess.SubprocessError, subprocess.TimeoutExpired) as e:
            logger.error(f"Failed to check Kubernetes deployments: {e}")
            return []
        except (json.JSONDecodeError, KeyError) as e:
            logger.error(f"Failed to parse Kubernetes deployment data: {e}")
            return []

    def _check_ansible_deployments(self) -> List[DeploymentStatus]:
        """Check Ansible-managed deployment status."""
        try:
            # Check systemd services on managed nodes
            result = subprocess.run(
                [
                    "ansible",
                    "all",
                    "-i",
                    "./_internal/tooling/_internal/tooling/infrastructure/ansible/host.ini",
                    "-m",
                    "service_facts",
                    "--one-line",
                ],
                capture_output=True,
                text=True,
                timeout=60,
            )

            if result.returncode != 0:
                return []

            deployments = []

            # Parse Ansible output for sega services
            for line in result.stdout.split("\n"):
                if "sega-" in line and "active" in line:
                    # Extract service info from ansible output
                    parts = line.split("|")
                    if len(parts) >= 2:
                        host = parts[0].strip()

                        deployment_status = DeploymentStatus(
                            name=f"sega-service-{host}",
                            target=host,
                            project_type="ansible",
                            status="running",
                            healthy=True,
                            health_summary="Service active",
                            last_updated=datetime.now(),
                        )
                        deployments.append(deployment_status)

            return deployments

        except (subprocess.SubprocessError, subprocess.TimeoutExpired) as e:
            logger.error(f"Failed to check Ansible deployments: {e}")
            return []
        except (ValueError, IndexError) as e:
            logger.error(f"Failed to parse Ansible deployment data: {e}")
            return []

    def _check_fpga_deployments(self) -> List[DeploymentStatus]:
        """Check FPGA programming status."""
        try:
            # Use openFPGALoader to detect programmed devices
            result = subprocess.run(
                ["openFPGALoader", "--detect"],
                capture_output=True,
                text=True,
                timeout=30,
            )

            if result.returncode != 0:
                return []

            deployments = []

            # Parse detected FPGA devices
            for line in result.stdout.split("\n"):
                if "found" in line.lower() and "fpga" in line.lower():
                    # Extract device info
                    device_id = line.split()[-1] if line.split() else "unknown"

                    deployment_status = DeploymentStatus(
                        name=f"fpga-{device_id}",
                        target=device_id,
                        project_type="fpga",
                        status="programmed",
                        healthy=True,
                        health_summary="Device programmed and responding",
                        last_updated=datetime.now(),
                    )
                    deployments.append(deployment_status)

            return deployments

        except (subprocess.SubprocessError, subprocess.TimeoutExpired) as e:
            logger.error(f"Failed to check FPGA deployments: {e}")
            return []
        except (ValueError, IndexError) as e:
            logger.error(f"Failed to parse FPGA deployment data: {e}")
            return []
