#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# Copyright 2025 SEGA

"""
SEGA SYSTEM TYPES DEFINITION
===============================================================================
File: src/sega/installation/system_types.py
Purpose: System type definitions and management for FLEET installations

Description: Loads system type definitions from config/sega.toml and provides
validation and installation utilities. The TOML file is the single source of
truth for system type configurations.

Configuration: config/sega.toml [system_types.*] sections
===============================================================================
"""

from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional, Any
import platform

try:
    import tomllib
except ImportError:
    import tomli as tomllib


@dataclass
class SystemType:
    """Definition of an FLEET system type with all requirements and capabilities."""
    
    name: str
    description: str
    os_types: List[str]  # ['macos', 'ubuntu', 'linux']
    technology_stacks: List[str]  # ['python', 'rust', 'nodejs', 'hardware']
    package_requirements: Dict[str, List[str]]  # os_type -> package list
    service_requirements: List[str]  # Required services
    vpn_mode: str  # 'server', 'client', 'none'
    storage_requirements: Dict[str, str]  # mount_point -> requirement
    security_profile: str  # 'development', 'production', 'minimal'
    ansible_roles: List[str] = field(default_factory=list)  # Required Ansible roles
    ansible_playbook: Optional[str] = None  # Ansible playbook for this system type
    resource_requirements: Dict[str, Any] = field(default_factory=dict)  # CPU, RAM, disk
    
    def validate_system_compatibility(self) -> Dict[str, Any]:
        """Validate if current system can support this system type."""
        issues = []
        requirements = []
        
        # Check OS compatibility
        current_os = self._detect_current_os()
        if current_os not in self.os_types:
            issues.append({
                'severity': 'error',
                'message': f"OS '{current_os}' not supported. Requires: {', '.join(self.os_types)}"
            })
        else:
            requirements.append({
                'description': f"Operating System ({current_os})",
                'satisfied': True
            })
        
        # Check resource requirements
        if self.resource_requirements:
            for resource, requirement in self.resource_requirements.items():
                satisfied = self._check_resource_requirement(resource, requirement)
                requirements.append({
                    'description': f"{resource.upper()}: {requirement}",
                    'satisfied': satisfied
                })
                if not satisfied:
                    issues.append({
                        'severity': 'warning',
                        'message': f"Insufficient {resource}: requires {requirement}"
                    })
        
        return {
            'compatible': len([i for i in issues if i['severity'] == 'error']) == 0,
            'issues': issues,
            'requirements': requirements
        }
    
    def get_ansible_variables(self, project_requirements: Dict[str, Any]) -> Dict[str, Any]:
        """Generate Ansible variables for this system type."""
        variables = {
            'system_type': self.name,
            'security_profile': self.security_profile,
            'vpn_mode': self.vpn_mode,
            'technology_stacks': self.technology_stacks,
            'service_requirements': self.service_requirements,
        }
        
        # Add project-specific variables
        variables.update(project_requirements)
        
        # Add storage configuration
        if self.storage_requirements:
            variables['storage_config'] = self.storage_requirements
        
        # Add system-specific configurations
        if 'server' in self.name:
            variables['install_monitoring'] = True
            variables['install_vpn_server'] = (self.vpn_mode == 'server')
        
        if 'engine' in self.name:
            variables['install_minimal'] = True
            variables['engine_type'] = self._get_engine_type()
        
        if 'platform' in self.name:
            variables['install_platform_services'] = True
        
        return variables
    
    def get_installation_steps(self) -> List[Dict[str, Any]]:
        """Get ordered list of installation steps for this system type."""
        steps = []
        
        # System preparation
        steps.append({
            'name': 'System Preparation',
            'description': 'Update system and install basic packages',
            'ansible_tasks': ['update_system', 'install_basic_packages']
        })
        
        # Package installation
        if self.package_requirements:
            steps.append({
                'name': 'Package Installation', 
                'description': f'Install {len(sum(self.package_requirements.values(), []))} packages',
                'ansible_tasks': ['install_packages']
            })
        
        # Storage setup
        if self.storage_requirements:
            steps.append({
                'name': 'Storage Configuration',
                'description': 'Configure data storage and mount points',
                'ansible_tasks': ['add_data_volume']
            })
        
        # VPN setup
        if self.vpn_mode != 'none':
            vpn_desc = 'VPN server' if self.vpn_mode == 'server' else 'VPN client'
            steps.append({
                'name': 'VPN Configuration',
                'description': f'Install and configure {vpn_desc}',
                'ansible_tasks': [f'openvpn_{self.vpn_mode}']
            })
        
        # Service installation
        if self.service_requirements:
            steps.append({
                'name': 'Service Installation',
                'description': f'Install and configure {len(self.service_requirements)} services',
                'ansible_tasks': ['install_services']
            })
        
        # Security hardening
        if self.security_profile in ['production', 'minimal']:
            steps.append({
                'name': 'Security Hardening',
                'description': f'Apply {self.security_profile} security profile',
                'ansible_tasks': ['configure_firewall', 'harden_system']
            })
        
        return steps
    
    def _detect_current_os(self) -> str:
        """Detect current operating system."""
        system = platform.system().lower()
        if system == 'darwin':
            return 'macos'
        elif system == 'linux':
            # Try to detect specific distribution
            try:
                with open('/etc/os-release', 'r') as f:
                    content = f.read()
                    if 'ubuntu' in content.lower():
                        return 'ubuntu'
                    else:
                        return 'linux'
            except FileNotFoundError:
                return 'linux'
        else:
            return system
    
    def _check_resource_requirement(self, resource: str, requirement: str) -> bool:
        """Check if system meets resource requirement."""
        # Placeholder implementation - would check actual system resources
        return True
    
    def _get_engine_type(self) -> str:
        """Determine engine type from the system type's Ansible roles/name.

        A system type whose Ansible roles install a Rust engine/platform is a
        'rust' system; hardware-flavoured names are 'hardware'; default python.
        """
        if any('rust' in role for role in self.ansible_roles):
            return 'rust'
        elif 'hardware' in self.name:
            return 'hardware'
        else:
            return 'python'


class SystemTypeManager:
    """Manager for all FLEET system types loaded from config/sega.toml."""

    # Default TOML config path relative to sega package
    TOML_CONFIG_PATH = Path(__file__).parent.parent.parent.parent / "config" / "sega.toml"

    def __init__(self, config_path: Optional[Path] = None):
        self._config_path = config_path or self.TOML_CONFIG_PATH
        self._system_types = self._load_system_types()

    def get_all_system_types(self) -> List[SystemType]:
        """Get all available system types."""
        return list(self._system_types.values())

    def get_system_type(self, name: str) -> Optional[SystemType]:
        """Get specific system type by name."""
        return self._system_types.get(name)

    def get_compatible_types(self, os_type: str = None) -> List[SystemType]:
        """Get system types compatible with specified OS."""
        if not os_type:
            os_type = self._detect_current_os()

        return [st for st in self._system_types.values()
                if os_type in st.os_types]

    def _load_system_types(self) -> Dict[str, SystemType]:
        """Load system type definitions from config/sega.toml."""
        system_types = {}

        if not self._config_path.exists():
            # Fallback: return empty dict if config not found
            return system_types

        with open(self._config_path, "rb") as f:
            config = tomllib.load(f)

        toml_types = config.get("system_types", {})

        for name, data in toml_types.items():
            system_types[name] = SystemType(
                name=name,
                description=data.get("description", ""),
                os_types=data.get("os_types", []),
                technology_stacks=data.get("technology_stacks", []),
                package_requirements=data.get("package_requirements", {}),
                service_requirements=data.get("service_requirements", []),
                vpn_mode=data.get("vpn_mode", "none"),
                storage_requirements=data.get("storage_requirements", {}),
                security_profile=data.get("security_profile", "development"),
                ansible_roles=data.get("ansible_roles", []),
                ansible_playbook=data.get("ansible_playbook"),
                resource_requirements=data.get("resource_requirements", {}),
            )

        return system_types

    def _detect_current_os(self) -> str:
        """Detect current operating system."""
        system = platform.system().lower()
        if system == 'darwin':
            return 'macos'
        elif system == 'linux':
            try:
                with open('/etc/os-release', 'r') as f:
                    content = f.read()
                    if 'ubuntu' in content.lower():
                        return 'ubuntu'
                    else:
                        return 'linux'
            except FileNotFoundError:
                return 'linux'
        else:
            return system