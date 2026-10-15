#!/usr/bin/env python3
# Copyright 2022-2026 Huntington Applied
# License: Apache-2.0
#
# SEGA Project Configuration Manager
# Manages fleet-projects.json configuration file
#
# AUTHORITATIVE REFERENCES:
# - Port Allocation Standards: /docs/standards/infrastructure/PORT_ALLOCATION_STANDARDS.md
# - FLEET Project Overview: /docs/references/FLEET_PROJECT_OVERVIEW.md

"""
SEGA Project Configuration Manager

Provides CRUD operations for fleet-projects.json with:
- Safe read/write operations
- Automatic backup before writes
- Validation integration
- Atomic file updates
"""

import json
import shutil
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

from .validators import ConfigValidator, ValidationResult


class ProjectConfigError(Exception):
    """Raised when configuration operations fail"""
    pass


def _default_registry_paths() -> List[Path]:
    """Candidate locations for the projects-registry JSON.

    Workspace-relative paths come from the `[fleet] project_registry_paths`
    config list (ships empty for new installs).
    """
    try:
        from .loader import get_config
        rel_paths = get_config().fleet.project_registry_paths
    except Exception:
        rel_paths = []
    root = Path.home() / "fleet"
    return [root / rel for rel in rel_paths]


class ProjectConfigManager:
    """
    Manages the fleet project registry stored in fleet-projects.json.

    Provides safe CRUD operations with automatic backups, validation,
    and atomic file updates.
    """

    DEFAULT_CONFIG_PATHS = _default_registry_paths()


    BACKUP_DIR = Path.home() / ".sega" / "config" / "backups"
    MAX_BACKUPS = 10
    
    def __init__(self, config_path: Optional[Path] = None):
        """
        Initialize configuration manager.
        
        Args:
            config_path: Optional path to fleet-projects.json.
                        If not provided, searches standard locations.
        """
        self.config_path = self._find_config_path(config_path)
        self.validator = ConfigValidator()
        self._ensure_backup_dir()
        self._config_cache: Optional[Dict[str, Any]] = None
    
    def _find_config_path(self, config_path: Optional[Path]) -> Path:
        """
        Find fleet-projects.json configuration file.
        
        Args:
            config_path: Optional explicit path
            
        Returns:
            Path to configuration file
            
        Raises:
            ProjectConfigError: If config file not found
        """
        if config_path:
            path = Path(config_path).expanduser()
            if path.exists():
                return path
            raise ProjectConfigError(f"Configuration file not found: {config_path}")
        
        # Search standard locations
        for path in self.DEFAULT_CONFIG_PATHS:
            if path.exists():
                return path
        
        raise ProjectConfigError(
            f"Configuration file not found. Searched: {', '.join(str(p) for p in self.DEFAULT_CONFIG_PATHS)}"
        )
    
    def _ensure_backup_dir(self):
        """Create backup directory if it doesn't exist"""
        self.BACKUP_DIR.mkdir(parents=True, exist_ok=True)
    
    def load_config(self, force_reload: bool = False) -> Dict[str, Any]:
        """
        Load and parse configuration from fleet-projects.json.
        
        Args:
            force_reload: Force reload from disk (ignore cache)
            
        Returns:
            Parsed configuration dictionary
            
        Raises:
            ProjectConfigError: If loading or parsing fails
        """
        if self._config_cache and not force_reload:
            return self._config_cache
        
        try:
            with open(self.config_path, 'r', encoding='utf-8') as f:
                config = json.load(f)
            
            # Validate structure
            if 'projects' not in config:
                raise ProjectConfigError("Invalid config: missing 'projects' key")
            
            if not isinstance(config['projects'], list):
                raise ProjectConfigError("Invalid config: 'projects' must be a list")
            
            self._config_cache = config
            return config
            
        except json.JSONDecodeError as e:
            raise ProjectConfigError(f"Invalid JSON in {self.config_path}: {e}")
        except Exception as e:
            raise ProjectConfigError(f"Failed to load config: {e}")
    
    def get_all_projects(self) -> List[Dict[str, Any]]:
        """
        Get all projects from configuration.
        
        Returns:
            List of project dictionaries
        """
        config = self.load_config()
        return config.get('projects', [])
    
    def get_project(self, slug: str) -> Optional[Dict[str, Any]]:
        """
        Get single project by slug.
        
        Args:
            slug: Project slug identifier
            
        Returns:
            Project dictionary or None if not found
        """
        projects = self.get_all_projects()
        for project in projects:
            if project.get('slug') == slug:
                return project
        return None
    
    def find_projects(self, **filters) -> List[Dict[str, Any]]:
        """
        Find projects matching filter criteria.
        
        Args:
            **filters: Field=value pairs to filter by
            
        Returns:
            List of matching projects
            
        Example:
            find_projects(status='demo', category='Simulation Engine')
        """
        projects = self.get_all_projects()
        
        if not filters:
            return projects
        
        results = []
        for project in projects:
            match = True
            for key, value in filters.items():
                if project.get(key) != value:
                    match = False
                    break
            if match:
                results.append(project)
        
        return results
    
    def create_backup(self) -> Path:
        """
        Create timestamped backup of current configuration.
        
        Returns:
            Path to backup file
            
        Raises:
            ProjectConfigError: If backup creation fails
        """
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        backup_filename = f"fleet-projects.backup.{timestamp}.json"
        backup_path = self.BACKUP_DIR / backup_filename
        
        try:
            shutil.copy2(self.config_path, backup_path)
            self._cleanup_old_backups()
            return backup_path
        except Exception as e:
            raise ProjectConfigError(f"Failed to create backup: {e}")
    
    def _cleanup_old_backups(self):
        """Remove old backups, keeping only MAX_BACKUPS most recent"""
        backups = sorted(
            self.BACKUP_DIR.glob("fleet-projects.backup.*.json"),
            key=lambda p: p.stat().st_mtime,
            reverse=True
        )
        
        # Remove backups beyond MAX_BACKUPS
        for old_backup in backups[self.MAX_BACKUPS:]:
            old_backup.unlink()
    
    def list_backups(self) -> List[Path]:
        """
        List available backups, most recent first.
        
        Returns:
            List of backup file paths
        """
        backups = sorted(
            self.BACKUP_DIR.glob("fleet-projects.backup.*.json"),
            key=lambda p: p.stat().st_mtime,
            reverse=True
        )
        return backups
    
    def rollback(self, backup_file: Optional[Path] = None) -> bool:
        """
        Rollback to a previous backup.
        
        Args:
            backup_file: Specific backup to restore. If None, uses most recent.
            
        Returns:
            True if rollback successful
            
        Raises:
            ProjectConfigError: If rollback fails
        """
        if backup_file:
            backup_path = Path(backup_file)
            if not backup_path.exists():
                raise ProjectConfigError(f"Backup file not found: {backup_file}")
        else:
            backups = self.list_backups()
            if not backups:
                raise ProjectConfigError("No backups available")
            backup_path = backups[0]
        
        try:
            # Validate backup before restoring
            with open(backup_path, 'r', encoding='utf-8') as f:
                backup_config = json.load(f)
            
            result = self.validator.validate_all(backup_config)
            if not result.is_valid:
                raise ProjectConfigError(
                    f"Backup validation failed: {', '.join(result.errors)}"
                )
            
            # Create backup of current state before rollback
            self.create_backup()
            
            # Restore backup
            shutil.copy2(backup_path, self.config_path)
            
            # Clear cache
            self._config_cache = None
            
            return True
            
        except Exception as e:
            raise ProjectConfigError(f"Rollback failed: {e}")
    
    def update_project(self, slug: str, updates: Dict[str, Any]) -> bool:
        """
        Update a project's fields.
        
        Args:
            slug: Project slug to update
            updates: Dictionary of field=value updates
            
        Returns:
            True if update successful
            
        Raises:
            ProjectConfigError: If project not found or update fails
        """
        config = self.load_config(force_reload=True)
        projects = config['projects']
        
        # Find project
        project_index = None
        for i, project in enumerate(projects):
            if project.get('slug') == slug:
                project_index = i
                break
        
        if project_index is None:
            raise ProjectConfigError(f"Project not found: {slug}")
        
        # Apply updates
        projects[project_index].update(updates)
        
        # Validate before saving
        result = self.validator.validate_all(config)
        if not result.is_valid:
            raise ProjectConfigError(
                f"Validation failed: {', '.join(result.errors)}"
            )
        
        # Save with backup
        return self.save_config(config, backup=True)
    
    def save_config(self, config: Dict[str, Any], backup: bool = True) -> bool:
        """
        Save configuration to disk with optional backup.
        
        Args:
            config: Configuration dictionary to save
            backup: Create backup before saving (default: True)
            
        Returns:
            True if save successful
            
        Raises:
            ProjectConfigError: If save fails
        """
        # Validate before saving
        result = self.validator.validate_all(config)
        if not result.is_valid:
            raise ProjectConfigError(
                f"Validation failed: {', '.join(result.errors)}"
            )
        
        # Atomic write using temporary file
        temp_path = self.config_path.with_suffix('.tmp')
        
        try:
            # Create backup if requested
            if backup:
                self.create_backup()
            
            with open(temp_path, 'w', encoding='utf-8') as f:
                json.dump(config, f, indent=2, ensure_ascii=False)
            
            # Atomic rename
            temp_path.replace(self.config_path)
            
            # Clear cache
            self._config_cache = None
            
            return True
            
        except Exception as e:
            # Clean up temp file if it exists
            if temp_path.exists():
                temp_path.unlink()
            raise ProjectConfigError(f"Failed to save config: {e}")
    
    def export_config(self, output_path: Path) -> bool:
        """
        Export configuration to a file.
        
        Args:
            output_path: Path to export file
            
        Returns:
            True if export successful
        """
        config = self.load_config()
        
        try:
            output_path = Path(output_path)
            with open(output_path, 'w', encoding='utf-8') as f:
                json.dump(config, f, indent=2, ensure_ascii=False)
            return True
        except Exception as e:
            raise ProjectConfigError(f"Failed to export config: {e}")
    
    def get_statistics(self) -> Dict[str, Any]:
        """
        Get statistics about the configuration.
        
        Returns:
            Dictionary with statistics
        """
        projects = self.get_all_projects()
        
        # Count by status
        status_counts = {}
        for project in projects:
            status = project.get('status', 'unknown')
            status_counts[status] = status_counts.get(status, 0) + 1
        
        # Count by category
        category_counts = {}
        for project in projects:
            category = project.get('category', 'unknown')
            category_counts[category] = category_counts.get(category, 0) + 1
        
        # Count by lab
        lab_counts = {}
        for project in projects:
            lab = project.get('lab_assignment', 'unknown')
            lab_counts[lab] = lab_counts.get(lab, 0) + 1
        
        return {
            'total_projects': len(projects),
            'by_status': status_counts,
            'by_category': category_counts,
            'by_lab': lab_counts,
            'config_path': str(self.config_path),
            'backup_count': len(self.list_backups()),
        }
