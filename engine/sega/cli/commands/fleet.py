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
SEGA FLEET MANAGEMENT COMMAND
==============================================================================
File: src/sega/commands/fleet.py
Project: SEGA (Scalable Engineering & Growth Automation)
Copyright: 2022-2025 FLEET
License: Apache-2.0

SEGA MODULE: Commands/Fleet
COMPONENT: Fleet Monorepo Operations CLI Command
PURPOSE: Manage the monorepo fleet with submodule operations and bulk deployment
DEPENDENCIES: click, pathlib, subprocess, yaml
USAGE: sega fleet [OPERATION] [PROJECTS...]

This command provides centralized management of the monorepo fleet including:
- Git submodule operations (pull, push, status)
- Bulk project deployment
- Engine systemd service management
- CI/CD pipeline orchestration
==============================================================================
"""

import click
from ...services.service import SegaService
from ...core.dependency_injection import inject


@click.group()
def fleet():
    """Manage your fleet — the set of projects SEGA operates.

    `sega fleet add` / `ls` / `remove` grow and inspect the fleet defined in
    config/sega.toml; the git/deploy subcommands operate across it.
    """
    pass


# ---------------------------------------------------------------------------
# Fleet composition: add / list / remove projects in config/sega.toml
# ---------------------------------------------------------------------------

def _locate_config():
    """Return the active sega.toml Path, or None if there is no fleet yet."""
    from ...core.config.loader import _find_config_file, ConfigurationError
    try:
        return _find_config_file()
    except ConfigurationError:
        return None


def _load_projects():
    """(config, {name: ProjectConfig}) or (None, {}) if no fleet exists."""
    from ...core.config.loader import load_config, ConfigurationError
    try:
        cfg = load_config()
        return cfg, cfg.projects
    except ConfigurationError:
        return None, {}


_STARTER_TOML = '''# SEGA fleet configuration.
# Add services with `sega fleet add <name>`, then boot with `sega local up`.

[meta]
version = "1.0.0"
description = "My fleet"

# Hosts your served projects deploy to (RFC 5737 example IP — replace with yours).
[instances.prod-01]
ip = "203.0.113.11"
ssh_user = "ubuntu"
ssh_key_path = "~/.ssh/id_rsa"
projects = ["web"]

# One block per service. `id` drives every port (api=8000+id, frontend=3000+id, ...).
[projects.web]
id = 0
engine_type = "none"
deployment_target = "local"
has_frontend = true

[domains]
web = { prod = "example.com" }
'''


@fleet.command(name="init")
@click.option("--force", is_flag=True, help="Overwrite an existing config/sega.toml.")
def init(force):
    """Scaffold a config/sega.toml for a new fleet (one starter service)."""
    from pathlib import Path
    target = Path.cwd() / "config" / "sega.toml"
    if target.exists() and not force:
        raise click.ClickException(f"{target} already exists. Use --force to overwrite, or `sega fleet add <name>` to grow it.")
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(_STARTER_TOML)
    click.echo(f"✓ Created {target} with a starter fleet (1 service: web)")
    click.echo("  Grow it:  sega fleet add <name>")
    click.echo("  See it:   sega fleet ls")
    click.echo("  Boot it:  sega local up")


@fleet.command(name="ls")
@click.option("--json", "as_json", is_flag=True, help="Output the fleet as JSON (for scripting / jq).")
def ls(as_json):
    """List the projects in your fleet, with their computed ports."""
    cfg, projects = _load_projects()
    if as_json:
        import json
        out = []
        for name, p in sorted(projects.items(), key=lambda kv: kv[1].id):
            out.append({
                "name": name, "id": p.id, "deployment_target": p.deployment_target,
                "domain": cfg.get_domain(name) if cfg else None,
                "ports": {"api": p.ports.api, "frontend": p.ports.frontend,
                          "database": p.ports.database, "redis": p.ports.redis, "metrics": p.ports.metrics},
            })
        click.echo(json.dumps(out, indent=2))
        return
    if not projects:
        click.echo("No fleet yet. Run `sega fleet init` to create one, then `sega fleet add <name>`.")
        return
    click.echo(f"Fleet: {len(projects)} project(s)")
    click.echo(f"  {'NAME':<20} {'ID':>3}  {'API':>5} {'FRONTEND':>8}  {'TARGET':<14} DOMAIN")
    for name, p in sorted(projects.items(), key=lambda kv: kv[1].id):
        domain = cfg.get_domain(name) or "-"
        click.echo(f"  {name:<20} {p.id:>3}  {p.ports.api:>5} {p.ports.frontend:>8}  {p.deployment_target:<14} {domain}")


@fleet.command()
@click.argument("name")
@click.option("--target", "-t", default="local", help="Deployment target: an instance name, or 'local'/'not_served'.")
@click.option("--domain", "-d", default=None, help="Production domain for this project (optional).")
@click.option("--no-frontend", is_flag=True, help="Project has no frontend.")
@click.option("--id", "explicit_id", type=int, default=None, help="Force a specific id (default: next free).")
def add(name, target, domain, no_frontend, explicit_id):
    """Add a project to your fleet.

    Allocates the next free id, computes its ports, and appends the project (and
    optional domain) to config/sega.toml. Example: `sega fleet add web -d web.example.com`.
    """
    name = name.strip().lower()
    cfg_path = _locate_config()
    if cfg_path is None:
        raise click.ClickException("No fleet config found. Run `sega fleet init` first, or copy config/sega.toml.example to config/sega.toml.")

    cfg, projects = _load_projects()
    if name in projects:
        raise click.ClickException(f"'{name}' is already in the fleet (id {projects[name].id}). Use `sega fleet remove {name}` first to change it.")

    used_ids = {p.id for p in projects.values()}
    if explicit_id is not None:
        if explicit_id in used_ids:
            raise click.ClickException(f"id {explicit_id} is already taken.")
        new_id = explicit_id
    else:
        new_id = 0
        while new_id in used_ids:
            new_id += 1

    block = [
        "",
        f"[projects.{name}]",
        f"id = {new_id}",
        'engine_type = "none"',
        f'deployment_target = "{target}"',
        f"has_frontend = {'false' if no_frontend else 'true'}",
        "has_mobile = false",
        "has_desktop = false",
        f'description = "{name}"',
    ]
    if domain:
        block += ["", f"[domains.{name}]", f'prod = "{domain}"']

    with open(cfg_path, "a") as f:
        f.write("\n".join(block) + "\n")

    # Ports are computed from the id (api=8000+id, frontend=3000+id, ...).
    from ...core.config.schema import PortConfig
    ports = PortConfig(new_id)
    click.echo(f"✓ Added '{name}' to the fleet (id {new_id}) in {cfg_path}")
    click.echo(f"    api {ports.api} · frontend {ports.frontend} · database {ports.database} · redis {ports.redis} · metrics {ports.metrics}")
    if domain:
        click.echo(f"    domain: {domain}")
    click.echo(f"  Boot it with: sega local up")


@fleet.command()
@click.argument("name")
@click.option("--yes", "-y", is_flag=True, help="Skip confirmation.")
def remove(name, yes):
    """Remove a project from your fleet (deletes its blocks from config/sega.toml)."""
    name = name.strip().lower()
    cfg_path = _locate_config()
    if cfg_path is None:
        raise click.ClickException("No fleet config found.")
    _, projects = _load_projects()
    if name not in projects:
        raise click.ClickException(f"'{name}' is not in the fleet. Run `sega fleet ls` to see it.")
    if not yes:
        click.confirm(f"Remove '{name}' from the fleet?", abort=True)

    lines = open(cfg_path).read().splitlines()
    out, i, removed = [], 0, 0
    targets = {f"[projects.{name}]", f"[domains.{name}]"}
    while i < len(lines):
        stripped = lines[i].strip()
        if stripped in targets:
            removed += 1
            i += 1
            # skip until the next table header or EOF
            while i < len(lines) and not lines[i].lstrip().startswith("["):
                i += 1
            # trim a single trailing blank line left behind
            if out and out[-1].strip() == "":
                out.pop()
            continue
        out.append(lines[i])
        i += 1
    with open(cfg_path, "w") as f:
        f.write("\n".join(out).rstrip("\n") + "\n")
    click.echo(f"✓ Removed '{name}' from the fleet ({removed} block(s)) in {cfg_path}")


@fleet.command()
@click.argument('projects', nargs=-1)
@inject(SegaService)
def pull(projects: tuple, fleet_service: SegaService = None):
    """Pull latest changes for all submodules or specific projects."""
    result = fleet_service.bulk_pull(list(projects) if projects else None)
    
    if result.success:
        click.echo(f"[OK] Pulled {len(result.updated_projects)} projects")
        for project in result.updated_projects:
            click.echo(f"  - {project}")
    else:
        click.echo(f"[ERROR] Pull operation failed: {result.error}")
        exit(1)


@fleet.command()
@click.argument('projects', nargs=-1)
@inject(SegaService)
def push(projects: tuple, fleet_service: SegaService = None):
    """Push changes for all submodules or specific projects."""
    result = fleet_service.bulk_push(list(projects) if projects else None)
    
    if result.success:
        click.echo(f"[OK] Pushed {len(result.pushed_projects)} projects")
        for project in result.pushed_projects:
            click.echo(f"  - {project}")
    else:
        click.echo(f"[ERROR] Push operation failed: {result.error}")
        exit(1)


@fleet.command()
@click.argument('projects', nargs=-1)
@inject(SegaService)
def status(projects: tuple, fleet_service: SegaService = None):
    """Show git status for all submodules or specific projects."""
    result = fleet_service.bulk_status(list(projects) if projects else None)
    
    click.echo("Fleet Monorepo Status:")
    click.echo("===================")
    
    for project, status_info in result.project_status.items():
        if status_info['clean']:
            click.echo(f"[OK] {project}: clean")
        else:
            click.echo(f"[WARNING] {project}: {status_info['changes']} changes")
            if status_info['behind']:
                click.echo(f"   [INFO] {status_info['behind']} commits behind")
            if status_info['ahead']:
                click.echo(f"   [INFO] {status_info['ahead']} commits ahead")


@fleet.command()
@click.argument('projects', nargs=-1)
@click.option('--environment', default='development', help='Target environment')
@inject(SegaService)
def deploy(projects: tuple, environment: str, fleet_service: SegaService = None):
    """Deploy fleet projects using multimodal strategy."""
    result = fleet_service.deploy_projects(
        list(projects) if projects else None,
        environment=environment
    )
    
    click.echo(f"[INFO] Deploying to {environment} environment:")
    click.echo("=========================================")
    
    for project, deploy_result in result.deployment_results.items():
        if deploy_result['success']:
            click.echo(f"[OK] {project}: deployed successfully")
            for component in deploy_result['components']:
                click.echo(f"   - {component}: {deploy_result['ports'][component]}")
        else:
            click.echo(f"[ERROR] {project}: deployment failed")
            click.echo(f"   Error: {deploy_result['error']}")


@fleet.command()
@click.argument('projects', nargs=-1)
@click.option('--action', type=click.Choice(['start', 'stop', 'restart', 'status']), default='status')
@inject(SegaService)
def engines(projects: tuple, action: str, fleet_service: SegaService = None):
    """Manage engine systemd services for projects."""
    result = fleet_service.manage_engines(
        list(projects) if projects else None,
        action=action
    )
    
    click.echo(f"[INFO] Engine Services ({action}):")
    click.echo("=========================")
    
    for project, engine_result in result.engine_results.items():
        if engine_result['success']:
            click.echo(f"[OK] {project}: {engine_result['status']}")
            if engine_result.get('ports'):
                click.echo(f"   Ports: {engine_result['ports']}")
        else:
            click.echo(f"[ERROR] {project}: {engine_result['error']}")


@fleet.command()
@click.argument('projects', nargs=-1)
@inject(SegaService)
def test(projects: tuple, fleet_service: SegaService = None):
    """Run tests across fleet projects."""
    result = fleet_service.run_tests(list(projects) if projects else None)
    
    click.echo("[INFO] Test Results:")
    click.echo("===============")
    
    for project, test_result in result.test_results.items():
        if test_result['success']:
            click.echo(f"[OK] {project}: {test_result['passed']}/{test_result['total']} tests passed")
        else:
            click.echo(f"[ERROR] {project}: tests failed")
            click.echo(f"   Error: {test_result['error']}")


@fleet.command()
@inject(SegaService)
def init_infrastructure(fleet_service: SegaService = None):
    """Initialize fleet deployment infrastructure."""
    result = fleet_service.init_infrastructure()
    
    if result.success:
        click.echo("[OK] Fleet infrastructure initialized")
        click.echo("  - Shared environments configured")
        click.echo("  - SystemD service templates created")
        click.echo("  - GitLab CI templates deployed")
    else:
        click.echo(f"[ERROR] Infrastructure initialization failed: {result.error}")
        exit(1)