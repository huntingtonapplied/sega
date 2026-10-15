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
# SEGA MODULE - ANSIBLE DEPLOYER
# ===============================================================
# File: src/sega/deployers/ansible_deployer.py
# Purpose: Ansible-based deployment for bare-metal and edge devices
#
# Description: Manages deployments to bare-metal servers and edge devices
# using Ansible playbooks. Supports multiple deployment modes including
# systemd services, firmware flashing, and Docker container orchestration.
#
# Dependencies:
# - External: subprocess
# - Internal: core.deployment_result
#
# Used by: deployment_router, deployment_service for edge/bare-metal deployments
#

"""Ansible-based deployment for bare-metal and edge devices."""

import os
import subprocess
from ...core.deployment_result import DeploymentResult

# Resolve the ansible dir from this file's location (sega repo root is 4 levels up
# from ship/deployers/), same pattern as swarm_deployer.py — never cwd-relative.
_THIS_DIR = os.path.dirname(os.path.abspath(__file__))
_ANSIBLE_DIR = os.path.abspath(
    os.path.join(_THIS_DIR, "..", "..", "..", "..", "infrastructure", "ansible")
)


class AnsibleDeployer:
    """Ansible deployment engine for bare-metal and edge targets."""

    def __init__(self, mode: str = "systemd"):
        self.mode = mode  # "systemd", "flash", "docker"
        self.inventory_path = os.path.join(_ANSIBLE_DIR, "host.ini")

    def deploy(
        self,
        target: str,
        strategy: str = "rolling",
        dry_run: bool = False,
        force: bool = False,
    ) -> DeploymentResult:
        """Deploy using Ansible playbooks."""

        try:
            # Select appropriate playbook based on mode
            playbook_map = {
                "systemd": os.path.join(_ANSIBLE_DIR, "03-playbook-setup-node.yml"),
                # NOTE: no firmware/flash playbook exists in infrastructure/ansible/
                # yet; this mode will fail until one is added.
                "flash": os.path.join(_ANSIBLE_DIR, "04-playbook-sega-node.yml"),
                "docker": os.path.join(_ANSIBLE_DIR, "01-playbook-setup-cloud.yml"),
            }

            playbook = playbook_map.get(self.mode, playbook_map["systemd"])

            # Build ansible command
            ansible_cmd = [
                "ansible-playbook",
                "-i",
                self.inventory_path,
                playbook,
                "--limit",
                target,
                "--extra-vars",
                f"deployment_strategy={strategy}",
            ]

            if dry_run:
                ansible_cmd.append("--check")

            if force:
                ansible_cmd.extend(["--extra-vars", "force_deployment=true"])

            # Execute deployment
            result = subprocess.run(
                ansible_cmd,
                capture_output=True,
                text=True,
                timeout=600,  # 10 minutes for hardware operations
            )

            if result.returncode == 0:
                return DeploymentResult(
                    success=True, deployment_id=f"ansible-{target}-{self.mode}"
                )
            else:
                return DeploymentResult(success=False, error=result.stderr)

        except subprocess.TimeoutExpired:
            return DeploymentResult(
                success=False,
                error="Ansible deployment timed out after 10 minutes",
            )
        except Exception as e:
            return DeploymentResult(success=False, error=str(e))
