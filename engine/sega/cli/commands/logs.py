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
SEGA LOG AGGREGATION COMMAND
==============================================================================
File: src/sega/commands/logs.py
Project: SEGA (Scalable Engineering & Growth Automation)
Copyright: 2022-2025 FLEET
License: Apache-2.0

SEGA MODULE: Commands/LogAggregation
COMPONENT: Multi-Infrastructure Log CLI Command
PURPOSE: Aggregate and stream logs from all deployment targets
DEPENDENCIES: click, LogAggregator
USAGE: sega logs [--target ENV] [--follow] [--lines N] [--service NAME]

This command provides unified log aggregation across Kubernetes, Ansible nodes,
and FPGA deployments with real-time streaming capabilities.
==============================================================================
"""

import click
from ...system.monitoring.log_aggregator import LogAggregator


@click.command()
@click.option("--target", help="Filter by target environment")
@click.option("--follow", "-f", is_flag=True, help="Stream logs in real-time")
@click.option(
    "--lines", "-n", default=100, help="Number of recent lines to show"
)
@click.option("--service", help="Filter by specific service name")
def logs(target: str, follow: bool, lines: int, service: str):
    """View aggregated logs from all deployment targets."""

    aggregator = LogAggregator()

    if follow:
        click.echo("Streaming logs... (Ctrl+C to stop)")
        try:
            for log_entry in aggregator.stream_logs(
                target_filter=target, service_filter=service
            ):
                click.echo(
                    f"[{log_entry.timestamp}] {log_entry.source}: {log_entry.message}"
                )
        except KeyboardInterrupt:
            click.echo("\nLog streaming stopped")
    else:
        logs = aggregator.get_recent_logs(
            target_filter=target, service_filter=service, limit=lines
        )

        for log_entry in logs:
            click.echo(
                f"[{log_entry.timestamp}] {log_entry.source}: {log_entry.message}"
            )
