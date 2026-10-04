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
SEGA PROJECT LEDGER CLI COMMANDS
==============================================================================
File: src/sega/commands/ledger.py
Project: SEGA (Scalable Engineering & Growth Automation)
Copyright: 2022-2025 SEGA Contributors
License: Apache-2.0

SEGA MODULE: Commands/ProjectLedger
COMPONENT: Project Reservation Management CLI
PURPOSE: Manage project reservations for concurrent testing
DEPENDENCIES: click, ProjectLedger, tabulate
USAGE: sega ledger [status|release|history|cleanup]

This command group provides management and monitoring of the project
reservation ledger used for concurrent agent testing coordination.
==============================================================================
"""

import click
from tabulate import tabulate
from ...core.project_ledger import ProjectLedger


@click.group()
def ledger():
    """Manage project reservation ledger for concurrent testing.

    The ledger ensures only one agent can test a specific project at a time,
    preventing port conflicts and resource contention during parallel testing.
    """
    pass


@ledger.command()
@click.option('--format', type=click.Choice(['table', 'json', 'simple']), default='table')
def status(format):
    """Show current project reservations.

    Examples:
        sega ledger status              # Show all active reservations
        sega ledger status --format json # JSON output
    """
    ledger_manager = ProjectLedger()
    reservations = ledger_manager.list_active_reservations()

    if not reservations:
        click.echo("[INFO] No active project reservations")
        return

    if format == 'json':
        import json
        click.echo(json.dumps(reservations, indent=2))
        return

    if format == 'simple':
        for project, res in reservations.items():
            click.echo(f"{project}: {res['agent_id']} (since {res['reserved_at'][:19]})")
        return

    # Table format
    data = []
    for project, res in sorted(reservations.items()):
        data.append([
            project,
            res['agent_id'],
            res['reserved_at'][:19],
            res['expires_at'][:19],
            res['status'],
            res['pid'],
            ', '.join(map(str, res.get('ports_used', []))) or 'N/A'
        ])

    headers = ['Project', 'Agent ID', 'Reserved At', 'Expires At', 'Status', 'PID', 'Ports']
    click.echo("\n[INFO] Active Project Reservations:")
    click.echo(tabulate(data, headers=headers, tablefmt='grid'))
    click.echo(f"\nTotal: {len(reservations)} active reservations")


@ledger.command()
@click.argument('project')
@click.option('--force', is_flag=True, help='Force release without agent verification')
def release(project, force):
    """Release a project reservation.

    Examples:
        sega ledger release orion         # Release orion
        sega ledger release orion --force # Force release (admin override)
    """
    ledger_manager = ProjectLedger()

    if force:
        # Admin override - force release
        if ledger_manager.force_release(project):
            click.echo(f"[OK] Force released reservation for: {project}")
        else:
            click.echo(f"[ERROR] Project not reserved: {project}")
    else:
        click.echo("[ERROR] Normal release requires agent ID")
        click.echo("Use --force to override, or release from the agent that acquired it")


@ledger.command()
@click.option('--project', '-p', help='Filter by project name')
@click.option('--limit', '-n', default=20, help='Number of entries to show')
@click.option('--format', type=click.Choice(['table', 'json', 'simple']), default='table')
def history(project, limit, format):
    """Show reservation history.

    Examples:
        sega ledger history                # Show last 20 entries
        sega ledger history -p orion    # Show orion history
        sega ledger history -n 50          # Show last 50 entries
    """
    ledger_manager = ProjectLedger()
    entries = ledger_manager.get_history(project_name=project, limit=limit)

    if not entries:
        click.echo(f"[INFO] No history entries{' for ' + project if project else ''}")
        return

    if format == 'json':
        import json
        click.echo(json.dumps(entries, indent=2))
        return

    if format == 'simple':
        for entry in entries:
            status_icon = "✓" if entry['status'] == 'completed' else "✗"
            click.echo(f"{status_icon} {entry['project_name']}: {entry['agent_id']} "
                      f"({entry['reserved_at'][:19]} → {entry.get('released_at', 'N/A')[:19]})")
        return

    # Table format
    data = []
    for entry in entries:
        duration = 'N/A'
        if 'released_at' in entry:
            from datetime import datetime
            reserved = datetime.fromisoformat(entry['reserved_at'])
            released = datetime.fromisoformat(entry['released_at'])
            delta = released - reserved
            duration = f"{delta.total_seconds():.0f}s"

        data.append([
            entry['project_name'],
            entry['agent_id'],
            entry['reserved_at'][:19],
            entry.get('released_at', 'N/A')[:19],
            entry['status'],
            duration
        ])

    headers = ['Project', 'Agent ID', 'Reserved At', 'Released At', 'Status', 'Duration']
    click.echo(f"\n[INFO] Reservation History{' for ' + project if project else ''}:")
    click.echo(tabulate(data, headers=headers, tablefmt='grid'))
    click.echo(f"\nShowing {len(entries)} entries (use -n to adjust)")


@ledger.command()
@click.option('--dry-run', is_flag=True, help='Show what would be cleaned up')
def cleanup(dry_run):
    """Clean up expired reservations.

    Examples:
        sega ledger cleanup              # Remove expired reservations
        sega ledger cleanup --dry-run    # Preview without removing
    """
    ledger_manager = ProjectLedger()

    if dry_run:
        reservations = ledger_manager.list_active_reservations()
        from datetime import datetime

        expired = []
        for project, res in reservations.items():
            expires_at = datetime.fromisoformat(res['expires_at'])
            if datetime.now() > expires_at:
                expired.append(project)

        if expired:
            click.echo(f"[INFO] Would clean up {len(expired)} expired reservations:")
            for project in expired:
                click.echo(f"  - {project}")
        else:
            click.echo("[INFO] No expired reservations to clean up")
    else:
        count = ledger_manager.cleanup_all()
        if count > 0:
            click.echo(f"[OK] Cleaned up {count} expired reservations")
        else:
            click.echo("[INFO] No expired reservations found")


@ledger.command()
@click.argument('project')
def check(project):
    """Check if a project is available for reservation.

    Examples:
        sega ledger check orion    # Check if orion is available
    """
    ledger_manager = ProjectLedger()

    if ledger_manager.is_available(project):
        click.echo(f"[OK] {project} is available for reservation")
    else:
        reservation = ledger_manager.get_reservation(project)
        if reservation:
            click.echo(f"[BUSY] {project} is reserved by {reservation['agent_id']}")
            click.echo(f"       Reserved at: {reservation['reserved_at'][:19]}")
            click.echo(f"       Expires at:  {reservation['expires_at'][:19]}")
        else:
            click.echo(f"[ERROR] Unable to check status for {project}")
