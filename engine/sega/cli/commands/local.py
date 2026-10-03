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
SEGA LOCAL DEPLOYMENT COMMAND
==============================================================================
File: src/sega/commands/local.py
Project: SEGA (Scalable Engineering & Growth Automation)
Copyright: 2022-2025 SEGA Contributors
License: Apache-2.0

SEGA MODULE: Commands/LocalDeployment
COMPONENT: Local Development Deployment CLI Command Group
PURPOSE: Manage local development deployments for any workspace
DEPENDENCIES: click, LocalDeploymentManager, SharedInfrastructureManager
USAGE: sega local [up|down|restart|status|logs] [--project PROJECT]

This command group provides comprehensive local development deployment management
including shared infrastructure, project deployments, and development tools.
==============================================================================
"""

import click
import os
from pathlib import Path
from tabulate import tabulate
from ...local import LocalDeploymentManager, SharedInfrastructureManager, NativeInfrastructureManager
from ...core.project_ledger import ProjectLedger
from ...core.config import get_config


@click.group()
@click.pass_context
def local(ctx):
    """Manage local development deployments for workspace projects.

    SEGA provides unified local deployment management for:
    - Shared infrastructure (PostgreSQL, Redis, TimescaleDB)
    - Individual project deployments
    - Development environment with shared venv
    - Coordinated multi-project deployments

    Configure your workspace with a .sega.yml file in the root.
    """
    # Initialize context for subcommands
    ctx.ensure_object(dict)
    ctx.obj["config_file"] = None  # Auto-discovered from .sega.yml


def validate_env_components(ctx, param, value):
    """Validate and parse environment component flags.

    Handles both bare flag (--shared) and flag with values (--shared backend engine).
    Returns tuple of (is_set, components) where components is a set of component names.
    """
    if not value:
        return (False, set())

    valid_components = {"backend", "engine", "frontend"}
    components = set()

    for v in value:
        if v in valid_components:
            components.add(v)
        else:
            raise click.BadParameter(f"Invalid component '{v}'. Must be one of: backend, engine, frontend")

    # If flag is used but no components specified, means "all components"
    if not components:
        components = valid_components.copy()

    return (True, components)


def _normalize_app_exclude(value: str) -> str | None:
    mapping = {
        "landing_app": "landing",
        "landing": "landing",
        "product_app": "product",
        "product": "product",
        "frontend": "frontend",
        "backend": "backend",
        "engine": "engine",
        "ide": "ide",
    }
    return mapping.get(value)


def parse_exclude_values(exclude_values):
    """Parse --exclude values into project and app exclusions."""
    exclude_projects = set()
    exclude_apps = set()
    project_app_excludes = {}

    if not exclude_values:
        return exclude_projects, exclude_apps, project_app_excludes

    for raw in exclude_values:
        for item in raw.split(","):
            item = item.strip()
            if not item:
                continue

            if ":" in item:
                project_name, app_name = item.split(":", 1)
                project_name = project_name.strip()
                app_name = app_name.strip()
                normalized_app = _normalize_app_exclude(app_name)
                if normalized_app:
                    project_app_excludes.setdefault(project_name, set()).add(normalized_app)
                else:
                    exclude_projects.add(project_name)
                continue

            normalized_app = _normalize_app_exclude(item)
            if normalized_app:
                exclude_apps.add(normalized_app)
            else:
                exclude_projects.add(item)

    return exclude_projects, exclude_apps, project_app_excludes


class ComponentChoice(click.ParamType):
    """Custom parameter type for component choices that allows empty value."""

    name = "component"

    def convert(self, value, param, ctx):
        valid = {"backend", "engine", "frontend", "ide", "all"}
        if value in valid:
            return value
        self.fail(f"'{value}' is not valid. Choose from: backend, engine, frontend, ide, all", param, ctx)


@local.command()
@click.option("--project", "-p", multiple=True, help="Specific project(s) to deploy")
@click.option("--all", "deploy_all", is_flag=True, help="Deploy all projects")
@click.option("--no-infra", is_flag=True, help="Skip shared infrastructure")
@click.option("--with-tools", is_flag=True, help="Start management tools (PgAdmin, Redis Commander)")
@click.option("--agent-id", help="Agent ID for concurrent testing (auto-generated if not provided)")
@click.option("--no-ledger", is_flag=True, help="Skip project reservation ledger (for single-agent use)")
@click.option(
    "--shared",
    "shared_components",
    multiple=True,
    type=ComponentChoice(),
    is_eager=True,
    help="Use shared environments (~/fleet/environments/). Specify: all, backend, engine, frontend, ide.",
)
@click.option(
    "--project-env",
    "project_components",
    multiple=True,
    type=ComponentChoice(),
    is_eager=True,
    help="Use project-local environments. Specify: all, backend, engine, frontend, ide.",
)
@click.option(
    "--backend-runtime",
    type=click.Choice(["python", "rust"], case_sensitive=False),
    default="python",
    show_default=True,
    help="Runtime for backend when using native envs.",
)
@click.option(
    "--engine-runtime",
    type=click.Choice(["python", "rust"], case_sensitive=False),
    default="python",
    show_default=True,
    help="Runtime for engine when using native envs.",
)
@click.option(
    "--port-offset",
    type=int,
    default=0,
    help="Offset to add to all ports (e.g., --port-offset 100 shifts 8010->8110, 3010->3110)",
)
@click.option(
    "--exclude",
    "exclude_values",
    multiple=True,
    help=(
        "Exclude projects or components. Repeatable and comma-separated. Examples: "
        "--exclude landing_app, --exclude atlas, --exclude atlas:landing_app, "
        "--exclude backend,frontend"
    ),
)
@click.option(
    "--native-infra",
    is_flag=True,
    help=(
        "Use hybrid infra (native Redis + Docker TimescaleDB) using FLEET port standards. "
        "For fully dockerless macOS infra, use 'sega local macos'."
    ),
)
@click.pass_context
def up(
    ctx,
    project,
    deploy_all,
    no_infra,
    with_tools,
    agent_id,
    no_ledger,
    shared_components,
    project_components,
    port_offset,
    exclude_values,
    native_infra,
    backend_runtime,
    engine_runtime,
):
    """Start local development services.

    Examples:
        sega local up                              # Start shared infrastructure only
        sega local up --all                        # Start all projects (Docker mode)
        sega local up -p atlas -p sega          # Start specific projects
        sega local up --all --with-tools           # Start with management tools
        sega local up -p atlas --shared all     # Use shared environments for all components
        sega local up -p atlas --shared backend engine  # Only backend/engine use shared
        sega local up -p atlas --project-env frontend   # Frontend uses project-local node_modules
        sega local up -p atlas --shared backend --project-env frontend  # Mixed mode
        sega local up -p atlas --backend-runtime rust --shared backend  # Use Rust backend runtime
        sega local up -p atlas --engine-runtime rust --shared engine  # Use Rust engine runtime
        sega local up -p atlas --port-offset 100  # Run with ports shifted by +100
        sega local up -p atlas --native-infra  # Hybrid infra (native Redis + Docker TimescaleDB)
        sega local up -p atlas --shared all --native-infra  # Shared env + hybrid infra

    Port Offset:
        Use --port-offset to run multiple instances of the same project simultaneously.
        The offset is added to all service ports (API, frontend, database, redis, etc.)
        Example: --port-offset 100 shifts atlas ports: 8010->8110, 3010->3110, etc.

    Environment Modes:
        Docker (default): Components run in Docker containers
        Shared (--shared): Uses ~/fleet/environments/{backend_venv,engine_venv,node_modules,ide}
        Project (--project-env): Uses project-local ./venv, ./node_modules

    Infrastructure Modes:
        Docker (default): PostgreSQL/Redis run in Docker containers
        Hybrid (--native-infra): Native Redis on 6000+project_id; Docker TimescaleDB on 5000+project_id

    Components:
        all       - All components (backend, engine, frontend, ide)
        backend   - Backend services (Python or Rust runtime)
        engine    - Simulation engines (Python or Rust runtime)
        frontend  - Node.js frontend applications
        ide       - VS Code fork IDE (gulp transpile + code-web server)

    Runtime Modes (native only):
        --backend-runtime python|rust
        --engine-runtime python|rust
    """
    # Determine environment mode for each component
    # Priority: explicit --project-env > explicit --shared > docker (default)
    env_mode = {"backend": "docker", "engine": "docker", "frontend": "docker", "ide": "docker"}
    runtime_mode = {"backend": backend_runtime.lower(), "engine": engine_runtime.lower()}

    # Apply shared environments
    if shared_components:
        # Expand 'all' to all components
        components_to_share = set(shared_components)
        if "all" in components_to_share:
            components_to_share = {"backend", "engine", "frontend", "ide"}
        for comp in components_to_share:
            env_mode[comp] = "shared"

    # Apply project-local environments (overrides shared)
    if project_components:
        # Expand 'all' to all components
        components_to_project = set(project_components)
        if "all" in components_to_project:
            components_to_project = {"backend", "engine", "frontend", "ide"}
        for comp in components_to_project:
            env_mode[comp] = "project"

    # Log environment mode if not all docker
    if any(mode != "docker" for mode in env_mode.values()):
        click.echo(
            f"[INFO] Environment modes: backend={env_mode['backend']}, engine={env_mode['engine']}, frontend={env_mode['frontend']}, ide={env_mode['ide']}"
        )
        click.echo(f"[INFO] Runtime modes: backend={runtime_mode['backend']}, engine={runtime_mode['engine']}")

    # Log port offset if specified
    if port_offset != 0:
        click.echo(f"[INFO] Port offset: +{port_offset} (all ports will be shifted)")

    exclude_projects, exclude_apps, project_app_excludes = parse_exclude_values(exclude_values)
    if exclude_projects or exclude_apps or project_app_excludes:
        click.echo("[INFO] Exclusions:")
        if exclude_projects:
            click.echo(f"  Projects: {', '.join(sorted(exclude_projects))}")
        if exclude_apps:
            click.echo(f"  Components: {', '.join(sorted(exclude_apps))}")
        if project_app_excludes:
            formatted = ", ".join(
                f"{project}:{','.join(sorted(apps))}" for project, apps in project_app_excludes.items()
            )
            click.echo(f"  Project components: {formatted}")

    config_file = ctx.obj.get("config_file")
    manager = LocalDeploymentManager(config_file=config_file)

    # Validate project args early (before starting infra)
    if project:
        available_projects = manager.get_projects_with_compose()
        invalid_projects = [proj for proj in project if proj not in available_projects]
        if invalid_projects:
            click.echo(f"[ERROR] The following projects were not found: {', '.join(invalid_projects)}")
            click.echo(f"[INFO] Available projects: {', '.join(sorted(available_projects))}")
            return

    # Determine what we'll deploy (respects exclusions)
    projects_to_deploy = []
    if deploy_all:
        projects_to_deploy = [proj for proj in manager.get_projects_with_compose() if proj not in exclude_projects]
    elif project:
        projects_to_deploy = [proj for proj in list(project) if proj not in exclude_projects]
    elif manager.current_project and manager.current_project not in exclude_projects:
        projects_to_deploy = [manager.current_project]

    # Determine if we should use hybrid infrastructure
    # Hybrid infra is per-project; selection only makes sense for a single project.
    if native_infra and len(projects_to_deploy) != 1:
        click.echo("[ERROR] --native-infra requires exactly one project")
        click.echo("[INFO] Use -p PROJECT, or run from within a project directory")
        return
    use_native_infra = native_infra or (shared_components and not with_tools and len(projects_to_deploy) <= 1)

    # Get project name for hybrid infra (single project only)
    project_for_infra = projects_to_deploy[0] if len(projects_to_deploy) == 1 else None

    # Initialize ledger for concurrent testing
    ledger = None if no_ledger else ProjectLedger()
    agent_id = agent_id or f"pid-{os.getpid()}"

    # Start infrastructure (unless skipped)
    infra_env_vars = None
    if not no_infra:
        if use_native_infra:
            # Hybrid: native Redis + Docker TimescaleDB
            if native_infra:
                click.echo("[INFO] Using hybrid infrastructure (--native-infra)")
            else:
                click.echo("[INFO] Using hybrid infrastructure (auto-selected for --shared mode)")
            native_manager = NativeInfrastructureManager(project=project_for_infra, port_offset=port_offset)
            if not native_manager.start(profile="development"):
                click.echo("[WARNING] Hybrid infrastructure not fully available")
                click.echo("[INFO] Requirements: redis-server, redis-cli, docker")
            # Get infrastructure env vars to pass to backend processes
            if len(projects_to_deploy) == 1:
                infra_env_vars = native_manager.get_env_vars()
        else:
            # Use Docker infrastructure (default)
            infra_manager = SharedInfrastructureManager(workspace_root=manager.workspace_root, config=manager.config)
            if not infra_manager.start(profile="development", with_tools=with_tools):
                click.echo("[WARNING] Continuing without shared infrastructure")

    # Deploy projects with ledger coordination
    if deploy_all:
        results = _deploy_with_ledger(
            manager,
            ledger,
            agent_id,
            projects_to_deploy,
            env_mode=env_mode,
            runtime_mode=runtime_mode,
            port_offset=port_offset,
            infra_env_vars=infra_env_vars,
            exclude_apps=exclude_apps,
            project_app_excludes=project_app_excludes,
        )
    elif project:
        results = _deploy_with_ledger(
            manager,
            ledger,
            agent_id,
            projects_to_deploy,
            env_mode=env_mode,
            runtime_mode=runtime_mode,
            port_offset=port_offset,
            infra_env_vars=infra_env_vars,
            exclude_apps=exclude_apps,
            project_app_excludes=project_app_excludes,
        )
    elif manager.current_project and projects_to_deploy:
        # Auto-detected current project
        click.echo(f"[INFO] Auto-detected project: {manager.current_project}")
        results = _deploy_with_ledger(
            manager,
            ledger,
            agent_id,
            projects_to_deploy,
            env_mode=env_mode,
            runtime_mode=runtime_mode,
            port_offset=port_offset,
            infra_env_vars=infra_env_vars,
            exclude_apps=exclude_apps,
            project_app_excludes=project_app_excludes,
        )
    else:
        # Just infrastructure
        click.echo("[INFO] No projects specified. Use --all or -p PROJECT to deploy projects.")
        click.echo("[INFO] Run 'sega local list' to see available projects.")
        return

    # Show summary
    if results:
        click.echo("\n[INFO] Deployment Summary:")
        successful = [p for p, r in results.items() if r.get("success")]
        failed = [p for p, r in results.items() if not r.get("success")]
        skipped = [p for p, r in results.items() if r.get("skipped")]

        if successful:
            click.echo(f"[OK] Successful ({len(successful)}): {', '.join(successful)}")
        if failed:
            click.echo(f"[ERROR] Failed ({len(failed)}): {', '.join(failed)}")
        if skipped:
            click.echo(f"[SKIP] Reserved by other agents ({len(skipped)}): {', '.join(skipped)}")


@local.command()
@click.option("--project", "-p", multiple=True, help="Specific project(s) to stop")
@click.option("--all", "stop_all", is_flag=True, help="Stop all projects")
@click.option("--keep-infra", is_flag=True, help="Keep shared infrastructure running")
@click.option(
    "--native-infra",
    is_flag=True,
    help="Stop hybrid infra (native Redis + Docker TimescaleDB) for the current/selected project",
)
@click.option("--port-offset", type=int, default=0, help="Port offset (must match what was used with 'up')")
@click.pass_context
def down(ctx, project, stop_all, keep_infra, native_infra, port_offset):
    """Stop local development services.

    Examples:
        sega local down --all            # Stop everything
        sega local down -p atlas      # Stop specific project
        sega local down --all --keep-infra # Stop projects but keep databases running
        sega local down -p atlas --native-infra  # Stop hybrid infra for project
    """
    config_file = ctx.obj.get("config_file")
    manager = LocalDeploymentManager(config_file=config_file)

    # Stop projects
    if stop_all:
        projects = manager.get_projects_with_compose()
        click.echo(f"[INFO] Stopping {len(projects)} projects...")
        for p in projects:
            manager.stop_project(p)
    elif project:
        for p in project:
            manager.stop_project(p)

    # Stop infrastructure (unless keeping it)
    if not keep_infra:
        if native_infra:
            # Stop hybrid infra for selected projects (or current project)
            projects_for_infra = list(project) if project else ([manager.current_project] if manager.current_project else [])
            if not projects_for_infra:
                click.echo("[ERROR] No project specified for --native-infra")
                click.echo("[INFO] Use -p PROJECT or run from within a project directory")
                return

            for proj in projects_for_infra:
                native_manager = NativeInfrastructureManager(project=proj, port_offset=port_offset)
                native_manager.stop()
            click.echo("[OK] Hybrid infrastructure stopped")
        else:
            # Docker infrastructure is shared across the workspace; only stop it when not targeting projects.
            if not project:
                infra_manager = SharedInfrastructureManager(workspace_root=manager.workspace_root, config=manager.config)
                infra_manager.stop()


@local.command()
@click.option("--project", "-p", multiple=True, help="Specific project(s) to restart")
@click.option("--all", "restart_all", is_flag=True, help="Restart all services")
@click.option("--infra-only", is_flag=True, help="Restart only infrastructure")
@click.pass_context
def restart(ctx, project, restart_all, infra_only):
    """Restart local development services.

    Examples:
        sega local restart --all         # Restart everything
        sega local restart -p atlas   # Restart specific project
        sega local restart --infra-only  # Restart just databases/redis
    """
    config_file = ctx.obj.get("config_file")
    manager = LocalDeploymentManager(config_file=config_file)
    infra_manager = SharedInfrastructureManager(workspace_root=manager.workspace_root, config=manager.config)

    if infra_only:
        infra_manager.restart()
        return

    if restart_all:
        # Restart infrastructure first
        infra_manager.restart()

        # Then restart all projects
        projects = manager.get_projects_with_compose()
        for p in projects:
            manager.stop_project(p)
            manager.deploy_project(
                p,
                runtime_mode={"backend": "python", "engine": "python"},
            )
    elif project:
        # Restart specific projects
        for p in project:
            manager.stop_project(p)
            manager.deploy_project(
                p,
                runtime_mode={"backend": "python", "engine": "python"},
            )


@local.command()
@click.option("--format", type=click.Choice(["table", "json", "simple"]), default="table")
@click.option("--infra", is_flag=True, help="Show infrastructure status")
@click.option(
    "--native-infra",
    is_flag=True,
    help="Show hybrid infra status (native Redis + Docker TimescaleDB)",
)
@click.option("--project", "-p", help="Project for hybrid infrastructure status")
@click.option("--port-offset", type=int, default=0, help="Port offset for hybrid infrastructure")
@click.pass_context
def status(ctx, format, infra, native_infra, project, port_offset):
    """Show status of local development services.

    Examples:
        sega local status              # Show all services
        sega local status --infra      # Show infrastructure details
        sega local status --format json # Output as JSON
        sega local status --native-infra  # Show hybrid infra status
        sega local status --native-infra -p atlas  # Show hybrid infra for project
    """
    config_file = ctx.obj.get("config_file")
    manager = LocalDeploymentManager(config_file=config_file)

    # Get project status
    project_status = manager.get_status()

    # Get infrastructure status
    if native_infra:
        # Show hybrid infrastructure status
        project_for_infra = project or manager.current_project
        native_manager = NativeInfrastructureManager(project=project_for_infra, port_offset=port_offset)
        infra_status = {"native": native_manager.status()}
    else:
        infra_manager = SharedInfrastructureManager(workspace_root=manager.workspace_root, config=manager.config)
        infra_status = infra_manager.get_status()

    if format == "json":
        import json

        output = {"projects": project_status, "infrastructure": infra_status}
        click.echo(json.dumps(output, indent=2))
        return

    # Table format
    workspace_name = manager.config.get("workspace", {}).get("name", "Local Workspace")
    click.echo(f"\n[INFO] {workspace_name} - Local Development Status")
    click.echo("=" * 60)

    # Infrastructure status
    if infra or native_infra or not project_status:
        if native_infra:
            click.echo("\n[INFO] Hybrid Infrastructure (--native-infra):")
            native_status = infra_status.get("native", {})
            for service, info in native_status.items():
                status_icon = "[OK]" if info.get("status") == "running" else "[--]"
                port = info.get("port", "N/A")
                typ = info.get("type", "")
                extra = f" Type: {typ}" if typ else ""
                if service == "postgres":
                    if info.get("database"):
                        extra += f" Database: {info['database']}"
                    if info.get("container"):
                        extra += f" Container: {info['container']}"
                click.echo(f"  {status_icon} {service:<12} Port: {port:<6}{extra}")
        else:
            click.echo("\n[INFO] Shared Infrastructure:")
            for env, services in infra_status.items():
                if any(s["running"] for s in services.values()):
                    click.echo(f"\n  {env.capitalize()} Environment:")
                    for service, info in services.items():
                        status_icon = "[OK]" if info["running"] else "[ERROR]"
                        health = info.get("health", "unknown")
                        port = info.get("port", "N/A")
                        click.echo(f"    {status_icon} {service:<12} Port: {port:<6} Health: {health}")

    # Project status
    if project_status:
        click.echo("\n[INFO] Projects:")

        if format == "simple":
            # Simple format
            for project, containers in sorted(project_status.items()):
                running = sum(1 for c in containers if c["status"] == "running")
                total = len(containers)
                status_icon = "[OK]" if running == total else "[WARNING]" if running > 0 else "[ERROR]"
                click.echo(f"  {status_icon} {project:<20} ({running}/{total} running)")
        else:
            # Detailed table format
            all_containers = []
            for project, containers in sorted(project_status.items()):
                for container in containers:
                    all_containers.append(
                        [
                            project,
                            container["name"].replace(f"fleet_{project}_", ""),
                            container["status"],
                            container.get("health", "N/A"),
                            ", ".join(f"{k}:{v[0]['HostPort']}" for k, v in container.get("ports", {}).items() if v)[
                                :30
                            ]
                            or "No ports",
                        ]
                    )

            if all_containers:
                headers = ["Project", "Service", "Status", "Health", "Ports"]
                click.echo("\n" + tabulate(all_containers, headers=headers, tablefmt="grid"))

    if not project_status and not any(
        any(s["running"] for s in services.values()) for services in infra_status.values()
    ):
        click.echo("\n[WARNING] No services are currently running")
        click.echo("Run 'sega local up --all' to start development environment")


@local.command()
@click.argument("project")
@click.option("--follow/--no-follow", "-f/-F", default=True, help="Follow log output")
@click.option("--tail", "-n", default=100, help="Number of lines to show from the end")
@click.option("--service", "-s", help="Show logs for specific service only")
@click.pass_context
def logs(ctx, project, follow, tail, service):
    """View logs for a project.

    Examples:
        sega local logs atlas          # Follow logs for atlas
        sega local logs sega -n 50        # Show last 50 lines
        sega local logs hermes -s backend  # Show only backend service logs
    """
    config_file = ctx.obj.get("config_file")
    manager = LocalDeploymentManager(config_file=config_file)

    click.echo(f"[INFO] Showing logs for {project}")
    if not follow:
        click.echo("[INFO] Not following logs (use -f to follow)")
    else:
        click.echo("[INFO] Following logs (Ctrl+C to stop)")

    manager.show_logs(project, follow=follow, tail=tail, service=service)


def _deploy_with_ledger(
    manager,
    ledger,
    agent_id,
    projects,
    env_mode=None,
    runtime_mode=None,
    port_offset=0,
    infra_env_vars=None,
    exclude_apps=None,
    project_app_excludes=None,
):
    """
    Deploy projects with ledger coordination for concurrent testing.

    Args:
        manager: LocalDeploymentManager instance
        ledger: ProjectLedger instance (or None to skip ledger)
        agent_id: Agent identifier for reservation
        projects: List of project names to deploy
        env_mode: Dict mapping component names to environment mode ('docker', 'shared', 'project')
        runtime_mode: Dict mapping component names to runtime ('python' or 'rust')
        port_offset: Integer offset to add to all ports (default 0)
        infra_env_vars: Infrastructure environment variables from NativeInfrastructureManager
        exclude_apps: Set of app names to exclude (landing, product, frontend, backend, engine, ide)
        project_app_excludes: Dict mapping project -> set of app names to exclude

    Returns:
        Dict mapping project names to result dicts with 'success' and 'skipped' flags
    """
    results = {}

    exclude_apps = exclude_apps or set()
    project_app_excludes = project_app_excludes or {}

    # Default to all docker if not specified
    if env_mode is None:
        env_mode = {"backend": "docker", "engine": "docker", "frontend": "docker"}
    if runtime_mode is None:
        runtime_mode = {"backend": "python", "engine": "python"}

    for project_name in projects:
        # Check if ledger should be used
        if ledger is None:
            # No ledger - direct deployment
            success = manager.deploy_project(
                project_name,
                env_mode=env_mode,
                runtime_mode=runtime_mode,
                port_offset=port_offset,
                infra_env_vars=infra_env_vars,
                exclude_apps=exclude_apps,
                project_app_excludes=project_app_excludes,
            )
            results[project_name] = {"success": success, "skipped": False}
            continue

        # Try to acquire project reservation
        if not ledger.acquire(project_name, agent_id):
            # Project is reserved by another agent
            reservation = ledger.get_reservation(project_name)
            click.echo(
                f"[SKIP] {project_name} - Reserved by {reservation['agent_id']} "
                f"(since {reservation['reserved_at'][:19]})"
            )
            results[project_name] = {"success": False, "skipped": True}
            continue

        # Acquired reservation - deploy project
        try:
            click.echo(f"[INFO] {project_name} - Acquired reservation (agent: {agent_id})")
            success = manager.deploy_project(
                project_name,
                env_mode=env_mode,
                runtime_mode=runtime_mode,
                port_offset=port_offset,
                infra_env_vars=infra_env_vars,
                exclude_apps=exclude_apps,
                project_app_excludes=project_app_excludes,
            )

            # Release with appropriate status
            status = "completed" if success else "failed"
            ledger.release(project_name, agent_id, status=status)

            results[project_name] = {"success": success, "skipped": False}

        except Exception as e:
            # Ensure release on exception
            ledger.release(project_name, agent_id, status="failed")
            click.echo(f"[ERROR] {project_name} - Deployment exception: {e}")
            results[project_name] = {"success": False, "skipped": False}

    return results


@local.command(name="list")
@click.pass_context
def list_projects(ctx):
    """List all available projects with Docker Compose configuration."""
    config_file = ctx.obj.get("config_file")
    manager = LocalDeploymentManager(config_file=config_file)

    projects = manager.get_projects_with_compose()

    click.echo("\n[INFO] Available Projects with Docker Compose:")
    click.echo("=" * 40)

    for project in sorted(projects):
        project_dir = manager.workspace_root / project

        # Check which compose file exists
        compose_files = []
        if (project_dir / "docker-compose.yml").exists():
            compose_files.append("docker-compose.yml")
        if (project_dir / "docker-compose.dev.yml").exists():
            compose_files.append("docker-compose.dev.yml")
        if (project_dir / "deployment" / "docker-compose.yml").exists():
            compose_files.append("deployment/docker-compose.yml")
        # Telemetry-integration compose bundled inside a project, if the fleet
        # has a configured telemetry project.
        _telemetry = get_config().fleet.telemetry_project
        if _telemetry and (project_dir / _telemetry / "docker-compose.yml").exists():
            compose_files.append(f"{_telemetry}/docker-compose.yml")

        # Check if has Makefile
        has_makefile = (project_dir / "Makefile").exists()

        click.echo(f"\n{project}:")
        click.echo(f"  Compose files: {', '.join(compose_files)}")
        if has_makefile:
            click.echo("  Has Makefile: [OK]")

    click.echo(f"\nTotal: {len(projects)} projects")


@local.command()
@click.option("--profile", type=click.Choice(["development", "testing"]), default="development")
@click.pass_context
def setup(ctx, profile):
    """Setup local development environment.

    This command will:
    - Create shared virtual environment
    - Initialize project databases
    - Generate development certificates
    - Setup development tools

    Examples:
        sega local setup              # Setup development environment
        sega local setup --profile testing  # Setup testing environment
    """
    config_file = ctx.obj.get("config_file")
    manager = LocalDeploymentManager(config_file=config_file)
    infra_manager = SharedInfrastructureManager(workspace_root=manager.workspace_root, config=manager.config)

    click.echo(f"[INFO] Setting up {profile} environment...")

    # Ensure shared venv
    if not manager.ensure_shared_venv():
        click.echo("[ERROR] Failed to setup shared virtual environment")
        return

    # Start infrastructure
    if not infra_manager.start(profile=profile):
        click.echo("[ERROR] Failed to start infrastructure")
        return

    # Create project databases
    projects = manager.get_projects_with_compose()
    infra_manager.create_databases(projects, profile=profile)

    click.echo("\n[OK] Local development environment is ready!")
    click.echo("\nNext steps:")
    click.echo("  sega local up --all    # Start all projects")
    click.echo("  sega local status      # Check status")
    click.echo("  sega local logs PROJECT # View project logs")


@local.command()
@click.option("--project", "-p", help="Specific project to setup nginx for (auto-detected if not provided)")
@click.option("--domain", "-d", help="Domain name for nginx setup (auto-detected if not provided)")
@click.option("--ssl", is_flag=True, help="Setup self-signed SSL certificates for local development")
@click.option("--dry-run", is_flag=True, help="Preview nginx configuration without applying")
@click.pass_context
def nginx(ctx, project, domain, ssl, dry_run):
    """Setup nginx reverse proxy for local development.

    This command sets up nginx configuration for local project testing
    with proper reverse proxy configuration and optional SSL certificates.

    Examples:
        sega local nginx                     # Auto-detect project and setup nginx
        sega local nginx -p atlas         # Setup nginx for specific project
        sega local nginx --ssl               # Setup nginx with self-signed SSL
        sega local nginx --dry-run           # Preview configuration
    """
    try:
        from .nginx import NginxManager

        # Determine project path
        if project:
            config_file = ctx.obj.get("config_file")
            manager = LocalDeploymentManager(config_file=config_file)
            project_path = manager.workspace_root / project

            if not project_path.exists():
                click.echo(f" Project '{project}' not found in workspace")
                return
        else:
            project_path = Path.cwd()

        # Initialize nginx manager for this project
        nginx_manager = NginxManager(project_path)

        # Auto-detect domain if not provided
        if not domain:
            project_name = project or project_path.name
            domain = f"{project_name}.local"

        click.echo(" Setting up nginx for local development...")
        click.echo(f"   Project: {nginx_manager.project_info['name']}")
        click.echo(f"   Domain: {domain}")
        click.echo(f"   SSL: {'Enabled (self-signed)' if ssl else 'Disabled'}")

        # Setup nginx configuration
        if nginx_manager.setup_nginx(domain=domain, ssl=ssl, dry_run=dry_run):
            if not dry_run:
                click.echo(" Nginx configuration complete!")

                # Setup self-signed SSL if requested
                if ssl:
                    click.echo("\n Setting up self-signed SSL certificates...")
                    if nginx_manager.setup_ssl(domain=domain, self_signed=True):
                        click.echo(" Self-signed SSL certificates created!")
                        click.echo(f" Local site available at: https://{domain}")
                        click.echo("ℹ️  Note: You'll need to accept the self-signed certificate in your browser")
                    else:
                        click.echo("️  SSL setup failed, but site is available via HTTP")
                        click.echo(f" Local site available at: http://{domain}")
                else:
                    click.echo(f" Local site available at: http://{domain}")

                click.echo("\nTo access your local site:")
                click.echo(f"  1. Add '{domain} 127.0.0.1' to /etc/hosts")
                click.echo(f"  2. Start your project: sega local up -p {nginx_manager.project_info['name']}")
                click.echo(f"  3. Visit: {'https' if ssl else 'http'}://{domain}")
        else:
            click.echo(" Nginx setup failed")

    except ImportError as e:
        click.echo(f" Could not import nginx module: {e}")
        click.echo("Ensure nginx dependencies are installed")
    except Exception as e:
        click.echo(f" Error setting up nginx: {e}")


# Port allocation and production domains now live in config (sega.core.config).
# Reference: /docs/standards/infrastructure/PORT_ALLOCATION_STANDARDS.md,
#            /docs/standards/infrastructure/URL_AND_ADDRESSING_REGISTRY.md

# Utility/CLI-only projects (no web frontend to open). Pure control logic.
# Sourced from config: "local" (non-served) projects are the CLI-only/utility set.
UTILITY_PROJECTS = {p.name for p in get_config().get_local_projects()}

# Inline fallback for legacy entries with no config equivalent.
# test_proj is a synthetic test project: no configured ports or domain.
_FALLBACK_PORTS = {
    "test_proj": {"api": 8020, "frontend": 3020, "metrics": 9020},
}
_FALLBACK_DOMAINS = {
    "test_proj": {"prod": "fleet.com", "dev": None},
}


def _project_ports(name: str) -> dict:
    """Port map for a project, sourced from config (with legacy fallback).

    Returns {} for unknown projects, matching the old ``PROJECT_PORTS.get(name, {})``.
    """
    proj = get_config().get_project(name)
    if proj is not None:
        p = proj.ports
        return {
            "api": p.api,
            "frontend": p.frontend,
            "desktop": p.desktop,
            "mobile": p.mobile,
            "metrics": p.metrics,
        }
    return _FALLBACK_PORTS.get(name, {})


def _known_projects() -> set:
    """Set of project names recognized by ``open``/``launch`` (config + fallbacks)."""
    return set(get_config().projects.keys()) | set(_FALLBACK_PORTS.keys())


def _project_domains(name: str) -> dict:
    """Domain map ({"prod","dev"}) for a project, sourced from config.

    Returns {} for projects with no configured/fallback domain.
    """
    prod = get_config().get_domain(name, env="prod")
    if prod is not None:
        return {"prod": prod, "dev": get_config().get_domain(name, env="dev")}
    return _FALLBACK_DOMAINS.get(name, {})


def _has_domain(name: str) -> bool:
    """Whether a project has any configured/fallback domain (old ``in PROJECT_DOMAINS``)."""
    return bool(_project_domains(name))


def _resolve_remote_host(remote: str):
    """Resolve a --remote shorthand (1/2/group1/group2) to an instance IP.

    Ordered config instances back the numeric groups; returns None for unknown
    shorthands so the caller can treat the value as a literal host.
    """
    instances = list(get_config().instances.values())
    index_map = {"1": 0, "group1": 0, "2": 1, "group2": 1}
    idx = index_map.get(remote)
    if idx is not None and idx < len(instances):
        return instances[idx].ip
    return None


def _discover_frontend_routes(project: str, workspace_root: Path = None) -> list:
    """Discover all frontend routes for a Next.js project.

    Scans the project's frontend directory for page.tsx files and extracts routes.
    Supports both dual-app (landing_app/product_app) and single-app architectures.

    Args:
        project: Project name
        workspace_root: Root directory of workspace (defaults to ~/fleet)

    Returns:
        List of dicts with 'route', 'app' (landing/product/main), 'file' keys
    """
    import re

    if workspace_root is None:
        workspace_root = Path.home() / "fleet"

    project_path = workspace_root / project
    routes = []

    # Check for dual-app structure first
    landing_app = project_path / "frontend" / "landing_app" / "src" / "app"
    product_app = project_path / "frontend" / "product_app" / "src" / "app"
    single_app = project_path / "frontend" / "src" / "app"

    def extract_routes(app_dir: Path, app_name: str):
        """Extract routes from a Next.js app directory."""
        if not app_dir.exists():
            return []

        found_routes = []
        for page_file in app_dir.rglob("page.tsx"):
            # Convert file path to route
            rel_path = page_file.relative_to(app_dir)
            route = "/" + str(rel_path.parent)

            # Clean up route
            route = route.replace("/page", "")
            if route == "/.":
                route = "/"

            # Strip route groups like (protected), (auth), (public)
            route = re.sub(r"\([^)]+\)/", "", route)
            route = re.sub(r"\([^)]+\)$", "", route)

            # Skip dynamic routes with [param] - they need actual values
            if "[" in route:
                continue

            # Skip API routes
            if "/api/" in route or route.startswith("/api"):
                continue

            # Normalize double slashes
            route = re.sub(r"/+", "/", route)
            if route != "/" and route.endswith("/"):
                route = route.rstrip("/")

            found_routes.append(
                {
                    "route": route,
                    "app": app_name,
                    "file": str(page_file),
                }
            )

        return found_routes

    # Check architectures in order of preference
    if landing_app.exists() and product_app.exists():
        # Dual-app architecture
        routes.extend(extract_routes(landing_app, "landing"))
        routes.extend(extract_routes(product_app, "product"))
    elif single_app.exists():
        # Single-app architecture
        routes.extend(extract_routes(single_app, "main"))
    else:
        # Try direct structure (no frontend/ subdirectory)
        direct_app = project_path / "src" / "app"
        if direct_app.exists():
            routes.extend(extract_routes(direct_app, "main"))

    # Sort routes for consistent ordering
    routes.sort(key=lambda r: (r["app"], r["route"]))

    return routes


def _check_url_reachable(url: str, timeout: float = 3.0) -> dict:
    """Check if a URL is reachable via HTTP(S).

    Args:
        url: URL to check
        timeout: Timeout in seconds

    Returns:
        dict with 'reachable', 'status_code', 'response_time', 'error'
    """
    import urllib.request
    import urllib.error
    import time
    import ssl

    result = {"url": url, "reachable": False, "status_code": None, "response_time": None, "error": None}

    try:
        start = time.time()

        # Create SSL context that doesn't verify (for self-signed certs in dev)
        ctx = ssl.create_default_context()
        ctx.check_hostname = False
        ctx.verify_mode = ssl.CERT_NONE

        req = urllib.request.Request(url, method="HEAD")
        req.add_header("User-Agent", "SEGA-Ping/1.0")

        with urllib.request.urlopen(req, timeout=timeout, context=ctx) as response:
            result["status_code"] = response.status
            result["reachable"] = response.status < 400
            result["response_time"] = round((time.time() - start) * 1000)  # ms

    except urllib.error.HTTPError as e:
        result["status_code"] = e.code
        result["reachable"] = e.code < 500  # 4xx might be auth required but reachable
        result["error"] = str(e.reason)
    except urllib.error.URLError as e:
        result["error"] = str(e.reason)
    except Exception as e:
        result["error"] = str(e)

    return result


# Project groups for scanning, from the curated `[fleet.scan_groups]` config
# map (ships empty for new installs).
INSTANCE_1_PROJECTS = list(get_config().fleet.scan_groups.get("group1", []))
INSTANCE_2_PROJECTS = list(get_config().fleet.scan_groups.get("group2", []))
# Display/priority order for browser opening (formerly PROJECT_DOMAINS key order).
# Domain data itself comes from config; the curated `[fleet] web_priority`
# config list only fixes presentation order.
_WEB_PROJECT_PRIORITY = list(get_config().fleet.web_priority)
ALL_WEB_PROJECTS = [p for p in _WEB_PROJECT_PRIORITY if p not in UTILITY_PROJECTS]


@local.command()
@click.option("--project", "-p", multiple=True, help="Specific project(s) to open")
@click.option(
    "--target",
    "-t",
    type=click.Choice(["web", "api", "ide", "mobile", "metrics", "docs", "all"]),
    default="web",
    help="Target to open: web, api, ide, mobile, metrics, docs, all",
)
@click.option(
    "--env",
    "-e",
    type=click.Choice(["local", "dev", "prod"]),
    default="prod",
    help="Environment: local (localhost:port), dev (staging.{domain}), prod (production domains)",
)
@click.option(
    "--remote", "-r", help="Open on remote EC2 instance (1, 2, group1, group2, or IP) - forces local env with IP"
)
@click.option("--list", "list_only", is_flag=True, help="List URLs without opening")
@click.option("--port-offset", type=int, default=0, help="Port offset (for test environments)")
@click.option("--ping", "ping_check", is_flag=True, help="Check which URLs are reachable before opening")
@click.option("--ping-only", is_flag=True, help="Only check reachability, do not open browser")
@click.option("--timeout", type=float, default=3.0, help="Timeout in seconds for ping checks (default: 3.0)")
@click.option("--scan", is_flag=True, help="Scan all projects for the instance/environment (auto-select projects)")
@click.option("--pages", is_flag=True, help="Discover and open all frontend pages/routes for the project")
@click.option(
    "--app",
    "app_filter",
    type=click.Choice(["landing", "product", "all"]),
    default="all",
    help="Filter pages by app type (landing, product, or all)",
)
@click.pass_context
def open(
    ctx, project, target, env, remote, list_only, port_offset, ping_check, ping_only, timeout, scan, pages, app_filter
):
    """Open project URLs in browser.

    Opens web browser to project endpoints based on target type.
    Supports local development, remote EC2 instances, and production domains.

    Targets:
        web      Web frontend (localhost:3XXX or production domain)
        api      API documentation (localhost:8XXX/docs or api.domain/docs)
        ide      IDE dev server (localhost:33XX) or IDE web page (ide.domain)
        mobile   Mobile app (exp://localhost or app.domain)
        metrics  Metrics endpoint (localhost:9XXX, local only)
        docs     Alias for api

    Examples:
        sega local open -p atlas             # Open atlas.example.com (prod)
        sega local open -p atlas -e dev      # Open staging.atlas.example.com
        sega local open -p atlas -e local    # Open localhost:3009
        sega local open -p atlas -t api      # Open api.atlas.example.com/docs
        sega local open -p atlas -t ide -e local  # Open localhost:3309
        sega local open --remote 1 -p atlas  # Open http://203.0.113.10:3009
        sega local open --list                   # List URLs without opening
        sega local open -t all -p atlas      # Open all endpoints

    Ping options:
        sega local open --ping -p atlas      # Check reachability, then open reachable URLs
        sega local open --ping-only -p atlas # Only check reachability (no browser)
        sega local open --ping --timeout 5       # Use 5 second timeout for checks
        sega local open --ping -t all            # Check all endpoints for all projects

    Scan options (auto-select projects for instance):
        sega local open --scan --ping-only -e local          # Scan all local projects
        sega local open --scan --ping-only --remote 1        # Scan EC2 Instance 1 (Group 1)
        sega local open --scan --ping-only --remote 2        # Scan EC2 Instance 2 (Group 2)
        sega local open --scan --ping --remote 1 -t api      # Scan & open reachable APIs on Instance 1

    Pages options (open all frontend routes):
        sega local open --pages -p atlas -e local        # Open all pages on localhost
        sega local open --pages -p atlas -e prod         # Open all pages on production domain
        sega local open --pages -p atlas --remote 2      # Open all pages on EC2 Instance 2
        sega local open --pages -p atlas --list          # List all discovered routes without opening
        sega local open --pages -p atlas --app product   # Open only product app pages
        sega local open --pages -p atlas --app landing   # Open only landing app pages
    """
    import webbrowser

    # Determine host/mode
    use_domain = True
    if remote:
        # Remote mode uses IP:port
        host = _resolve_remote_host(remote) or remote
        use_domain = False
        click.echo(f"  Target: Remote ({host})")
    elif env == "local":
        host = "localhost"
        use_domain = False
        click.echo(f"  Target: Local ({host})")
    else:
        host = None  # Will use domain names
        click.echo(f"  Target: {env.upper()} domains")

    # Determine projects to open
    projects_to_open = []

    if scan:
        # Auto-select projects based on instance/environment
        if remote in ("1", "group1"):
            projects_to_open = INSTANCE_1_PROJECTS.copy()
            click.echo(f"  Scanning: Instance 1 projects ({len(projects_to_open)} projects)")
        elif remote in ("2", "group2"):
            projects_to_open = INSTANCE_2_PROJECTS.copy()
            click.echo(f"  Scanning: Instance 2 projects ({len(projects_to_open)} projects)")
        elif remote:
            # Custom IP - scan all web projects
            projects_to_open = ALL_WEB_PROJECTS.copy()
            click.echo(f"  Scanning: All web projects ({len(projects_to_open)} projects)")
        else:
            # Local or domain - scan all web projects
            projects_to_open = ALL_WEB_PROJECTS.copy()
            click.echo(f"  Scanning: All web projects ({len(projects_to_open)} projects)")
    elif project:
        projects_to_open = [p for p in project]
    else:
        # Auto-detect from current directory
        known_projects = _known_projects()
        cwd = Path.cwd()
        project_name = cwd.name
        if project_name in known_projects:
            projects_to_open = [project_name]
        else:
            # Check if we're in a subdirectory of a project
            for parent in cwd.parents:
                if parent.name in known_projects:
                    projects_to_open = [parent.name]
                    break

        if not projects_to_open:
            click.echo("  Could not auto-detect project. Use -p to specify, or use --scan.")
            click.echo(f"\n  Available projects: {', '.join(sorted(_known_projects()))}")
            return

    # Validate projects and filter out utilities
    known_projects = _known_projects()
    valid_projects = []
    for proj in projects_to_open:
        if proj not in known_projects:
            click.echo(f"  Unknown project: {proj}")
            click.echo(f"  Available: {', '.join(sorted(known_projects))}")
            return
        if proj in UTILITY_PROJECTS:
            click.echo(f"  Skipping utility project: {proj} (CLI-only, no web frontend)")
            continue
        if use_domain and not _has_domain(proj):
            click.echo(f"  Skipping {proj}: no domain configured")
            continue
        valid_projects.append(proj)

    projects_to_open = valid_projects
    if not projects_to_open:
        click.echo("  No projects to open after filtering")
        return

    # Handle --pages mode: discover and open all frontend routes
    if pages:
        urls = []
        for proj in projects_to_open:
            ports = _project_ports(proj)
            domains = _project_domains(proj)

            # Discover routes for this project
            routes = _discover_frontend_routes(proj)

            if not routes:
                click.echo(f"  No routes discovered for {proj}")
                continue

            # Filter by app type if specified
            if app_filter != "all":
                # Map 'main' to match 'all' filter (single-app projects)
                routes = [
                    r for r in routes if r["app"] == app_filter or (app_filter == "product" and r["app"] == "main")
                ]

            if not routes:
                click.echo(f"  No {app_filter} routes found for {proj}")
                continue

            click.echo(f"  Discovered {len(routes)} {app_filter if app_filter != 'all' else ''} routes for {proj}")

            # Determine base URLs for landing vs product apps
            # Dual-app: landing on frontend port, product on frontend port (same domain, different base)
            # For local: landing=3XXX, product=3XX1 (offset by 1) - but typically same port
            frontend_port = ports.get("frontend", 3000) + port_offset

            for route_info in routes:
                route = route_info["route"]
                app = route_info["app"]

                if use_domain and _has_domain(proj):
                    domain = domains.get("prod" if env == "prod" else "dev")
                    if not domain:
                        continue
                    # For dual-app, product app is typically at app.domain or same domain
                    # Landing is at root domain
                    if app == "product":
                        base_url = f"https://app.{domain}"
                    else:
                        base_url = f"https://{domain}"
                    url = f"{base_url}{route}"
                    port_display = "-"
                else:
                    # Local/remote mode uses ports
                    # For dual-app structure, product might be on different port
                    if app == "product":
                        # Product app typically on port + 1 for local dev
                        app_port = frontend_port + 1
                    else:
                        app_port = frontend_port
                    url = f"http://{host}:{app_port}{route}"
                    port_display = app_port

                urls.append(
                    {
                        "project": proj,
                        "target": f"{app}:{route}",
                        "port": port_display,
                        "url": url,
                        "app": app,
                        "route": route,
                    }
                )

        if not urls:
            click.echo("  No page URLs discovered")
            return

        # Display discovered pages
        click.echo(f"\n  {'Project':<16} {'App':<10} {'Route':<30} URL")
        click.echo(f"  {'-' * 16} {'-' * 10} {'-' * 30} {'-' * 50}")

        for u in urls:
            click.echo(f"  {u['project']:<16} {u.get('app', '-'):<10} {u.get('route', '-'):<30} {u['url']}")

        # Open in browser if not list-only
        if not list_only:
            click.echo(f"\n  Opening {len(urls)} page(s) in browser...")
            for u in urls:
                try:
                    webbrowser.open(u["url"])
                    click.echo(f"  Opened: {u['url']}")
                except Exception as e:
                    click.echo(f"  Failed to open {u['url']}: {e}")
        else:
            click.echo(f"\n  Use without --list to open {len(urls)} pages in browser")

        return

    # Build URLs
    urls = []
    targets = ["web", "api", "ide", "mobile", "metrics"] if target == "all" else [target]

    # Map new target names to port keys
    target_to_port_key = {
        "web": "frontend",
        "ide": "desktop",
        "api": "api",
        "mobile": "mobile",
        "metrics": "metrics",
        "docs": "api",
    }

    for proj in projects_to_open:
        ports = _project_ports(proj)
        domains = _project_domains(proj)

        for t in targets:
            port = None
            url = None

            if use_domain and _has_domain(proj):
                # Use domain-based URLs
                domain = domains.get("prod" if env == "prod" else "dev")
                if not domain:
                    continue

                if t == "web":
                    url = f"https://{domain}"
                elif t == "api" or t == "docs":
                    url = f"https://api.{domain}/docs"
                elif t == "ide":
                    url = f"https://ide.{domain}"  # IDE web page / download
                elif t == "mobile":
                    url = f"https://app.{domain}"  # Mobile web app
                elif t == "metrics":
                    continue  # Metrics not exposed via domain
                port = "-"
            else:
                # Use IP:port URLs
                port_key = target_to_port_key.get(t, t)
                if port_key in ports:
                    port = ports[port_key] + port_offset
                    if t == "api" or t == "docs":
                        url = f"http://{host}:{port}/docs"
                    elif t == "mobile":
                        url = f"exp://{host}:{port}"
                    else:
                        url = f"http://{host}:{port}"
                else:
                    continue

            if url:
                urls.append({"project": proj, "target": t, "port": port if port else "-", "url": url})

    if not urls:
        click.echo("  No URLs to open")
        return

    # Ping check if requested
    do_ping = ping_check or ping_only
    if do_ping:
        click.echo(f"\n  Checking reachability (timeout: {timeout}s)...")
        for u in urls:
            # Skip non-HTTP URLs (like exp:// for mobile)
            if not u["url"].startswith("http"):
                u["reachable"] = None
                u["ping_info"] = "N/A (non-HTTP)"
                continue

            result = _check_url_reachable(u["url"], timeout=timeout)
            u["reachable"] = result["reachable"]

            if result["reachable"]:
                time_str = f"{result['response_time']}ms" if result["response_time"] else ""
                if result["status_code"]:
                    u["ping_info"] = f"{result['status_code']} ({time_str})" if time_str else f"{result['status_code']}"
                else:
                    u["ping_info"] = f"OK ({time_str})" if time_str else "OK"
            else:
                if result["error"]:
                    u["ping_info"] = result["error"]
                elif result["status_code"]:
                    u["ping_info"] = f"HTTP {result['status_code']}"
                else:
                    u["ping_info"] = "unreachable"

    # Display URLs with ping status if checked
    if do_ping:
        click.echo(f"\n  {'Project':<16} {'Target':<10} {'Port':<6} {'Status':<20} URL")
        click.echo(f"  {'-' * 16} {'-' * 10} {'-' * 6} {'-' * 20} {'-' * 40}")

        for u in urls:
            status = u.get("ping_info", "-")
            icon = "[OK]" if u.get("reachable") else "[--]" if u.get("reachable") is None else "[X]"
            click.echo(f"  {u['project']:<16} {u['target']:<10} {u['port']:<6} {icon} {status:<15} {u['url']}")

        # Summary
        reachable = [u for u in urls if u.get("reachable") is True]
        unreachable = [u for u in urls if u.get("reachable") is False]
        skipped = [u for u in urls if u.get("reachable") is None]

        click.echo(f"\n  Summary: {len(reachable)} reachable, {len(unreachable)} unreachable, {len(skipped)} skipped")

        if ping_only:
            return
    else:
        # Standard display without ping
        click.echo(f"\n  {'Project':<20} {'Target':<12} {'Port':<8} URL")
        click.echo(f"  {'-' * 20} {'-' * 12} {'-' * 8} {'-' * 40}")

        for u in urls:
            click.echo(f"  {u['project']:<20} {u['target']:<12} {u['port']:<8} {u['url']}")

    # Open in browser if not list-only
    if not list_only:
        # Filter to reachable URLs if ping was used
        urls_to_open = urls
        if ping_check:
            urls_to_open = [u for u in urls if u.get("reachable") is not False]
            if not urls_to_open:
                click.echo("\n  No reachable URLs to open")
                return

        click.echo(f"\n  Opening {len(urls_to_open)} URL(s) in browser...")
        for u in urls_to_open:
            try:
                webbrowser.open(u["url"])
                click.echo(f"  Opened: {u['url']}")
            except Exception as e:
                click.echo(f"  Failed to open {u['url']}: {e}")
    else:
        click.echo(f"\n  Use without --list to open in browser")


@local.command()
@click.option("--project", "-p", help="Project to launch (auto-detected if not specified)")
@click.option(
    "--target",
    "-t",
    type=click.Choice(["desktop", "ide"]),
    default="desktop",
    help="Target type: desktop (Electron) or ide (VS Code fork)",
)
@click.option("--path", type=click.Path(), help="Path to application binary/bundle (required unless --dev)")
@click.option("--dev", is_flag=True, help="Run in development mode (npm run electron:dev)")
@click.pass_context
def launch(ctx, project, target, path, dev):
    """Launch local application binaries.

    Executes packaged desktop applications or IDE binaries.
    Use --dev to run unpackaged in development mode.

    Targets:
        desktop  Electron-based desktop application
        ide      VS Code fork IDE application

    Examples:
        sega local launch -t desktop --path ./dist/MyApp.app
        sega local launch -t ide --path ~/apps/BoltzmannIDE.app
        sega local launch -t desktop --dev -p atlas
        sega local launch -t ide --dev
    """
    import subprocess
    import platform
    import os

    def _resolve_project_path(project_name: str) -> str:
        """Resolve project path from name or auto-detect from cwd."""
        if project_name:
            # Try to find project in known locations
            fleet_root = Path.home() / "fleet"
            project_path = fleet_root / project_name
            if project_path.exists():
                return str(project_path)
            click.echo(f"  Project not found at: {project_path}")
            return None

        # Auto-detect from current directory
        known_projects = _known_projects()
        cwd = Path.cwd()
        project_name = cwd.name
        if project_name in known_projects:
            return str(cwd)

        # Check if we're in a subdirectory of a project
        for parent in cwd.parents:
            if parent.name in known_projects:
                return str(parent)

        return None

    def _launch_binary(binary_path: str) -> bool:
        """Launch a binary application (platform-aware)."""
        system = platform.system()
        binary_path = os.path.expanduser(binary_path)

        if not os.path.exists(binary_path):
            click.echo(f"  Error: Path does not exist: {binary_path}")
            return False

        try:
            if system == "Darwin":  # macOS
                subprocess.Popen(["open", binary_path])
            elif system == "Linux":
                # Make executable if needed, then run
                if os.path.isfile(binary_path):
                    subprocess.Popen([binary_path], start_new_session=True)
                else:
                    # Directory (AppImage extracted or similar)
                    click.echo(f"  Error: Expected executable file, got directory: {binary_path}")
                    return False
            elif system == "Windows":
                os.startfile(binary_path)
            else:
                click.echo(f"  Unsupported platform: {system}")
                return False

            click.echo(f"  Launched: {binary_path}")
            return True
        except Exception as e:
            click.echo(f"  Failed to launch: {e}")
            return False

    def _launch_dev_mode(project_path: str, target_type: str) -> bool:
        """Launch application in development mode."""
        if target_type == "desktop":
            cmd = "npm run electron:dev"
        elif target_type == "ide":
            cmd = "npm run watch"
        else:
            click.echo(f"  Unknown target type: {target_type}")
            return False

        click.echo(f"  Starting {target_type} in dev mode...")
        click.echo(f"  Directory: {project_path}")
        click.echo(f"  Command: {cmd}")

        try:
            # Run in background, don't wait for completion
            subprocess.Popen(cmd, shell=True, cwd=project_path, start_new_session=True)
            click.echo(f"  Dev server started in background")
            return True
        except Exception as e:
            click.echo(f"  Failed to start dev mode: {e}")
            return False

    # Main logic
    click.echo(f"\n  SEGA Local Launch")
    click.echo(f"  {'-' * 40}")
    click.echo(f"  Target: {target}")

    if dev:
        # Dev mode: need project path
        project_path = _resolve_project_path(project)
        if not project_path:
            click.echo("  Error: Could not detect project. Use -p to specify.")
            click.echo(f"\n  Available projects: {', '.join(sorted(_known_projects()))}")
            return

        click.echo(f"  Mode: Development")
        _launch_dev_mode(project_path, target)
    else:
        # Binary mode: need --path
        if not path:
            click.echo("  Error: --path is required when not using --dev mode")
            click.echo("\n  Examples:")
            click.echo("    sega local launch -t desktop --path ./dist/MyApp.app")
            click.echo("    sega local launch -t ide --path ~/apps/IDE.app")
            click.echo("\n  Or use --dev for development mode:")
            click.echo("    sega local launch -t desktop --dev -p atlas")
            return

        click.echo(f"  Mode: Binary")
        _launch_binary(path)


# =============================================================================
# macOS Native Infrastructure (Truly Dockerless)
# =============================================================================

@local.group()
def macos():
    """macOS native infrastructure (truly dockerless).
    
    Manages PostgreSQL and Redis as native Homebrew services.
    No Docker required - optimal for Mac Mini development machines.
    
    \b
    Setup (one-time):
        sega local macos setup
    
    \b
    Daily usage:
        sega local macos start          # Start PostgreSQL + Redis
        sega local macos run atlas      # Run atlas backend directly
        sega local macos run hermes      # Run hermes backend directly
    
    \b
    Database management:
        sega local macos createdb atlas # Create database for project
        sega local macos createall      # Create all project databases
    """
    import sys
    if sys.platform != "darwin":
        click.echo("[ERROR] macOS commands only work on macOS")
        raise SystemExit(1)


@macos.command("setup")
def macos_setup():
    """One-time setup of PostgreSQL and Redis via Homebrew."""
    from ...local import MacOSNativeInfraManager
    mgr = MacOSNativeInfraManager()
    mgr.setup()


@macos.command("start")
def macos_start():
    """Start PostgreSQL and Redis services."""
    from ...local import MacOSNativeInfraManager
    mgr = MacOSNativeInfraManager()
    mgr.start()


@macos.command("stop")
def macos_stop():
    """Stop PostgreSQL and Redis services."""
    from ...local import MacOSNativeInfraManager
    mgr = MacOSNativeInfraManager()
    mgr.stop()


@macos.command("restart")
def macos_restart():
    """Restart PostgreSQL and Redis services."""
    from ...local import MacOSNativeInfraManager
    mgr = MacOSNativeInfraManager()
    mgr.restart()


@macos.command("status")
def macos_status():
    """Show status of infrastructure services."""
    from ...local import MacOSNativeInfraManager
    mgr = MacOSNativeInfraManager()
    status = mgr.status()
    
    click.echo("\nmacOS Native Infrastructure Status:")
    click.echo("-" * 40)
    for service, info in status.items():
        status_str = "running" if info["ready"] else "stopped"
        click.echo(f"  {service}: {status_str} (port {info['port']})")


@macos.command("createdb")
@click.argument("project")
def macos_createdb(project):
    """Create database for a project."""
    from ...local import MacOSNativeInfraManager
    mgr = MacOSNativeInfraManager()
    mgr.create_database(project)


@macos.command("createall")
def macos_createall():
    """Create databases for all projects."""
    from ...local import MacOSNativeInfraManager
    mgr = MacOSNativeInfraManager()
    mgr.create_all_databases()


@macos.command("env")
@click.argument("project")
def macos_env(project):
    """Print environment variables for a project."""
    from ...local import MacOSNativeInfraManager
    mgr = MacOSNativeInfraManager()
    mgr.print_env_vars(project)


@macos.command("run")
@click.argument("project")
@click.option("--port", "-p", type=int, help="Override API port")
def macos_run(project, port):
    """Run a project backend directly (no Docker).
    
    \b
    Examples:
        sega local macos run atlas          # Run atlas on port 8001
        sega local macos run hermes          # Run hermes on port 8004
        sega local macos run orion -p 9000  # Run orion on custom port
    """
    from ...local import MacOSNativeInfraManager
    mgr = MacOSNativeInfraManager()
    mgr.run_backend(project, port)


# Register the command group
if __name__ == "__main__":
    local()
