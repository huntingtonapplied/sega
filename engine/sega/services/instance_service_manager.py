#!/usr/bin/env python3
# Copyright 2025 SEGA

"""
INSTANCE SERVICE MANAGER
==============================================================================
File: engine/sega/services/instance_service_manager.py
Project: SEGA (Scalable Engineering & Growth Automation)
Copyright: 2022-2025 FLEET
License: Apache-2.0
SEGA MODULE: Services/InstanceServiceManager
COMPONENT: EC2 Instance systemd Service Orchestration
PURPOSE: Generate, install, and manage systemd service units for all
         frontend and backend processes running on a given EC2 instance.

Supports:
  - Frontend: Next.js via `next start`
  - Backend: FastAPI via `uvicorn`
  - IDE: VS Code fork via `node ./scripts/code-web.js`

Usage (programmatic):
    mgr = InstanceServiceManager(instance_id="1")
    mgr.install_all()          # SSH to instance, write + enable all units
    mgr.status_all()           # Show status of every unit
    mgr.restart_all()          # Restart every unit (e.g. after redeploy)

Usage (CLI):
    sega services install --instance 1
    sega services status  --instance 1
    sega services restart --instance 1 --project atlas
==============================================================================
"""

import json
import subprocess
import tempfile
from pathlib import Path
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple

from ..infrastructure.ec2_config import get_instance, build_ssh_command


# ---------------------------------------------------------------------------
# Data structures
# ---------------------------------------------------------------------------


@dataclass
class ServiceDefinition:
    """Describes a single systemd unit to create on the remote host."""

    unit_name: str  # e.g. fleet-atlas-landing-frontend
    project: str  # e.g. atlas
    service_type: str  # "frontend" | "backend" | "ide"
    port: int
    app_name: str  # e.g. landing_app | product_app | backend | ide
    # frontend/ide-specific
    app_path: str = ""  # relative to project root, e.g. frontend/landing_app or ide
    # backend-specific
    uvicorn_module: str = ""  # e.g. app.main


@dataclass
class InstallResult:
    success: bool
    unit_name: str
    message: str
    error: Optional[str] = None


@dataclass
class InstanceServiceReport:
    instance_id: str
    results: List[InstallResult] = field(default_factory=list)

    @property
    def success_count(self) -> int:
        return sum(1 for r in self.results if r.success)

    @property
    def failure_count(self) -> int:
        return sum(1 for r in self.results if not r.success)


# ---------------------------------------------------------------------------
# Template rendering
# ---------------------------------------------------------------------------

_TEMPLATE_DIR = Path(__file__).parent.parent.parent.parent / "templates" / "systemd"
# Fallback for installed package
_TEMPLATE_DIR_FALLBACK = Path.home() / "fleet" / "_internal" / "templates" / "systemd"


def _load_template(name: str) -> str:
    for base in (_TEMPLATE_DIR, _TEMPLATE_DIR_FALLBACK):
        path = base / name
        if path.exists():
            with open(path) as fh:
                return fh.read()
    raise FileNotFoundError(f"systemd template '{name}' not found in {_TEMPLATE_DIR}")


def _render_frontend(svc: ServiceDefinition, fleet_root: str) -> str:
    tmpl = _load_template("fleet-frontend.service.template")
    return (
        tmpl.replace("{{PROJECT_NAME}}", svc.project)
        .replace("{{APP_NAME}}", svc.app_name)
        .replace("{{PORT}}", str(svc.port))
        .replace("{{APP_PATH}}", svc.app_path)
        .replace("{{FLEET_ROOT}}", fleet_root)
    )


def _render_backend(svc: ServiceDefinition, fleet_root: str) -> str:
    tmpl = _load_template("fleet-backend.service.template")
    return (
        tmpl.replace("{{PROJECT_NAME}}", svc.project)
        .replace("{{PORT}}", str(svc.port))
        .replace("{{MODULE}}", svc.uvicorn_module or "app.main")
        .replace("{{FLEET_ROOT}}", fleet_root)
    )


def _render_ide(svc: ServiceDefinition, fleet_root: str) -> str:
    tmpl = _load_template("fleet-ide.service.template")
    return (
        tmpl.replace("{{PROJECT_NAME}}", svc.project)
        .replace("{{APP_NAME}}", svc.app_name)
        .replace("{{PORT}}", str(svc.port))
        .replace("{{APP_PATH}}", svc.app_path)
        .replace("{{FLEET_ROOT}}", fleet_root)
    )


# ---------------------------------------------------------------------------
# SSH helpers
# ---------------------------------------------------------------------------


def _resolve_instance(instance_id: str):
    """Resolve instance ID to EC2Instance, raising ValueError if unknown."""
    instance = get_instance(instance_id)
    if instance is None:
        raise ValueError(f"Unknown instance identifier: '{instance_id}'")
    return instance


def _ssh_run(instance_id: str, cmd: str, check: bool = True) -> subprocess.CompletedProcess:
    """Run a shell command on the remote instance via SSH."""
    instance = _resolve_instance(instance_id)
    ssh_cmd = build_ssh_command(instance, cmd)
    return subprocess.run(ssh_cmd, capture_output=True, text=True, check=check)


def _ssh_write_file(instance_id: str, remote_path: str, content: str) -> None:
    """Write content to a remote file via SSH + sudo tee."""
    instance = _resolve_instance(instance_id)
    # Stream content through stdin so we avoid shell escaping issues
    tee_cmd = f"sudo tee {remote_path} > /dev/null"
    ssh_cmd = build_ssh_command(instance, tee_cmd)
    subprocess.run(ssh_cmd, input=content, capture_output=True, text=True, check=True)


# ---------------------------------------------------------------------------
# Service definitions for each instance
# ---------------------------------------------------------------------------

# Instance 1 project list mirrors config/instance1-frontend-builds.json
_INSTANCE1_CONFIG_PATH = Path(__file__).parent.parent.parent.parent.parent / "config" / "instance1-frontend-builds.json"

# Backend uvicorn module convention: <project>.main  (override per-project if needed)
_BACKEND_MODULE_OVERRIDES: Dict[str, str] = {
    # e.g. "hermes": "hermes.server:app"
}


def _default_backend_module(project: str) -> str:
    return _BACKEND_MODULE_OVERRIDES.get(project, f"{project}.main:app")


def build_instance1_definitions(fleet_root: str = "/home/ubuntu/fleet") -> List[ServiceDefinition]:
    """
    Build ServiceDefinition list for Instance 1 from the canonical
    config/instance1-frontend-builds.json plus derived backend ports.
    Apps with service_type="ide" generate IDE units (VS Code fork) instead
    of standard Next.js frontend units.
    """
    defs: List[ServiceDefinition] = []

    # Load frontend manifest
    if not _INSTANCE1_CONFIG_PATH.exists():
        raise FileNotFoundError(f"Instance 1 build config not found: {_INSTANCE1_CONFIG_PATH}")
    with open(_INSTANCE1_CONFIG_PATH) as fh:
        manifest = json.load(fh)

    for proj in manifest["projects"]:
        name = proj["name"]
        proj_id = proj["id"]

        # --- Frontend / IDE services (only build=true apps) ---
        for app in proj["apps"]:
            if not app.get("build", False):
                continue
            app_name = app["name"]
            svc_type = app.get("service_type", "frontend")  # "frontend" | "ide"
            safe_app = app_name.replace("_", "-")
            unit = f"fleet-{name.replace('_', '-')}-{safe_app}-{svc_type}"
            defs.append(
                ServiceDefinition(
                    unit_name=unit,
                    project=name,
                    service_type=svc_type,
                    port=app["port"],
                    app_name=app_name,
                    app_path=app["path"],
                )
            )

        # --- Backend service (FastAPI, port = 8000 + proj_id) ---
        backend_port = 8000 + proj_id
        unit = f"fleet-{name.replace('_', '-')}-backend"
        defs.append(
            ServiceDefinition(
                unit_name=unit,
                project=name,
                service_type="backend",
                port=backend_port,
                app_name="backend",
                uvicorn_module=_default_backend_module(name),
            )
        )

    return defs


_INSTANCE_BUILDERS = {
    "1": build_instance1_definitions,
    "instance1": build_instance1_definitions,
    "fleet-prod-01": build_instance1_definitions,
}


# ---------------------------------------------------------------------------
# Manager
# ---------------------------------------------------------------------------


class InstanceServiceManager:
    """
    Manages systemd service units for all frontends and backends on an
    EC2 instance.  Communicates exclusively via SSH.
    """

    SYSTEMD_DIR = "/etc/systemd/system"

    def __init__(self, instance_id: str, fleet_root: str = "/home/ubuntu/fleet"):
        self.instance_id = instance_id
        self.fleet_root = fleet_root
        builder = _INSTANCE_BUILDERS.get(instance_id)
        if builder is None:
            raise ValueError(
                f"No service definitions for instance '{instance_id}'. Available: {list(_INSTANCE_BUILDERS.keys())}"
            )
        self.definitions: List[ServiceDefinition] = builder(fleet_root)

    def _filter(self, project: Optional[str], service_type: Optional[str]) -> List[ServiceDefinition]:
        defs = self.definitions
        if project:
            defs = [d for d in defs if d.project == project]
        if service_type:
            defs = [d for d in defs if d.service_type == service_type]
        return defs

    # ------------------------------------------------------------------
    # Install
    # ------------------------------------------------------------------

    def install(
        self,
        project: Optional[str] = None,
        service_type: Optional[str] = None,
        start: bool = True,
    ) -> InstanceServiceReport:
        """
        Write unit files, daemon-reload, enable, and optionally start services.
        Filters by project and/or service_type when provided.
        """
        report = InstanceServiceReport(instance_id=self.instance_id)
        targets = self._filter(project, service_type)

        if not targets:
            report.results.append(
                InstallResult(
                    success=False,
                    unit_name="(none)",
                    message="No matching service definitions found",
                )
            )
            return report

        for svc in targets:
            result = self._install_one(svc, start=start)
            report.results.append(result)

        # Single daemon-reload after all unit files are written
        try:
            _ssh_run(self.instance_id, "sudo systemctl daemon-reload")
        except subprocess.CalledProcessError as exc:
            report.results.append(
                InstallResult(
                    success=False,
                    unit_name="systemd-daemon-reload",
                    message="daemon-reload failed",
                    error=exc.stderr,
                )
            )

        return report

    def _install_one(self, svc: ServiceDefinition, start: bool) -> InstallResult:
        unit_path = f"{self.SYSTEMD_DIR}/{svc.unit_name}.service"
        try:
            # Render template
            if svc.service_type == "frontend":
                content = _render_frontend(svc, self.fleet_root)
            elif svc.service_type == "ide":
                content = _render_ide(svc, self.fleet_root)
            else:
                content = _render_backend(svc, self.fleet_root)

            # Write to remote
            _ssh_write_file(self.instance_id, unit_path, content)

            # Enable
            _ssh_run(self.instance_id, f"sudo systemctl enable {svc.unit_name}")

            # Start if requested
            if start:
                _ssh_run(self.instance_id, f"sudo systemctl start {svc.unit_name}")

            return InstallResult(
                success=True,
                unit_name=svc.unit_name,
                message=f"installed{' and started' if start else ''}",
            )

        except FileNotFoundError as exc:
            return InstallResult(
                success=False,
                unit_name=svc.unit_name,
                message="template not found",
                error=str(exc),
            )
        except subprocess.CalledProcessError as exc:
            return InstallResult(
                success=False,
                unit_name=svc.unit_name,
                message="remote command failed",
                error=exc.stderr,
            )
        except Exception as exc:
            return InstallResult(
                success=False,
                unit_name=svc.unit_name,
                message="unexpected error",
                error=str(exc),
            )

    # ------------------------------------------------------------------
    # Control (start / stop / restart / enable / disable)
    # ------------------------------------------------------------------

    def control(
        self,
        action: str,
        project: Optional[str] = None,
        service_type: Optional[str] = None,
    ) -> InstanceServiceReport:
        """Run a systemctl action on matching services."""
        if action not in {"start", "stop", "restart", "enable", "disable"}:
            raise ValueError(f"Invalid action: {action}")

        report = InstanceServiceReport(instance_id=self.instance_id)
        targets = self._filter(project, service_type)

        for svc in targets:
            try:
                _ssh_run(self.instance_id, f"sudo systemctl {action} {svc.unit_name}")
                report.results.append(
                    InstallResult(
                        success=True,
                        unit_name=svc.unit_name,
                        message=f"{action}ed",
                    )
                )
            except subprocess.CalledProcessError as exc:
                report.results.append(
                    InstallResult(
                        success=False,
                        unit_name=svc.unit_name,
                        message=f"{action} failed",
                        error=exc.stderr,
                    )
                )

        return report

    # ------------------------------------------------------------------
    # Status
    # ------------------------------------------------------------------

    def status(
        self,
        project: Optional[str] = None,
        service_type: Optional[str] = None,
    ) -> List[Tuple[str, str]]:
        """
        Return a list of (unit_name, active_state) tuples for all matching
        services, e.g. ("fleet-atlas-landing-frontend", "active").
        """
        targets = self._filter(project, service_type)
        results: List[Tuple[str, str]] = []

        for svc in targets:
            try:
                proc = _ssh_run(
                    self.instance_id,
                    f"systemctl is-active {svc.unit_name}",
                    check=False,
                )
                state = proc.stdout.strip() or "unknown"
            except Exception:
                state = "unknown"
            results.append((svc.unit_name, state))

        return results

    # ------------------------------------------------------------------
    # Convenience wrappers
    # ------------------------------------------------------------------

    def install_all(self, start: bool = True) -> InstanceServiceReport:
        return self.install(start=start)

    def restart_all(self) -> InstanceServiceReport:
        return self.control("restart")

    def status_all(self) -> List[Tuple[str, str]]:
        return self.status()
