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
SEGA UNIFIED SERVER MANAGEMENT COMMAND
==============================================================================
File: src/sega/commands/unified_server.py
Project: SEGA (Scalable Engineering & Growth Automation)
Copyright: 2022-2025 FLEET
License: Apache-2.0

SEGA MODULE: Commands/UnifiedServer
COMPONENT: Single-Server Multi-Project Deployment Management
PURPOSE: Manage reverse proxy setup for cost-effective multi-project hosting
DEPENDENCIES: click, jinja2, subprocess
USAGE: sega unified-server [setup|start|stop|status|config|urls]

This command provides infrastructure for hosting multiple FLEET projects on a
single server using nginx reverse proxy, reducing costs during early development.

Configuration is loaded from config/sega.toml (TOML-based central configuration).
==============================================================================
"""

import click
import subprocess
from pathlib import Path
from typing import Dict, Any, Optional, List
from datetime import datetime
import json
import socket

from sega.core.config import get_config, SegaConfig


class UnifiedServerManager:
    """Manages unified server infrastructure for multiple FLEET projects."""

    def __init__(self):
        self.config = get_config()
        self.templates_path = Path(__file__).parent.parent.parent / 'templates' / 'nginx'

    @property
    def infra(self):
        """Shortcut to infrastructure config."""
        return self.config.infrastructure

    @property
    def unified_server(self):
        """Shortcut to unified server config."""
        return self.infra.unified_server

    def get_project_port(self, project_name: str, port_type: str = "api") -> Optional[int]:
        """Get port for a project using computed port formulas."""
        project = self.config.get_project(project_name)
        if project:
            return getattr(project.ports, port_type, None)
        return None

    def get_instance_ip(self, project_name: str) -> Optional[str]:
        """Get the EC2 instance IP for a project deployment."""
        return self.config.get_instance_ip(project_name)

    def get_all_projects(self) -> List[str]:
        """Get list of all project names."""
        return list(self.config.projects.keys())

    def get_served_projects(self) -> List[str]:
        """Get list of projects that are served (deployed to EC2)."""
        return [p.name for p in self.config.get_served_projects()]

    def setup_reverse_proxy(self, template: str = 'simple', domain: str = None, dry_run: bool = False) -> bool:
        """Setup nginx reverse proxy configuration."""
        try:
            # Choose template
            if template == 'simple':
                template_file = self.templates_path / 'unified_server_simple.conf.j2'
            else:
                template_file = self.templates_path / 'unified_server.conf.j2'

            if not template_file.exists():
                click.echo(f"[ERROR] Template not found: {template_file}")
                return False

            # Load and render template
            try:
                from jinja2 import Template
            except ImportError:
                click.echo("[ERROR] jinja2 not installed. Install with: pip install jinja2")
                return False

            with open(template_file, 'r') as f:
                template_content = f.read()

            jinja_template = Template(template_content)

            # Prepare template variables from TOML config
            template_vars = {
                'domain': domain or self.unified_server.domain,
                'ssl_enabled': self.unified_server.ssl.enabled,
                'ssl_cert_path': self.unified_server.ssl.cert_path,
                'ssl_key_path': self.unified_server.ssl.key_path,
                'projects': self._get_projects_for_template(),
                'routing': self.infra.routing,
                'security': self.infra.security,
                'timestamp': datetime.now().isoformat(),
            }

            # Render configuration
            nginx_config = jinja_template.render(**template_vars)

            if dry_run:
                click.echo("[INFO] Dry run - Generated nginx configuration:")
                click.echo("=" * 80)
                click.echo(nginx_config)
                click.echo("=" * 80)
                return True

            # Write configuration file
            nginx_config_dir = Path(self.unified_server.reverse_proxy.config_path)
            nginx_config_file = nginx_config_dir / 'fleet-unified-server'

            # Ensure directory exists
            nginx_config_dir.mkdir(parents=True, exist_ok=True)

            with open(nginx_config_file, 'w') as f:
                f.write(nginx_config)

            click.echo(f"[OK] Nginx configuration written to: {nginx_config_file}")

            # Enable site
            enabled_dir = Path(self.unified_server.reverse_proxy.enabled_path)
            enabled_link = enabled_dir / 'fleet-unified-server'

            if not enabled_link.exists():
                enabled_dir.mkdir(parents=True, exist_ok=True)
                enabled_link.symlink_to(nginx_config_file)
                click.echo(f"[OK] Site enabled: {enabled_link}")
            else:
                click.echo(f"[INFO] Site already enabled: {enabled_link}")

            return True

        except Exception as e:
            click.echo(f"[ERROR] Failed to setup reverse proxy: {e}")
            return False

    def _get_projects_for_template(self) -> Dict[str, Dict[str, Any]]:
        """Get project data formatted for Jinja template."""
        projects = {}
        for name, project in self.config.projects.items():
            projects[name] = {
                'id': project.id,
                'name': project.name,
                'description': project.description,
                'ports': project.ports.to_dict(),
                'has_frontend': project.has_frontend,
                'has_mobile': project.has_mobile,
                'has_desktop': project.has_desktop,
                'is_served': project.is_served,
            }
        return projects

    def start_nginx_service(self) -> bool:
        """Start nginx service."""
        try:
            service_name = self.unified_server.reverse_proxy.service_name

            # Test nginx configuration first
            result = subprocess.run(
                ['nginx', '-t'],
                capture_output=True,
                text=True
            )

            if result.returncode != 0:
                click.echo("[ERROR] Nginx configuration test failed:")
                click.echo(result.stderr)
                return False

            # Start/reload nginx
            result = subprocess.run(
                ['systemctl', 'start', service_name],
                capture_output=True,
                text=True
            )

            if result.returncode == 0:
                click.echo(f"[OK] {service_name} started successfully")

                # Reload to pick up new configuration
                subprocess.run(['systemctl', 'reload', service_name])
                click.echo(f"[OK] {service_name} configuration reloaded")
                return True
            else:
                click.echo(f"[ERROR] Failed to start {service_name}:")
                click.echo(result.stderr)
                return False

        except FileNotFoundError:
            click.echo("[ERROR] nginx or systemctl not found. Please install nginx.")
            return False
        except Exception as e:
            click.echo(f"[ERROR] Failed to start nginx: {e}")
            return False

    def stop_nginx_service(self) -> bool:
        """Stop nginx service."""
        try:
            service_name = self.unified_server.reverse_proxy.service_name

            result = subprocess.run(
                ['systemctl', 'stop', service_name],
                capture_output=True,
                text=True
            )

            if result.returncode == 0:
                click.echo(f"[OK] {service_name} stopped successfully")
                return True
            else:
                click.echo(f"[ERROR] Failed to stop {service_name}:")
                click.echo(result.stderr)
                return False

        except Exception as e:
            click.echo(f"[ERROR] Failed to stop nginx: {e}")
            return False

    def get_service_status(self) -> Dict[str, Any]:
        """Get unified server status."""
        status = {
            'unified_server': {
                'configured': False,
                'nginx_running': False,
                'config_valid': False
            },
            'projects': {}
        }

        try:
            # Check if configuration exists
            nginx_config_file = Path(self.unified_server.reverse_proxy.config_path) / 'fleet-unified-server'
            status['unified_server']['configured'] = nginx_config_file.exists()

            # Check nginx service status
            service_name = self.unified_server.reverse_proxy.service_name
            result = subprocess.run(
                ['systemctl', 'is-active', service_name],
                capture_output=True,
                text=True
            )
            status['unified_server']['nginx_running'] = result.stdout.strip() == 'active'

            # Test nginx configuration
            if status['unified_server']['configured']:
                result = subprocess.run(
                    ['nginx', '-t'],
                    capture_output=True,
                    text=True
                )
                status['unified_server']['config_valid'] = result.returncode == 0

            # Check project service availability
            if self.infra.monitoring.project_health.enabled:
                status['projects'] = self._check_project_health()

        except Exception as e:
            click.echo(f"[WARNING] Could not get complete status: {e}")

        return status

    def _check_project_health(self) -> Dict[str, Dict[str, bool]]:
        """Check health of individual project services."""
        project_health = {}
        check_services = self.infra.monitoring.project_health.check_services

        for name, project in self.config.projects.items():
            if not project.is_served:
                continue

            project_health[name] = {}

            for service_name in check_services:
                port = getattr(project.ports, service_name, None)
                if port:
                    try:
                        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                        sock.settimeout(1)
                        result = sock.connect_ex(('127.0.0.1', port))
                        project_health[name][service_name] = result == 0
                        sock.close()
                    except Exception:
                        project_health[name][service_name] = False

        return project_health

    def generate_project_urls(self, routing_type: str = 'path') -> Dict[str, Dict[str, str]]:
        """Generate URLs for all project services."""
        urls = {}
        domain = self.unified_server.domain
        ssl = self.unified_server.ssl.enabled
        protocol = 'https' if ssl else 'http'

        for name, project in self.config.projects.items():
            if not project.is_served:
                continue

            urls[name] = {}

            if routing_type == 'subdomain' and self.infra.routing.subdomain.enabled:
                urls[name]['frontend'] = f"{protocol}://{name}.{domain}"
                urls[name]['api'] = f"{protocol}://{name}-api.{domain}"
                if project.has_mobile:
                    urls[name]['mobile'] = f"{protocol}://{name}-mobile.{domain}"
                if project.has_desktop:
                    urls[name]['desktop'] = f"{protocol}://{name}-desktop.{domain}"

            elif routing_type == 'path' and self.infra.routing.path.enabled:
                api_prefix = self.infra.routing.path.api_prefix
                mobile_prefix = self.infra.routing.path.mobile_prefix
                desktop_prefix = self.infra.routing.path.desktop_prefix

                urls[name]['frontend'] = f"{protocol}://{domain}/{name}/"
                urls[name]['api'] = f"{protocol}://{domain}{api_prefix}/{name}/"
                if project.has_mobile:
                    urls[name]['mobile'] = f"{protocol}://{domain}{mobile_prefix}/{name}/"
                if project.has_desktop:
                    urls[name]['desktop'] = f"{protocol}://{domain}{desktop_prefix}/{name}/"

            elif routing_type == 'port':
                urls[name]['frontend'] = f"http://localhost:{project.ports.frontend}"
                urls[name]['api'] = f"http://localhost:{project.ports.api}"
                if project.has_mobile:
                    urls[name]['mobile'] = f"http://localhost:{project.ports.mobile}"
                if project.has_desktop:
                    urls[name]['desktop'] = f"http://localhost:{project.ports.desktop}"

        return urls


@click.group()
def unified_server():
    """Manage unified server infrastructure for cost-effective multi-project hosting.

    This command helps setup and manage a reverse proxy configuration that allows
    multiple FLEET projects to be served from a single server, reducing infrastructure
    costs during early development phases.

    Configuration is loaded from config/sega.toml.
    """
    pass


@unified_server.command()
@click.option('--template', type=click.Choice(['simple', 'advanced']), default='simple',
              help='Configuration template to use')
@click.option('--domain', help='Override default domain')
@click.option('--dry-run', is_flag=True, help='Show generated configuration without applying')
def setup(template, domain, dry_run):
    """Setup reverse proxy configuration for unified server.

    Examples:
        sega unified-server setup                    # Basic setup with simple template
        sega unified-server setup --template advanced # Full-featured template
        sega unified-server setup --dry-run          # Preview configuration
        sega unified-server setup --domain fleet-dev.example.com   # Custom domain
    """
    try:
        manager = UnifiedServerManager()

        click.echo(f"[INFO] Setting up unified server with {template} template...")

        if domain:
            click.echo(f"[INFO] Using custom domain: {domain}")

        success = manager.setup_reverse_proxy(template=template, domain=domain, dry_run=dry_run)

        if success and not dry_run:
            click.echo("\n[OK] Reverse proxy setup completed!")
            click.echo("\nNext steps:")
            click.echo("  sega unified-server start    # Start nginx service")
            click.echo("  sega unified-server status   # Check service status")
            click.echo("  sega unified-server urls     # Show project URLs")
        elif success and dry_run:
            click.echo("\n[INFO] Dry run completed successfully")
        else:
            click.echo("\n[ERROR] Setup failed")
            exit(1)

    except Exception as e:
        click.echo(f"[ERROR] Setup failed: {e}")
        exit(1)


@unified_server.command()
def start():
    """Start unified server (nginx) service.

    This will start the nginx service and reload configuration to serve
    all configured FLEET projects through the reverse proxy.
    """
    try:
        manager = UnifiedServerManager()

        click.echo("[INFO] Starting unified server service...")

        success = manager.start_nginx_service()

        if success:
            click.echo("\n[OK] Unified server started successfully!")
            click.echo("\nService is now running. Use 'sega unified-server status' to check health.")
        else:
            click.echo("\n[ERROR] Failed to start unified server")
            exit(1)

    except Exception as e:
        click.echo(f"[ERROR] Start failed: {e}")
        exit(1)


@unified_server.command()
def stop():
    """Stop unified server (nginx) service.

    This will stop the nginx service, making all proxied services unavailable
    until the service is started again.
    """
    try:
        manager = UnifiedServerManager()

        click.echo("[INFO] Stopping unified server service...")

        success = manager.stop_nginx_service()

        if success:
            click.echo("\n[OK] Unified server stopped successfully!")
        else:
            click.echo("\n[ERROR] Failed to stop unified server")
            exit(1)

    except Exception as e:
        click.echo(f"[ERROR] Stop failed: {e}")
        exit(1)


@unified_server.command()
@click.option('--format', 'output_format', type=click.Choice(['table', 'json']), default='table',
              help='Output format')
@click.option('--check-health', is_flag=True, help='Check individual project health')
def status(output_format, check_health):
    """Show unified server status and project health.

    Examples:
        sega unified-server status                # Show basic status
        sega unified-server status --check-health # Include project health checks
        sega unified-server status --format json  # JSON output
    """
    try:
        manager = UnifiedServerManager()

        click.echo("[INFO] Checking unified server status...")

        status_data = manager.get_service_status()

        if output_format == 'json':
            click.echo(json.dumps(status_data, indent=2))
            return

        # Table format
        click.echo("\n" + "=" * 60)
        click.echo("FLEET Unified Server Status")
        click.echo("=" * 60)

        # Server status
        server_status = status_data['unified_server']
        click.echo("\nServer Status:")
        click.echo(f"  Configured:     {'[OK]' if server_status['configured'] else '[ERROR]'}")
        click.echo(f"  Nginx Running:  {'[OK]' if server_status['nginx_running'] else '[ERROR]'}")
        click.echo(f"  Config Valid:   {'[OK]' if server_status['config_valid'] else '[ERROR]'}")

        # Project health (if requested)
        if check_health and status_data.get('projects'):
            click.echo("\nProject Health:")
            for project_name, services in status_data['projects'].items():
                click.echo(f"\n  {project_name}:")
                for service_name, healthy in services.items():
                    status_icon = '[OK]' if healthy else '[DOWN]'
                    click.echo(f"    {service_name}: {status_icon}")

        # Overall status
        overall_healthy = (server_status['configured'] and
                          server_status['nginx_running'] and
                          server_status['config_valid'])

        click.echo(f"\nOverall Status: {'[HEALTHY]' if overall_healthy else '[UNHEALTHY]'}")

        if not overall_healthy:
            click.echo("\nTroubleshooting:")
            if not server_status['configured']:
                click.echo("  - Run 'sega unified-server setup' to configure")
            if not server_status['nginx_running']:
                click.echo("  - Run 'sega unified-server start' to start nginx")
            if not server_status['config_valid']:
                click.echo("  - Check nginx configuration with 'nginx -t'")

    except Exception as e:
        click.echo(f"[ERROR] Status check failed: {e}")
        exit(1)


@unified_server.command()
@click.option('--routing', type=click.Choice(['path', 'subdomain', 'port']), default='path',
              help='URL routing type to show')
@click.option('--format', 'output_format', type=click.Choice(['table', 'json', 'list']), default='table',
              help='Output format')
def urls(routing, output_format):
    """Show URLs for all project services.

    Examples:
        sega unified-server urls                      # Path-based URLs
        sega unified-server urls --routing subdomain  # Subdomain-based URLs
        sega unified-server urls --routing port       # Direct port URLs
        sega unified-server urls --format json        # JSON output
    """
    try:
        manager = UnifiedServerManager()

        click.echo(f"[INFO] Generating {routing}-based URLs...")

        urls_data = manager.generate_project_urls(routing_type=routing)

        if output_format == 'json':
            click.echo(json.dumps(urls_data, indent=2))
            return

        elif output_format == 'list':
            for project_name, services in urls_data.items():
                for service_name, url in services.items():
                    click.echo(f"{url}")
            return

        # Table format
        click.echo("\n" + "=" * 80)
        click.echo(f"FLEET Project URLs ({routing} routing)")
        click.echo("=" * 80)

        for project_name, services in sorted(urls_data.items()):
            if services:  # Only show projects with URLs
                click.echo(f"\n{project_name}:")
                for service_name, url in sorted(services.items()):
                    click.echo(f"  {service_name:<10} {url}")

    except Exception as e:
        click.echo(f"[ERROR] URL generation failed: {e}")
        exit(1)


@unified_server.command()
@click.option('--format', 'output_format', type=click.Choice(['toml', 'json']), default='toml',
              help='Output format')
def config(output_format):
    """Show current unified server configuration.

    Examples:
        sega unified-server config                # Show TOML config summary
        sega unified-server config --format json  # JSON output
    """
    try:
        manager = UnifiedServerManager()
        infra = manager.infra

        if output_format == 'json':
            config_data = {
                'unified_server': {
                    'name': infra.unified_server.name,
                    'domain': infra.unified_server.domain,
                    'ssl_enabled': infra.unified_server.ssl.enabled,
                    'reverse_proxy': {
                        'type': infra.unified_server.reverse_proxy.type,
                        'service_name': infra.unified_server.reverse_proxy.service_name,
                    },
                },
                'routing': {
                    'subdomain_enabled': infra.routing.subdomain.enabled,
                    'path_enabled': infra.routing.path.enabled,
                    'port_enabled': infra.routing.port.enabled,
                },
                'monitoring': {
                    'enabled': infra.monitoring.enabled,
                    'health_check_path': infra.monitoring.health_check_path,
                },
                'security': {
                    'rate_limiting_enabled': infra.security.rate_limiting.enabled,
                    'cors_enabled': infra.security.cors.enabled,
                },
            }
            click.echo(json.dumps(config_data, indent=2))
            return

        # TOML-style summary
        click.echo("Unified Server Configuration (from sega.toml)")
        click.echo("=" * 50)
        click.echo(f"\n[unified_server]")
        click.echo(f"  name = \"{infra.unified_server.name}\"")
        click.echo(f"  domain = \"{infra.unified_server.domain}\"")
        click.echo(f"  ssl.enabled = {str(infra.unified_server.ssl.enabled).lower()}")
        click.echo(f"\n[reverse_proxy]")
        click.echo(f"  type = \"{infra.unified_server.reverse_proxy.type}\"")
        click.echo(f"  config_path = \"{infra.unified_server.reverse_proxy.config_path}\"")
        click.echo(f"  service_name = \"{infra.unified_server.reverse_proxy.service_name}\"")
        click.echo(f"\n[routing]")
        click.echo(f"  subdomain.enabled = {str(infra.routing.subdomain.enabled).lower()}")
        click.echo(f"  path.enabled = {str(infra.routing.path.enabled).lower()}")
        click.echo(f"\n[monitoring]")
        click.echo(f"  enabled = {str(infra.monitoring.enabled).lower()}")
        click.echo(f"  health_check_path = \"{infra.monitoring.health_check_path}\"")

    except Exception as e:
        click.echo(f"[ERROR] Config display failed: {e}")
        exit(1)


# Register the command group
if __name__ == '__main__':
    unified_server()
