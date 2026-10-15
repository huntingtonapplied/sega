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
SEGA Native Infrastructure Manager
==============================================================================
File: sega/local/native_infra.py
Project: SEGA (Scalable Engineering & Growth Automation)
Copyright: 2025 SEGA Contributors
License: Apache-2.0

PURPOSE: Manage infrastructure for --shared development mode using FLEET port standards

Port Allocation Standards (from sega.toml):
- database_port = 5000 + project_id
- redis_port = 6000 + project_id

Infrastructure Strategy:
- Redis: Native redis-server (can bind to any port)
- PostgreSQL: Docker container with TimescaleDB (FLEET standard port)

This provides fast startup while maintaining FLEET port standards compliance.
==============================================================================
"""

import subprocess
import os
import time
import sys
from pathlib import Path
from typing import Dict, Optional, Tuple
import click


class NativeInfrastructureManager:
    """Manages infrastructure for --shared development mode.

    Uses FLEET port allocation standards:
    - PostgreSQL: Docker container on 5000 + project_id (e.g., 5009 for Atlas)
    - Redis: Native redis-server on 6000 + project_id (e.g., 6009 for Atlas)

    Directory structure:
    ~/fleet/environments/infrastructure/
    ├── redis/
    │   ├── run/     # PID files
    │   ├── data/    # Persistence
    │   └── logs/    # Log files
    ├── postgres/
    │   └── data/    # PostgreSQL data (Docker volume mount)
    └── config/      # Configuration templates
    """

    INFRA_DIR = Path.home() / "fleet" / "environments" / "infrastructure"

    # Project IDs sourced from config (name -> id).
    # Port formulas: postgres = 5000 + id, redis = 6000 + id
    from sega.core.config import get_config as _get_config

    PROJECT_IDS = {name: proj.id for name, proj in _get_config().projects.items()}
    del _get_config

    def __init__(self, project: Optional[str] = None, port_offset: int = 0):
        """Initialize infrastructure manager.

        Args:
            project: Project name (for port allocation from sega.toml)
            port_offset: Additional port offset for running multiple instances
        """
        self.project = project
        self.port_offset = port_offset
        self.ports = self._get_project_ports()
        self._ensure_directories()

    def _get_project_ports(self) -> Dict[str, int]:
        """Get FLEET-assigned ports for project per PORT_ALLOCATION_STANDARDS.md."""
        if self.project:
            project_id = self.PROJECT_IDS.get(self.project, 0)
        else:
            project_id = 0
        offset = project_id + self.port_offset

        # FLEET port formulas from sega.toml
        return {
            'postgres': 5000 + offset,  # FLEET standard: 5000 + project_id
            'redis': 6000 + offset,      # FLEET standard: 6000 + project_id
            'api': 8000 + offset,
            'frontend': 3000 + offset,
        }

    def _ensure_directories(self):
        """Create infrastructure directories if they don't exist."""
        dirs = [
            self.INFRA_DIR / "redis" / "run",
            self.INFRA_DIR / "redis" / "data",
            self.INFRA_DIR / "redis" / "logs",
            self.INFRA_DIR / "postgres" / "data",
            self.INFRA_DIR / "postgres" / "initdb",
            self.INFRA_DIR / "config",
        ]
        for d in dirs:
            d.mkdir(parents=True, exist_ok=True)

    def start(self, profile: str = "development", with_tools: bool = False) -> bool:
        """Start shared infrastructure using FLEET port standards.

        Args:
            profile: Configuration profile (unused, for API compatibility)
            with_tools: Start management tools (unused for native mode)

        Returns:
            True if all services started successfully
        """
        click.echo("[INFO] Starting shared infrastructure (FLEET port standards)...")

        redis_ok = self.start_redis()
        postgres_ok = self.start_postgres()

        if redis_ok and postgres_ok:
            click.echo("[OK] Shared infrastructure ready")
            self._print_ports()
            return True
        else:
            if not redis_ok:
                click.echo("[ERROR] Redis failed to start")
            if not postgres_ok:
                click.echo("[ERROR] PostgreSQL failed to start")
            return False

    def _print_ports(self):
        """Print the ports being used."""
        click.echo(f"     PostgreSQL: localhost:{self.ports['postgres']}")
        click.echo(f"     Redis:      localhost:{self.ports['redis']}")

    def start_redis(self) -> bool:
        """Start Redis on project's FLEET port."""
        port = self.ports['redis']
        pid_file = self.INFRA_DIR / "redis" / "run" / f"redis-{port}.pid"
        log_file = self.INFRA_DIR / "redis" / "logs" / f"redis-{port}.log"
        data_dir = self.INFRA_DIR / "redis" / "data"

        # Check if already running on this port
        if self._check_redis_running(port):
            click.echo(f"[OK] Redis already running on port {port}")
            return True

        # Clean up stale PID file if exists
        if pid_file.exists():
            pid_file.unlink()

        # Start Redis
        cmd = [
            "redis-server",
            "--port", str(port),
            "--daemonize", "yes",
            "--pidfile", str(pid_file),
            "--logfile", str(log_file),
            "--dir", str(data_dir),
        ]

        try:
            result = subprocess.run(cmd, capture_output=True, text=True)
            if result.returncode == 0:
                # Wait a moment for Redis to start
                time.sleep(0.5)
                if self._check_redis_running(port):
                    click.echo(f"[OK] Redis started on port {port}")
                    return True
                else:
                    click.echo(f"[ERROR] Redis started but not responding on port {port}")
                    return False
            else:
                click.echo(f"[ERROR] Failed to start Redis: {result.stderr}")
                return False
        except FileNotFoundError:
            if sys.platform == "darwin":
                click.echo("[ERROR] redis-server not found. Install with: brew install redis")
            else:
                click.echo("[ERROR] redis-server not found. Install with: sudo apt install redis-server")
            return False

    def _check_redis_running(self, port: int) -> bool:
        """Check if Redis is running on specified port."""
        try:
            result = subprocess.run(
                ["redis-cli", "-p", str(port), "ping"],
                capture_output=True,
                text=True,
                timeout=5
            )
            return result.returncode == 0 and "PONG" in result.stdout
        except (subprocess.TimeoutExpired, FileNotFoundError):
            return False

    def start_postgres(self) -> bool:
        """Start PostgreSQL/TimescaleDB via Docker on FLEET port.

        Uses Docker to run TimescaleDB on the project's FLEET-assigned port.
        Container name: {project}-db-shared (e.g., atlas-db-shared)
        """
        port = self.ports['postgres']
        db_name = self.project or "postgres"
        container_name = f"{db_name}-db-shared"

        # Check if already running
        if self._check_postgres_running(port):
            click.echo(f"[OK] PostgreSQL already running on port {port}")
            return True

        # Check if container exists but is stopped
        result = subprocess.run(
            ["docker", "ps", "-a", "--filter", f"name={container_name}", "--format", "{{.Names}}"],
            capture_output=True,
            text=True
        )

        if container_name in result.stdout:
            # Start existing container
            click.echo(f"[INFO] Starting existing PostgreSQL container...")
            result = subprocess.run(
                ["docker", "start", container_name],
                capture_output=True,
                text=True
            )
            if result.returncode == 0:
                time.sleep(2)  # Wait for PostgreSQL to be ready
                if self._check_postgres_running(port):
                    click.echo(f"[OK] PostgreSQL started on port {port}")
                    return True

        # Create and start new container
        click.echo(f"[INFO] Creating PostgreSQL container on port {port}...")

        # Get initdb path from project if it exists
        project_root = Path.home() / "fleet" / db_name
        initdb_path = project_root / "backend" / "apps" / "db-model" / "initdb"
        initdb_mount = []
        if initdb_path.exists():
            initdb_mount = ["-v", f"{initdb_path}:/docker-entrypoint-initdb.d:ro"]

        cmd = [
            "docker", "run", "-d",
            "--name", container_name,
            "-p", f"{port}:{port}",
            "-e", f"POSTGRES_USER={db_name}",
            "-e", f"POSTGRES_PASSWORD={db_name}",
            "-e", f"POSTGRES_DB={db_name}",
            "-e", f"PGPORT={port}",
            *initdb_mount,
            "--restart", "unless-stopped",
            "timescale/timescaledb:latest-pg15"
        ]

        try:
            result = subprocess.run(cmd, capture_output=True, text=True)
            if result.returncode != 0:
                click.echo(f"[ERROR] Failed to start PostgreSQL: {result.stderr}")
                return False

            # Wait for PostgreSQL to be ready
            click.echo("[INFO] Waiting for PostgreSQL to be ready...")
            for i in range(30):  # Wait up to 30 seconds
                time.sleep(1)
                if self._check_postgres_running(port):
                    click.echo(f"[OK] PostgreSQL started on port {port}")
                    return True

            click.echo("[ERROR] PostgreSQL container started but not responding")
            return False

        except FileNotFoundError:
            click.echo("[ERROR] Docker not found. Install Docker to use shared mode.")
            return False
        except Exception as e:
            click.echo(f"[ERROR] Failed to start PostgreSQL: {e}")
            return False

    def _check_postgres_running(self, port: int) -> bool:
        """Check if PostgreSQL is running on specified port."""
        try:
            result = subprocess.run(
                ["pg_isready", "-h", "localhost", "-p", str(port)],
                capture_output=True,
                text=True,
                timeout=5
            )
            return result.returncode == 0
        except subprocess.TimeoutExpired:
            return False
        except FileNotFoundError:
            # Fallback when postgres client tools are not installed.
            # A TCP connect isn't a full readiness check, but avoids false negatives.
            import socket

            try:
                with socket.create_connection(("localhost", port), timeout=1.0):
                    return True
            except OSError:
                return False

    def stop_postgres(self) -> bool:
        """Stop PostgreSQL container for this project."""
        db_name = self.project or "postgres"
        container_name = f"{db_name}-db-shared"

        try:
            result = subprocess.run(
                ["docker", "stop", container_name],
                capture_output=True,
                text=True,
                timeout=30
            )
            if result.returncode == 0:
                click.echo(f"[OK] PostgreSQL stopped ({container_name})")
                return True
            else:
                click.echo(f"[INFO] PostgreSQL container not running")
                return True
        except Exception as e:
            click.echo(f"[ERROR] Failed to stop PostgreSQL: {e}")
            return False

    def stop(self) -> bool:
        """Stop shared infrastructure for this project."""
        redis_ok = self.stop_redis()
        postgres_ok = self.stop_postgres()
        return redis_ok and postgres_ok

    def stop_redis(self) -> bool:
        """Stop Redis for this project's port."""
        port = self.ports['redis']
        pid_file = self.INFRA_DIR / "redis" / "run" / f"redis-{port}.pid"

        if not self._check_redis_running(port):
            click.echo(f"[INFO] Redis not running on port {port}")
            return True

        try:
            # Try graceful shutdown first
            result = subprocess.run(
                ["redis-cli", "-p", str(port), "shutdown"],
                capture_output=True,
                text=True,
                timeout=10
            )

            # Clean up PID file
            if pid_file.exists():
                pid_file.unlink()

            click.echo(f"[OK] Redis stopped (port {port})")
            return True

        except subprocess.TimeoutExpired:
            # Force kill if graceful shutdown fails
            if pid_file.exists():
                try:
                    pid = int(pid_file.read_text().strip())
                    subprocess.run(["kill", "-9", str(pid)], capture_output=True)
                    pid_file.unlink()
                except (ValueError, ProcessLookupError):
                    pass
            return True
        except Exception as e:
            click.echo(f"[ERROR] Failed to stop Redis: {e}")
            return False

    def status(self) -> Dict[str, Dict]:
        """Get status of shared infrastructure."""
        redis_port = self.ports['redis']
        postgres_port = self.ports['postgres']

        return {
            'redis': {
                'status': 'running' if self._check_redis_running(redis_port) else 'stopped',
                'port': redis_port,
                'type': 'native',
            },
            'postgres': {
                'status': 'running' if self._check_postgres_running(postgres_port) else 'stopped',
                'port': postgres_port,
                'database': self.project or 'postgres',
                'type': 'docker',
                'container': f"{self.project or 'postgres'}-db-shared",
            }
        }

    def get_env_vars(self) -> Dict[str, str]:
        """Get environment variables for shared infrastructure.

        Returns dict of env vars that should be set for the application
        to connect to shared infrastructure using FLEET port standards.
        """
        redis_port = self.ports['redis']
        postgres_port = self.ports['postgres']
        db_name = self.project or "postgres"
        # Docker container uses project name as user/password
        db_user = db_name
        db_pass = db_name

        return {
            'POSTGRES_HOST': 'localhost',
            'POSTGRES_PORT': str(postgres_port),
            'POSTGRES_USER': db_user,
            'POSTGRES_PASSWORD': db_pass,
            'POSTGRES_DB': db_name,
            'DATABASE_URL': f'postgresql://{db_user}:{db_pass}@localhost:{postgres_port}/{db_name}',
            'POSTGRESQL_URL': f'postgresql://{db_user}:{db_pass}@localhost:{postgres_port}/{db_name}',
            'TIMESCALEDB_URL': f'postgresql://{db_user}:{db_pass}@localhost:{postgres_port}/{db_name}',
            'REDIS_HOST': 'localhost',
            'REDIS_PORT': str(redis_port),
            'REDIS_URL': f'redis://localhost:{redis_port}/0',
            'CELERY_BROKER_URL': f'redis://localhost:{redis_port}/0',
        }
