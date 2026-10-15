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
SEGA WORKSPACE MANAGEMENT COMMAND
==============================================================================
File: src/sega/commands/workspace.py
Project: SEGA (Scalable Engineering & Growth Automation)
Copyright: 2022-2025 FLEET
License: Apache-2.0

SEGA MODULE: Commands/WorkspaceManagement
COMPONENT: Multi-Project Workspace CLI Command Group
PURPOSE: Manage multi-project workspaces for coordinated operations
DEPENDENCIES: click, json, yaml, WorkspaceManager
USAGE: sega workspace [list|build|deploy|test] [--team TEAM] [--type TYPE]

This command group provides workspace-level operations across multiple projects
with team filtering, project type filtering, and coordinated build/deploy/test cycles.
==============================================================================
"""

import click
import json
import yaml
from ...core.workspace_manager import WorkspaceManager


@click.group()
def workspace():
    """Manage multi-project workspaces for coordinated operations."""
    pass


@workspace.command()
@click.option(
    "--format",
    type=click.Choice(["json", "yaml", "table"]),
    default="table",
    help="Output format",
)
@click.option("--team", help="Filter by team")
@click.option("--type", help="Filter by project type")
@click.option("--config", help="Load projects from custom configuration file")
def list(format, team, type, config):
    """List all projects in the workspace."""
    if config:
        # Load projects from custom configuration file
        try:
            import yaml
            from pathlib import Path

            config_path = Path(config)
            if not config_path.exists():
                click.echo(f" Configuration file not found: {config}")
                return

            try:
                with open(config_path) as f:
                    config_data = yaml.safe_load(f)
            except (IOError, OSError) as e:
                click.echo(f" Error reading {config_path}: {e}")
                return

            # Create manager with custom config
            manager = WorkspaceManager()
            manager.projects = {}

            # Load projects from config
            if "projects" in config_data:
                for team_name, project_paths in config_data[
                    "projects"
                ].items():
                    for project_path in project_paths:
                        full_path = Path(project_path)
                        if full_path.exists():
                            from ...project.project_detector import (
                                ProjectDetector,
                            )

                            detector = ProjectDetector(str(full_path))
                            manager.projects[project_path] = {
                                "name": full_path.name,
                                "team": team_name,
                                "path": full_path,
                                "detector": detector,
                            }
        except Exception as e:
            click.echo(f" Error loading configuration: {e}")
            return
    else:
        manager = WorkspaceManager()

    projects = manager.projects

    # Apply filters
    if team:
        projects = {k: v for k, v in projects.items() if v["team"] == team}

    if type:
        projects = {
            k: v for k, v in projects.items() if v["detector"].detect() == type
        }

    if format == "json":
        output = {}
        for key, project in projects.items():
            output[key] = {
                "name": project["name"],
                "team": project["team"],
                "type": project["detector"].detect(),
                "path": str(project["path"]),
                "components": project["detector"].get_components(),
            }
        click.echo(json.dumps(output, indent=2))

    elif format == "yaml":
        output = {}
        for key, project in projects.items():
            output[key] = {
                "name": project["name"],
                "team": project["team"],
                "type": project["detector"].detect(),
                "path": str(project["path"]),
                "components": project["detector"].get_components(),
            }
        click.echo(yaml.dump(output, default_flow_style=False))

    else:  # table format
        click.echo("Projects in workspace:")
        click.echo("=" * 80)
        for key, project in projects.items():
            project_type = project["detector"].detect()
            components = project["detector"].get_components()

            click.echo(f" {key}")
            click.echo(f"   Team: {project['team']}")
            click.echo(f"   Type: {project_type}")
            click.echo(f"   Path: {project['path']}")

            if components:
                click.echo(
                    f"   Components: {', '.join([c['name'] for c in components])}"
                )

            click.echo()


@workspace.command()
@click.option("--output", "-o", help="Output file path")
def config(output):
    """Generate workspace configuration file."""
    manager = WorkspaceManager()
    config = manager.generate_workspace_config()

    if output:
        try:
            with open(output, "w") as f:
                yaml.dump(config, f, default_flow_style=False)
            click.echo(f" Workspace configuration written to {output}")
        except (IOError, OSError) as e:
            click.echo(f" Failed to write {output}: {e}", err=True)
    else:
        click.echo(yaml.dump(config, default_flow_style=False))


@workspace.command()
def validate():
    """Validate workspace configuration and dependencies."""
    manager = WorkspaceManager()
    issues = manager.validate_workspace()

    has_issues = any(issues.values())

    if not has_issues:
        click.echo(" Workspace validation passed!")
        return

    click.echo(" Workspace validation found issues:")
    click.echo()

    if issues["missing_dependencies"]:
        click.echo("Missing Dependencies:")
        for dep in issues["missing_dependencies"]:
            click.echo(f"  - {dep}")
        click.echo()

    if issues["circular_dependencies"]:
        click.echo("Circular Dependencies:")
        for dep in issues["circular_dependencies"]:
            click.echo(f"  - {dep}")
        click.echo()

    if issues["missing_configs"]:
        click.echo("Missing Configurations:")
        for project in issues["missing_configs"]:
            click.echo(f"  - {project} (missing sega.yaml)")
        click.echo()

    if issues["configuration_errors"]:
        click.echo("Configuration Errors:")
        for error in issues["configuration_errors"]:
            click.echo(f"  - {error}")
        click.echo()


@workspace.command()
@click.option("--target", required=True, help="Deployment target")
@click.option("--team", multiple=True, help="Deploy specific teams")
@click.option(
    "--project",
    multiple=True,
    help="Deploy specific projects (can be used multiple times)",
)
@click.option(
    "--strategy",
    type=click.Choice(["coordinated", "parallel", "fail_fast"]),
    default="coordinated",
    help="Deployment strategy",
)
@click.option(
    "--dry-run", is_flag=True, help="Show deployment plan without executing"
)
def deploy(target, team, project, strategy, dry_run):
    """Deploy multiple projects in coordinated manner."""
    manager = WorkspaceManager()

    # Determine projects to deploy
    if list(project):
        target_projects = list(project)
    elif list(team):
        target_projects = []
        for t in team:
            target_projects.extend(manager.get_projects_by_team(t))
    else:
        target_projects = list(manager.projects.keys())

    # Get deployment order
    try:
        deployment_order = manager.get_deployment_order(target_projects)
    except ValueError as e:
        click.echo(f" Error: {e}")
        return

    click.echo(f" Deployment Plan (target: {target}, strategy: {strategy})")
    click.echo("=" * 60)

    for i, project_key in enumerate(deployment_order, 1):
        project = manager.projects[project_key]
        project_type = project["detector"].detect()
        click.echo(f"{i}. {project_key} ({project_type})")

    click.echo()

    if dry_run:
        click.echo(" Dry run completed. Use --no-dry-run to execute.")
        return

    # Execute deployment
    if not click.confirm(
        f"Deploy {len(deployment_order)} projects to {target}?"
    ):
        return

    click.echo(" Starting coordinated deployment...")

    result = manager.deploy_workspace(
        target=target,
        teams=list(team) if team else None,
        projects=list(project) if project else None,
        strategy=strategy,
    )

    # Display results
    click.echo("\n Deployment Results:")
    click.echo("=" * 40)

    for project_key in result["deployment_order"]:
        project_result = result["results"].get(project_key, {})
        if project_result.get("success"):
            click.echo(f" {project_key}: Deployed successfully")
        else:
            click.echo(
                f" {project_key}: Failed - {project_result.get('error', 'Unknown error')}"
            )

    if result["overall_success"]:
        click.echo("\n All deployments completed successfully!")
    else:
        click.echo("\n  Some deployments failed. Check logs for details.")


@workspace.command()
@click.option("--target", required=True, help="Deployment target to rollback")
@click.option("--project", multiple=True, help="Rollback specific projects")
@click.option("--confirm", is_flag=True, help="Skip confirmation prompt")
def rollback(target, project, confirm):
    """Rollback multiple projects in reverse deployment order."""
    manager = WorkspaceManager()

    projects_to_rollback = (
        list(project) if project else list(manager.projects.keys())
    )

    if not projects_to_rollback:
        click.echo("No projects to rollback")
        return

    # Get rollback order (reverse deployment order)
    deployment_order = manager.get_deployment_order(projects_to_rollback)
    rollback_order = deployment_order[::-1]

    click.echo(f" Rollback Plan (target: {target})")
    click.echo("=" * 40)

    for i, project_key in enumerate(rollback_order, 1):
        project = manager.projects[project_key]
        project_type = project["detector"].detect()
        click.echo(f"{i}. {project_key} ({project_type})")

    click.echo()

    if not confirm and not click.confirm(
        f"Rollback {len(rollback_order)} projects from {target}?"
    ):
        return

    click.echo(" Starting coordinated rollback...")

    result = manager.rollback_workspace(
        target=target, projects=projects_to_rollback
    )

    # Display results
    click.echo("\n Rollback Results:")
    click.echo("=" * 40)

    for project_key in result["rollback_order"]:
        project_result = result["results"].get(project_key, {})
        if project_result.get("success"):
            click.echo(f" {project_key}: Rolled back successfully")
        else:
            click.echo(
                f" {project_key}: Failed - {project_result.get('error', 'Unknown error')}"
            )

    if result["overall_success"]:
        click.echo("\n All rollbacks completed successfully!")
    else:
        click.echo("\n  Some rollbacks failed. Check logs for details.")


@workspace.command()
@click.option(
    "--format",
    type=click.Choice(["json", "yaml", "table"]),
    default="table",
    help="Output format",
)
def dependencies(format):
    """Show dependency graph for all projects."""
    manager = WorkspaceManager()
    dep_graph = manager.build_dependency_graph()

    if format == "json":
        click.echo(json.dumps(dep_graph, indent=2))
    elif format == "yaml":
        click.echo(yaml.dump(dep_graph, default_flow_style=False))
    else:  # table format
        click.echo("Project Dependencies:")
        click.echo("=" * 60)

        for project, deps in dep_graph.items():
            click.echo(f" {project}")
            if deps:
                for dep in deps:
                    click.echo(f"  └── {dep}")
            else:
                click.echo("  └── (no dependencies)")
            click.echo()


@workspace.command()
@click.option(
    "--format",
    type=click.Choice(["json", "yaml", "table"]),
    default="table",
    help="Output format",
)
def shared(format):
    """Show shared resources across projects."""
    manager = WorkspaceManager()
    shared_resources = manager.get_shared_resources()

    if format == "json":
        click.echo(
            json.dumps(
                {k: list(v) for k, v in shared_resources.items()}, indent=2
            )
        )
    elif format == "yaml":
        click.echo(
            yaml.dump(
                {k: list(v) for k, v in shared_resources.items()},
                default_flow_style=False,
            )
        )
    else:  # table format
        click.echo("Shared Resources:")
        click.echo("=" * 60)

        for resource, projects in shared_resources.items():
            click.echo(f" {resource}")
            for project in projects:
                click.echo(f"  └── {project}")
            click.echo()


@workspace.command()
@click.argument("team")
@click.option(
    "--format",
    type=click.Choice(["json", "yaml", "table"]),
    default="table",
    help="Output format",
)
def team(team, format):
    """Show projects for a specific team."""
    manager = WorkspaceManager()
    team_projects = manager.get_projects_by_team(team)

    if not team_projects:
        click.echo(f"No projects found for team: {team}")
        return

    if format == "json":
        output = {}
        for project_key in team_projects:
            project = manager.projects[project_key]
            output[project_key] = {
                "name": project["name"],
                "type": project["detector"].detect(),
                "path": str(project["path"]),
            }
        click.echo(json.dumps(output, indent=2))

    elif format == "yaml":
        output = {}
        for project_key in team_projects:
            project = manager.projects[project_key]
            output[project_key] = {
                "name": project["name"],
                "type": project["detector"].detect(),
                "path": str(project["path"]),
            }
        click.echo(yaml.dump(output, default_flow_style=False))

    else:  # table format
        click.echo(f"Projects for team '{team}':")
        click.echo("=" * 60)

        for project_key in team_projects:
            project = manager.projects[project_key]
            project_type = project["detector"].detect()
            click.echo(f" {project['name']} ({project_type})")
            click.echo(f"   Path: {project['path']}")

            components = project["detector"].get_components()
            if components:
                click.echo(
                    f"   Components: {', '.join([c['name'] for c in components])}"
                )

            click.echo()


if __name__ == "__main__":
    workspace()
