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
# SEGA MODULE - INFRASTRUCTURE MANAGER
# ===============================================================
# File: src/sega/core/infrastructure_manager.py
# Purpose: Orchestrates infrastructure management using specialized components
#
# Description: Infrastructure manager that coordinates configuration,
# AWS credentials, Terraform operations, and status monitoring through focused
# component managers. Provides high-level interface for infrastructure lifecycle.
#
# Dependencies:
# - External: click, pathlib
# - Internal: cloud.* (config_manager, aws_credentials, terraform_manager, etc.)
#
# Used by: CLI commands, deployment_service, API infrastructure endpoints
#

"""Infrastructure manager using focused components."""

import click
from pathlib import Path
from typing import Dict, Optional

from ..infrastructure.cloud.config_manager import InfrastructureConfigManager
from ..infrastructure.cloud.aws_credentials import AWSCredentialManager
from ..infrastructure.cloud.terraform_manager import TerraformManager
from ..infrastructure.cloud.setup_wizard import InfrastructureSetupWizard
from ..infrastructure.cloud.status_checker import InfrastructureStatusChecker


class InfrastructureManager:
    """Orchestrates infrastructure management using specialized components."""

    def __init__(self, workspace_root: Optional[str] = None):
        self.workspace_root = Path(workspace_root) if workspace_root else Path.cwd()

        # Initialize specialized managers
        self.config_manager = InfrastructureConfigManager(self.workspace_root)
        self.aws_credentials = AWSCredentialManager()
        self.terraform_manager = TerraformManager(self.workspace_root)
        self.setup_wizard = InfrastructureSetupWizard()
        self.status_checker = None  # Initialized after AWS auth

    def interactive_setup(self) -> Dict:
        """Run interactive infrastructure configuration setup."""
        # Load current config
        current_config = self.config_manager.load()

        # Run setup wizard
        new_config = self.setup_wizard.run(current_config)

        # Save configuration
        self.config_manager.save(new_config)

        return new_config

    def provision_infrastructure(self, config: Optional[Dict] = None, dry_run: bool = False) -> Dict:
        """Provision infrastructure based on configuration."""
        # Load config if not provided
        if config is None:
            config = self.config_manager.load()

        if not config:
            click.echo(" No infrastructure configuration found. Run setup first.")
            return {"success": False, "errors": ["No configuration found"]}

        # Ensure AWS credentials are configured
        if not self._ensure_aws_auth(config):
            return {"success": False, "errors": ["AWS authentication failed"]}

        click.echo("\n Provisioning Infrastructure")
        click.echo("=" * 40)

        # Generate Terraform configuration
        tf_config = self.terraform_manager.generate_config(config)

        # Write Terraform files
        tf_dir = self.terraform_manager.write_config(tf_config)

        # Execute Terraform
        result = self.terraform_manager.execute(tf_dir, dry_run=dry_run)

        # Update config with outputs if successful
        if result["success"] and result.get("outputs"):
            config["terraform_outputs"] = result["outputs"]
            self.config_manager.save(config)

        return result

    def get_infrastructure_status(self, config: Optional[Dict] = None) -> Dict:
        """Get current infrastructure status."""
        # Load config if not provided
        if config is None:
            config = self.config_manager.load()

        if not config:
            return {
                "overall": "not_configured",
                "message": "No infrastructure configuration found",
            }

        # Ensure AWS credentials are configured
        if not self._ensure_aws_auth(config):
            return {"overall": "error", "message": "AWS authentication failed"}

        # Check infrastructure status
        return self.status_checker.check_status(config)

    def destroy_infrastructure(self, config: Optional[Dict] = None) -> Dict:
        """Destroy provisioned infrastructure."""
        # Load config if not provided
        if config is None:
            config = self.config_manager.load()

        if not config:
            click.echo(" No infrastructure configuration found.")
            return {"success": False, "errors": ["No configuration found"]}

        # Ensure AWS credentials are configured
        if not self._ensure_aws_auth(config):
            return {"success": False, "errors": ["AWS authentication failed"]}

        click.echo("\n Destroying Infrastructure")
        click.echo("=" * 40)
        click.echo("  WARNING: This will destroy all provisioned resources!")

        if not click.confirm("\nAre you sure you want to destroy the infrastructure?"):
            return {"success": False, "errors": ["Destruction cancelled"]}

        # Execute terraform destroy
        tf_dir = self.terraform_manager.terraform_dir
        if not tf_dir.exists():
            return {
                "success": False,
                "errors": ["Terraform directory not found"],
            }

        try:
            import subprocess

            destroy_result = subprocess.run(
                ["terraform", "destroy", "-auto-approve"],
                cwd=tf_dir,
                capture_output=True,
                text=True,
            )

            if destroy_result.returncode == 0:
                click.echo("\n Infrastructure destroyed successfully!")
                return {"success": True}
            else:
                return {
                    "success": False,
                    "errors": [f"Terraform destroy failed: {destroy_result.stderr}"],
                }

        except FileNotFoundError:
            return {"success": False, "errors": ["Terraform not found"]}
        except Exception as e:
            return {"success": False, "errors": [str(e)]}

    def load_infrastructure_config(self) -> Optional[Dict]:
        """Load infrastructure configuration. Facade over config_manager.load()."""
        return self.config_manager.load()

    def _ensure_aws_auth(self, config: Dict) -> bool:
        """Ensure AWS credentials are configured and valid."""
        # Test with profile if available
        if config.get("aws_profile"):
            if self.aws_credentials.test_credentials(profile=config["aws_profile"]):
                self.status_checker = InfrastructureStatusChecker(self.aws_credentials.aws_session)
                return True

        # Test with keys if available
        if config.get("aws_access_key") and config.get("aws_secret_key"):
            if self.aws_credentials.test_credentials(
                access_key=config["aws_access_key"],
                secret_key=config["aws_secret_key"],
            ):
                self.status_checker = InfrastructureStatusChecker(self.aws_credentials.aws_session)
                return True

        # Try default credentials
        if self.aws_credentials.test_credentials():
            self.status_checker = InfrastructureStatusChecker(self.aws_credentials.aws_session)
            return True

        click.echo(" AWS credentials not configured or invalid")
        return False
