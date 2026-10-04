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
SEGA VPN INFRASTRUCTURE MANAGER
=============================================================================
Manages VPN server provisioning, client configuration, and network topology.
"""

import os
import subprocess
import logging
from typing import Dict, List, Optional, Any
from pathlib import Path
from dataclasses import dataclass

logger = logging.getLogger(__name__)


@dataclass
class VPNConfig:
    """VPN configuration parameters."""

    domain: str = "vpn.example.com"
    network: str = "10.10.10.0/24"
    port: int = 1194
    protocol: str = "udp"
    device: str = "tap"
    ca_country: str = "US"
    ca_province: str = "State"
    ca_city: str = "City"
    ca_org: str = "Example Organization"
    ca_email: str = "admin@example.com"
    ca_ou: str = "IT"


class VPNManager:
    """Manages VPN infrastructure provisioning and configuration."""

    def __init__(self, config: Optional[VPNConfig] = None):
        self.config = config or VPNConfig()
        self.ca_dir = Path.home() / "openvpn-ca"
        self.client_config_dir = self.ca_dir / "client-configs"

    def provision_server(
        self, host: str, ssh_key: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Provision a VPN server on a remote host.

        Args:
            host: Target host IP or hostname
            ssh_key: Path to SSH private key

        Returns:
            Provisioning result with server details
        """
        logger.info(f"Provisioning VPN server on {host}")

        # Generate provisioning script
        script = self._generate_server_script()

        # Execute remotely via SSH
        ssh_cmd = ["ssh"]
        if ssh_key:
            ssh_cmd.extend(["-i", ssh_key])
        ssh_cmd.extend([f"root@{host}", "bash -s"])

        try:
            result = subprocess.run(
                ssh_cmd, input=script.encode(), capture_output=True, text=True
            )

            if result.returncode == 0:
                logger.info("VPN server provisioned successfully")
                return {
                    "status": "success",
                    "host": host,
                    "network": self.config.network,
                    "port": self.config.port,
                    "ca_cert": self._get_ca_cert(),
                }
            else:
                logger.error(f"VPN provisioning failed: {result.stderr}")
                return {"status": "failed", "error": result.stderr}

        except Exception as e:
            logger.error(f"VPN provisioning error: {e}")
            return {"status": "error", "error": str(e)}

    def generate_client_config(
        self, client_name: str, output_path: Optional[str] = None
    ) -> str:
        """
        Generate VPN client configuration.

        Args:
            client_name: Name for the client certificate
            output_path: Where to save the .ovpn file

        Returns:
            Path to generated .ovpn file
        """
        logger.info(f"Generating VPN client config for {client_name}")

        # Ensure CA exists
        if not self.ca_dir.exists():
            raise RuntimeError(
                "CA not initialized. Run server provisioning first."
            )

        # Generate client certificate
        self._generate_client_cert(client_name)

        # Create .ovpn file
        ovpn_content = self._create_ovpn_config(client_name)

        # Save to file
        if output_path:
            ovpn_path = Path(output_path)
        else:
            ovpn_path = self.client_config_dir / f"{client_name}.ovpn"

        ovpn_path.parent.mkdir(parents=True, exist_ok=True)
        ovpn_path.write_text(ovpn_content)

        logger.info(f"Client config saved to {ovpn_path}")
        return str(ovpn_path)

    def list_clients(self) -> List[Dict[str, str]]:
        """List all VPN clients."""
        clients = []

        if self.client_config_dir.exists():
            for ovpn_file in self.client_config_dir.glob("*.ovpn"):
                clients.append(
                    {
                        "name": ovpn_file.stem,
                        "config": str(ovpn_file),
                        "created": ovpn_file.stat().st_mtime,
                    }
                )

        return clients

    def revoke_client(self, client_name: str) -> bool:
        """Revoke a client certificate."""
        logger.info(f"Revoking VPN access for {client_name}")

        try:
            # Revoke certificate
            subprocess.run(
                ["./easyrsa", "revoke", client_name],
                cwd=self.ca_dir,
                check=True,
            )

            # Generate CRL
            subprocess.run(
                ["./easyrsa", "gen-crl"], cwd=self.ca_dir, check=True
            )

            # Remove client config
            ovpn_path = self.client_config_dir / f"{client_name}.ovpn"
            if ovpn_path.exists():
                ovpn_path.unlink()

            logger.info(f"Client {client_name} revoked")
            return True

        except Exception as e:
            logger.error(f"Failed to revoke client: {e}")
            return False

    def get_network_status(
        self, host: str, ssh_key: Optional[str] = None
    ) -> Dict[str, Any]:
        """Get VPN network status from server."""
        ssh_cmd = ["ssh"]
        if ssh_key:
            ssh_cmd.extend(["-i", ssh_key])
        ssh_cmd.extend(
            [f"root@{host}", "cat /var/log/openvpn/openvpn-status.log"]
        )

        try:
            result = subprocess.run(ssh_cmd, capture_output=True, text=True)
            if result.returncode == 0:
                return self._parse_vpn_status(result.stdout)
            else:
                return {"status": "error", "error": result.stderr}
        except Exception as e:
            return {"status": "error", "error": str(e)}

    def _generate_server_script(self) -> str:
        """Generate VPN server provisioning script."""
        return f"""#!/bin/bash
set -euo pipefail

# Install OpenVPN and Easy-RSA
apt update && apt install -y openvpn easy-rsa

# Setup CA
make-cadir ~/openvpn-ca
cd ~/openvpn-ca

# Configure CA
cat > vars <<EOF
set_var EASYRSA_REQ_COUNTRY     "{self.config.ca_country}"
set_var EASYRSA_REQ_PROVINCE    "{self.config.ca_province}"
set_var EASYRSA_REQ_CITY        "{self.config.ca_city}"
set_var EASYRSA_REQ_ORG         "{self.config.ca_org}"
set_var EASYRSA_REQ_EMAIL       "{self.config.ca_email}"
set_var EASYRSA_REQ_OU          "{self.config.ca_ou}"
EOF

# Initialize PKI
./easyrsa init-pki
./easyrsa build-ca nopass <<< "FLEET CA"
./easyrsa gen-req fleet-vpn-server nopass <<< "FLEET VPN Server"
./easyrsa sign-req server fleet-vpn-server
./easyrsa gen-dh
openvpn --genkey secret ta.key

# Copy certificates
mkdir -p /etc/openvpn/server
cp pki/private/fleet-vpn-server.key /etc/openvpn/server/
cp pki/issued/fleet-vpn-server.crt /etc/openvpn/server/
cp ta.key /etc/openvpn/server/
cp pki/dh.pem /etc/openvpn/server/
cp pki/ca.crt /etc/openvpn/server/

# Configure server
cat > /etc/openvpn/server/fleet-vpn-server.conf <<EOF
proto {self.config.protocol}
port {self.config.port}
dev {self.config.device}
server {self.config.network.split('/')[0]} 255.255.255.0
topology subnet
client-to-client
keepalive 10 120
ca ca.crt
cert fleet-vpn-server.crt
key fleet-vpn-server.key
dh dh.pem
tls-crypt ta.key 0
cipher AES-256-CBC
data-ciphers AES-256-GCM:AES-128-GCM:AES-256-CBC
user nobody
group nogroup
persist-key
persist-tun
status /var/log/openvpn/openvpn-status.log
verb 3
EOF

# Enable IP forwarding
echo "net.ipv4.ip_forward = 1" >> /etc/sysctl.conf
sysctl -p

# Start VPN
mkdir -p /var/log/openvpn
systemctl enable openvpn-server@fleet-vpn-server.service
systemctl start openvpn-server@fleet-vpn-server.service

echo "VPN server provisioned successfully"
"""

    def _generate_client_cert(self, client_name: str):
        """Generate client certificate."""
        os.chdir(self.ca_dir)

        # Generate request
        subprocess.run(
            ["./easyrsa", "gen-req", client_name, "nopass"],
            input=f"{client_name}\n".encode(),
            check=True,
        )

        # Sign request
        subprocess.run(
            ["./easyrsa", "sign-req", "client", client_name], check=True
        )

    def _create_ovpn_config(self, client_name: str) -> str:
        """Create .ovpn configuration file."""
        ca_cert = (self.ca_dir / "pki" / "ca.crt").read_text()
        client_cert = (
            self.ca_dir / "pki" / "issued" / f"{client_name}.crt"
        ).read_text()
        client_key = (
            self.ca_dir / "pki" / "private" / f"{client_name}.key"
        ).read_text()
        ta_key = (self.ca_dir / "ta.key").read_text()

        return f"""client
proto {self.config.protocol}
dev {self.config.device}
remote {self.config.domain} {self.config.port}
resolv-retry infinite
nobind
user nobody
group nogroup
persist-key
persist-tun
verb 3
cipher AES-256-CBC
data-ciphers AES-256-GCM:AES-128-GCM:AES-256-CBC
remote-cert-tls server

<ca>
{ca_cert}</ca>

<cert>
{client_cert}</cert>

<key>
{client_key}</key>

<tls-crypt>
{ta_key}</tls-crypt>
"""

    def _get_ca_cert(self) -> str:
        """Get CA certificate."""
        ca_path = self.ca_dir / "pki" / "ca.crt"
        if ca_path.exists():
            return ca_path.read_text()
        return ""

    def _parse_vpn_status(self, status_log: str) -> Dict[str, Any]:
        """Parse OpenVPN status log."""
        lines = status_log.strip().split("\n")
        clients = []

        in_client_list = False
        for line in lines:
            if line.startswith("Common Name,Real Address"):
                in_client_list = True
                continue
            elif line.startswith("ROUTING TABLE"):
                in_client_list = False
                continue

            if in_client_list and "," in line:
                parts = line.split(",")
                if len(parts) >= 5:
                    clients.append(
                        {
                            "name": parts[0],
                            "address": parts[1],
                            "bytes_received": parts[2],
                            "bytes_sent": parts[3],
                            "connected_since": parts[4],
                        }
                    )

        return {
            "status": "active",
            "clients": clients,
            "client_count": len(clients),
        }
