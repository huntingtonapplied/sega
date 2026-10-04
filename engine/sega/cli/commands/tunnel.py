#!/usr/bin/env python3
"""
SEGA CLOUDFLARE TUNNEL DEPLOYMENT COMMAND
================================================================================
Deploy projects to local hosts with Cloudflare Tunnel exposure.

Usage:
    sega tunnel deploy atlas --host node-1 --port 3000 --domain atlas.yourdomain.com
    sega tunnel status
    sega tunnel list
    sega tunnel delete atlas

Environment Variables:
    CF_API_TOKEN: Cloudflare API token (Zone:DNS:Edit, Tunnel:Edit)
    CF_ZONE_ID: Cloudflare Zone ID (optional, auto-detected)
"""

import click
import sys
import os

# Add engine to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(__file__)))))

from sega.infrastructure.ec2_config import get_local_host, get_all_local_hosts
from sega.infrastructure.cloudflare_manager import CloudflareManager, Tunnel, TunnelRoute


@click.group()
def tunnel():
    """Manage Cloudflare Tunnels for local deployments."""
    pass


@tunnel.command()
@click.option("--host", required=True, help="Local host name (e.g., node-1)")
@click.option("--port", required=True, type=int, help="Local service port")
@click.option("--domain", required=True, help="Public domain (e.g., atlas.yourdomain.com)")
@click.option("--protocol", default="http", help="Protocol (http or https)")
@click.option("--project", default="", help="Project name for logging")
def deploy(host: str, port: int, domain: str, protocol: str, project: str):
    """Deploy a local service via Cloudflare Tunnel."""
    
    # Get local host config
    local_host = get_local_host(host)
    if not local_host:
        click.echo(f"Error: Host '{host}' not found. Available hosts:", err=True)
        for h in get_all_local_hosts():
            click.echo(f"  - {h.name}: {h.ip}")
        sys.exit(1)
    
    # Initialize Cloudflare manager
    try:
        cf = CloudflareManager()
    except ValueError as e:
        click.echo(f"Error: {e}", err=True)
        click.echo("Set CF_API_TOKEN environment variable", err=True)
        sys.exit(1)
    
    # Create tunnel config
    tunnel_config = Tunnel(
        name=host,
        host=local_host.ip,
        user=local_host.user,
        routes=[TunnelRoute(project=project, domain=domain, local_port=port, protocol=protocol)]
    )
    
    click.echo(f"Deploying {project or 'service'} from {host} ({local_host.ip}:{port})")
    click.echo(f"Public domain: {domain}")
    
    # Deploy tunnel
    try:
        result = cf.deploy_tunnel_service(
            tunnel_config=tunnel_config,
            project=project or host,
            local_port=port,
            domain=domain,
            protocol=protocol
        )
        
        click.echo(f"\n✓ Tunnel deployed successfully!")
        click.echo(f"  DNS: {domain} -> {tunnel_config.name}.cfargotunnel.com")
        
    except Exception as e:
        click.echo(f"Error deploying tunnel: {e}", err=True)
        sys.exit(1)


@tunnel.command()
@click.option("--domain", required=True, help="Domain to update")
@click.option("--ttl", default=300, help="DNS TTL in seconds")
def ddns(domain: str, ttl: int):
    """Update DNS A record to current public IP (Dynamic DNS)."""
    
    try:
        cf = CloudflareManager()
    except ValueError as e:
        click.echo(f"Error: {e}", err=True)
        sys.exit(1)
    
    try:
        result = cf.update_ddns(domain, ttl=ttl)
        current_ip = cf.get_public_ip()
        click.echo(f"✓ Updated {domain} -> {current_ip}")
    except Exception as e:
        click.echo(f"Error: {e}", err=True)
        sys.exit(1)


@tunnel.command()
def status():
    """List all Cloudflare Tunnels."""
    
    try:
        cf = CloudflareManager()
    except ValueError as e:
        click.echo(f"Error: {e}", err=True)
        sys.exit(1)
    
    try:
        tunnels = cf.list_tunnels()
        if not tunnels:
            click.echo("No tunnels found")
        else:
            for t in tunnels:
                click.echo(f"  {t.get('name')}: {t.get('id')}")
    except Exception as e:
        click.echo(f"Error: {e}", err=True)
        sys.exit(1)


@tunnel.command()
@click.argument("domain")
def delete(domain: str):
    """Delete DNS record for a domain."""
    
    try:
        cf = CloudflareManager()
    except ValueError as e:
        click.echo(f"Error: {e}", err=True)
        sys.exit(1)
    
    try:
        cf.delete_dns_record(domain)
        click.echo(f"✓ Deleted DNS record for {domain}")
    except Exception as e:
        click.echo(f"Error: {e}", err=True)
        sys.exit(1)


@tunnel.command()
def list_hosts():
    """List available local hosts."""
    hosts = get_all_local_hosts()
    
    if not hosts:
        click.echo("No local hosts configured")
        return
    
    for h in hosts:
        click.echo(f"  {h.name}:")
        click.echo(f"    IP: {h.ip}")
        click.echo(f"    User: {h.user}")
        click.echo(f"    Type: {h.host_type}")
        click.echo(f"    RAM: {h.ram_gb}GB")
        click.echo(f"    Storage: {h.storage_gb}GB")
        click.echo()


if __name__ == "__main__":
    tunnel()
