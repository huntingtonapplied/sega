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
SEGA FRONTEND ORCHESTRATION COMMAND
==============================================================================
File: src/sega/commands/frontend.py
Project: SEGA (Scalable Engineering & Growth Automation)
Copyright: 2022-2025 FLEET
License: Apache-2.0

SEGA MODULE: Commands/Frontend
COMPONENT: Group-Based Frontend Build and Serve Orchestration
PURPOSE: Build and serve multiple Next.js frontends with shared/isolated modes
DEPENDENCIES: click, subprocess, pathlib
USAGE: sega frontend [build|serve|up|down|status|install]

This command provides orchestrated frontend deployment for FLEET projects:
- Group-based operations (group1, group2, local, all)
- Shared mode (uses ~/fleet/environments/node_modules)
- Isolated mode (uses project-specific node_modules)
- Parallel build/serve with configurable concurrency

Configuration is loaded from config/sega.toml (TOML-based central configuration).
==============================================================================
"""

import click
import subprocess
import os
import signal
import socket
import json
import time
from pathlib import Path
from typing import Dict, List, Optional, Any
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass

from sega.core.config import get_config, SegaConfig, DeploymentTarget
from sega.infrastructure.ec2_config import (
    get_instance,
    get_instance_by_project,
    build_ssh_command,
    EC2Instance,
)


@dataclass
class FrontendResult:
    """Result of a frontend operation."""
    project: str
    success: bool
    message: str
    port: Optional[int] = None
    pid: Optional[int] = None


class FrontendOrchestrator:
    """Orchestrates frontend build and serve operations across project groups."""

    def __init__(self):
        self.config = get_config()
        self.fleet_root = self._find_fleet_root()

    @property
    def infra(self):
        """Shortcut to infrastructure config."""
        return self.config.infrastructure

    @property
    def fe_config(self):
        """Shortcut to frontend orchestration config."""
        return self.infra.frontend_orchestration

    def _find_fleet_root(self) -> Path:
        """Find FLEET root directory."""
        # Check environment variable
        if 'FLEET_ROOT' in os.environ:
            return Path(os.environ['FLEET_ROOT'])

        # Try common locations
        home = Path.home()
        for path in [home / 'fleet', Path('/home/ubuntu/fleet'), Path.cwd()]:
            if (path / '.gitmodules').exists():
                return path

        # Default to home/fleet
        return home / 'fleet'

    def get_group_projects(self, group: str) -> List[str]:
        """Get list of projects in a group.

        Groups are mapped to configured instances (declaration order):
        - group1: first [instances.*] entry's projects
        - group2: second [instances.*] entry's projects (groupN likewise)
        - local: local-only projects
        - all: all projects with frontends
        """
        if group == 'all':
            return [p.name for p in self.config.projects.values() if p.has_frontend]

        if group.startswith('group') and group[5:].isdigit():
            idx = int(group[5:])
            names = list(self.config.instances.keys())
            if 1 <= idx <= len(names):
                instance = self.config.get_instance(names[idx - 1])
                if instance:
                    return [n for n in instance.projects if self._has_frontend(n)]
            return []

        if group == 'local':
            return [
                p.name for p in self.config.projects.values()
                if p.deployment_target in (DeploymentTarget.LOCAL, DeploymentTarget.NOT_SERVED)
                and p.has_frontend
            ]

        return []

    def _has_frontend(self, project_name: str) -> bool:
        """Check if project has a frontend."""
        project = self.config.get_project(project_name)
        return project.has_frontend if project else False

    def get_shared_env_path(self) -> Path:
        """Get path to shared environments directory."""
        root = self.infra.shared_environments.root
        root = root.replace('${FLEET_ROOT}', str(self.fleet_root))
        return Path(root)

    def get_frontend_path(self, project: str) -> Path:
        """Get path to project's frontend directory."""
        return self.fleet_root / project / 'frontend'

    def get_project_port(self, project: str) -> int:
        """Get frontend port for a project (computed from project ID)."""
        proj = self.config.get_project(project)
        if proj:
            return proj.frontend_port
        return 3000

    def setup_shared_mode(self, project: str) -> bool:
        """Setup shared node_modules symlink for a project."""
        frontend_path = self.get_frontend_path(project)
        if not frontend_path.exists():
            return False

        shared_env = self.get_shared_env_path()
        shared_node_modules = shared_env / 'node_modules'

        if not shared_node_modules.exists():
            click.echo(f"[WARNING] Shared node_modules not found at {shared_node_modules}")
            return False

        project_node_modules = frontend_path / 'node_modules'

        # Remove existing node_modules if it's not a symlink
        if project_node_modules.exists() and not project_node_modules.is_symlink():
            click.echo(f"[INFO] Removing existing node_modules for {project}")
            subprocess.run(['rm', '-rf', str(project_node_modules)], check=True)

        # Create symlink if it doesn't exist
        if not project_node_modules.exists():
            click.echo(f"[INFO] Creating symlink for {project} -> shared node_modules")
            project_node_modules.symlink_to(shared_node_modules)

        return True

    def setup_isolated_mode(self, project: str) -> bool:
        """Ensure project has its own node_modules (remove symlink if exists)."""
        frontend_path = self.get_frontend_path(project)
        if not frontend_path.exists():
            return False

        project_node_modules = frontend_path / 'node_modules'

        # Remove symlink if it exists
        if project_node_modules.is_symlink():
            click.echo(f"[INFO] Removing symlink for {project}, will use isolated mode")
            project_node_modules.unlink()

        # Run npm install if node_modules doesn't exist
        if not project_node_modules.exists():
            click.echo(f"[INFO] Running npm install for {project}")
            result = subprocess.run(
                ['npm', 'install'],
                cwd=frontend_path,
                capture_output=True,
                text=True
            )
            if result.returncode != 0:
                click.echo(f"[ERROR] npm install failed for {project}: {result.stderr}")
                return False

        return True

    def build_frontend(self, project: str, mode: str = 'shared', clean: bool = False) -> FrontendResult:
        """Build a single frontend project."""
        frontend_path = self.get_frontend_path(project)

        if not frontend_path.exists():
            return FrontendResult(
                project=project,
                success=False,
                message=f"Frontend directory not found: {frontend_path}"
            )

        # Setup dependency mode
        if mode == 'shared':
            if not self.setup_shared_mode(project):
                return FrontendResult(
                    project=project,
                    success=False,
                    message="Failed to setup shared mode"
                )
        else:
            if not self.setup_isolated_mode(project):
                return FrontendResult(
                    project=project,
                    success=False,
                    message="Failed to setup isolated mode"
                )

        # Clean if requested
        if clean:
            output_dir = self.fe_config.build.output_dir
            next_dir = frontend_path / output_dir
            if next_dir.exists():
                subprocess.run(['rm', '-rf', str(next_dir)])

        # Get build config from TOML
        build_cmd = self.fe_config.build.command
        timeout = self.fe_config.build.timeout

        click.echo(f"[INFO] Building {project}...")

        try:
            result = subprocess.run(
                build_cmd.split(),
                cwd=frontend_path,
                capture_output=True,
                text=True,
                timeout=timeout
            )

            if result.returncode == 0:
                return FrontendResult(
                    project=project,
                    success=True,
                    message="Build successful"
                )
            else:
                return FrontendResult(
                    project=project,
                    success=False,
                    message=f"Build failed: {result.stderr[:500]}"
                )

        except subprocess.TimeoutExpired:
            return FrontendResult(
                project=project,
                success=False,
                message=f"Build timed out after {timeout}s"
            )
        except Exception as e:
            return FrontendResult(
                project=project,
                success=False,
                message=f"Build error: {str(e)}"
            )

    def serve_frontend(
        self,
        project: str,
        mode: str = 'shared',
        dev: bool = False,
        background: bool = True
    ) -> FrontendResult:
        """Start a frontend server for a project."""
        frontend_path = self.get_frontend_path(project)

        if not frontend_path.exists():
            return FrontendResult(
                project=project,
                success=False,
                message=f"Frontend directory not found: {frontend_path}"
            )

        # Setup dependency mode
        if mode == 'shared':
            if not self.setup_shared_mode(project):
                return FrontendResult(
                    project=project,
                    success=False,
                    message="Failed to setup shared mode"
                )

        port = self.get_project_port(project)

        # Check if port is already in use
        if self._is_port_in_use(port):
            return FrontendResult(
                project=project,
                success=False,
                message=f"Port {port} is already in use",
                port=port
            )

        # Get serve config from TOML
        if dev:
            serve_cmd = self.fe_config.serve.dev_command
        else:
            serve_cmd = self.fe_config.serve.command

        # Add port to command
        serve_cmd = f"{serve_cmd} -- -p {port}"

        click.echo(f"[INFO] Starting {project} on port {port}...")

        try:
            if background:
                # Start in background
                process = subprocess.Popen(
                    serve_cmd,
                    shell=True,
                    cwd=frontend_path,
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                    preexec_fn=os.setsid
                )

                # Wait briefly and check if process started
                time.sleep(2)
                if process.poll() is None:
                    return FrontendResult(
                        project=project,
                        success=True,
                        message=f"Server started on port {port}",
                        port=port,
                        pid=process.pid
                    )
                else:
                    return FrontendResult(
                        project=project,
                        success=False,
                        message="Server process exited immediately",
                        port=port
                    )
            else:
                # Run in foreground (blocking)
                result = subprocess.run(
                    serve_cmd,
                    shell=True,
                    cwd=frontend_path
                )
                return FrontendResult(
                    project=project,
                    success=result.returncode == 0,
                    message="Server stopped" if result.returncode == 0 else "Server failed",
                    port=port
                )

        except Exception as e:
            return FrontendResult(
                project=project,
                success=False,
                message=f"Failed to start server: {str(e)}",
                port=port
            )

    def stop_frontend(self, project: str, force: bool = False) -> FrontendResult:
        """Stop a frontend server for a project."""
        port = self.get_project_port(project)

        # Find process using the port
        try:
            result = subprocess.run(
                ['lsof', '-t', f'-i:{port}'],
                capture_output=True,
                text=True
            )

            if result.returncode == 0 and result.stdout.strip():
                pids = result.stdout.strip().split('\n')
                for pid in pids:
                    try:
                        sig = signal.SIGKILL if force else signal.SIGTERM
                        os.kill(int(pid), sig)
                    except ProcessLookupError:
                        pass

                return FrontendResult(
                    project=project,
                    success=True,
                    message=f"Stopped {len(pids)} process(es) on port {port}",
                    port=port
                )
            else:
                return FrontendResult(
                    project=project,
                    success=True,
                    message=f"No process found on port {port}",
                    port=port
                )

        except Exception as e:
            return FrontendResult(
                project=project,
                success=False,
                message=f"Failed to stop: {str(e)}",
                port=port
            )

    def get_frontend_status(self, project: str) -> Dict[str, Any]:
        """Get status of a frontend server."""
        port = self.get_project_port(project)
        frontend_path = self.get_frontend_path(project)

        status = {
            'project': project,
            'port': port,
            'running': False,
            'healthy': False,
            'mode': 'unknown',
            'pid': None
        }

        if not frontend_path.exists():
            status['error'] = 'Frontend directory not found'
            return status

        # Check mode
        node_modules = frontend_path / 'node_modules'
        if node_modules.is_symlink():
            status['mode'] = 'shared'
        elif node_modules.exists():
            status['mode'] = 'isolated'
        else:
            status['mode'] = 'no_deps'

        # Check if port is in use
        if self._is_port_in_use(port):
            status['running'] = True

            # Get PID
            try:
                result = subprocess.run(
                    ['lsof', '-t', f'-i:{port}'],
                    capture_output=True,
                    text=True
                )
                if result.stdout.strip():
                    status['pid'] = int(result.stdout.strip().split('\n')[0])
            except Exception:
                pass

            # Health check
            try:
                import urllib.request
                health_path = self.fe_config.serve.health_check_path
                url = f'http://localhost:{port}{health_path}'
                req = urllib.request.Request(url, method='HEAD')
                with urllib.request.urlopen(req, timeout=5) as response:
                    status['healthy'] = response.status == 200
            except Exception:
                status['healthy'] = False

        return status

    def _is_port_in_use(self, port: int) -> bool:
        """Check if a port is in use."""
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                return s.connect_ex(('127.0.0.1', port)) == 0
        except Exception:
            return False

    def build_group(
        self,
        group: str,
        mode: str = 'shared',
        parallel: int = 4,
        clean: bool = False
    ) -> Dict[str, FrontendResult]:
        """Build all frontends in a group."""
        projects = self.get_group_projects(group)
        results = {}

        if not projects:
            click.echo(f"[WARNING] No projects found in group: {group}")
            return results

        click.echo(f"[INFO] Building {len(projects)} frontends in {group} ({mode} mode)")

        # Get max concurrent from TOML config
        max_concurrent = min(parallel, self.fe_config.parallel.max_concurrent)

        with ThreadPoolExecutor(max_workers=max_concurrent) as executor:
            futures = {
                executor.submit(self.build_frontend, project, mode, clean): project
                for project in projects
            }

            for future in as_completed(futures):
                project = futures[future]
                try:
                    result = future.result()
                    results[project] = result
                    status = "[OK]" if result.success else "[ERROR]"
                    click.echo(f"  {status} {project}: {result.message}")
                except Exception as e:
                    results[project] = FrontendResult(
                        project=project,
                        success=False,
                        message=str(e)
                    )

        return results

    def serve_group(
        self,
        group: str,
        mode: str = 'shared',
        dev: bool = False,
        background: bool = True
    ) -> Dict[str, FrontendResult]:
        """Serve all frontends in a group."""
        projects = self.get_group_projects(group)
        results = {}

        if not projects:
            click.echo(f"[WARNING] No projects found in group: {group}")
            return results

        click.echo(f"[INFO] Starting {len(projects)} frontends in {group}")

        # Get stagger delay from TOML config
        stagger_delay = self.fe_config.parallel.stagger_delay

        for project in projects:
            result = self.serve_frontend(project, mode, dev, background)
            results[project] = result
            status = "[OK]" if result.success else "[ERROR]"
            click.echo(f"  {status} {project}: {result.message}")

            if background:
                time.sleep(stagger_delay)

        return results

    def stop_group(self, group: str, force: bool = False) -> Dict[str, FrontendResult]:
        """Stop all frontends in a group."""
        projects = self.get_group_projects(group)
        results = {}

        if not projects:
            click.echo(f"[WARNING] No projects found in group: {group}")
            return results

        click.echo(f"[INFO] Stopping {len(projects)} frontends in {group}")

        for project in projects:
            result = self.stop_frontend(project, force)
            results[project] = result
            status = "[OK]" if result.success else "[ERROR]"
            click.echo(f"  {status} {project}: {result.message}")

        return results

    def get_instance_for_group(self, group: str) -> Optional[EC2Instance]:
        """Get EC2 instance for a group."""
        if group == 'group1':
            return get_instance('1')
        elif group == 'group2':
            return get_instance('2')
        return None

    def execute_remote(
        self,
        instance: EC2Instance,
        command: str,
        capture_output: bool = True,
        timeout: int = 300
    ) -> FrontendResult:
        """Execute a command on a remote EC2 instance via SSH.

        Args:
            instance: Target EC2 instance
            command: Command to execute
            capture_output: Whether to capture stdout/stderr
            timeout: Timeout in seconds

        Returns:
            FrontendResult with execution status
        """
        ssh_cmd = build_ssh_command(instance, command)

        click.echo(f"[INFO] Executing on {instance.name}: {command[:80]}...")

        try:
            result = subprocess.run(
                ssh_cmd,
                capture_output=capture_output,
                text=True,
                timeout=timeout
            )

            if result.returncode == 0:
                return FrontendResult(
                    project=instance.name,
                    success=True,
                    message=f"Remote command succeeded",
                )
            else:
                error_msg = result.stderr[:500] if result.stderr else f"Exit code {result.returncode}"
                return FrontendResult(
                    project=instance.name,
                    success=False,
                    message=f"Remote command failed: {error_msg}",
                )

        except subprocess.TimeoutExpired:
            return FrontendResult(
                project=instance.name,
                success=False,
                message=f"Remote command timed out after {timeout}s",
            )
        except Exception as e:
            return FrontendResult(
                project=instance.name,
                success=False,
                message=f"SSH error: {str(e)}",
            )

    def build_remote(
        self,
        group: str,
        mode: str = 'shared',
        clean: bool = False
    ) -> FrontendResult:
        """Build frontends on remote EC2 instance."""
        instance = self.get_instance_for_group(group)
        if not instance:
            return FrontendResult(
                project=group,
                success=False,
                message=f"No EC2 instance for group: {group}"
            )

        # Build the remote command
        clean_flag = '--clean' if clean else ''
        cmd = f"cd ~/fleet/sega && sega frontend build --group {group} --mode {mode} {clean_flag}"

        return self.execute_remote(instance, cmd.strip())

    def serve_remote(
        self,
        group: str,
        mode: str = 'shared',
        dev: bool = False
    ) -> FrontendResult:
        """Serve frontends on remote EC2 instance."""
        instance = self.get_instance_for_group(group)
        if not instance:
            return FrontendResult(
                project=group,
                success=False,
                message=f"No EC2 instance for group: {group}"
            )

        # Build the remote command
        dev_flag = '--dev' if dev else ''
        cmd = f"cd ~/fleet/sega && sega frontend serve --group {group} --mode {mode} {dev_flag}"

        return self.execute_remote(instance, cmd.strip())

    def stop_remote(self, group: str, force: bool = False) -> FrontendResult:
        """Stop frontends on remote EC2 instance."""
        instance = self.get_instance_for_group(group)
        if not instance:
            return FrontendResult(
                project=group,
                success=False,
                message=f"No EC2 instance for group: {group}"
            )

        force_flag = '--force' if force else ''
        cmd = f"cd ~/fleet/sega && sega frontend down --group {group} {force_flag}"

        return self.execute_remote(instance, cmd.strip())


# =============================================================================
# CLI COMMANDS
# =============================================================================

@click.group()
def frontend():
    """Group-based frontend build and serve orchestration.

    Build and serve multiple Next.js frontends across project groups with
    support for shared or isolated dependency modes.

    Groups (from sega.toml):
      - group1: first configured instance's projects
      - group2: second configured instance's projects
      - local: Local-only projects (sega, tracker, spro)
      - all: All projects with frontends

    Modes:
      - shared: Use ~/fleet/environments/node_modules (faster, less disk)
      - isolated: Use project-specific node_modules (version isolation)

    Configuration is loaded from config/sega.toml.
    """
    pass


@frontend.command()
@click.option('--group', '-g', required=True,
              type=click.Choice(['group1', 'group2', 'local', 'all']),
              help='Project group to build')
@click.option('--mode', '-m', default='shared',
              type=click.Choice(['shared', 'isolated']),
              help='Dependency mode (default: shared)')
@click.option('--parallel', '-p', default=4, type=int,
              help='Max concurrent builds (default: 4)')
@click.option('--project', multiple=True,
              help='Build specific project(s) instead of group')
@click.option('--clean', is_flag=True,
              help='Clean build directory before build')
@click.option('--dry-run', is_flag=True,
              help='Show what would be built without executing')
@click.option('--remote', is_flag=True,
              help='Execute on remote EC2 instance (auto-detects from group)')
def build(group, mode, parallel, project, clean, dry_run, remote):
    """Build frontend assets for projects in a group.

    Examples:
        sega frontend build --group group1
        sega frontend build --group group1 --mode isolated
        sega frontend build --project atlas --project hermes
        sega frontend build --group group1 --clean
        sega frontend build --group group1 --remote  # Build on EC2 Instance 1
    """
    try:
        orchestrator = FrontendOrchestrator()

        if dry_run:
            if project:
                projects = list(project)
            else:
                projects = orchestrator.get_group_projects(group)
            remote_info = " (remote)" if remote else ""
            click.echo(f"[DRY RUN] Would build {len(projects)} frontends{remote_info}:")
            for p in projects:
                port = orchestrator.get_project_port(p)
                click.echo(f"  - {p} (port {port})")
            return

        # Handle remote execution
        if remote:
            if group in ('local', 'all'):
                click.echo(f"[ERROR] --remote not supported for group: {group}")
                click.echo("  Use --group group1 or --group group2 for remote execution")
                exit(1)

            click.echo(f"[INFO] Building on remote EC2 instance for {group}...")
            result = orchestrator.build_remote(group, mode, clean)
            status = "[OK]" if result.success else "[ERROR]"
            click.echo(f"{status} {result.message}")

            if not result.success:
                exit(1)
            return

        if project:
            # Build specific projects
            results = {}
            for p in project:
                result = orchestrator.build_frontend(p, mode, clean)
                results[p] = result
                status = "[OK]" if result.success else "[ERROR]"
                click.echo(f"{status} {p}: {result.message}")
        else:
            # Build group
            results = orchestrator.build_group(group, mode, parallel, clean)

        # Summary
        successful = sum(1 for r in results.values() if r.success)
        failed = len(results) - successful

        click.echo(f"\n[INFO] Build Summary: {successful} successful, {failed} failed")

        if failed > 0:
            exit(1)

    except Exception as e:
        click.echo(f"[ERROR] Build failed: {e}")
        exit(1)


@frontend.command()
@click.option('--group', '-g', required=True,
              type=click.Choice(['group1', 'group2', 'local', 'all']),
              help='Project group to serve')
@click.option('--mode', '-m', default='shared',
              type=click.Choice(['shared', 'isolated']),
              help='Dependency mode (default: shared)')
@click.option('--dev', is_flag=True,
              help='Use development server (npm run dev)')
@click.option('--background/--foreground', default=True,
              help='Run in background (default: background)')
@click.option('--project', multiple=True,
              help='Serve specific project(s) instead of group')
@click.option('--remote', is_flag=True,
              help='Execute on remote EC2 instance (auto-detects from group)')
def serve(group, mode, dev, background, project, remote):
    """Start frontend servers for projects in a group.

    Examples:
        sega frontend serve --group group1
        sega frontend serve --group group1 --dev
        sega frontend serve --project atlas --foreground
        sega frontend serve --group group1 --remote  # Serve on EC2 Instance 1
    """
    try:
        orchestrator = FrontendOrchestrator()

        # Handle remote execution
        if remote:
            if group in ('local', 'all'):
                click.echo(f"[ERROR] --remote not supported for group: {group}")
                click.echo("  Use --group group1 or --group group2 for remote execution")
                exit(1)

            click.echo(f"[INFO] Starting frontends on remote EC2 instance for {group}...")
            result = orchestrator.serve_remote(group, mode, dev)
            status = "[OK]" if result.success else "[ERROR]"
            click.echo(f"{status} {result.message}")

            if not result.success:
                exit(1)
            return

        if project:
            # Serve specific projects
            results = {}
            for p in project:
                result = orchestrator.serve_frontend(p, mode, dev, background)
                results[p] = result
                status = "[OK]" if result.success else "[ERROR]"
                click.echo(f"{status} {p}: {result.message}")
        else:
            # Serve group
            results = orchestrator.serve_group(group, mode, dev, background)

        # Summary
        successful = sum(1 for r in results.values() if r.success)
        failed = len(results) - successful

        click.echo(f"\n[INFO] Serve Summary: {successful} started, {failed} failed")

        if failed > 0:
            exit(1)

    except Exception as e:
        click.echo(f"[ERROR] Serve failed: {e}")
        exit(1)


@frontend.command()
@click.option('--group', '-g', required=True,
              type=click.Choice(['group1', 'group2', 'local', 'all']),
              help='Project group')
@click.option('--mode', '-m', default='shared',
              type=click.Choice(['shared', 'isolated']),
              help='Dependency mode (default: shared)')
@click.option('--dev', is_flag=True,
              help='Use development servers')
@click.option('--skip-build', is_flag=True,
              help='Skip build step, only serve')
@click.option('--clean', is_flag=True,
              help='Clean before build')
def up(group, mode, dev, skip_build, clean):
    """Build and serve frontends in one command.

    Examples:
        sega frontend up --group group1 --mode shared
        sega frontend up --group group1 --skip-build
        sega frontend up --group group1 --dev
    """
    try:
        orchestrator = FrontendOrchestrator()

        # Build step
        if not skip_build:
            click.echo("\n=== BUILD PHASE ===")
            build_results = orchestrator.build_group(group, mode, clean=clean)

            build_failed = sum(1 for r in build_results.values() if not r.success)
            if build_failed > 0:
                click.echo(f"[WARNING] {build_failed} builds failed, continuing with serve...")

        # Serve step
        click.echo("\n=== SERVE PHASE ===")
        serve_results = orchestrator.serve_group(group, mode, dev, background=True)

        # Final summary
        successful = sum(1 for r in serve_results.values() if r.success)
        click.echo(f"\n[INFO] {successful}/{len(serve_results)} frontends running")

    except Exception as e:
        click.echo(f"[ERROR] Up failed: {e}")
        exit(1)


@frontend.command()
@click.option('--group', '-g', required=True,
              type=click.Choice(['group1', 'group2', 'local', 'all']),
              help='Project group to stop')
@click.option('--project', multiple=True,
              help='Stop specific project(s)')
@click.option('--force', is_flag=True,
              help='Force kill processes')
def down(group, project, force):
    """Stop frontend servers for projects in a group.

    Examples:
        sega frontend down --group group1
        sega frontend down --project atlas --force
    """
    try:
        orchestrator = FrontendOrchestrator()

        if project:
            for p in project:
                result = orchestrator.stop_frontend(p, force)
                status = "[OK]" if result.success else "[ERROR]"
                click.echo(f"{status} {p}: {result.message}")
        else:
            orchestrator.stop_group(group, force)

    except Exception as e:
        click.echo(f"[ERROR] Down failed: {e}")
        exit(1)


@frontend.command()
@click.option('--group', '-g', default='all',
              type=click.Choice(['group1', 'group2', 'local', 'all']),
              help='Filter by group (default: all)')
@click.option('--format', '-f', 'output_format', default='table',
              type=click.Choice(['table', 'json', 'simple']),
              help='Output format (default: table)')
def status(group, output_format):
    """Show status of frontend servers.

    Examples:
        sega frontend status
        sega frontend status --group group1
        sega frontend status --format json
    """
    try:
        orchestrator = FrontendOrchestrator()
        projects = orchestrator.get_group_projects(group)

        statuses = []
        for project in projects:
            statuses.append(orchestrator.get_frontend_status(project))

        if output_format == 'json':
            click.echo(json.dumps(statuses, indent=2))
            return

        if output_format == 'simple':
            for s in statuses:
                running = "[RUNNING]" if s['running'] else "[STOPPED]"
                click.echo(f"{running} {s['project']}:{s['port']} ({s['mode']})")
            return

        # Table format
        click.echo(f"\nFrontend Status - {group}")
        click.echo("=" * 70)
        click.echo(f"{'Project':<20} {'Port':<7} {'Status':<10} {'Health':<10} {'Mode':<10}")
        click.echo("-" * 70)

        for s in statuses:
            status_str = "running" if s['running'] else "stopped"
            health_str = "healthy" if s['healthy'] else ("unhealthy" if s['running'] else "-")
            click.echo(f"{s['project']:<20} {s['port']:<7} {status_str:<10} {health_str:<10} {s['mode']:<10}")

        # Summary
        running = sum(1 for s in statuses if s['running'])
        healthy = sum(1 for s in statuses if s['healthy'])
        click.echo("-" * 70)
        click.echo(f"Total: {len(statuses)} | Running: {running} | Healthy: {healthy}")

    except Exception as e:
        click.echo(f"[ERROR] Status failed: {e}")
        exit(1)


@frontend.command()
@click.option('--mode', '-m', default='shared',
              type=click.Choice(['shared', 'isolated']),
              help='Target mode')
@click.option('--update', is_flag=True,
              help='Update dependencies (npm update)')
def install(mode, update):
    """Install/sync dependencies for shared mode.

    Examples:
        sega frontend install --mode shared
        sega frontend install --mode shared --update
    """
    try:
        orchestrator = FrontendOrchestrator()
        shared_env = orchestrator.get_shared_env_path()

        if mode == 'shared':
            click.echo(f"[INFO] Installing shared dependencies at {shared_env}")

            if not shared_env.exists():
                shared_env.mkdir(parents=True, exist_ok=True)

            # Check for package.json
            package_json = shared_env / 'package.json'
            if not package_json.exists():
                click.echo("[WARNING] No package.json found in shared environment")
                click.echo("[INFO] You may need to create one or copy from a project")
                return

            cmd = 'npm update' if update else 'npm install'
            result = subprocess.run(
                cmd.split(),
                cwd=shared_env,
                capture_output=True,
                text=True
            )

            if result.returncode == 0:
                click.echo("[OK] Dependencies installed successfully")
            else:
                click.echo(f"[ERROR] Install failed: {result.stderr}")
                exit(1)

        else:
            click.echo("[INFO] For isolated mode, use 'sega frontend build --mode isolated'")
            click.echo("[INFO] This will run npm install for each project as needed")

    except Exception as e:
        click.echo(f"[ERROR] Install failed: {e}")
        exit(1)


# Register the command group
if __name__ == '__main__':
    frontend()
