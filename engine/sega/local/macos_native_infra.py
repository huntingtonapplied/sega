#!/usr/bin/env python3
"""
SEGA macOS Native Infrastructure Manager
==============================================================================
File: sega/local/macos_native_infra.py
Project: SEGA (Scalable Engineering & Growth Automation)
Copyright: 2025-2026 SEGA Contributors
License: Apache-2.0

PURPOSE: Truly dockerless infrastructure on macOS using Homebrew services

This provides ZERO Docker infrastructure for rapid development:
- PostgreSQL: Native via `brew services` (postgresql@16)
- Redis: Native via `brew services`

All backends run directly with Python using shared venv from:
  ~/fleet/environments/backend_venv

Port Allocation follows FLEET standards (from sega.toml):
- PostgreSQL: Single instance on 5432 (shared by all projects via databases)
- Redis: Single instance on 6379 (shared by all projects via database numbers)
- API: 8000 + project_id
- Frontend: 3000 + project_id
==============================================================================
"""

import subprocess
import sys
import time
from pathlib import Path
from typing import Dict, List, Optional, Tuple
import click


class MacOSNativeInfraManager:
    """Manages truly dockerless infrastructure on macOS.

    Uses Homebrew services for PostgreSQL and Redis - no Docker at all.
    This is optimal for development on Mac Mini M4 Pro (Node-1/Node-2).

    Architecture:
    - Single PostgreSQL instance (port 5432) with per-project databases
    - Single Redis instance (port 6379) with per-project database numbers
    - Backends run directly with Python from shared venv
    """

    # Project IDs sourced from config - used for Redis DB numbers and API ports
    from sega.core.config import get_config as _get_config

    PROJECT_IDS = {name: proj.id for name, proj in _get_config().projects.items()}
    del _get_config

    # Shared infrastructure ports (single instance, shared by all projects)
    POSTGRES_PORT = 5432
    REDIS_PORT = 6379

    # Default credentials for local dev
    POSTGRES_USER = "fleet"
    POSTGRES_PASSWORD = "ahldev"

    # Homebrew paths for Apple Silicon and Intel Macs
    HOMEBREW_PREFIX_ARM = "/opt/homebrew"
    HOMEBREW_PREFIX_INTEL = "/usr/local"

    def __init__(self):
        """Initialize macOS native infrastructure manager."""
        self._check_platform()
        self.fleet_root = Path.home() / "fleet"
        self.venv_path = self.fleet_root / "environments" / "backend_venv"
        self.brew_path = self._find_brew()
        self.homebrew_prefix = self._get_homebrew_prefix()
        self.pg_bin_path = Path(self.homebrew_prefix) / "opt" / "postgresql@16" / "bin"
        self.redis_bin_path = Path(self.homebrew_prefix) / "bin"

    def _get_homebrew_prefix(self) -> str:
        """Get Homebrew prefix based on architecture."""
        if Path(self.HOMEBREW_PREFIX_ARM).exists():
            return self.HOMEBREW_PREFIX_ARM
        return self.HOMEBREW_PREFIX_INTEL

    def _check_platform(self):
        """Verify we're on macOS."""
        if sys.platform != "darwin":
            raise RuntimeError("MacOSNativeInfraManager only works on macOS")

    def _find_brew(self) -> Optional[str]:
        """Find Homebrew executable path."""
        # Check standard Homebrew locations
        brew_paths = [
            "/opt/homebrew/bin/brew",  # Apple Silicon
            "/usr/local/bin/brew",      # Intel Mac
        ]
        for path in brew_paths:
            if Path(path).exists():
                return path
        # Fall back to PATH
        result = subprocess.run(["which", "brew"], capture_output=True, text=True)
        if result.returncode == 0:
            return result.stdout.strip()
        return None

    def _run(self, cmd: List[str], check: bool = True, capture: bool = True) -> subprocess.CompletedProcess:
        """Run a command and return result."""
        # Replace 'brew' with full path if needed
        if cmd and cmd[0] == "brew" and self.brew_path:
            cmd = [self.brew_path] + cmd[1:]
        return subprocess.run(
            cmd,
            capture_output=capture,
            text=True,
            check=check if not capture else False
        )

    def _brew_installed(self) -> bool:
        """Check if Homebrew is installed."""
        return self.brew_path is not None

    def _service_installed(self, service: str) -> bool:
        """Check if a brew service is installed."""
        result = self._run(["brew", "list", service])
        return result.returncode == 0

    def _service_running(self, service: str) -> bool:
        """Check if a brew service is running."""
        result = self._run(["brew", "services", "list"])
        if result.returncode != 0:
            return False
        for line in result.stdout.split("\n"):
            if service in line and "started" in line:
                return True
        return False

    # =========================================================================
    # SETUP
    # =========================================================================

    def setup(self) -> bool:
        """One-time setup of native infrastructure.
        
        Installs PostgreSQL and Redis via Homebrew if not present.
        Creates the shared 'fleet' superuser for PostgreSQL.
        """
        click.echo("[INFO] Setting up macOS native infrastructure...")

        if not self._brew_installed():
            click.echo("[ERROR] Homebrew not installed. Install from https://brew.sh")
            return False

        # Install PostgreSQL
        if not self._service_installed("postgresql@16"):
            click.echo("[INFO] Installing PostgreSQL 16...")
            result = self._run(["brew", "install", "postgresql@16"])
            if result.returncode != 0:
                click.echo(f"[ERROR] Failed to install PostgreSQL: {result.stderr}")
                return False
            click.echo("[OK] PostgreSQL 16 installed")
        else:
            click.echo("[OK] PostgreSQL 16 already installed")

        # Install Redis
        if not self._service_installed("redis"):
            click.echo("[INFO] Installing Redis...")
            result = self._run(["brew", "install", "redis"])
            if result.returncode != 0:
                click.echo(f"[ERROR] Failed to install Redis: {result.stderr}")
                return False
            click.echo("[OK] Redis installed")
        else:
            click.echo("[OK] Redis already installed")

        # Start services
        self.start()

        # Create FLEET superuser
        self._setup_postgres_user()

        click.echo("")
        click.echo("[OK] macOS native infrastructure ready")
        return True

    def _setup_postgres_user(self):
        """Create the FLEET PostgreSQL user if it doesn't exist."""
        psql = str(self.pg_bin_path / "psql")
        
        # Wait for PostgreSQL to be ready
        for _ in range(10):
            if self._check_postgres_ready():
                break
            time.sleep(1)

        # Get current user for connecting (brew postgres uses current user)
        import os
        current_user = os.environ.get("USER", "postgres")

        # Check if user exists
        result = self._run([
            psql, "-p", str(self.POSTGRES_PORT), "-U", current_user, "-d", "postgres", "-tAc",
            f"SELECT 1 FROM pg_roles WHERE rolname='{self.POSTGRES_USER}'"
        ])

        if "1" not in result.stdout:
            click.echo(f"[INFO] Creating PostgreSQL user '{self.POSTGRES_USER}'...")
            self._run([
                psql, "-p", str(self.POSTGRES_PORT), "-U", current_user, "-d", "postgres", "-c",
                f"CREATE USER {self.POSTGRES_USER} WITH SUPERUSER PASSWORD '{self.POSTGRES_PASSWORD}';"
            ])
            click.echo(f"[OK] User '{self.POSTGRES_USER}' created")
        else:
            click.echo(f"[OK] PostgreSQL user '{self.POSTGRES_USER}' exists")

    # =========================================================================
    # START / STOP
    # =========================================================================

    def start(self) -> bool:
        """Start PostgreSQL and Redis services."""
        click.echo("[INFO] Starting native infrastructure...")

        postgres_ok = self._start_postgres()
        redis_ok = self._start_redis()

        if postgres_ok and redis_ok:
            click.echo("[OK] Native infrastructure running")
            self._print_status()
            return True
        return False

    def _start_postgres(self) -> bool:
        """Start PostgreSQL via brew services."""
        if self._service_running("postgresql@16"):
            click.echo(f"[OK] PostgreSQL already running on port {self.POSTGRES_PORT}")
            return True

        click.echo("[INFO] Starting PostgreSQL...")
        result = self._run(["brew", "services", "start", "postgresql@16"])
        if result.returncode != 0:
            click.echo(f"[ERROR] Failed to start PostgreSQL: {result.stderr}")
            return False

        # Wait for it to be ready
        for _ in range(30):
            if self._check_postgres_ready():
                click.echo(f"[OK] PostgreSQL started on port {self.POSTGRES_PORT}")
                return True
            time.sleep(1)

        click.echo("[ERROR] PostgreSQL started but not responding")
        return False

    def _start_redis(self) -> bool:
        """Start Redis via brew services."""
        if self._service_running("redis"):
            click.echo(f"[OK] Redis already running on port {self.REDIS_PORT}")
            return True

        click.echo("[INFO] Starting Redis...")
        result = self._run(["brew", "services", "start", "redis"])
        if result.returncode != 0:
            click.echo(f"[ERROR] Failed to start Redis: {result.stderr}")
            return False

        # Wait for it to be ready
        for _ in range(10):
            if self._check_redis_ready():
                click.echo(f"[OK] Redis started on port {self.REDIS_PORT}")
                return True
            time.sleep(0.5)

        click.echo("[ERROR] Redis started but not responding")
        return False

    def stop(self) -> bool:
        """Stop PostgreSQL and Redis services."""
        click.echo("[INFO] Stopping native infrastructure...")

        self._run(["brew", "services", "stop", "postgresql@16"])
        self._run(["brew", "services", "stop", "redis"])

        click.echo("[OK] Native infrastructure stopped")
        return True

    def restart(self) -> bool:
        """Restart infrastructure services."""
        self.stop()
        time.sleep(1)
        return self.start()

    # =========================================================================
    # STATUS / HEALTH CHECKS
    # =========================================================================

    def _check_postgres_ready(self) -> bool:
        """Check if PostgreSQL is accepting connections."""
        pg_isready = str(self.pg_bin_path / "pg_isready")
        result = self._run([pg_isready, "-p", str(self.POSTGRES_PORT)])
        return result.returncode == 0

    def _check_redis_ready(self) -> bool:
        """Check if Redis is responding."""
        redis_cli = str(self.redis_bin_path / "redis-cli")
        result = self._run([redis_cli, "-p", str(self.REDIS_PORT), "ping"])
        return result.returncode == 0 and "PONG" in result.stdout

    def status(self) -> Dict[str, Dict]:
        """Get status of infrastructure services."""
        return {
            "postgresql": {
                "running": self._service_running("postgresql@16"),
                "ready": self._check_postgres_ready(),
                "port": self.POSTGRES_PORT,
                "type": "native (brew)",
            },
            "redis": {
                "running": self._service_running("redis"),
                "ready": self._check_redis_ready(),
                "port": self.REDIS_PORT,
                "type": "native (brew)",
            },
        }

    def _print_status(self):
        """Print current status."""
        status = self.status()
        click.echo("")
        click.echo("  PostgreSQL:")
        click.echo(f"    Port: {self.POSTGRES_PORT}")
        click.echo(f"    User: {self.POSTGRES_USER}")
        click.echo(f"    Status: {'ready' if status['postgresql']['ready'] else 'not ready'}")
        click.echo("")
        click.echo("  Redis:")
        click.echo(f"    Port: {self.REDIS_PORT}")
        click.echo(f"    Status: {'ready' if status['redis']['ready'] else 'not ready'}")

    # =========================================================================
    # DATABASE MANAGEMENT
    # =========================================================================

    def create_database(self, project: str) -> bool:
        """Create a database for a project."""
        psql = str(self.pg_bin_path / "psql")
        
        if project not in self.PROJECT_IDS:
            click.echo(f"[ERROR] Unknown project: {project}")
            return False

        # Check if database exists
        result = self._run([
            psql, "-p", str(self.POSTGRES_PORT), "-U", self.POSTGRES_USER, "-d", "postgres", "-tAc",
            f"SELECT 1 FROM pg_database WHERE datname='{project}'"
        ])

        if "1" in result.stdout:
            click.echo(f"[OK] Database '{project}' already exists")
            return True

        # Create database
        click.echo(f"[INFO] Creating database '{project}'...")
        result = self._run([
            psql, "-p", str(self.POSTGRES_PORT), "-U", self.POSTGRES_USER, "-d", "postgres", "-c",
            f"CREATE DATABASE {project} OWNER {self.POSTGRES_USER};"
        ])

        if result.returncode == 0:
            # Add common extensions
            self._run([
                psql, "-p", str(self.POSTGRES_PORT), "-U", self.POSTGRES_USER, "-d", project, "-c",
                "CREATE EXTENSION IF NOT EXISTS \"uuid-ossp\"; CREATE EXTENSION IF NOT EXISTS \"pgcrypto\";"
            ])
            click.echo(f"[OK] Database '{project}' created")
            return True
        else:
            click.echo(f"[ERROR] Failed to create database: {result.stderr}")
            return False

    def create_all_databases(self) -> bool:
        """Create databases for all known projects."""
        click.echo("[INFO] Creating databases for all projects...")
        for project in self.PROJECT_IDS.keys():
            self.create_database(project)
        click.echo("[OK] All databases created")
        return True

    def list_databases(self):
        """List all databases."""
        psql = str(self.pg_bin_path / "psql")
        result = self._run([
            psql, "-p", str(self.POSTGRES_PORT), "-U", self.POSTGRES_USER, "-d", "postgres", "-c", "\\l"
        ])
        click.echo(result.stdout)

    # =========================================================================
    # ENVIRONMENT VARIABLES
    # =========================================================================

    def get_env_vars(self, project: str) -> Dict[str, str]:
        """Get environment variables for a project to connect to shared infra.
        
        Args:
            project: Project name
            
        Returns:
            Dict of environment variables
        """
        project_id = self.PROJECT_IDS.get(project, 0)
        redis_db = project_id  # Each project gets its own Redis DB number

        return {
            # PostgreSQL
            "POSTGRES_HOST": "localhost",
            "POSTGRES_PORT": str(self.POSTGRES_PORT),
            "POSTGRES_USER": self.POSTGRES_USER,
            "POSTGRES_PASSWORD": self.POSTGRES_PASSWORD,
            "POSTGRES_DB": project,
            "DATABASE_URL": f"postgresql://{self.POSTGRES_USER}:{self.POSTGRES_PASSWORD}@localhost:{self.POSTGRES_PORT}/{project}",
            
            # Redis (each project gets its own DB number 0-15)
            "REDIS_HOST": "localhost",
            "REDIS_PORT": str(self.REDIS_PORT),
            "REDIS_URL": f"redis://localhost:{self.REDIS_PORT}/{redis_db}",
            "REDIS_DB": str(redis_db),
            
            # API port for this project
            "API_PORT": str(8000 + project_id),
            "FRONTEND_PORT": str(3000 + project_id),
            
            # Development mode
            "ENVIRONMENT": "development",
            "DEBUG": "true",
            
            # Telemetry backend (if running)
            "TIFFANY_HOST": "localhost",
            "TIFFANY_PORT": "3308",
            "TELEMETRY_ENABLED": "false",  # Disable by default in dev
        }

    def print_env_vars(self, project: str):
        """Print environment variables for a project."""
        env_vars = self.get_env_vars(project)
        click.echo(f"\n[INFO] Environment variables for {project}:\n")
        for key, value in env_vars.items():
            click.echo(f"export {key}=\"{value}\"")

    # =========================================================================
    # BACKEND RUNNER
    # =========================================================================

    def run_backend(self, project: str, port: Optional[int] = None) -> None:
        """Run a project backend directly with Python.
        
        Args:
            project: Project name
            port: Override port (default: 8000 + project_id)
        """
        if project not in self.PROJECT_IDS:
            click.echo(f"[ERROR] Unknown project: {project}")
            return

        project_id = self.PROJECT_IDS[project]
        api_port = port or (8000 + project_id)
        backend_dir = self.fleet_root / project / "backend"

        if not backend_dir.exists():
            click.echo(f"[ERROR] Backend directory not found: {backend_dir}")
            return

        # Ensure database exists
        self.create_database(project)

        # Get environment variables
        env_vars = self.get_env_vars(project)
        env_vars["API_PORT"] = str(api_port)

        # Build environment
        import os
        env = os.environ.copy()
        env.update(env_vars)

        # Activate venv if it exists
        venv_python = self.venv_path / "bin" / "python"
        if venv_python.exists():
            python_cmd = str(venv_python)
            click.echo(f"[INFO] Using shared venv: {self.venv_path}")
        else:
            python_cmd = "python3"
            click.echo("[WARNING] Shared venv not found, using system Python")

        # Determine the module to run - check various common patterns
        main_py = backend_dir / "main.py"
        project_main = backend_dir / project / "main.py"
        project_core_main = backend_dir / project / "core" / "main.py"
        app_py = backend_dir / "app.py"

        if main_py.exists():
            module = "main:app"
        elif project_main.exists():
            module = f"{project}.main:app"
        elif project_core_main.exists():
            module = f"{project}.core.main:app"
        elif app_py.exists():
            module = "app:app"
        else:
            click.echo(f"[ERROR] Could not find main.py in {backend_dir}")
            return

        click.echo(f"[INFO] Starting {project} backend on port {api_port}...")
        click.echo(f"[INFO] Database: {env_vars['DATABASE_URL']}")
        click.echo("")

        # Run uvicorn
        cmd = [
            python_cmd, "-m", "uvicorn",
            module,
            "--host", "0.0.0.0",
            "--port", str(api_port),
            "--reload"
        ]

        try:
            subprocess.run(cmd, cwd=str(backend_dir), env=env)
        except KeyboardInterrupt:
            click.echo("\n[INFO] Backend stopped")


# CLI interface for standalone use
@click.group()
def cli():
    """macOS Native Infrastructure Manager for FLEET development."""
    pass


@cli.command()
def setup():
    """One-time setup of PostgreSQL and Redis via Homebrew."""
    mgr = MacOSNativeInfraManager()
    mgr.setup()


@cli.command()
def start():
    """Start PostgreSQL and Redis services."""
    mgr = MacOSNativeInfraManager()
    mgr.start()


@cli.command()
def stop():
    """Stop PostgreSQL and Redis services."""
    mgr = MacOSNativeInfraManager()
    mgr.stop()


@cli.command()
def status():
    """Show status of infrastructure services."""
    mgr = MacOSNativeInfraManager()
    s = mgr.status()
    click.echo("\nInfrastructure Status:")
    for service, info in s.items():
        status_str = "running" if info["ready"] else "stopped"
        click.echo(f"  {service}: {status_str} (port {info['port']})")


@cli.command()
@click.argument("project")
def createdb(project):
    """Create database for a project."""
    mgr = MacOSNativeInfraManager()
    mgr.create_database(project)


@cli.command()
def createall():
    """Create databases for all projects."""
    mgr = MacOSNativeInfraManager()
    mgr.create_all_databases()


@cli.command()
@click.argument("project")
def env(project):
    """Print environment variables for a project."""
    mgr = MacOSNativeInfraManager()
    mgr.print_env_vars(project)


@cli.command()
@click.argument("project")
@click.option("--port", "-p", type=int, help="Override API port")
def run(project, port):
    """Run a project backend directly."""
    mgr = MacOSNativeInfraManager()
    mgr.run_backend(project, port)


if __name__ == "__main__":
    cli()
