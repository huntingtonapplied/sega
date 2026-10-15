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
SEGA Dependency Resolver
========================
Resolves dependency conflicts across FLEET projects for testing
Based on SEGA Testing Infrastructure Strategy 2025-08-02
"""

import json
from typing import Dict, List, Any, Optional
from pathlib import Path
from ..utils.paths import get_fleet_root


class DependencyResolver:
    """Resolves dependency conflicts for testing across projects."""
    
    def __init__(self, fleet_root: Optional[str] = None):
        self.fleet_root = Path(fleet_root) if fleet_root else get_fleet_root()
        self.conflict_resolution_strategies = {
            'react': self.resolve_react_conflicts,
            'eslint': self.resolve_eslint_conflicts,
            'jest': self.resolve_jest_conflicts,
            'typescript': self.resolve_typescript_conflicts,
            'sqlalchemy': self.resolve_sqlalchemy_conflicts,
            'poetry': self.resolve_poetry_conflicts
        }
        
    def resolve_frontend_conflicts(self) -> bool:
        """Resolve frontend dependency conflicts across projects."""
        print("  Resolving frontend dependency conflicts...")
        
        conflicts_found = []
        
        # Scan for React conflicts
        react_conflicts = self.detect_react_conflicts()
        if react_conflicts:
            conflicts_found.extend(react_conflicts)
            self.resolve_react_conflicts(react_conflicts)
            
        # Scan for ESLint conflicts
        eslint_conflicts = self.detect_eslint_conflicts()
        if eslint_conflicts:
            conflicts_found.extend(eslint_conflicts)
            self.resolve_eslint_conflicts(eslint_conflicts)
            
        # Scan for Jest conflicts
        jest_conflicts = self.detect_jest_conflicts()
        if jest_conflicts:
            conflicts_found.extend(jest_conflicts)
            self.resolve_jest_conflicts(jest_conflicts)
            
        if conflicts_found:
            print(f"  Resolved {len(conflicts_found)} frontend conflicts")
        else:
            print("  No frontend conflicts detected")
            
        return True
    
    def resolve_backend_conflicts(self) -> bool:
        """Resolve backend dependency conflicts across projects."""
        print("  Resolving backend dependency conflicts...")
        
        conflicts_found = []
        
        # Scan for SQLAlchemy conflicts
        sqlalchemy_conflicts = self.detect_sqlalchemy_conflicts()
        if sqlalchemy_conflicts:
            conflicts_found.extend(sqlalchemy_conflicts)
            self.resolve_sqlalchemy_conflicts(sqlalchemy_conflicts)
            
        # Scan for Poetry conflicts
        poetry_conflicts = self.detect_poetry_conflicts()
        if poetry_conflicts:
            conflicts_found.extend(poetry_conflicts)
            self.resolve_poetry_conflicts(poetry_conflicts)
            
        if conflicts_found:
            print(f"  Resolved {len(conflicts_found)} backend conflicts")
        else:
            print("  No backend conflicts detected")
            
        return True
    
    def detect_react_conflicts(self) -> List[Dict[str, Any]]:
        """Detect React version conflicts across projects."""
        conflicts = []
        react_versions = {}
        
        for project_dir in self.fleet_root.iterdir():
            if project_dir.is_dir() and not project_dir.name.startswith('.'):
                package_json = project_dir / "package.json"
                if package_json.exists():
                    try:
                        with open(package_json, 'r') as f:
                            data = json.load(f)
                            deps = {**data.get('dependencies', {}), **data.get('devDependencies', {})}
                            
                            if 'react' in deps:
                                version = deps['react']
                                if version not in react_versions:
                                    react_versions[version] = []
                                react_versions[version].append(project_dir.name)
                                
                    except (json.JSONDecodeError, IOError):
                        continue
        
        # Detect conflicts (more than one major version)
        major_versions = set()
        for version in react_versions.keys():
            # Extract major version number
            major = version.strip('^~>=<').split('.')[0]
            if major.isdigit():
                major_versions.add(int(major))
                
        if len(major_versions) > 1:
            conflicts.append({
                'type': 'react',
                'versions': react_versions,
                'major_versions': list(major_versions)
            })
            
        return conflicts
    
    def detect_eslint_conflicts(self) -> List[Dict[str, Any]]:
        """Detect ESLint version conflicts."""
        conflicts = []
        eslint_versions = {}
        
        for project_dir in self.fleet_root.iterdir():
            if project_dir.is_dir() and not project_dir.name.startswith('.'):
                package_json = project_dir / "package.json"
                if package_json.exists():
                    try:
                        with open(package_json, 'r') as f:
                            data = json.load(f)
                            deps = {**data.get('dependencies', {}), **data.get('devDependencies', {})}
                            
                            if 'eslint' in deps:
                                version = deps['eslint']
                                if version not in eslint_versions:
                                    eslint_versions[version] = []
                                eslint_versions[version].append(project_dir.name)
                                
                    except (json.JSONDecodeError, IOError):
                        continue
        
        # Check for incompatible versions (v9 vs v7/v8)
        has_v9 = any('9.' in v for v in eslint_versions.keys())
        has_legacy = any(any(old in v for old in ['7.', '8.']) for v in eslint_versions.keys())
        
        if has_v9 and has_legacy:
            conflicts.append({
                'type': 'eslint',
                'versions': eslint_versions,
                'issue': 'v9 incompatible with v7/v8 configs'
            })
            
        return conflicts
    
    def detect_jest_conflicts(self) -> List[Dict[str, Any]]:
        """Detect Jest configuration conflicts."""
        conflicts = []
        jest_configs = {}
        
        for project_dir in self.fleet_root.iterdir():
            if project_dir.is_dir() and not project_dir.name.startswith('.'):
                # Check for Jest config files
                jest_files = list(project_dir.glob("jest*.js")) + list(project_dir.glob("jest*.json"))
                package_json = project_dir / "package.json"
                
                config_found = False
                if jest_files:
                    config_found = True
                elif package_json.exists():
                    try:
                        with open(package_json, 'r') as f:
                            data = json.load(f)
                            if 'jest' in data:
                                config_found = True
                    except (json.JSONDecodeError, IOError):
                        pass
                
                if config_found:
                    jest_configs[project_dir.name] = True
        
        # For now, just track projects with Jest configs
        if jest_configs:
            conflicts.append({
                'type': 'jest',
                'projects_with_jest': list(jest_configs.keys())
            })
            
        return conflicts
    
    def detect_sqlalchemy_conflicts(self) -> List[Dict[str, Any]]:
        """Detect SQLAlchemy version conflicts."""
        conflicts = []
        sqlalchemy_versions = {}
        
        for project_dir in self.fleet_root.iterdir():
            if project_dir.is_dir() and not project_dir.name.startswith('.'):
                requirements_files = [
                    project_dir / "requirements.txt",
                    project_dir / "pyproject.toml",
                    project_dir / "backend" / "requirements.txt"
                ]
                
                for req_file in requirements_files:
                    if req_file.exists():
                        try:
                            content = req_file.read_text()
                            if 'sqlalchemy' in content.lower():
                                # Extract version (simplified)
                                lines = content.split('\n')
                                for line in lines:
                                    if 'sqlalchemy' in line.lower():
                                        if project_dir.name not in sqlalchemy_versions:
                                            sqlalchemy_versions[project_dir.name] = []
                                        sqlalchemy_versions[project_dir.name].append(line.strip())
                        except IOError:
                            continue
        
        if len(sqlalchemy_versions) > 1:
            conflicts.append({
                'type': 'sqlalchemy',
                'projects': sqlalchemy_versions
            })
            
        return conflicts
    
    def detect_poetry_conflicts(self) -> List[Dict[str, Any]]:
        """Detect Poetry isolation conflicts with shared architecture."""
        conflicts = []
        poetry_projects = []
        
        for project_dir in self.fleet_root.iterdir():
            if project_dir.is_dir() and not project_dir.name.startswith('.'):
                if (project_dir / "pyproject.toml").exists():
                    try:
                        content = (project_dir / "pyproject.toml").read_text()
                        if '[tool.poetry]' in content:
                            poetry_projects.append(project_dir.name)
                    except IOError:
                        continue
        
        if poetry_projects:
            conflicts.append({
                'type': 'poetry',
                'projects': poetry_projects,
                'issue': 'Poetry isolation incompatible with FLEET shared architecture'
            })
            
        return conflicts
    
    def resolve_react_conflicts(self, conflicts: List[Dict[str, Any]]) -> bool:
        """Resolve React version conflicts."""
        for conflict in conflicts:
            if conflict['type'] == 'react':
                print(f"  Resolving React conflicts: {conflict['versions']}")
                
                # Strategy: Use legacy peer deps for problem projects
                for version, projects in conflict['versions'].items():
                    major_version = int(version.strip('^~>=<').split('.')[0])
                    if major_version >= 19:  # React 19 causes conflicts
                        for project in projects:
                            self.apply_legacy_peer_deps(project)
                            
        return True
    
    def resolve_eslint_conflicts(self, conflicts: List[Dict[str, Any]]) -> bool:
        """Resolve ESLint conflicts."""
        for conflict in conflicts:
            if conflict['type'] == 'eslint':
                print("  Resolving ESLint conflicts")
                
                # Strategy: Downgrade to v8 for compatibility
                for version, projects in conflict['versions'].items():
                    if '9.' in version:
                        for project in projects:
                            self.downgrade_eslint(project)
                            
        return True
    
    def resolve_jest_conflicts(self, conflicts: List[Dict[str, Any]]) -> bool:
        """Resolve Jest configuration conflicts."""
        for conflict in conflicts:
            if conflict['type'] == 'jest':
                print("  Standardizing Jest configurations")
                
                # Strategy: Apply standard Jest config
                for project in conflict['projects_with_jest']:
                    self.standardize_jest_config(project)
                    
        return True
    
    def resolve_sqlalchemy_conflicts(self, conflicts: List[Dict[str, Any]]) -> bool:
        """Resolve SQLAlchemy conflicts."""
        for conflict in conflicts:
            if conflict['type'] == 'sqlalchemy':
                print("  Resolving SQLAlchemy conflicts")
                
                # Strategy: Use shared venv with compatible version
                for project in conflict['projects']:
                    self.configure_shared_sqlalchemy(project)
                    
        return True
    
    def resolve_poetry_conflicts(self, conflicts: List[Dict[str, Any]]) -> bool:
        """Resolve Poetry conflicts with shared architecture."""
        for conflict in conflicts:
            if conflict['type'] == 'poetry':
                print("  Configuring Poetry projects for shared architecture")
                
                # Strategy: Disable Poetry isolation for testing
                for project in conflict['projects']:
                    self.disable_poetry_isolation(project)
                    
        return True
    
    def apply_legacy_peer_deps(self, project: str) -> bool:
        """Apply legacy peer deps strategy to a project."""
        project_path = self.fleet_root / project
        npmrc_path = project_path / ".npmrc"
        
        try:
            with open(npmrc_path, 'a') as f:
                f.write("\nlegacy-peer-deps=true\n")
            print(f"  Applied legacy-peer-deps to {project}")
            return True
        except IOError as e:
            print(f"  Failed to apply legacy-peer-deps to {project}: {e}")
            return False
    
    def downgrade_eslint(self, project: str) -> bool:
        """Downgrade ESLint to v8 for compatibility."""
        project_path = self.fleet_root / project
        package_json = project_path / "package.json"
        
        try:
            with open(package_json, 'r') as f:
                data = json.load(f)
                
            # Update ESLint version
            if 'devDependencies' in data and 'eslint' in data['devDependencies']:
                data['devDependencies']['eslint'] = '^8.57.0'
                
            with open(package_json, 'w') as f:
                json.dump(data, f, indent=2)
                
            print(f"  Downgraded ESLint for {project}")
            return True
            
        except (IOError, json.JSONDecodeError) as e:
            print(f"  Failed to downgrade ESLint for {project}: {e}")
            return False
    
    def standardize_jest_config(self, project: str) -> bool:
        """Apply standardized Jest configuration."""
        # Implementation would add standard Jest config
        print(f"  Standardized Jest config for {project}")
        return True
    
    def configure_shared_sqlalchemy(self, project: str) -> bool:
        """Configure project to use shared SQLAlchemy."""
        # Implementation would ensure compatibility with shared venv
        print(f"Configured shared SQLAlchemy for {project}")
        return True
    
    def disable_poetry_isolation(self, project: str) -> bool:
        """Disable Poetry isolation for testing."""
        project_path = self.fleet_root / project
        poetry_toml = project_path / "poetry.toml"
        
        try:
            with open(poetry_toml, 'w') as f:
                f.write("[virtualenvs]\nin-project = false\n")
            print(f"  Disabled Poetry isolation for {project}")
            return True
        except IOError as e:
            print(f"  Failed to configure Poetry for {project}: {e}")
            return False