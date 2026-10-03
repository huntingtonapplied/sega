#!/usr/bin/env python3
# Copyright 2025 SEGA

"""
SEGA SERVICES COMMAND - Instance systemd Service Management
==============================================================================
File: engine/sega/cli/commands/services.py
Project: SEGA (Scalable Engineering & Growth Automation)
Copyright: 2022-2025 FLEET
License: Apache-2.0
SEGA MODULE: Commands/Services
COMPONENT: EC2 Instance systemd Service Orchestration CLI
PURPOSE: Install, control, and monitor systemd units for all frontends
         and backends running on a given EC2 instance.

Core Principle: Actions are commands, platforms are options.

Usage:
    sega services install --instance 1                    # install + start all
    sega services install --instance 1 --project hermes    # one project only
    sega services install --instance 1 --type frontend    # frontends only
    sega services install --instance 1 --no-start         # write units, don't start

    sega services status  --instance 1
    sega services status  --instance 1 --project atlas

    sega services restart --instance 1
    sega services restart --instance 1 --project orion --type backend

    sega services start   --instance 1
    sega services stop    --instance 1 --project atlas
    sega services enable  --instance 1
    sega services disable --instance 1 --project hermes

    sega services list    --instance 1                    # show all unit names
==============================================================================
"""

import click
import json
from typing import Optional

from ...services.instance_service_manager import InstanceServiceManager
from ...services.deployment_state import scan_instance_state, load_deployment_config
from ...services.conflict_detector import detect_conflicts, get_conflicts_by_severity, get_conflicts_by_project


# ─── helpers ──────────────────────────────────────────────────────────────────


def _make_manager(instance: str) -> InstanceServiceManager:
    try:
        return InstanceServiceManager(instance_id=instance)
    except ValueError as exc:
        raise click.UsageError(str(exc))


def _print_report(report, verb: str) -> None:
    """Print install/control report to stdout."""
    click.echo(f"\n[{report.instance_id}] {verb} — {report.success_count} ok, {report.failure_count} failed")
    click.echo("─" * 60)
    for r in report.results:
        icon = "[OK]" if r.success else "[FAIL]"
        click.echo(f"  {icon}  {r.unit_name}  ({r.message})")
        if r.error:
            click.echo(f"         {r.error.strip()}")


def _type_choice(value: Optional[str]) -> Optional[str]:
    """Normalise --type flag to 'frontend' | 'backend' | None."""
    if value in (None, "all"):
        return None
    return value


# ─── group ────────────────────────────────────────────────────────────────────


@click.group()
def services():
    """Manage systemd services for FLEET frontends and backends on EC2 instances.

    \b
    Examples:
        sega services install --instance 1
        sega services status  --instance 1
        sega services restart --instance 1 --project atlas
    """
    pass


# ─── shared options ───────────────────────────────────────────────────────────

_instance_opt = click.option(
    "--instance",
    "-i",
    required=True,
    help="Instance ID or name (e.g. 1, instance1, fleet-prod-01)",
)
_project_opt = click.option(
    "--project",
    "-p",
    default=None,
    help="Limit to a single project (e.g. atlas, hermes)",
)
_type_opt = click.option(
    "--type",
    "-t",
    "service_type",
    type=click.Choice(["frontend", "backend", "all"]),
    default="all",
    help="Limit to frontends, backends, or all (default: all)",
)


# ─── install ──────────────────────────────────────────────────────────────────


@services.command()
@_instance_opt
@_project_opt
@_type_opt
@click.option("--start/--no-start", default=True, help="Start services after installing (default: yes)")
def install(instance: str, project: Optional[str], service_type: str, start: bool):
    """Write systemd unit files, enable, and optionally start services.

    Connects to the instance over SSH, writes unit files to
    /etc/systemd/system/, runs daemon-reload, enables, and starts.

    \b
    Examples:
        sega services install --instance 1
        sega services install --instance 1 --project hermes --no-start
        sega services install --instance 1 --type backend
    """
    mgr = _make_manager(instance)
    click.echo(f"Installing services on instance {instance}...")
    report = mgr.install(
        project=project,
        service_type=_type_choice(service_type),
        start=start,
    )
    _print_report(report, "install")
    if report.failure_count:
        raise SystemExit(1)


# ─── status ───────────────────────────────────────────────────────────────────


@services.command()
@_instance_opt
@_project_opt
@_type_opt
def status(instance: str, project: Optional[str], service_type: str):
    """Show active/inactive/failed state for each service unit.

    \b
    Examples:
        sega services status --instance 1
        sega services status --instance 1 --project orion
    """
    mgr = _make_manager(instance)
    rows = mgr.status(project=project, service_type=_type_choice(service_type))

    if not rows:
        click.echo("No matching services found.")
        return

    click.echo(f"\n[{instance}] Service Status")
    click.echo("─" * 60)
    col = 50
    for unit, state in rows:
        color = "green" if state == "active" else ("red" if state in ("failed", "inactive") else "yellow")
        state_str = click.style(state, fg=color)
        click.echo(f"  {unit:<{col}}  {state_str}")


# ─── restart ──────────────────────────────────────────────────────────────────


@services.command()
@_instance_opt
@_project_opt
@_type_opt
def restart(instance: str, project: Optional[str], service_type: str):
    """Restart matching service units.

    \b
    Examples:
        sega services restart --instance 1
        sega services restart --instance 1 --project atlas --type frontend
    """
    mgr = _make_manager(instance)
    click.echo(f"Restarting services on instance {instance}...")
    report = mgr.control("restart", project=project, service_type=_type_choice(service_type))
    _print_report(report, "restart")
    if report.failure_count:
        raise SystemExit(1)


# ─── start ────────────────────────────────────────────────────────────────────


@services.command()
@_instance_opt
@_project_opt
@_type_opt
def start(instance: str, project: Optional[str], service_type: str):
    """Start matching service units."""
    mgr = _make_manager(instance)
    click.echo(f"Starting services on instance {instance}...")
    report = mgr.control("start", project=project, service_type=_type_choice(service_type))
    _print_report(report, "start")
    if report.failure_count:
        raise SystemExit(1)


# ─── stop ─────────────────────────────────────────────────────────────────────


@services.command()
@_instance_opt
@_project_opt
@_type_opt
def stop(instance: str, project: Optional[str], service_type: str):
    """Stop matching service units."""
    mgr = _make_manager(instance)
    click.echo(f"Stopping services on instance {instance}...")
    report = mgr.control("stop", project=project, service_type=_type_choice(service_type))
    _print_report(report, "stop")
    if report.failure_count:
        raise SystemExit(1)


# ─── enable ───────────────────────────────────────────────────────────────────


@services.command()
@_instance_opt
@_project_opt
@_type_opt
def enable(instance: str, project: Optional[str], service_type: str):
    """Enable (auto-start on boot) matching service units."""
    mgr = _make_manager(instance)
    report = mgr.control("enable", project=project, service_type=_type_choice(service_type))
    _print_report(report, "enable")
    if report.failure_count:
        raise SystemExit(1)


# ─── disable ──────────────────────────────────────────────────────────────────


@services.command()
@_instance_opt
@_project_opt
@_type_opt
def disable(instance: str, project: Optional[str], service_type: str):
    """Disable (no auto-start on boot) matching service units."""
    mgr = _make_manager(instance)
    report = mgr.control("disable", project=project, service_type=_type_choice(service_type))
    _print_report(report, "disable")
    if report.failure_count:
        raise SystemExit(1)


# ─── list ─────────────────────────────────────────────────────────────────────


@services.command(name="list")
@_instance_opt
@_project_opt
@_type_opt
def list_services(instance: str, project: Optional[str], service_type: str):
    """List all unit names that would be managed (no SSH required).

    \b
    Examples:
        sega services list --instance 1
        sega services list --instance 1 --type backend
    """
    mgr = _make_manager(instance)
    defs = mgr._filter(project, _type_choice(service_type))

    if not defs:
        click.echo("No matching service definitions.")
        return

    click.echo(f"\n[{instance}] Managed Units ({len(defs)} total)")
    click.echo("─" * 60)
    for d in defs:
        click.echo(f"  {d.unit_name:<50}  port={d.port}  type={d.service_type}")


# ─── state ────────────────────────────────────────────────────────────────────


@services.command()
@_instance_opt
@click.option("--project", "-p", help="Filter by project")
@click.option("--format", type=click.Choice(["text", "json"]), default="text", help="Output format")
def state(instance: str, project: Optional[str], format: str):
    """Show complete deployment state for an instance.

    Scans Docker containers, systemd services, and native processes.
    Detects conflicts and provides deployment health overview.

    \b
    Examples:
        sega services state --instance 1
        sega services state --instance 1 --project atlas
        sega services state --instance 1 --format json
    """
    try:
        # Scan instance state
        click.echo(f"Scanning instance {instance}...", err=True)
        state_data = scan_instance_state(instance)

        # Load expected configuration
        expected_config = load_deployment_config()

        # Detect conflicts
        conflicts = detect_conflicts(state_data, expected_config)

        # Filter by project if specified
        if project:
            state_data.services = [s for s in state_data.services if s.project == project]
            conflicts = [c for c in conflicts if c.project == project]

        # Output based on format
        if format == "json":
            _print_state_json(state_data, conflicts)
        else:
            _print_state_text(state_data, conflicts)

    except Exception as e:
        click.echo(f"Error scanning instance: {e}", err=True)
        raise SystemExit(1)


def _print_state_json(state_data, conflicts):
    """Print state as JSON"""
    output = state_data.to_dict()
    output["conflicts_detailed"] = [c.to_dict() for c in conflicts]
    click.echo(json.dumps(output, indent=2))


def _print_state_text(state_data, conflicts):
    """Print state in human-readable text format"""
    click.echo()
    click.echo("=" * 80)
    click.echo(f"INSTANCE: {state_data.instance_name} ({state_data.ip})")
    click.echo(f"Scanned: {state_data.timestamp}")
    click.echo("=" * 80)

    # Group services by project
    services_by_project = {}
    for service in state_data.services:
        if service.project not in services_by_project:
            services_by_project[service.project] = []
        services_by_project[service.project].append(service)

    # Get conflicts by project
    conflicts_by_project = get_conflicts_by_project(conflicts)
    conflicts_by_severity = get_conflicts_by_severity(conflicts)

    # Classify projects
    aligned_projects = []
    conflicted_projects = []

    for project_name, services in services_by_project.items():
        if project_name in conflicts_by_project:
            conflicted_projects.append((project_name, services))
        else:
            aligned_projects.append((project_name, services))

    # Print aligned deployments
    if aligned_projects:
        click.echo()
        click.echo(f"✅ ALIGNED DEPLOYMENTS ({len(aligned_projects)}):")
        click.echo()

        for project_name, services in sorted(aligned_projects):
            # Get deployment mode if available
            mode = _get_project_mode(project_name, state_data)
            mode_str = f" [{mode}]" if mode else ""

            click.echo(f"  {project_name}{mode_str}:")

            # Group by service type
            by_type = {}
            for s in services:
                if s.service_type not in by_type:
                    by_type[s.service_type] = []
                by_type[s.service_type].append(s)

            for service_type in sorted(by_type.keys()):
                type_services = by_type[service_type]
                status_icon = "✓" if all(s.status == "running" for s in type_services) else "⚠"

                if len(type_services) == 1:
                    s = type_services[0]
                    port_str = f" on port {s.port}" if s.port else ""
                    click.echo(f"    {status_icon} {service_type}: {s.method} ({s.service_name}){port_str}")
                else:
                    containers = ", ".join(s.service_name for s in type_services)
                    click.echo(
                        f"    {status_icon} {service_type}: {type_services[0].method} ({len(type_services)} services)"
                    )

            click.echo()

    # Print conflicted deployments
    if conflicted_projects:
        click.echo(f"⚠️  CONFLICTS DETECTED ({len(conflicted_projects)} projects):")
        click.echo()

        for project_name, services in sorted(conflicted_projects):
            project_conflicts = conflicts_by_project.get(project_name, [])

            mode = _get_project_mode(project_name, state_data)
            mode_str = f" [{mode}]" if mode else ""

            click.echo(f"  {project_name}{mode_str}:")

            # Show services
            by_type = {}
            for s in services:
                if s.service_type not in by_type:
                    by_type[s.service_type] = []
                by_type[s.service_type].append(s)

            for service_type in sorted(by_type.keys()):
                type_services = by_type[service_type]

                # Check if this service type has conflicts
                has_conflict = any(
                    service_type in c.description.lower()
                    or any(svc in c.affected_services for svc in [s.service_name for s in type_services])
                    for c in project_conflicts
                )

                if len(type_services) == 1:
                    s = type_services[0]
                    status_icon = "✓" if s.status == "running" else "❌"
                    port_str = f" on port {s.port}" if s.port else ""
                    click.echo(
                        f"    {status_icon} {service_type}: {s.method} ({s.service_name}){port_str} - {s.status}"
                    )
                else:
                    healthy_count = sum(1 for s in type_services if s.status == "running")
                    status_icon = "✓" if healthy_count == len(type_services) else "❌"
                    click.echo(
                        f"    {status_icon} {service_type}: {type_services[0].method} ({healthy_count}/{len(type_services)} healthy)"
                    )

            # Show conflicts for this project
            click.echo()
            for conflict in project_conflicts:
                severity_icon = "❌" if conflict.severity == "ERROR" else "⚠️"
                click.echo(f"    {severity_icon} {conflict.description}")
                if conflict.fix_description:
                    click.echo(f"       Fix: {conflict.fix_description}")

            click.echo()

    # Print orphaned services
    if state_data.orphans:
        click.echo(f"🔶 ORPHANED SERVICES ({len(state_data.orphans)}):")
        for orphan in state_data.orphans:
            click.echo(f"  {orphan}")
        click.echo()

    # Print summary
    click.echo("─" * 80)
    click.echo("SUMMARY:")
    click.echo(f"  Total projects: {len(services_by_project)}")
    click.echo(f"  Services running: {len([s for s in state_data.services if s.status == 'running'])}")
    click.echo(f"  Healthy: {len(aligned_projects)}")
    click.echo(f"  With conflicts: {len(conflicted_projects)}")
    click.echo(f"  Errors: {len(conflicts_by_severity.get('ERROR', []))}")
    click.echo(f"  Warnings: {len(conflicts_by_severity.get('WARNING', []))}")
    click.echo("=" * 80)
    click.echo()


def _get_project_mode(project_name: str, state_data) -> Optional[str]:
    """Try to determine deployment mode for a project"""
    # Simple heuristic based on observed services
    services = [s for s in state_data.services if s.project == project_name]

    if not services:
        return None

    methods = {s.method for s in services}

    if methods == {"docker"}:
        return "docker_isolated"
    elif "native" in methods:
        return "native_dev"
    elif methods == {"docker", "systemd"}:
        return "hybrid"
    else:
        return "mixed"
