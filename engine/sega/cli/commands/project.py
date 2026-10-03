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
SEGA PROJECT COMMANDS
==============================================================================
File: src/sega/commands/project.py
Project: SEGA (Scalable Engineering & Growth Automation)
Copyright: 2022-2025 FLEET
License: Apache-2.0

SEGA MODULE: Commands/Project
COMPONENT: Project Management Commands
PURPOSE: Individual project operations and configuration management
DEPENDENCIES: click, yaml, pathlib
USAGE: sega project [detect|config|status]

Commands provided:
- sega project detect: Auto-detect project type
- sega project config: Show/edit project configuration
- sega project status: Show project deployment status
==============================================================================
"""

import click
import yaml
import os
from pathlib import Path
from typing import Optional

from ...project.project_detector import ProjectDetector
from ...core.dependency_injection import inject
from ...services.deployment_service import DeploymentService


@click.group()
def project():
    """Individual project operations and configuration."""
    pass


@project.command()
@click.option(
    "--path", default=".", help="Path to analyze (default: current directory)"
)
@click.option(
    "--verbose", "-v", is_flag=True, help="Show detailed detection information"
)
def detect(path: str, verbose: bool):
    """Auto-detect project type and configuration."""
    try:
        detector = ProjectDetector()
        project_type = detector.detect(path)

        click.echo(f"Project path: {os.path.abspath(path)}")
        click.echo(f"Detected type: {project_type}")

        if verbose:
            # Get additional project metadata
            metadata = detector.get_project_metadata(path)
            if metadata:
                click.echo("\nProject details:")
                for key, value in metadata.items():
                    click.echo(f"  {key}: {value}")

        # Check for existing sega.yaml
        sega_config = Path(path) / "sega.yaml"
        if sega_config.exists():
            click.echo(f"\nExisting configuration: {sega_config}")
        else:
            click.echo(
                "\nNo sega.yaml found. Run 'sega init' to create configuration."
            )

    except Exception as e:
        click.echo(f"Error detecting project: {str(e)}", err=True)
        raise click.Abort()


@project.command()
@click.option(
    "--path", default=".", help="Path to project (default: current directory)"
)
@click.option(
    "--edit", "-e", is_flag=True, help="Open configuration for editing"
)
@click.option("--set", help="Set configuration value (format: key=value)")
def config(path: str, edit: bool, set: Optional[str]):
    """Show or edit project configuration."""
    sega_config = Path(path) / "sega.yaml"

    if not sega_config.exists():
        click.echo(f"No sega.yaml found in {os.path.abspath(path)}")
        click.echo("Run 'sega init' to create a configuration file.")
        raise click.Abort()

    try:
        # Load current configuration
        with open(sega_config, "r") as f:
            config_data = yaml.safe_load(f)

        if set:
            # Set a configuration value
            if "=" not in set:
                click.echo("Invalid format. Use: key=value", err=True)
                raise click.Abort()

            key, value = set.split("=", 1)
            keys = key.split(".")

            # Navigate to nested key
            current = config_data
            for k in keys[:-1]:
                if k not in current:
                    current[k] = {}
                current = current[k]

            # Set the value
            try:
                # Try to parse as boolean, number, or keep as string
                if value.lower() in ["true", "false"]:
                    current[keys[-1]] = value.lower() == "true"
                elif value.isdigit():
                    current[keys[-1]] = int(value)
                else:
                    current[keys[-1]] = value
            except (ValueError, AttributeError):
                current[keys[-1]] = value

            # Save updated configuration
            with open(sega_config, "w") as f:
                yaml.dump(config_data, f, default_flow_style=False)

            click.echo(f"Updated {key} = {value}")

        elif edit:
            # Open for editing (basic implementation)
            editor = os.environ.get("EDITOR", "vi")
            os.system(f"{editor} {sega_config}")

        else:
            # Show current configuration
            click.echo(f"Configuration for {os.path.abspath(path)}:")
            click.echo(yaml.dump(config_data, default_flow_style=False))

    except Exception as e:
        click.echo(f"Error handling configuration: {str(e)}", err=True)
        raise click.Abort()


@project.command()
@click.option(
    "--path", default=".", help="Path to project (default: current directory)"
)
@click.option("--target", default="staging", help="Deployment target to check")
@click.option(
    "--verbose", "-v", is_flag=True, help="Show detailed status information"
)
@inject("deployment_service")
def status(
    path: str,
    target: str,
    verbose: bool,
    deployment_service: DeploymentService,
):
    """Show project deployment status."""
    try:
        sega_config = Path(path) / "sega.yaml"
        if not sega_config.exists():
            click.echo(f"No sega.yaml found in {os.path.abspath(path)}")
            click.echo("Run 'sega init' to create a configuration file.")
            raise click.Abort()

        # Load project configuration
        with open(sega_config, "r") as f:
            config_data = yaml.safe_load(f)

        project_name = config_data.get("name", Path(path).name)

        click.echo(f"Project: {project_name}")
        click.echo(f"Path: {os.path.abspath(path)}")
        click.echo(f"Target: {target}")

        # Get deployment status
        status_info = deployment_service.get_deployment_status(
            project_name, target
        )

        if status_info:
            click.echo(
                f"\nDeployment Status: {status_info.get('status', 'Unknown')}"
            )

            if verbose and "details" in status_info:
                click.echo("\nDetails:")
                for key, value in status_info["details"].items():
                    click.echo(f"  {key}: {value}")
        else:
            click.echo(f"\nNo deployment found for {project_name} in {target}")

    except Exception as e:
        click.echo(f"Error getting project status: {str(e)}", err=True)
        raise click.Abort()


if __name__ == "__main__":
    project()
