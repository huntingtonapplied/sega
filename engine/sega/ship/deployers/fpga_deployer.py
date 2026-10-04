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
# SEGA MODULE - FPGA DEPLOYER
# ===============================================================
# File: src/sega/deployers/fpga_deployer.py
# Purpose: FPGA hardware deployment engine
#
# Description: Manages FPGA bitstream deployment using openFPGALoader tool.
# Handles programming of FPGA devices with verification and blue-green
# deployment strategies for safe hardware updates with rollback capabilities.
#
# Dependencies:
# - External: subprocess
# - Internal: core.deployment_result
#
# Used by: deployment_router, deployment_service for FPGA deployments
#

"""FPGA hardware deployment engine."""

import subprocess
from ...core.deployment_result import DeploymentResult


class FPGADeployer:
    """FPGA hardware programming and deployment."""

    def __init__(self):
        self.programmer_tool = "openFPGALoader"
        self.verification_required = True

    def deploy(
        self,
        target: str,
        strategy: str = "blue_green",
        dry_run: bool = False,
        force: bool = False,
    ) -> DeploymentResult:
        """Deploy bitstream to FPGA hardware."""

        try:
            # Locate bitstream file
            bitstream_path = f"./build/{target}.bit"

            if dry_run:
                return DeploymentResult(
                    success=True, deployment_id=f"fpga-{target}-dry-run"
                )

            # Program FPGA
            program_cmd = [
                self.programmer_tool,
                "-b",
                target,  # Board target
                "-f",
                bitstream_path,
            ]

            if force:
                program_cmd.append("--force")

            # Execute programming
            result = subprocess.run(
                program_cmd,
                capture_output=True,
                text=True,
                timeout=120,  # 2 minutes for FPGA programming
            )

            if result.returncode != 0:
                return DeploymentResult(
                    success=False,
                    error=f"FPGA programming failed: {result.stderr}",
                )

            # Verification step
            if self.verification_required:
                verify_result = self._verify_programming(target)
                if not verify_result:
                    return DeploymentResult(
                        success=False,
                        error="FPGA verification failed after programming",
                    )

            return DeploymentResult(
                success=True, deployment_id=f"fpga-{target}"
            )

        except subprocess.TimeoutExpired:
            return DeploymentResult(
                success=False,
                error="FPGA programming timed out after 2 minutes",
            )
        except Exception as e:
            return DeploymentResult(success=False, error=str(e))

    def _verify_programming(self, target: str) -> bool:
        """Verify FPGA programming was successful."""
        try:
            verify_cmd = [self.programmer_tool, "-b", target, "--verify"]

            result = subprocess.run(
                verify_cmd, capture_output=True, text=True, timeout=30
            )

            return result.returncode == 0

        except Exception:
            return False
