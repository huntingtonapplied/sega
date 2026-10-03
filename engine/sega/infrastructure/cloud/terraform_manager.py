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
# SEGA MODULE - TERRAFORM MANAGER
# ===============================================================
# File: src/sega/core/_internal/tooling/_internal/tooling/infrastructure/terraform_manager.py
# Purpose: Terraform configuration generation and execution
#
# Description: Generates Terraform configurations from SEGA infrastructure
# specifications and manages Terraform execution lifecycle. Supports AWS
# resource provisioning for VPC, EKS, ECS, and other cloud components.
#
# Dependencies:
# - External: subprocess, tempfile, shutil, click, pathlib
# - Internal: None (generates standalone Terraform configurations)
#
# Used by: infrastructure_manager, CLI infrastructure commands
#

"""Terraform configuration generation and execution."""

import json
import logging
import subprocess
import click
from pathlib import Path
from typing import Dict, Any, Optional

logger = logging.getLogger(__name__)


class TerraformManager:
    """Manages Terraform configuration generation and execution."""

    def __init__(self, workspace_root: Optional[Path] = None):
        self.workspace_root = (
            Path(workspace_root) if workspace_root else Path.cwd()
        )
        self.terraform_dir = self.workspace_root / ".sega" / "terraform"

    def generate_config(self, infrastructure_config: Dict) -> Dict:
        """Generate Terraform configuration from infrastructure settings."""
        tf_config = {
            "terraform": {
                "required_providers": {
                    "aws": {"source": "hashicorp/aws", "version": "~> 5.0"}
                }
            },
            "provider": {
                "aws": {
                    "region": infrastructure_config.get("region", "us-east-1")
                }
            },
            "variable": {},
            "resource": {},
            "output": {},
        }

        # Add AWS profile if specified
        if infrastructure_config.get("aws_profile"):
            tf_config["provider"]["aws"]["profile"] = infrastructure_config[
                "aws_profile"
            ]

        # Generate resources based on components
        components = infrastructure_config.get("components", {})

        if components.get("networking", {}).get("enabled"):
            self._add_networking_resources(tf_config, components["networking"])

        if components.get("compute", {}).get("enabled"):
            self._add_compute_resources(
                tf_config, components["compute"], infrastructure_config
            )

        if components.get("storage", {}).get("enabled"):
            self._add_storage_resources(tf_config, components["storage"])

        if components.get("monitoring", {}).get("enabled"):
            self._add_monitoring_resources(tf_config, components["monitoring"])

        return tf_config

    def _add_networking_resources(
        self, tf_config: Dict, networking_config: Dict
    ):
        """Add networking resources to Terraform config."""
        tf_config["resource"]["aws_vpc"] = {
            "main": {
                "cidr_block": networking_config.get("vpc_cidr", "10.8.0.0/16"),
                "enable_dns_hostnames": True,
                "enable_dns_support": True,
                "tags": {"Name": "sega-vpc", "ManagedBy": "SEGA"},
            }
        }

        tf_config["resource"]["aws_subnet"] = {
            "public": {
                "vpc_id": "${aws_vpc.main.id}",
                "cidr_block": networking_config.get(
                    "public_subnet", "10.0.1.0/24"
                ),
                "availability_zone": "${data.aws_availability_zones.available.names[0]}",
                "map_public_ip_on_launch": True,
                "tags": {"Name": "sega-public-subnet", "Type": "public"},
            }
        }

        tf_config["data"] = {
            "aws_availability_zones": {"available": {"state": "available"}}
        }

    def _add_compute_resources(
        self, tf_config: Dict, compute_config: Dict, infra_config: Dict
    ):
        """Add compute resources to Terraform config."""
        if compute_config.get("type") == "ecs":
            tf_config["resource"]["aws_ecs_cluster"] = {
                "main": {
                    "name": f"sega-{infra_config.get('project_name', 'default')}",
                    "setting": {
                        "name": "containerInsights",
                        "value": "enabled",
                    },
                    "tags": {
                        "Name": f"sega-{infra_config.get('project_name', 'default')}",
                        "ManagedBy": "SEGA",
                    },
                }
            }

            tf_config["output"]["ecs_cluster_name"] = {
                "value": "${aws_ecs_cluster.main.name}",
                "description": "Name of the ECS cluster",
            }

        elif compute_config.get("type") == "kubernetes":
            tf_config["resource"]["aws_eks_cluster"] = {
                "main": {
                    "name": f"sega-{infra_config.get('project_name', 'default')}",
                    "role_arn": "${aws_iam_role.eks_cluster.arn}",
                    "vpc_config": {"subnet_ids": ["${aws_subnet.public.id}"]},
                    "tags": {
                        "Name": f"sega-{infra_config.get('project_name', 'default')}",
                        "ManagedBy": "SEGA",
                    },
                }
            }

    def _add_storage_resources(self, tf_config: Dict, storage_config: Dict):
        """Add storage resources to Terraform config."""
        if storage_config.get("s3_buckets"):
            for bucket in storage_config["s3_buckets"]:
                bucket_name = bucket.replace("_", "-").lower()
                tf_config["resource"]["aws_s3_bucket"] = tf_config[
                    "resource"
                ].get("aws_s3_bucket", {})
                tf_config["resource"]["aws_s3_bucket"][bucket_name] = {
                    "bucket": f"sega-{bucket_name}",
                    "tags": {
                        "Name": f"sega-{bucket_name}",
                        "ManagedBy": "SEGA",
                    },
                }

    def _add_monitoring_resources(
        self, tf_config: Dict, monitoring_config: Dict
    ):
        """Add monitoring resources to Terraform config."""
        if monitoring_config.get("cloudwatch_logs"):
            tf_config["resource"]["aws_cloudwatch_log_group"] = {
                "main": {
                    "name": "/sega/aApplications",
                    "retention_in_days": 30,
                    "tags": {"ManagedBy": "SEGA"},
                }
            }

    def write_config(
        self, tf_config: Dict, output_dir: Optional[Path] = None
    ) -> Path:
        """Write Terraform configuration to HCL format."""
        output_dir = output_dir or self.terraform_dir
        output_dir.mkdir(parents=True, exist_ok=True)

        main_tf = output_dir / "main.tf"
        try:
            with open(main_tf, "w") as f:
                f.write(self._dict_to_hcl(tf_config))
        except (IOError, OSError) as e:
            logger.error(f"Failed to write {main_tf}: {e}")
            raise

        return output_dir

    def _dict_to_hcl(self, config: Dict) -> str:
        """Convert dictionary to HCL format."""

        def format_value(value, indent=0):
            indent_str = "  " * indent

            if isinstance(value, bool):
                return str(value).lower()
            elif isinstance(value, (int, float)):
                return str(value)
            elif isinstance(value, str):
                # Check if it's a reference
                if value.startswith("${") and value.endswith("}"):
                    return value
                return f'"{value}"'
            elif isinstance(value, list):
                if not value:
                    return "[]"
                items = [
                    f"{indent_str}  {format_value(item, indent + 1)}"
                    for item in value
                ]
                return "[\n" + ",\n".join(items) + f"\n{indent_str}]"
            elif isinstance(value, dict):
                if not value:
                    return "{}"
                items = []
                for k, v in value.items():
                    formatted_value = format_value(v, indent + 1)
                    if isinstance(v, dict) and v:
                        items.append(
                            f"{indent_str}  {k} {{\n{format_dict_items(v, indent + 2)}{indent_str}  }}"
                        )
                    else:
                        items.append(f"{indent_str}  {k} = {formatted_value}")
                return "{\n" + "\n".join(items) + f"\n{indent_str}}}"
            else:
                return str(value)

        def format_dict_items(d: Dict, indent: int) -> str:
            items = []
            indent_str = "  " * indent
            for k, v in d.items():
                formatted_value = format_value(v, indent)
                if (
                    isinstance(v, dict)
                    and v
                    and not (
                        isinstance(v, dict)
                        and all(k2 in ["source", "version"] for k2 in v.keys())
                    )
                ):
                    items.append(
                        f"{indent_str}{k} {{\n{format_dict_items(v, indent + 1)}{indent_str}}}"
                    )
                else:
                    items.append(f"{indent_str}{k} = {formatted_value}")
            return "\n".join(items) + "\n"

        return format_dict_items(config, 0)

    def execute(self, tf_dir: Path, dry_run: bool = False) -> Dict[str, Any]:
        """Execute Terraform commands."""
        result = {"success": False, "outputs": {}, "errors": []}

        try:
            # Copy Terraform modules if needed
            self._copy_terraform_modules(tf_dir)

            # Initialize Terraform
            click.echo("\n Initializing Terraform...")
            init_result = subprocess.run(
                ["terraform", "init"],
                cwd=tf_dir,
                capture_output=True,
                text=True,
            )

            if init_result.returncode != 0:
                result["errors"].append(
                    f"Terraform init failed: {init_result.stderr}"
                )
                return result

            # Plan
            click.echo("\n Creating Terraform plan...")
            plan_result = subprocess.run(
                ["terraform", "plan", "-out=tfplan"],
                cwd=tf_dir,
                capture_output=True,
                text=True,
            )

            if plan_result.returncode != 0:
                result["errors"].append(
                    f"Terraform plan failed: {plan_result.stderr}"
                )
                return result

            click.echo(plan_result.stdout)

            if dry_run:
                click.echo("\n Dry run complete. No resources created.")
                result["success"] = True
                return result

            # Apply
            if click.confirm("\n Apply Terraform plan?"):
                click.echo("\n Applying Terraform configuration...")
                apply_result = subprocess.run(
                    ["terraform", "apply", "-auto-approve", "tfplan"],
                    cwd=tf_dir,
                    capture_output=True,
                    text=True,
                )

                if apply_result.returncode != 0:
                    result["errors"].append(
                        f"Terraform apply failed: {apply_result.stderr}"
                    )
                    return result

                # Get outputs
                output_result = subprocess.run(
                    ["terraform", "output", "-json"],
                    cwd=tf_dir,
                    capture_output=True,
                    text=True,
                )

                if output_result.returncode == 0 and output_result.stdout:
                    result["outputs"] = json.loads(output_result.stdout)

                result["success"] = True
                click.echo("\n Infrastructure provisioned successfully!")
            else:
                click.echo("\n Terraform apply cancelled.")

        except FileNotFoundError:
            result["errors"].append(
                "Terraform not found. Please install Terraform."
            )
        except Exception as e:
            result["errors"].append(f"Unexpected error: {str(e)}")

        return result

    def _copy_terraform_modules(self, dest_dir: Path):
        """Copy Terraform modules from package to destination."""
        # This would copy any required Terraform modules
        # For now, we'll skip this as modules should be in the _internal/tooling/_internal/tooling/infrastructure/terraform directory
        pass
