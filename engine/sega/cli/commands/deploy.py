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
SEGA MULTI-DOMAIN DEPLOYMENT COMMAND
==============================================================================
File: src/sega/commands/deploy.py
Project: SEGA (Scalable Engineering & Growth Automation)
Copyright: 2022-2025 FLEET
License: Apache-2.0

SEGA MODULE: Commands/MultiDomainDeployment
COMPONENT: Auto-Detected Pipeline Deployment CLI Command
PURPOSE: Deploy projects to target environments with auto-detected pipelines
DEPENDENCIES: click, pathlib, ProjectDetector, DeploymentService, dependency_injection
USAGE: sega deploy --target ENV [--strategy STRATEGY] [--dry-run] [--force]

This command provides intelligent deployment with auto-detected project types,
dependency injection, and support for multiple deployment strategies.
==============================================================================
"""

import click
from pathlib import Path
from ...core.dependency_injection import inject
from ...project.project_detector import ProjectDetector
from ...services.deployment_service import DeploymentService
from ...ship.registry import RegistryDeployer, DeploymentConfig
from ...ship.production import ProductionSetup, ProductionConfig


@click.command()
@click.option(
    "--target", required=True, help="Target environment (staging, prod)"
)
@click.option("--strategy", default="rolling", help="Deployment strategy")
@click.option(
    "--domains",
    multiple=True,
    help="Specify domains to deploy (software, embedded, fpga, bare-metal). If not specified, all detected domains are deployed."
)
@click.option(
    "--dry-run", is_flag=True, help="Preview changes without deploying"
)
@click.option(
    "--force", is_flag=True, help="Force deployment without confirmations"
)
@click.option(
    "--setup-nginx", is_flag=True, help="Automatically setup nginx reverse proxy after deployment"
)
@click.option(
    "--domain", help="Domain name for nginx setup (auto-detected if not provided)"
)
@click.option(
    "--ssl", is_flag=True, help="Setup SSL certificates with Let's Encrypt"
)
# Modern Docker Registry deployment options
@click.option(
    "--image", help="Docker image to deploy (registry.example.com/fleet/project:tag)"
)
@click.option(
    "--registry", help="Container registry URL (defaults to GitLab Container Registry)"
)
@click.option(
    "--version", help="Specific version/tag to deploy (defaults to latest)"
)
@click.option(
    "--backup-previous", is_flag=True, help="Backup previous deployment before updating"
)
@click.option(
    "--wait-for-health", is_flag=True, help="Wait for health check to pass after deployment"
)
@click.option(
    "--health-check-timeout", default=60, help="Health check timeout in seconds"
)
@click.option(
    "--port-mapping", help="Port mapping in format 'host:container,host2:container2'"
)
@click.option(
    "--environment", help="Environment name (overrides --target for clarity)"
)
@inject(ProjectDetector, DeploymentService)
def deploy(
    target: str,
    strategy: str,
    domains: tuple,
    dry_run: bool,
    force: bool,
    setup_nginx: bool,
    domain: str,
    ssl: bool,
    # Modern Docker Registry parameters
    image: str,
    registry: str,
    version: str,
    backup_previous: bool,
    wait_for_health: bool,
    health_check_timeout: int,
    port_mapping: str,
    environment: str,
    project_detector: ProjectDetector = None,
    deployment_service: DeploymentService = None,
):
    """Deploy project to target environment with auto-detected pipeline."""

    # Use environment parameter if provided, otherwise use target
    deploy_env = environment if environment else target

    # Modern Docker Registry deployment path
    if image:
        success = _deploy_from_registry(
            image=image,
            registry=registry,
            version=version,
            environment=deploy_env,
            strategy=strategy,
            backup_previous=backup_previous,
            wait_for_health=wait_for_health,
            health_check_timeout=health_check_timeout,
            port_mapping=port_mapping,
            setup_nginx=setup_nginx,
            domain=domain,
            ssl=ssl,
            dry_run=dry_run,
            force=force
        )
        if not success and not dry_run:
            raise click.Abort()
        return

    # Detect project type
    project_type = project_detector.detect()
    config = project_detector.get_build_config()

    click.echo(f"Detected project type: {project_type}")
    click.echo(f"Using deployer: {config['deployer']}")
    
    # Handle domain filtering
    if domains:
        click.echo(f"Deploying to domains: {', '.join(domains)}")
        # Map project types to domains
        domain_mapping = {
            'software': ['web_app', 'service_app', 'api_server'],
            'embedded': ['firmware_edge', 'embedded_system'],
            'fpga': ['hdl_fpga', 'fpga_bitstream'],
            'bare-metal': ['bare_metal', 'hardware_controller']
        }
        
        # Check if current project type matches requested domains
        project_domains = []
        for domain, types in domain_mapping.items():
            if project_type in types:
                project_domains.append(domain)
        
        if not any(d in domains for d in project_domains):
            click.echo(f"Project type '{project_type}' does not match requested domains: {', '.join(domains)}")
            click.echo("Skipping deployment.")
            return

    if dry_run:
        click.echo("DRY RUN - Would execute:")
        click.echo(f"  - Deploy {project_type} to {deploy_env}")
        click.echo(f"  - Strategy: {strategy}")
        if setup_nginx:
            click.echo(f"  - Setup nginx for {domain or 'auto-detected domain'}")
            if ssl:
                click.echo("  - Configure SSL certificates")
        return
    
    # Execute traditional deployment
    success = deployment_service.deploy(
        target=deploy_env,
        project_type=project_type,
        config=config,
        strategy=strategy,
        force=force
    )
    
    if success:
        click.echo(f" Deployment to {deploy_env} completed successfully")
        
        # Setup nginx if requested
        if setup_nginx:
            _setup_nginx_post_deployment(domain, ssl, project_detector)
    else:
        click.echo(f" Deployment to {deploy_env} failed")
        raise click.Abort()


def _deploy_from_registry(
    image: str,
    registry: str,
    version: str,
    environment: str,
    strategy: str,
    backup_previous: bool,
    wait_for_health: bool,
    health_check_timeout: int,
    port_mapping: str,
    setup_nginx: bool,
    domain: str,
    ssl: bool,
    dry_run: bool,
    force: bool
) -> bool:
    """Deploy using modern Docker registry approach via RegistryDeployer module."""

    click.echo(" Modern Docker Registry Deployment")
    click.echo("=" * 50)

    # Extract project name from image
    if '/' in image:
        project_name = image.split('/')[-1].split(':')[0]
    else:
        project_name = image.split(':')[0] if ':' in image else image

    # Configure registry
    registry_url = registry or "registry.example.com/fleet"
    ver = version or "latest"

    click.echo(f" Project: {project_name}")
    click.echo(f" Registry: {registry_url}")
    click.echo(f" Version: {ver}")
    click.echo(f" Environment: {environment}")

    if dry_run:
        click.echo("\nDRY RUN - Would execute:")
        click.echo(f"  1. Pull image: {registry_url}/{project_name}:{ver}")
        if backup_previous:
            click.echo(f"  2. Backup current {project_name} deployment")
        click.echo(f"  3. Deploy new container with {strategy} strategy")
        if port_mapping:
            click.echo(f"  4. Configure port mapping: {port_mapping}")
        if wait_for_health:
            click.echo(f"  5. Wait for health check (timeout: {health_check_timeout}s)")
        if setup_nginx:
            click.echo(f"  6. Setup nginx for {domain or project_name + '.local'}")
        return True

    try:
        # Create deployer with configuration
        config = DeploymentConfig(
            registry=registry_url,
            version=ver,
            environment=environment
        )
        deployer = RegistryDeployer(config)

        # Deploy the project
        result = deployer.deploy_project(project_name, ver, dry_run=False)

        if not result.get("success"):
            click.echo(f" Deployment failed: {result.get('message', 'Unknown error')}")
            return False

        click.echo(f" {result.get('message', 'Deployment complete')}")

        if result.get("warning"):
            click.echo(f" Warning: {result['warning']}")

        if result.get("port"):
            click.echo(f" Service available on port {result['port']}")

        # Setup nginx if requested
        if setup_nginx:
            nginx_success = _setup_nginx_for_container(
                project_name, domain, ssl, port_mapping
            )
            if nginx_success:
                click.echo(" Nginx configuration completed")
            else:
                click.echo(" Nginx setup failed")

        click.echo(f"\n Deployment of {project_name} to {environment} completed!")
        return True

    except Exception as e:
        click.echo(f" Deployment failed: {e}")
        return False


def _backup_deployment(project_name: str, environment: str) -> bool:
    """Backup current deployment."""
    import subprocess
    import datetime
    
    try:
        # Create backup of current container
        timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_name = f"{project_name}-{environment}-backup-{timestamp}"
        
        # Commit current container to backup image
        commit_cmd = [
            'docker', 'commit',
            f"{project_name}-{environment}",
            backup_name
        ]
        
        result = subprocess.run(commit_cmd, capture_output=True, text=True)
        return result.returncode == 0
        
    except Exception:
        return False


def _wait_for_health(project_name: str, environment: str, timeout: int) -> bool:
    """Wait for container health check to pass."""
    import subprocess
    import time
    import requests
    
    # Try to get container port mapping
    inspect_cmd = [
        'docker', 'inspect',
        f"{project_name}-{environment}",
        '--format', '{{.NetworkSettings.Ports}}'
    ]
    
    start_time = time.time()
    
    while time.time() - start_time < timeout:
        try:
            # Check if container is running
            status_cmd = [
                'docker', 'inspect',
                f"{project_name}-{environment}",
                '--format', '{{.State.Status}}'
            ]
            
            result = subprocess.run(status_cmd, capture_output=True, text=True)
            
            if result.returncode == 0 and result.stdout.strip() == 'running':
                # Try health endpoint
                try:
                    response = requests.get('http://localhost:3001/health', timeout=2)
                    if response.status_code == 200:
                        return True
                except requests.exceptions.RequestException:
                    pass
            
            time.sleep(2)
            
        except Exception:
            time.sleep(2)
    
    return False


def _setup_nginx_for_container(
    project_name: str, domain: str, ssl: bool, port_mapping: str
) -> bool:
    """Setup nginx for deployed container."""
    try:
        from ...local.nginx import NginxManager
        
        # Extract port from mapping
        backend_port = 3001  # Default
        if port_mapping:
            for mapping in port_mapping.split(','):
                if ':' in mapping:
                    host_port = mapping.split(':')[0].strip()
                    if host_port.isdigit():
                        backend_port = int(host_port)
                        break
        
        # Setup nginx
        manager = NginxManager()
        domain_name = domain or f"{project_name}.local"
        
        success = manager.setup_nginx(
            domain=domain_name,
            backend_port=backend_port,
            ssl=ssl
        )
        
        if success and ssl:
            manager.setup_ssl(domain=domain_name)
        
        return success
        
    except Exception as e:
        click.echo(f"Nginx setup error: {e}")
        return False


def _setup_nginx_post_deployment(domain: str, ssl: bool, project_detector):
    """Setup nginx after traditional deployment."""
    try:
        from ...local.nginx import NginxManager
        
        manager = NginxManager()
        
        # Auto-detect domain if not provided
        if not domain:
            config = project_detector.get_build_config()
            domain = config.get('domain', Path.cwd().name + '.local')
        
        success = manager.setup_nginx(domain=domain, ssl=ssl)
        
        if success:
            click.echo(f" Nginx configured for {domain}")
            if ssl:
                if manager.setup_ssl(domain=domain):
                    click.echo(" SSL certificates obtained")
                else:
                    click.echo("️ SSL setup failed")
        else:
            click.echo("️ Nginx setup failed")
            
    except Exception as e:
        click.echo(f"Nginx setup error: {e}")


def deploy_project(
    project_path: str,
    target: str,
    strategy: str = "rolling",
    dry_run: bool = False,
    force: bool = False,
) -> dict:
    """Deploy a single project programmatically (for workspace usage)."""
    from ..services import deployment_service

    result = deployment_service.deploy_project(
        project_path=project_path,
        target=target,
        strategy=strategy,
        force=force,
        dry_run=dry_run,
    )

    return {
        "success": result.success,
        "deployment_id": result.deployment_id,
        "metadata": result.metadata,
        "error": result.error if not result.success else None,
    }


def _setup_nginx_after_deployment(domain: str, ssl: bool, project_detector: ProjectDetector):
    """Setup nginx reverse proxy after successful deployment."""
    try:
        from .nginx import NginxManager
        
        click.echo("\n Setting up nginx reverse proxy...")
        
        # Initialize nginx manager
        nginx_manager = NginxManager()
        
        # Setup nginx configuration
        if nginx_manager.setup_nginx(domain=domain, ssl=ssl):
            click.echo(" Nginx configuration complete!")
            
            # Setup SSL if requested
            if ssl:
                click.echo("\n Setting up SSL certificates...")
                if nginx_manager.setup_ssl(domain=domain):
                    click.echo(" SSL certificates obtained successfully!")
                    click.echo(f" Your aApplication is now available at: https://{domain or 'your-domain'}")
                else:
                    click.echo("️  SSL setup failed, but site is available via HTTP")
                    click.echo(f" Your aApplication is available at: http://{domain or 'your-domain'}")
            else:
                click.echo(f" Your aApplication is available at: http://{domain or 'your-domain'}")
        else:
            click.echo("️  Nginx setup failed. You may need to configure it manually.")
            
    except ImportError as e:
        click.echo(f"️  Could not import nginx module: {e}")
    except Exception as e:
        click.echo(f"️  Error setting up nginx: {e}")
        click.echo("You can setup nginx manually using 'sega nginx setup'")
