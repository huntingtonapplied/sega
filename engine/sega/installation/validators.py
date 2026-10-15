#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# Copyright 2025 SEGA

"""
SEGA INSTALLATION VALIDATORS
===============================================================================
File: src/sega/installation/validators.py
Purpose: Installation validation and system health checking

Description: Validates system compatibility, installation requirements, and
post-installation health checks for FLEET system types. Provides detailed
feedback on installation readiness and system configuration status.
===============================================================================
"""

import os
import subprocess
import platform
import shutil
from pathlib import Path
from typing import Dict, List, Optional, Any
import logging
import socket
import psutil

from .system_types import SystemType, SystemTypeManager


class InstallationValidator:
    """Validates system installations and compatibility."""
    
    def __init__(self, logger: Optional[logging.Logger] = None):
        self.logger = logger or logging.getLogger(__name__)
        self.system_manager = SystemTypeManager()
    
    def validate_target_compatibility(self, target: str) -> Dict[str, Any]:
        """Validate if current system can support target installation."""
        system_type = self.system_manager.get_system_type(target)
        if not system_type:
            return {
                'compatible': False,
                'issues': [{'severity': 'error', 'message': f'Unknown target type: {target}'}],
                'requirements': []
            }
        
        return system_type.validate_system_compatibility()
    
    def validate_current_installation(self) -> Dict[str, Any]:
        """Validate current SEGA installation and system configuration."""
        result = {
            'sega_installed': False,
            'system_configured': False,
            'services_healthy': False,
            'detected_type': None,
            'issues': [],
            'service_status': {},
            'recommendations': []
        }
        
        # Check SEGA installation
        sega_status = self._validate_sega_installation()
        result.update(sega_status)
        
        # Detect current system configuration
        detection_result = self._detect_current_system_type()
        result.update(detection_result)
        
        # Check service health if system is configured
        if result['system_configured']:
            service_status = self._validate_services_health(result['detected_type'])
            result.update(service_status)
        
        # Generate recommendations
        recommendations = self._generate_validation_recommendations(result)
        result['recommendations'] = recommendations
        
        return result
    
    def validate_prerequisites(self, target: str) -> Dict[str, Any]:
        """Validate all prerequisites for target installation."""
        result = {
            'ready_to_install': True,
            'missing_prerequisites': [],
            'system_checks': {},
            'warnings': []
        }
        
        system_type = self.system_manager.get_system_type(target)
        if not system_type:
            result['ready_to_install'] = False
            result['missing_prerequisites'].append(f'Invalid target: {target}')
            return result
        
        # Check system compatibility
        compatibility = system_type.validate_system_compatibility()
        result['system_checks']['compatibility'] = compatibility
        
        if not compatibility['compatible']:
            result['ready_to_install'] = False
            error_issues = [i for i in compatibility['issues'] if i['severity'] == 'error']
            result['missing_prerequisites'].extend([i['message'] for i in error_issues])
        
        # Check disk space
        disk_check = self._check_disk_space_requirements(system_type)
        result['system_checks']['disk_space'] = disk_check
        
        if not disk_check['sufficient']:
            result['ready_to_install'] = False
            result['missing_prerequisites'].append(disk_check['message'])
        
        # Check network connectivity
        network_check = self._check_network_connectivity()
        result['system_checks']['network'] = network_check
        
        if not network_check['connected']:
            result['ready_to_install'] = False
            result['missing_prerequisites'].append('Internet connectivity required')
        
        # Check package manager availability
        package_mgr_check = self._check_package_manager_availability()
        result['system_checks']['package_manager'] = package_mgr_check
        
        if not package_mgr_check['available']:
            result['ready_to_install'] = False
            result['missing_prerequisites'].append(package_mgr_check['message'])
        
        # Check for existing conflicting installations
        conflict_check = self._check_installation_conflicts(system_type)
        result['system_checks']['conflicts'] = conflict_check
        
        if conflict_check['conflicts_found']:
            result['warnings'].extend(conflict_check['warnings'])
        
        return result
    
    def validate_post_installation(self, target: str) -> Dict[str, Any]:
        """Validate system after installation completion."""
        result = {
            'installation_successful': False,
            'services_running': False,
            'configuration_valid': False,
            'issues': [],
            'next_steps': []
        }
        
        system_type = self.system_manager.get_system_type(target)
        if not system_type:
            result['issues'].append(f'Unknown target type: {target}')
            return result
        
        # Validate package installation
        package_validation = self._validate_package_installation(system_type)
        result['packages_installed'] = package_validation['all_installed']
        
        if not package_validation['all_installed']:
            result['issues'].extend(package_validation['missing_packages'])
        
        # Validate service status
        service_validation = self._validate_service_status(system_type)
        result['services_running'] = service_validation['all_running']
        result['service_details'] = service_validation['service_status']
        
        if not service_validation['all_running']:
            result['issues'].extend(service_validation['failed_services'])
        
        # Validate configuration files
        config_validation = self._validate_configuration_files(system_type)
        result['configuration_valid'] = config_validation['all_valid']
        
        if not config_validation['all_valid']:
            result['issues'].extend(config_validation['invalid_configs'])
        
        # Check VPN configuration
        if system_type.vpn_mode != 'none':
            vpn_validation = self._validate_vpn_configuration(system_type)
            result['vpn_configured'] = vpn_validation['configured']
            
            if not vpn_validation['configured']:
                result['issues'].append(vpn_validation['message'])
        
        # Overall success determination
        critical_issues = [i for i in result['issues'] if 'error' in i.lower()]
        result['installation_successful'] = (
            package_validation['all_installed'] and
            len(critical_issues) == 0
        )
        
        # Generate next steps
        result['next_steps'] = self._generate_post_install_next_steps(system_type, result)
        
        return result
    
    def _validate_sega_installation(self) -> Dict[str, Any]:
        """Validate SEGA installation status."""
        result = {
            'sega_installed': False,
            'sega_version': None,
            'sega_path': None,
            'virtual_env': None
        }
        
        try:
            # Check if SEGA is available in PATH
            sega_result = subprocess.run(['python', '-m', 'sega', '--version'], 
                                       capture_output=True, text=True)
            
            if sega_result.returncode == 0:
                result['sega_installed'] = True
                # Extract version from output
                version_line = sega_result.stdout.strip()
                if 'version' in version_line:
                    result['sega_version'] = version_line.split()[-1]
            
            # Check for virtual environment
            if 'VIRTUAL_ENV' in os.environ:
                result['virtual_env'] = os.environ['VIRTUAL_ENV']
            
            # Try to find SEGA installation path
            try:
                import sega
                result['sega_path'] = str(Path(sega.__file__).parent.parent)
            except ImportError:
                pass
                
        except (subprocess.SubprocessError, FileNotFoundError):
            pass
        
        return result
    
    def _detect_current_system_type(self) -> Dict[str, Any]:
        """Detect current system type configuration."""
        result = {
            'system_configured': False,
            'detected_type': None,
            'confidence': 0.0,
            'evidence': []
        }
        
        # Check for SEGA configuration files
        config_paths = [
            Path.home() / '.sega' / 'system_type',
            Path.cwd() / '.sega_system_type',
            Path('/etc/sega/system_type')
        ]
        
        for config_path in config_paths:
            if config_path.exists():
                try:
                    with open(config_path, 'r') as f:
                        detected_type = f.read().strip()
                        if self.system_manager.get_system_type(detected_type):
                            result['system_configured'] = True
                            result['detected_type'] = detected_type
                            result['confidence'] = 1.0
                            result['evidence'].append(f'Configuration file: {config_path}')
                            return result
                except Exception as e:
                    self.logger.warning(f"Failed to read config file {config_path}: {e}")
        
        # Try to infer system type from installed packages and services
        inference_result = self._infer_system_type_from_environment()
        if inference_result['type']:
            result.update(inference_result)
        
        return result
    
    def _validate_services_health(self, system_type_name: str) -> Dict[str, Any]:
        """Validate health of system services."""
        result = {
            'services_healthy': True,
            'service_status': {},
            'failed_services': []
        }
        
        system_type = self.system_manager.get_system_type(system_type_name)
        if not system_type or not system_type.service_requirements:
            return result
        
        for service_name in system_type.service_requirements:
            status = self._check_service_status(service_name)
            result['service_status'][service_name] = status
            
            if not status['running']:
                result['services_healthy'] = False
                result['failed_services'].append({
                    'service': service_name,
                    'status': status['status'],
                    'message': status.get('message', 'Service not running')
                })
        
        return result
    
    def _check_service_status(self, service_name: str) -> Dict[str, Any]:
        """Check status of a specific service."""
        try:
            # Try systemctl first (Linux)
            result = subprocess.run(['systemctl', 'is-active', service_name],
                                  capture_output=True, text=True)
            
            if result.returncode == 0:
                return {'running': True, 'status': 'active', 'method': 'systemctl'}
            else:
                return {'running': False, 'status': 'inactive', 'method': 'systemctl'}
                
        except FileNotFoundError:
            # Try launchctl (macOS)
            try:
                result = subprocess.run(['launchctl', 'list', service_name],
                                      capture_output=True, text=True)
                
                if result.returncode == 0:
                    return {'running': True, 'status': 'loaded', 'method': 'launchctl'}
                else:
                    return {'running': False, 'status': 'not loaded', 'method': 'launchctl'}
                    
            except FileNotFoundError:
                # Try process check
                for proc in psutil.process_iter(['pid', 'name']):
                    try:
                        if service_name.lower() in proc.info['name'].lower():
                            return {'running': True, 'status': 'process found', 'method': 'process'}
                    except (psutil.NoSuchProcess, psutil.AccessDenied):
                        continue
                
                return {'running': False, 'status': 'not found', 'method': 'process'}
    
    def _generate_validation_recommendations(self, validation_result: Dict[str, Any]) -> List[str]:
        """Generate recommendations based on validation results."""
        recommendations = []
        
        if not validation_result['sega_installed']:
            recommendations.append('Install SEGA using the bootstrap script: curl -sSL https://install.fleet-dev.example.com/fleet_install | bash')
        
        if not validation_result['system_configured']:
            recommendations.append('Configure system type: sega install detect')
            recommendations.append('Install system configuration: sega install target --target <type>')
        
        if validation_result['system_configured'] and not validation_result['services_healthy']:
            recommendations.append('Check service status: systemctl status <service>')
            recommendations.append('Restart failed services: sudo systemctl restart <service>')
        
        if validation_result.get('service_status'):
            for service, status in validation_result['service_status'].items():
                if not status['running']:
                    recommendations.append(f'Start {service} service: sudo systemctl start {service}')
        
        return recommendations
    
    def _check_disk_space_requirements(self, system_type: SystemType) -> Dict[str, Any]:
        """Check if system has sufficient disk space."""
        required_space_gb = 5  # Default minimum
        
        # Parse resource requirements
        if system_type.resource_requirements.get('disk'):
            disk_req = system_type.resource_requirements['disk']
            if 'GB' in disk_req:
                required_space_gb = int(disk_req.replace('GB', ''))
            elif 'TB' in disk_req:
                required_space_gb = int(disk_req.replace('TB', '')) * 1024
        
        # Check available space
        statvfs = os.statvfs('/')
        available_bytes = statvfs.f_bavail * statvfs.f_frsize
        available_gb = available_bytes / (1024**3)
        
        return {
            'sufficient': available_gb >= required_space_gb,
            'required_gb': required_space_gb,
            'available_gb': round(available_gb, 2),
            'message': f'Requires {required_space_gb}GB, available {available_gb:.1f}GB'
        }
    
    def _check_network_connectivity(self) -> Dict[str, Any]:
        """Check internet connectivity."""
        try:
            # Try to connect to a reliable host
            socket.create_connection(('8.8.8.8', 53), timeout=5)
            return {'connected': True, 'message': 'Internet connectivity verified'}
        except OSError:
            return {'connected': False, 'message': 'No internet connectivity'}
    
    def _check_package_manager_availability(self) -> Dict[str, Any]:
        """Check if required package manager is available."""
        current_os = self._get_current_os()
        
        if current_os == 'macos':
            if shutil.which('brew'):
                return {'available': True, 'manager': 'homebrew'}
            else:
                return {'available': False, 'manager': 'homebrew', 
                       'message': 'Homebrew package manager not found'}
        
        elif current_os in ['ubuntu', 'linux']:
            if shutil.which('apt-get'):
                return {'available': True, 'manager': 'apt'}
            elif shutil.which('yum'):
                return {'available': True, 'manager': 'yum'}
            elif shutil.which('dnf'):
                return {'available': True, 'manager': 'dnf'}
            else:
                return {'available': False, 'manager': 'unknown',
                       'message': 'No supported package manager found'}
        
        else:
            return {'available': False, 'manager': 'unknown',
                   'message': f'Unsupported OS: {current_os}'}
    
    def _check_installation_conflicts(self, system_type: SystemType) -> Dict[str, Any]:
        """Check for existing installations that might conflict."""
        conflicts = []
        warnings = []
        
        # Check for conflicting services
        for service in system_type.service_requirements:
            if self._check_service_status(service)['running']:
                warnings.append(f'Service {service} is already running')
        
        # Check for conflicting VPN configurations
        if system_type.vpn_mode == 'server':
            openvpn_configs = list(Path('/etc/openvpn').glob('*.conf')) if Path('/etc/openvpn').exists() else []
            if openvpn_configs:
                warnings.append(f'Existing OpenVPN configurations found: {len(openvpn_configs)} files')
        
        return {
            'conflicts_found': len(conflicts) > 0,
            'conflicts': conflicts,
            'warnings': warnings
        }
    
    def _validate_package_installation(self, system_type: SystemType) -> Dict[str, Any]:
        """Validate that required packages are installed."""
        current_os = self._get_current_os()
        required_packages = system_type.package_requirements.get(current_os, [])
        
        installed_packages = []
        missing_packages = []
        
        for package in required_packages:
            if self._is_package_installed(package, current_os):
                installed_packages.append(package)
            else:
                missing_packages.append(f'Missing package: {package}')
        
        return {
            'all_installed': len(missing_packages) == 0,
            'installed_packages': installed_packages,
            'missing_packages': missing_packages
        }
    
    def _validate_service_status(self, system_type: SystemType) -> Dict[str, Any]:
        """Validate that required services are running."""
        running_services = []
        failed_services = []
        service_status = {}
        
        for service in system_type.service_requirements:
            status = self._check_service_status(service)
            service_status[service] = status
            
            if status['running']:
                running_services.append(service)
            else:
                failed_services.append(f'Service {service} not running: {status["status"]}')
        
        return {
            'all_running': len(failed_services) == 0,
            'running_services': running_services,
            'failed_services': failed_services,
            'service_status': service_status
        }
    
    def _validate_configuration_files(self, system_type: SystemType) -> Dict[str, Any]:
        """Validate system configuration files."""
        valid_configs = []
        invalid_configs = []
        
        # Check for system type marker file
        config_paths = [
            Path.home() / '.sega' / 'system_type',
            Path.cwd() / '.sega_system_type'
        ]
        
        config_found = False
        for config_path in config_paths:
            if config_path.exists():
                try:
                    with open(config_path, 'r') as f:
                        content = f.read().strip()
                        if content == system_type.name:
                            valid_configs.append(f'System type configuration: {config_path}')
                            config_found = True
                        else:
                            invalid_configs.append(f'System type mismatch in {config_path}: {content}')
                except Exception as e:
                    invalid_configs.append(f'Failed to read {config_path}: {e}')
        
        if not config_found:
            invalid_configs.append('No system type configuration found')
        
        return {
            'all_valid': len(invalid_configs) == 0,
            'valid_configs': valid_configs,
            'invalid_configs': invalid_configs
        }
    
    def _validate_vpn_configuration(self, system_type: SystemType) -> Dict[str, Any]:
        """Validate VPN configuration."""
        if system_type.vpn_mode == 'none':
            return {'configured': True, 'message': 'No VPN required'}
        
        # Check for OpenVPN configuration
        config_paths = [
            Path('/etc/openvpn'),
            Path.home() / '.openvpn'
        ]
        
        for config_path in config_paths:
            if config_path.exists():
                config_files = list(config_path.glob('*.conf'))
                if config_files:
                    return {
                        'configured': True, 
                        'message': f'VPN configuration found: {len(config_files)} files'
                    }
        
        return {
            'configured': False,
            'message': f'VPN {system_type.vpn_mode} configuration not found'
        }
    
    def _generate_post_install_next_steps(self, system_type: SystemType, 
                                        validation_result: Dict[str, Any]) -> List[str]:
        """Generate next steps after installation."""
        steps = []
        
        if not validation_result.get('packages_installed', True):
            steps.append('Install missing packages manually')
        
        if not validation_result.get('services_running', True):
            steps.append('Start required services: sudo systemctl start <service>')
        
        if system_type.vpn_mode != 'none' and not validation_result.get('vpn_configured', True):
            if system_type.vpn_mode == 'server':
                steps.append('Configure VPN server and generate client certificates')
            else:
                steps.append('Configure VPN client with server certificates')
        
        steps.extend([
            'Save system type configuration: echo "{system_type.name}" > ~/.sega/system_type',
            'Verify installation: sega install validate',
            'Deploy FLEET projects: sega deploy'
        ])
        
        return steps
    
    def _infer_system_type_from_environment(self) -> Dict[str, Any]:
        """Infer system type from installed packages and services."""
        result = {
            'type': None,
            'confidence': 0.0,
            'evidence': []
        }
        
        # Check for development vs production indicators
        dev_indicators = ['docker-compose', 'node', 'npm', 'python3-dev']
        prod_indicators = ['nginx', 'postgresql', 'redis-server', 'systemd']
        
        current_os = self._get_current_os()
        dev_score = sum(1 for indicator in dev_indicators if self._is_package_installed(indicator, current_os))
        prod_score = sum(1 for indicator in prod_indicators if self._is_package_installed(indicator, current_os))
        
        # Check for specific patterns
        if current_os == 'macos' and dev_score > 0:
            result['type'] = 'mac-dev'
            result['confidence'] = min(dev_score * 0.3, 0.9)
            result['evidence'].append(f'macOS with development tools ({dev_score} indicators)')
        
        elif current_os in ['ubuntu', 'linux']:
            if prod_score >= 3:
                result['type'] = 'server-jellyfish'
                result['confidence'] = min(prod_score * 0.25, 0.8)
                result['evidence'].append(f'Linux with production services ({prod_score} indicators)')
            elif dev_score >= 2:
                result['type'] = 'development-jellyfish'
                result['confidence'] = min(dev_score * 0.3, 0.7)
                result['evidence'].append(f'Linux with development tools ({dev_score} indicators)')
        
        return result
    
    def _is_package_installed(self, package: str, os_type: str) -> bool:
        """Check if a package is installed on the system."""
        try:
            if os_type == 'macos':
                # Check Homebrew
                result = subprocess.run(['brew', 'list', package], 
                                      capture_output=True, text=True)
                return result.returncode == 0
            
            elif os_type in ['ubuntu', 'linux']:
                # Check apt/dpkg
                result = subprocess.run(['dpkg', '-l', package], 
                                      capture_output=True, text=True)
                return result.returncode == 0 and 'ii' in result.stdout
            
        except FileNotFoundError:
            pass
        
        # Fallback: check if command exists
        return shutil.which(package) is not None
    
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