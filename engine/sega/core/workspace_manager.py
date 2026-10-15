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
# SEGA MODULE - WORKSPACE MANAGER
# ===============================================================
# File: src/sega/core/workspace_manager.py
# Purpose: Multi-project workspace management for FLEET projects
#
# Description: Discovers and manages projects within FLEET workspace structure,
# handles dependency graphs between projects, and coordinates multi-project
# operations. Supports team-based project organization and navigation.
#
# Dependencies:
# - External: yaml, pathlib
# - Internal: detectors.project_detector
#
# Used by: enterprise_orchestrator, deployment_service, CLI commands
#

"""Multi-project workspace management for FLEET projects."""

import yaml
from pathlib import Path
from typing import Dict, List, Optional, Set
from ..project.project_detector import ProjectDetector


class WorkspaceManager:
    """Manages multi-project workspaces for coordinated deployment and operations."""

    def __init__(self, workspace_root: str = None):
        self.workspace_root = (
            Path(workspace_root)
            if workspace_root
            else self._find_workspace_root()
        )
        self.projects = {}
        self.dependency_graph = {}
        self._discover_projects()
        self.build_dependency_graph()

    def _find_workspace_root(self) -> Path:
        """Find the FLEET workspace root directory."""
        current = Path.cwd()

        # Look for FLEET workspace indicators
        while current != current.parent:
            # If we're already in a projects directory, use it
            if current.name == "projects":
                return current
            # If we find a projects subdirectory, use it
            if (current / "projects").exists():
                return current / "projects"
            current = current.parent

        # Default to current directory
        return Path.cwd()

    def _discover_projects(self):
        """Discover all projects in the workspace."""
        if not self.workspace_root.exists():
            return

        # FLEET project structure: teams/projects
        for team_dir in self.workspace_root.iterdir():
            if team_dir.is_dir() and not team_dir.name.startswith("."):
                self._discover_team_projects(team_dir)

    def _discover_team_projects(self, team_dir: Path):
        """Discover projects within a team directory."""
        team_name = team_dir.name

        for project_dir in team_dir.iterdir():
            if project_dir.is_dir() and not project_dir.name.startswith("."):
                project_key = f"{team_name}/{project_dir.name}"
                self.projects[project_key] = {
                    "name": project_dir.name,
                    "team": team_name,
                    "path": project_dir,
                    "detector": ProjectDetector(str(project_dir)),
                    "config": self._load_project_config(project_dir),
                }

    def _load_project_config(self, project_path: Path) -> Optional[Dict]:
        """Load project configuration from sega.yaml."""
        config_path = project_path / "sega.yaml"
        if config_path.exists():
            with open(config_path) as f:
                return yaml.safe_load(f)

        # Try legacy format
        config_path = project_path / ".sega.yml"
        if config_path.exists():
            with open(config_path) as f:
                return yaml.safe_load(f)

        return None

    def get_project_dependencies(self, project_key: str) -> List[str]:
        """Get dependencies for a specific project."""
        if project_key not in self.projects:
            return []

        project = self.projects[project_key]
        config = project["config"]

        if not config:
            return []

        # Check workspace dependencies
        if "workspace" in config and "dependencies" in config["workspace"]:
            return config["workspace"]["dependencies"]

        # Check legacy dependencies
        if "dependencies" in config:
            return config["dependencies"]

        return []

    def build_dependency_graph(self) -> Dict[str, List[str]]:
        """Build dependency graph for all projects."""
        self.dependency_graph = {}

        for project_key in self.projects:
            self.dependency_graph[project_key] = self.get_project_dependencies(
                project_key
            )

        return self.dependency_graph

    def get_deployment_order(
        self, target_projects: List[str] = None
    ) -> List[str]:
        """Get optimal deployment order considering dependencies."""
        if target_projects is None:
            target_projects = list(self.projects.keys())

        # Build dependency graph
        self.build_dependency_graph()

        # Topological sort
        visited = set()
        temp_visited = set()
        order = []

        def visit(project: str):
            if project in temp_visited:
                raise ValueError(
                    f"Circular dependency detected involving {project}"
                )
            if project in visited:
                return

            temp_visited.add(project)

            # Visit dependencies first
            for dep in self.dependency_graph.get(project, []):
                if dep in target_projects:
                    visit(dep)

            temp_visited.remove(project)
            visited.add(project)
            order.append(project)

        for project in target_projects:
            if project not in visited:
                visit(project)

        return order

    def get_shared_resources(self) -> Dict[str, Set[str]]:
        """Get shared resources across projects."""
        shared_resources = {}

        for project_key, project in self.projects.items():
            config = project["config"]
            if not config:
                continue

            # Check for shared resources
            if "workspace" in config and "shared" in config["workspace"]:
                for resource in config["workspace"]["shared"]:
                    if resource not in shared_resources:
                        shared_resources[resource] = set()
                    shared_resources[resource].add(project_key)

        return shared_resources

    def get_projects_by_team(self, team: str) -> List[str]:
        """Get all projects for a specific team."""
        return [
            key
            for key, project in self.projects.items()
            if project["team"] == team
        ]

    def get_projects_by_type(self, project_type: str) -> List[str]:
        """Get all projects of a specific type."""
        matching_projects = []

        for project_key, project in self.projects.items():
            detector = project["detector"]
            if detector.detect() == project_type:
                matching_projects.append(project_key)

        return matching_projects

    def get_hybrid_projects(self) -> List[str]:
        """Get all hybrid/multi-component projects."""
        return self.get_projects_by_type("hybrid_system")

    def validate_workspace(self) -> Dict[str, List[str]]:
        """Validate workspace configuration and dependencies."""
        issues = {
            "missing_dependencies": [],
            "circular_dependencies": [],
            "configuration_errors": [],
            "missing_configs": [],
        }

        # Check for missing dependencies
        for project_key, deps in self.dependency_graph.items():
            for dep in deps:
                if dep not in self.projects:
                    issues["missing_dependencies"].append(
                        f"{project_key} -> {dep}"
                    )

        # Check for circular dependencies
        try:
            self.get_deployment_order()
        except ValueError as e:
            issues["circular_dependencies"].append(str(e))

        # Check for missing configurations
        for project_key, project in self.projects.items():
            if not project["config"]:
                issues["missing_configs"].append(project_key)

        return issues

    def generate_workspace_config(self) -> Dict:
        """Generate workspace-level configuration."""
        config = {
            "workspace": {
                "version": "2.1",
                "projects": {},
                "teams": {},
                "dependencies": self.build_dependency_graph(),
                "shared_resources": {
                    k: list(v) for k, v in self.get_shared_resources().items()
                },
            }
        }

        # Add project summaries
        for project_key, project in self.projects.items():
            detector = project["detector"]
            metadata = detector.get_fleet_metadata()

            config["workspace"]["projects"][project_key] = {
                "name": project["name"],
                "team": project["team"],
                "type": detector.detect(),
                "path": str(project["path"].relative_to(self.workspace_root)),
                "components": detector.get_components(),
                "metadata": metadata,
            }

        # Add team summaries
        teams = {}
        for project_key, project in self.projects.items():
            team = project["team"]
            if team not in teams:
                teams[team] = []
            teams[team].append(project_key)

        config["workspace"]["teams"] = teams

        return config

    def deploy_workspace(
        self,
        target: str,
        teams: List[str] = None,
        projects: List[str] = None,
        strategy: str = "coordinated",
    ) -> Dict:
        """Deploy multiple projects in coordinated manner."""
        # Determine projects to deploy
        if projects:
            target_projects = projects
        elif teams:
            target_projects = []
            for team in teams:
                target_projects.extend(self.get_projects_by_team(team))
        else:
            target_projects = list(self.projects.keys())

        # Get deployment order
        deployment_order = self.get_deployment_order(target_projects)

        # Execute deployments
        results = {}

        for project_key in deployment_order:
            project = self.projects[project_key]

            # Use deployment service to avoid circular dependencies
            from ..services import deployment_service

            result = deployment_service.deploy_project(
                project_path=str(project["path"]),
                target=target,
                strategy=strategy,
            )

            results[project_key] = {
                "success": result.success,
                "result": result,
                "error": result.error if not result.success else None,
            }

            # Check if we should stop on failure
            if not result.success and strategy == "fail_fast":
                break

        return {
            "deployment_order": deployment_order,
            "results": results,
            "overall_success": all(r["success"] for r in results.values()),
        }

    def rollback_workspace(
        self, target: str, projects: List[str] = None
    ) -> Dict:
        """Rollback multiple projects in reverse deployment order."""
        if projects is None:
            projects = list(self.projects.keys())

        # Reverse deployment order for rollback
        deployment_order = self.get_deployment_order(projects)
        rollback_order = deployment_order[::-1]

        results = {}

        for project_key in rollback_order:
            project = self.projects[project_key]

            # Use deployment service for rollback to avoid circular dependencies
            from ..services import deployment_service

            result = deployment_service.rollback_project(
                project_path=str(project["path"]), target=target
            )

            results[project_key] = {
                "success": result.success,
                "result": result,
                "error": result.error if not result.success else None,
            }

        return {
            "rollback_order": rollback_order,
            "results": results,
            "overall_success": all(r["success"] for r in results.values()),
        }


def deploy_project(project_path: str, target: str, strategy: str) -> Dict:
    """Deploy a single project (placeholder for actual deployment logic)."""
    # This would integrate with the actual deploy command
    return {"status": "deployed", "target": target, "strategy": strategy}


def rollback_project(project_path: str, target: str) -> Dict:
    """Rollback a single project (placeholder for actual rollback logic)."""
    # This would integrate with the actual rollback command
    return {"status": "rolled_back", "target": target}
