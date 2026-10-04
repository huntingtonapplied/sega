#!/usr/bin/env python3
"""
SEGA Sysnc Command - Multi-System Synchronization

Provides git synchronization utilities for the FLEET 3-system architecture:
- Local system (infrastructure focus)
- Instance 1 (healer workers + project group 1)
- Instance 2 (surgeon workers + project group 2)

Wraps the battle-tested bash/python implementations with a SEGA-native CLI interface.

EC2 instance configuration is loaded from config/sega.toml and passed
to the shell scripts via environment variables.
"""

import os
import subprocess
import sys
from pathlib import Path
from typing import List, Optional

import click

from sega.infrastructure import (
    INSTANCE1,
    INSTANCE2,
    INSTANCE3,
    INSTANCE4,
    get_ssh_key_path,
)

# Path to embedded sysnc scripts
SYSNC_DIR = Path(__file__).parent.parent / "system" / "sysnc"


def run_script(script_name: str, args: Optional[List[str]] = None, env_overrides: Optional[dict] = None) -> int:
    """Execute a sysnc script with given arguments.

    Passes EC2 configuration from sega.toml via environment variables.
    """
    # Build environment with EC2 config from TOML
    env = os.environ.copy()

    # Set EC2 instance IPs from TOML config
    env["INSTANCE1_IP"] = INSTANCE1.ip
    env["INSTANCE2_IP"] = INSTANCE2.ip
    env["INSTANCE3_IP"] = INSTANCE3.ip if INSTANCE3.ip else ""
    env["INSTANCE4_IP"] = INSTANCE4.ip if INSTANCE4.ip else ""
    env["INSTANCE1_USER"] = INSTANCE1.user
    env["INSTANCE2_USER"] = INSTANCE2.user
    env["INSTANCE3_USER"] = INSTANCE3.user
    env["INSTANCE4_USER"] = INSTANCE4.user

    # Project lane definitions for lane-validation scripts (regex alternations)
    if INSTANCE1.projects:
        env["SYSNC_GROUP1_PROJECTS"] = "|".join(INSTANCE1.projects)
    if INSTANCE2.projects:
        env["SYSNC_GROUP2_PROJECTS"] = "|".join(INSTANCE2.projects)
    if INSTANCE3.projects:
        env["SYSNC_GROUP3_PROJECTS"] = "|".join(INSTANCE3.projects)

    # Union of all configured projects (space-separated)
    all_projects = sorted(
        {p for inst in (INSTANCE1, INSTANCE2, INSTANCE3, INSTANCE4) for p in inst.projects}
    )
    if all_projects:
        env["SYSNC_ALL_PROJECTS"] = " ".join(all_projects)

    # Set SSH key path
    try:
        env["SSH_KEY_PATH"] = str(get_ssh_key_path())
    except FileNotFoundError:
        # Let scripts use their defaults
        pass

    if env_overrides:
        env.update(env_overrides)

    script_path = SYSNC_DIR / script_name
    cmd = [str(script_path)] + (args or [])

    try:
        result = subprocess.run(cmd, cwd=str(Path.home() / "fleet"), env=env)
        return result.returncode
    except KeyboardInterrupt:
        return 130
    except Exception as e:
        click.echo(f"Error running {script_name}: {e}", err=True)
        return 1


@click.group()
def sysnc():
    """Multi-system synchronization for FLEET ecosystem.

    Manages git synchronization across 4 systems:
    - Local: Infrastructure (sega, tracker, spro, atlas)
    - Instance 1 (203.0.113.10): Group 1 + Group 4 (temp)
    - Instance 2 (203.0.113.20): Group 2
    - Instance 3 (203.0.113.30): Group 3
    - Instance 4 (TBD): Group 4 (future)
    """
    pass


@sysnc.command()
@click.option("--enhanced", "-e", is_flag=True, help="Use enhanced inspection with lane validation")
def inspect(enhanced):
    """Inspect changes across all 3 systems.

    Shows git status, file counts, and directory breakdown for each system.
    Use --enhanced for lane separation validation.
    """
    script = "inspect-ec2-changes-enhanced.sh" if enhanced else "inspect-ec2-changes.sh"
    sys.exit(run_script(script))


@sysnc.command()
def analyze():
    """Analyze 3-way conflicts before consolidation.

    Detects files modified on multiple systems and categorizes by priority:
    - 3-way conflicts (all systems) - requires manual intervention
    - 2-way conflicts (two systems) - careful review needed
    - Unique changes (one system) - safe to sync
    """
    script_path = SYSNC_DIR / "analyze-3way-conflicts.py"
    result = subprocess.run([sys.executable, str(script_path)], cwd=str(Path.home() / "fleet"))
    sys.exit(result.returncode)


@sysnc.command()
@click.option("--dry-run", is_flag=True, help="Preview without executing")
@click.option("--phase", type=click.Choice(["1", "2", "3", "all"]), default="all",
              help="Execute specific phase (1=I2, 2=I1, 3=Local, all=full workflow)")
@click.option("--yes", "-y", is_flag=True, help="Skip confirmation prompt")
def run(dry_run, phase, yes):
    """Execute consolidation workflow.

    Runs the stash-pull-pop-push workflow across systems in order:
    Phase 1: Instance 2 (pushes first)
    Phase 2: Instance 1 (pulls I2, then pushes)
    Phase 3: Local (pulls all, then pushes)

    CAUTION: This modifies git history across all systems.
    """
    if not yes and not dry_run:
        click.confirm("This will sync across all systems. Continue?", abort=True)

    args = []
    if dry_run:
        args.append("--dry-run")
    if phase != "all":
        args.extend(["--phase", phase])
    sys.exit(run_script("consolidate-with-submodules.sh", args))


@sysnc.command()
@click.option("--dry-run", is_flag=True, help="Preview without executing")
@click.option("--commit-number", "-c", help="Specific commit number (e.g., cc54)")
def bulk(dry_run, commit_number):
    """Run bulk stash-pull-pop-push on current system.

    This is the primary sync script - run it on each system in order:
    1. Instance 2 first
    2. Instance 1 second
    3. Local last

    Handles submodules with double-stash pattern for pointer consistency.
    """
    args = []
    if dry_run:
        args.append("--dry-run")
    if commit_number:
        args.extend(["--commit-number", commit_number])
    sys.exit(run_script("bulk-stash-pull-pop-push.sh", args))


@sysnc.command()
@click.option("--push", is_flag=True, help="Push settings to EC2 instances")
def settings(push):
    """Sync Claude settings to EC2 instances.

    Copies .claude/settings.local.json to both EC2 instances
    to maintain consistent AI context across systems.
    """
    if push:
        sys.exit(run_script("sync-claude-settings-to-ec2.sh"))
    else:
        click.echo("Use --push to sync settings to EC2 instances")
        click.echo("Settings file: ~/.claude/settings.local.json")


if __name__ == "__main__":
    sysnc()
