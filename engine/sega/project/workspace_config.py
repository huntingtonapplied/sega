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
Workspace configuration definitions for SEGA

Provides flexible, configuration-driven workspace management.
"""

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Set
import yaml
import json
import logging

logger = logging.getLogger(__name__)


@dataclass
class ProjectDefinition:
    """Definition of a project within a workspace"""
    name: str
    path: str
    type: Optional[str] = None
    team: Optional[str] = None
    description: Optional[str] = None
    dependencies: List[str] = field(default_factory=list)
    ports: Dict[str, int] = field(default_factory=dict)
    components: List[str] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary representation"""
        return {
            'name': self.name,
            'path': self.path,
            'type': self.type,
            'team': self.team,
            'description': self.description,
            'dependencies': self.dependencies,
            'ports': self.ports,
            'components': self.components,
            'metadata': self.metadata
        }


@dataclass
class TeamDefinition:
    """Definition of a team within a workspace"""
    name: str
    description: Optional[str] = None
    projects: List[str] = field(default_factory=list)
    lead: Optional[str] = None
    contact: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary representation"""
        return {
            'name': self.name,
            'description': self.description,
            'projects': self.projects,
            'lead': self.lead,
            'contact': self.contact,
            'metadata': self.metadata
        }


@dataclass
class WorkspaceConfig:
    """Configuration for a SEGA-managed workspace"""
    
    # Basic information
    name: str
    version: str = "1.0"
    description: Optional[str] = None
    
    # Structure configuration
    root_path: Optional[Path] = None
    project_discovery: Dict[str, Any] = field(default_factory=dict)
    
    # Projects and teams
    projects: Dict[str, ProjectDefinition] = field(default_factory=dict)
    teams: Dict[str, TeamDefinition] = field(default_factory=dict)
    
    # Infrastructure configuration
    shared_infrastructure: Dict[str, Any] = field(default_factory=dict)
    environments: List[str] = field(default_factory=lambda: ['development', 'staging', 'production'])
    
    # Deployment configuration
    deployment: Dict[str, Any] = field(default_factory=dict)
    
    # Git configuration
    git: Dict[str, Any] = field(default_factory=dict)
    
    # Testing configuration
    testing: Dict[str, Any] = field(default_factory=dict)
    
    # Additional metadata
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    @classmethod
    def from_file(cls, filepath: Path) -> 'WorkspaceConfig':
        """Load workspace configuration from file"""
        if not filepath.exists():
            raise FileNotFoundError(f"Configuration file not found: {filepath}")
        
        with open(filepath, 'r') as f:
            if filepath.suffix == '.yaml' or filepath.suffix == '.yml':
                data = yaml.safe_load(f)
            elif filepath.suffix == '.json':
                data = json.load(f)
            else:
                raise ValueError(f"Unsupported file format: {filepath.suffix}")
        
        return cls.from_dict(data)
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'WorkspaceConfig':
        """Create workspace configuration from dictionary"""
        config = cls(
            name=data.get('name', 'workspace'),
            version=data.get('version', '1.0'),
            description=data.get('description')
        )
        
        # Set root path
        if 'root_path' in data:
            config.root_path = Path(data['root_path'])
        
        # Load project discovery rules
        config.project_discovery = data.get('project_discovery', {})
        
        # Load projects
        projects_data = data.get('projects', {})
        for proj_name, proj_data in projects_data.items():
            if isinstance(proj_data, dict):
                config.projects[proj_name] = ProjectDefinition(
                    name=proj_name,
                    path=proj_data.get('path', proj_name),
                    type=proj_data.get('type'),
                    team=proj_data.get('team'),
                    description=proj_data.get('description'),
                    dependencies=proj_data.get('dependencies', []),
                    ports=proj_data.get('ports', {}),
                    components=proj_data.get('components', []),
                    metadata=proj_data.get('metadata', {})
                )
        
        # Load teams
        teams_data = data.get('teams', {})
        for team_name, team_data in teams_data.items():
            if isinstance(team_data, dict):
                config.teams[team_name] = TeamDefinition(
                    name=team_name,
                    description=team_data.get('description'),
                    projects=team_data.get('projects', []),
                    lead=team_data.get('lead'),
                    contact=team_data.get('contact'),
                    metadata=team_data.get('metadata', {})
                )
        
        # Load other configurations
        config.shared_infrastructure = data.get('shared_infrastructure', {})
        config.environments = data.get('environments', ['development', 'staging', 'production'])
        config.deployment = data.get('deployment', {})
        config.git = data.get('git', {})
        config.testing = data.get('testing', {})
        config.metadata = data.get('metadata', {})
        
        return config
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary representation"""
        return {
            'name': self.name,
            'version': self.version,
            'description': self.description,
            'root_path': str(self.root_path) if self.root_path else None,
            'project_discovery': self.project_discovery,
            'projects': {
                name: proj.to_dict() 
                for name, proj in self.projects.items()
            },
            'teams': {
                name: team.to_dict() 
                for name, team in self.teams.items()
            },
            'shared_infrastructure': self.shared_infrastructure,
            'environments': self.environments,
            'deployment': self.deployment,
            'git': self.git,
            'testing': self.testing,
            'metadata': self.metadata
        }
    
    def save(self, filepath: Path) -> None:
        """Save configuration to file"""
        data = self.to_dict()
        
        with open(filepath, 'w') as f:
            if filepath.suffix == '.yaml' or filepath.suffix == '.yml':
                yaml.dump(data, f, default_flow_style=False, sort_keys=False)
            elif filepath.suffix == '.json':
                json.dump(data, f, indent=2)
            else:
                raise ValueError(f"Unsupported file format: {filepath.suffix}")
    
    def get_project(self, name: str) -> Optional[ProjectDefinition]:
        """Get project by name"""
        return self.projects.get(name)
    
    def get_team(self, name: str) -> Optional[TeamDefinition]:
        """Get team by name"""
        return self.teams.get(name)
    
    def get_projects_by_team(self, team_name: str) -> List[ProjectDefinition]:
        """Get all projects for a team"""
        return [
            proj for proj in self.projects.values()
            if proj.team == team_name
        ]
    
    def get_project_dependencies(self, project_name: str) -> List[ProjectDefinition]:
        """Get dependencies for a project"""
        project = self.get_project(project_name)
        if not project:
            return []
        
        dependencies = []
        for dep_name in project.dependencies:
            dep_project = self.get_project(dep_name)
            if dep_project:
                dependencies.append(dep_project)
        
        return dependencies
    
    def validate(self) -> List[str]:
        """Validate configuration consistency"""
        errors = []
        
        # Check project references in teams
        for team in self.teams.values():
            for proj_name in team.projects:
                if proj_name not in self.projects:
                    errors.append(f"Team {team.name} references unknown project: {proj_name}")
        
        # Check dependency references
        for project in self.projects.values():
            for dep_name in project.dependencies:
                if dep_name not in self.projects:
                    errors.append(f"Project {project.name} has unknown dependency: {dep_name}")
        
        # Check for circular dependencies
        for project in self.projects.values():
            visited = set()
            if self._has_circular_dependency(project.name, visited):
                errors.append(f"Circular dependency detected involving project: {project.name}")
        
        return errors
    
    def _has_circular_dependency(self, project_name: str, visited: Set[str]) -> bool:
        """Check for circular dependencies"""
        if project_name in visited:
            return True
        
        visited.add(project_name)
        project = self.get_project(project_name)
        
        if project:
            for dep_name in project.dependencies:
                if self._has_circular_dependency(dep_name, visited.copy()):
                    return True
        
        return False