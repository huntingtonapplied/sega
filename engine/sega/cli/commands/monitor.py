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
SEGA MONITOR COMMANDS
==============================================================================
File: src/sega/commands/monitor.py
Project: SEGA (Scalable Engineering & Growth Automation)
Copyright: 2022-2025 FLEET
License: Apache-2.0

SEGA MODULE: Commands/Monitor
COMPONENT: Deployment Monitoring Commands
PURPOSE: Monitor deployment status, logs, and metrics
DEPENDENCIES: click, boto3, kubernetes
USAGE: sega monitor [status|logs|metrics]

Commands provided:
- sega monitor status: Check deployment status across platforms
- sega monitor logs: View deployment logs from various sources
- sega monitor metrics: Show performance metrics and health data
==============================================================================
"""

import click
import yaml
import json
from pathlib import Path
from typing import Optional
from datetime import datetime, timedelta

from ...core.dependency_injection import inject
from ...services.deployment_service import DeploymentService
from ...system.monitoring.status_monitor import StatusMonitor
from ...system.monitoring.log_aggregator import LogAggregator


@click.group()
def monitor():
    """Monitor deployment status, logs, and performance metrics."""
    pass


@monitor.command()
@click.option(
    "--target", default="staging", help="Deployment target to monitor"
)
@click.option(
    "--project",
    help="Specific project to monitor (default: current directory)",
)
@click.option(
    "--format",
    "output_format",
    type=click.Choice(["table", "json", "yaml"]),
    default="table",
    help="Output format",
)
@click.option(
    "--watch", "-w", is_flag=True, help="Continuously monitor status"
)
@click.option("--interval", default=30, help="Watch interval in seconds")
@inject("deployment_service")
def status(
    target: str,
    project: Optional[str],
    output_format: str,
    watch: bool,
    interval: int,
    deployment_service: DeploymentService,
):
    """Check deployment status across platforms."""
    try:
        # Determine project
        if project:
            project_path = Path(project)
        else:
            project_path = Path(".")

        # Load project configuration if available
        sega_config = project_path / "sega.yaml"
        project_name = project or project_path.name

        if sega_config.exists():
            with open(sega_config, "r") as f:
                config_data = yaml.safe_load(f)
                project_name = config_data.get("name", project_name)

        def get_status():
            """Get current deployment status"""
            status_info = deployment_service.get_deployment_status(
                project_name, target
            )

            if not status_info:
                return {
                    "project": project_name,
                    "target": target,
                    "status": "Not Found",
                    "message": f"No deployment found for {project_name} in {target}",
                    "timestamp": datetime.utcnow().isoformat(),
                }

            return {
                "project": project_name,
                "target": target,
                "status": status_info.get("status", "Unknown"),
                "health": status_info.get("health", "Unknown"),
                "last_updated": status_info.get("last_updated", "Unknown"),
                "instances": status_info.get("instances", 0),
                "version": status_info.get("version", "Unknown"),
                "timestamp": datetime.utcnow().isoformat(),
            }

        def display_status(status_data):
            """Display status in requested format"""
            if output_format == "json":
                click.echo(json.dumps(status_data, indent=2))
            elif output_format == "yaml":
                click.echo(yaml.dump(status_data, default_flow_style=False))
            else:  # table format
                click.echo(f"Project: {status_data['project']}")
                click.echo(f"Target: {status_data['target']}")
                click.echo(f"Status: {status_data['status']}")
                click.echo(f"Health: {status_data.get('health', 'Unknown')}")
                click.echo(f"Instances: {status_data.get('instances', 0)}")
                click.echo(f"Version: {status_data.get('version', 'Unknown')}")
                click.echo(
                    f"Last Updated: {status_data.get('last_updated', 'Unknown')}"
                )
                click.echo(f"Check Time: {status_data['timestamp']}")

        if watch:
            import time

            click.echo(
                f"Monitoring {project_name} in {target} (every {interval}s, Ctrl+C to stop)"
            )
            try:
                while True:
                    click.clear()
                    status_data = get_status()
                    display_status(status_data)
                    time.sleep(interval)
            except KeyboardInterrupt:
                click.echo("\nMonitoring stopped.")
        else:
            status_data = get_status()
            display_status(status_data)

    except Exception as e:
        click.echo(f"Error monitoring status: {str(e)}", err=True)
        raise click.Abort()


@monitor.command()
@click.option("--target", default="staging", help="Deployment target")
@click.option(
    "--project", help="Specific project (default: current directory)"
)
@click.option(
    "--lines", "-n", default=100, help="Number of log lines to retrieve"
)
@click.option("--follow", "-f", is_flag=True, help="Follow log output")
@click.option(
    "--since",
    help='Show logs since timestamp (e.g., "1h", "30m", "2023-01-01T00:00:00")',
)
@click.option(
    "--level",
    type=click.Choice(["DEBUG", "INFO", "WARN", "ERROR"]),
    help="Filter by log level",
)
@inject("deployment_service")
def logs(
    target: str,
    project: Optional[str],
    lines: int,
    follow: bool,
    since: Optional[str],
    level: Optional[str],
    deployment_service: DeploymentService,
):
    """View deployment logs from various sources."""
    try:
        # Determine project
        if project:
            project_path = Path(project)
        else:
            project_path = Path(".")

        # Load project configuration if available
        sega_config = project_path / "sega.yaml"
        project_name = project or project_path.name

        if sega_config.exists():
            with open(sega_config, "r") as f:
                config_data = yaml.safe_load(f)
                project_name = config_data.get("name", project_name)

        # Parse since parameter
        since_datetime = None
        if since:
            try:
                if since.endswith("h"):
                    hours = int(since[:-1])
                    since_datetime = datetime.utcnow() - timedelta(hours=hours)
                elif since.endswith("m"):
                    minutes = int(since[:-1])
                    since_datetime = datetime.utcnow() - timedelta(
                        minutes=minutes
                    )
                elif since.endswith("d"):
                    days = int(since[:-1])
                    since_datetime = datetime.utcnow() - timedelta(days=days)
                else:
                    # Try parsing as ISO format
                    since_datetime = datetime.fromisoformat(
                        since.replace("Z", "+00:00")
                    )
            except (ValueError, TypeError):
                click.echo(f"Invalid since format: {since}", err=True)
                raise click.Abort()

        # Initialize log aggregator
        log_aggregator = LogAggregator()

        click.echo(f"Retrieving logs for {project_name} in {target}...")

        if follow:
            click.echo("Following logs (Ctrl+C to stop)...")
            try:
                # Stream logs continuously
                for log_entry in log_aggregator.stream_logs(
                    project_name, target, since=since_datetime, level=level
                ):
                    timestamp = log_entry.get(
                        "timestamp", datetime.utcnow().isoformat()
                    )
                    log_level = log_entry.get("level", "INFO")
                    message = log_entry.get("message", "")
                    source = log_entry.get("source", "unknown")

                    click.echo(
                        f"[{timestamp}] [{log_level}] [{source}] {message}"
                    )

            except KeyboardInterrupt:
                click.echo("\nStopped following logs.")
        else:
            # Get historical logs
            logs_data = log_aggregator.get_logs(
                project_name,
                target,
                lines=lines,
                since=since_datetime,
                level=level,
            )

            if not logs_data:
                click.echo(f"No logs found for {project_name} in {target}")
                return

            for log_entry in logs_data:
                timestamp = log_entry.get("timestamp", "Unknown")
                log_level = log_entry.get("level", "INFO")
                message = log_entry.get("message", "")
                source = log_entry.get("source", "unknown")

                click.echo(f"[{timestamp}] [{log_level}] [{source}] {message}")

    except Exception as e:
        click.echo(f"Error retrieving logs: {str(e)}", err=True)
        raise click.Abort()


@monitor.command()
@click.option("--target", default="staging", help="Deployment target")
@click.option(
    "--project", help="Specific project (default: current directory)"
)
@click.option(
    "--metric",
    type=click.Choice(
        ["cpu", "memory", "network", "disk", "requests", "errors"]
    ),
    help="Specific metric to show",
)
@click.option(
    "--period", default="1h", help='Time period (e.g., "1h", "24h", "7d")'
)
@click.option(
    "--format",
    "output_format",
    type=click.Choice(["table", "json", "graph"]),
    default="table",
    help="Output format",
)
@inject("deployment_service")
def metrics(
    target: str,
    project: Optional[str],
    metric: Optional[str],
    period: str,
    output_format: str,
    deployment_service: DeploymentService,
):
    """Show performance metrics and health data."""
    try:
        # Determine project
        if project:
            project_path = Path(project)
        else:
            project_path = Path(".")

        # Load project configuration if available
        sega_config = project_path / "sega.yaml"
        project_name = project or project_path.name

        if sega_config.exists():
            with open(sega_config, "r") as f:
                config_data = yaml.safe_load(f)
                project_name = config_data.get("name", project_name)

        # Parse period
        try:
            if period.endswith("h"):
                hours = int(period[:-1])
                period_timedelta = timedelta(hours=hours)
            elif period.endswith("d"):
                days = int(period[:-1])
                period_timedelta = timedelta(days=days)
            elif period.endswith("m"):
                minutes = int(period[:-1])
                period_timedelta = timedelta(minutes=minutes)
            else:
                raise ValueError("Invalid period format")
        except (ValueError, TypeError):
            click.echo(
                f"Invalid period format: {period}. Use format like '1h', '24h', '7d'",
                err=True,
            )
            raise click.Abort()

        # Initialize status monitor
        status_monitor = StatusMonitor()

        click.echo(
            f"Retrieving metrics for {project_name} in {target} (period: {period})"
        )

        # Get metrics data
        end_time = datetime.utcnow()
        start_time = end_time - period_timedelta

        metrics_data = status_monitor.get_metrics(
            project_name,
            target,
            start_time=start_time,
            end_time=end_time,
            metric_type=metric,
        )

        if not metrics_data:
            click.echo(f"No metrics found for {project_name} in {target}")
            return

        def display_metrics(data):
            """Display metrics in requested format"""
            if output_format == "json":
                click.echo(json.dumps(data, indent=2, default=str))
            elif output_format == "graph":
                # Simple ASCII graph representation
                click.echo(
                    "ASCII graphs not implemented yet. Use --format table or json."
                )
                display_table_metrics(data)
            else:  # table format
                display_table_metrics(data)

        def display_table_metrics(data):
            """Display metrics in table format"""
            for metric_name, metric_values in data.items():
                click.echo(f"\n{metric_name.upper()} Metrics:")
                click.echo("-" * 50)

                if isinstance(metric_values, dict):
                    if "current" in metric_values:
                        click.echo(f"Current: {metric_values['current']}")
                    if "average" in metric_values:
                        click.echo(f"Average: {metric_values['average']}")
                    if "max" in metric_values:
                        click.echo(f"Maximum: {metric_values['max']}")
                    if "min" in metric_values:
                        click.echo(f"Minimum: {metric_values['min']}")
                else:
                    click.echo(f"Value: {metric_values}")

        display_metrics(metrics_data)

    except Exception as e:
        click.echo(f"Error retrieving metrics: {str(e)}", err=True)
        raise click.Abort()


if __name__ == "__main__":
    monitor()
