#!/usr/bin/env python3
# Copyright 2025 SEGA

"""
FLEET MONOREPO SERVICE
==============================================================================
File: src/sega/services/service.py
Project: SEGA (Scalable Engineering & Growth Automation)
Copyright: 2022-2025 FLEET
License: Apache-2.0
SEGA MODULE: Services/FLEET
COMPONENT: FLEET Monorepo Management Service
PURPOSE: Core business logic for FLEET monorepo operations
==============================================================================
"""

import subprocess
from pathlib import Path
from typing import List, Optional, Dict, Any
from dataclasses import dataclass
from .systemd_service import SystemdService


@dataclass
class SegaResult:
    success: bool
    error: Optional[str] = None
    updated_projects: Optional[List[str]] = None
    pushed_projects: Optional[List[str]] = None
    project_status: Optional[Dict[str, Any]] = None
    deployment_results: Optional[Dict[str, Any]] = None
    engine_results: Optional[Dict[str, Any]] = None
    test_results: Optional[Dict[str, Any]] = None


class SegaService:
    """Service for managing FLEET monorepo operations."""

    def __init__(self, fleet_root: Optional[Path] = None):
        self.fleet_root = fleet_root or self._find_fleet_root()
        self.projects = self._get_submodule_projects()
        self.systemd = SystemdService()

    def _find_fleet_root(self) -> Path:
        """Find FLEET root directory."""
        current = Path.cwd()
        while current != current.parent:
            if (current / ".gitmodules").exists():
                return current
            current = current.parent
        raise RuntimeError("FLEET root not found")

    def _get_submodule_projects(self) -> List[str]:
        """Get list of git submodule projects."""
        try:
            result = subprocess.run(
                ["git", "submodule", "status"], cwd=self.fleet_root, capture_output=True, text=True, check=True
            )
            projects = []
            for line in result.stdout.strip().split("\n"):
                if line.strip():
                    # Extract project name from submodule status
                    parts = line.split()
                    if len(parts) >= 2:
                        projects.append(parts[1])
            return projects
        except subprocess.CalledProcessError:
            return []

    def bulk_pull(self, projects: Optional[List[str]] = None) -> SegaResult:
        """Pull latest changes for projects."""
        target_projects = projects or self.projects
        updated_projects = []

        try:
            # Update submodules
            subprocess.run(
                ["git", "submodule", "update", "--init", "--recursive", "--remote"], cwd=self.fleet_root, check=True
            )

            # Pull each project
            for project in target_projects:
                project_path = self.fleet_root / project
                if project_path.exists():
                    subprocess.run(["git", "pull", "origin", "main"], cwd=project_path, check=True)
                    updated_projects.append(project)

            return SegaResult(success=True, updated_projects=updated_projects)

        except subprocess.CalledProcessError as e:
            return SegaResult(success=False, error=str(e))

    def bulk_push(self, projects: Optional[List[str]] = None) -> SegaResult:
        """Push changes for projects."""
        target_projects = projects or self.projects
        pushed_projects = []

        try:
            for project in target_projects:
                project_path = self.fleet_root / project
                if project_path.exists():
                    # Check if there are changes to push
                    result = subprocess.run(
                        ["git", "status", "--porcelain"], cwd=project_path, capture_output=True, text=True
                    )

                    if result.stdout.strip():
                        subprocess.run(["git", "push", "origin", "main"], cwd=project_path, check=True)
                        pushed_projects.append(project)

            return SegaResult(success=True, pushed_projects=pushed_projects)

        except subprocess.CalledProcessError as e:
            return SegaResult(success=False, error=str(e))

    def bulk_status(self, projects: Optional[List[str]] = None) -> SegaResult:
        """Get git status for projects."""
        target_projects = projects or self.projects
        project_status = {}

        for project in target_projects:
            project_path = self.fleet_root / project
            if project_path.exists():
                try:
                    # Get working tree status
                    status_result = subprocess.run(
                        ["git", "status", "--porcelain"], cwd=project_path, capture_output=True, text=True
                    )

                    # Get branch comparison
                    branch_result = subprocess.run(
                        ["git", "rev-list", "--left-right", "--count", "HEAD...origin/main"],
                        cwd=project_path,
                        capture_output=True,
                        text=True,
                    )

                    changes = len(status_result.stdout.strip().split("\n")) if status_result.stdout.strip() else 0
                    ahead, behind = (0, 0)
                    if branch_result.stdout.strip():
                        try:
                            ahead, behind = map(int, branch_result.stdout.strip().split())
                        except ValueError:
                            pass

                    project_status[project] = {
                        "clean": changes == 0,
                        "changes": changes,
                        "ahead": ahead,
                        "behind": behind,
                    }

                except subprocess.CalledProcessError:
                    project_status[project] = {"clean": False, "changes": "unknown", "ahead": 0, "behind": 0}

        return SegaResult(success=True, project_status=project_status)

    def deploy_projects(self, projects: Optional[List[str]] = None, environment: str = "development") -> SegaResult:
        """Deploy FLEET projects with multimodal strategy."""
        target_projects = projects or self.projects
        deployment_results = {}

        for project in target_projects:
            project_path = self.fleet_root / project
            if not project_path.exists():
                continue

            # Check for multimodal components
            components = self._detect_project_components(project_path)

            try:
                ports = {}
                # Deploy each component
                if "backend" in components:
                    # Deploy backend service
                    ports["backend"] = self._deploy_backend(project_path, environment)

                if "frontend" in components:
                    # Deploy frontend service
                    ports["frontend"] = self._deploy_frontend(project_path, environment)

                if "engine" in components:
                    # Deploy engine as systemd service
                    ports["engine"] = self._deploy_engine_systemd(project_path, environment)

                if "expo" in components:
                    # Deploy mobile app dev server
                    ports["expo"] = self._deploy_expo(project_path, environment)

                if "desktop" in components:
                    # Handle desktop app
                    ports["desktop"] = self._deploy_desktop(project_path, environment)

                deployment_results[project] = {"success": True, "components": components, "ports": ports}

            except Exception as e:
                deployment_results[project] = {"success": False, "error": str(e)}

        return SegaResult(success=True, deployment_results=deployment_results)

    def manage_engines(self, projects: Optional[List[str]] = None, action: str = "status") -> SegaResult:
        """Manage engine systemd services."""
        target_projects = projects or self.projects
        engine_results = {}

        for project in target_projects:
            project_path = self.fleet_root / project
            engine_path = project_path / "engine"

            if not engine_path.exists():
                continue

            service_name = f"fleet-{project}-engine"

            try:
                result = self.systemd.manage_service(service_name, action)

                engine_results[project] = {"success": result.success, "status": result.status, "error": result.error}

            except Exception as e:
                engine_results[project] = {"success": False, "error": str(e)}

        return SegaResult(success=True, engine_results=engine_results)

    def run_tests(self, projects: Optional[List[str]] = None) -> SegaResult:
        """Run tests for projects."""
        target_projects = projects or self.projects
        test_results = {}

        for project in target_projects:
            project_path = self.fleet_root / project
            if not project_path.exists():
                continue

            try:
                # Try different test runners
                if (project_path / "backend" / "pyproject.toml").exists():
                    # Python project with pytest
                    result = subprocess.run(
                        ["python", "-m", "pytest", "--tb=short"],
                        cwd=project_path / "backend",
                        capture_output=True,
                        text=True,
                    )

                elif (project_path / "frontend" / "package.json").exists():
                    # Node.js project with npm test
                    result = subprocess.run(
                        ["npm", "test"], cwd=project_path / "frontend", capture_output=True, text=True
                    )

                else:
                    # Skip if no recognizable test setup
                    continue

                # Parse test results (simplified)
                success = result.returncode == 0
                test_results[project] = {
                    "success": success,
                    "passed": 0,  # Would parse from output
                    "total": 0,  # Would parse from output
                    "output": result.stdout,
                }

            except Exception as e:
                test_results[project] = {"success": False, "error": str(e)}

        return SegaResult(success=True, test_results=test_results)

    def init_infrastructure(self) -> SegaResult:
        """Initialize FLEET deployment infrastructure."""
        try:
            # Create shared environments
            shared_env_script = self.fleet_root / "_internal" / "scripts" / "init_shared_environments.sh"
            if shared_env_script.exists():
                subprocess.run([str(shared_env_script)], check=True)

            # Generate systemd service templates for engines
            self._generate_systemd_templates()

            # Set up GitLab CI integration
            self._setup_gitlab_ci()

            return SegaResult(success=True)

        except Exception as e:
            return SegaResult(success=False, error=str(e))

    def _detect_project_components(self, project_path: Path) -> List[str]:
        """Detect available components in a project."""
        components = []

        if (project_path / "backend").exists():
            components.append("backend")
        if (project_path / "frontend").exists():
            components.append("frontend")
        if (project_path / "engine").exists():
            components.append("engine")
        if (project_path / "expo").exists():
            components.append("expo")
        if (project_path / "desktop").exists():
            components.append("desktop")

        return components

    def _deploy_backend(self, project_path: Path, environment: str) -> int:
        """Deploy backend component."""
        # Use existing docker-compose logic
        compose_file = project_path / "docker-compose.dev.yml"
        if compose_file.exists():
            subprocess.run(
                ["docker-compose", "-f", str(compose_file), "up", "-d", "backend"], cwd=project_path, check=True
            )
        return 8000  # Default backend port

    def _deploy_frontend(self, project_path: Path, environment: str) -> int:
        """Deploy frontend component."""
        compose_file = project_path / "docker-compose.dev.yml"
        if compose_file.exists():
            subprocess.run(
                ["docker-compose", "-f", str(compose_file), "up", "-d", "frontend"], cwd=project_path, check=True
            )
        return 3000  # Default frontend port

    def _deploy_engine_systemd(self, project_path: Path, environment: str) -> int:
        """Deploy engine as systemd service."""
        project_name = project_path.name
        engine_path = project_path / "engine"

        # Install systemd service using SystemdService
        result = self.systemd.install_engine_service(
            project_name=project_name, engine_path=engine_path, environment=environment, start_service=True
        )

        if not result.success:
            raise RuntimeError(f"Failed to install engine service: {result.error}")

        return 9000  # Default engine port

    def _deploy_expo(self, project_path: Path, environment: str) -> int:
        """Deploy Expo development server."""
        expo_path = project_path / "expo"
        if expo_path.exists():
            # Start Expo dev server in background
            subprocess.Popen(["npx", "expo", "start", "--web"], cwd=expo_path)
        return 19006  # Default Expo web port

    def _deploy_desktop(self, project_path: Path, environment: str) -> int:
        """Deploy desktop aApplication."""
        # For local development, desktop aApps run natively
        # In production, they would be packaged and distributed
        return 0  # No port for desktop aApps

    def _generate_engine_service(self, project_path: Path, environment: str) -> str:
        """Generate systemd service file for engine."""
        project_name = project_path.name
        engine_path = project_path / "engine"

        return f"""[Unit]
Description=FLEET {project_name.title()} Engine Service
After=network.target

[Service]
Type=simple
User=fleet
WorkingDirectory={engine_path}
Environment=ENVIRONMENT={environment}
Environment=PYTHONPATH={engine_path}
ExecStart=/usr/bin/python3 -m {project_name}.main
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
"""

    def _generate_systemd_templates(self):
        """Generate systemd service templates."""
        templates_dir = self.fleet_root / "_internal" / "templates" / "systemd"
        templates_dir.mkdir(parents=True, exist_ok=True)

        # Create template for engine services
        template_content = """[Unit]
Description=FLEET {{PROJECT_NAME}} Engine Service
After=network.target

[Service]
Type=simple
User=fleet
WorkingDirectory={{ENGINE_PATH}}
Environment=ENVIRONMENT={{ENVIRONMENT}}
Environment=PYTHONPATH={{ENGINE_PATH}}
ExecStart=/usr/bin/python3 -m {{PROJECT_MODULE}}.main
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
"""

        with open(templates_dir / "engine.service.template", "w") as f:
            f.write(template_content)

    def _setup_gitlab_ci(self):
        """Set up GitLab CI integration."""
        ci_template = self.fleet_root / ".gitlab-ci.yml"

        gitlab_ci_content = """# FLEET Monorepo GitLab CI - Managed by SEGA
stages:
  - validate
  - test
  - build
  - deploy-development
  - deploy-production

variables:
  SEGA_VERSION: "latest"

# Validation stage - check all submodules
validate:fleet:
  stage: validate
  script:
    - sega fleet status
    - sega fleet pull
  only:
    - main
    - develop

# Test stage - run tests across projects
test:fleet:
  stage: test
  script:
    - sega fleet test
  only:
    - main
    - develop

# Build stage - build all projects
build:fleet:
  stage: build
  script:
    - sega fleet deploy --environment=staging
  only:
    - main
    - develop

# Development deployment
deploy:development:
  stage: deploy-development
  script:
    - sega fleet deploy --environment=development
    - sega fleet engines --action=restart
  only:
    - develop
  environment:
    name: development

# Production deployment
deploy:production:
  stage: deploy-production
  script:
    - sega fleet deploy --environment=production
    - sega fleet engines --action=restart
  only:
    - main
  environment:
    name: production
  when: manual
"""

        with open(ci_template, "w") as f:
            f.write(gitlab_ci_content)
