#!/usr/bin/env python3
"""
SEGA NGINX & SSL MANAGEMENT COMMAND
==============================================================================
File: engine/sega/cli/commands/nginx.py
Purpose: Nginx Configuration & SSL Certificate Management CLI
==============================================================================
"""

import subprocess
from pathlib import Path

import click

from ...local.nginx import NginxManager
from ...infrastructure import (
    INSTANCE1,
    INSTANCE2,
    INSTANCE3,
    EC2_INSTANCES,
    get_ssh_key_path,
    get_ssh_options,
)
from ...infrastructure.nginx_checker import NginxChecker

# Path to nginx config files
SEGA_ROOT = Path(__file__).parent.parent.parent.parent.parent
CONFIG_DIR = SEGA_ROOT / "config"


@click.group()
def nginx():
    """Manage nginx configuration and SSL certificates."""
    pass


@nginx.command()
@click.option("--domain", "-d", help="Domain name for the site")
@click.option("--backend-port", "-b", type=int, help="Backend/API port")
@click.option("--frontend-port", "-f", type=int, help="Frontend port")
@click.option("--template", "-t", default="auto", help="Nginx template to use")
@click.option("--ssl/--no-ssl", default=False, help="Enable SSL configuration")
@click.option("--dry-run", is_flag=True, help="Show configuration without applying")
@click.option("--project-path", "-p", type=click.Path(exists=True), help="Project path")
def setup(domain, backend_port, frontend_port, template, ssl, dry_run, project_path):
    """Setup nginx reverse proxy for a project."""
    manager = NginxManager(project_path)

    if manager.setup_nginx(
        domain=domain,
        backend_port=backend_port,
        frontend_port=frontend_port,
        template=template,
        ssl=ssl,
        dry_run=dry_run,
    ):
        if not dry_run:
            click.echo("\nNginx configuration complete!")
            if ssl:
                click.echo("Run 'sega nginx ssl' to obtain SSL certificates")
    else:
        click.echo("\nNginx configuration failed")
        raise click.Abort()


@nginx.command()
@click.option("--domain", "-d", help="Domain name for SSL certificate")
@click.option("--email", "-e", help="Email for Let's Encrypt registration")
@click.option("--staging", is_flag=True, help="Use Let's Encrypt staging server")
@click.option("--self-signed", is_flag=True, help="Generate self-signed certificate")
@click.option("--project-path", "-p", type=click.Path(exists=True), help="Project path")
def ssl(domain, email, staging, self_signed, project_path):
    """Setup SSL certificates for the domain."""
    manager = NginxManager(project_path)

    if manager.setup_ssl(domain=domain, email=email, staging=staging, self_signed=self_signed):
        click.echo("\nSSL setup complete!")
        click.echo("Your site is now accessible via HTTPS")
    else:
        click.echo("\nSSL setup failed")
        raise click.Abort()


@nginx.command()
@click.option("--project-path", "-p", type=click.Path(exists=True), help="Project path")
def status(project_path):
    """Show nginx configuration status."""
    manager = NginxManager(project_path)
    status = manager.get_status()

    click.echo(f"\nNginx Status for {status['project']}")
    click.echo("=" * 50)

    click.echo("\nConfiguration:")
    click.echo(f"  Config File: {'OK' if status['nginx_config'] else 'Missing'}")
    click.echo(f"  Site Enabled: {'OK' if status['nginx_enabled'] else 'No'}")
    click.echo(f"  Config Valid: {'OK' if status['nginx_valid'] else 'Invalid'}")
    click.echo(f"  SSL Configured: {'OK' if status['ssl_configured'] else 'No'}")

    if status["services"]:
        click.echo("\nServices:")
        for service, is_running in status["services"].items():
            click.echo(f"  {service.capitalize()}: {'Running' if is_running else 'Not running'}")


@nginx.command()
def reload():
    """Reload nginx configuration."""
    manager = NginxManager()

    if manager._test_nginx_config():
        if manager._reload_nginx():
            click.echo("Nginx reloaded successfully")
        else:
            click.echo("Failed to reload nginx")
            raise click.Abort()
    else:
        click.echo("Nginx configuration test failed")
        click.echo("Run 'nginx -t' to see errors")
        raise click.Abort()


@nginx.command()
@click.option("--domain", "-d", required=True, help="Domain name")
@click.option("--backend-port", "-b", type=int, required=True, help="Backend port")
@click.option("--frontend-port", "-f", type=int, help="Frontend port (optional)")
def quick(domain, backend_port, frontend_port):
    """Quick setup with minimal configuration."""
    manager = NginxManager()

    click.echo(f"Quick setup for {domain}")
    click.echo(f"Backend: localhost:{backend_port}")
    if frontend_port:
        click.echo(f"Frontend: localhost:{frontend_port}")

    if manager.setup_nginx(domain=domain, backend_port=backend_port, frontend_port=frontend_port, ssl=True):
        click.echo("\nNginx configured!")

        click.echo("\nAttempting to obtain SSL certificate...")
        if manager.setup_ssl(domain=domain):
            click.echo("SSL certificate obtained!")
            click.echo(f"\nYour site is ready at: https://{domain}")
        else:
            click.echo(f"SSL setup failed, site available at: http://{domain}")
    else:
        click.echo("Setup failed")
        raise click.Abort()


@nginx.command()
@click.option(
    "--instance",
    "-i",
    type=click.Choice(["1", "2", "3", "all"]),
    required=True,
    help="Instance to deploy to (1, 2, 3, or all)",
)
@click.option("--dry-run", is_flag=True, help="Show commands without executing")
@click.option("--skip-reload", is_flag=True, help="Skip nginx reload after deploy")
def deploy(instance, dry_run, skip_reload):
    """Deploy nginx configuration to EC2 instance(s).

    Deploys the per-instance nginx config files from config/ to the target
    EC2 instance(s), then tests and reloads nginx.

    Examples:
        sega nginx deploy --instance 1         # Deploy to Instance 1
        sega nginx deploy --instance all       # Deploy to all instances
        sega nginx deploy -i 2 --dry-run       # Preview Instance 2 deploy
    """
    instances_to_deploy = []

    if instance == "all":
        instances_to_deploy = [("1", INSTANCE1), ("2", INSTANCE2), ("3", INSTANCE3)]
    else:
        instance_map = {"1": INSTANCE1, "2": INSTANCE2, "3": INSTANCE3}
        instances_to_deploy = [(instance, instance_map[instance])]

    # Get SSH key path
    try:
        ssh_key = get_ssh_key_path()
    except FileNotFoundError as e:
        click.echo(f"[ERROR] {e}")
        raise click.Abort()

    ssh_opts = get_ssh_options()

    for inst_num, inst in instances_to_deploy:
        # Check if instance has valid IP
        if not inst.ip:
            click.echo(f"\n[SKIP] Instance {inst_num}: No IP configured (TBD)")
            continue

        config_file = CONFIG_DIR / f"fleet-nginx-instance{inst_num}.conf"

        if not config_file.exists():
            click.echo(f"\n[ERROR] Config file not found: {config_file}")
            continue

        click.echo(f"\n{'=' * 60}")
        click.echo(f"Deploying to Instance {inst_num} ({inst.ip})")
        click.echo(f"Config: {config_file.name}")
        click.echo(f"Projects: {', '.join(inst.projects[:5])}{'...' if len(inst.projects) > 5 else ''}")
        click.echo("=" * 60)

        # Step 1: SCP config file to /tmp
        scp_cmd = ["scp", "-i", str(ssh_key), *ssh_opts, str(config_file), f"{inst.ssh_host}:/tmp/fleet.conf"]

        click.echo(f"\n[1/4] Copying config to instance...")
        if dry_run:
            click.echo(f"  Would run: {' '.join(scp_cmd)}")
        else:
            result = subprocess.run(scp_cmd, capture_output=True, text=True)
            if result.returncode != 0:
                click.echo(f"  [ERROR] SCP failed: {result.stderr}")
                continue
            click.echo("  [OK] Config copied to /tmp/fleet.conf")

        # Step 2: Move config to nginx sites-available
        move_cmd = [
            "ssh",
            "-i",
            str(ssh_key),
            *ssh_opts,
            inst.ssh_host,
            "sudo mv /tmp/fleet.conf /etc/nginx/sites-available/fleet.conf",
        ]

        click.echo(f"[2/4] Installing to sites-available...")
        if dry_run:
            click.echo(f"  Would run: ssh {inst.ssh_host} 'sudo mv /tmp/fleet.conf /etc/nginx/sites-available/fleet.conf'")
        else:
            result = subprocess.run(move_cmd, capture_output=True, text=True)
            if result.returncode != 0:
                click.echo(f"  [ERROR] Move failed: {result.stderr}")
                continue
            click.echo("  [OK] Installed to /etc/nginx/sites-available/fleet.conf")

        # Step 3: Create symlink in sites-enabled
        link_cmd = [
            "ssh",
            "-i",
            str(ssh_key),
            *ssh_opts,
            inst.ssh_host,
            "sudo ln -sf /etc/nginx/sites-available/fleet.conf /etc/nginx/sites-enabled/fleet.conf",
        ]

        click.echo(f"[3/4] Enabling site...")
        if dry_run:
            click.echo(f"  Would run: ssh {inst.ssh_host} 'sudo ln -sf ...'")
        else:
            result = subprocess.run(link_cmd, capture_output=True, text=True)
            if result.returncode != 0:
                click.echo(f"  [ERROR] Symlink failed: {result.stderr}")
                continue
            click.echo("  [OK] Site enabled in sites-enabled/")

        # Step 4: Test and reload nginx
        if skip_reload:
            click.echo(f"[4/4] Skipping nginx reload (--skip-reload)")
        else:
            reload_cmd = [
                "ssh",
                "-i",
                str(ssh_key),
                *ssh_opts,
                inst.ssh_host,
                "sudo nginx -t && sudo systemctl reload nginx",
            ]

            click.echo(f"[4/4] Testing and reloading nginx...")
            if dry_run:
                click.echo(f"  Would run: ssh {inst.ssh_host} 'sudo nginx -t && sudo systemctl reload nginx'")
            else:
                result = subprocess.run(reload_cmd, capture_output=True, text=True)
                if result.returncode != 0:
                    click.echo(f"  [ERROR] Nginx reload failed: {result.stderr}")
                    click.echo("  Run 'sudo nginx -t' on the instance to see errors")
                    continue
                click.echo("  [OK] Nginx configuration tested and reloaded")

        click.echo(f"\n[SUCCESS] Instance {inst_num} deployment complete!")

    click.echo(f"\n{'=' * 60}")
    click.echo("Deployment Summary")
    click.echo("=" * 60)
    if dry_run:
        click.echo("[DRY-RUN] No changes were made")
    else:
        click.echo("Configs deployed. Verify with: sega nginx status --instance <N>")


@nginx.command("status-remote")
@click.option("--instance", "-i", type=click.Choice(["1", "2", "3", "all"]), default="all", help="Instance to check")
def status_remote(instance):
    """Check nginx status on remote EC2 instance(s).

    Examples:
        sega nginx status-remote              # Check all instances
        sega nginx status-remote -i 2         # Check Instance 2 only
    """
    instances_to_check = []

    if instance == "all":
        instances_to_check = [("1", INSTANCE1), ("2", INSTANCE2), ("3", INSTANCE3)]
    else:
        instance_map = {"1": INSTANCE1, "2": INSTANCE2, "3": INSTANCE3}
        instances_to_check = [(instance, instance_map[instance])]

    try:
        ssh_key = get_ssh_key_path()
    except FileNotFoundError as e:
        click.echo(f"[ERROR] {e}")
        raise click.Abort()

    ssh_opts = get_ssh_options()

    for inst_num, inst in instances_to_check:
        if not inst.ip:
            click.echo(f"\nInstance {inst_num}: [SKIP] No IP configured")
            continue

        click.echo(f"\n{'=' * 50}")
        click.echo(f"Instance {inst_num} ({inst.ip})")
        click.echo("=" * 50)

        # Check nginx status
        status_cmd = [
            "ssh",
            "-i",
            str(ssh_key),
            *ssh_opts,
            inst.ssh_host,
            "systemctl is-active nginx && nginx -t 2>&1 | tail -1",
        ]

        result = subprocess.run(status_cmd, capture_output=True, text=True)

        if result.returncode == 0:
            lines = result.stdout.strip().split("\n")
            nginx_status = lines[0] if lines else "unknown"
            config_status = lines[-1] if len(lines) > 1 else "unknown"

            click.echo(f"  Nginx Service: {nginx_status}")
            click.echo(f"  Config Test: {config_status}")
        else:
            click.echo(f"  [ERROR] Could not connect or check status")
            click.echo(f"  {result.stderr.strip()}")


@nginx.command("check")
@click.option(
    "--instance",
    "-i",
    type=click.Choice(["1", "2", "3", "all"]),
    default="all",
    help="Instance to check (default: all)",
)
@click.option("--ssl", is_flag=True, help="Check SSL certificates")
@click.option("--certbot", is_flag=True, help="Check certbot auto-renewal")
@click.option("--domains", is_flag=True, help="List configured domains")
@click.option("--detailed", is_flag=True, help="Show detailed information")
@click.option(
    "--format", "output_format", type=click.Choice(["table", "json", "markdown"]), default="table", help="Output format"
)
def check(instance, ssl, certbot, domains, detailed, output_format):
    """Comprehensive nginx and SSL configuration check.

    Validates nginx configuration, SSL certificates, certbot auto-renewal,
    and domain mappings across EC2 instances.

    Examples:
        sega nginx check                    # Check all instances (basic)
        sega nginx check -i 1 --ssl        # Check Instance 1 SSL
        sega nginx check --ssl --certbot   # Full check all instances
        sega nginx check --detailed        # Detailed output
        sega nginx check --format json     # JSON output
    """
    # If no specific checks requested, enable all
    if not any([ssl, certbot, domains]):
        ssl = certbot = domains = True

    # Determine which instances to check
    instances_to_check = []

    if instance == "all":
        instances_to_check = [("1", INSTANCE1), ("2", INSTANCE2), ("3", INSTANCE3)]
    else:
        instance_map = {"1": INSTANCE1, "2": INSTANCE2, "3": INSTANCE3}
        instances_to_check = [(instance, instance_map[instance])]

    # Get SSH configuration
    try:
        ssh_key = get_ssh_key_path()
    except FileNotFoundError as e:
        click.echo(f"[ERROR] {e}")
        raise click.Abort()

    ssh_opts = get_ssh_options()

    # Create checker
    checker = NginxChecker(ssh_key, ssh_opts)

    # Collect results
    results = []

    for inst_num, inst in instances_to_check:
        # Skip instances without IP
        if not inst.ip:
            click.echo(f"\n[SKIP] Instance {inst_num}: No IP configured (TBD)")
            continue

        # Show progress (only for table format)
        if output_format == "table":
            click.echo(f"Checking Instance {inst_num} ({inst.ip})...")

        try:
            result = checker.check_instance(inst, inst_num, check_ssl=ssl, check_certbot=certbot, check_domains=domains)
            results.append(result)
        except Exception as e:
            click.echo(f"[ERROR] Failed to check Instance {inst_num}: {e}")
            continue

    # Format and output results
    if not results:
        click.echo("[ERROR] No instances could be checked")
        raise click.Abort()

    output = checker.format_results(results, output_format, detailed)
    click.echo(output)
