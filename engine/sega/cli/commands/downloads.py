#!/usr/bin/env python3
"""
SEGA DOWNLOADS INFRASTRUCTURE COMMAND
==============================================================================
File: engine/sega/cli/commands/downloads.py
Purpose: Desktop binary downloads infrastructure management
==============================================================================
"""

import subprocess
from pathlib import Path
from typing import Optional

import click

from ...core.config import get_config
from ...infrastructure import (
    INSTANCE1,
    INSTANCE2,
    INSTANCE3,
    get_ssh_key_path,
    get_ssh_options,
)

# A few projects serve their downloads/product site on a domain distinct from
# their primary app domain; those carry a `downloads` key in their `[domains]`
# config entry.
def _download_domain(project: str):
    """Domain for a project's downloads site (config override, else app domain)."""
    cfg = get_config()
    domain = cfg.domains.get(project)
    if domain is not None and domain.downloads:
        return domain.downloads
    return cfg.get_domain(project)


# Project -> downloads-site domain. Retained as a module symbol because
# models.py/binaries.py import it as a single-domain map
# (PROJECT_DOMAINS.get(project) -> "domain.tld"). nginx/sites-available/*.conf
# must match these domains.
PROJECT_DOMAINS = {name: _download_domain(name) for name in get_config().domains}

# Instance 1 projects with desktop builds — derived from configured domains.
INSTANCE1_PROJECTS = list(PROJECT_DOMAINS.keys())


@click.group()
def downloads():
    """Manage desktop binary downloads infrastructure."""
    pass


@downloads.command()
@click.option("--instance", "-i", type=int, default=1, help="Instance number (default: 1)")
@click.option("--project", "-p", help="Specific project (default: all)")
@click.option("--dry-run", is_flag=True, help="Show what would be created")
def setup_directories(instance, project, dry_run):
    """Create download directory structure on instance."""
    if instance != 1:
        click.echo(f"Error: Downloads currently only supported on Instance 1")
        return

    projects = [project] if project else INSTANCE1_PROJECTS

    click.echo(f"Setting up download directories on Instance {instance}...")
    click.echo(f"Projects: {', '.join(projects)}")

    if dry_run:
        click.echo("\nDry run - would create:")
        for proj in projects:
            click.echo(f"  /var/www/downloads/{proj}/{{mac,windows,linux}}/")
        return

    # Build command
    commands = []
    commands.append("sudo mkdir -p /var/www/downloads/")

    for proj in projects:
        commands.append(f"sudo mkdir -p /var/www/downloads/{proj}/{{mac,windows,linux}}")

    commands.append("sudo chown -R www-data:www-data /var/www/downloads/")
    commands.append("sudo chmod -R 755 /var/www/downloads/")

    # Execute on instance
    instance_config = INSTANCE1
    ssh_key = get_ssh_key_path()
    ssh_opts = get_ssh_options()

    full_command = " && ".join(commands)
    ssh_command = [
        "ssh",
        *ssh_opts,
        "-i",
        str(ssh_key),
        f"{instance_config.user}@{instance_config.ip}",
        full_command,
    ]

    click.echo(f"\nExecuting on Instance {instance}...")
    result = subprocess.run(ssh_command)

    if result.returncode == 0:
        click.echo(f"✓ Download directories created successfully")
    else:
        click.echo(f"✗ Failed to create directories")
        raise click.Abort()


@downloads.command()
@click.option("--instance", "-i", type=int, default=1, help="Instance number")
@click.option("--project", "-p", help="Specific project (default: all)")
@click.option("--template", "-t", type=click.Path(exists=True), help="Custom nginx template")
@click.option("--dry-run", is_flag=True, help="Show generated config without applying")
def add_nginx(instance, project, template, dry_run):
    """Add downloads server blocks to nginx configs."""
    if instance != 1:
        click.echo(f"Error: Downloads currently only supported on Instance 1")
        return

    projects = [project] if project else INSTANCE1_PROJECTS

    click.echo(f"Adding downloads nginx configs for: {', '.join(projects)}")

    # Use local nginx configs from sega/nginx/sites-available/
    sega_root = Path(__file__).parent.parent.parent.parent.parent
    nginx_configs = sega_root / "nginx" / "sites-available"

    config = get_config()

    for proj in projects:
        domain = _download_domain(proj)
        if not domain:
            click.echo(f"⚠ No domain configured for {proj}")
            continue
        downloads_subdomain = f"downloads.{domain}"

        # Check if local config exists
        config_file = nginx_configs / f"{domain}.conf"
        if not config_file.exists():
            click.echo(f"⚠ Local config not found: {config_file}")
            continue

        click.echo(f"\nProcessing {proj} ({domain})...")

        if dry_run:
            click.echo(f"  Would add downloads block for: {downloads_subdomain}")
            click.echo(f"  Source: {config_file}")
            continue

        # Generate downloads server block
        downloads_config = generate_downloads_block(proj, domain)

        # Append to local config file
        with open(config_file, "a") as f:
            f.write("\n\n")
            f.write(downloads_config)

        click.echo(f"  ✓ Added downloads config locally")

    if not dry_run:
        click.echo("\n✓ Nginx configs updated locally")
        click.echo("\nNext steps:")
        click.echo("  1. Deploy configs: sega downloads deploy-configs")
        click.echo("  2. Install SSL: sega downloads install-ssl")


@downloads.command()
@click.option("--instance", "-i", type=int, default=1, help="Instance number")
@click.option("--project", "-p", help="Specific project")
def deploy_configs(instance, project):
    """Deploy local nginx configs to instance."""
    if instance != 1:
        click.echo(f"Error: Downloads currently only supported on Instance 1")
        return

    projects = [project] if project else INSTANCE1_PROJECTS

    click.echo(f"Deploying nginx configs to Instance {instance}...")

    sega_root = Path(__file__).parent.parent.parent.parent.parent
    nginx_configs = sega_root / "nginx" / "sites-available"

    instance_config = INSTANCE1
    ssh_key = get_ssh_key_path()
    ssh_opts = get_ssh_options()

    config = get_config()

    for proj in projects:
        domain = _download_domain(proj)
        if not domain:
            click.echo(f"⚠ No domain configured for {proj}")
            continue
        config_file = nginx_configs / f"{domain}.conf"

        if not config_file.exists():
            click.echo(f"⚠ Config not found: {config_file}")
            continue

        click.echo(f"\nDeploying {domain}.conf...")

        # SCP config to instance
        scp_command = [
            "scp",
            *ssh_opts,
            "-i",
            str(ssh_key),
            str(config_file),
            f"{instance_config.user}@{instance_config.ip}:/tmp/{domain}.conf",
        ]

        subprocess.run(scp_command, check=True)

        # Move to sites-enabled and reload
        ssh_command = [
            "ssh",
            *ssh_opts,
            "-i",
            str(ssh_key),
            f"{instance_config.user}@{instance_config.ip}",
            f"sudo mv /tmp/{domain}.conf /etc/nginx/sites-enabled/{proj} && sudo nginx -t && sudo systemctl reload nginx",
        ]

        result = subprocess.run(ssh_command)

        if result.returncode == 0:
            click.echo(f"  ✓ Deployed and reloaded")
        else:
            click.echo(f"  ✗ Deployment failed")


@downloads.command()
@click.option("--instance", "-i", type=int, default=1, help="Instance number")
@click.option("--project", "-p", help="Specific project")
@click.option("--email", "-e", envvar="SEGA_LETSENCRYPT_EMAIL", required=True, help="Email for Let's Encrypt (or set SEGA_LETSENCRYPT_EMAIL)")
def install_ssl(instance, project, email):
    """Install SSL certificates for downloads subdomains."""
    if instance != 1:
        click.echo(f"Error: Downloads currently only supported on Instance 1")
        return

    projects = [project] if project else INSTANCE1_PROJECTS

    click.echo(f"Installing SSL certificates...")
    click.echo(f"Email: {email}")

    instance_config = INSTANCE1
    ssh_key = get_ssh_key_path()
    ssh_opts = get_ssh_options()

    config = get_config()

    for proj in projects:
        domain = _download_domain(proj)
        if not domain:
            click.echo(f"⚠ No domain configured for {proj}")
            continue
        downloads_subdomain = f"downloads.{domain}"

        click.echo(f"\nInstalling SSL for {downloads_subdomain}...")

        # Run certbot on instance
        certbot_cmd = f"sudo certbot --nginx -d {downloads_subdomain} --non-interactive --agree-tos --email {email}"

        ssh_command = [
            "ssh",
            *ssh_opts,
            "-i",
            str(ssh_key),
            f"{instance_config.user}@{instance_config.ip}",
            certbot_cmd,
        ]

        result = subprocess.run(ssh_command)

        if result.returncode == 0:
            click.echo(f"  ✓ SSL installed")
        else:
            click.echo(f"  ⚠ SSL installation failed (check DNS)")


@downloads.command()
@click.option("--instance", "-i", type=int, default=1, help="Instance number")
def verify(instance):
    """Verify downloads infrastructure setup."""
    if instance != 1:
        click.echo(f"Error: Downloads currently only supported on Instance 1")
        return

    click.echo(f"Verifying downloads infrastructure on Instance {instance}...")

    instance_config = INSTANCE1
    ssh_key = get_ssh_key_path()
    ssh_opts = get_ssh_options()

    # Check directories
    click.echo("\n1. Checking directories...")
    check_cmd = "ls -la /var/www/downloads/ | grep -E '^d'"

    ssh_command = [
        "ssh",
        *ssh_opts,
        "-i",
        str(ssh_key),
        f"{instance_config.user}@{instance_config.ip}",
        check_cmd,
    ]

    subprocess.run(ssh_command)

    # Check HTTPS access
    click.echo("\n2. Checking HTTPS access...")
    config = get_config()
    for proj in INSTANCE1_PROJECTS[:3]:  # Test first 3
        domain = _download_domain(proj)
        if not domain:
            continue
        subdomain = f"downloads.{domain}"

        click.echo(f"  Testing {subdomain}...")
        result = subprocess.run(
            ["curl", "-s", "-o", "/dev/null", "-w", "%{http_code}", f"https://{subdomain}/"],
            capture_output=True,
            text=True,
        )

        status = result.stdout.strip()
        if status == "200":
            click.echo(f"    ✓ HTTP {status}")
        else:
            click.echo(f"    ⚠ HTTP {status}")


def generate_downloads_block(project: str, domain: str) -> str:
    """Generate downloads server block configuration."""
    return f"""# ============================================
# Downloads Subdomain - Desktop Binaries
# Project: {project}
# ============================================

# HTTP to HTTPS redirect
server {{
    listen 80;
    listen [::]:80;
    server_name downloads.{domain};
    
    location /.well-known/acme-challenge/ {{
        root /var/www/html;
    }}
    
    location / {{
        return 301 https://$server_name$request_uri;
    }}
}}

# HTTPS - Static file serving
server {{
    listen 443 ssl http2;
    listen [::]:443 ssl http2;
    server_name downloads.{domain};
    
    # SSL (managed by certbot)
    ssl_certificate /etc/letsencrypt/live/downloads.{domain}/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/downloads.{domain}/privkey.pem;
    
    # SSL best practices
    ssl_protocols TLSv1.2 TLSv1.3;
    ssl_prefer_server_ciphers off;
    
    # Security headers
    add_header Strict-Transport-Security "max-age=31536000" always;
    add_header X-Frame-Options DENY always;
    add_header X-Content-Type-Options nosniff always;
    
    # Static file serving
    root /var/www/downloads/{project};
    autoindex on;
    
    # Force download for binaries
    location ~* \\.(dmg|exe|AppImage)$ {{
        add_header Content-Disposition "attachment";
        expires 30d;
    }}
    
    # Version manifest
    location /latest.yml {{
        expires 1h;
    }}
    
    # CORS for version checks
    add_header Access-Control-Allow-Origin "*" always;
}}"""
