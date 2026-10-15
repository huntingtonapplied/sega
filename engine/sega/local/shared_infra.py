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
SEGA Shared Infrastructure Manager
==============================================================================
File: src/sega/deployment/shared_infrastructure.py
Project: SEGA (Scalable Engineering & Growth Automation)
Copyright: 2022-2025 SEGA Contributors
License: Apache-2.0

SEGA MODULE: Deployment/SharedInfrastructure
COMPONENT: Shared Infrastructure Manager
PURPOSE: Manage shared development infrastructure (databases, caches, etc.)
==============================================================================
"""

import subprocess
from pathlib import Path
from typing import Dict, List, Optional, Any
import click
import docker
from docker.errors import DockerException


class SharedInfrastructureManager:
    """Manages shared infrastructure for development."""
    
    def __init__(self, workspace_root: Optional[Path] = None, config: Optional[Dict[str, Any]] = None):
        """Initialize the shared infrastructure manager.
        
        Args:
            workspace_root: Root directory of workspace
            config: Configuration dictionary (if None, will use defaults)
        """
        self.workspace_root = workspace_root or Path.cwd()
        self.config = config or self._load_default_config()
        
        # Extract infrastructure configuration
        infra_config = self.config.get('infrastructure', {})
        self.compose_project_prefix = self.config.get('workspace', {}).get('compose_project_prefix', 'sega')
        self.compose_project_name = f"{self.compose_project_prefix}_infra"
        
        # Set compose file path
        compose_file = infra_config.get('compose_file')
        if compose_file:
            self.infra_compose_path = self.workspace_root / compose_file
        else:
            self.infra_compose_path = None
            
        # Load service configurations from config
        self.services = self._load_services_from_config()
        
        self.docker_client = None
        self._init_docker_client()
        
    def _load_default_config(self) -> Dict[str, Any]:
        """Load default configuration when none provided.
        
        Returns:
            Default configuration dictionary
        """
        return {
            'workspace': {
                'compose_project_prefix': 'sega'
            },
            'infrastructure': {
                'profiles': {
                    'development': {
                        'postgres': {
                            'port': 5432,
                            'database': 'dev_db',
                            'user': 'dev_user',
                            'password': 'dev_password'
                        },
                        'redis': {
                            'port': 6379
                        }
                    },
                    'testing': {
                        'postgres': {
                            'port': 5433,
                            'database': 'test_db',
                            'user': 'test_user',
                            'password': 'test_password'
                        },
                        'redis': {
                            'port': 6380
                        }
                    }
                }
            }
        }
        
    def _load_services_from_config(self) -> Dict[str, Dict[str, Any]]:
        """Load service configurations from config.
        
        Returns:
            Service configuration dictionary
        """
        services = {}
        infra_config = self.config.get('infrastructure', {})
        profiles = infra_config.get('profiles', {})
        
        for profile_name, profile_services in profiles.items():
            services[profile_name] = {}
            
            for service_type, service_config in profile_services.items():
                container_name = f"{self.compose_project_prefix}_{profile_name[:3]}_{service_type}"
                
                services[profile_name][service_type] = {
                    'container': container_name,
                    'port': service_config.get('port'),
                    'db': service_config.get('database', service_config.get('db')),
                    'user': service_config.get('user'),
                    'password': service_config.get('password')
                }
                
        return services
        
    def _init_docker_client(self):
        """Initialize Docker client."""
        try:
            self.docker_client = docker.from_env()
            self.docker_client.ping()
        except DockerException:
            self.docker_client = None
            
    def has_infrastructure_config(self) -> bool:
        """Check if infrastructure is configured.
        
        Returns:
            True if infrastructure compose file exists
        """
        return self.infra_compose_path is not None and self.infra_compose_path.exists()
        
    def start(self, profile: str = 'development', with_tools: bool = False) -> bool:
        """Start shared infrastructure.
        
        Args:
            profile: Profile to use (development, testing, all)
            with_tools: Whether to start management tools
            
        Returns:
            True if successful
        """
        if not self.has_infrastructure_config():
            click.echo("[INFO] No shared infrastructure configured")
            return True
            
        click.echo(f"[INFO] Starting shared infrastructure (profile: {profile})...")
        
        cmd = [
            'docker-compose',
            '-f', str(self.infra_compose_path),
            '-p', self.compose_project_name,
            '--profile', profile
        ]
        
        if with_tools:
            cmd.extend(['--profile', 'tools'])
            
        cmd.extend(['up', '-d'])
        
        try:
            result = subprocess.run(cmd, capture_output=True, text=True)
            if result.returncode == 0:
                click.echo("[OK] Shared infrastructure started")
                self._show_connection_info(profile)
                return True
            else:
                click.echo(f"[ERROR] Failed to start infrastructure: {result.stderr}")
                return False
        except Exception as e:
            click.echo(f"[ERROR] Error starting infrastructure: {e}")
            return False
            
    def stop(self) -> bool:
        """Stop shared infrastructure.
        
        Returns:
            True if successful
        """
        if not self.has_infrastructure_config():
            return True
            
        click.echo("[INFO] Stopping shared infrastructure...")
        
        cmd = [
            'docker-compose',
            '-f', str(self.infra_compose_path),
            '-p', self.compose_project_name,
            'down'
        ]
        
        try:
            result = subprocess.run(cmd, capture_output=True, text=True)
            if result.returncode == 0:
                click.echo("[OK] Shared infrastructure stopped")
                return True
            else:
                click.echo(f"[WARNING] Failed to stop infrastructure: {result.stderr}")
                return False
        except Exception as e:
            click.echo(f"[ERROR] Error stopping infrastructure: {e}")
            return False
            
    def restart(self, profile: str = 'development') -> bool:
        """Restart shared infrastructure.
        
        Args:
            profile: Profile to use
            
        Returns:
            True if successful
        """
        click.echo("[INFO] Restarting shared infrastructure...")
        self.stop()
        return self.start(profile)
        
    def get_status(self) -> Dict[str, Dict]:
        """Get status of infrastructure services.
        
        Returns:
            Dictionary of service status
        """
        if not self.docker_client:
            return {}
            
        status = {}
        
        for env, services in self.services.items():
            status[env] = {}
            
            for service_type, config in services.items():
                container_name = config['container']
                
                try:
                    container = self.docker_client.containers.get(container_name)
                    health = container.attrs.get('State', {}).get('Health', {})
                    
                    status[env][service_type] = {
                        'running': container.status == 'running',
                        'health': health.get('Status', 'unknown'),
                        'port': config.get('port'),
                        'container': container_name
                    }
                except docker.errors.NotFound:
                    status[env][service_type] = {
                        'running': False,
                        'health': 'not found',
                        'port': config.get('port'),
                        'container': container_name
                    }
                except Exception as e:
                    status[env][service_type] = {
                        'running': False,
                        'health': f'error: {e}',
                        'port': config.get('port'),
                        'container': container_name
                    }
                    
        return status
        
    def _show_connection_info(self, profile: str):
        """Show connection information for started services.
        
        Args:
            profile: Profile that was started
        """
        click.echo("\n[INFO] Connection Information:")
        
        infra_config = self.config.get('infrastructure', {})
        
        if profile in ['development', 'all']:
            dev_services = self.services.get('development', {})
            if dev_services:
                click.echo("\n[INFO] Development Services:")
                for service_type, config in dev_services.items():
                    port = config.get('port', 'N/A')
                    click.echo(f"  {service_type.capitalize()}: localhost:{port}")
                    if 'db' in config:
                        click.echo(f"    Database: {config['db']}")
                    if 'user' in config:
                        click.echo(f"    User: {config['user']}")
                    if 'password' in config:
                        click.echo(f"    Password: {config['password']}")
            
        if profile in ['testing', 'all']:
            test_services = self.services.get('testing', {})
            if test_services:
                click.echo("\n[INFO] Testing Services:")
                for service_type, config in test_services.items():
                    port = config.get('port', 'N/A')
                    click.echo(f"  {service_type.capitalize()}: localhost:{port}")
                    if 'db' in config:
                        click.echo(f"    Database: {config['db']}")
                    if 'user' in config:
                        click.echo(f"    User: {config['user']}")
                    if 'password' in config:
                        click.echo(f"    Password: {config['password']}")
                        
        # Show management tools if configured
        mgmt_tools = infra_config.get('management_tools', {})
        if mgmt_tools:
            click.echo("\n[INFO] Management Tools:")
            for tool_name, tool_config in mgmt_tools.items():
                port = tool_config.get('port')
                if port:
                    click.echo(f"  {tool_name.replace('_', ' ').title()}: http://localhost:{port}")
                    if 'email' in tool_config:
                        click.echo(f"    Email: {tool_config['email']}")
                    if 'password' in tool_config:
                        click.echo(f"    Password: {tool_config['password']}")
        
    def create_databases(self, projects: List[str], profile: str = 'development') -> bool:
        """Create project-specific databases.
        
        Args:
            projects: List of project names
            profile: Environment profile
            
        Returns:
            True if successful
        """
        if profile not in self.services:
            click.echo(f"[ERROR] Unknown profile: {profile}")
            return False
            
        pg_config = self.services[profile].get('postgres')
        if not pg_config:
            click.echo(f"[INFO] No PostgreSQL configured for {profile}")
            return True
            
        click.echo(f"[INFO] Creating databases for {len(projects)} projects...")
        
        for project in projects:
            db_name = f"{project}_{profile}"
            
            # Create database using psql
            cmd = [
                'docker', 'exec', '-i', pg_config['container'],
                'psql', '-U', pg_config['user'], '-d', pg_config['db'],
                '-c', f"CREATE DATABASE {db_name} OWNER {pg_config['user']};"
            ]
            
            try:
                result = subprocess.run(cmd, capture_output=True, text=True)
                if result.returncode == 0:
                    click.echo(f"  [OK] Created database: {db_name}")
                elif 'already exists' in result.stderr:
                    click.echo(f"  [INFO] Database already exists: {db_name}")
                else:
                    click.echo(f"  [ERROR] Failed to create database {db_name}: {result.stderr}")
            except Exception as e:
                click.echo(f"  [ERROR] Error creating database {db_name}: {e}")
                
        return True
        
    def backup_databases(self, output_dir: Optional[Path] = None) -> bool:
        """Backup all databases.
        
        Args:
            output_dir: Directory to save backups
            
        Returns:
            True if successful
        """
        if output_dir is None:
            output_dir = self.workspace_root / 'backups'
            
        output_dir.mkdir(parents=True, exist_ok=True)
        
        click.echo(f"[INFO] Backing up databases to {output_dir}...")
        
        # Backup each environment
        for env, services in self.services.items():
            pg_config = services.get('postgres')
            if not pg_config:
                continue
                
            # Check if container is running
            try:
                self.docker_client.containers.get(pg_config['container'])
            except:
                click.echo(f"  [WARNING] Skipping {env} - container not running")
                continue
                
            timestamp = subprocess.check_output(['date', '+%Y%m%d_%H%M%S']).strip().decode()
            backup_file = output_dir / f"{env}_backup_{timestamp}.sql"
            
            cmd = [
                'docker', 'exec', pg_config['container'],
                'pg_dumpall', '-U', pg_config['user']
            ]
            
            try:
                with open(backup_file, 'w') as f:
                    result = subprocess.run(cmd, stdout=f, stderr=subprocess.PIPE, text=True)
                    
                if result.returncode == 0:
                    click.echo(f"  [OK] Backed up {env} to {backup_file.name}")
                else:
                    click.echo(f"  [ERROR] Failed to backup {env}: {result.stderr}")
                    backup_file.unlink()
            except Exception as e:
                click.echo(f"  [ERROR] Error backing up {env}: {e}")
                
        return True