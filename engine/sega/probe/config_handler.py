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
SEGA Browser Test Configuration Handler
========================================
Handles project-agnostic configuration with environment variable support
"""

import os
import json
from pathlib import Path
from typing import Dict, Any, Optional
from ..utils.paths import get_fleet_root
from ..core.config import get_config


# Project set sourced from the curated `[fleet] app_projects` config list;
# frontend/backend port VALUES come from central config
# (frontend = 3000 + id, backend/api = 8000 + id).
# AUTHORITATIVE: /docs/standards/infrastructure/PORT_ALLOCATION_STANDARDS.md
_BROWSER_TEST_PROJECTS = list(get_config().fleet.app_projects)


def _browser_test_port_overrides() -> Dict[str, Dict[str, int]]:
    """Manual per-project port overrides NOT derivable from the port formulas.

    The telemetry project's TCP protobuf port has no formula-derived config
    port, so it is layered on from `[telemetry] tcp_protobuf_port`.
    """
    cfg = get_config()
    overrides: Dict[str, Dict[str, int]] = {}
    if cfg.fleet.telemetry_project:
        overrides[cfg.fleet.telemetry_project] = {'tcp': cfg.telemetry.tcp_protobuf_port}
    return overrides


_BROWSER_TEST_PORT_OVERRIDES = _browser_test_port_overrides()


def _build_browser_test_ports() -> Dict[str, Dict[str, int]]:
    """Build {project: {'frontend': ..., 'backend': ...}} from central config."""
    cfg = get_config()
    ports: Dict[str, Dict[str, int]] = {}
    for name in _BROWSER_TEST_PROJECTS:
        proj = cfg.get_project(name)
        if proj is None:
            continue
        entry = {'frontend': proj.ports.frontend, 'backend': proj.ports.api}
        entry.update(_BROWSER_TEST_PORT_OVERRIDES.get(name, {}))
        ports[name] = entry
    return ports


class BrowserTestConfig:
    """Handles browser test configuration with environment variable expansion."""

    # Default port mappings for FLEET projects (config-derived, see above).
    PROJECT_PORTS = _build_browser_test_ports()

    # Default health check paths per project type
    PROJECT_HEALTH_PATHS = {
        'default': '/health',
        'auth0': '/api/auth0/health',
        'metrics': '/api/metrics/health',
        'monitoring': '/api/monitoring/health',
    }
    
    def __init__(self, project: str, config_path: Optional[str] = None):
        self.project = project
        self.config_path = config_path or self._find_config_file(project)
        self.config = self._load_config()
        self._expand_variables()
        self._apply_defaults()
        
    def _find_config_file(self, project: str) -> Path:
        """Find the browser test config file for a project."""
        fleet_root = get_fleet_root()
        
        # Try multiple locations
        possible_paths = [
            fleet_root / project / 'tests' / 'browser' / 'config.json',
            fleet_root / project / 'browser.config.json',
            fleet_root / 'sega' / 'templates' / 'browser' / 'config.json',
        ]
        
        for path in possible_paths:
            if path.exists():
                return path
                
        # Return default template path
        return fleet_root / 'sega' / 'templates' / 'browser' / 'config.json'
        
    def _load_config(self) -> Dict[str, Any]:
        """Load configuration from file."""
        if not Path(self.config_path).exists():
            return self._get_default_config()
            
        with open(self.config_path, 'r') as f:
            return json.load(f)
            
    def _get_default_config(self) -> Dict[str, Any]:
        """Return default configuration."""
        ports = self.PROJECT_PORTS.get(self.project, {'frontend': 3000, 'backend': 3001})
        
        return {
            'services': {
                'start': 'make dev-shared',
                'healthCheck': f"http://localhost:{ports['frontend']}/health",
                'stop': 'make down'
            },
            'testData': {
                'strategy': 'api_creation_ui_validation',
                'apiBaseUrl': f"http://localhost:{ports['backend']}/api"
            },
            'validation': {
                'tiers': ['static', 'dynamic', 'integration'],
                'successCriteria': 'database_write_then_ui_read'
            },
            'browser': {
                'headless': True,
                'viewport': {'width': 1280, 'height': 720},
                'timeout': 30000
            }
        }
        
    def _expand_variables(self):
        """Expand environment variables in configuration."""
        def expand_value(value):
            if isinstance(value, str):
                # Expand environment variables like ${VAR} or ${VAR:-default}
                import re
                pattern = r'\$\{([^}:]+)(?::-([^}]*))?\}'
                
                def replacer(match):
                    var_name = match.group(1)
                    default_value = match.group(2)
                    if default_value is not None:
                        # Has default value
                        return os.environ.get(var_name, default_value)
                    else:
                        # No default value
                        return os.environ.get(var_name, '')
                
                return re.sub(pattern, replacer, value)
            elif isinstance(value, dict):
                return {k: expand_value(v) for k, v in value.items()}
            elif isinstance(value, list):
                return [expand_value(item) for item in value]
            else:
                return value
                
        self.config = expand_value(self.config)
        
    def _apply_defaults(self):
        """Apply project-specific defaults."""
        # Get project ports with fallback defaults
        ports = self.PROJECT_PORTS.get(self.project, {'frontend': 3000, 'backend': 3001})
        
        # Update ports in URLs if they're using defaults
        if 'services' in self.config:
            services = self.config['services']
            
            # Update health check URL with correct port
            if 'healthCheck' in services and 'localhost:3001' in services['healthCheck']:
                frontend_port = ports.get('frontend', 3001)
                services['healthCheck'] = services['healthCheck'].replace(
                    'localhost:3001', f"localhost:{frontend_port}"
                )
                
        if 'testData' in self.config:
            test_data = self.config['testData']
            
            # Update API base URL with correct port
            if 'apiBaseUrl' in test_data and 'localhost:3001' in test_data['apiBaseUrl']:
                backend_port = ports.get('backend', 3001)
                test_data['apiBaseUrl'] = test_data['apiBaseUrl'].replace(
                    'localhost:3001', f"localhost:{backend_port}"
                )
                
        # Add project-specific metadata if not present
        if 'projectSpecific' not in self.config:
            self.config['projectSpecific'] = {
                'projectName': self.project,
                'ports': ports
            }
        else:
            # Ensure ports are present in existing projectSpecific
            if 'ports' not in self.config['projectSpecific']:
                self.config['projectSpecific']['ports'] = ports
            
    def get(self, path: str, default: Any = None) -> Any:
        """Get a configuration value by dot-separated path."""
        keys = path.split('.')
        value = self.config
        
        for key in keys:
            if isinstance(value, dict) and key in value:
                value = value[key]
            else:
                return default
                
        return value
        
    def update(self, path: str, value: Any):
        """Update a configuration value by dot-separated path."""
        keys = path.split('.')
        target = self.config
        
        for key in keys[:-1]:
            if key not in target:
                target[key] = {}
            target = target[key]
            
        target[keys[-1]] = value
        
    def save(self, path: Optional[str] = None):
        """Save configuration to file."""
        save_path = path or self.config_path
        
        with open(save_path, 'w') as f:
            json.dump(self.config, f, indent=2)
            
    def validate(self) -> Dict[str, Any]:
        """Validate configuration and return issues."""
        issues = []
        
        # Check required fields
        required_fields = [
            'services.start',
            'services.healthCheck',
            'services.stop'
        ]
        
        for field in required_fields:
            if not self.get(field):
                issues.append(f"Missing required field: {field}")
                
        # Check URL formats
        health_check = self.get('services.healthCheck')
        if health_check and not health_check.startswith(('http://', 'https://')):
            issues.append(f"Invalid health check URL: {health_check}")
            
        api_base = self.get('testData.apiBaseUrl')
        if api_base and not api_base.startswith(('http://', 'https://')):
            issues.append(f"Invalid API base URL: {api_base}")
            
        return {
            'valid': len(issues) == 0,
            'issues': issues
        }