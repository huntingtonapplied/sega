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
CONFLICT DETECTOR
==============================================================================
File: engine/sega/services/conflict_detector.py
Project: SEGA (Scalable Engineering & Growth Automation)
Copyright: 2025 FLEET
License: Apache-2.0

PURPOSE: Detect deployment conflicts and misconfigurations
         Apply rules to identify issues
         Generate fix recommendations

USAGE:
    from sega.services.conflict_detector import detect_conflicts
    from sega.services.deployment_state import scan_instance_state

    state = scan_instance_state("1")
    conflicts = detect_conflicts(state)

    for conflict in conflicts:
        print(f"{conflict.severity}: {conflict.description}")
        if conflict.auto_fix_available:
            print(f"  Fix: {conflict.fix_description}")
==============================================================================
"""

from dataclasses import dataclass, field
from typing import Callable, Dict, List, Optional

from .deployment_state import InstanceState, ServiceState


# =============================================================================
# Data Structures
# =============================================================================


@dataclass
class Conflict:
    """Detected conflict or misconfiguration"""

    rule_id: str
    severity: str  # ERROR, WARNING, INFO
    project: str
    description: str
    affected_services: List[str] = field(default_factory=list)
    auto_fix_available: bool = False
    fix_description: Optional[str] = None
    fix_commands: List[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        """Convert to dictionary"""
        return {
            "rule_id": self.rule_id,
            "severity": self.severity,
            "project": self.project,
            "description": self.description,
            "affected_services": self.affected_services,
            "auto_fix_available": self.auto_fix_available,
            "fix_description": self.fix_description,
            "fix_commands": self.fix_commands,
        }


@dataclass
class ConflictRule:
    """Rule for detecting conflicts"""

    rule_id: str
    severity: str
    check_function: Callable
    description: str
    auto_fix_available: bool = False

    def check(self, state: InstanceState, expected_config: Optional[dict] = None) -> List[Conflict]:
        """Run the check function"""
        return self.check_function(state, expected_config)


# =============================================================================
# Conflict Detection Rules
# =============================================================================


def check_duplicate_postgres(state: InstanceState, expected_config: Optional[dict] = None) -> List[Conflict]:
    """
    Detect projects with both systemd and Docker postgres

    For docker_isolated mode: This is an ERROR
    For hybrid mode: This is OK if using the correct postgres
    For native_dev mode: Should only have systemd postgres
    """
    conflicts = []

    # Group postgres services by project
    postgres_by_project = {}
    for service in state.services:
        if service.service_type == "database" and service.status == "running":
            if service.project not in postgres_by_project:
                postgres_by_project[service.project] = []
            postgres_by_project[service.project].append(service)

    # Check each project
    for project, postgres_services in postgres_by_project.items():
        if len(postgres_services) > 1:
            methods = {s.method for s in postgres_services}

            if "docker" in methods and "systemd" in methods:
                # Get expected deployment mode
                mode = _get_expected_mode(project, expected_config)

                if mode == "docker_isolated":
                    # ERROR: Should only have Docker postgres
                    conflicts.append(
                        Conflict(
                            rule_id="duplicate_postgres",
                            severity="ERROR",
                            project=project,
                            description=f"Duplicate postgres: Docker container and systemd service both running",
                            affected_services=[s.service_name for s in postgres_services],
                            auto_fix_available=True,
                            fix_description="Stop and disable systemd postgres, use Docker postgres",
                            fix_commands=[
                                f"systemctl stop {s.service_name}" for s in postgres_services if s.method == "systemd"
                            ]
                            + [
                                f"systemctl disable {s.service_name}"
                                for s in postgres_services
                                if s.method == "systemd"
                            ],
                        )
                    )
                elif mode == "native_dev":
                    # ERROR: Should only have systemd postgres
                    conflicts.append(
                        Conflict(
                            rule_id="duplicate_postgres",
                            severity="ERROR",
                            project=project,
                            description=f"Duplicate postgres: Should use systemd only for native_dev mode",
                            affected_services=[s.service_name for s in postgres_services],
                            auto_fix_available=True,
                            fix_description="Stop Docker postgres container, use systemd postgres",
                            fix_commands=[
                                f"docker stop {s.pid_or_container}" for s in postgres_services if s.method == "docker"
                            ],
                        )
                    )
                else:
                    # WARN ING: Hybrid mode - may be intentional
                    conflicts.append(
                        Conflict(
                            rule_id="duplicate_postgres",
                            severity="WARNING",
                            project=project,
                            description=f"Duplicate postgres detected (hybrid mode may be intentional)",
                            affected_services=[s.service_name for s in postgres_services],
                            auto_fix_available=False,
                            fix_description="Verify which postgres is intended for this project",
                        )
                    )

    return conflicts


def check_port_collisions(state: InstanceState, expected_config: Optional[dict] = None) -> List[Conflict]:
    """
    Detect multiple services trying to bind the same port
    """
    conflicts = []

    # Group services by port
    services_by_port = {}
    for service in state.services:
        if service.port and service.status == "running":
            if service.port not in services_by_port:
                services_by_port[service.port] = []
            services_by_port[service.port].append(service)

    # Check for collisions
    for port, services in services_by_port.items():
        if len(services) > 1:
            conflicts.append(
                Conflict(
                    rule_id="port_collision",
                    severity="ERROR",
                    project=services[0].project,
                    description=f"Port {port} collision: {len(services)} services attempting to bind",
                    affected_services=[s.service_name for s in services],
                    auto_fix_available=False,
                    fix_description=f"Stop conflicting services or reassign ports",
                )
            )

    return conflicts


def check_orphaned_containers(state: InstanceState, expected_config: Optional[dict] = None) -> List[Conflict]:
    """
    Detect Docker containers that are stopped/exited while systemd alternative is running
    """
    conflicts = []

    # Find stopped Docker containers
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
            conflicts.append(
                Conflict(
                    rule_id="orphaned_container",
                    severity="WARNING",
                    project=container.project,
                    description=f"Orphaned container: {container.service_name} ({container.status}) while systemd running",
                    affected_services=[container.service_name, matching_systemd[0].service_name],
                    auto_fix_available=True,
                    fix_description=f"Remove orphaned container {container.service_name}",
                    fix_commands=[f"docker rm {container.pid_or_container}"],
                )
            )

    return conflicts


def check_missing_database(state: InstanceState, expected_config: Optional[dict] = None) -> List[Conflict]:
    """
    Detect backends running without a database
    """
    conflicts = []

    # Group services by project
    services_by_project = {}
    for service in state.services:
        if service.project not in services_by_project:
            services_by_project[service.project] = []
        services_by_project[service.project].append(service)

    # Check each project
    for project, services in services_by_project.items():
        # Check if backend is running
        backends = [s for s in services if s.service_type in ["backend", "api"] and s.status == "running"]
        # Check if database exists
        databases = [s for s in services if s.service_type == "database" and s.status == "running"]

        if backends and not databases:
            conflicts.append(
                Conflict(
                    rule_id="missing_database",
                    severity="ERROR",
                    project=project,
                    description=f"Backend running without database",
                    affected_services=[s.service_name for s in backends],
                    auto_fix_available=False,
                    fix_description="Start database service or update backend configuration",
                )
            )

    return conflicts


def check_unhealthy_services(state: InstanceState, expected_config: Optional[dict] = None) -> List[Conflict]:
    """
    Detect services that are unhealthy or crash-looping
    """
    conflicts = []

    unhealthy_services = [s for s in state.services if s.status in ["unhealthy", "restarting"]]

    # Group by project
    unhealthy_by_project = {}
    for service in unhealthy_services:
        if service.project not in unhealthy_by_project:
            unhealthy_by_project[service.project] = []
        unhealthy_by_project[service.project].append(service)

    for project, services in unhealthy_by_project.items():
        conflicts.append(
            Conflict(
                rule_id="unhealthy_services",
                severity="WARNING",
                project=project,
                description=f"{len(services)} unhealthy/restarting services detected",
                affected_services=[s.service_name for s in services],
                auto_fix_available=False,
                fix_description="Check logs and fix underlying issues",
            )
        )

    return conflicts


def check_mode_mismatch(state: InstanceState, expected_config: Optional[dict] = None) -> List[Conflict]:
    """
    Detect services running with wrong method for their deployment mode

    Example: docker_isolated mode but using systemd postgres
    """
    if not expected_config:
        return []

    conflicts = []

    # Get expected projects for this instance
    expected_projects = [
        p
        for p in expected_config.get("projects", [])
        if p.get("instance") == state.instance_name
        or (isinstance(p.get("instance"), str) and "fleet-prod-01" in p.get("instance"))
    ]

    for expected_project in expected_projects:
        project_name = expected_project["slug"]
        expected_mode = expected_project["deployment_mode"]

        # Get actual services for this project
        actual_services = [s for s in state.services if s.project == project_name and s.status == "running"]

        if expected_mode == "docker_isolated":
            # All services should be Docker
            non_docker = [s for s in actual_services if s.method != "docker"]
            if non_docker:
                conflicts.append(
                    Conflict(
                        rule_id="mode_mismatch",
                        severity="ERROR",
                        project=project_name,
                        description=f"Mode mismatch: docker_isolated expects all Docker, found {len(non_docker)} non-Docker services",
                        affected_services=[s.service_name for s in non_docker],
                        auto_fix_available=False,
                        fix_description="Migrate non-Docker services to Docker containers",
                    )
                )

        elif expected_mode == "native_dev":
            # Should have native or systemd services, not Docker
            docker_services = [s for s in actual_services if s.method == "docker"]
            if docker_services:
                conflicts.append(
                    Conflict(
                        rule_id="mode_mismatch",
                        severity="WARNING",
                        project=project_name,
                        description=f"Mode mismatch: native_dev has {len(docker_services)} Docker services",
                        affected_services=[s.service_name for s in docker_services],
                        auto_fix_available=False,
                        fix_description="Consider migrating to native processes for faster development iteration",
                    )
                )

    return conflicts


# =============================================================================
# Rule Registry
# =============================================================================

CONFLICT_RULES: Dict[str, ConflictRule] = {
    "duplicate_postgres": ConflictRule(
        rule_id="duplicate_postgres",
        severity="ERROR",
        check_function=check_duplicate_postgres,
        description="Project has both systemd and Docker postgres running",
        auto_fix_available=True,
    ),
    "port_collision": ConflictRule(
        rule_id="port_collision",
        severity="ERROR",
        check_function=check_port_collisions,
        description="Multiple services binding the same port",
        auto_fix_available=False,
    ),
    "orphaned_container": ConflictRule(
        rule_id="orphaned_container",
        severity="WARNING",
        check_function=check_orphaned_containers,
        description="Stopped Docker container while systemd service running",
        auto_fix_available=True,
    ),
    "missing_database": ConflictRule(
        rule_id="missing_database",
        severity="ERROR",
        check_function=check_missing_database,
        description="Backend running without database",
        auto_fix_available=False,
    ),
    "unhealthy_services": ConflictRule(
        rule_id="unhealthy_services",
        severity="WARNING",
        check_function=check_unhealthy_services,
        description="Services that are unhealthy or crash-looping",
        auto_fix_available=False,
    ),
    "mode_mismatch": ConflictRule(
        rule_id="mode_mismatch",
        severity="ERROR",
        check_function=check_mode_mismatch,
        description="Service deployment method does not match expected mode",
        auto_fix_available=False,
    ),
}


# =============================================================================
# Main Detection Function
# =============================================================================


def detect_conflicts(
    state: InstanceState, expected_config: Optional[dict] = None, rules_to_run: Optional[List[str]] = None
) -> List[Conflict]:
    """
    Run conflict detection rules on instance state

    Args:
        state: Scanned instance state
        expected_config: Expected deployment configuration (optional)
        rules_to_run: List of rule IDs to run (default: all rules)

    Returns:
        List of detected conflicts

    Example:
        conflicts = detect_conflicts(state)
        for conflict in conflicts:
            if conflict.severity == 'ERROR':
                print(f"ERROR: {conflict.description}")
    """
    all_conflicts = []

    # Determine which rules to run
    if rules_to_run is None:
        rules_to_run = list(CONFLICT_RULES.keys())

    # Run each rule
    for rule_id in rules_to_run:
        if rule_id not in CONFLICT_RULES:
            continue

        rule = CONFLICT_RULES[rule_id]
        conflicts = rule.check(state, expected_config)
        all_conflicts.extend(conflicts)

    return all_conflicts


def get_conflicts_by_severity(conflicts: List[Conflict]) -> Dict[str, List[Conflict]]:
    """
    Group conflicts by severity

    Returns:
        Dict of {severity: [conflicts]}
    """
    by_severity = {"ERROR": [], "WARNING": [], "INFO": []}

    for conflict in conflicts:
        if conflict.severity in by_severity:
            by_severity[conflict.severity].append(conflict)

    return by_severity


def get_conflicts_by_project(conflicts: List[Conflict]) -> Dict[str, List[Conflict]]:
    """
    Group conflicts by project

    Returns:
        Dict of {project: [conflicts]}
    """
    by_project = {}

    for conflict in conflicts:
        if conflict.project not in by_project:
            by_project[conflict.project] = []
        by_project[conflict.project].append(conflict)

    return by_project


# =============================================================================
# Utility Functions
# =============================================================================


def _get_expected_mode(project: str, expected_config: Optional[dict]) -> Optional[str]:
    """Get expected deployment mode for a project"""
    if not expected_config:
        return None

    for proj in expected_config.get("projects", []):
        if proj.get("slug") == project:
            return proj.get("deployment_mode")

    return None


__all__ = [
    "Conflict",
    "ConflictRule",
    "CONFLICT_RULES",
    "detect_conflicts",
    "get_conflicts_by_severity",
    "get_conflicts_by_project",
]
