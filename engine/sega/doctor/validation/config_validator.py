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
Configuration validation for SEGA

Validates sega.yaml configuration files for correctness and completeness.
"""

from pathlib import Path
from typing import Any, Dict, List
import logging

from .base import BaseValidator, ValidationResult

logger = logging.getLogger(__name__)


class ConfigValidator(BaseValidator):
    """Validates SEGA configuration files"""
    
    # Valid project types
    VALID_PROJECT_TYPES = {
        'web_app', 'ml_pipeline', 'firmware_edge', 
        'native_app', 'hdl_fpga', 'hybrid_system'
    }
    
    # Valid build strategies
    VALID_BUILD_STRATEGIES = {
        'containerized', 'native', 'hybrid'
    }
    
    # Valid deployment types
    VALID_DEPLOYMENT_TYPES = {
        'local', 'docker', 'kubernetes', 'aws-ecs', 
        'aws-fargate', 'gcp-run', 'azure-container'
    }
    
    # Valid deployment strategies
    VALID_DEPLOYMENT_STRATEGIES = {
        'rolling', 'canary', 'blue_green', 'recreate'
    }
    
    # Valid security scanners
    VALID_SECURITY_SCANNERS = {
        'dependency', 'static', 'container', 'dast'
    }
    
    # Valid intelligence features
    VALID_INTELLIGENCE_FEATURES = {
        'anomaly_detection', 'predictive_scaling', 
        'optimization_suggestions', 'cost_analysis',
        'performance_insights'
    }
    
    def __init__(self):
        super().__init__("ConfigValidator")
        self.current_config = None
        self.current_path = None
    
    def validate(self, target: Any, **kwargs) -> ValidationResult:
        """Validate configuration"""
        if isinstance(target, dict):
            # Direct config validation
            result = ValidationResult(
                valid=True,
                validator_name=self.name,
                target="Configuration"
            )
            self.current_config = target
            self._validate_config(target, result)
            return result
        elif isinstance(target, (str, Path)):
            # File or directory validation
            path = Path(target)
            if path.is_file():
                return self.validate_file(path, **kwargs)
            elif path.is_dir():
                return self.validate_directory(
                    path, 
                    pattern="sega.yaml", 
                    recursive=True,
                    **kwargs
                )
        
        # Invalid target
        result = ValidationResult(
            valid=False,
            validator_name=self.name,
            target=str(target)
        )
        result.add_error(f"Invalid validation target: {target}")
        return result
    
    def _validate_file_content(self, filepath: Path, result: ValidationResult, **kwargs) -> ValidationResult:
        """Validate a sega.yaml file"""
        self.current_path = filepath
        
        # Check for template variables
        try:
            content = filepath.read_text()
            if '{{' in content or '}}' in content:
                result.add_warning(
                    "Template variables found - this may be a template file",
                    path=str(filepath)
                )
        except Exception as e:
            result.add_error(f"Error reading file: {e}", path=str(filepath))
            return result
        
        # Load and parse YAML
        config = self.load_yaml(filepath)
        if config is None:
            result.add_error("Failed to parse YAML", path=str(filepath))
            return result
        
        if not isinstance(config, dict):
            result.add_error("YAML root must be a dictionary", path=str(filepath))
            return result
        
        self.current_config = config
        
        # Validate configuration
        self._validate_config(config, result)
        
        # Check for project-specific requirements
        if self.current_path:
            self._validate_project_files(config, result)
        
        return result
    
    def _validate_config(self, config: Dict[str, Any], result: ValidationResult) -> None:
        """Validate configuration structure and values"""
        # Validate required top-level fields
        self._validate_required_fields(config, result)
        
        # Validate specific sections
        if 'project' in config:
            self._validate_project_section(config['project'], result)
        
        if 'build' in config:
            self._validate_build_section(config['build'], result)
        
        if 'deployment' in config:
            self._validate_deployment_section(config['deployment'], result)
        
        if 'security' in config:
            self._validate_security_section(config['security'], result)
        
        if 'monitoring' in config:
            self._validate_monitoring_section(config['monitoring'], result)
        
        if 'intelligence' in config:
            self._validate_intelligence_section(config['intelligence'], result)
        
        if 'components' in config:
            self._validate_components_section(config['components'], result)
    
    def _validate_required_fields(self, config: Dict[str, Any], result: ValidationResult) -> None:
        """Validate required top-level fields"""
        required_fields = ['version', 'project', 'build', 'deployment']
        
        for field in required_fields:
            if field not in config:
                result.add_error(f"Missing required field: {field}")
    
    def _validate_project_section(self, project: Dict[str, Any], result: ValidationResult) -> None:
        """Validate project section"""
        required_project_fields = ['name', 'type', 'domain', 'team', 'description']
        
        for field in required_project_fields:
            if field not in project:
                result.add_error(f"Missing required project field: {field}")
        
        # Validate project type
        if 'type' in project:
            project_type = project['type']
            if project_type not in self.VALID_PROJECT_TYPES:
                result.add_error(
                    f"Invalid project type: {project_type}",
                    suggestion=f"Valid types: {', '.join(sorted(self.VALID_PROJECT_TYPES))}"
                )
    
    def _validate_build_section(self, build: Dict[str, Any], result: ValidationResult) -> None:
        """Validate build section"""
        if 'strategy' not in build:
            result.add_error("Missing required build field: strategy")
        else:
            strategy = build['strategy']
            if strategy not in self.VALID_BUILD_STRATEGIES:
                result.add_error(
                    f"Invalid build strategy: {strategy}",
                    suggestion=f"Valid strategies: {', '.join(sorted(self.VALID_BUILD_STRATEGIES))}"
                )
        
        if 'commands' not in build:
            result.add_error("Missing required build field: commands")
        
        # Validate containerized build
        if build.get('strategy') == 'containerized':
            if 'docker' not in build:
                result.add_warning("Containerized build should include docker configuration")
            else:
                docker = build['docker']
                if 'dockerfile' not in docker:
                    result.add_warning("Docker configuration should specify dockerfile")
    
    def _validate_deployment_section(self, deployment: Dict[str, Any], result: ValidationResult) -> None:
        """Validate deployment section"""
        if 'targets' not in deployment:
            result.add_error("Missing required deployment field: targets")
            return
        
        targets = deployment['targets']
        if not targets:
            result.add_error("Deployment targets cannot be empty")
            return
        
        # Check for development target
        if 'development' not in targets:
            result.add_error("Missing required deployment target: development")
        
        # Validate each target
        for target_name, target_config in targets.items():
            if not isinstance(target_config, dict):
                result.add_error(f"Deployment target {target_name} must be a dictionary")
                continue
            
            # Validate deployment type
            if 'type' in target_config:
                deploy_type = target_config['type']
                if deploy_type not in self.VALID_DEPLOYMENT_TYPES:
                    result.add_error(
                        f"Invalid deployment type for {target_name}: {deploy_type}",
                        suggestion=f"Valid types: {', '.join(sorted(self.VALID_DEPLOYMENT_TYPES))}"
                    )
            
            # Validate deployment strategy
            if 'strategy' in target_config:
                strategy = target_config['strategy']
                if strategy not in self.VALID_DEPLOYMENT_STRATEGIES:
                    result.add_error(
                        f"Invalid deployment strategy for {target_name}: {strategy}",
                        suggestion=f"Valid strategies: {', '.join(sorted(self.VALID_DEPLOYMENT_STRATEGIES))}"
                    )
            
            # Check for infrastructure in targets (not at deployment level)
            if 'infrastructure' in target_config:
                self._validate_infrastructure(target_config['infrastructure'], result, target_name)
        
        # Warn if infrastructure is at deployment level (should be under targets)
        if 'infrastructure' in deployment:
            result.add_warning(
                "Infrastructure should be nested under specific targets, not at deployment level",
                suggestion="Move infrastructure configuration under deployment.targets.<target>.infrastructure"
            )
    
    def _validate_infrastructure(self, infra: Dict[str, Any], result: ValidationResult, 
                               target: str) -> None:
        """Validate infrastructure configuration"""
        # Check compute resources
        if 'compute' in infra:
            compute = infra['compute']
            if 'cpu' in compute and not isinstance(compute['cpu'], (int, float)):
                result.add_error(f"Invalid CPU value for {target}: must be a number")
            if 'memory' in compute and not isinstance(compute['memory'], (int, float)):
                result.add_error(f"Invalid memory value for {target}: must be a number")
    
    def _validate_security_section(self, security: Dict[str, Any], result: ValidationResult) -> None:
        """Validate security section"""
        if not security:
            result.add_warning("Empty security configuration - recommended for production")
            return
        
        # Validate vulnerability scanning
        if 'vulnerability_scanning' in security:
            vuln_scan = security['vulnerability_scanning']
            if vuln_scan.get('enabled', False) and 'scanners' in vuln_scan:
                scanners = vuln_scan['scanners']
                for scanner in scanners:
                    if scanner not in self.VALID_SECURITY_SCANNERS:
                        result.add_error(
                            f"Invalid security scanner: {scanner}",
                            suggestion=f"Valid scanners: {', '.join(sorted(self.VALID_SECURITY_SCANNERS))}"
                        )
    
    def _validate_monitoring_section(self, monitoring: Dict[str, Any], result: ValidationResult) -> None:
        """Validate monitoring section"""
        if not monitoring:
            result.add_warning("Empty monitoring configuration - recommended for production")
            return
        
        # Check metrics
        metrics = monitoring.get('metrics', {})
        if not metrics.get('enabled', False):
            result.add_warning("Metrics collection not enabled")
        
        # Check logging
        if 'logging' not in monitoring:
            result.add_warning("No logging configuration found")
    
    def _validate_intelligence_section(self, intelligence: Dict[str, Any], result: ValidationResult) -> None:
        """Validate intelligence/AI section"""
        if intelligence.get('enabled', False):
            features = intelligence.get('features', [])
            if not features:
                result.add_warning("Intelligence enabled but no features specified")
            
            for feature in features:
                if feature not in self.VALID_INTELLIGENCE_FEATURES:
                    result.add_warning(
                        f"Unknown intelligence feature: {feature}",
                        suggestion=f"Valid features: {', '.join(sorted(self.VALID_INTELLIGENCE_FEATURES))}"
                    )
    
    def _validate_components_section(self, components: List[Dict[str, Any]], result: ValidationResult) -> None:
        """Validate multi-component configuration"""
        if not isinstance(components, list):
            result.add_error("Components must be a list")
            return
        
        component_names = set()
        for i, component in enumerate(components):
            if not isinstance(component, dict):
                result.add_error(f"Component {i} must be a dictionary")
                continue
            
            # Check required fields
            if 'name' not in component:
                result.add_error(f"Component {i} missing required field: name")
            else:
                name = component['name']
                if name in component_names:
                    result.add_error(f"Duplicate component name: {name}")
                component_names.add(name)
            
            if 'type' not in component:
                result.add_error(f"Component {i} missing required field: type")
            elif component['type'] not in self.VALID_PROJECT_TYPES:
                result.add_error(
                    f"Invalid component type: {component['type']}",
                    suggestion=f"Valid types: {', '.join(sorted(self.VALID_PROJECT_TYPES))}"
                )
    
    def _validate_project_files(self, config: Dict[str, Any], result: ValidationResult) -> None:
        """Validate that referenced files exist"""
        if not self.current_path:
            return
        
        project_dir = self.current_path.parent
        
        # Check Dockerfile for containerized builds
        build = config.get('build', {})
        if build.get('strategy') == 'containerized':
            docker = build.get('docker', {})
            dockerfile = docker.get('dockerfile', 'Dockerfile')
            dockerfile_path = project_dir / dockerfile
            
            if not dockerfile_path.exists():
                result.add_error(
                    f"Dockerfile not found: {dockerfile}",
                    path=str(self.current_path),
                    suggestion=f"Create {dockerfile} or update docker.dockerfile in config"
                )
        
        # Check component paths
        components = config.get('components', [])
        for component in components:
            if 'path' in component:
                component_path = project_dir / component['path']
                if not component_path.exists():
                    result.add_warning(
                        f"Component path not found: {component['path']}",
                        path=str(self.current_path)
                    )