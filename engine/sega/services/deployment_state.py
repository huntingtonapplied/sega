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
DEPLOYMENT STATE SCANNER
==============================================================================
File: engine/sega/services/deployment_state.py
Project: SEGA (Scalable Engineering & Growth Automation)
Copyright: 2025 FLEET
License: Apache-2.0

PURPOSE: Scan EC2 instances to detect actual deployment state
         Compare against expected configuration
         Detect conflicts and mismatches

USAGE:
    from sega.services.deployment_state import scan_instance_state

    state = scan_instance_state("1")
    print(f"Instance: {state.instance_id}")
    print(f"Services running: {len(state.services)}")
    print(f"Conflicts detected: {len(state.conflicts)}")
==============================================================================
"""

import json
import re
import subprocess
from dataclasses import dataclass, field, asdict
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from ..infrastructure.ec2_config import get_instance, build_ssh_command, EC2Instance


# =============================================================================
# Data Structures
# =============================================================================


@dataclass
class ServiceState:
    """State of a single service (container, systemd unit, or native process)"""

    project: str
    service_type: str  # frontend, backend, database, redis, ide, worker, forwarder
    service_name: str  # e.g. "atlas-api", "postgresql@16-main", "next dev"
    method: str  # docker, systemd, native, none
    port: Optional[int] = None
    status: str = "unknown"  # running, stopped, unhealthy, missing, restarting
    pid_or_container: Optional[str] = None
    details: Dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        """Convert to dictionary"""
        return asdict(self)


@dataclass
class InstanceState:
    """Complete deployment state for an EC2 instance"""

    instance_id: str
    instance_name: str
    ip: str
    timestamp: str
    services: List[ServiceState] = field(default_factory=list)
    conflicts: List[str] = field(default_factory=list)
    orphans: List[str] = field(default_factory=list)
    port_bindings: Dict[int, str] = field(default_factory=dict)

    def to_dict(self) -> dict:
        """Convert to dictionary"""
        return {
            "instance_id": self.instance_id,
            "instance_name": self.instance_name,
            "ip": self.ip,
            "timestamp": self.timestamp,
            "services": [s.to_dict() for s in self.services],
            "conflicts": self.conflicts,
            "orphans": self.orphans,
            "port_bindings": {str(k): v for k, v in self.port_bindings.items()},
            "summary": {
                "total_services": len(self.services),
                "running": len([s for s in self.services if s.status == "running"]),
                "unhealthy": len([s for s in self.services if s.status in ["unhealthy", "restarting"]]),
                "stopped": len([s for s in self.services if s.status == "stopped"]),
                "conflicts_count": len(self.conflicts),
                "orphans_count": len(self.orphans),
            },
        }


# =============================================================================
# SSH Execution Helpers
# =============================================================================


def _run_ssh_command(instance: EC2Instance, command: str) -> Tuple[str, int]:
    """
    Execute SSH command on instance and return (output, returncode)
    """
    ssh_cmd = build_ssh_command(instance, command)
    try:
        result = subprocess.run(ssh_cmd, capture_output=True, text=True, timeout=30)
        return result.stdout, result.returncode
    except subprocess.TimeoutExpired:
        return "", -1
    except Exception as e:
        return f"Error: {e}", -1


# =============================================================================
# Service Scanners
# =============================================================================


def _scan_docker_containers(instance: EC2Instance) -> List[ServiceState]:
    """
    Scan Docker containers on instance
    Returns list of ServiceState objects
    """
    services = []

    # Get all containers (running and stopped)
    cmd = "docker ps -a --format '{{.Names}}|{{.Image}}|{{.Status}}|{{.Ports}}'"
    output, returncode = _run_ssh_command(instance, cmd)

    if returncode != 0 or not output.strip():
        return services

    for line in output.strip().split("\n"):
        if not line:
            continue

        parts = line.split("|")
        if len(parts) < 3:
            continue

        name = parts[0]
        image = parts[1]
        status_str = parts[2]
        ports_str = parts[3] if len(parts) > 3 else ""

        # Parse project name from container name
        # Format: {project}-{service} or {project}_{service}
        project = name.split("-")[0].split("_")[0]

        # Determine service type
        service_type = _classify_docker_service(name, image)

        # Determine status
        status = _parse_docker_status(status_str)

        # Extract port
        port = _extract_port_from_docker(ports_str)

        services.append(
            ServiceState(
                project=project,
                service_type=service_type,
                service_name=name,
                method="docker",
                port=port,
                status=status,
                pid_or_container=name,
                details={"image": image, "raw_status": status_str, "ports": ports_str},
            )
        )

    return services


def _classify_docker_service(name: str, image: str) -> str:
    """Classify Docker container service type"""
    name_lower = name.lower()

    if "landing" in name_lower or "product" in name_lower:
        return "frontend"
    elif "ide" in name_lower:
        return "ide"
    elif "worker" in name_lower:
        return "worker"
    elif "forwarder" in name_lower:
        return "forwarder"
    elif "api" in name_lower or "backend" in name_lower:
        return "backend"
    elif "postgres" in image.lower() or "timescale" in image.lower() or "db" in name_lower:
        return "database"
    elif "redis" in image.lower():
        return "redis"
    else:
        return "other"


def _parse_docker_status(status_str: str) -> str:
    """Parse Docker status string into normalized status"""
    status_lower = status_str.lower()

    if "up" in status_lower and "healthy" in status_lower:
        return "running"
    elif "up" in status_lower:
        return "running"
    elif "restarting" in status_lower:
        return "restarting"
    elif "exited" in status_lower:
        return "stopped"
    elif "unhealthy" in status_lower:
        return "unhealthy"
    else:
        return "unknown"


def _extract_port_from_docker(ports_str: str) -> Optional[int]:
    """Extract primary port from Docker ports string"""
    if not ports_str:
        return None

    # Format: "0.0.0.0:3009->3009/tcp" or "0.0.0.0:3009->3009/tcp, [::]:3009->3009/tcp"
    match = re.search(r"0\.0\.0\.0:(\d+)->", ports_str)
    if match:
        return int(match.group(1))

    return None


def _scan_systemd_services(instance: EC2Instance) -> List[ServiceState]:
    """
    Scan systemd services on instance
    Focus on PostgreSQL and other FLEET-related services
    """
    services = []

    # Scan PostgreSQL services
    cmd = "systemctl list-units 'postgresql@*' --no-pager --no-legend --all"
    output, returncode = _run_ssh_command(instance, cmd)

    if returncode == 0 and output.strip():
        for line in output.strip().split("\n"):
            if not line:
                continue

            # Format: "  postgresql@16-boltzmann_5010.service  loaded active running ..."
            parts = line.split()
            if len(parts) < 4:
                continue

            unit_name = parts[0]
            load_state = parts[1]
            active_state = parts[2]
            sub_state = parts[3]

            # Parse project and port from unit name
            # Format: postgresql@16-{project}_{port}.service
            match = re.search(r"postgresql@\d+-([^_]+)_(\d+)\.service", unit_name)
            if match:
                project = match.group(1)
                port = int(match.group(2))
            else:
                # Format: postgresql@16-main.service
                project = "shared"
                port = None
                if "main" in unit_name:
                    port = 5009  # Default main postgres port

            status = "running" if active_state == "active" and sub_state == "running" else "stopped"

            services.append(
                ServiceState(
                    project=project,
                    service_type="database",
                    service_name=unit_name,
                    method="systemd",
                    port=port,
                    status=status,
                    details={"load_state": load_state, "active_state": active_state, "sub_state": sub_state},
                )
            )

    # Scan Redis systemd service
    cmd = "systemctl list-units 'redis*' --no-pager --no-legend --all"
    output, returncode = _run_ssh_command(instance, cmd)

    if returncode == 0 and output.strip():
        for line in output.strip().split("\n"):
            if not line or "redis-server" not in line:
                continue

            parts = line.split()
            if len(parts) < 4:
                continue

            unit_name = parts[0]
            active_state = parts[2]
            sub_state = parts[3]

            status = "running" if active_state == "active" and sub_state == "running" else "stopped"

            services.append(
                ServiceState(
                    project="shared",
                    service_type="redis",
                    service_name=unit_name,
                    method="systemd",
                    port=6379,  # Default Redis port
                    status=status,
                    details={"active_state": active_state, "sub_state": sub_state},
                )
            )

    return services


def _scan_native_processes(instance: EC2Instance) -> List[ServiceState]:
    """
    Scan native processes (Next.js dev servers, etc.)
    """
    services = []

    # Scan for Next.js dev servers
    cmd = "ps aux | grep -E 'next dev|next start' | grep -v grep"
    output, returncode = _run_ssh_command(instance, cmd)

    if returncode == 0 and output.strip():
        for line in output.strip().split("\n"):
            if not line:
                continue

            # Extract port from command line
            # Format: "next dev -p 4023" or "next start -p 4023"
            port_match = re.search(r"-p\s+(\d+)", line)
            port = int(port_match.group(1)) if port_match else None

            # Extract PID
            parts = line.split()
            pid = parts[1] if len(parts) > 1 else None

            # Try to determine project from working directory or command
            project = "unknown"
            if "/fleet/" in line:
                project_match = re.search(r"/fleet/([^/\s]+)", line)
                if project_match:
                    project = project_match.group(1)

            service_type = "frontend" if "next" in line else "other"

            services.append(
                ServiceState(
                    project=project,
                    service_type=service_type,
                    service_name=f"next dev (port {port})" if port else "next dev",
                    method="native",
                    port=port,
                    status="running",
                    pid_or_container=pid,
                    details={
                        "command": line[:200]  # Truncate long commands
                    },
                )
            )

    return services


def _scan_port_bindings(instance: EC2Instance) -> Dict[int, str]:
    """
    Scan all port bindings to detect conflicts
    Returns dict of {port: service_name}
    """
    port_bindings = {}

    cmd = "sudo netstat -tlnp 2>/dev/null | grep LISTEN"
    output, returncode = _run_ssh_command(instance, cmd)

    if returncode != 0 or not output.strip():
        return port_bindings

    for line in output.strip().split("\n"):
        if not line:
            continue

        # Format: "tcp   0   0 0.0.0.0:3009   0.0.0.0:*   LISTEN   1234/docker-proxy"
        parts = line.split()
        if len(parts) < 7:
            continue

        # Extract port from "0.0.0.0:PORT" or ":::PORT"
        addr_port = parts[3]
        port_match = re.search(r":(\d+)$", addr_port)
        if not port_match:
            continue

        port = int(port_match.group(1))
        service_name = parts[6] if len(parts) > 6 else "unknown"

        port_bindings[port] = service_name

    return port_bindings


# =============================================================================
# Main Scanner Function
# =============================================================================


def scan_instance_state(instance_id: str) -> InstanceState:
    """
    Scan complete deployment state for an EC2 instance

    Args:
        instance_id: Instance identifier ("1", "instance1", "fleet-prod-01")

    Returns:
        InstanceState object with complete deployment information

    Example:
        state = scan_instance_state("1")
        print(f"Instance: {state.instance_name}")
        for service in state.services:
            print(f"  {service.project}/{service.service_type}: {service.status}")
    """
    # Get instance configuration
    instance = get_instance(instance_id)
    if not instance:
        raise ValueError(f"Instance not found: {instance_id}")

    # Create state object
    state = InstanceState(
        instance_id=instance_id,
        instance_name=instance.name,
        ip=instance.ip,
        timestamp=datetime.utcnow().isoformat() + "Z",
    )

    # Scan all service types
    docker_services = _scan_docker_containers(instance)
    systemd_services = _scan_systemd_services(instance)
    native_services = _scan_native_processes(instance)

    # Combine all services
    state.services.extend(docker_services)
    state.services.extend(systemd_services)
    state.services.extend(native_services)

    # Scan port bindings
    state.port_bindings = _scan_port_bindings(instance)

    # Detect basic conflicts (detailed conflict detection in conflict_detector.py)
    state.conflicts = _detect_basic_conflicts(state)

    # Detect orphaned containers
    state.orphans = _detect_orphans(state)

    return state


def _detect_basic_conflicts(state: InstanceState) -> List[str]:
    """Detect basic conflicts (detailed detection in conflict_detector.py)"""
    conflicts = []

    # Check for duplicate postgres
    postgres_services = [s for s in state.services if s.service_type == "database"]
    projects_with_postgres = {}

    for service in postgres_services:
        if service.project not in projects_with_postgres:
            projects_with_postgres[service.project] = []
        projects_with_postgres[service.project].append(service)

    for project, services in projects_with_postgres.items():
        if len(services) > 1:
            methods = [s.method for s in services]
            if "docker" in methods and "systemd" in methods:
                conflicts.append(f"{project}: Duplicate postgres detected (Docker + systemd)")

    # Check for port collisions
    port_usage = {}
    for service in state.services:
        if service.port and service.status == "running":
            if service.port in port_usage:
                conflicts.append(
                    f"Port {service.port}: Collision between {port_usage[service.port]} and {service.service_name}"
                )
            else:
                port_usage[service.port] = service.service_name

    return conflicts


def _detect_orphans(state: InstanceState) -> List[str]:
    """Detect orphaned containers"""
    orphans = []

    # Find Docker containers that are stopped/exited
    stopped_containers = [s for s in state.services if s.method == "docker" and s.status in ["stopped", "exited"]]

    for container in stopped_containers:
        # Check if there's a systemd service running for the same project/service_type
        matching_systemd = [
            s
            for s in state.services
            if s.method == "systemd"
            and s.project == container.project
            and s.service_type == container.service_type
            and s.status == "running"
        ]

        if matching_systemd:
            orphans.append(
                f"{container.service_name} (Docker {container.status}) - "
                f"systemd {matching_systemd[0].service_name} running instead"
            )

    return orphans


# =============================================================================
# Utility Functions
# =============================================================================


def load_deployment_config(config_path: Optional[Path] = None) -> dict:
    """
    Load deployment configuration from deployment-modes-mapping.json

    Args:
        config_path: Optional path to config file

    Returns:
        Dictionary with deployment configuration
    """
    if config_path is None:
        # Default path
        config_path = Path(__file__).parent.parent.parent.parent / "config" / "deployment-modes-mapping.json"

    if not config_path.exists():
        return {}

    with open(config_path) as f:
        return json.load(f)


def compare_to_expected(actual_state: InstanceState, expected_config: dict) -> Dict[str, List[str]]:
    """
    Compare actual state to expected configuration

    Args:
        actual_state: Scanned instance state
        expected_config: Expected deployment configuration

    Returns:
        Dictionary of {project: [list of mismatches]}
    """
    mismatches = {}

    # Get expected projects for this instance
    expected_projects = [
        p for p in expected_config.get("projects", []) if p.get("instance") == actual_state.instance_name
    ]

    for expected_project in expected_projects:
        project_name = expected_project["slug"]
        project_mismatches = []

        # Get actual services for this project
        actual_services = [s for s in actual_state.services if s.project == project_name]

        # Check each expected service
        expected_services = expected_project.get("services", {})
        for service_type, expected_spec in expected_services.items():
            expected_method = expected_spec.get("method")

            # Find matching actual service
            matching_actual = [s for s in actual_services if s.service_type == service_type]

            if not matching_actual and expected_method not in ["none", "planned"]:
                project_mismatches.append(f"{service_type}: Missing (expected {expected_method})")
            elif matching_actual:
                actual = matching_actual[0]
                if actual.method != expected_method:
                    project_mismatches.append(
                        f"{service_type}: Method mismatch (expected {expected_method}, actual {actual.method})"
                    )
                if actual.status not in ["running", "healthy"]:
                    project_mismatches.append(f"{service_type}: Not running (status: {actual.status})")

        if project_mismatches:
            mismatches[project_name] = project_mismatches

    return mismatches


__all__ = [
    "ServiceState",
    "InstanceState",
    "scan_instance_state",
    "load_deployment_config",
    "compare_to_expected",
]
