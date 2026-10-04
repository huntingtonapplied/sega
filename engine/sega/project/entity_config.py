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
SEGA ENTITY CONFIG DISCOVERY
==============================================================================
File: engine/sega/project/entity_config.py
Purpose: Discover and load sega.yaml configs from user workspace entities
Dependencies: os, yaml, pathlib
Usage: discovery = EntityConfigDiscovery(workspace_root); configs = discovery.discover_all()

This module allows SEGA to discover entity configurations from the user's
workspace (e.g., devuser/) rather than having configs embedded in SEGA itself.

Supported entity structures:
- example-org/fleet/sega.yaml
- example-org/acme/sega.yaml
- example_studio/sega.yaml
==============================================================================
"""

import os
import yaml
from typing import Dict, Optional, List, Any
from pathlib import Path
from dataclasses import dataclass, field


@dataclass
class EntityConfig:
    """Represents a parsed entity sega.yaml configuration."""
    
    name: str
    path: Path
    config: Dict[str, Any]
    
    # Parsed fields from config
    parent: Optional[str] = None
    domain: Optional[str] = None
    description: Optional[str] = None
    
    # Platform configurations
    platforms: Dict[str, Dict[str, Any]] = field(default_factory=dict)
    
    # Projects defined in this entity
    projects: Dict[str, Dict[str, Any]] = field(default_factory=dict)
    
    # Deployment settings
    deployment: Dict[str, Any] = field(default_factory=dict)
    
    def __post_init__(self):
        """Parse config into structured fields."""
        entity = self.config.get("entity", {})
        self.parent = entity.get("parent")
        self.domain = entity.get("domain")
        self.description = entity.get("description")
        
        self.platforms = self.config.get("platforms", {})
        self.projects = self.config.get("projects", {})
        self.deployment = self.config.get("deployment", {})
    
    def get_enabled_platforms(self) -> List[str]:
        """Get list of enabled platforms for this entity."""
        enabled = []
        for platform, config in self.platforms.items():
            if config.get("enabled", False):
                enabled.append(platform)
        return enabled
    
    def get_platform_config(self, platform: str) -> Optional[Dict[str, Any]]:
        """Get configuration for a specific platform."""
        return self.platforms.get(platform)
    
    def get_project(self, project_name: str) -> Optional[Dict[str, Any]]:
        """Get configuration for a specific project."""
        return self.projects.get(project_name)
    
    def get_project_platform(self, project_name: str) -> Optional[str]:
        """Get the primary platform for a project."""
        project = self.projects.get(project_name)
        if project:
            return project.get("primary_platform")
        return None


class EntityConfigDiscovery:
    """Discovers and loads entity configurations from a workspace."""
    
    # Known entity directory patterns
    ENTITY_PATTERNS = [
        "example-org/*/sega.yaml",
        "example_studio/sega.yaml",
        "*/sega.yaml",  # Catch-all for other entities
    ]
    
    # Environment variable for workspace root
    WORKSPACE_ENV_VAR = "DEV_ROOT"
    
    def __init__(self, workspace_root: Optional[str] = None):
        """Initialize with workspace root directory.
        
        Args:
            workspace_root: Path to workspace root. If None, will try to
                           determine from DEV_ROOT env var or common locations.
        """
        self.workspace_root = self._resolve_workspace_root(workspace_root)
        self._config_cache: Dict[str, EntityConfig] = {}
    
    def _resolve_workspace_root(self, workspace_root: Optional[str]) -> Path:
        """Resolve the workspace root directory."""
        if workspace_root:
            return Path(workspace_root).resolve()
        
        # Try environment variable
        env_root = os.environ.get(self.WORKSPACE_ENV_VAR)
        if env_root:
            return Path(env_root).resolve()
        
        # Try common locations
        home = Path.home()
        common_locations = [
            home / "devuser",
            home / "workspace" / "devuser",
        ]
        
        for loc in common_locations:
            if loc.exists() and loc.is_dir():
                return loc
        
        # Fall back to current directory
        return Path.cwd()
    
    def discover_all(self) -> Dict[str, EntityConfig]:
        """Discover all entity configurations in the workspace.
        
        Returns:
            Dict mapping entity names to their configurations
        """
        entities = {}
        
        # Search for sega.yaml files in entity directories
        for pattern in self.ENTITY_PATTERNS:
            for config_path in self.workspace_root.glob(pattern):
                if config_path.is_file():
                    entity_config = self._load_entity_config(config_path)
                    if entity_config:
                        entities[entity_config.name] = entity_config
        
        self._config_cache = entities
        return entities
    
    def get_entity(self, entity_name: str) -> Optional[EntityConfig]:
        """Get a specific entity configuration.
        
        Args:
            entity_name: Name of the entity (e.g., 'fleet', 'acme', 'example_studio')
            
        Returns:
            EntityConfig if found, None otherwise
        """
        # Check cache first
        if entity_name in self._config_cache:
            return self._config_cache[entity_name]
        
        # Discover if cache is empty
        if not self._config_cache:
            self.discover_all()
        
        return self._config_cache.get(entity_name)
    
    def get_project_config(
        self,
        entity_name: str,
        project_name: str,
    ) -> Optional[Dict[str, Any]]:
        """Get configuration for a specific project within an entity.
        
        Args:
            entity_name: Name of the entity
            project_name: Name of the project
            
        Returns:
            Project configuration dict if found, None otherwise
        """
        entity = self.get_entity(entity_name)
        if entity:
            return entity.get_project(project_name)
        return None
    
    def get_platform_for_project(
        self,
        entity_name: str,
        project_name: str,
    ) -> Optional[str]:
        """Get the deployment platform for a specific project.
        
        Args:
            entity_name: Name of the entity
            project_name: Name of the project
            
        Returns:
            Platform name (e.g., 'vercel', 'firebase') if found, None otherwise
        """
        entity = self.get_entity(entity_name)
        if entity:
            return entity.get_project_platform(project_name)
        return None
    
    def _load_entity_config(self, config_path: Path) -> Optional[EntityConfig]:
        """Load and parse an entity configuration file.
        
        Args:
            config_path: Path to sega.yaml file
            
        Returns:
            EntityConfig if successfully loaded, None otherwise
        """
        try:
            with open(config_path) as f:
                config = yaml.safe_load(f)
            
            if not config:
                return None
            
            # Determine entity name from config or path
            entity_info = config.get("entity", {})
            entity_name = entity_info.get("name")
            
            if not entity_name:
                # Derive from path
                # e.g., example-org/acme/sega.yaml -> acme
                # e.g., example_studio/sega.yaml -> example_studio
                parent_dir = config_path.parent.name
                if parent_dir == "sega.yaml":
                    parent_dir = config_path.parent.parent.name
                entity_name = parent_dir
            
            return EntityConfig(
                name=entity_name,
                path=config_path,
                config=config,
            )
            
        except (yaml.YAMLError, IOError, OSError) as e:
            # Log error but don't crash
            import logging
            logging.warning(f"Failed to load entity config {config_path}: {e}")
            return None
    
    def list_entities(self) -> List[str]:
        """List all discovered entity names."""
        if not self._config_cache:
            self.discover_all()
        return list(self._config_cache.keys())
    
    def list_projects(self, entity_name: str) -> List[str]:
        """List all projects in an entity."""
        entity = self.get_entity(entity_name)
        if entity:
            return list(entity.projects.keys())
        return []
    
    def get_deployment_config(
        self,
        entity_name: str,
        project_name: str,
        target: str = "production",
    ) -> Dict[str, Any]:
        """Get complete deployment configuration for a project.
        
        Merges entity-level and project-level settings.
        
        Args:
            entity_name: Name of the entity
            project_name: Name of the project
            target: Deployment target (development, staging, production)
            
        Returns:
            Merged deployment configuration
        """
        entity = self.get_entity(entity_name)
        if not entity:
            return {}
        
        project = entity.get_project(project_name)
        if not project:
            return {}
        
        # Get platform
        platform = project.get("primary_platform", "vercel")
        platform_config = entity.get_platform_config(platform) or {}
        
        # Get environment-specific settings
        env_settings = entity.deployment.get("environments", {}).get(target, {})
        
        # Merge configurations
        return {
            "entity": entity_name,
            "project": project_name,
            "platform": platform,
            "platform_config": platform_config.get("defaults", {}),
            "project_config": project.get("platforms", {}).get(platform, {}),
            "environment": env_settings,
            "target": target,
            "repository": project.get("repository"),
        }


# Singleton instance for convenience
_discovery_instance: Optional[EntityConfigDiscovery] = None


def get_entity_discovery(workspace_root: Optional[str] = None) -> EntityConfigDiscovery:
    """Get the entity config discovery instance.
    
    Args:
        workspace_root: Optional workspace root path
        
    Returns:
        EntityConfigDiscovery instance
    """
    global _discovery_instance
    
    if _discovery_instance is None or workspace_root:
        _discovery_instance = EntityConfigDiscovery(workspace_root)
    
    return _discovery_instance


def discover_entities(workspace_root: Optional[str] = None) -> Dict[str, EntityConfig]:
    """Convenience function to discover all entities.
    
    Args:
        workspace_root: Optional workspace root path
        
    Returns:
        Dict mapping entity names to configurations
    """
    discovery = get_entity_discovery(workspace_root)
    return discovery.discover_all()


def get_project_deployment_config(
    entity_name: str,
    project_name: str,
    target: str = "production",
    workspace_root: Optional[str] = None,
) -> Dict[str, Any]:
    """Convenience function to get deployment config for a project.
    
    Args:
        entity_name: Name of the entity
        project_name: Name of the project
        target: Deployment target
        workspace_root: Optional workspace root path
        
    Returns:
        Deployment configuration dict
    """
    discovery = get_entity_discovery(workspace_root)
    return discovery.get_deployment_config(entity_name, project_name, target)
