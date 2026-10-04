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
SEGA PROJECT INITIALIZATION COMMAND
==============================================================================
File: src/sega/commands/init.py
Project: SEGA (Scalable Engineering & Growth Automation)
Copyright: 2022-2025 FLEET
License: Apache-2.0

SEGA MODULE: Commands/ProjectInitialization
COMPONENT: Project Setup and Configuration CLI Command
PURPOSE: Initialize projects with SEGA configuration and infrastructure templates
DEPENDENCIES: click, yaml, ProjectDetector, TemplateGenerator, PortfolioManager
USAGE: sega init [--type TYPE] [--targets LIST] [--portfolio] [--template NAME]

This command initializes single projects or entire portfolios with SEGA configuration,
auto-detected build pipelines, and infrastructure templates.
==============================================================================
"""

import click
import yaml
from pathlib import Path
from ...project.project_detector import ProjectDetector
from ...core.template_generator import TemplateGenerator
from ...core.portfolio_manager import PortfolioManager


@click.command()
@click.option(
    "--type", "project_type", help="Override auto-detected project type"
)
@click.option(
    "--targets",
    default="staging,prod",
    help="Comma-separated deployment targets",
)
@click.option("--force", is_flag=True, help="Overwrite existing configuration")
@click.option(
    "--generate-templates",
    is_flag=True,
    help="Generate infrastructure templates",
)
@click.option("--name", default="sega-app", help="Project name for templates")
@click.option(
    "--portfolio",
    is_flag=True,
    help="Initialize entire portfolio (discover git projects)",
)
@click.option(
    "--team", multiple=True, help="Filter by team (use with --portfolio)"
)
@click.option(
    "--project-type-filter",
    multiple=True,
    help="Filter by project type (use with --portfolio)",
)
@click.option(
    "--dry-run",
    is_flag=True,
    help="Show what would be done without making changes",
)
@click.option(
    "--template", default="fleet", help="Template to use for configuration"
)
@click.option(
    "--domain",
    default="yourdomain.com",
    help="Domain for ingress configuration",
)
def init(
    project_type: str,
    targets: str,
    force: bool,
    generate_templates: bool,
    name: str,
    portfolio: bool,
    team: tuple,
    project_type_filter: tuple,
    dry_run: bool,
    template: str,
    domain: str,
):
    """Initialize project with SEGA configuration."""

    if portfolio:
        # Portfolio-level initialization
        _init_portfolio(team, project_type_filter, force, template, dry_run)
    else:
        # Single project initialization
        _init_single_project(
            project_type,
            targets,
            force,
            generate_templates,
            name,
            template,
            dry_run,
        )


def _init_portfolio(
    team_filter: tuple,
    type_filter: tuple,
    force: bool,
    template: str,
    dry_run: bool,
):
    """Initialize entire portfolio of projects."""
    click.echo(" Discovering git projects in portfolio...")

    portfolio_manager = PortfolioManager()

    # Discover all git projects
    git_projects = portfolio_manager.discover_git_projects()

    if not git_projects:
        click.echo(" No git projects found in current directory tree.")
        return

    click.echo(f" Found {len(git_projects)} git projects")

    # Apply filters
    filters = {}
    if team_filter:
        filters["teams"] = list(team_filter)
    if type_filter:
        filters["types"] = list(type_filter)

    if filters:
        filtered_projects = portfolio_manager.filter_projects(
            git_projects, filters
        )
        click.echo(f" Filtered to {len(filtered_projects)} projects")
    else:
        filtered_projects = git_projects

    # Show summary
    summary = portfolio_manager.get_project_summary()
    click.echo("\n Portfolio Summary:")
    click.echo(f"   Total projects: {summary['total']}")
    click.echo(f"   With SEGA config: {summary['with_sega_config']}")

    if summary["by_team"]:
        click.echo("   By team:")
        for team_name, count in summary["by_team"].items():
            click.echo(f"     {team_name}: {count} projects")

    if summary["by_type"]:
        click.echo("   By type:")
        for project_type, count in summary["by_type"].items():
            click.echo(f"     {project_type}: {count} projects")

    # Initialize projects
    project_paths = list(filtered_projects.keys())

    if dry_run:
        click.echo("\n Dry run - would initialize:")
        for path in project_paths:
            project_info = filtered_projects[path]
            config_status = (
                " has config"
                if project_info["has_sega_config"]
                else " would create"
            )
            click.echo(
                f"   {path} ({project_info['detected_type']}) - {config_status}"
            )
        return

    if not click.confirm(
        f"\n Initialize SEGA configuration for {len(project_paths)} projects?"
    ):
        return

    click.echo("\n Initializing projects...")

    results = portfolio_manager.init_projects(
        project_paths, force, template, dry_run
    )

    # Report results
    successful = sum(1 for r in results.values() if r["success"])
    failed = len(results) - successful

    click.echo(f"\n Results: {successful} successful, {failed} failed")

    for path, result in results.items():
        if result["success"]:
            action = result.get("action", "unknown")
            project_type = result.get("project_type", "unknown")
            components = result.get("components", 0)

            if action == "created":
                click.echo(f"    {path} ({project_type}) - created config")
                if components > 0:
                    click.echo(f"      └── {components} components detected")
            elif action == "would_create":
                click.echo(
                    f"    {path} ({project_type}) - would create config"
                )
        else:
            click.echo(f"    {path} - {result['error']}")

    # Generate workspace configuration
    click.echo("\n  Generating workspace configuration...")
    workspace_config = portfolio_manager.generate_workspace_config(
        filtered_projects
    )

    # Save workspace config
    workspace_config_path = Path("sega-workspace.yaml")
    try:
        with open(workspace_config_path, "w") as f:
            yaml.dump(workspace_config, f, default_flow_style=False, indent=2)
        click.echo(f"   Created {workspace_config_path}")
    except (IOError, OSError) as e:
        click.echo(f" Failed to write {workspace_config_path}: {e}", err=True)
        return

    # Save project paths for easy loading
    project_paths_config = {}
    for path, project_info in filtered_projects.items():
        team = project_info.get("team", "unknown")
        if team not in project_paths_config:
            project_paths_config[team] = []
        project_paths_config[team].append(path)

    portfolio_manager.save_project_paths(project_paths_config)
    click.echo("   Created sega-projects.yaml")

    click.echo("\nNext steps:")
    click.echo("  sega workspace list          # View all managed projects")
    click.echo("  sega workspace validate      # Validate configurations")
    click.echo(
        "  sega workspace deploy --team <team> --target staging  # Deploy team projects"
    )


def _init_single_project(
    project_type: str,
    targets: str,
    force: bool,
    generate_templates: bool,
    name: str,
    template: str,
    dry_run: bool,
):
    """Initialize single project with SEGA configuration."""

    # Use new sega.yaml format
    config_path = Path("sega.yaml")
    legacy_path = Path(".sega.yml")

    # Check for existing configuration
    try:
        if (config_path.exists() or legacy_path.exists()) and not force:
            existing_file = (
                "sega.yaml" if config_path.exists() else ".sega.yml"
            )
            click.echo(
                f" {existing_file} already exists. Use --force to overwrite."
            )
            return
    except (OSError, IOError) as e:
        click.echo(f" Error checking existing configuration: {e}", err=True)
        return

    # Auto-detect if not specified
    if not project_type:
        try:
            detector = ProjectDetector()
            project_type = detector.detect()
            fleet_metadata = detector.get_fleet_metadata()
            components = detector.get_components()
        except (OSError, IOError) as e:
            click.echo(f" Error during project detection: {e}", err=True)
            return
        click.echo(f"Auto-detected project type: {project_type}")

        if fleet_metadata.get("team"):
            click.echo(f"Detected team: {fleet_metadata['team']}")
        if components:
            click.echo(
                f"Detected {len(components)} components: {', '.join([c['name'] for c in components])}"
            )
    else:
        detector = ProjectDetector()
        fleet_metadata = detector.get_fleet_metadata()
        components = detector.get_components()

    # Generate minimal working configuration
    portfolio_manager = PortfolioManager()
    config = portfolio_manager._generate_minimal_config(
        project_type, fleet_metadata, components
    )

    if dry_run:
        click.echo("\n Dry run - would create:")
        click.echo(f"   File: {config_path}")
        click.echo(f"   Type: {project_type}")
        click.echo(f"   Team: {fleet_metadata.get('team', 'unknown')}")
        click.echo(f"   Components: {len(components)}")
        click.echo("\nConfiguration preview:")
        click.echo(yaml.dump(config, default_flow_style=False, indent=2))
        return

    # Write configuration
    try:
        with open(config_path, "w") as f:
            yaml.dump(config, f, default_flow_style=False, indent=2)
        click.echo(f" Created {config_path} for {project_type} project")
    except (IOError, OSError) as e:
        click.echo(f" Failed to write {config_path}: {e}", err=True)
        return
    click.echo(f"   Team: {fleet_metadata.get('team', 'unknown')}")
    click.echo(f"   Components: {len(components)}")

    # Generate GitLab CI configuration
    gitlab_ci_path = Path(".gitlab-ci.yml")
    if not gitlab_ci_path.exists() or force:
        gitlab_config = portfolio_manager._generate_gitlab_ci(
            project_type, fleet_metadata
        )
        try:
            with open(gitlab_ci_path, "w") as f:
                f.write(gitlab_config)
        except (IOError, OSError) as e:
            click.echo(f" Failed to write {gitlab_ci_path}: {e}", err=True)
        click.echo(f" Created {gitlab_ci_path}")

    # Generate health endpoint if applicable
    if project_type in ["web_app", "ml_pipeline"]:
        portfolio_manager._generate_health_endpoint(Path("."), project_type)
        click.echo(" Generated health endpoint template")

    # Update .gitignore to exclude .sega/ runtime directory
    gitignore_path = Path(".gitignore")
    gitignore_entries = [
        "\n# SEGA runtime directory (test configs, benchmarks, etc.)",
        ".sega/",
        "\n# Legacy SEGA config (if migrating)",
        ".sega.yml.bak",
    ]

    if gitignore_path.exists():
        with open(gitignore_path, "r") as f:
            content = f.read()

        # Add entries if not already present
        entries_to_add = []
        for entry in gitignore_entries:
            if entry.strip() and entry.strip() not in content:
                entries_to_add.append(entry)

        if entries_to_add:
            with open(gitignore_path, "a") as f:
                f.write("\n")
                for entry in entries_to_add:
                    f.write(entry + "\n")
            click.echo(" Updated .gitignore to exclude .sega/ runtime directory")
    else:
        # Create new .gitignore
        with open(gitignore_path, "w") as f:
            f.write("# Build artifacts\n")
            f.write("dist/\n")
            f.write("build/\n")
            f.write("*.egg-info/\n")
            f.write("__pycache__/\n")
            f.write("*.pyc\n")
            f.write("\n# Environment files\n")
            f.write(".env\n")
            f.write(".env.*\n")
            f.write("!.env.example\n")
            for entry in gitignore_entries:
                f.write(entry + "\n")
        click.echo(" Created .gitignore with standard exclusions")

    # Generate infrastructure templates if requested
    if generate_templates:
        click.echo(
            f"\n  Generating infrastructure templates for {project_type}..."
        )
        try:
            generator = TemplateGenerator(project_type)
            templates = generator.generate_all(name, "yourdomain.com")
            generator.write_templates(templates)
            click.echo(f"   Generated {len(templates)} template files")
        except Exception as e:
            click.echo(f"     Template generation failed: {e}")

    click.echo("\nNext steps:")
    if not generate_templates:
        click.echo(
            "  sega init --generate-templates  # Generate infrastructure files"
        )
    click.echo("  sega doctor          # Validate environment")
    click.echo("  sega build           # Build project")
    click.echo(
        "  sega deploy --target staging --dry-run  # Preview deployment"
    )
