#!/usr/bin/env python3
"""
SEGA Sysmon Command - System Monitoring

Provides system monitoring for local and EC2 instances via the embedded
sysmon utility. Wraps the battle-tested bash implementation with a
SEGA-native CLI interface.

EC2 instance configuration is loaded from config/sega.toml and passed
to the shell scripts via environment variables.
"""

import os
import subprocess
import sys
from pathlib import Path
from typing import Optional

import click

from sega.infrastructure import (
    INSTANCE1,
    INSTANCE2,
    INSTANCE3,
    THRESHOLDS,
    get_ssh_key_path,
)

# Path to embedded sysmon scripts
SYSMON_DIR = Path(__file__).parent.parent.parent / "system" / "sysmon"
SYSMON_SCRIPT = SYSMON_DIR / "sysmon"


def run_sysmon(args: list, env_overrides: Optional[dict] = None) -> int:
    """Execute sysmon with given arguments.

    Passes EC2 configuration from sega.toml via environment variables.
    """
    # Build environment with EC2 config from TOML
    env = os.environ.copy()

    # Set EC2 instance IPs from TOML config
    env["SYSMON_INSTANCE1_IP"] = INSTANCE1.ip
    env["SYSMON_INSTANCE2_IP"] = INSTANCE2.ip
    env["SYSMON_INSTANCE3_IP"] = INSTANCE3.ip

    # SSH users and project groups from TOML config
    env["SYSMON_INSTANCE1_USER"] = INSTANCE1.user
    env["SYSMON_INSTANCE2_USER"] = INSTANCE2.user
    env["SYSMON_INSTANCE3_USER"] = INSTANCE3.user
    env["SYSMON_INSTANCE1_PROJECTS"] = " ".join(INSTANCE1.projects)
    env["SYSMON_INSTANCE2_PROJECTS"] = " ".join(INSTANCE2.projects)
    env["SYSMON_INSTANCE3_PROJECTS"] = " ".join(INSTANCE3.projects)

    # Set SSH key path
    try:
        env["SYSMON_SSH_KEY"] = str(get_ssh_key_path())
    except FileNotFoundError:
        # Let sysmon use its default if key not found
        pass

    # Set thresholds from config
    env["SYSMON_DISK_WARNING"] = str(THRESHOLDS["disk_warning"])
    env["SYSMON_DISK_CRITICAL"] = str(THRESHOLDS["disk_critical"])

    if env_overrides:
        env.update(env_overrides)

    cmd = [str(SYSMON_SCRIPT)] + args

    try:
        result = subprocess.run(cmd, cwd=str(SYSMON_DIR), env=env)
        return result.returncode
    except KeyboardInterrupt:
        return 130
    except Exception as e:
        click.echo(f"Error running sysmon: {e}", err=True)
        return 1


@click.group()
def sysmon():
    """System monitoring for local and EC2 instances.

    Monitor disk, memory, CPU, and Docker across the FLEET ecosystem.
    Supports local system and both EC2 instances (203.0.113.10, 203.0.113.20).
    """
    pass


@sysmon.command()
@click.option("--instance", "-i", type=click.Choice(["1", "2", "3"]), help="Specific EC2 instance")
@click.option("--all", "all_instances", is_flag=True, help="Check all instances (local + all EC2)")
@click.option("--quick", "-q", is_flag=True, help="Skip slow operations")
def status(instance, all_instances, quick):
    """Quick system status check.

    Shows disk, memory, load, Docker containers, and active sessions.
    """
    args = ["status"]
    if all_instances:
        args.append("--all")
    elif instance:
        args.extend(["--instance", instance])
    if quick:
        args.append("--quick")
    sys.exit(run_sysmon(args))


@sysmon.command()
@click.option("--instance", "-i", type=click.Choice(["1", "2", "3"]), help="Analyze specific EC2 instance")
@click.option("--with-cpu", is_flag=True, help="Include CPU/memory/process metrics")
@click.option("--output", "-o", type=click.Path(), help="Save report to file")
def analyze(instance, with_cpu, output):
    """Deep disk analysis with cleanup recommendations.

    Analyzes disk usage, Docker, build artifacts, and large files.
    """
    args = ["analyze"]
    if instance:
        args.extend(["--instance", instance])
    if with_cpu:
        args.append("--with-cpu")
    if output:
        args.extend(["--output", output])
    sys.exit(run_sysmon(args))


@sysmon.command()
@click.option("--quick", "-q", is_flag=True, help="Skip database volume sizing")
@click.option("--animate", is_flag=True, help="Enable live auto-updating dashboard")
@click.option("--interval", "-n", type=int, default=3, help="Refresh interval in seconds")
@click.option("--debug", is_flag=True, help="Enable debug logging to ~/.cache/sysmon/dashboard_debug.log")
def dashboard(quick, animate, interval, debug):
    """Multi-instance overview dashboard.

    Shows 4-table layout with storage and CPU metrics for both instances.

    In animated mode, use keys 1-6 to switch between pages:
      1=Overview, 2=Storage, 3=Docker, 4=CPU, 5=Graphs, 6=Services

    Page 6 (Services) shows non-Docker services running via npm/venv
    including Node.js frontends and Python/uvicorn backends.
    """
    args = ["dashboard"]
    if quick:
        args.append("--quick")
    if animate:
        args.append("--animate")
    if interval != 3:
        args.extend(["--interval", str(interval)])
    if debug:
        args.append("--debug")
    sys.exit(run_sysmon(args))


@sysmon.command()
@click.option("--instance", "-i", type=click.Choice(["1", "2", "3"]), help="Filter by instance")
@click.option("--project", "-p", help="Detailed view of single project")
@click.option("--quick", "-q", is_flag=True, help="Skip DB volume sizing")
def projects(instance, project, quick):
    """Project-based metrics dashboard.

    Shows containers, DB volumes, and disk usage per project.
    """
    args = ["projects"]
    if instance:
        args.extend(["--instance", instance])
    if project:
        args.extend(["--project", project])
    if quick:
        args.append("--quick")
    sys.exit(run_sysmon(args))


@sysmon.group()
def cleanup():
    """Cleanup operations for Docker and build artifacts."""
    pass


@cleanup.command("docker")
@click.option("--yes", "-y", is_flag=True, help="Skip confirmation prompts")
@click.option("--all-containers", is_flag=True, help="Stop and remove ALL containers (including running)")
@click.option("--aggressive", is_flag=True, help="Full cleanup including all unused images/volumes")
@click.option("--instance", "-i", type=click.Choice(["1", "2", "3"]), help="Run on EC2 instance")
@click.option("--all-instances", is_flag=True, help="Run on all EC2 instances")
@click.option("--dry-run", is_flag=True, help="Preview without executing")
def cleanup_docker(yes, all_containers, aggressive, instance, all_instances, dry_run):
    """Clean up Docker resources.

    Removes dangling images, stopped containers, and build cache.
    Use --all-containers to stop and remove running containers.
    Use --aggressive for full cleanup (includes unused volumes - DATA LOSS WARNING).
    """
    args = ["cleanup", "docker"]
    if yes:
        args.append("--yes")
    if all_containers:
        args.append("--all-containers")
    if aggressive:
        args.append("--aggressive")
    if instance:
        args.extend(["--instance", instance])
    if all_instances:
        args.append("--all-instances")
    if dry_run:
        args.append("--dry-run")
    sys.exit(run_sysmon(args))


@cleanup.command("builds")
@click.option("--yes", "-y", is_flag=True, help="Skip confirmation prompts")
@click.option("--include-node-modules", is_flag=True, help="Also remove node_modules directories")
@click.option("--include-rust", is_flag=True, help="Also remove Rust target directories")
@click.option("--path", type=click.Path(exists=True), help="Custom base path (default: ~/fleet)")
@click.option("--instance", "-i", type=click.Choice(["1", "2", "3"]), help="Run on EC2 instance")
@click.option("--all-instances", is_flag=True, help="Run on all EC2 instances")
@click.option("--dry-run", is_flag=True, help="Preview without executing")
def cleanup_builds(yes, include_node_modules, include_rust, path, instance, all_instances, dry_run):
    """Clean up build artifacts.

    Removes .next, build, dist, __pycache__, .pytest_cache, and .mypy_cache directories.
    Use --include-node-modules to also remove node_modules (requires npm install to restore).
    Use --include-rust to also remove Rust target directories.
    """
    args = ["cleanup", "builds"]
    if yes:
        args.append("--yes")
    if include_node_modules:
        args.append("--include-node-modules")
    if include_rust:
        args.append("--include-rust")
    if path:
        args.extend(["--path", path])
    if instance:
        args.extend(["--instance", instance])
    if all_instances:
        args.append("--all-instances")
    if dry_run:
        args.append("--dry-run")
    sys.exit(run_sysmon(args))


@cleanup.command("processes")
@click.option("--yes", "-y", is_flag=True, help="Skip confirmation prompts")
@click.option("--langservers", is_flag=True, help="Kill language server processes")
@click.option("--watchers", is_flag=True, help="Kill file watcher processes")
@click.option("--node", is_flag=True, help="Kill all node processes (careful!)")
@click.option("--all", "all_procs", is_flag=True, help="Kill langservers + watchers")
@click.option("--instance", "-i", type=click.Choice(["1", "2", "3"]), help="Run on EC2 instance")
@click.option("--all-instances", is_flag=True, help="Run on all EC2 instances")
def cleanup_processes(yes, langservers, watchers, node, all_procs, instance, all_instances):
    """Kill development processes.

    Kills language servers (pylsp, pyright, tsserver, etc.), file watchers,
    and optionally all node processes.
    """
    args = ["cleanup", "processes"]
    if yes:
        args.append("--yes")
    if langservers:
        args.append("--langservers")
    if watchers:
        args.append("--watchers")
    if node:
        args.append("--node")
    if all_procs:
        args.append("--all")
    if instance:
        args.extend(["--instance", instance])
    if all_instances:
        args.append("--all-instances")
    sys.exit(run_sysmon(args))


@cleanup.command("memory")
@click.option("--yes", "-y", is_flag=True, help="Skip confirmation prompts")
@click.option("--pagecache", is_flag=True, help="Clear page cache only (safest)")
@click.option("--dentries", is_flag=True, help="Clear dentries and inodes")
@click.option("--all", "all_caches", is_flag=True, help="Clear all memory caches")
@click.option("--instance", "-i", type=click.Choice(["1", "2", "3"]), help="Run on EC2 instance")
@click.option("--all-instances", is_flag=True, help="Run on all EC2 instances")
def cleanup_memory(yes, pagecache, dentries, all_caches, instance, all_instances):
    """Clear system memory caches.

    Clears page cache, dentries, and inodes. Requires sudo.
    This is safe - caches will be rebuilt automatically.
    """
    args = ["cleanup", "memory"]
    if yes:
        args.append("--yes")
    if pagecache:
        args.append("--pagecache")
    if dentries:
        args.append("--dentries")
    if all_caches:
        args.append("--all")
    if instance:
        args.extend(["--instance", instance])
    if all_instances:
        args.append("--all-instances")
    sys.exit(run_sysmon(args))


@sysmon.command()
@click.option("--format", "-f", type=click.Choice(["markdown", "json"]), default="markdown", help="Output format")
@click.option("--output", "-o", type=click.Path(), help="Save to file instead of stdout")
@click.option("--instance", "-i", type=click.Choice(["1", "2", "3"]), help="Single instance report")
@click.option("--all", "all_instances", is_flag=True, help="Include all instances")
def report(format, output, instance, all_instances):
    """Generate structured reports.

    Creates markdown or JSON reports with system metrics.
    """
    args = ["report"]
    if format:
        args.extend(["--format", format])
    if output:
        args.extend(["--output", output])
    if instance:
        args.extend(["--instance", instance])
    if all_instances:
        args.append("--all")
    sys.exit(run_sysmon(args))


@sysmon.command()
@click.option("--yes", "-y", is_flag=True, help="Skip confirmation prompts (DANGEROUS)")
@click.option("--include-volumes", is_flag=True, help="Include Docker volumes (DATA LOSS WARNING)")
@click.option("--instance", "-i", type=click.Choice(["1", "2", "3"]), help="Run on EC2 instance")
@click.option("--all-instances", is_flag=True, help="Run on all EC2 instances")
def nuke(yes, include_volumes, instance, all_instances):
    """Aggressive full system cleanup.

    Performs aggressive cleanup: kills language servers, stops all containers,
    prunes Docker, removes build artifacts and node_modules, clears memory cache.

    WARNING: This is destructive! All containers will be stopped and cached
    data will be lost.
    """
    args = ["nuke"]
    if yes:
        args.append("--yes")
    if include_volumes:
        args.append("--include-volumes")
    if instance:
        args.extend(["--instance", instance])
    if all_instances:
        args.append("--all-instances")
    sys.exit(run_sysmon(args))


if __name__ == "__main__":
    sysmon()
