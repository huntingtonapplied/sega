#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# Copyright 2025 SEGA

"""
SEGA SYSTEM INSTALLER
===============================================================================
File: src/sega/installation/installer.py
Purpose: Core system installation orchestration and execution

Description: Orchestrates system installations using Ansible roles and provides
integration with existing SEGA deployment capabilities. Handles both local and
remote installations with project-agnostic configuration.
===============================================================================
"""

import os
import json
import subprocess
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional, Any
import platform
import logging

from .system_types import SystemType, SystemTypeManager


@dataclass
class InstallationResult:
    """Result of a system installation operation."""
    
    success: bool
    target: str
    message: str
    error: Optional[str] = None
    warnings: List[str] = None
    next_steps: List[str] = None
    installation_log: Optional[str] = None
    ansible_output: Optional[str] = None
    
    def __post_init__(self):
        if self.warnings is None:
            self.warnings = []
        if self.next_steps is None:
            self.next_steps = []


class SystemInstaller:
    """Core system installer for FLEET system types."""
    
    def __init__(self, logger: Optional[logging.Logger] = None):
        self.logger = logger or logging.getLogger(__name__)
        self.system_manager = SystemTypeManager()
        self._ansible_available = self._check_ansible_availability()
        
    def is_valid_target(self, target: str) -> bool:
        """Check if target system type is valid."""
        return self.system_manager.get_system_type(target) is not None
    
    def detect_recommended_target(self) -> Dict[str, Any]:
        """Auto-detect recommended system type for current environment."""
        current_system = self._get_current_system_info()
        detected_projects = self._detect_fleet_projects()
        
        recommendations = []
        
        # Get compatible system types
        compatible_types = self.system_manager.get_compatible_types()
        
        for system_type in compatible_types:
            confidence = self._calculate_recommendation_confidence(
                system_type, current_system, detected_projects
            )
            
            if confidence > 0.3:  # Only include reasonable recommendations
                reason = self._get_recommendation_reason(
                    system_type, current_system, detected_projects
                )
                recommendations.append({
                    'target': system_type.name,
                    'confidence': confidence,
                    'reason': reason
                })
        
        # Sort by confidence
        recommendations.sort(key=lambda x: x['confidence'], reverse=True)
        
        return {
            'current_system': current_system,
            'detected_projects': detected_projects,
            'recommendations': recommendations
        }
    
    def install_local(self, target: str, dry_run: bool = False, 
                     force: bool = False, config_file: Optional[str] = None) -> InstallationResult:
        """Install system configuration locally."""
        try:
            system_type = self.system_manager.get_system_type(target)
            if not system_type:
                return InstallationResult(
                    success=False,
                    target=target,
                    message="Invalid target system type",
                    error=f"Unknown system type: {target}"
                )
            
            # Validate system compatibility
            compatibility = system_type.validate_system_compatibility()
            if not compatibility['compatible'] and not force:
                error_issues = [i for i in compatibility['issues'] if i['severity'] == 'error']
                return InstallationResult(
                    success=False,
                    target=target,
                    message="System incompatible with target",
                    error=f"Compatibility issues: {'; '.join([i['message'] for i in error_issues])}"
                )
            
            # Generate installation configuration
            install_config = self._generate_installation_config(system_type, config_file)
            
            if dry_run:
                return self._generate_dry_run_result(system_type, install_config)
            
            # Execute installation
            return self._execute_local_installation(system_type, install_config, force)
            
        except Exception as e:
            self.logger.exception(f"Local installation failed for {target}")
            return InstallationResult(
                success=False,
                target=target,
                message="Installation failed with exception",
                error=str(e)
            )
    
    def install_remote(self, target: str, inventory: str, host: Optional[str] = None,
                      dry_run: bool = False, force: bool = False, 
                      config_file: Optional[str] = None) -> InstallationResult:
        """Install system configuration on remote host via Ansible."""
        try:
            if not self._ansible_available:
                return InstallationResult(
                    success=False,
                    target=target,
                    message="Ansible not available",
                    error="Ansible is required for remote installations"
                )
            
            system_type = self.system_manager.get_system_type(target)
            if not system_type:
                return InstallationResult(
                    success=False,
                    target=target,
                    message="Invalid target system type",
                    error=f"Unknown system type: {target}"
                )
            
            # Generate Ansible playbook and configuration
            playbook_config = self._generate_ansible_configuration(
                system_type, inventory, host, config_file
            )
            
            if dry_run:
                return self._generate_ansible_dry_run_result(system_type, playbook_config)
            
            # Execute remote installation
            return self._execute_remote_installation(
                system_type, playbook_config, inventory, host, force
            )
            
        except Exception as e:
            self.logger.exception(f"Remote installation failed for {target}")
            return InstallationResult(
                success=False,
                target=target,
                message="Remote installation failed with exception",
                error=str(e)
            )
    
    def _get_current_system_info(self) -> Dict[str, Any]:
        """Get current system information."""
        system_info = {
            'os': platform.system().lower(),
            'arch': platform.machine(),
            'platform': platform.platform(),
            'python_version': platform.python_version()
        }
        
        # Detect specific distribution for Linux
        if system_info['os'] == 'linux':
            try:
                with open('/etc/os-release', 'r') as f:
                    content = f.read()
                    for line in content.split('\n'):
                        if line.startswith('ID='):
                            system_info['distribution'] = line.split('=')[1].strip('"')
                            break
            except FileNotFoundError:
                pass
        elif system_info['os'] == 'darwin':
            system_info['os'] = 'macos'
        
        return system_info
    
    def _detect_fleet_projects(self) -> List[Dict[str, Any]]:
        """Detect FLEET projects in current directory."""
        detected_projects = []
        
        try:
            # Look for FLEET projects in current directory and parent directories
            current_dir = Path.cwd()
            
            # Check if we're in an FLEET project directory
            for path in [current_dir] + list(current_dir.parents):
                if path.name == 'fleet' or (path / 'fleet').exists():
                    fleet_root = path if path.name == 'fleet' else path / 'fleet'
                    
                    # Scan for projects
                    for item in fleet_root.iterdir():
                        if item.is_dir() and not item.name.startswith('.'):
                            try:
                                # Import here to avoid circular imports
                                from ..project.project_detector import ProjectDetector
                                detector = ProjectDetector(str(item))
                                project_type = detector.detect()
                                if project_type and project_type != 'unknown':
                                    detected_projects.append({
                                        'name': item.name,
                                        'path': str(item),
                                        'technology_stacks': self._map_framework_to_tech_stack(project_type)
                                    })
                            except Exception as e:
                                self.logger.debug(f"Failed to detect project type for {item}: {e}")
                    break
                    
        except Exception as e:
            self.logger.warning(f"Failed to detect FLEET projects: {e}")
        
        return detected_projects
    
    def _calculate_recommendation_confidence(self, system_type: SystemType, 
                                           current_system: Dict[str, Any],
                                           detected_projects: List[Dict[str, Any]]) -> float:
        """Calculate confidence score for system type recommendation."""
        confidence = 0.0
        
        # OS compatibility (base requirement)
        current_os = current_system.get('os', '')
        if current_os == 'macos':
            current_os = 'macos'
        elif current_os == 'linux':
            current_os = current_system.get('distribution', 'linux')
        
        if current_os in system_type.os_types:
            confidence += 0.4
        else:
            return 0.0  # No confidence if OS not compatible
        
        # Technology stack alignment
        if detected_projects:
            project_tech_stacks = set()
            for project in detected_projects:
                project_tech_stacks.update(project.get('technology_stacks', []))
            
            common_stacks = project_tech_stacks.intersection(set(system_type.technology_stacks))
            if common_stacks:
                confidence += 0.3 * (len(common_stacks) / len(system_type.technology_stacks))
        
        # Development vs production preference
        if 'dev' in system_type.name:
            # Prefer development systems for local development
            confidence += 0.2
        elif detected_projects and len(detected_projects) > 3:
            # Prefer production systems if many projects detected
            if system_type.name in ['server-jellyfish', 'omni-jellyfish']:
                confidence += 0.3
        
        # Architecture-specific adjustments
        if current_system.get('arch') == 'arm64' and system_type.name.startswith('mac'):
            confidence += 0.1
        
        return min(confidence, 1.0)
    
    def _get_recommendation_reason(self, system_type: SystemType,
                                 current_system: Dict[str, Any],
                                 detected_projects: List[Dict[str, Any]]) -> str:
        """Get human-readable reason for recommendation."""
        reasons = []
        
        # OS compatibility
        current_os = current_system.get('os', 'unknown')
        if current_os in system_type.os_types:
            reasons.append(f"Compatible with {current_os}")
        
        # Project alignment
        if detected_projects:
            project_count = len(detected_projects)
            reasons.append(f"Supports {project_count} detected project{'s' if project_count > 1 else ''}")
        
        # System type specific reasons
        if 'dev' in system_type.name:
            reasons.append("Optimized for development workflow")
        elif 'server' in system_type.name:
            reasons.append("Full production server with monitoring")
        elif 'engine' in system_type.name:
            reasons.append("Lightweight engine deployment")
        elif 'platform' in system_type.name:
            reasons.append("Platform services without full server overhead")
        
        return ', '.join(reasons) if reasons else "Basic compatibility"
    
    def _generate_installation_config(self, system_type: SystemType, 
                                    config_file: Optional[str]) -> Dict[str, Any]:
        """Generate installation configuration for system type."""
        config = {
            'system_type': system_type.name,
            'target_config': system_type.get_ansible_variables({}),
            'installation_steps': system_type.get_installation_steps(),
            'dry_run': False
        }
        
        # Load custom configuration if provided
        if config_file and Path(config_file).exists():
            try:
                with open(config_file, 'r') as f:
                    custom_config = json.load(f)
                    config['target_config'].update(custom_config)
            except Exception as e:
                self.logger.warning(f"Failed to load config file {config_file}: {e}")
        
        return config
    
    def _generate_dry_run_result(self, system_type: SystemType, 
                               install_config: Dict[str, Any]) -> InstallationResult:
        """Generate dry-run result showing what would be installed."""
        steps = install_config['installation_steps']
        
        next_steps = [
            f"Would execute {len(steps)} installation steps:",
        ]
        
        for i, step in enumerate(steps, 1):
            next_steps.append(f"{i}. {step['name']}: {step['description']}")
        
        # Add package information
        if system_type.package_requirements:
            current_os = self._get_current_os()
            packages = system_type.package_requirements.get(current_os, [])
            if packages:
                next_steps.append(f"Would install {len(packages)} packages: {', '.join(packages[:5])}{'...' if len(packages) > 5 else ''}")
        
        return InstallationResult(
            success=True,
            target=system_type.name,
            message=f"Dry run completed for {system_type.name}",
            next_steps=next_steps
        )
    
    def _execute_local_installation(self, system_type: SystemType, 
                                  install_config: Dict[str, Any], 
                                  force: bool) -> InstallationResult:
        """Execute local installation using available methods."""
        if self._ansible_available:
            return self._execute_ansible_local(system_type, install_config, force)
        else:
            return self._execute_script_local(system_type, install_config, force)
    
    def _execute_ansible_local(self, system_type: SystemType,
                             install_config: Dict[str, Any],
                             force: bool) -> InstallationResult:
        """Execute local installation using Ansible."""
        try:
            # Check for dedicated system playbook first
            dedicated_playbook = self._get_system_playbook_path(system_type)
            
            if dedicated_playbook:
                return self._execute_dedicated_playbook(system_type, dedicated_playbook, force)
            else:
                return self._execute_generated_playbook(system_type, install_config, force)
                    
        except Exception as e:
            return InstallationResult(
                success=False,
                target=system_type.name,
                message="Ansible execution failed",
                error=str(e)
            )
    
    def _execute_dedicated_playbook(self, system_type: SystemType, 
                                  playbook_path: str, force: bool) -> InstallationResult:
        """Execute dedicated system playbook."""
        try:
            with tempfile.TemporaryDirectory() as temp_dir:
                temp_path = Path(temp_dir)
                
                # Create inventory for localhost
                inventory_file = temp_path / 'inventory'
                with open(inventory_file, 'w') as f:
                    f.write('[localhost]\n127.0.0.1 ansible_connection=local\n')
                
                # Execute dedicated playbook
                cmd = [
                    'ansible-playbook',
                    '-i', str(inventory_file),
                    playbook_path,
                    '-v'
                ]
                
                if force:
                    cmd.extend(['--extra-vars', 'force_install=true'])
                
                result = subprocess.run(cmd, capture_output=True, text=True)
                
                if result.returncode == 0:
                    return InstallationResult(
                        success=True,
                        target=system_type.name,
                        message=f"Successfully installed {system_type.name} using dedicated playbook",
                        ansible_output=result.stdout,
                        next_steps=self._get_post_install_steps(system_type)
                    )
                else:
                    return InstallationResult(
                        success=False,
                        target=system_type.name,
                        message="Dedicated playbook installation failed",
                        error=result.stderr,
                        ansible_output=result.stdout
                    )
        except Exception as e:
            return InstallationResult(
                success=False,
                target=system_type.name,
                message="Dedicated playbook execution failed",
                error=str(e)
            )
    
    def _execute_generated_playbook(self, system_type: SystemType,
                                  install_config: Dict[str, Any],
                                  force: bool) -> InstallationResult:
        """Execute generated playbook as fallback."""
        try:
            # Create temporary Ansible configuration
            with tempfile.TemporaryDirectory() as temp_dir:
                temp_path = Path(temp_dir)
                
                # Create inventory for localhost
                inventory_file = temp_path / 'inventory'
                with open(inventory_file, 'w') as f:
                    f.write('[localhost]\n127.0.0.1 ansible_connection=local\n')
                
                # Create playbook
                playbook_file = temp_path / 'install.yml'
                playbook_content = self._generate_local_playbook(system_type, install_config)
                with open(playbook_file, 'w') as f:
                    f.write(playbook_content)
                
                # Execute Ansible playbook
                cmd = [
                    'ansible-playbook',
                    '-i', str(inventory_file),
                    str(playbook_file),
                    '-v'
                ]
                
                if force:
                    cmd.extend(['--extra-vars', 'force_install=true'])
                
                result = subprocess.run(
                    cmd, 
                    capture_output=True, 
                    text=True,
                    cwd=temp_dir
                )
                
                if result.returncode == 0:
                    return InstallationResult(
                        success=True,
                        target=system_type.name,
                        message=f"Successfully installed {system_type.name}",
                        ansible_output=result.stdout,
                        next_steps=self._get_post_install_steps(system_type)
                    )
                else:
                    return InstallationResult(
                        success=False,
                        target=system_type.name,
                        message="Ansible installation failed",
                        error=result.stderr,
                        ansible_output=result.stdout
                    )
                    
        except Exception as e:
            return InstallationResult(
                success=False,
                target=system_type.name,
                message="Generated playbook execution failed",
                error=str(e)
            )
    
    def _execute_script_local(self, system_type: SystemType,
                            install_config: Dict[str, Any],
                            force: bool) -> InstallationResult:
        """Execute local installation using shell scripts (fallback)."""
        try:
            # Generate installation script
            script_content = self._generate_installation_script(system_type, install_config, force)
            
            # Execute script
            with tempfile.NamedTemporaryFile(mode='w', suffix='.sh', delete=False) as f:
                f.write(script_content)
                script_path = f.name
            
            try:
                result = subprocess.run(
                    ['bash', script_path],
                    capture_output=True,
                    text=True
                )
                
                if result.returncode == 0:
                    return InstallationResult(
                        success=True,
                        target=system_type.name,
                        message=f"Successfully installed {system_type.name}",
                        installation_log=result.stdout,
                        next_steps=self._get_post_install_steps(system_type)
                    )
                else:
                    return InstallationResult(
                        success=False,
                        target=system_type.name,
                        message="Script installation failed",
                        error=result.stderr,
                        installation_log=result.stdout
                    )
            finally:
                os.unlink(script_path)
                
        except Exception as e:
            return InstallationResult(
                success=False,
                target=system_type.name,
                message="Script execution failed",
                error=str(e)
            )
    
    def _generate_installation_script(self, system_type: SystemType,
                                    install_config: Dict[str, Any],
                                    force: bool) -> str:
        """Generate bash installation script for system type."""
        current_os = self._get_current_os()
        packages = system_type.package_requirements.get(current_os, [])
        
        script = f"""#!/bin/bash
# Generated installation script for {system_type.name}
set -euo pipefail

echo "Installing {system_type.name}..."

"""
        
        # Add package installation commands
        if packages:
            if current_os == 'macos':
                script += f"""
# Install packages via Homebrew
if ! command -v brew >/dev/null 2>&1; then
    echo "Error: Homebrew is required but not installed"
    exit 1
fi

brew install {' '.join(packages)}
"""
            elif current_os in ['ubuntu', 'linux']:
                script += f"""
# Update package list and install packages
sudo apt-get update -qq
sudo apt-get install -y {' '.join(packages)}
"""
        
        # Add service configuration
        if system_type.service_requirements:
            script += f"""
# Configure and start services
for service in {' '.join(system_type.service_requirements)}; do
    if systemctl is-enabled "$service" >/dev/null 2>&1; then
        sudo systemctl enable "$service"
        sudo systemctl start "$service"
    fi
done
"""
        
        # Add VPN configuration
        if system_type.vpn_mode != 'none':
            script += f"""
# Configure VPN ({system_type.vpn_mode} mode)
echo "VPN configuration for {system_type.vpn_mode} mode would be applied here"
"""
        
        script += """
echo "Installation completed successfully!"
"""
        
        return script
    
    def _get_post_install_steps(self, system_type: SystemType) -> List[str]:
        """Get post-installation steps for system type."""
        steps = []
        
        if system_type.service_requirements:
            steps.append("Verify services are running: systemctl status <service>")
        
        if system_type.vpn_mode == 'server':
            steps.append("Configure VPN clients and distribute certificates")
        elif system_type.vpn_mode == 'client':
            steps.append("Connect to VPN server using provided configuration")
        
        steps.append("Run 'sega install validate' to verify installation")
        steps.append("Deploy FLEET projects using 'sega deploy'")
        
        return steps
    
    def _generate_ansible_configuration(self, system_type: SystemType,
                                      inventory: str, host: Optional[str],
                                      config_file: Optional[str]) -> Dict[str, Any]:
        """Generate Ansible configuration for remote installation."""
        return {
            'system_type': system_type,
            'inventory': inventory,
            'host': host,
            'playbook_vars': system_type.get_ansible_variables({}),
            'roles': system_type.ansible_roles
        }
    
    def _generate_ansible_dry_run_result(self, system_type: SystemType,
                                       playbook_config: Dict[str, Any]) -> InstallationResult:
        """Generate dry-run result for Ansible installation."""
        next_steps = [
            f"Would execute Ansible playbook for {system_type.name}",
            f"Target: {playbook_config.get('host', 'all hosts')}",
            f"Roles: {', '.join(system_type.ansible_roles)}",
            f"VPN Mode: {system_type.vpn_mode}",
            f"Security Profile: {system_type.security_profile}"
        ]
        
        return InstallationResult(
            success=True,
            target=system_type.name,
            message=f"Ansible dry run completed for {system_type.name}",
            next_steps=next_steps
        )
    
    def _execute_remote_installation(self, system_type: SystemType,
                                   playbook_config: Dict[str, Any],
                                   inventory: str, host: Optional[str],
                                   force: bool) -> InstallationResult:
        """Execute remote installation using Ansible."""
        try:
            # Check for dedicated system playbook first
            dedicated_playbook = self._get_system_playbook_path(system_type)

            if dedicated_playbook:
                return self._execute_remote_dedicated_playbook(
                    system_type, dedicated_playbook, inventory, host, force
                )
            else:
                return self._execute_remote_generated_playbook(
                    system_type, playbook_config, inventory, host, force
                )

        except Exception as e:
            self.logger.exception(f"Remote installation failed for {system_type.name}")
            return InstallationResult(
                success=False,
                target=system_type.name,
                message="Remote Ansible execution failed",
                error=str(e)
            )

    def _execute_remote_dedicated_playbook(self, system_type: SystemType,
                                          playbook_path: str, inventory: str,
                                          host: Optional[str], force: bool) -> InstallationResult:
        """Execute dedicated playbook on remote host."""
        try:
            # Build ansible-playbook command
            cmd = [
                'ansible-playbook',
                '-i', inventory,
                playbook_path,
                '-v'
            ]

            # Limit to specific host if provided
            if host:
                cmd.extend(['--limit', host])

            if force:
                cmd.extend(['--extra-vars', 'force_install=true'])

            self.logger.info(f"Executing remote playbook: {' '.join(cmd)}")

            result = subprocess.run(cmd, capture_output=True, text=True)

            if result.returncode == 0:
                return InstallationResult(
                    success=True,
                    target=system_type.name,
                    message=f"Successfully installed {system_type.name} on remote host",
                    ansible_output=result.stdout,
                    next_steps=self._get_remote_post_install_steps(system_type, host)
                )
            else:
                return InstallationResult(
                    success=False,
                    target=system_type.name,
                    message="Remote dedicated playbook installation failed",
                    error=result.stderr,
                    ansible_output=result.stdout
                )
        except Exception as e:
            return InstallationResult(
                success=False,
                target=system_type.name,
                message="Remote dedicated playbook execution failed",
                error=str(e)
            )

    def _execute_remote_generated_playbook(self, system_type: SystemType,
                                          playbook_config: Dict[str, Any],
                                          inventory: str, host: Optional[str],
                                          force: bool) -> InstallationResult:
        """Execute generated playbook on remote host."""
        try:
            with tempfile.TemporaryDirectory() as temp_dir:
                temp_path = Path(temp_dir)

                # Get roles directory path
                roles_dir = self._get_ansible_roles_path()

                # Create playbook that applies system type roles
                playbook_file = temp_path / 'install_remote.yml'
                playbook_content = self._generate_remote_playbook(system_type, playbook_config)
                with open(playbook_file, 'w') as f:
                    f.write(playbook_content)

                # Build ansible-playbook command
                cmd = [
                    'ansible-playbook',
                    '-i', inventory,
                    str(playbook_file),
                    '-v'
                ]

                # Add roles path if available
                if roles_dir and roles_dir.exists():
                    cmd.extend(['--roles-path', str(roles_dir)])

                # Limit to specific host if provided
                if host:
                    cmd.extend(['--limit', host])

                if force:
                    cmd.extend(['--extra-vars', 'force_install=true'])

                self.logger.info(f"Executing remote playbook: {' '.join(cmd)}")

                result = subprocess.run(cmd, capture_output=True, text=True)

                if result.returncode == 0:
                    return InstallationResult(
                        success=True,
                        target=system_type.name,
                        message=f"Successfully installed {system_type.name} on remote host",
                        ansible_output=result.stdout,
                        next_steps=self._get_remote_post_install_steps(system_type, host)
                    )
                else:
                    return InstallationResult(
                        success=False,
                        target=system_type.name,
                        message="Remote generated playbook installation failed",
                        error=result.stderr,
                        ansible_output=result.stdout
                    )

        except Exception as e:
            return InstallationResult(
                success=False,
                target=system_type.name,
                message="Remote generated playbook execution failed",
                error=str(e)
            )

    def _generate_remote_playbook(self, system_type: SystemType,
                                 playbook_config: Dict[str, Any]) -> str:
        """Generate Ansible playbook for remote installation."""
        # Build roles list from system type configuration
        roles_yaml = '\n'.join([f"    - {role}" for role in system_type.ansible_roles]) if system_type.ansible_roles else "    - install_packages"

        playbook = f"""---
- name: Install {system_type.name}
  hosts: all
  become: yes
  vars:
    system_type: {system_type.name}
    security_profile: {system_type.security_profile}
    vpn_mode: {system_type.vpn_mode}
    technology_stacks: {system_type.technology_stacks}

  roles:
{roles_yaml}
"""
        return playbook

    def _get_ansible_roles_path(self) -> Optional[Path]:
        """Get path to SEGA's Ansible roles directory."""
        possible_paths = [
            Path(__file__).parent.parent.parent.parent / "infrastructure" / "ansible" / "roles",
            Path.cwd() / "infrastructure" / "ansible" / "roles"
        ]

        for path in possible_paths:
            if path.exists():
                return path

        return None

    def _get_remote_post_install_steps(self, system_type: SystemType,
                                       host: Optional[str]) -> List[str]:
        """Get post-installation steps for remote system."""
        host_display = host or "remote host"
        steps = [
            f"SSH to {host_display} to verify installation",
            f"Run 'sega install validate --target {system_type.name}' on remote host"
        ]

        if system_type.service_requirements:
            services = ', '.join(system_type.service_requirements[:3])
            steps.append(f"Verify services are running: systemctl status {services}")

        if system_type.vpn_mode == 'server':
            steps.append("Distribute VPN certificates to client systems")
        elif system_type.vpn_mode == 'client':
            steps.append("Verify VPN connection: ping vpn-server")

        steps.append("Deploy FLEET projects using 'sega deploy'")

        return steps
    
    def _get_system_playbook_path(self, system_type: SystemType) -> Optional[str]:
        """Get path to dedicated system playbook if it exists."""
        playbook_name = f"install_{system_type.name.replace('-', '_')}.yml"
        
        # Look for playbook in SEGA's Ansible directory
        from ..utils.paths import get_sega_root
        possible_paths = [
            Path(__file__).parent.parent.parent.parent / "infrastructure" / "ansible" / "playbooks" / playbook_name,
            get_sega_root() / "infrastructure" / "ansible" / "playbooks" / playbook_name,
            Path.cwd() / "infrastructure" / "ansible" / "playbooks" / playbook_name
        ]
        
        for path in possible_paths:
            if path.exists():
                return str(path)
        
        return None
    
    def _generate_local_playbook(self, system_type: SystemType,
                               install_config: Dict[str, Any]) -> str:
        """Generate Ansible playbook for local installation."""
        playbook = f"""---
- name: Install {system_type.name}
  hosts: localhost
  become: yes
  vars:
    system_type: {system_type.name}
    security_profile: {system_type.security_profile}
    vpn_mode: {system_type.vpn_mode}
  
  tasks:
"""
        
        # Add tasks based on system type requirements
        current_os = self._get_current_os()
        packages = system_type.package_requirements.get(current_os, [])
        
        if packages:
            if current_os == 'macos':
                playbook += f"""
    - name: Install packages via Homebrew
      homebrew:
        name: {packages}
        state: present
"""
            else:
                playbook += f"""
    - name: Update package list
      apt:
        update_cache: yes
      
    - name: Install packages
      apt:
        name: {packages}
        state: present
"""
        
        # Add service tasks
        if system_type.service_requirements:
            playbook += f"""
    - name: Start and enable services
      systemd:
        name: "{{{{ item }}}}"
        state: started
        enabled: yes
      loop: {system_type.service_requirements}
      ignore_errors: yes
"""
        
        return playbook
    
    def _check_ansible_availability(self) -> bool:
        """Check if Ansible is available on the system."""
        try:
            result = subprocess.run(['ansible', '--version'], 
                                  capture_output=True, text=True)
            return result.returncode == 0
        except FileNotFoundError:
            return False
    
    def _get_current_os(self) -> str:
        """Get current OS in system type format."""
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
    
    def _map_framework_to_tech_stack(self, framework: str) -> List[str]:
        """Map detected framework to technology stack."""
        mapping = {
            'python': ['python'],
            'rust': ['rust'],
            'nodejs': ['nodejs'],
            'react': ['nodejs'],
            'vue': ['nodejs'],
            'django': ['python'],
            'flask': ['python'],
            'fastapi': ['python'],
            'cargo': ['rust'],
            'npm': ['nodejs'],
            'yarn': ['nodejs']
        }
        
        return mapping.get(framework.lower(), [])