#!/usr/bin/env python3
# -*- coding: utf-8 -*-
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
SEGA CLOUDFLARE MANAGER
================================================================================
Manages Cloudflare DNS records and Tunnels for exposing local services.

Features:
- DNS record management (A, CNAME records)
- Cloudflare Tunnel management
- Dynamic IP detection and DDNS updates
- Integration with SEGA deployment system

Usage:
    cf = CloudflareManager()
    cf.update_dns_record("atlas.yourdomain.com", "192.168.1.100")
    cf.create_tunnel_route("node-1", "atlas.yourdomain.com", 3000)
"""

import os
import json
import logging
import subprocess
import requests
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, field
from pathlib import Path
from enum import Enum

logger = logging.getLogger(__name__)


class RecordType(Enum):
    A = "A"
    AAAA = "AAAA"
    CNAME = "CNAME"
    TXT = "TXT"


@dataclass
class DNSRecord:
    """Cloudflare DNS record."""
    name: str
    type: str
    content: str
    ttl: int = 300
    proxied: bool = True


@dataclass
class TunnelRoute:
    """Tunnel route configuration."""
    project: str
    domain: str
    local_port: int
    protocol: str = "http"


@dataclass
class Tunnel:
    """Cloudflare Tunnel configuration."""
    name: str
    id: Optional[str] = None
    routes: List[TunnelRoute] = field(default_factory=list)
    host: str = ""
    user: str = "ubuntu"


@dataclass
class LocalHost:
    """Local host configuration (e.g., node-1, home server)."""
    name: str
    ip: str
    user: str
    host_type: str = "generic"  # mac_mini, linux_server, etc.
    ram_gb: int = 0
    storage_gb: int = 0
    ssh_key_path: Optional[str] = None


class CloudflareManager:
    """
    Manages Cloudflare DNS and Tunnel operations.
    
    Supports two modes of operation:
    1. DNS-only: Update A/CNAME records for existing domains
    2. Tunnel: Create Cloudflare Tunnels to expose local services
    """

    def __init__(
        self,
        api_token: Optional[str] = None,
        zone_id: Optional[str] = None,
        account_id: Optional[str] = None,
        config: Optional[Dict] = None
    ):
        """
        Initialize Cloudflare Manager.
        
        Args:
            api_token: Cloudflare API token (or env:CF_API_TOKEN)
            zone_id: Cloudflare Zone ID
            account_id: Cloudflare Account ID (required for tunnels)
            config: Full config dict from sega.toml [cloudflare] section
        """
        self.api_token = self._resolve_token(api_token or os.environ.get("CF_API_TOKEN"))
        self.zone_id = zone_id or os.environ.get("CF_ZONE_ID")
        self.account_id = account_id or os.environ.get("CF_ACCOUNT_ID") or "46a4d004cbbacaaa295cd42f01231751"
        self.config = config or {}
        
        if not self.api_token:
            raise ValueError("Cloudflare API token required. Set CF_API_TOKEN or pass api_token")
        
        self.base_url = "https://api.cloudflare.com/client/v4"
        self.headers = {
            "Authorization": f"Bearer {self.api_token}",
            "Content-Type": "application/json"
        }

    def _resolve_token(self, token: Optional[str]) -> Optional[str]:
        """Resolve token from env: prefix."""
        if token and token.startswith("env:"):
            env_var = token[4:]
            return os.environ.get(env_var)
        return token

    def _request(
        self,
        method: str,
        endpoint: str,
        data: Optional[Dict] = None,
        params: Optional[Dict] = None
    ) -> Dict:
        """Make API request to Cloudflare."""
        url = f"{self.base_url}/{endpoint}"
        
        try:
            response = requests.request(
                method=method,
                url=url,
                headers=self.headers,
                json=data,
                params=params,
                timeout=30
            )
            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException as e:
            logger.error(f"Cloudflare API error: {e}")
            raise

    def get_zone_id(self, domain: str) -> str:
        """Get zone ID for a domain."""
        if self.zone_id:
            return self.zone_id
            
        parts = domain.split(".")
        if len(parts) >= 2:
            zone_name = ".".join(parts[-2:])
        else:
            zone_name = domain
            
        result = self._request("GET", f"zones", params={"name": zone_name})
        if result.get("result"):
            return result["result"][0]["id"]
        raise ValueError(f"Could not find zone for {domain}")

    def list_dns_records(self, domain: str) -> List[Dict]:
        """List all DNS records for a domain."""
        zone_id = self.get_zone_id(domain)
        result = self._request("GET", f"zones/{zone_id}/dns_records", 
                              params={"name": domain})
        return result.get("result", [])

    def get_dns_record(self, domain: str, record_type: str = "A") -> Optional[Dict]:
        """Get existing DNS record."""
        zone_id = self.get_zone_id(domain)
        result = self._request(
            "GET", 
            f"zones/{zone_id}/dns_records",
            params={"name": domain, "type": record_type}
        )
        records = result.get("result", [])
        return records[0] if records else None

    def create_dns_record(
        self,
        domain: str,
        content: str,
        record_type: str = "A",
        ttl: int = 300,
        proxied: bool = True
    ) -> Dict:
        """
        Create a new DNS record.
        
        Args:
            domain: Full domain (e.g., atlas.yourdomain.com)
            content: IP address or CNAME target
            record_type: A, AAAA, CNAME, TXT
            ttl: Time to live (seconds)
            proxied: Whether to proxy through Cloudflare
            
        Returns:
            Created record dict
        """
        zone_id = self.get_zone_id(domain)
        
        data = {
            "name": domain,
            "type": record_type,
            "content": content,
            "ttl": ttl,
            "proxied": proxied
        }
        
        result = self._request("POST", f"zones/{zone_id}/dns_records", data)
        logger.info(f"Created {record_type} record for {domain} -> {content}")
        return result.get("result", {})

    def update_dns_record(
        self,
        domain: str,
        content: str,
        record_type: str = "A",
        ttl: int = 300,
        proxied: bool = True
    ) -> Dict:
        """
        Update existing DNS record or create if not exists.
        
        Args:
            domain: Full domain
            content: IP address or CNAME target
            record_type: A, AAAA, CNAME
            ttl: Time to live
            proxied: Proxy through Cloudflare
            
        Returns:
            Updated/created record dict
        """
        existing = self.get_dns_record(domain, record_type)
        
        if existing:
            zone_id = self.get_zone_id(domain)
            data = {
                "name": domain,
                "type": record_type,
                "content": content,
                "ttl": ttl,
                "proxied": proxied
            }
            result = self._request(
                "PUT",
                f"zones/{zone_id}/dns_records/{existing['id']}",
                data
            )
            logger.info(f"Updated {record_type} record for {domain} -> {content}")
            return result.get("result", {})
        else:
            return self.create_dns_record(domain, content, record_type, ttl, proxied)

    def delete_dns_record(self, domain: str, record_type: str = "A") -> bool:
        """Delete a DNS record."""
        existing = self.get_dns_record(domain, record_type)
        if existing:
            zone_id = self.get_zone_id(domain)
            self._request("DELETE", f"zones/{zone_id}/dns_records/{existing['id']}")
            logger.info(f"Deleted {record_type} record for {domain}")
            return True
        return False

    def get_public_ip(self) -> str:
        """Get current public IP address."""
        try:
            response = requests.get("https://api.ipify.org", timeout=10)
            return response.text.strip()
        except Exception as e:
            logger.error(f"Failed to get public IP: {e}")
            raise

    def update_ddns(
        self,
        domain: str,
        ttl: int = 300,
        proxied: bool = True
    ) -> Dict:
        """
        Update DNS A record to current public IP (DDNS).
        
        Args:
            domain: Domain to update
            ttl: Time to live
            proxied: Proxy through Cloudflare
            
        Returns:
            Updated record
        """
        public_ip = self.get_public_ip()
        return self.update_dns_record(domain, public_ip, "A", ttl, proxied)

    # =========================================================================
    # Tunnel Management
    # =========================================================================

    def list_tunnels(self) -> List[Dict]:
        """List all Cloudflare Tunnels."""
        result = self._request("GET", f"accounts/{self.account_id}/cfd_tunnel")
        return result.get("result", [])

    def get_tunnel(self, name: str) -> Optional[Dict]:
        """Get tunnel by name."""
        result = self._request("GET", f"accounts/{self.account_id}/cfd_tunnel")
        tunnels = result.get("result", [])
        for tunnel in tunnels:
            if tunnel.get("name") == name:
                return tunnel
        return None

    def create_tunnel(
        self,
        name: str,
        secret: Optional[str] = None
    ) -> Dict:
        """
        Create a new Cloudflare Tunnel.
        
        Args:
            name: Tunnel name
            secret: Tunnel secret (auto-generated if not provided)
            
        Returns:
            Created tunnel dict
        """
        import secrets as secrets_module
        import base64
        
        # Generate 32-byte secret and base64 encode it
        secret_bytes = secrets_module.token_bytes(32)
        secret_b64 = base64.b64encode(secret_bytes).decode('utf-8')
        
        data = {
            "name": name,
            "tunnel_secret": secret_b64,
            "config_src": "local"
        }
        
        result = self._request("POST", f"accounts/{self.account_id}/cfd_tunnel", data)
        logger.info(f"Created Cloudflare Tunnel: {name}")
        return result.get("result", {})

    def ensure_tunnel(self, name: str) -> Dict:
        """Get existing tunnel or create new one."""
        existing = self.get_tunnel(name)
        if existing:
            return existing
        return self.create_tunnel(name)

    def delete_tunnel(self, name: str) -> bool:
        """Delete a tunnel by name."""
        tunnel = self.get_tunnel(name)
        if tunnel:
            self._request("DELETE", f"accounts/{self.account_id}/cfd_tunnel/{tunnel['id']}")
            logger.info(f"Deleted tunnel: {name}")
            return True
        return False

    def create_tunnel_dns_route(
        self,
        tunnel_name: str,
        domain: str,
        origin_ip: Optional[str] = None
    ) -> Dict:
        """
        Create DNS CNAME record pointing to tunnel.
        
        Args:
            tunnel_name: Name of the tunnel
            domain: Domain to route (e.g., atlas.yourdomain.com)
            origin_ip: Origin IP (not needed for tunnels, used for A records)
            
        Returns:
            Created DNS record
        """
        tunnel = self.ensure_tunnel(tunnel_name)
        tunnel_uuid = tunnel.get("id") or tunnel.get("tunnel_id")
        
        cname_target = f"{tunnel_uuid}.cfargotunnel.com"
        
        return self.update_dns_record(
            domain=domain,
            content=cname_target,
            record_type="CNAME",
            ttl=300,
            proxied=True
        )

    def install_cloudflared(self, host: str, user: str) -> bool:
        """
        Install cloudflared on remote host via SSH.
        
        Args:
            host: Hostname or IP
            user: SSH user
            
        Returns:
            True if successful
        """
        install_script = """
        if command -v cloudflared &> /dev/null; then
            echo "cloudflared already installed"
        else
            curl -sSL https://github.com/cloudflare/cloudflared/releases/latest/download/cloudflared-linux-amd64 -o /usr/local/bin/cloudflared
            chmod +x /usr/local/bin/cloudflared
            echo "cloudflared installed"
        fi
        """
        
        try:
            result = subprocess.run(
                ["ssh", f"{user}@{host}", install_script],
                capture_output=True,
                text=True,
                timeout=60
            )
            return result.returncode == 0
        except Exception as e:
            logger.error(f"Failed to install cloudflared: {e}")
            return False

    def start_tunnel(
        self,
        tunnel_name: str,
        local_port: int,
        host: str = "localhost",
        protocol: str = "http",
        port: int = 8080
    ) -> subprocess.Popen:
        """
        Start cloudflared tunnel to local service.
        
        Args:
            tunnel_name: Name of tunnel
            local_port: Local service port
            host: Local host (default localhost)
            protocol: http or https
            port: Tunnel listener port
            
        Returns:
            Popen process object
        """
        tunnel = self.ensure_tunnel(tunnel_name)
        tunnel_token = tunnel.get("token")
        
        if not tunnel_token:
            tunnel_id = tunnel.get("id") or tunnel.get("tunnel_id")
            tunnel_token = tunnel.get("access_token")
        
        cmd = [
            "cloudflared",
            "tunnel",
            "--url", f"{protocol}://{host}:{local_port}",
        ]
        
        if tunnel_token:
            cmd.extend(["--token", tunnel_token])
        else:
            cmd.extend(["--tunnel-id", tunnel.get("id", "")])
        
        process = subprocess.Popen(cmd)
        logger.info(f"Started tunnel {tunnel_name} -> {protocol}://{host}:{local_port}")
        return process

    def deploy_tunnel_service(
        self,
        tunnel_config: Tunnel,
        project: str,
        local_port: int,
        domain: str,
        protocol: str = "http"
    ) -> Dict:
        """
        Full tunnel deployment: ensure tunnel + DNS route + start connector.
        
        Args:
            tunnel_config: Tunnel configuration
            project: Project name
            local_port: Local service port
            domain: Public domain
            protocol: http or https
            
        Returns:
            Deployment result
        """
        results = {}
        
        tunnel = self.ensure_tunnel(tunnel_config.name)
        results["tunnel"] = tunnel
        
        dns_result = self.create_tunnel_dns_route(
            tunnel_name=tunnel_config.name,
            domain=domain
        )
        results["dns"] = dns_result
        
        logger.info(f"Deployed {project} at {domain} -> localhost:{local_port}")
        
        return results

    # =========================================================================
    # Integration Helpers
    # =========================================================================

    def configure_for_local_deployment(
        self,
        local_host: LocalHost,
        routes: List[TunnelRoute]
    ) -> Dict:
        """
        Configure Cloudflare for a local deployment.
        
        Args:
            local_host: Local host config
            routes: List of routes to expose
            
        Returns:
            Configuration result
        """
        results = {}
        
        for route in routes:
            results[route.domain] = self.deploy_tunnel_service(
                tunnel_config=Tunnel(
                    name=local_host.name,
                    host=local_host.ip,
                    user=local_host.user
                ),
                project=route.project,
                local_port=route.local_port,
                domain=route.domain,
                protocol=route.protocol
            )
        
        return results


class DDNSUpdater:
    """
    Dynamic DNS updater for home networks.
    
    Usage:
        updater = DDNSUpdater("yourdomain.com", "api-token")
        updater.run(interval=300)  # Check every 5 minutes
    """

    def __init__(self, domain: str, api_token: str, zone_id: Optional[str] = None):
        self.manager = CloudflareManager(api_token=api_token, zone_id=zone_id)
        self.domain = domain
        self.last_ip = None

    def check_and_update(self) -> bool:
        """Check if IP changed and update if needed."""
        current_ip = self.manager.get_public_ip()
        
        if current_ip != self.last_ip:
            logger.info(f"IP changed: {self.last_ip} -> {current_ip}")
            self.manager.update_ddns(self.domain)
            self.last_ip = current_ip
            return True
        
        return False

    def run(self, interval: int = 300):
        """Run DDNS updater loop."""
        import time
        logger.info(f"Starting DDNS updater for {self.domain}")
        
        while True:
            try:
                self.check_and_update()
            except Exception as e:
                logger.error(f"DDNS update error: {e}")
            
            time.sleep(interval)


def from_config(config: Dict) -> CloudflareManager:
    """Create CloudflareManager from sega.toml config."""
    api_token = config.get("api_token", "")
    if api_token.startswith("env:"):
        api_token = os.environ.get(api_token[4:])
    
    return CloudflareManager(
        api_token=api_token,
        zone_id=config.get("zone_id"),
        config=config
    )
