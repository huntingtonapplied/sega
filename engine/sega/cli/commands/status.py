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
SEGA DEPLOYMENT STATUS MONITORING COMMAND
==============================================================================
File: src/sega/commands/status.py
Project: SEGA (Scalable Engineering & Growth Automation)
Copyright: 2022-2025 FLEET
License: Apache-2.0

SEGA MODULE: Commands/StatusMonitoring
COMPONENT: Deployment Status CLI Command
PURPOSE: Monitor and display deployment status across all environments
DEPENDENCIES: click, StatusMonitor
USAGE: sega status [--target ENV] [--watch] [--interval SECONDS]

This command provides real-time monitoring of deployment health and status
across Kubernetes, Ansible, and FPGA infrastructure targets.
==============================================================================
"""

import click
import time
from ...system.monitoring.status_monitor import StatusMonitor


@click.command()
@click.option("--target", help="Filter by target environment")
@click.option(
    "--watch", "-w", is_flag=True, help="Continuously monitor status"
)
@click.option("--interval", default=5, help="Watch interval in seconds")
def status(target: str, watch: bool, interval: int):
    """Check deployment status across all environments."""

    monitor = StatusMonitor()

    def show_status():
        deployments = monitor.get_deployments(target_filter=target)

        if not deployments:
            click.echo("No active deployments found")
            return

        click.echo("Active Deployments:")
        click.echo("=" * 60)

        for deployment in deployments:
            status_icon = "" if deployment.healthy else ""
            click.echo(
                f"{status_icon} {deployment.name} [{deployment.target}]"
            )
            click.echo(f"   Type: {deployment.project_type}")
            click.echo(f"   Status: {deployment.status}")
            click.echo(f"   Health: {deployment.health_summary}")
            click.echo()

    if watch:
        try:
            while True:
                click.clear()
                show_status()
                click.echo(f"Refreshing every {interval}s... (Ctrl+C to stop)")
                time.sleep(interval)
        except KeyboardInterrupt:
            click.echo("\nMonitoring stopped")
    else:
        show_status()
