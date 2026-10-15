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
SEGA AWS INFRASTRUCTURE MANAGEMENT COMMAND
==============================================================================
File: src/sega/commands/infrastructure.py
Project: SEGA (Scalable Engineering & Growth Automation)
Copyright: 2022-2025 FLEET
License: Apache-2.0

SEGA MODULE: Commands/InfrastructureManagement
COMPONENT: AWS Infrastructure Orchestration CLI Command Group
PURPOSE: Manage AWS infrastructure deployment and orchestration
DEPENDENCIES: click, subprocess, boto3, json, InfrastructureManager
USAGE: sega infrastructure [setup|deploy|destroy|status] [--force] [--region REGION]

This command group provides comprehensive AWS infrastructure management including
interactive setup, deployment orchestration, resource management, and status monitoring.
==============================================================================
"""

import click
import subprocess
import boto3
import json
import os
import asyncio
from tabulate import tabulate
from ...core.infrastructure_manager import InfrastructureManager
from ...infrastructure import (
    VPNManager,
    VPNConfig,
    EngineDeployer,
    RunnerManager,
    NetworkOrchestrator,
)


@click.group()
def infrastructure():
    """Unified infrastructure management for VPN, engines, runners, and cloud resources.

    SEGA provides comprehensive infrastructure orchestration across:
    - VPN network provisioning and management
    - Engine component deployment (the configured [engines.<name>] types)
    - GitLab runner clusters
    - AWS/cloud resource provisioning
    - Network-wide orchestration
    """
    pass


@infrastructure.command()
@click.option("--force", is_flag=True, help="Overwrite existing configuration")
def setup(force):
    """Interactive infrastructure setup and configuration."""
    click.echo("  SEGA Infrastructure Setup")

    manager = InfrastructureManager()

    # Check for existing configuration
    existing_config = manager.load_infrastructure_config()

    if existing_config and not force:
        click.echo("Infrastructure configuration already exists.")
        if click.confirm("Update existing configuration?"):
            manager.interactive_setup()
        else:
            click.echo("Setup cancelled. Use --force to overwrite.")
            return
    else:
        manager.interactive_setup()

    click.echo("\n Infrastructure setup completed!")
    click.echo("\nNext steps:")
    click.echo(
        "  sega infrastructure provision --dry-run  # Preview infrastructure"
    )
    click.echo(
        "  sega infrastructure provision            # Deploy infrastructure"
    )
    click.echo("  sega infrastructure status               # Check status")


@infrastructure.command()
@click.option(
    "--dry-run",
    is_flag=True,
    help="Preview infrastructure without provisioning",
)
@click.option("--component", help="Provision specific component only")
def provision(dry_run, component):
    """Provision infrastructure based on configuration."""
    manager = InfrastructureManager()

    config = manager.load_infrastructure_config()
    if not config:
        click.echo(" No infrastructure configuration found.")
        click.echo("Run 'sega infrastructure setup' first.")
        return

    if dry_run:
        click.echo(" Dry run - infrastructure plan:")
        click.echo("=" * 40)

        project = config.get("project", {})
        click.echo(f"Project: {project.get('name')}")
        click.echo(f"Environment: {project.get('environment')}")
        click.echo(f"Region: {project.get('region')}")
        click.echo()

        components = config.get("components", {})
        click.echo("Components to provision:")
        for comp, comp_config in components.items():
            if comp_config.get("enabled"):
                click.echo(f"   {comp}")
            else:
                click.echo(f"   {comp} (disabled)")

        return

    result = manager.provision_infrastructure(config, dry_run=dry_run)

    if result["success"]:
        click.echo(" Infrastructure provisioned successfully!")
    else:
        click.echo(
            f" Infrastructure provisioning failed: {result.get('error')}"
        )


@infrastructure.command()
def status():
    """Check infrastructure status."""
    manager = InfrastructureManager()

    status = manager.get_infrastructure_status()

    if status["status"] == "not_configured":
        click.echo(
            " Infrastructure not configured. Run 'sega infrastructure setup' first."
        )
        return
    elif status["status"] == "credentials_invalid":
        click.echo(" AWS credentials invalid. Check your configuration.")
        return

    click.echo(" Infrastructure Status")
    click.echo("=" * 30)

    project = status.get("project", {})
    click.echo(f"Project: {project.get('name')}")
    click.echo(f"Environment: {project.get('environment')}")
    click.echo(f"Region: {project.get('region')}")
    click.echo()

    components = status.get("components", {})
    if components:
        click.echo("Components:")
        for comp, comp_status in components.items():
            status_icon = "" if comp_status.get("status") == "exists" else ""
            click.echo(f"  {status_icon} {comp}: {comp_status.get('status')}")
    else:
        click.echo("No components configured.")


@infrastructure.command()
@click.option("--component", help="Destroy specific component only")
@click.option("--force", is_flag=True, help="Skip confirmation prompts")
def destroy(component, force):
    """Destroy infrastructure components."""
    manager = InfrastructureManager()

    config = manager.load_infrastructure_config()
    if not config:
        click.echo(" No infrastructure configuration found.")
        return

    project = config.get("project", {})

    if not force:
        target = component if component else "all infrastructure"
        if not click.confirm(
            f"  Destroy {target} for {project.get('name')} ({project.get('environment')})?"
        ):
            click.echo("Destruction cancelled.")
            return

    click.echo("  Destroying infrastructure...")
    click.echo("  This feature is not yet implemented.")
    click.echo("Use Terraform directly for now:")
    click.echo(
        "  cd _internal/tooling/_internal/tooling/infrastructure/terraform/aws"
    )
    click.echo("  terraform destroy")


# Legacy commands for backward compatibility
@infrastructure.command()
@click.option(
    "--action",
    type=click.Choice(["deploy", "destroy", "plan", "status"]),
    required=True,
    help="Infrastructure action to perform",
)
@click.option(
    "--target",
    type=click.Choice(["aws", "local", "hybrid"]),
    default="aws",
    help="Target infrastructure",
)
@click.option("--region", default="us-east-1", help="AWS region")
@click.option("--environment", default="prod", help="Environment name")
@click.option(
    "--component", help="Specific component to deploy (ecs, eks, ec2, rds)"
)
@click.option(
    "--auto-approve", is_flag=True, help="Auto-approve Terraform changes"
)
def legacy(action, target, region, environment, component, auto_approve):
    """Legacy infrastructure management (deprecated - use subcommands instead)."""
    click.echo("  This command format is deprecated.")
    click.echo(
        "Use 'sega infrastructure setup' and 'sega infrastructure provision' instead."
    )

    if action == "deploy":
        _deploy_infrastructure(
            target, region, environment, component, auto_approve
        )
    elif action == "destroy":
        _destroy_infrastructure(
            target, region, environment, component, auto_approve
        )
    elif action == "plan":
        _plan_infrastructure(target, region, environment, component)
    elif action == "status":
        _status_infrastructure(target, region, environment)


def _deploy_infrastructure(
    target: str,
    region: str,
    environment: str,
    component: str,
    auto_approve: bool,
):
    """Deploy infrastructure components."""

    if target == "aws":
        _deploy_aws_infrastructure(
            region, environment, component, auto_approve
        )
    elif target == "local":
        _deploy_local_infrastructure(environment, component)
    elif target == "hybrid":
        _deploy_hybrid_infrastructure(
            region, environment, component, auto_approve
        )


def _deploy_aws_infrastructure(
    region: str, environment: str, component: str, auto_approve: bool
):
    """Deploy AWS infrastructure using Terraform."""

    # Define deployment order for components
    deployment_order = [
        "vpc",  # Network foundation
        "security",  # Security groups, IAM
        "storage",  # S3, EFS, RDS
        "compute",  # EC2, ECS, EKS
        "load-balancer",  # ALB, NLB
        "monitoring",  # CloudWatch, X-Ray
        "cdn",  # CloudFront, Route53
    ]

    components_to_deploy = [component] if component else deployment_order

    for comp in components_to_deploy:
        click.echo(f"Deploying {comp} infrastructure...")

        terraform_dir = f"_internal/tooling/_internal/tooling/infrastructure/terraform/aws/{comp}"

        if not os.path.exists(terraform_dir):
            click.echo(f"  {terraform_dir} not found, skipping {comp}")
            continue

        # Initialize Terraform
        init_cmd = ["terraform", "init"]
        subprocess.run(init_cmd, cwd=terraform_dir, check=True)

        # Plan deployment
        plan_cmd = [
            "terraform",
            "plan",
            "-var",
            f"region={region}",
            "-var",
            f"environment={environment}",
            "-out",
            f"{comp}.tfplan",
        ]

        result = subprocess.run(
            plan_cmd, cwd=terraform_dir, capture_output=True, text=True
        )

        if result.returncode != 0:
            click.echo(f" Planning failed for {comp}: {result.stderr}")
            continue

        # Apply deployment
        apply_cmd = ["terraform", "apply"]
        if auto_approve:
            apply_cmd.append("-auto-approve")
        apply_cmd.append(f"{comp}.tfplan")

        result = subprocess.run(apply_cmd, cwd=terraform_dir)

        if result.returncode == 0:
            click.echo(f" {comp} deployed successfully")
        else:
            click.echo(f" {comp} deployment failed")
            return

    click.echo(" AWS infrastructure deployment completed")


def _deploy_local_infrastructure(environment: str, component: str):
    """Deploy local infrastructure (Docker Compose, K3s)."""

    if component == "docker" or not component:
        # Deploy Docker Compose stack
        compose_file = f"_internal/tooling/_internal/tooling/infrastructure/docker/docker-compose.{environment}.yml"

        if os.path.exists(compose_file):
            cmd = ["docker-compose", "-f", compose_file, "up", "-d"]
            result = subprocess.run(cmd, capture_output=True, text=True)

            if result.returncode == 0:
                click.echo(" Docker infrastructure deployed")
            else:
                click.echo(f" Docker deployment failed: {result.stderr}")
        else:
            click.echo(f"  {compose_file} not found")

    if component == "k3s" or not component:
        # Deploy K3s cluster
        k3s_script = "_internal/tooling/_internal/tooling/infrastructure/scripts/setup-k3s.sh"

        if os.path.exists(k3s_script):
            result = subprocess.run(
                ["bash", k3s_script], capture_output=True, text=True
            )

            if result.returncode == 0:
                click.echo(" K3s cluster deployed")
            else:
                click.echo(f" K3s deployment failed: {result.stderr}")


def _deploy_hybrid_infrastructure(
    region: str, environment: str, component: str, auto_approve: bool
):
    """Deploy hybrid infrastructure (AWS + on-premise)."""

    # Deploy AWS components first
    click.echo("Deploying AWS components...")
    _deploy_aws_infrastructure(region, environment, component, auto_approve)

    # Deploy on-premise components
    click.echo("Deploying on-premise components...")
    _deploy_local_infrastructure(environment, component)

    # Configure VPN connectivity
    click.echo("Configuring VPN connectivity...")
    ansible_cmd = [
        "ansible-playbook",
        "-i",
        "_internal/tooling/_internal/tooling/infrastructure/ansible/host.ini",
        "_internal/tooling/_internal/tooling/infrastructure/ansible/setup-vpn-connectivity.yml",
        "--extra-vars",
        f"region={region} environment={environment}",
    ]

    result = subprocess.run(ansible_cmd, capture_output=True, text=True)

    if result.returncode == 0:
        click.echo(" Hybrid infrastructure deployed")
    else:
        click.echo(f" Hybrid deployment failed: {result.stderr}")


def _plan_infrastructure(
    target: str, region: str, environment: str, component: str
):
    """Plan infrastructure changes without applying."""

    click.echo(f" Planning {target} infrastructure changes...")

    if target == "aws":
        terraform_dir = f"_internal/tooling/_internal/tooling/infrastructure/terraform/aws/{component or 'compute'}"

        if os.path.exists(terraform_dir):
            plan_cmd = [
                "terraform",
                "plan",
                "-var",
                f"region={region}",
                "-var",
                f"environment={environment}",
            ]

            result = subprocess.run(plan_cmd, cwd=terraform_dir)

            if result.returncode == 0:
                click.echo(" Planning completed")
            else:
                click.echo(" Planning failed")
        else:
            click.echo(f"  {terraform_dir} not found")


def _status_infrastructure(target: str, region: str, environment: str):
    """Check infrastructure status."""

    click.echo(f" Checking {target} infrastructure status...")

    if target == "aws":
        _check_aws_status(region, environment)
    elif target == "local":
        _check_local_status()


def _check_aws_status(region: str, environment: str):
    """Check AWS infrastructure status."""

    try:
        # Initialize AWS session
        session = boto3.Session(region_name=region)

        # Check EC2 instances
        ec2 = session.client("ec2")
        instances = ec2.describe_instances(
            Filters=[
                {"Name": "tag:Environment", "Values": [environment]},
                {"Name": "tag:ManagedBy", "Values": ["sega"]},
            ]
        )

        click.echo("  EC2 Instances:")
        for reservation in instances["Reservations"]:
            for instance in reservation["Instances"]:
                state = instance["State"]["Name"]
                instance_id = instance["InstanceId"]
                instance_type = instance["InstanceType"]

                status_icon = "" if state == "running" else ""
                click.echo(
                    f"  {status_icon} {instance_id} ({instance_type}) - {state}"
                )

        # Check ECS services
        ecs = session.client("ecs")
        clusters = ecs.list_clusters()

        click.echo(" ECS Clusters:")
        for cluster_arn in clusters["clusterArns"]:
            cluster_name = cluster_arn.split("/")[-1]
            services = ecs.list_services(cluster=cluster_name)

            click.echo(
                f"   {cluster_name}: {len(services['serviceArns'])} services"
            )

        # Check RDS instances
        rds = session.client("rds")
        databases = rds.describe_db_instances()

        click.echo("  RDS Instances:")
        for db in databases["DBInstances"]:
            db_id = db["DBInstanceIdentifier"]
            status = db["DBInstanceStatus"]
            engine = db["Engine"]

            status_icon = "" if status == "available" else ""
            click.echo(f"  {status_icon} {db_id} ({engine}) - {status}")

        # Check Load Balancers
        elb = session.client("elbv2")
        load_balancers = elb.describe_load_balancers()

        click.echo("  Load Balancers:")
        for lb in load_balancers["LoadBalancers"]:
            lb_name = lb["LoadBalancerName"]
            state = lb["State"]["Code"]

            status_icon = "" if state == "active" else ""
            click.echo(f"  {status_icon} {lb_name} - {state}")

    except Exception as e:
        click.echo(f" Error checking AWS status: {str(e)}")


def _check_local_status():
    """Check local infrastructure status."""

    # Check Docker containers
    try:
        result = subprocess.run(
            ["docker", "ps", "--format", "table {{.Names}}\t{{.Status}}"],
            capture_output=True,
            text=True,
        )

        if result.returncode == 0:
            click.echo(" Docker Containers:")
            for line in result.stdout.split("\n")[1:]:  # Skip header
                if line.strip():
                    click.echo(f"  {line}")
        else:
            click.echo("  Docker not available")

    except Exception:
        click.echo("  Docker not available")

    # Check K3s cluster
    try:
        result = subprocess.run(
            ["kubectl", "get", "nodes", "--no-headers"],
            capture_output=True,
            text=True,
        )

        if result.returncode == 0:
            click.echo("  Kubernetes Nodes:")
            for line in result.stdout.split("\n"):
                if line.strip():
                    parts = line.split()
                    if len(parts) >= 2:
                        name = parts[0]
                        status = parts[1]
                        status_icon = "" if status == "Ready" else ""
                        click.echo(f"  {status_icon} {name} - {status}")
        else:
            click.echo("  Kubernetes not available")

    except Exception:
        click.echo("  Kubernetes not available")


def _destroy_infrastructure(
    target: str,
    region: str,
    environment: str,
    component: str,
    auto_approve: bool,
):
    """Destroy infrastructure components."""

    click.echo(f"  Destroying {target} infrastructure...")

    if not auto_approve:
        confirm = click.confirm(
            f"Are you sure you want to destroy {target} infrastructure in {environment}?"
        )
        if not confirm:
            click.echo("Destruction cancelled")
            return

    if target == "aws":
        # Reverse order for destruction
        destruction_order = [
            "cdn",
            "monitoring",
            "load-balancer",
            "compute",
            "storage",
            "security",
            "vpc",
        ]

        components_to_destroy = [component] if component else destruction_order

        for comp in components_to_destroy:
            terraform_dir = f"_internal/tooling/_internal/tooling/infrastructure/terraform/aws/{comp}"

            if os.path.exists(terraform_dir):
                destroy_cmd = [
                    "terraform",
                    "destroy",
                    "-var",
                    f"region={region}",
                    "-var",
                    f"environment={environment}",
                    "-auto-approve",
                ]

                result = subprocess.run(destroy_cmd, cwd=terraform_dir)

                if result.returncode == 0:
                    click.echo(f" {comp} destroyed successfully")
                else:
                    click.echo(f" {comp} destruction failed")

    elif target == "local":
        # Destroy Docker Compose stack
        compose_file = f"_internal/tooling/_internal/tooling/infrastructure/docker/docker-compose.{environment}.yml"

        if os.path.exists(compose_file):
            cmd = ["docker-compose", "-f", compose_file, "down", "-v"]
            result = subprocess.run(cmd, capture_output=True, text=True)

            if result.returncode == 0:
                click.echo(" Local infrastructure destroyed")
            else:
                click.echo(f" Local destruction failed: {result.stderr}")

    click.echo(" Infrastructure destruction completed")


# VPN Infrastructure Commands
@infrastructure.group()
def vpn():
    """VPN infrastructure management commands."""
    pass


@vpn.command("provision")
@click.argument("host")
@click.option("--ssh-key", help="SSH private key path")
@click.option("--domain", default="vpn.fleet-dev.example.com", help="VPN domain")
@click.option("--network", default="10.10.10.0/24", help="VPN network CIDR")
@click.option("--port", default=1194, type=int, help="VPN port")
def vpn_provision(host, ssh_key, domain, network, port):
    """Provision a VPN server on a remote host.

    Example:
        sega infrastructure vpn provision 192.168.1.100 --ssh-key ~/.ssh/id_rsa
    """
    config = VPNConfig(domain=domain, network=network, port=port)
    manager = VPNManager(config)

    click.echo(f" Provisioning VPN server on {host}...")
    result = manager.provision_server(host, ssh_key)

    if result["status"] == "success":
        click.secho(" VPN server provisioned successfully", fg="green")
        click.echo(f"Network: {result['network']}")
        click.echo(f"Port: {result['port']}")
        click.echo("\nNext steps:")
        click.echo(
            "  sega infrastructure vpn client <name>  # Generate client config"
        )
        click.echo(
            f"  sega infrastructure vpn status {host}   # Check VPN status"
        )
    else:
        click.secho(f" Provisioning failed: {result.get('error')}", fg="red")


@vpn.command("client")
@click.argument("client_name")
@click.option("--output", "-o", help="Output path for .ovpn file")
@click.option("--email", help="Client email address")
def vpn_client(client_name, output, email):
    """Generate VPN client configuration.

    Example:
        sega infrastructure vpn client john-doe --output ~/vpn/john.ovpn
    """
    manager = VPNManager()

    try:
        ovpn_path = manager.generate_client_config(client_name, output)
        click.secho(f" Client config generated: {ovpn_path}", fg="green")

        if email:
            import smtplib
            from email.mime.multipart import MIMEMultipart
            from email.mime.text import MIMEText
            from email.mime.base import MIMEBase
            from email import encoders
            import os
            
            # Check for email configuration
            smtp_host = os.environ.get('SMTP_HOST', 'localhost')
            smtp_port = int(os.environ.get('SMTP_PORT', '587'))
            smtp_user = os.environ.get('SMTP_USER', '')
            smtp_pass = os.environ.get('SMTP_PASS', '')
            
            if smtp_host and smtp_user:
                try:
                    msg = MIMEMultipart()
                    msg['From'] = smtp_user
                    msg['To'] = email
                    msg['Subject'] = f'VPN Configuration for {client_name}'
                    
                    body = f"""
Your VPN configuration for {client_name} has been generated.

Setup instructions:
1. Install OpenVPN client on your device
2. Import the attached configuration file
3. Connect using your OpenVPN client

FFFFFFFFFFor support, please contact your system administrator.
"""
                    msg.attach(MIMEText(body, 'plain'))
                    
                    # Attach the config file
                    with open(ovpn_path, 'rb') as f:
                        part = MIMEBase('application', 'octet-stream')
                        part.set_payload(f.read())
                        encoders.encode_base64(part)
                        part.add_header(
                            'Content-Disposition',
                            f'attachment; filename={os.path.basename(ovpn_path)}'
                        )
                        msg.attach(part)
                    
                    # Send email
                    server = smtplib.SMTP(smtp_host, smtp_port)
                    if smtp_port == 587:
                        server.starttls()
                    if smtp_pass:
                        server.login(smtp_user, smtp_pass)
                    server.send_message(msg)
                    server.quit()
                    
                    click.echo(f" Config emailed to {email}")
                except Exception as e:
                    click.echo(f" Failed to email config: {e}")
                    click.echo(" Please send the config file manually")
            else:
                click.echo(" Email not configured. Set SMTP_HOST and SMTP_USER environment variables")

        click.echo("\nClient setup instructions:")
        click.echo("  1. Install OpenVPN client")
        click.echo(f"  2. Import config: {ovpn_path}")
        click.echo("  3. Connect to VPN")
    except Exception as e:
        click.secho(f" Failed to generate client config: {e}", fg="red")


@vpn.command("status")
@click.argument("host")
@click.option("--ssh-key", help="SSH private key path")
def vpn_status(host, ssh_key):
    """Check VPN network status."""
    manager = VPNManager()

    status = manager.get_network_status(host, ssh_key)

    if status.get("status") == "active":
        click.secho(" VPN Status: ACTIVE", fg="green")
        click.echo(f"Connected clients: {status['client_count']}")

        if status["clients"]:
            headers = [
                "Name",
                "Address",
                "Bytes In",
                "Bytes Out",
                "Connected Since",
            ]
            rows = [
                [
                    c["name"],
                    c["address"],
                    c["bytes_received"],
                    c["bytes_sent"],
                    c["connected_since"],
                ]
                for c in status["clients"]
            ]
            click.echo("\n" + tabulate(rows, headers=headers, tablefmt="grid"))
    else:
        click.secho(
            f" VPN Status: {status.get('status', 'UNKNOWN').upper()}", fg="red"
        )
        if "error" in status:
            click.echo(f"Error: {status['error']}")


@vpn.command("revoke")
@click.argument("client_name")
@click.confirmation_option(
    prompt="Are you sure you want to revoke this client?"
)
def vpn_revoke(client_name):
    """Revoke a VPN client certificate."""
    manager = VPNManager()

    if manager.revoke_client(client_name):
        click.secho(f" Client {client_name} revoked", fg="green")
    else:
        click.secho(" Failed to revoke client", fg="red")


# Engine Deployment Commands
@infrastructure.group()
def engine():
    """Engine component deployment and management."""
    pass


def _engine_type_choice():
    """Argument type for engine types: the configured `[engines.<name>]` keys.

    Falls back to a plain string argument when no engines are configured, so
    the command still parses (and reports "Unknown engine type" at runtime).
    """
    from ...core.config import get_config
    names = list(get_config().engines.keys())
    return click.Choice(names) if names else click.STRING


@engine.command("deploy")
@click.argument(
    "engine_type",
    type=_engine_type_choice(),
)
@click.argument("target_host")
@click.option("--vpn-ip", help="VPN IP address of the host")
@click.option("--cpu", type=int, help="CPU cores to allocate")
@click.option("--memory", help="Memory to allocate (e.g., 8Gi)")
@click.option("--gpu", is_flag=True, help="Enable GPU support")
@click.option(
    "--env", "-e", multiple=True, help="Environment variables (KEY=VALUE)"
)
def engine_deploy(engine_type, target_host, vpn_ip, cpu, memory, gpu, env):
    """Deploy an engine component to a VPN node.

    Examples:
        sega infrastructure engine deploy <engine> 10.0.3.10
        sega infrastructure engine deploy <engine> 10.0.3.20 --gpu --memory 16Gi
    """
    deployer = EngineDeployer()

    # Build kwargs
    kwargs = {}
    if vpn_ip:
        kwargs["vpn_ip"] = vpn_ip

    resources = {}
    if cpu:
        resources["cpu"] = cpu
    if memory:
        resources["memory"] = memory
    if gpu:
        resources["gpu"] = True

    if resources:
        kwargs["resources"] = resources

    # Parse environment variables
    if env:
        env_dict = {}
        for e in env:
            if "=" in e:
                k, v = e.split("=", 1)
                env_dict[k] = v
        kwargs["env"] = env_dict

    click.echo(f" Deploying {engine_type} engine to {target_host}...")
    result = deployer.deploy_engine(engine_type, target_host, **kwargs)

    if result["status"] == "success":
        click.secho(f" {engine_type} engine deployed successfully", fg="green")
        click.echo("\nEndpoints:")
        for name, url in result["endpoints"].items():
            click.echo(f"  {name}: {url}")
    else:
        click.secho(f" Deployment failed: {result.get('error')}", fg="red")


@engine.command("scale")
@click.argument("engine_type")
@click.argument("replicas", type=int)
def engine_scale(engine_type, replicas):
    """Scale an engine component horizontally.

    Example:
        sega infrastructure engine scale <engine> 3
    """
    deployer = EngineDeployer()

    click.echo(f" Scaling {engine_type} to {replicas} replicas...")
    result = deployer.scale_engine(engine_type, replicas)

    if result["status"] == "success":
        click.secho(f" Scaled to {result['scaled_to']} replicas", fg="green")
        if "deployments" in result:
            for deployment in result["deployments"]:
                if deployment["status"] == "success":
                    click.echo(f"   Deployed to {deployment['host']}")
    elif result["status"] == "partial":
        click.secho(f" {result['message']}", fg="yellow")
    else:
        click.secho(" Scaling failed", fg="red")


@engine.command("status")
@click.option("--type", "engine_type", help="Filter by engine type")
def engine_status(engine_type):
    """Get status of deployed engines."""
    deployer = EngineDeployer()

    status = deployer.get_engine_status(engine_type)

    if not status["engines"]:
        click.echo("No engines deployed")
        return

    for engine, nodes in status["engines"].items():
        click.echo(f"\n {engine.upper()} Engines:")

        headers = ["Name", "Host", "VPN IP", "Health", "Capabilities"]
        rows = []

        for n in nodes:
            health_icon = "" if n["health"] == "healthy" else ""
            rows.append(
                [
                    n["name"],
                    n["host"],
                    n["vpn_ip"],
                    f"{health_icon} {n['health']}",
                    ", ".join(n["capabilities"][:2])
                    + ("..." if len(n["capabilities"]) > 2 else ""),
                ]
            )

        click.echo(tabulate(rows, headers=headers, tablefmt="grid"))


@engine.command("workflow")
@click.argument("workflow_file", type=click.Path(exists=True))
def engine_workflow(workflow_file):
    """Execute a multi-engine workflow.

    Example workflow.yaml:
        name: RF Analysis Pipeline
        steps:
          - name: Generate Signal
            engine: alpha
            operation: generate_signal
            params:
              frequency: 2.4e9
              duration: 1.0
          - name: Analyze Signal
            engine: beta
            operation: analyze
            params:
              model: signal_classifier
    """
    import yaml

    deployer = EngineDeployer()

    with open(workflow_file) as f:
        workflow = yaml.safe_load(f)

    click.echo(f" Executing workflow: {workflow.get('name', 'unnamed')}")

    async def run():
        return await deployer.orchestrate_workflow(workflow)

    result = asyncio.run(run())

    if result["status"] == "completed":
        click.secho(" Workflow completed successfully", fg="green")
    else:
        click.secho(" Workflow partially completed", fg="yellow")

    # Show step results
    for step_name, step_result in result["results"].items():
        status_icon = "" if step_result.get("status") == "success" else ""
        click.echo(f"\n{status_icon} {step_name}:")
        if "error" in step_result:
            click.echo(f"  Error: {step_result['error']}")
        elif "result" in step_result:
            click.echo(
                f"  Result: {json.dumps(step_result['result'], indent=2)}"
            )


# GitLab Runner Commands
@infrastructure.group()
def runner():
    """GitLab runner management commands."""
    pass


@runner.command("register")
@click.argument("name")
@click.argument("token")
@click.option("--host", help="Remote host to register on (VPN IP)")
@click.option(
    "--executor",
    default="docker",
    type=click.Choice(["docker", "shell", "kubernetes"]),
)
@click.option(
    "--docker-image", default="alpine:latest", help="Default Docker image"
)
@click.option("--tags", help="Comma-separated tags")
@click.option(
    "--privileged", is_flag=True, help="Enable privileged mode for Docker"
)
def runner_register(
    name, token, host, executor, docker_image, tags, privileged
):
    """Register a new GitLab runner.

    Example:
        sega infrastructure runner register my-runner glrt-xxxxx --host 10.0.2.21 --tags docker,vpn
    """
    manager = RunnerManager()

    tag_list = tags.split(",") if tags else []

    kwargs = {
        "docker_image": docker_image,
        "environment": [
            "SEGA_ENDPOINT=http://10.0.2.10:8000",
            "CI_DEBUG_TRACE=false",
        ],
    }

    if privileged and executor == "docker":
        kwargs["privileged"] = True

    click.echo(f" Registering runner '{name}'...")
    result = manager.register_runner(
        name, token, executor, tags=tag_list, host=host, **kwargs
    )

    if result["status"] == "success":
        click.secho(" Runner registered successfully", fg="green")
        click.echo(f"Name: {result['runner']['name']}")
        click.echo(f"Executor: {result['runner']['executor']}")
        click.echo(f"Host: {result['runner']['host']}")
        if result["runner"]["tags"]:
            click.echo(f"Tags: {', '.join(result['runner']['tags'])}")
    else:
        click.secho(f" Registration failed: {result.get('error')}", fg="red")


@runner.command("cluster")
@click.argument("cluster_name")
@click.argument("token")
@click.option("--hosts", required=True, help="Comma-separated VPN host IPs")
@click.option("--replicas-per-host", default=1, type=int)
@click.option("--executor", default="docker")
def runner_cluster(cluster_name, token, hosts, replicas_per_host, executor):
    """Deploy a cluster of runners across VPN nodes.

    Example:
        sega infrastructure runner cluster prod-runners glrt-xxxxx --hosts 10.0.2.21,10.0.2.22,10.0.2.23
    """
    manager = RunnerManager()

    host_list = [h.strip() for h in hosts.split(",")]

    click.echo(f" Deploying runner cluster '{cluster_name}'...")
    click.echo(f"Hosts: {len(host_list)}")
    click.echo(f"Replicas per host: {replicas_per_host}")
    click.echo(f"Total runners: {len(host_list) * replicas_per_host}")

    result = manager.deploy_runner_cluster(
        cluster_name, token, host_list, executor, replicas_per_host
    )

    if result["status"] == "success":
        click.secho(" Cluster deployed successfully", fg="green")
    elif result["status"] == "partial":
        click.secho(" Partial deployment", fg="yellow")

    click.echo("\nDeployment summary:")
    click.echo(f"Total runners: {result['total_runners']}")
    click.echo(f"Successful: {result['successful']}")

    if result["successful"] < result["total_runners"]:
        click.echo("\nFailed deployments:")
        for r in result["results"]:
            if r["result"]["status"] != "success":
                click.echo(
                    f"   {r['runner']} on {r['host']}: {r['result'].get('error', 'Unknown error')}"
                )


@runner.command("list")
@click.option("--host", help="Remote host to query")
def runner_list(host):
    """List all registered runners."""
    manager = RunnerManager()

    runners = manager.list_runners(host)

    if runners:
        headers = ["Name", "Executor", "Status"]
        rows = []

        for r in runners:
            status_icon = "" if r["status"] == "active" else ""
            rows.append(
                [r["name"], r["executor"], f"{status_icon} {r['status']}"]
            )

        click.echo(tabulate(rows, headers=headers, tablefmt="grid"))
    else:
        click.echo("No runners found")


@runner.command("status")
@click.argument("name")
@click.option("--host", help="Remote host")
def runner_status(name, host):
    """Check runner status."""
    manager = RunnerManager()

    status = manager.get_runner_status(name, host)

    if status["status"] == "alive":
        click.secho(f" Runner '{name}' is alive", fg="green")
    elif status["status"] == "dead":
        click.secho(f" Runner '{name}' is dead", fg="red")
    else:
        click.secho(
            f" Runner '{name}' status: {status['status']}", fg="yellow"
        )

    if "output" in status:
        click.echo(f"\nOutput:\n{status['output']}")


# Network Orchestration Commands
@infrastructure.group()
def network():
    """Network-wide orchestration commands."""
    pass


@network.command("discover")
@click.option("--subnet", default="10.8.0.0/16", help="VPN subnet to scan")
def network_discover(subnet):
    """Discover all nodes and services on the VPN network."""
    orchestrator = NetworkOrchestrator()

    click.echo(f" Discovering network {subnet}...")

    async def run():
        return await orchestrator.discover_network(subnet)

    result = asyncio.run(run())

    if result["status"] == "success":
        click.secho(f" Discovered {result['total_nodes']} nodes", fg="green")

        for category, nodes in result["discovered"].items():
            if nodes:
                click.echo(f"\n{category.upper()}:")
                for node in nodes:
                    port_info = (
                        f":{node.get('port', '')}" if "port" in node else ""
                    )
                    click.echo(
                        f"  • {node['service']} @ {node['ip']}{port_info}"
                    )
    else:
        click.secho(" Discovery failed", fg="red")


@network.command("health")
@click.option("--json", "output_json", is_flag=True, help="Output as JSON")
def network_health(output_json):
    """Check health of all network nodes."""
    orchestrator = NetworkOrchestrator()

    click.echo(" Running network-wide health check...")

    async def run():
        # First discover network
        await orchestrator.discover_network()
        # Then check health
        return await orchestrator.health_check_all()

    result = asyncio.run(run())

    if output_json:
        click.echo(json.dumps(result, indent=2))
    else:
        click.echo("\n Network Health Summary:")
        click.echo(f"Total nodes: {result['total_nodes']}")

        healthy_pct = (
            (result["healthy"] / result["total_nodes"] * 100)
            if result["total_nodes"] > 0
            else 0
        )

        if healthy_pct >= 90:
            click.secho(
                f"Healthy: {result['healthy']} ({healthy_pct:.0f}%)",
                fg="green",
            )
        elif healthy_pct >= 70:
            click.secho(
                f"Healthy: {result['healthy']} ({healthy_pct:.0f}%)",
                fg="yellow",
            )
        else:
            click.secho(
                f"Healthy: {result['healthy']} ({healthy_pct:.0f}%)", fg="red"
            )

        if result["unhealthy"] > 0:
            click.secho(f"Unhealthy: {result['unhealthy']}", fg="red")

            click.echo("\nUnhealthy nodes:")
            for node, health in result["results"].items():
                if health["status"] != "healthy":
                    click.echo(
                        f"   {node}: {health.get('error', health['status'])}"
                    )


@network.command("deploy")
@click.argument("service_name")
@click.option("--replicas", default=1, type=int)
@click.option(
    "--node-type", type=click.Choice(["backend", "engine", "runner", "edge"])
)
@click.option("--config-file", type=click.Path(exists=True))
def network_deploy(service_name, replicas, node_type, config_file):
    """Deploy a service across the VPN network."""
    orchestrator = NetworkOrchestrator()

    config = {"replicas": replicas}

    if node_type:
        config["requirements"] = {"node_type": node_type}

    if config_file:
        import yaml

        with open(config_file) as f:
            config.update(yaml.safe_load(f))

    click.echo(f" Deploying {service_name} across network...")

    async def run():
        # First discover network
        await orchestrator.discover_network()
        # Then deploy service
        return await orchestrator.deploy_service(service_name, config)

    result = asyncio.run(run())

    if result["status"] == "success":
        click.secho(" Service deployed successfully", fg="green")
        click.echo(f"Deployed to {result['deployed_to']} nodes")
    else:
        click.secho(f" Deployment failed: {result.get('error')}", fg="red")


@network.command("route")
@click.argument("source_service")
@click.argument("destination_service")
@click.option(
    "--protocol", default="http", type=click.Choice(["http", "grpc", "tcp"])
)
def network_route(source_service, destination_service, protocol):
    """Configure traffic routing between services."""
    orchestrator = NetworkOrchestrator()

    click.echo(f" Configuring route: {source_service} → {destination_service}")

    async def run():
        # First discover network
        await orchestrator.discover_network()
        # Then configure routing
        return await orchestrator.route_traffic(
            source_service, destination_service, protocol
        )

    result = asyncio.run(run())

    if result["status"] == "success":
        click.secho(" Routing configured", fg="green")
        routing = result["routing"]
        click.echo(f"Source: {routing['source']}")
        click.echo(f"Destination: {routing['destination']}:{routing['port']}")
        click.echo(f"Protocol: {routing['protocol']}")
    else:
        click.secho(f" Routing failed: {result.get('error')}", fg="red")


@network.command("balance")
@click.argument("service")
@click.option(
    "--strategy",
    default="round-robin",
    type=click.Choice(["round-robin", "least-connections", "ip-hash"]),
)
def network_balance(service, strategy):
    """Configure load balancing for a service."""
    orchestrator = NetworkOrchestrator()

    click.echo(f" Configuring load balancing for {service}...")

    async def run():
        # First discover network
        await orchestrator.discover_network()
        # Then balance load
        return await orchestrator.balance_load(service)

    result = asyncio.run(run())

    if result["status"] == "success":
        click.secho(" Load balancing configured", fg="green")
        lb_config = result["load_balancing"]
        click.echo(f"Strategy: {lb_config['strategy']}")
        click.echo(f"Nodes: {', '.join(lb_config['nodes'])}")
    elif result["status"] == "no_action":
        click.secho(f" {result['message']}", fg="yellow")
    else:
        click.secho(f" Configuration failed: {result.get('error')}", fg="red")
