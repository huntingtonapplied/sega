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
EC2 Instance Configuration for FLEET Ecosystem

Reads configuration from config/sega.toml (central TOML config).
Environment variables can override toml values.

Config hierarchy (highest priority first):
1. Environment variables (SEGA_*)
2. config/sega.toml instances section
3. Hardcoded defaults
"""

import os
import sys
from dataclasses import dataclass

if sys.version_info >= (3, 11):
    import tomllib as toml_parser
else:
    try:
        import tomli as toml_parser
    except ImportError:
        toml_parser = None
from pathlib import Path
from typing import Dict, List, Optional, Any

from sega.core.config import get_config


# =============================================================================
# Local Host Configuration (for non-EC2 deployments like node-1)
# =============================================================================

@dataclass
class LocalHost:
    """
    Local non-EC2 host configuration (Mac Mini, home server, etc.).
    
    These are hosts that can be used as deployment targets but aren't
    EC2 instances (e.g., node-1, node-2 on local network).
    """
    
    name: str
    ip: str
    user: str
    host_type: str = "generic"
    ram_gb: int = 0
    storage_gb: int = 0
    ssh_key_path: Optional[str] = None
    enabled: bool = True
    
    @property
    def ssh_host(self) -> str:
        """Return user@ip format for SSH."""
        return f"{self.user}@{self.ip}"
    
    @property
    def ssh_options(self) -> List[str]:
        """Get SSH options for this host."""
        options = ["-o", "StrictHostKeyChecking=no"]
        
        if self.ssh_key_path:
            key_path = Path(self.ssh_key_path).expanduser()
            if key_path.exists():
                options.extend(["-i", str(key_path)])
        
        return options
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "name": self.name,
            "ip": self.ip,
            "user": self.user,
            "type": self.host_type,
            "ram_gb": self.ram_gb,
            "storage_gb": self.storage_gb,
            "enabled": self.enabled,
        }


def _get_config_path() -> Path:
    """Get path to sega.toml config file."""
    config = get_config()
    config_path = getattr(config.meta, 'config_path', None)
    if config_path:
        return Path(config_path)
    return Path(__file__).parent.parent.parent.parent / "config" / "sega.toml"


def _load_local_hosts() -> Dict[str, LocalHost]:
    """Load local hosts from sega.toml config."""
    hosts: Dict[str, LocalHost] = {}
    
    try:
        if toml_parser is None:
            return hosts
            
        config_path = _get_config_path()
        if config_path.exists():
            with open(config_path, "rb") as f:
                toml_config = toml_parser.load(f)
            local_hosts_section = toml_config.get("local_hosts", {})
            
            for name, host_config in local_hosts_section.items():
                host = LocalHost(
                    name=name,
                    ip=host_config.get("ip", ""),
                    user=host_config.get("user", "ubuntu"),
                    host_type=host_config.get("type", "generic"),
                    ram_gb=host_config.get("ram_gb", 0),
                    storage_gb=host_config.get("storage_gb", 0),
                    ssh_key_path=host_config.get("ssh_key_path"),
                    enabled=host_config.get("enabled", True),
                )
                hosts[name] = host
    except Exception as e:
        print(f"Warning: Could not load local hosts: {e}")
    
    return hosts


LOCAL_HOSTS = _load_local_hosts()


def get_local_host(name: str) -> Optional[LocalHost]:
    """Get local host by name."""
    return LOCAL_HOSTS.get(name)


def get_all_local_hosts() -> List[LocalHost]:
    """Get all enabled local hosts."""
    return [h for h in LOCAL_HOSTS.values() if h.enabled]


def get_host_by_project(project: str) -> Optional[LocalHost]:
    """Find a local host suitable for a project."""
    hosts = get_all_local_hosts()
    if not hosts:
        return None
    return hosts[0]


@dataclass
class EC2Instance:
    """Configuration for a single EC2 instance."""

    name: str
    ip: str
    user: str
    projects: List[str]
    role: str  # healer, surgeon, etc.

    @property
    def ssh_host(self) -> str:
        """Return user@ip format for SSH."""
        return f"{self.user}@{self.ip}"


@dataclass
class DistributionConfig:
    """Configuration for artifact distribution."""

    instance_download_path: str
    instance_download_url: str
    s3_bucket: str
    s3_region: str
    github_org: str


# =============================================================================
# SSH Configuration
# =============================================================================

def _get_ssh_key_path() -> Path:
    """Get SSH key path from config or environment."""
    config = get_config()
    # Try environment first, then instance config
    env_key = os.environ.get("SEGA_SSH_KEY")
    if env_key:
        return Path(env_key).expanduser()

    # Get from first instance config
    names = list(config.instances.keys())
    if names:
        instance = config.get_instance(names[0])
        if instance and instance.ssh_key_path:
            return Path(instance.ssh_key_path).expanduser()

    return Path("~/.ssh/id_rsa").expanduser()


def _get_ssh_user() -> str:
    """Get SSH user from config or environment."""
    env_user = os.environ.get("SEGA_SSH_USER")
    if env_user:
        return env_user

    config = get_config()
    names = list(config.instances.keys())
    if names:
        instance = config.get_instance(names[0])
        if instance and instance.ssh_user:
            return instance.ssh_user

    return "ubuntu"


def _get_ssh_timeout() -> int:
    """Get SSH timeout from environment."""
    return int(os.environ.get("SEGA_SSH_TIMEOUT", "5"))


SSH_KEY_PATH = _get_ssh_key_path()


# =============================================================================
# EC2 Instance Definitions (from sega.toml)
# =============================================================================

def _build_instance_from_config(instance_name: str, role: str = "") -> EC2Instance:
    """Build EC2Instance from sega.toml config."""
    config = get_config()
    instance = config.get_instance(instance_name)

    if not instance:
        return EC2Instance(name=instance_name, ip="", user="ubuntu", projects=[], role=role)

    return EC2Instance(
        name=instance_name,
        ip=instance.ip,
        user=instance.ssh_user or "ubuntu",
        projects=list(instance.projects),
        role=role,
    )


# Build instances from TOML config, in [instances.*] declaration order.
# Ordinal aliases (INSTANCE1..4, "1"/"instance1") map to that order.
def _build_instance_by_ordinal(idx: int) -> EC2Instance:
    """Build the idx-th (1-based) configured instance; empty stub if absent."""
    names = list(get_config().instances.keys())
    if idx <= len(names):
        return _build_instance_from_config(names[idx - 1])
    return EC2Instance(name=f"instance{idx}", ip="", user="ubuntu", projects=[], role="")


INSTANCE1 = _build_instance_by_ordinal(1)
INSTANCE2 = _build_instance_by_ordinal(2)
INSTANCE3 = _build_instance_by_ordinal(3)
INSTANCE4 = _build_instance_by_ordinal(4)

# Instance registry for lookup: ordinal keys plus each instance's config name.
EC2_INSTANCES: Dict[str, EC2Instance] = {}
for _idx, _inst in enumerate((INSTANCE1, INSTANCE2, INSTANCE3, INSTANCE4), start=1):
    EC2_INSTANCES[str(_idx)] = _inst
    EC2_INSTANCES[f"instance{_idx}"] = _inst
    EC2_INSTANCES.setdefault(_inst.name, _inst)

# All configured instances for iteration (however many the config declares).
ALL_INSTANCES: List[EC2Instance] = [
    _build_instance_from_config(_name) for _name in get_config().instances.keys()
] or [INSTANCE1, INSTANCE2, INSTANCE3, INSTANCE4]


# =============================================================================
# Distribution Configuration
# =============================================================================

def get_distribution_config() -> DistributionConfig:
    """Get distribution configuration from sega.toml."""
    config = get_config()

    return DistributionConfig(
        instance_download_path=os.environ.get(
            "SEGA_DISTRIBUTION_PATH",
            "/var/www/downloads"
        ),
        instance_download_url=os.environ.get(
            "SEGA_DISTRIBUTION_URL",
            "https://downloads.example.com"
        ),
        s3_bucket=config.distribution.s3.bucket if config.distribution else "releases",
        s3_region=config.distribution.s3.region if config.distribution else "us-east-2",
        github_org=config.distribution.github_org if config.distribution else "",
    )


# =============================================================================
# Thresholds Configuration
# =============================================================================

def _get_threshold(name: str, default: int) -> int:
    """Get threshold value with environment override."""
    env_key = f"SEGA_{name.upper()}"
    return int(os.environ.get(env_key, default))


THRESHOLDS = {
    "disk_warning": _get_threshold("disk_warning", 75),
    "disk_critical": _get_threshold("disk_critical", 90),
    "cpu_warning": _get_threshold("cpu_warning", 70),
    "cpu_critical": _get_threshold("cpu_critical", 90),
    "memory_warning": _get_threshold("memory_warning", 80),
    "memory_critical": _get_threshold("memory_critical", 95),
}


# =============================================================================
# Helper Functions
# =============================================================================

def get_instance(identifier: str) -> Optional[EC2Instance]:
    """
    Get an EC2 instance by identifier.

    Args:
        identifier: Instance number ("1", "2") or name ("instance1", "instance2")

    Returns:
        EC2Instance or None if not found
    """
    return EC2_INSTANCES.get(identifier)


def get_instance_by_project(project: str) -> Optional[EC2Instance]:
    """
    Find which instance hosts a given project.

    Args:
        project: Project name (e.g., "atlas", "hermes")

    Returns:
        EC2Instance or None if project not found
    """
    for instance in ALL_INSTANCES:
        if project in instance.projects:
            return instance
    return None


def get_ssh_key_path() -> Path:
    """Get the SSH key path, checking for existence."""
    if not SSH_KEY_PATH.exists():
        raise FileNotFoundError(
            f"SSH key not found at {SSH_KEY_PATH}. "
            f"Set SEGA_SSH_KEY environment variable to override."
        )
    return SSH_KEY_PATH


def get_ssh_options() -> List[str]:
    """Get standard SSH options for EC2 connections."""
    timeout = _get_ssh_timeout()
    return [
        "-o", f"ConnectTimeout={timeout}",
        "-o", "StrictHostKeyChecking=no",
        "-o", "LogLevel=ERROR",
        "-o", "BatchMode=yes",
    ]


def build_ssh_command(instance: EC2Instance, command: str) -> List[str]:
    """
    Build a complete SSH command for an instance.

    Args:
        instance: Target EC2Instance
        command: Command to execute remotely

    Returns:
        List of command arguments for subprocess
    """
    ssh_key = get_ssh_key_path()
    return [
        "ssh",
        "-i", str(ssh_key),
        *get_ssh_options(),
        instance.ssh_host,
        command,
    ]


__all__ = [
    "EC2Instance",
    "LocalHost",
    "DistributionConfig",
    "INSTANCE1",
    "INSTANCE2",
    "INSTANCE3",
    "INSTANCE4",
    "EC2_INSTANCES",
    "ALL_INSTANCES",
    "LOCAL_HOSTS",
    "SSH_KEY_PATH",
    "THRESHOLDS",
    "get_instance",
    "get_instance_by_project",
    "get_local_host",
    "get_all_local_hosts",
    "get_host_by_project",
    "get_ssh_key_path",
    "get_ssh_options",
    "build_ssh_command",
    "get_distribution_config",
]
