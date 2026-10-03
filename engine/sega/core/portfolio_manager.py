#!/usr/bin/env python
# -*- coding: utf-8 -*-
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

# ===============================================================
# SEGA MODULE - Portfolio Manager
# ===============================================================
# File: src/sega/core/portfolio_manager.py
# Purpose: Manages SEGA at the portfolio level across multiple projects
#
# Description: Provides portfolio-level management capabilities for discovering
# and configuring multiple SEGA projects. Handles Git repository scanning,
# project detection, and workspace-level configuration management.
#
# Dependencies:
# - External: git, yaml, pathlib, typing
# - Internal: sega.detectors.project_detector
#
# Used by: Workspace management commands, enterprise orchestrator
#

import os
import git
import yaml
from pathlib import Path
from typing import Dict, List, Optional
from ..project.project_detector import ProjectDetector


class PortfolioManager:
    """Manages SEGA at the portfolio level, discovering and configuring multiple projects."""

    def __init__(self, root_path: str = None):
        self.root_path = Path(root_path) if root_path else Path.cwd()
        self.discovered_projects = {}
        self.git_repositories = {}
        self.workspace_config = None

    def discover_git_projects(self) -> Dict[str, Dict]:
        """Discover all git repositories in the portfolio."""
        git_projects = {}

        # Walk through directory structure
        for root, dirs, files in os.walk(self.root_path):
            # Skip hidden directories and common ignore patterns
            dirs[:] = [
                d
                for d in dirs
                if not d.startswith(".")
                and d
                not in [
                    "_internal/environments/_internal/environments/node_modules",
                    "__pycache__",
                    "venv",
                    "env",
                ]
            ]

            if ".git" in dirs:
                project_path = Path(root)
                relative_path = project_path.relative_to(self.root_path)

                try:
                    repo = git.Repo(project_path)

                    # Get project info
                    project_info = {
                        "path": project_path,
                        "relative_path": str(relative_path),
                        "git_url": self._get_git_url(repo),
                        "current_branch": repo.active_branch.name
                        if repo.active_branch
                        else "unknown",
                        "has_sega_config": self._has_sega_config(project_path),
                        "detector": ProjectDetector(str(project_path)),
                        "last_commit": repo.head.commit.hexsha[:8]
                        if repo.head.commit
                        else "unknown",
                    }

                    # Auto-detect project type
                    project_info["detected_type"] = project_info[
                        "detector"
                    ].detect()

                    # Extract team and project name from path structure
                    path_parts = str(relative_path).split(os.sep)
                    if len(path_parts) >= 2:
                        project_info["team"] = path_parts[0]
                        project_info["project_name"] = path_parts[1]
                    else:
                        project_info["team"] = "unknown"
                        project_info["project_name"] = (
                            path_parts[-1] if path_parts else "unknown"
                        )

                    git_projects[str(relative_path)] = project_info

                except Exception:
                    # Skip repositories that can't be processed
                    continue

        self.git_repositories = git_projects
        return git_projects

    def _get_git_url(self, repo: git.Repo) -> Optional[str]:
        """Get the git remote URL."""
        try:
            return list(repo.remotes.origin.urls)[0]
        except (IndexError, AttributeError):
            return None

    def _has_sega_config(self, project_path: Path) -> bool:
        """Check if project has SEGA configuration."""
        return (project_path / "sega.yaml").exists() or (
            project_path / ".sega.yml"
        ).exists()

    def load_project_paths(
        self, paths_file: str = "sega-projects.yaml"
    ) -> Dict[str, List[str]]:
        """Load project paths from configuration file."""
        paths_config_path = self.root_path / paths_file

        if not paths_config_path.exists():
            return {}

        try:
            with open(paths_config_path) as f:
                config = yaml.safe_load(f)
                return config.get("projects", {})
        except Exception:
            return {}

    def save_project_paths(
        self,
        project_paths: Dict[str, List[str]],
        paths_file: str = "sega-projects.yaml",
    ):
        """Save project paths to configuration file."""
        paths_config_path = self.root_path / paths_file

        config = {
            "version": "2.1",
            "projects": project_paths,
            "metadata": {
                "discovered_at": str(self.root_path),
                "total_projects": sum(
                    len(projects) for projects in project_paths.values()
                ),
            },
        }

        with open(paths_config_path, "w") as f:
            yaml.dump(config, f, default_flow_style=False, indent=2)

    def filter_projects(
        self, projects: Dict[str, Dict], filters: Dict
    ) -> Dict[str, Dict]:
        """Filter projects based on criteria."""
        filtered = {}

        for project_key, project_info in projects.items():
            include = True

            # Filter by team
            if (
                "teams" in filters
                and project_info.get("team") not in filters["teams"]
            ):
                include = False

            # Filter by project type
            if (
                "types" in filters
                and project_info.get("detected_type") not in filters["types"]
            ):
                include = False

            # Filter by having SEGA config
            if (
                "has_sega_config" in filters
                and project_info.get("has_sega_config")
                != filters["has_sega_config"]
            ):
                include = False

            # Filter by path pattern
            if "path_pattern" in filters and filters[
                "path_pattern"
            ] not in str(project_info.get("relative_path", "")):
                include = False

            if include:
                filtered[project_key] = project_info

        return filtered

    def generate_workspace_config(
        self, selected_projects: Dict[str, Dict] = None
    ) -> Dict:
        """Generate workspace-level configuration."""
        if selected_projects is None:
            selected_projects = self.git_repositories

        # Group projects by team
        teams = {}
        for project_key, project_info in selected_projects.items():
            team = project_info.get("team", "unknown")
            if team not in teams:
                teams[team] = []
            teams[team].append(project_key)

        # Generate configuration
        config = {
            "version": "2.1",
            "workspace": {
                "root_path": str(self.root_path),
                "total_projects": len(selected_projects),
                "teams": teams,
                "projects": {},
            },
        }

        # Add project details
        for project_key, project_info in selected_projects.items():
            config["workspace"]["projects"][project_key] = {
                "name": project_info.get("project_name"),
                "team": project_info.get("team"),
                "type": project_info.get("detected_type"),
                "path": str(project_info.get("relative_path")),
                "git_url": project_info.get("git_url"),
                "has_sega_config": project_info.get("has_sega_config"),
                "components": project_info["detector"].get_components(),
            }

        self.workspace_config = config
        return config

    def init_projects(
        self,
        project_paths: List[str],
        force: bool = False,
        template: str = "fleet",
        dry_run: bool = False,
    ) -> Dict[str, Dict]:
        """Initialize SEGA configuration for multiple projects."""
        results = {}

        for project_path in project_paths:
            full_path = self.root_path / project_path

            if not full_path.exists():
                results[project_path] = {
                    "success": False,
                    "error": f"Path does not exist: {full_path}",
                }
                continue

            try:
                # Initialize project
                result = self._init_single_project(
                    full_path, force, template, dry_run
                )
                results[project_path] = result

            except Exception as e:
                results[project_path] = {"success": False, "error": str(e)}

        return results

    def _init_single_project(
        self, project_path: Path, force: bool, template: str, dry_run: bool
    ) -> Dict:
        """Initialize SEGA configuration for a single project."""
        # Check if config already exists
        sega_yaml_path = project_path / "sega.yaml"
        legacy_path = project_path / ".sega.yml"

        if (sega_yaml_path.exists() or legacy_path.exists()) and not force:
            return {
                "success": False,
                "error": "SEGA configuration already exists. Use --force to overwrite.",
            }

        # Auto-detect project
        detector = ProjectDetector(str(project_path))
        project_type = detector.detect()
        fleet_metadata = detector.get_fleet_metadata()
        components = detector.get_components()

        # Generate minimal configuration
        config = self._generate_minimal_config(
            project_type, fleet_metadata, components
        )

        if dry_run:
            return {
                "success": True,
                "action": "would_create",
                "config": config,
                "project_type": project_type,
                "components": len(components),
            }

        # Write configuration
        with open(sega_yaml_path, "w") as f:
            yaml.dump(config, f, default_flow_style=False, indent=2)

        # Generate GitLab CI if requested
        gitlab_ci_path = project_path / ".gitlab-ci.yml"
        if not gitlab_ci_path.exists():
            gitlab_config = self._generate_gitlab_ci(
                project_type, fleet_metadata
            )
            with open(gitlab_ci_path, "w") as f:
                f.write(gitlab_config)

        # Generate health endpoint template if web project
        if project_type in ["web_app", "ml_pipeline"]:
            self._generate_health_endpoint(project_path, project_type)

        return {
            "success": True,
            "action": "created",
            "config_path": str(sega_yaml_path),
            "project_type": project_type,
            "components": len(components),
        }

    def _generate_minimal_config(
        self, project_type: str, fleet_metadata: Dict, components: List[Dict]
    ) -> Dict:
        """Generate minimal working SEGA configuration."""
        config = {
            "version": "2.1",
            "project": {
                "name": fleet_metadata.get("project_name", "unknown"),
                "type": project_type,
                "domain": "fleet",
                "team": fleet_metadata.get("team", "unknown"),
            },
        }

        # Add components if multi-component project
        if components:
            config["components"] = components

        # Add deployment configuration
        config["deployment"] = {
            "targets": {
                "staging": {
                    "type": "aws-ecs",
                    "region": "us-east-1",
                    "cluster": "fleet-staging",
                    "strategy": "rolling",
                    "auto_deploy": True,
                },
                "production": {
                    "type": "aws-ecs",
                    "region": "us-east-1",
                    "cluster": "fleet-production",
                    "strategy": "canary",
                    "auto_deploy": False,
                    "approval_required": True,
                },
            }
        }

        # Add build configuration
        config["build"] = {
            "strategy": "containerized",
            "docker": {
                "dockerfile": "Dockerfile",
                "context": ".",
                "registry": "ecr",
            },
        }

        # Add project-specific configurations
        if project_type == "web_app":
            config["deployment"]["targets"]["staging"]["infrastructure"] = {
                "port": 3000,
                "health_check_path": "/health",
                "cpu": 256,
                "memory": 512,
                "min_instances": 2,
                "max_instances": 10,
            }
            config["deployment"]["targets"]["production"]["infrastructure"] = {
                "port": 3000,
                "health_check_path": "/health",
                "cpu": 256,
                "memory": 512,
                "min_instances": 2,
                "max_instances": 10,
            }
        elif project_type == "ml_pipeline":
            config["deployment"]["targets"]["staging"]["infrastructure"] = {
                "port": 8000,
                "health_check_path": "/health",
                "cpu": 1024,
                "memory": 2048,
                "min_instances": 1,
                "max_instances": 5,
                "gpu_required": True,
            }
            config["deployment"]["targets"]["production"]["infrastructure"] = {
                "port": 8000,
                "health_check_path": "/health",
                "cpu": 1024,
                "memory": 2048,
                "min_instances": 1,
                "max_instances": 5,
                "gpu_required": True,
            }
        elif project_type == "firmware_edge":
            config["deployment"] = {
                "targets": {
                    "staging": {
                        "type": "ansible_flash",
                        "target_devices": "lab-devices",
                        "strategy": "rolling",
                    },
                    "production": {
                        "type": "ansible_flash",
                        "target_devices": "production-devices",
                        "strategy": "blue_green",
                    },
                }
            }

        return config

    def _generate_gitlab_ci(
        self, project_type: str, fleet_metadata: Dict
    ) -> str:
        """Generate GitLab CI configuration."""
        team = fleet_metadata.get("team", "unknown")
        project_name = fleet_metadata.get("project_name", "unknown")

        return f"""# Auto-generated GitLab CI for FLEET project
# Team: {team}, Project: {project_name}, Type: {project_type}

include:
  - project: 'fleet/sega'
    file: '/templates/fleet/gitlab-ci-fleet.yml'

variables:
  FLEET_TEAM: "{team}"
  FLEET_PROJECT: "{project_name}"
  SEGA_PROJECT_TYPE: "{project_type}"

# Override stages if needed
stages:
  - validate
  - build
  - test
  - security
  - deploy-staging
  - deploy-production
"""

    def _generate_health_endpoint(self, project_path: Path, project_type: str):
        """Generate health endpoint template."""
        if project_type == "web_app":
            # Check if it's a Node.js project
            if (project_path / "package.json").exists():
                health_content = """// Auto-generated health endpoint
app.get('/health', (req, res) => {
  res.status(200).json({
    status: 'healthy',
    timestamp: new Date().toISOString(),
    service: process.env.FLEET_PROJECT || 'unknown'
  });
});
"""
                with open(project_path / "health.js", "w") as f:
                    f.write(health_content)

            # Check if it's a Python project
            elif (project_path / "requirements.txt").exists():
                health_content = """# Auto-generated health endpoint with authentication
from flask import Flask, jsonify, request
import datetime
import os
import secrets
import hashlib

app = Flask(__name__)

# Simple API key authentication for health endpoint
def authenticate_request():
    api_key = request.headers.get('X-API-Key')
    expected_key = os.getenv('HEALTH_API_KEY')
    
    if not expected_key:
        # If no API key is configured, allow localhost only
        if request.remote_addr not in ['127.0.0.1', '::1']:
            return False
        return True
    
    if not api_key:
        return False
    
    # Secure comparison to prevent timing attacks
    return secrets.compare_digest(api_key, expected_key)

@app.route('/health')
def health():
    if not authenticate_request():
        return jsonify({
            'error': 'Authentication required',
            'message': 'Health endpoint requires X-API-Key header or localhost access'
        }), 401
    
    return jsonify({
        'status': 'healthy',
        'timestamp': datetime.datetime.utcnow().isoformat(),
        'service': os.getenv('FLEET_PROJECT', 'unknown'),
        'version': os.getenv('FLEET_VERSION', '1.0.0')
    })

@app.route('/metrics')
def metrics():
    if not authenticate_request():
        return jsonify({
            'error': 'Authentication required'
        }), 401
    
    # Basic metrics for monitoring
    import psutil
    import time
    
    # Get process info
    process = psutil.Process()
    
    return jsonify({
        'uptime': time.time() - process.create_time(),
        'requests_total': 0,  # Would need middleware to track
        'memory_usage': process.memory_info().rss / 1024 / 1024  # MB
    })
"""
                with open(project_path / "health.py", "w") as f:
                    f.write(health_content)

    def get_project_summary(self) -> Dict:
        """Get summary of discovered projects."""
        if not self.git_repositories:
            return {
                "total": 0,
                "by_team": {},
                "by_type": {},
                "with_sega_config": 0,
            }

        summary = {
            "total": len(self.git_repositories),
            "by_team": {},
            "by_type": {},
            "with_sega_config": 0,
        }

        for project_info in self.git_repositories.values():
            # Count by team
            team = project_info.get("team", "unknown")
            summary["by_team"][team] = summary["by_team"].get(team, 0) + 1

            # Count by type
            project_type = project_info.get("detected_type", "unknown")
            summary["by_type"][project_type] = (
                summary["by_type"].get(project_type, 0) + 1
            )

            # Count with SEGA config
            if project_info.get("has_sega_config"):
                summary["with_sega_config"] += 1

        return summary
