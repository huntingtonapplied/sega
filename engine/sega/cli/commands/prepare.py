#!/usr/bin/env python3
"""
SEGA Prepare Command
===============================================================================
File: engine/sega/cli/commands/prepare.py
Project: SEGA (Scalable Engineering & Growth Automation)
Purpose: Prepare shared infrastructure and dependencies for projects
===============================================================================
"""

import click
import logging
from pathlib import Path
from typing import Optional
import sys

# Import through existing integration layer
sys.path.insert(0, str(Path(__file__).parent.parent.parent))
from sega.local.integration import get_integration

logger = logging.getLogger(__name__)


@click.command()
@click.option("--project", "-p", required=True, help="Project name to prepare")
@click.option(
    "--component",
    "-c",
    multiple=True,
    type=click.Choice(["frontend", "ide", "backend", "engine", "all"]),
    default=["all"],
    help="Components to prepare",
)
@click.option("--fleet-root", type=Path, default=Path.home() / "fleet", help="FLEET root directory")
@click.option("--verbose", "-v", is_flag=True, help="Verbose output")
def prepare(project: str, component: tuple, fleet_root: Path, verbose: bool):
    """Prepare shared infrastructure and dependencies for projects.

    This command sets up the necessary shared infrastructure including:
    - Component-specific node_modules (for atlas: frontend, IDE)
    - Shared Python environments (backend_venv, engine_venv)
    - Data directories for native databases
    - Configuration directories
    - Symlinks for efficient development

    Examples:
        sega prepare -p atlas --component all
        sega prepare -p atlas -c frontend -c ide
        sega prepare -p myproject --component backend
    """

    if verbose:
        logging.basicConfig(level=logging.DEBUG)
    else:
        logging.basicConfig(level=logging.INFO)

    # Convert component tuple to list
    components = list(component)
    if "all" in components:
        components = ["frontend", "ide", "backend", "engine"]

    # Initialize integration manager
    integration = get_integration(fleet_root, project)

    click.echo(f"🚀 Preparing shared infrastructure for project: {project}")
    click.echo(f"📁 FLEET Root: {fleet_root}")
    click.echo(f"🔧 Components: {', '.join(components)}")

    # Prepare shared infrastructure
    if integration.prepare_shared_infrastructure(components):
        click.echo("✅ Shared infrastructure prepared successfully")
    else:
        click.echo("❌ Failed to prepare shared infrastructure", err=True)
        return 1

    # Show status
    status = integration.shared_manager.get_status()
    click.echo("\n📊 Infrastructure Status:")

    for category, items in status.items():
        if category == "project":
            continue
        click.echo(f"  {category.replace('_', ' ').title()}:")
        if isinstance(items, dict):
            for item, exists in items.items():
                status_icon = "✅" if exists else "❌"
                click.echo(f"    {item}: {status_icon}")
        else:
            status_icon = "✅" if items else "❌"
            click.echo(f"    {category}: {status_icon}")

    click.echo(f"\n🎉 Project '{project}' infrastructure preparation completed!")
    click.echo(f"💡 Next steps:")
    click.echo(f"   - Run 'sega local up -p {project} --shared all' to start services")
    click.echo(f"   - Use 'sega local status' to check running services")

    return 0


if __name__ == "__main__":
    sys.exit(prepare())
