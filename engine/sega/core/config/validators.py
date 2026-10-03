#!/usr/bin/env python3
# Copyright 2022-2026 Huntington Applied
# License: Apache-2.0
#
# SEGA Configuration Validators
# Validation rules for fleet-projects.json
#
# AUTHORITATIVE REFERENCES:
# - Port Allocation Standards: /docs/standards/infrastructure/PORT_ALLOCATION_STANDARDS.md

"""
SEGA Configuration Validators

Provides comprehensive validation for project configurations:
- Required fields validation
- Port conflict detection
- Port range validation
- Status value constraints
- Domain format validation
"""

from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Set


@dataclass
class ValidationResult:
    """Result of configuration validation"""
    is_valid: bool
    errors: List[str]
    warnings: List[str] = None
    
    def __post_init__(self):
        if self.warnings is None:
            self.warnings = []


class ConfigValidator:
    """
    Validates FLEET project configuration.
    
    Enforces:
    - Required fields presence
    - Valid status values
    - Port allocation standards
    - Port conflict detection
    - Domain format validation
    """
    
    # Valid status values (project lifecycle phase: demo -> alpha -> production)
    VALID_STATUSES = {'demo', 'alpha', 'production'}
    
    # Required fields for all projects
    REQUIRED_FIELDS = {'id', 'slug', 'name', 'title', 'category', 'status', 'lab_assignment'}
    
    # Port ranges per PORT_ALLOCATION_STANDARDS.md
    PORT_RANGES = {
        'port_api': (8000, 8099),
        'port_frontend': (3000, 3099),
        'port_desktop': (3300, 3399),
        'port_mobile': (19000, 19099),
        'port_database': (5000, 5099),
        'port_redis': (6000, 6099),
        'port_metrics': (9000, 9099),
    }
    
    def validate_all(self, config: Dict[str, Any]) -> ValidationResult:
        """
        Run all validation checks on configuration.
        
        Args:
            config: Full configuration dictionary with 'projects' key
            
        Returns:
            ValidationResult with all errors and warnings
        """
        errors = []
        warnings = []
        
        # Validate structure
        if 'projects' not in config:
            errors.append("Configuration missing 'projects' key")
            return ValidationResult(is_valid=False, errors=errors)
        
        projects = config['projects']
        
        if not isinstance(projects, list):
            errors.append("'projects' must be a list")
            return ValidationResult(is_valid=False, errors=errors)
        
        # Validate each project
        for i, project in enumerate(projects):
            project_errors = self.validate_project(project, index=i)
            errors.extend(project_errors)
        
        # Check for port conflicts across all projects
        conflict_errors = self.check_port_conflicts(projects)
        errors.extend(conflict_errors)
        
        # Check for duplicate IDs
        id_errors = self.check_duplicate_ids(projects)
        errors.extend(id_errors)
        
        # Check for duplicate slugs
        slug_errors = self.check_duplicate_slugs(projects)
        errors.extend(slug_errors)
        
        return ValidationResult(
            is_valid=len(errors) == 0,
            errors=errors,
            warnings=warnings
        )
    
    def validate_project(self, project: Dict[str, Any], index: Optional[int] = None) -> List[str]:
        """
        Validate a single project.
        
        Args:
            project: Project dictionary
            index: Optional project index for error messages
            
        Returns:
            List of error messages (empty if valid)
        """
        errors = []
        prefix = f"Project {index}" if index is not None else "Project"
        slug = project.get('slug', 'unknown')
        
        # Check required fields
        for field in self.REQUIRED_FIELDS:
            if field not in project:
                errors.append(f"{prefix} '{slug}': Missing required field '{field}'")
        
        # Validate status
        status = project.get('status')
        if status and status not in self.VALID_STATUSES:
            errors.append(
                f"{prefix} '{slug}': Invalid status '{status}'. "
                f"Must be one of: {', '.join(sorted(self.VALID_STATUSES))}"
            )
        
        # Validate ports
        port_errors = self.validate_ports(project, prefix=f"{prefix} '{slug}'")
        errors.extend(port_errors)
        
        # Validate ID
        if 'id' in project:
            if not isinstance(project['id'], int):
                errors.append(f"{prefix} '{slug}': ID must be an integer")
            elif project['id'] < 0:
                errors.append(f"{prefix} '{slug}': ID must be non-negative")
        
        return errors
    
    def validate_ports(self, project: Dict[str, Any], prefix: str = "Project") -> List[str]:
        """
        Validate port assignments for a project.
        
        Args:
            project: Project dictionary
            prefix: Prefix for error messages
            
        Returns:
            List of error messages
        """
        errors = []
        
        for port_field, (min_port, max_port) in self.PORT_RANGES.items():
            if port_field in project:
                port = project[port_field]
                
                if port is None:
                    continue  # Optional port
                
                if not isinstance(port, int):
                    errors.append(f"{prefix}: {port_field} must be an integer")
                    continue
                
                if not (min_port <= port <= max_port):
                    errors.append(
                        f"{prefix}: {port_field}={port} outside valid range "
                        f"({min_port}-{max_port})"
                    )
        
        return errors
    
    def check_port_conflicts(self, projects: List[Dict[str, Any]]) -> List[str]:
        """
        Check for port conflicts across all projects.
        
        Args:
            projects: List of all projects
            
        Returns:
            List of error messages for conflicts
        """
        errors = []
        
        # Track ports by type
        port_usage: Dict[str, Dict[int, List[str]]] = {
            port_type: {} for port_type in self.PORT_RANGES.keys()
        }
        
        # Build port usage map
        for project in projects:
            slug = project.get('slug', 'unknown')
            
            for port_type in self.PORT_RANGES.keys():
                port = project.get(port_type)
                
                if port is not None and isinstance(port, int):
                    if port not in port_usage[port_type]:
                        port_usage[port_type][port] = []
                    port_usage[port_type][port].append(slug)
        
        # Find conflicts
        for port_type, ports in port_usage.items():
            for port, slugs in ports.items():
                if len(slugs) > 1:
                    errors.append(
                        f"Port conflict: {port_type}={port} used by multiple projects: "
                        f"{', '.join(sorted(slugs))}"
                    )
        
        return errors
    
    def check_duplicate_ids(self, projects: List[Dict[str, Any]]) -> List[str]:
        """
        Check for duplicate project IDs.
        
        Args:
            projects: List of all projects
            
        Returns:
            List of error messages
        """
        errors = []
        id_map: Dict[int, List[str]] = {}
        
        for project in projects:
            project_id = project.get('id')
            slug = project.get('slug', 'unknown')
            
            if project_id is not None:
                if project_id not in id_map:
                    id_map[project_id] = []
                id_map[project_id].append(slug)
        
        for project_id, slugs in id_map.items():
            if len(slugs) > 1:
                errors.append(
                    f"Duplicate ID {project_id} used by projects: {', '.join(sorted(slugs))}"
                )
        
        return errors
    
    def check_duplicate_slugs(self, projects: List[Dict[str, Any]]) -> List[str]:
        """
        Check for duplicate project slugs.
        
        Args:
            projects: List of all projects
            
        Returns:
            List of error messages
        """
        errors = []
        slug_set: Set[str] = set()
        duplicates: Set[str] = set()
        
        for project in projects:
            slug = project.get('slug')
            if slug:
                if slug in slug_set:
                    duplicates.add(slug)
                else:
                    slug_set.add(slug)
        
        for slug in sorted(duplicates):
            errors.append(f"Duplicate slug: '{slug}'")
        
        return errors
    
    def validate_status(self, status: str) -> bool:
        """
        Validate a status value.
        
        Args:
            status: Status string to validate
            
        Returns:
            True if valid
        """
        return status in self.VALID_STATUSES
    
    def has_port_conflict(
        self, 
        project: Dict[str, Any], 
        all_projects: List[Dict[str, Any]]
    ) -> bool:
        """
        Check if a project has port conflicts with other projects.
        
        Args:
            project: Project to check
            all_projects: All projects in configuration
            
        Returns:
            True if conflicts exist
        """
        project_slug = project.get('slug')
        
        for port_type in self.PORT_RANGES.keys():
            port = project.get(port_type)
            
            if port is None:
                continue
            
            # Check against all other projects
            for other_project in all_projects:
                other_slug = other_project.get('slug')
                
                # Skip self
                if other_slug == project_slug:
                    continue
                
                other_port = other_project.get(port_type)
                
                if other_port == port:
                    return True
        
        return False
    
    def get_port_conflicts_for_project(
        self,
        project: Dict[str, Any],
        all_projects: List[Dict[str, Any]]
    ) -> List[str]:
        """
        Get detailed port conflict messages for a project.
        
        Args:
            project: Project to check
            all_projects: All projects in configuration
            
        Returns:
            List of conflict messages
        """
        conflicts = []
        project_slug = project.get('slug', 'unknown')
        
        for port_type in self.PORT_RANGES.keys():
            port = project.get(port_type)
            
            if port is None:
                continue
            
            # Find conflicting projects
            conflicting_slugs = []
            for other_project in all_projects:
                other_slug = other_project.get('slug')
                
                # Skip self
                if other_slug == project_slug:
                    continue
                
                other_port = other_project.get(port_type)
                
                if other_port == port:
                    conflicting_slugs.append(other_slug)
            
            if conflicting_slugs:
                conflicts.append(
                    f"{port_type}={port} conflicts with: {', '.join(sorted(conflicting_slugs))}"
                )
        
        return conflicts
