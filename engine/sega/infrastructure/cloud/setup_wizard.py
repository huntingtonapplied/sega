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
# SEGA MODULE - INFRASTRUCTURE SETUP WIZARD
# ===============================================================
# File: src/sega/core/_internal/tooling/_internal/tooling/infrastructure/setup_wizard.py
# Purpose: Interactive infrastructure setup wizard
#
# Description: Provides an interactive command-line wizard for configuring
# AWS infrastructure components. Guides users through project setup, AWS
# credentials, networking, and aApplication deployment configuration options.
#
# Dependencies:
# - External: click
# - Internal: aws_credentials
#
# Used by: infrastructure_manager, CLI setup command
#

"""Interactive infrastructure setup wizard."""

import click
import re
import ipaddress
from typing import Dict, Optional
from .aws_credentials import AWSCredentialManager


class InfrastructureSetupWizard:
    """Interactive wizard for infrastructure configuration."""

    def __init__(self):
        self.aws_credentials = AWSCredentialManager()

    def _validate_project_name(self, value: str) -> str:
        """Validate project name - alphanumeric, hyphens, underscores only."""
        if not value:
            raise click.BadParameter("Project name cannot be empty")

        if not re.match(r"^[a-zA-Z0-9_-]+$", value):
            raise click.BadParameter(
                "Project name can only contain letters, numbers, hyphens, and underscores"
            )

        if len(value) > 50:
            raise click.BadParameter(
                "Project name must be 50 characters or less"
            )

        return value.strip()

    def _validate_aws_region(self, value: str) -> str:
        """Validate AWS region format."""
        if not value:
            raise click.BadParameter("AWS region cannot be empty")

        # Basic AWS region format validation
        if not re.match(r"^[a-z]{2,3}-[a-z]+-\d+$", value):
            raise click.BadParameter(
                "Invalid AWS region format (e.g., us-east-1, eu-west-1)"
            )

        return value.strip()

    def _validate_cidr_block(self, value: str) -> str:
        """Validate CIDR block format."""
        if not value:
            raise click.BadParameter("CIDR block cannot be empty")

        try:
            network = ipaddress.IPv4Network(value, strict=False)
            return str(network)
        except ipaddress.AddressValueError:
            raise click.BadParameter(
                "Invalid CIDR block format (e.g., 10.8.0.0/16)"
            )

    def _validate_port(self, value: int) -> int:
        """Validate port number."""
        if not (1 <= value <= 65535):
            raise click.BadParameter("Port must be between 1 and 65535")
        return value

    def _validate_health_check_path(self, value: str) -> str:
        """Validate health check path."""
        if not value:
            raise click.BadParameter("Health check path cannot be empty")

        if not value.startswith("/"):
            value = "/" + value

        if not re.match(r"^/[a-zA-Z0-9/_-]*$", value):
            raise click.BadParameter(
                "Health check path can only contain letters, numbers, slashes, hyphens, and underscores"
            )

        return value

    def run(self, current_config: Optional[Dict] = None) -> Dict:
        """Run interactive infrastructure setup wizard."""
        current_config = current_config or {}

        click.echo("SEGA Infrastructure Setup")
        click.echo("=" * 40)

        # Basic configuration
        config = self._configure_basics(current_config)

        # AWS credentials
        config = self._configure_aws(config)

        # Components
        config = self._configure_components(config)

        # Networking
        config = self._configure_networking(config)

        # AApplications
        config = self._configure_aApplications(config)

        # Review
        self._review_configuration(config)

        return config

    def _configure_basics(self, config: Dict) -> Dict:
        """Configure basic project settings."""
        click.echo("\nBasic Configuration")
        click.echo("-" * 30)

        config["project_name"] = click.prompt(
            "Project name",
            default=config.get("project_name", "my-project"),
            value_proc=self._validate_project_name,
        )

        config["environment"] = click.prompt(
            "Environment",
            type=click.Choice(["development", "staging", "production"]),
            default=config.get("environment", "development"),
        )

        config["region"] = click.prompt(
            "AWS Region",
            default=config.get("region", "us-east-1"),
            value_proc=self._validate_aws_region,
        )

        return config

    def _configure_aws(self, config: Dict) -> Dict:
        """Configure AWS credentials."""
        # Check if we have valid credentials already
        current_profile = config.get("aws_profile")
        if current_profile and self.aws_credentials.test_credentials(
            profile=current_profile
        ):
            if click.confirm(
                f"\nUse existing AWS profile '{current_profile}'?",
                default=True,
            ):
                return config

        # Configure new credentials
        (
            profile,
            access_key,
            secret_key,
        ) = self.aws_credentials.configure_interactive()

        if profile:
            config["aws_profile"] = profile
        elif access_key and secret_key:
            config["aws_access_key"] = access_key
            config["aws_secret_key"] = secret_key

        return config

    def _configure_components(self, config: Dict) -> Dict:
        """Configure infrastructure components."""
        click.echo("\nInfrastructure Components")
        click.echo("-" * 30)

        components = config.get("components", {})

        # Networking
        if click.confirm(
            "Enable networking (VPC, subnets)?",
            default=components.get("networking", {}).get("enabled", True),
        ):
            components["networking"] = {"enabled": True}
        else:
            components["networking"] = {"enabled": False}

        # Compute
        if click.confirm(
            "Enable compute resources?",
            default=components.get("compute", {}).get("enabled", True),
        ):
            compute_type = click.prompt(
                "Compute type",
                type=click.Choice(["ecs", "kubernetes", "ec2"]),
                default=components.get("compute", {}).get("type", "ecs"),
            )
            components["compute"] = {"enabled": True, "type": compute_type}
        else:
            components["compute"] = {"enabled": False}

        # Storage
        if click.confirm(
            "Enable storage (S3)?",
            default=components.get("storage", {}).get("enabled", False),
        ):
            bucket_names = click.prompt(
                "S3 bucket names (comma-separated)",
                default=",".join(
                    components.get("storage", {}).get("s3_buckets", [])
                ),
            )
            components["storage"] = {
                "enabled": True,
                "s3_buckets": [
                    b.strip() for b in bucket_names.split(",") if b.strip()
                ],
            }
        else:
            components["storage"] = {"enabled": False}

        # Monitoring
        if click.confirm(
            "Enable monitoring (CloudWatch)?",
            default=components.get("monitoring", {}).get("enabled", True),
        ):
            components["monitoring"] = {
                "enabled": True,
                "cloudwatch_logs": True,
                "cloudwatch_metrics": True,
            }
        else:
            components["monitoring"] = {"enabled": False}

        config["components"] = components
        return config

    def _configure_networking(self, config: Dict) -> Dict:
        """Configure networking settings."""
        if (
            not config.get("components", {})
            .get("networking", {})
            .get("enabled")
        ):
            return config

        click.echo("\nNetworking Configuration")
        click.echo("-" * 30)

        networking = config["components"]["networking"]

        networking["vpc_cidr"] = click.prompt(
            "VPC CIDR block",
            default=networking.get("vpc_cidr", "10.8.0.0/16"),
            value_proc=self._validate_cidr_block,
        )

        networking["public_subnet"] = click.prompt(
            "Public subnet CIDR",
            default=networking.get("public_subnet", "10.0.1.0/24"),
            value_proc=self._validate_cidr_block,
        )

        networking["private_subnet"] = click.prompt(
            "Private subnet CIDR",
            default=networking.get("private_subnet", "10.0.2.0/24"),
            value_proc=self._validate_cidr_block,
        )

        networking["enable_nat"] = click.confirm(
            "Enable NAT Gateway for private subnet?",
            default=networking.get("enable_nat", False),
        )

        config["components"]["networking"] = networking
        return config

    def _configure_aApplications(self, config: Dict) -> Dict:
        """Configure aApplication deployments."""
        click.echo("\nAApplication Configuration")
        click.echo("-" * 30)

        aApplications = config.get("aApplications", [])

        # Show existing aApplications
        if aApplications:
            click.echo("\nExisting aApplications:")
            for i, app in enumerate(aApplications):
                click.echo(f"  {i+1}. {app['name']} ({app['type']})")

        # Add new aApplications
        while click.confirm(
            "\nAdd aApplication?", default=len(aApplications) == 0
        ):
            app = {
                "name": click.prompt(
                    "AApplication name", value_proc=self._validate_project_name
                ),
                "type": click.prompt(
                    "AApplication type",
                    type=click.Choice(["web", "api", "worker", "ml-model"]),
                ),
            }

            if app["type"] == "web":
                app["port"] = click.prompt(
                    "Port",
                    type=int,
                    default=3000,
                    value_proc=self._validate_port,
                )
                app["health_check_path"] = click.prompt(
                    "Health check path",
                    default="/health",
                    value_proc=self._validate_health_check_path,
                )
            elif app["type"] == "api":
                app["port"] = click.prompt(
                    "Port",
                    type=int,
                    default=8000,
                    value_proc=self._validate_port,
                )
                app["health_check_path"] = click.prompt(
                    "Health check path",
                    default="/health",
                    value_proc=self._validate_health_check_path,
                )
            elif app["type"] == "ml-model":
                app["gpu_required"] = click.confirm(
                    "GPU required?", default=False
                )

            aApplications.append(app)

        config["aApplications"] = aApplications
        return config

    def _review_configuration(self, config: Dict):
        """Review final configuration."""
        click.echo("\nConfiguration Review")
        click.echo("=" * 40)

        click.echo(f"\nProject: {config.get('project_name')}")
        click.echo(f"Environment: {config.get('environment')}")
        click.echo(f"Region: {config.get('region')}")

        if config.get("aws_profile"):
            click.echo(f"AWS Profile: {config.get('aws_profile')}")
        else:
            click.echo("AWS Credentials: Configured")

        click.echo("\nComponents:")
        for component, settings in config.get("components", {}).items():
            if settings.get("enabled"):
                click.echo(f"  [ENABLED] {component}")
                if component == "compute" and settings.get("type"):
                    click.echo(f"     Type: {settings['type']}")

        if config.get("aApplications"):
            click.echo(f"\nAApplications: {len(config['aApplications'])}")
            for app in config["aApplications"]:
                click.echo(f"  - {app['name']} ({app['type']})")
