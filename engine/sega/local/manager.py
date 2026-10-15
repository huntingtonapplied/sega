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
SEGA Local Deployment Manager
==============================================================================
File: src/sega/deployment/local_deployment_manager.py
Project: SEGA (Scalable Engineering & Growth Automation)
Copyright: 2022-2025 SEGA Contributors
License: Apache-2.0

SEGA MODULE: Deployment/LocalDeploymentManager
COMPONENT: Local Development Deployment Orchestrator
PURPOSE: Manage local development deployments for any workspace
==============================================================================
"""

import os
import subprocess
import yaml
from pathlib import Path
from typing import List, Dict, Optional, Any
import click
import docker
from docker.errors import DockerException, NotFound
import time


class LocalDeploymentManager:
    """Manages local development deployments for any workspace."""

    def __init__(self, workspace_root: Optional[Path] = None, config_file: Optional[Path] = None):
        """Initialize the local deployment manager.

        Args:
            workspace_root: Root directory of workspace
            config_file: Path to SEGA configuration file
        """
        self.workspace_root = workspace_root or Path.cwd()
        self.config_file = config_file or self._find_config_file()
        self.config = self._load_config()

        # Auto-detect if we're in a project directory
        self.current_project = self._detect_current_project()
        if self.current_project:
            # Adjust workspace root if we're inside a project
            if self.workspace_root.name == self.current_project:
                self.workspace_root = self.workspace_root.parent

        # Extract configuration values
        self.compose_project_prefix = self.config.get("workspace", {}).get("compose_project_prefix", "sega")
        self.docker_client = None
        self._init_docker_client()

        # Detect docker-compose command (V1 vs V2)
        self.compose_command = self._detect_compose_command()

    def _find_config_file(self) -> Optional[Path]:
        """Find SEGA configuration file in workspace.

        Searches for .sega.yml or sega.yml in:
        1. Current directory
        2. Workspace root
        3. Parent directories up to home

        Returns:
            Path to config file or None
        """
        config_names = [".sega.yml", "sega.yml", ".sega.yaml", "sega.yaml"]

        # Search in current directory and up
        search_dir = self.workspace_root
        while search_dir != search_dir.parent:
            for name in config_names:
                config_path = search_dir / name
                if config_path.exists():
                    return config_path
            search_dir = search_dir.parent

        return None

    def _load_config(self) -> Dict[str, Any]:
        """Load configuration from file or use defaults.

        Returns:
            Configuration dictionary
        """
        if self.config_file and self.config_file.exists():
            with open(self.config_file, "r") as f:
                config = yaml.safe_load(f) or {}

            # Update workspace root if specified in config
            if "workspace" in config and "root" in config["workspace"]:
                config_root = Path(config["workspace"]["root"])
                if config_root.is_absolute():
                    self.workspace_root = config_root
                else:
                    # Relative to config file location
                    self.workspace_root = (self.config_file.parent / config_root).resolve()

            return config
        else:
            # Default configuration
            return {
                "workspace": {"name": "Local Workspace", "compose_project_prefix": "sega"},
                "project_discovery": {
                    "scan_paths": ["."],
                    "exclude_paths": [".git", "node_modules", "__pycache__", "_internal", "_docs"],
                    "project_markers": ["docker-compose.yml", "docker-compose.dev.yml"],
                    "compose_file_patterns": [
                        "docker-compose.dev.yml",
                        "docker-compose.yml",
                        "deployment/docker-compose.yml",
                    ],
                },
                "environment_defaults": {"NODE_ENV": "development", "ENV": "development", "ENVIRONMENT": "development"},
                "deployment": {
                    "prefer_makefile": True,
                    "makefile_targets": {
                        "up": ["up", "start", "dev"],
                        "down": ["down", "stop"],
                        "restart": ["restart"],
                    },
                    "health_check": {"enabled": True, "timeout": 30, "interval": 2},
                },
            }

    def _init_docker_client(self):
        """Initialize Docker client."""
        try:
            self.docker_client = docker.from_env()
            self.docker_client.ping()
        except DockerException as e:
            click.echo(f"[WARNING] Docker initialization failed: {e}", err=True)
            self.docker_client = None

    def _detect_compose_command(self) -> List[str]:
        """Detect which docker-compose command to use (V1 or V2).

        Returns:
            List with compose command: ['docker-compose'] or ['docker', 'compose']
        """
        # Try docker-compose (V1) first
        try:
            result = subprocess.run(["docker-compose", "--version"], capture_output=True, text=True, timeout=5)
            if result.returncode == 0:
                return ["docker-compose"]
        except (FileNotFoundError, subprocess.TimeoutExpired):
            pass

        # Try docker compose (V2)
        try:
            result = subprocess.run(["docker", "compose", "version"], capture_output=True, text=True, timeout=5)
            if result.returncode == 0:
                return ["docker", "compose"]
        except (FileNotFoundError, subprocess.TimeoutExpired):
            pass

        # Default to V2 (will fail with helpful error later)
        return ["docker", "compose"]

    def _detect_current_project(self) -> Optional[str]:
        """Detect if current directory is a project directory.

        Returns:
            Project name if detected, None otherwise
        """
        # Check if we have a .sega.yml or sega.yaml in current directory
        cwd = Path.cwd()
        config_names = [".sega.yml", "sega.yml", ".sega.yaml", "sega.yaml"]
        has_config_in_cwd = any((cwd / name).exists() for name in config_names)

        if has_config_in_cwd:
            # Try to extract project name from config
            project_name = self.config.get("project", {}).get("name")
            if project_name and project_name != "unknown":
                return project_name

            # Use current directory name as fallback
            cwd_name = cwd.name

            # Don't use 'fleet' as a project name (that's the workspace root)
            if cwd_name != "fleet" and cwd_name != "sega":
                return cwd_name

        return None

    def get_projects_with_compose(self) -> List[str]:
        """Get all projects that have docker-compose configuration."""
        projects = []

        # Get configuration
        discovery_config = self.config.get("project_discovery", {})
        scan_paths = discovery_config.get("scan_paths", ["."])
        exclude_paths = set(discovery_config.get("exclude_paths", []))
        project_markers = discovery_config.get("project_markers", ["docker-compose.yml"])

        # Scan for projects
        for scan_path in scan_paths:
            scan_dir = self.workspace_root / scan_path
            if not scan_dir.exists():
                continue

            for project_dir in scan_dir.iterdir():
                if not project_dir.is_dir():
                    continue

                # Skip excluded directories
                if project_dir.name.startswith(".") or project_dir.name in exclude_paths:
                    continue

                # Check for project markers
                has_marker = False
                for marker in project_markers:
                    if "/" in marker:
                        # Handle nested markers like "deployment/docker-compose.yml"
                        marker_path = project_dir / marker
                    else:
                        # Simple file marker
                        marker_path = project_dir / marker

                    if marker_path.exists():
                        has_marker = True
                        break

                if has_marker:
                    projects.append(project_dir.name)

        return sorted(projects)

    def get_project_config(self, project: str) -> Dict[str, Any]:
        """Get configuration for a specific project.

        Args:
            project: Project name

        Returns:
            Project configuration dictionary
        """
        # Check if project has specific configuration
        project_configs = self.config.get("projects", {})
        if project in project_configs:
            return project_configs[project]

        # Return default configuration
        return {
            "has_makefile": (self.workspace_root / project / "Makefile").exists(),
            "compose_file": self._find_compose_file(project),
        }

    def _find_compose_file(self, project: str) -> str:
        """Find the compose file for a project.

        Args:
            project: Project name

        Returns:
            Relative path to compose file
        """
        project_dir = self.workspace_root / project
        patterns = self.config.get("project_discovery", {}).get("compose_file_patterns", [])

        for pattern in patterns:
            # Replace {project} placeholder
            pattern = pattern.replace("{project}", project)

            compose_path = project_dir / pattern
            if compose_path.exists():
                return pattern

        # Default
        return "docker-compose.yml"

    def create_env_file(self, project: str) -> bool:
        """Create environment file for a project if it doesn't exist.

        Args:
            project: Project name

        Returns:
            True if env file was created or already exists
        """
        project_dir = self.workspace_root / project
        env_file = project_dir / ".env"

        if env_file.exists():
            return True

        # Get environment defaults
        env_defaults = self.config.get("environment_defaults", {})
        project_config = self.get_project_config(project)
        project_env = project_config.get("environment", {})

        # Check for template
        env_example = project_dir / ".env.example"
        if env_example.exists():
            env_content = env_example.read_text()
            # Apply defaults
            for key, value in env_defaults.items():
                if f"{key}=" not in env_content:
                    env_content += f"\n{key}={value}"
        else:
            # Create minimal development env
            env_lines = [f"# Auto-generated environment file for {project}"]

            # Add defaults
            for key, value in env_defaults.items():
                env_lines.append(f"{key}={value}")

            # Add project-specific environment
            for key, value in project_env.items():
                env_lines.append(f"{key}={value}")

            # Add database configuration if infrastructure is configured
            infra_config = self.config.get("infrastructure", {})
            if infra_config:
                dev_profile = infra_config.get("profiles", {}).get("development", {})
                if "postgres" in dev_profile:
                    pg = dev_profile["postgres"]
                    env_lines.extend(
                        [
                            f"DATABASE_HOST={self.compose_project_prefix}_dev_postgres",
                            "DATABASE_PORT=5432",
                            f"DATABASE_NAME={project}_dev",
                            f"DATABASE_USER={pg.get('user', 'postgres')}",
                            f"DATABASE_PASSWORD={pg.get('password', 'dev_password')}",
                        ]
                    )
                if "redis" in dev_profile:
                    env_lines.extend([f"REDIS_HOST={self.compose_project_prefix}_dev_redis", "REDIS_PORT=6379"])

            env_content = "\n".join(env_lines)

        env_file.write_text(env_content)
        click.echo(f"  [OK] Created .env file for {project}")
        return True

    def get_compose_command(self, project: str, command: str, *args) -> List[str]:
        """Build docker-compose command for a project.

        Args:
            project: Project name
            command: Docker-compose command
            *args: Additional arguments

        Returns:
            Command list for subprocess
        """
        project_dir = self.workspace_root / project
        config = self.get_project_config(project)

        # Find compose file
        compose_file = config.get("compose_file", "docker-compose.yml")
        compose_path = project_dir / compose_file

        # Build command using detected compose command
        cmd = self.compose_command.copy()  # ['docker-compose'] or ['docker', 'compose']
        cmd.extend(["-f", str(compose_path), "-p", f"{self.compose_project_prefix}_{project}", command])
        cmd.extend(args)

        return cmd

    def ensure_shared_venv(self) -> bool:
        """Ensure shared virtual environment exists if configured.

        Returns:
            True if shared venv is ready or not configured
        """
        dev_config = self.config.get("development", {})
        venv_config = dev_config.get("shared_venv", {})

        if not venv_config:
            # No shared venv configured
            return True

        venv_path = self.workspace_root / venv_config.get("path", "")
        if not venv_path or venv_path == self.workspace_root:
            return True

        if not venv_path.exists():
            click.echo("[WARNING] Shared virtual environment not found")

            # Check for setup script
            setup_script = venv_config.get("setup_script")
            if setup_script:
                setup_path = self.workspace_root / setup_script
                if setup_path.exists():
                    click.echo("Creating shared environment...")
                    try:
                        subprocess.run(["bash", str(setup_path)], check=True)
                        click.echo("[OK] Shared environment created")
                    except subprocess.CalledProcessError as e:
                        click.echo(f"[ERROR] Failed to create shared environment: {e}")
                        return False

        return venv_path.exists()

    def start_shared_infrastructure(self) -> bool:
        """Start shared infrastructure services if configured.

        Returns:
            True if infrastructure started successfully or not configured
        """
        infra_config = self.config.get("infrastructure", {})
        if not infra_config:
            # No infrastructure configured
            return True

        compose_file = infra_config.get("compose_file")
        if not compose_file:
            return True

        infra_compose = self.workspace_root / compose_file

        if not infra_compose.exists():
            click.echo(f"[WARNING] Infrastructure compose file not found: {compose_file}")
            return False

        click.echo("[INFO] Starting shared infrastructure...")

        cmd = [
            "docker-compose",
            "-f",
            str(infra_compose),
            "-p",
            f"{self.compose_project_prefix}_infra",
            "--profile",
            "development",
            "up",
            "-d",
        ]

        env = os.environ.copy()
        env["COMPOSE_PROJECT_NAME"] = f"{self.compose_project_prefix}_infra"

        try:
            result = subprocess.run(cmd, env=env, capture_output=True, text=True)
            if result.returncode == 0:
                click.echo("[OK] Shared infrastructure started")
                # Wait for services to be healthy
                if self.config.get("deployment", {}).get("health_check", {}).get("enabled", True):
                    self._wait_for_infrastructure_health()
                return True
            else:
                click.echo(f"[ERROR] Failed to start infrastructure: {result.stderr}")
                return False
        except Exception as e:
            click.echo(f"[ERROR] Error starting infrastructure: {e}")
            return False

    def _wait_for_infrastructure_health(self, timeout: Optional[int] = None):
        """Wait for infrastructure services to be healthy.

        Args:
            timeout: Maximum seconds to wait
        """
        if not self.docker_client:
            return

        health_config = self.config.get("deployment", {}).get("health_check", {})
        timeout = timeout or health_config.get("timeout", 30)
        interval = health_config.get("interval", 2)

        click.echo("[INFO] Waiting for infrastructure services to be healthy...")

        # Build list of services to check from infrastructure config
        services_to_check = []
        infra_config = self.config.get("infrastructure", {})
        dev_profile = infra_config.get("profiles", {}).get("development", {})

        for service_type in ["postgres", "redis", "timescale"]:
            if service_type in dev_profile:
                container_name = f"{self.compose_project_prefix}_dev_{service_type}"
                services_to_check.append(container_name)

        if not services_to_check:
            return

        start_time = time.time()
        all_healthy = False

        while time.time() - start_time < timeout and not all_healthy:
            try:
                all_healthy = True
                for service_name in services_to_check:
                    try:
                        container = self.docker_client.containers.get(service_name)
                        health = container.attrs.get("State", {}).get("Health", {})
                        if health.get("Status") != "healthy":
                            all_healthy = False
                            break
                    except NotFound:
                        all_healthy = False
                        break

                if not all_healthy:
                    time.sleep(interval)

            except Exception:
                all_healthy = False
                time.sleep(interval)

        if all_healthy:
            click.echo("[OK] All infrastructure services are healthy")
        else:
            click.echo("[WARNING] Some services may not be fully ready")

    def deploy_project(
        self,
        project: str,
        use_makefile: Optional[bool] = None,
        env_mode: Optional[Dict[str, str]] = None,
        runtime_mode: Optional[Dict[str, str]] = None,
        port_offset: int = 0,
        infra_env_vars: Optional[Dict[str, str]] = None,
        exclude_apps: Optional[set] = None,
        project_app_excludes: Optional[Dict[str, set]] = None,
    ) -> bool:
        """Deploy a single project.

        Args:
            project: Project name
            use_makefile: Whether to use Makefile if available (None = use config)
            env_mode: Dict mapping component names to environment mode ('docker', 'shared', 'project')
            runtime_mode: Dict mapping component names to runtime ('python' or 'rust')
            port_offset: Integer offset to add to all ports (default 0)
            infra_env_vars: Infrastructure environment variables from NativeInfrastructureManager
            app_excludes: Set of app names to exclude (landing, product, frontend, backend, engine, ide)

        Returns:
            True if successful
        """
        project_dir = self.workspace_root / project
        success = True

        app_excludes = exclude_apps or set()
        runtime_mode = runtime_mode or {"backend": "python", "engine": "python"}
        if env_mode is None:
            env_mode = {"backend": "docker", "engine": "docker", "frontend": "docker", "ide": "docker"}

        click.echo(f"\n[INFO] Deploying {project}...")

        # Shared environment paths.
        #
        # NOTE on Rust: the legacy unified Cargo workspace at
        # `environments/rust_shared/` has been retired. The canonical scheme is
        # per-surface target dirs pinned via repo-relative `.cargo/config.toml`
        # in each <project>/<surface>/ (see common/TARGET_DIR_STANDARD.md).
        # The "cargo" entry below maps to the backend surface's target dir;
        # in practice `_start_rust_component(is_shared=True)` is not the
        # supported shared-Rust path anymore — engine cargo runs from the
        # project's own surface dir, where `.cargo/config.toml` already routes
        # the build output into the right shared `environments/<surface>_target/target`.
        shared_envs = {
            "backend": self.workspace_root / "environments" / "backend_venv",
            "engine": self.workspace_root / "environments" / "engine_venv",
            "frontend": self.workspace_root / "environments" / "node_modules",
            "ide": self._get_shared_ide_env_path(project),
            "cargo": self.workspace_root / "environments" / "backend_target" / "target",
        }

        # Detect which components exist in this project
        components = self._detect_project_components(project)

        started_any = False
        attempted_any = False
        for component, mode in env_mode.items():
            if component not in components:
                continue  # Skip components that don't exist in this project

            if component in app_excludes:
                click.echo(f"    [SKIP] {component}: excluded")
                continue

            attempted_any = True
            if mode == "docker":
                # Deploy this component with Docker
                status = self._deploy_component_docker(project, component, port_offset=port_offset)
                if status == "started":
                    started_any = True
                elif status == "error":
                    success = False
            elif mode == "shared":
                # Deploy using shared environment
                env_path = shared_envs.get(component)
                if component in ["backend", "engine"] and runtime_mode.get(component) == "rust":
                    env_path = shared_envs.get("cargo")
                ok = self._deploy_component_native(
                    project,
                    component,
                    env_path,
                    is_shared=True,
                    port_offset=port_offset,
                    infra_env_vars=infra_env_vars,
                    app_excludes=app_excludes,
                    runtime_mode=runtime_mode,
                )
                success = success and ok
                started_any = started_any or ok
            elif mode == "project":
                # Deploy using project-local environment
                project_env = self._get_project_env_path(project, component)
                if component in ["backend", "engine"] and runtime_mode.get(component) == "rust":
                    project_env = self._get_project_cargo_path(project, component)
                ok = self._deploy_component_native(
                    project,
                    component,
                    project_env,
                    is_shared=False,
                    port_offset=port_offset,
                    infra_env_vars=infra_env_vars,
                    app_excludes=app_excludes,
                    runtime_mode=runtime_mode,
                )
                success = success and ok
                started_any = started_any or ok

        # A project whose components were all skipped (e.g. compose service names
        # don't match backend/engine/frontend/ide or '<project>-<component>')
        # previously reported success while starting nothing. Surface that.
        if attempted_any and not started_any and success:
            click.echo(
                f"    [WARN] {project}: no components were started — the compose "
                f"file defines no service matching backend/engine/frontend/ide "
                f"(or '{project}-<component>'). Bring it up directly with "
                f"docker-compose if it uses a non-standard topology."
            )
            success = False

        return success

    def _detect_project_components(self, project: str) -> List[str]:
        """Detect which components exist in a project.

        Args:
            project: Project name

        Returns:
            List of component names that exist in the project
        """
        project_dir = self.workspace_root / project
        components = []

        # Check for backend
        if (project_dir / "backend").exists() or (project_dir / "src").exists():
            components.append("backend")

        # Check for engine
        if (project_dir / "engine").exists():
            components.append("engine")

        # Check for frontend
        if (project_dir / "frontend").exists() or (project_dir / "package.json").exists():
            components.append("frontend")

        # Check for IDE component
        if (project_dir / "ide").exists():
            components.append("ide")

        return components

    def _get_project_env_path(self, project: str, component: str) -> Path:
        """Get the project-local environment path for a component.

        Args:
            project: Project name
            component: Component name (backend, engine, frontend)

        Returns:
            Path to project-local environment
        """
        project_dir = self.workspace_root / project

        if component == "backend":
            # Check common backend venv locations
            for venv_path in ["backend/venv", "venv", ".venv", "backend/.venv"]:
                if (project_dir / venv_path).exists():
                    return project_dir / venv_path
            return project_dir / "backend" / "venv"  # Default

        elif component == "engine":
            # Check common engine venv locations
            for venv_path in ["engine/venv", "engine/.venv"]:
                if (project_dir / venv_path).exists():
                    return project_dir / venv_path
            return project_dir / "engine" / "venv"  # Default

        elif component == "ide":
            for nm_path in ["ide/node_modules", "ide/remote/node_modules", "ide/web/node_modules"]:
                if (project_dir / nm_path).exists():
                    return project_dir / nm_path
            return project_dir / "ide" / "node_modules"

        return project_dir

    def _get_project_cargo_path(self, project: str, component: str) -> Path:
        """Get the project-local Cargo workspace path for a component."""
        project_dir = self.workspace_root / project
        candidates = []
        if component in ["backend", "engine"]:
            candidates.append(project_dir / component)
        candidates.append(project_dir)

        for candidate in candidates:
            if (candidate / "Cargo.toml").exists():
                return candidate

        return project_dir

    def _get_shared_ide_env_path(self, project: str) -> Path:
        """Get shared IDE environment path for a project."""
        project_dir = self.workspace_root / project
        env_dir = self.workspace_root / "environments"
        shared_ide_env = env_dir / "ide" / "node_modules"
        if shared_ide_env.exists():
            return shared_ide_env

        if (project_dir / "ide").exists():
            return project_dir / "ide" / "node_modules"

        return shared_ide_env

    def _start_ide_component(
        self,
        project: str,
        node_modules_path: Path,
        is_shared: bool,
        port_offset: int = 0,
    ) -> bool:
        """Start IDE component using node_modules."""
        project_dir = self.workspace_root / project
        ide_dir = project_dir / "ide"

        if not ide_dir.exists():
            click.echo("    [SKIP] ide: No ide/ directory found")
            return True

        package_json = ide_dir / "package.json"
        if not package_json.exists():
            click.echo("    [SKIP] ide: No package.json found")
            return True

        if not node_modules_path.exists():
            click.echo(f"    [ERROR] ide: Environment not found at {node_modules_path}")
            return False

        ports = self._get_project_ports(project)
        ide_port = ports.get("desktop", 3300) + port_offset

        env = os.environ.copy()
        env.update(self.config.get("environment_defaults", {}))
        env["PORT"] = str(ide_port)

        if port_offset != 0:
            env["SEGA_PORT_OFFSET"] = str(port_offset)
            env["PORT_OFFSET"] = str(port_offset)

        if is_shared:
            env["NODE_PATH"] = str(node_modules_path)
            local_nm = ide_dir / "node_modules"
            if not local_nm.exists():
                try:
                    local_nm.symlink_to(node_modules_path)
                    click.echo("    [INFO] ide: Created symlink to shared node_modules")
                except Exception as e:
                    click.echo(f"    [WARNING] ide: Could not create symlink: {e}")

        build_cmd = ["npm", "run", "gulp", "--", "transpile-client-esbuild"]
        run_cmd = [
            "node",
            "./scripts/code-web.js",
            str(project_dir),
            "--host",
            "127.0.0.1",
            "--port",
            str(ide_port),
        ]

        click.echo("    [INFO] ide: Running transpile step (gulp)...")
        try:
            result = subprocess.run(build_cmd, cwd=str(ide_dir), env=env, capture_output=True, text=True)
            if result.returncode != 0:
                click.echo("    [ERROR] ide: Transpile failed")
                click.echo(f"    {result.stderr[:500]}")
                return False
        except Exception as e:
            click.echo(f"    [ERROR] ide: Failed to run transpile: {e}")
            return False

        click.echo(f"    [INFO] ide: Starting on port {ide_port}...")
        try:
            process = subprocess.Popen(
                run_cmd,
                cwd=str(ide_dir),
                env=env,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                start_new_session=True,
            )

            pid_suffix = f"_offset{port_offset}" if port_offset != 0 else ""
            pid_file = project_dir / f".ide{pid_suffix}.pid"
            pid_file.write_text(str(process.pid))

            click.echo(f"    [OK] ide started (PID: {process.pid}, port: {ide_port})")
            return True
        except Exception as e:
            click.echo(f"    [ERROR] ide: Failed to start: {e}")
            return False

    def _get_compose_services(self, project: str) -> Optional[set]:
        """Return the set of service names defined in the project's compose file.

        Parsed directly from YAML (not `docker-compose config`) so that missing
        interpolation variables do not prevent service-name discovery. Returns
        None if the compose file cannot be read/parsed. Cached per project.
        """
        if not hasattr(self, "_compose_services_cache"):
            self._compose_services_cache: Dict[str, Optional[set]] = {}
        if project in self._compose_services_cache:
            return self._compose_services_cache[project]

        services: Optional[set] = None
        try:
            config = self.get_project_config(project)
            compose_path = (
                self.workspace_root / project / config.get("compose_file", "docker-compose.yml")
            )
            with open(compose_path) as fh:
                data = yaml.safe_load(fh) or {}
            raw = data.get("services")
            if isinstance(raw, dict):
                services = set(raw.keys())
        except Exception:
            services = None

        self._compose_services_cache[project] = services
        return services

    def _resolve_compose_service(self, project: str, component: str) -> Optional[str]:
        """Map a logical component to the actual compose service name.

        Most projects name services after the component (`backend`, `engine`,
        `frontend`, `ide`). Some (e.g. orion, atlas) prefix them with the
        project name (`orion-backend`). This resolves both conventions and
        returns None only when the compose file genuinely defines no matching
        service.
        """
        services = self._get_compose_services(project)
        if not services:
            # Introspection failed — preserve legacy behavior (try literal name).
            return component
        if component in services:
            return component
        prefixed = f"{project}-{component}"
        if prefixed in services:
            return prefixed
        suffix_matches = [s for s in services if s.endswith(f"-{component}")]
        if len(suffix_matches) == 1:
            return suffix_matches[0]
        return None

    def _deploy_component_docker(self, project: str, component: str, port_offset: int = 0) -> str:
        """Deploy a single component using Docker.

        Args:
            project: Project name
            component: Component name (backend, engine, frontend)
            port_offset: Integer offset to add to all ports (default 0)

        Returns:
            "started" if the component's service was brought up, "skipped" if the
            project defines no matching compose service, or "error" on failure.
        """
        service = self._resolve_compose_service(project, component)
        if service is None:
            click.echo(f"    [SKIP] {component}: not defined in docker-compose")
            return "skipped"

        label = component if service == component else f"{component} (service: {service})"
        click.echo(f"    [INFO] {label}: Using Docker")

        # Use docker-compose with the resolved service name
        cmd = self.get_compose_command(project, "up", "-d", service)

        env = os.environ.copy()
        env.update(self.config.get("environment_defaults", {}))
        env["COMPOSE_PROJECT_NAME"] = f"{self.compose_project_prefix}_{project}"

        # Add port offset environment variables
        if port_offset != 0:
            env["SEGA_PORT_OFFSET"] = str(port_offset)
            env["PORT_OFFSET"] = str(port_offset)

        try:
            project_dir = self.workspace_root / project
            result = subprocess.run(cmd, cwd=str(project_dir), env=env, capture_output=True, text=True)

            if result.returncode == 0:
                click.echo(f"    [OK] {component} started (Docker)")
                return "started"
            # Service might not exist in compose file, that's ok
            if "no such service" in result.stderr.lower():
                click.echo(f"    [SKIP] {component}: not defined in docker-compose")
                return "skipped"
            click.echo(f"    [ERROR] {component}: {result.stderr}")
            return "error"
        except Exception as e:
            click.echo(f"    [ERROR] {component}: {e}")
            return "error"

    def _get_project_ports(self, project: str) -> Dict[str, int]:
        """Get base port allocations for a project.

        Args:
            project: Project name

        Returns:
            Dict mapping service type to base port number
        """
        # Standard port allocation pattern based on project, sourced from config.
        # API/Backend: 80XX, Frontend: 30XX, Database: 50XX, Redis: 60XX
        # AUTHORITATIVE: /docs/standards/infrastructure/PORT_ALLOCATION_STANDARDS.md
        from sega.core.config import get_config

        project_config = get_config().get_project(project)
        if project_config is None:
            # Unknown project: preserve legacy default.
            return {"api": 8000, "frontend": 3000, "database": 5432, "redis": 6379}

        ports = project_config.ports
        return {
            "api": ports.api,
            "frontend": ports.frontend,
            "database": ports.database,
            "redis": ports.redis,
        }

    def _deploy_component_native(
        self,
        project: str,
        component: str,
        env_path: Path,
        is_shared: bool,
        port_offset: int = 0,
        infra_env_vars: Optional[Dict[str, str]] = None,
        app_excludes: Optional[set] = None,
        runtime_mode: Optional[Dict[str, str]] = None,
    ) -> bool:
        """Deploy a single component using native environment (venv, node_modules, or Cargo workspace).

        Args:
            project: Project name
            component: Component name (backend, engine, frontend)
            env_path: Path to the environment (venv, node_modules, or cargo workspace)
            is_shared: Whether this is a shared environment
            port_offset: Integer offset to add to all ports (default 0)
            infra_env_vars: Infrastructure environment variables from NativeInfrastructureManager
            app_excludes: Set of app names to exclude (landing, product, frontend, backend, engine, ide)
            runtime_mode: Dict mapping component names to runtime ('python' or 'rust')

        Returns:
            True if successful
        """
        env_type = "shared" if is_shared else "project-local"
        click.echo(f"    [INFO] {component}: Using {env_type} environment")

        project_dir = self.workspace_root / project
        app_excludes = app_excludes or set()
        runtime_mode = runtime_mode or {"backend": "python", "engine": "python"}

        if component == "ide":
            if "ide" in app_excludes:
                click.echo("    [SKIP] ide: excluded")
                return True
            return self._start_ide_component(project, env_path, is_shared, port_offset=port_offset)

        # Check if environment exists
        if not env_path.exists():
            click.echo(f"    [ERROR] {component}: Environment not found at {env_path}")
            return False

        if component in ["backend", "engine"]:
            if runtime_mode.get(component) == "rust":
                return self._start_rust_component(project, env_path, is_shared, port_offset=port_offset)
            return self._start_python_component(project, component, env_path, is_shared, port_offset=port_offset)
        elif component == "frontend":
            return self._start_frontend_component(
                project,
                env_path,
                is_shared,
                port_offset=port_offset,
                app_excludes=app_excludes,
            )

        return False

    def _start_python_component(
        self,
        project: str,
        component: str,
        venv_path: Path,
        is_shared: bool,
        port_offset: int = 0,
        infra_env_vars: Optional[Dict[str, str]] = None,
    ) -> bool:
        """Start a Python component (backend or engine) using venv.

        Args:
            project: Project name
            component: Component name (backend or engine)
            venv_path: Path to the virtual environment
            is_shared: Whether this is a shared environment
            port_offset: Integer offset to add to all ports (default 0)
            infra_env_vars: Infrastructure environment variables from NativeInfrastructureManager

        Returns:
            True if successful
        """
        project_dir = self.workspace_root / project
        component_dir = project_dir / component if (project_dir / component).exists() else project_dir

        # Get Python executable from venv
        python_exe = venv_path / "bin" / "python"
        if not python_exe.exists():
            click.echo(f"    [ERROR] {component}: Python not found in venv at {python_exe}")
            return False

        # Get port for this component
        ports = self._get_project_ports(project)
        api_port = ports.get("api", 8000) + port_offset

        # Prepare environment
        env = os.environ.copy()
        env.update(self.config.get("environment_defaults", {}))
        env["VIRTUAL_ENV"] = str(venv_path)
        env["PATH"] = f"{venv_path / 'bin'}:{env.get('PATH', '')}"

        # Add port offset to environment
        if port_offset != 0:
            env["SEGA_PORT_OFFSET"] = str(port_offset)
            env["PORT_OFFSET"] = str(port_offset)

        # Load .env file if exists
        env_file = project_dir / ".env"
        if env_file.exists():
            self._load_env_file(env_file, env)

        # Apply infrastructure environment variables (DATABASE_URL, REDIS_URL, etc.)
        # These override .env file values to ensure backend connects to native infrastructure
        if infra_env_vars:
            env.update(infra_env_vars)
            click.echo(f"    [INFO] {component}: Applied infrastructure env vars (DATABASE_URL, REDIS_URL)")

        # Determine start command based on component type
        if component == "backend":
            # Try to find main module
            main_module = self._find_backend_main(project, component_dir)
            if main_module:
                cmd = [
                    str(python_exe),
                    "-m",
                    "uvicorn",
                    main_module,
                    "--host",
                    "0.0.0.0",
                    "--port",
                    str(api_port),
                    "--reload",
                ]
            else:
                click.echo(f"    [ERROR] {component}: Could not find main module")
                return False
        elif component == "engine":
            # Engine typically runs as a module
            cmd = [str(python_exe), "-m", project]

        click.echo(f"    [INFO] {component}: Starting on port {api_port}...")

        try:
            # Start process in background
            process = subprocess.Popen(
                cmd,
                cwd=str(component_dir),
                env=env,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                start_new_session=True,
            )

            # Store PID for later management (include port offset in filename for uniqueness)
            pid_suffix = f"_offset{port_offset}" if port_offset != 0 else ""
            pid_file = project_dir / f".{component}{pid_suffix}.pid"
            pid_file.write_text(str(process.pid))

            click.echo(f"    [OK] {component} started (PID: {process.pid}, port: {api_port})")
            return True

        except Exception as e:
            click.echo(f"    [ERROR] {component}: Failed to start: {e}")
            return False

    def _start_frontend_component(
        self,
        project: str,
        node_modules_path: Path,
        is_shared: bool,
        port_offset: int = 0,
        app_excludes: Optional[set] = None,
    ) -> bool:
        """Start a frontend component using node_modules.

        Args:
            project: Project name
            node_modules_path: Path to node_modules
            is_shared: Whether this is a shared environment
            port_offset: Integer offset to add to all ports (default 0)
            app_excludes: Set of app names to exclude (landing, product, frontend)

        Returns:
            True if successful
        """
        project_dir = self.workspace_root / project
        frontend_dir = project_dir / "frontend" if (project_dir / "frontend").exists() else project_dir
        app_excludes = app_excludes or set()

        if "frontend" in app_excludes:
            click.echo("    [SKIP] frontend: excluded")
            return True

        # Check for uix_split architecture (landing_app + product_app)
        product_app_dir = frontend_dir / "product_app"
        landing_app_dir = frontend_dir / "landing_app"
        has_uix_split = product_app_dir.exists() and landing_app_dir.exists()

        if has_uix_split:
            # Start both apps for uix_split architecture
            click.echo("    [INFO] frontend: Detected uix_split architecture (landing_app + product_app)")
            success = True
            if "landing" not in app_excludes:
                success = success and self._start_uix_app(
                    project, landing_app_dir, "landing", node_modules_path, is_shared, port_offset
                )
            else:
                click.echo("    [SKIP] landing_app: excluded")
            if "product" not in app_excludes:
                success = success and self._start_uix_app(
                    project, product_app_dir, "product", node_modules_path, is_shared, port_offset
                )
            else:
                click.echo("    [SKIP] product_app: excluded")
            return success

        # Single frontend app (legacy/simple architecture)
        # Check for package.json
        package_json = frontend_dir / "package.json"
        if not package_json.exists():
            click.echo(f"    [SKIP] frontend: No package.json found")
            return True

        # Get port for this component
        ports = self._get_project_ports(project)
        frontend_port = ports.get("frontend", 3000) + port_offset

        # Prepare environment
        env = os.environ.copy()
        env.update(self.config.get("environment_defaults", {}))

        # Add port to environment (many frontend tools read PORT env var)
        env["PORT"] = str(frontend_port)

        # Add port offset to environment
        if port_offset != 0:
            env["SEGA_PORT_OFFSET"] = str(port_offset)
            env["PORT_OFFSET"] = str(port_offset)

        # If using shared node_modules, set NODE_PATH
        if is_shared:
            env["NODE_PATH"] = str(node_modules_path)
            # Also need to symlink or copy node_modules if not present
            local_nm = frontend_dir / "node_modules"
            if not local_nm.exists():
                try:
                    local_nm.symlink_to(node_modules_path)
                    click.echo(f"    [INFO] frontend: Created symlink to shared node_modules")
                except Exception as e:
                    click.echo(f"    [WARNING] frontend: Could not create symlink: {e}")

        # Determine start command - use port argument if possible
        # Most dev servers support --port (vite, next, etc.)
        cmd = ["npm", "run", "dev", "--", "--port", str(frontend_port)]

        click.echo(f"    [INFO] frontend: Starting on port {frontend_port}...")

        try:
            # Start process in background
            process = subprocess.Popen(
                cmd,
                cwd=str(frontend_dir),
                env=env,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                start_new_session=True,
            )

            # Store PID for later management (include port offset in filename for uniqueness)
            pid_suffix = f"_offset{port_offset}" if port_offset != 0 else ""
            pid_file = project_dir / f".frontend{pid_suffix}.pid"
            pid_file.write_text(str(process.pid))

            click.echo(f"    [OK] frontend started (PID: {process.pid}, port: {frontend_port})")
            return True

        except Exception as e:
            click.echo(f"    [ERROR] frontend: Failed to start: {e}")
            return False

    def _start_uix_app(
        self, project: str, app_dir: Path, app_type: str, node_modules_path: Path, is_shared: bool, port_offset: int = 0
    ) -> bool:
        """Start a single app within uix_split architecture (landing or product).

        Args:
            project: Project name
            app_dir: Path to the app directory (landing_app or product_app)
            app_type: 'landing' or 'product'
            node_modules_path: Path to node_modules
            is_shared: Whether this is a shared environment
            port_offset: Integer offset to add to all ports (default 0)

        Returns:
            True if successful
        """
        project_dir = self.workspace_root / project

        # Check for package.json
        package_json = app_dir / "package.json"
        if not package_json.exists():
            click.echo(f"    [SKIP] {app_type}_app: No package.json found")
            return True

        # Get port for this app type - PORT_ALLOCATION_STANDARDS.md
        # Landing: 3000 + project_id, Product: 4000 + project_id
        ports = self._get_project_ports(project)
        if app_type == "landing":
            app_port = ports.get("frontend", 3000) + port_offset  # 3000 + project_id
        else:  # product
            # Product app uses 4000 + project_id per PORT_ALLOCATION_STANDARDS
            project_id = self._get_project_id(project)
            app_port = 4000 + project_id + port_offset

        # Prepare environment
        env = os.environ.copy()
        env.update(self.config.get("environment_defaults", {}))

        # Add port to environment
        env["PORT"] = str(app_port)

        # Add port offset to environment
        if port_offset != 0:
            env["SEGA_PORT_OFFSET"] = str(port_offset)
            env["PORT_OFFSET"] = str(port_offset)

        # If using shared node_modules, set NODE_PATH and create symlink
        if is_shared:
            env["NODE_PATH"] = str(node_modules_path)
            local_nm = app_dir / "node_modules"
            if not local_nm.exists():
                try:
                    local_nm.symlink_to(node_modules_path)
                    click.echo(f"    [INFO] {app_type}_app: Created symlink to shared node_modules")
                except Exception as e:
                    click.echo(f"    [WARNING] {app_type}_app: Could not create symlink: {e}")

        # Determine start command
        cmd = ["npm", "run", "dev", "--", "--port", str(app_port)]

        click.echo(f"    [INFO] {app_type}_app: Starting on port {app_port}...")

        try:
            # Start process in background
            process = subprocess.Popen(
                cmd,
                cwd=str(app_dir),
                env=env,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                start_new_session=True,
            )

            # Store PID for later management
            pid_suffix = f"_offset{port_offset}" if port_offset != 0 else ""
            pid_file = project_dir / f".{app_type}_app{pid_suffix}.pid"
            pid_file.write_text(str(process.pid))

            click.echo(f"    [OK] {app_type}_app started (PID: {process.pid}, port: {app_port})")
            return True

        except Exception as e:
            click.echo(f"    [ERROR] {app_type}_app: Failed to start: {e}")
            return False

    def _get_project_id(self, project: str) -> int:
        """Get the project ID from PORT_ALLOCATION_STANDARDS.

        Args:
            project: Project name

        Returns:
            Project ID (0-22)
        """
        # Source project IDs from config (formerly native_infra.PROJECT_IDS).
        from sega.core.config import get_config

        project_config = get_config().get_project(project)
        return project_config.id if project_config is not None else 0

    def _start_rust_component(self, project: str, env_path: Path, is_shared: bool, port_offset: int = 0) -> bool:
        """Start a Rust component using Cargo.

        Args:
            project: Project name
            env_path: Path to the Cargo workspace (shared) or project directory (local)
            is_shared: Whether this is using the shared Cargo workspace
            port_offset: Integer offset to add to all ports (default 0)

        Returns:
            True if successful
        """
        project_dir = self.workspace_root / project

        # Prepare environment
        env = os.environ.copy()
        env.update(self.config.get("environment_defaults", {}))

        # Add port offset to environment (Rust components read from env vars)
        if port_offset != 0:
            env["SEGA_PORT_OFFSET"] = str(port_offset)
            env["PORT_OFFSET"] = str(port_offset)
            # Also set computed ports that Rust apps might use
            ports = self._get_project_ports(project)
            env["API_PORT"] = str(ports.get("api", 8000) + port_offset)
            env["PORT"] = str(ports.get("api", 8000) + port_offset)

        # Load .env file if exists
        env_file = project_dir / ".env"
        if env_file.exists():
            self._load_env_file(env_file, env)

        if is_shared:
            # LEGACY PATH (kept for back-compat, but should not be hit on a
            # current checkout). The previous design ran cargo from a unified
            # workspace at ~/fleet/environments/rust_shared whose Cargo.toml had
            # members like "../orion/backend". That workspace has been
            # retired — each project now owns its own Cargo.toml and pins its
            # target-dir via `.cargo/config.toml` to
            # `environments/{backend,engine,cli}_target/target` (repo-relative).
            # Building from `env_path` here will fail unless callers pass a
            # real workspace directory; prefer the `is_shared=False` branch,
            # which builds from the project's own surface and gets shared
            # target output for free via the per-surface pin.
            workspace_dir = env_path

            # Find which package to run based on project name
            # Check if project has backend or engine Rust components
            rust_packages = self._find_rust_packages(project)

            if not rust_packages:
                click.echo(f"    [ERROR] rust: No Rust packages found for {project}")
                return False

            # Build and run each Rust package from the shared workspace
            for package in rust_packages:
                click.echo(f"    [INFO] rust: Building {package} from shared workspace...")

                # Build the package
                build_cmd = ["cargo", "build", "--release", "-p", package]
                try:
                    result = subprocess.run(
                        build_cmd,
                        cwd=str(workspace_dir),
                        env=env,
                        capture_output=True,
                        text=True,
                        timeout=300,  # 5 minute timeout for Rust builds
                    )

                    if result.returncode != 0:
                        click.echo(f"    [ERROR] rust: Build failed for {package}")
                        click.echo(f"    {result.stderr[:500]}")
                        return False

                except subprocess.TimeoutExpired:
                    click.echo(f"    [ERROR] rust: Build timeout for {package}")
                    return False
                except Exception as e:
                    click.echo(f"    [ERROR] rust: Build error: {e}")
                    return False

                # Run the binary
                click.echo(f"    [INFO] rust: Starting {package}...")
                run_cmd = ["cargo", "run", "--release", "-p", package]

                try:
                    process = subprocess.Popen(
                        run_cmd,
                        cwd=str(workspace_dir),
                        env=env,
                        stdout=subprocess.PIPE,
                        stderr=subprocess.PIPE,
                        start_new_session=True,
                    )

                    # Store PID for later management (include port offset for uniqueness)
                    pid_suffix = f"_offset{port_offset}" if port_offset != 0 else ""
                    pid_file = project_dir / f".rust_{package}{pid_suffix}.pid"
                    pid_file.write_text(str(process.pid))

                    click.echo(f"    [OK] rust: {package} started (PID: {process.pid})")

                except Exception as e:
                    click.echo(f"    [ERROR] rust: Failed to start {package}: {e}")
                    return False

            return True

        else:
            # Project-local Rust build
            cargo_dir = self._get_project_cargo_path(project, "backend")

            if not (cargo_dir / "Cargo.toml").exists():
                click.echo(f"    [ERROR] rust: No Cargo.toml found at {cargo_dir}")
                return False

            click.echo(f"    [INFO] rust: Building from {cargo_dir}...")

            # Build
            build_cmd = ["cargo", "build", "--release"]
            try:
                result = subprocess.run(
                    build_cmd, cwd=str(cargo_dir), env=env, capture_output=True, text=True, timeout=300
                )

                if result.returncode != 0:
                    click.echo(f"    [ERROR] rust: Build failed")
                    click.echo(f"    {result.stderr[:500]}")
                    return False

            except subprocess.TimeoutExpired:
                click.echo(f"    [ERROR] rust: Build timeout")
                return False

            # Run
            run_cmd = ["cargo", "run", "--release"]
            try:
                process = subprocess.Popen(
                    run_cmd,
                    cwd=str(cargo_dir),
                    env=env,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    start_new_session=True,
                )

                pid_suffix = f"_offset{port_offset}" if port_offset != 0 else ""
                pid_file = project_dir / f".rust{pid_suffix}.pid"
                pid_file.write_text(str(process.pid))

                click.echo(f"    [OK] rust: started (PID: {process.pid})")
                return True

            except Exception as e:
                click.echo(f"    [ERROR] rust: Failed to start: {e}")
                return False

    def _find_rust_packages(self, project: str) -> List[str]:
        """Find Rust package names for a project.

        Args:
            project: Project name

        Returns:
            List of Cargo package names (e.g., ['orion-backend', 'orion-engine'])
        """
        project_dir = self.workspace_root / project
        packages = []

        # Check common locations for Cargo.toml and extract package name
        cargo_locations = [
            project_dir / "backend" / "Cargo.toml",
            project_dir / "engine" / "Cargo.toml",
            project_dir / "Cargo.toml",
        ]

        for cargo_path in cargo_locations:
            if cargo_path.exists():
                try:
                    # Parse Cargo.toml to get package name
                    import tomllib

                    with open(cargo_path, "rb") as f:
                        cargo_toml = tomllib.load(f)
                        if "package" in cargo_toml and "name" in cargo_toml["package"]:
                            packages.append(cargo_toml["package"]["name"])
                except ImportError:
                    # Python < 3.11, try toml package or fallback to convention
                    try:
                        import toml

                        cargo_toml = toml.load(cargo_path)
                        if "package" in cargo_toml and "name" in cargo_toml["package"]:
                            packages.append(cargo_toml["package"]["name"])
                    except ImportError:
                        # Fallback: use conventional naming
                        if "backend" in str(cargo_path):
                            packages.append(f"{project}-backend")
                        elif "engine" in str(cargo_path):
                            packages.append(f"{project}-engine")
                        else:
                            packages.append(project)
                except Exception:
                    # Fallback to conventional naming
                    if "backend" in str(cargo_path):
                        packages.append(f"{project}-backend")
                    elif "engine" in str(cargo_path):
                        packages.append(f"{project}-engine")
                    else:
                        packages.append(project)

        return packages

    def _find_backend_main(self, project: str, component_dir: Path) -> Optional[str]:
        """Find the main module for a backend component.

        Args:
            project: Project name
            component_dir: Path to the backend component directory

        Returns:
            Module string for uvicorn (e.g., 'project.main:app') or None
        """
        # First check project's .sega.yml for explicit main_module config
        project_dir = component_dir.parent
        sega_config_path = project_dir / ".sega.yml"
        if sega_config_path.exists():
            try:
                with open(sega_config_path, "r") as f:
                    project_config = yaml.safe_load(f)
                    if project_config and "services" in project_config:
                        backend_config = project_config["services"].get("backend", {})
                        if "main_module" in backend_config:
                            return backend_config["main_module"]
            except Exception:
                pass  # Fall back to pattern detection

        # Common patterns for FastAPI/Starlette apps
        patterns = [
            (component_dir / "main.py", f"{project}.main:app"),
            (component_dir / project / "main.py", f"{project}.main:app"),
            (component_dir / "app.py", f"{project}.app:app"),
            (component_dir / "src" / "main.py", f"src.main:app"),
            (component_dir / "src" / project / "main.py", f"src.{project}.main:app"),
            # Additional pattern for {project}_ui naming convention (e.g., chrona_ui)
            (component_dir / f"{project}_ui" / "main.py", f"{project}_ui.main:app"),
        ]

        for path, module in patterns:
            if path.exists():
                return module

        return None

    def _load_env_file(self, env_file: Path, env: Dict[str, str]) -> None:
        """Load environment variables from .env file.

        Args:
            env_file: Path to .env file
            env: Environment dict to update
        """
        try:
            with open(env_file, "r") as f:
                for line in f:
                    line = line.strip()
                    if line and not line.startswith("#") and "=" in line:
                        key, value = line.split("=", 1)
                        env[key.strip()] = value.strip().strip('"').strip("'")
        except Exception:
            pass  # Ignore errors reading env file

    def deploy_all(self, projects: Optional[List[str]] = None) -> Dict[str, bool]:
        """Deploy multiple projects.

        Args:
            projects: List of project names, or None for all projects

        Returns:
            Dictionary of project -> success status
        """
        if projects is None:
            projects = self.get_projects_with_compose()

        workspace_name = self.config.get("workspace", {}).get("name", "workspace")
        click.echo(f"[INFO] Deploying {len(projects)} projects in {workspace_name}...")

        # Ensure shared venv if configured
        if not self.ensure_shared_venv():
            click.echo("[WARNING] Continuing without shared venv")

        # Start shared infrastructure if configured
        if not self.start_shared_infrastructure():
            click.echo("[WARNING] Continuing without shared infrastructure")

        # Deploy each project
        results = {}
        for project in projects:
            results[project] = self.deploy_project(project)

        # Summary
        click.echo("\n[INFO] Deployment Summary:")
        successful = [p for p, success in results.items() if success]
        failed = [p for p, success in results.items() if not success]

        if successful:
            click.echo(f"[OK] Successful: {', '.join(successful)}")
        if failed:
            click.echo(f"[ERROR] Failed: {', '.join(failed)}")

        return results

    def stop_project(self, project: str) -> bool:
        """Stop a single project.

        Args:
            project: Project name

        Returns:
            True if successful
        """
        click.echo(f"[INFO] Stopping {project}...")

        # Check if we should use Makefile
        config = self.get_project_config(project)
        if config.get("has_makefile"):
            project_dir = self.workspace_root / project
            targets = self.config.get("deployment", {}).get("makefile_targets", {}).get("down", ["down", "stop"])

            env = os.environ.copy()
            env.update(self.config.get("environment_defaults", {}))

            for target in targets:
                try:
                    result = subprocess.run(
                        ["make", target], cwd=str(project_dir), env=env, capture_output=True, text=True
                    )
                    if result.returncode == 0:
                        click.echo(f"[OK] {project} stopped with make {target}")
                        return True
                except Exception:
                    continue

        # Use docker-compose
        cmd = self.get_compose_command(project, "down")

        try:
            result = subprocess.run(cmd, capture_output=True, text=True)

            if result.returncode == 0:
                click.echo(f"[OK] {project} stopped")
                return True
            else:
                click.echo(f"[WARNING] Failed to stop {project}")
                return False
        except Exception as e:
            click.echo(f"[ERROR] Error stopping {project}: {e}")
            return False

    def get_status(self) -> Dict[str, List[Dict]]:
        """Get status of all services.

        Returns:
            Dictionary of project -> list of container info
        """
        if not self.docker_client:
            return {}

        status = {}

        try:
            containers = self.docker_client.containers.list(all=True)

            for container in containers:
                labels = container.labels
                project = labels.get("com.docker.compose.project", "")

                if project.startswith(self.compose_project_prefix):
                    project_name = project.replace(f"{self.compose_project_prefix}_", "")

                    if project_name not in status:
                        status[project_name] = []

                    status[project_name].append(
                        {
                            "name": container.name,
                            "status": container.status,
                            "ports": container.ports,
                            "health": container.attrs.get("State", {}).get("Health", {}).get("Status", "unknown"),
                        }
                    )

        except Exception as e:
            click.echo(f"Error getting status: {e}")

        return status

    def show_logs(self, project: str, follow: bool = True, tail: int = 100, service: str | None = None):
        """Show logs for a project.

        Args:
            project: Project name
            follow: Whether to follow logs
            tail: Number of lines to show
            service: Optional compose service name to filter logs
        """
        cmd = self.get_compose_command(project, "logs")

        if follow:
            cmd.append("-f")
        if tail:
            cmd.extend(["--tail", str(tail)])

        # Compose service filters must come after the options.
        if service:
            cmd.append(service)

        try:
            subprocess.run(cmd)
        except KeyboardInterrupt:
            click.echo("\nStopped following logs")
        except Exception as e:
            click.echo(f"Error showing logs: {e}")
