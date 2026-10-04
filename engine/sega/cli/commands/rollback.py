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
SEGA DEPLOYMENT ROLLBACK COMMAND
==============================================================================
File: src/sega/commands/rollback.py
Project: SEGA (Scalable Engineering & Growth Automation)
Copyright: 2022-2025 FLEET
License: Apache-2.0

SEGA MODULE: Commands/DeploymentRollback
COMPONENT: Safe Deployment Reversion CLI Command
PURPOSE: Safely rollback deployments to previous versions with audit trail
DEPENDENCIES: click, subprocess, json, StatusMonitor
USAGE: sega rollback --target ENV [--to-version VER] [--reason TEXT] [--dry-run]

This command provides safe deployment rollbacks with version control,
audit trails, and confirmation workflows across all infrastructure types.
==============================================================================
"""

import click
import subprocess
import json
from datetime import datetime
from ...system.monitoring.status_monitor import StatusMonitor


@click.command()
@click.option("--target", required=True, help="Target environment to rollback")
@click.option("--to-version", help="Specific version to rollback to")
@click.option("--reason", help="Reason for rollback (for audit trail)")
@click.option(
    "--dry-run", is_flag=True, help="Preview rollback without executing"
)
@click.option(
    "--force", is_flag=True, help="Force rollback without confirmations"
)
def rollback(
    target: str, to_version: str, reason: str, dry_run: bool, force: bool
):
    """Rollback deployment to previous version."""

    click.echo(f" Rolling back {target} deployment")

    if reason:
        click.echo(f"Reason: {reason}")

    # Get current deployment status
    monitor = StatusMonitor()
    deployments = monitor.get_deployments(target_filter=target)

    if not deployments:
        click.echo(f" No deployments found for target: {target}")
        return

    deployment = deployments[0]
    click.echo(f"Current deployment: {deployment.name} ({deployment.status})")

    # Determine rollback strategy based on deployment type
    if deployment.project_type == "kubernetes":
        success = _rollback_kubernetes(target, to_version, dry_run, force)
    elif deployment.project_type == "ansible":
        success = _rollback_ansible(target, to_version, dry_run, force)
    elif deployment.project_type == "fpga":
        success = _rollback_fpga(target, to_version, dry_run, force)
    else:
        click.echo(f" Rollback not supported for {deployment.project_type}")
        return

    if success:
        click.echo(" Rollback completed successfully")

        # Log rollback event
        _log_rollback_event(target, to_version, reason)
    else:
        click.echo(" Rollback failed")
        exit(1)


def _rollback_kubernetes(
    target: str, to_version: str, dry_run: bool, force: bool
) -> bool:
    """Rollback Kubernetes deployment using Helm."""
    try:
        # Get rollback history
        history_cmd = [
            "helm",
            "history",
            f"sega-{target}",
            "--namespace",
            "sega-deployments",
            "--output",
            "json",
        ]

        result = subprocess.run(
            history_cmd, capture_output=True, text=True, timeout=30
        )
        if result.returncode != 0:
            click.echo(f" Failed to get deployment history: {result.stderr}")
            return False

        history = json.loads(result.stdout)

        if not history:
            click.echo(" No deployment history found")
            return False

        # Determine target revision
        if to_version:
            # Find specific version in history
            target_revision = None
            for entry in history:
                if entry.get("app_version") == to_version:
                    target_revision = entry["revision"]
                    break

            if not target_revision:
                click.echo(
                    f" Version {to_version} not found in deployment history"
                )
                return False
        else:
            # Rollback to previous revision
            if len(history) < 2:
                click.echo(" No previous version to rollback to")
                return False

            # Get second-to-last revision (current is last)
            target_revision = history[-2]["revision"]
            to_version = history[-2].get("app_version", "unknown")

        click.echo(
            f"Rolling back to revision {target_revision} (version: {to_version})"
        )

        if not force and not dry_run:
            if not click.confirm("Continue with rollback?"):
                click.echo("Rollback cancelled")
                return False

        if dry_run:
            click.echo("DRY RUN - Would execute:")
            click.echo(
                f"  helm rollback sega-{target} {target_revision} --namespace sega-deployments"
            )
            return True

        # Execute rollback
        rollback_cmd = [
            "helm",
            "rollback",
            f"sega-{target}",
            str(target_revision),
            "--namespace",
            "sega-deployments",
        ]

        result = subprocess.run(
            rollback_cmd, capture_output=True, text=True, timeout=300
        )

        if result.returncode == 0:
            click.echo("Helm rollback completed")
            return True
        else:
            click.echo(f" Helm rollback failed: {result.stderr}")
            return False

    except Exception as e:
        click.echo(f" Rollback error: {str(e)}")
        return False


def _rollback_ansible(
    target: str, to_version: str, dry_run: bool, force: bool
) -> bool:
    """Rollback Ansible deployment."""
    try:
        click.echo(" Ansible rollback...")

        if dry_run:
            click.echo("DRY RUN - Would execute Ansible rollback playbook")
            return True

        # Run ansible rollback playbook
        ansible_cmd = [
            "ansible-playbook",
            "-i",
            "./_internal/tooling/_internal/tooling/infrastructure/ansible/host.ini",
            "./_internal/tooling/_internal/tooling/infrastructure/ansible/rollback-playbook.yml",
            "--limit",
            target,
            "--extra-vars",
            f"target_version={to_version or 'previous'}",
        ]

        if force:
            ansible_cmd.extend(["--extra-vars", "force_rollback=true"])

        result = subprocess.run(
            ansible_cmd, capture_output=True, text=True, timeout=600
        )

        if result.returncode == 0:
            click.echo("Ansible rollback completed")
            return True
        else:
            click.echo(f" Ansible rollback failed: {result.stderr}")
            return False

    except Exception as e:
        click.echo(f" Ansible rollback error: {str(e)}")
        return False


def _rollback_fpga(
    target: str, to_version: str, dry_run: bool, force: bool
) -> bool:
    """Rollback FPGA programming."""
    try:
        click.echo(" FPGA rollback...")

        if not to_version:
            click.echo(
                " FPGA rollback requires specific version (--to-version)"
            )
            return False

        bitstream_path = f"./backups/{target}-{to_version}.bit"

        if dry_run:
            click.echo(f"DRY RUN - Would program FPGA with {bitstream_path}")
            return True

        # Program FPGA with backup bitstream
        program_cmd = ["openFPGALoader", "-b", target, "-f", bitstream_path]

        result = subprocess.run(
            program_cmd, capture_output=True, text=True, timeout=120
        )

        if result.returncode == 0:
            click.echo("FPGA rollback completed")
            return True
        else:
            click.echo(f" FPGA rollback failed: {result.stderr}")
            return False

    except Exception as e:
        click.echo(f" FPGA rollback error: {str(e)}")
        return False


def _sanitize_log_data(data: str) -> str:
    """Sanitize sensitive data from log entries."""
    import re

    # Patterns for sensitive data
    sensitive_patterns = [
        # AWS keys
        (r"AKIA[0-9A-Z]{16}", "[AWS_ACCESS_KEY_REDACTED]"),
        (r"[A-Za-z0-9/+=]{40}", "[AWS_SECRET_KEY_REDACTED]"),
        # Generic secrets
        (
            r"(?i)(password|secret|key|token)[\s]*[=:]\s*[^\s]+",
            r"\1=[REDACTED]",
        ),
        # API keys
        (r"[a-zA-Z0-9]{32,}", "[API_KEY_REDACTED]"),
        # Database URLs with credentials
        (r"://[^:]+:[^@]+@", "://[USER]:[PASS]@"),
    ]

    sanitized = data
    for pattern, replacement in sensitive_patterns:
        sanitized = re.sub(pattern, replacement, sanitized)

    return sanitized


def _log_rollback_event(target: str, version: str, reason: str):
    """Log rollback event for audit trail with sensitive data sanitization."""
    try:
        # Sanitize sensitive data
        sanitized_reason = _sanitize_log_data(reason or "Not specified")
        sanitized_target = _sanitize_log_data(target)

        log_entry = {
            "timestamp": datetime.now().isoformat(),
            "event": "rollback",
            "target": sanitized_target,
            "version": version,
            "reason": sanitized_reason,
            "user": "sega-cli",  # Could get from environment
        }

        # Append to audit log
        with open("sega-audit.log", "a") as f:
            f.write(json.dumps(log_entry) + "\n")

    except Exception:
        # Don't fail rollback if logging fails
        pass


def rollback_project(
    project_path: str,
    target: str,
    to_version: str = None,
    reason: str = None,
    dry_run: bool = False,
) -> dict:
    """Rollback a single project programmatically (for workspace usage)."""
    try:
        # Detect project type from the specified path
        from ...project.project_detector import ProjectDetector

        detector = ProjectDetector(project_path)
        project_type = detector.detect()

        # For now, implement basic rollback based on project type
        if project_type in ["web_app", "ml_pipeline"]:
            # ECS rollback - would need to get previous task definition
            return {
                "success": True,
                "message": f"Simulated rollback for {project_type} project",
                "target": target,
                "version": to_version or "previous",
            }
        elif project_type == "firmware_edge":
            # Firmware rollback - would flash previous firmware
            return {
                "success": True,
                "message": "Simulated firmware rollback",
                "target": target,
                "version": to_version or "previous",
            }
        else:
            return {
                "success": False,
                "error": f"Rollback not supported for project type: {project_type}",
            }

    except Exception as e:
        return {"success": False, "error": str(e)}
