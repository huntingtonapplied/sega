#!/usr/bin/env python3
# Copyright 2025 SEGA

"""
SYSTEMD SERVICE MANAGEMENT
==============================================================================
File: src/sega/services/systemd_service.py
Project: SEGA (Scalable Engineering & Growth Automation)
Copyright: 2022-2025 FLEET
License: Apache-2.0
SEGA MODULE: Services/SystemD
COMPONENT: SystemD Service Management Service
PURPOSE: Manage systemd services for FLEET engines and other services
==============================================================================
"""

import subprocess
import tempfile
from pathlib import Path
from typing import Dict, List, Optional, Any
from dataclasses import dataclass


@dataclass
class ServiceResult:
    success: bool
    status: str
    error: Optional[str] = None
    service_file: Optional[str] = None


class SystemdService:
    """Service for managing systemd services."""

    def __init__(self, template_dir: Optional[Path] = None):
        self.template_dir = template_dir or self._find_template_dir()

    def _find_template_dir(self) -> Path:
        """Find systemd template directory."""
        # Look for templates relative to this file
        current_dir = Path(__file__).parent
        template_dir = current_dir.parent.parent / "templates" / "systemd"

        if template_dir.exists():
            return template_dir

        # Fallback to FLEET internal templates
        fleet_templates = Path.home() / "fleet" / "_internal" / "templates" / "systemd"
        if fleet_templates.exists():
            return fleet_templates

        raise RuntimeError("SystemD templates not found")

    def create_engine_service(
        self,
        project_name: str,
        engine_path: Path,
        environment: str = "development",
        fleet_root: Optional[Path] = None,
        env_vars: Optional[Dict[str, str]] = None,
    ) -> ServiceResult:
        """Create systemd service for an FLEET engine."""

        service_name = f"fleet-{project_name}-engine"
        service_file = f"/etc/systemd/system/{service_name}.service"

        try:
            # Load template
            template_file = self.template_dir / "fleet-engine.service.template"
            if not template_file.exists():
                return ServiceResult(success=False, status="error", error=f"Template not found: {template_file}")

            with open(template_file, "r") as f:
                template_content = f.read()

            # Prepare template variables
            template_vars: Dict[str, Any] = {
                "PROJECT_NAME": project_name,
                "ENGINE_PATH": str(engine_path),
                "ENVIRONMENT": environment,
                "FLEET_ROOT": str(fleet_root or Path.home() / "fleet"),
            }

            # Add environment variables
            if env_vars:
                env_lines = [f"{k}={v}" for k, v in env_vars.items()]
                template_vars["ENGINE_ENV_VARS"] = env_lines
            else:
                template_vars["ENGINE_ENV_VARS"] = []

            # Simple template substitution (would use Jinja2 in production)
            service_content = template_content
            for key, value in template_vars.items():
                if key == "ENGINE_ENV_VARS" and isinstance(value, list):
                    # Handle environment variables list
                    env_section = "\n".join([f"Environment={env}" for env in value])
                    service_content = service_content.replace(
                        "{{#ENGINE_ENV_VARS}}\nEnvironment={{.}}\n{{/ENGINE_ENV_VARS}}", env_section
                    )
                else:
                    service_content = service_content.replace(f"{{{{{key}}}}}", str(value))

            # Clean up any remaining template syntax
            service_content = service_content.replace(
                "{{#ENGINE_ENV_VARS}}\nEnvironment={{.}}\n{{/ENGINE_ENV_VARS}}", ""
            )

            # Write service file
            with tempfile.NamedTemporaryFile(mode="w", suffix=".service", delete=False) as tmp_file:
                tmp_file.write(service_content)
                tmp_file_path = tmp_file.name

            # Copy to systemd directory with sudo
            subprocess.run(["sudo", "cp", tmp_file_path, service_file], check=True)

            # Set proper permissions
            subprocess.run(["sudo", "chmod", "644", service_file], check=True)

            # Clean up temp file
            Path(tmp_file_path).unlink()

            return ServiceResult(success=True, status="created", service_file=service_file)

        except subprocess.CalledProcessError as e:
            return ServiceResult(success=False, status="error", error=f"Failed to create service: {e}")
        except Exception as e:
            return ServiceResult(success=False, status="error", error=str(e))

    def manage_service(self, service_name: str, action: str) -> ServiceResult:
        """Manage a systemd service (start, stop, restart, enable, disable, status)."""

        if action not in ["start", "stop", "restart", "enable", "disable", "status", "reload"]:
            return ServiceResult(success=False, status="error", error=f"Invalid action: {action}")

        try:
            if action == "status":
                # Get service status
                result = subprocess.run(["systemctl", "is-active", service_name], capture_output=True, text=True)

                status = result.stdout.strip()
                return ServiceResult(success=True, status=status)

            else:
                # Perform action that requires sudo
                subprocess.run(["sudo", "systemctl", action, service_name], check=True)

                return ServiceResult(success=True, status=f"{action}ed")

        except subprocess.CalledProcessError as e:
            return ServiceResult(success=False, status="error", error=f"Service {action} failed: {e}")

    def reload_systemd(self) -> ServiceResult:
        """Reload systemd daemon after service file changes."""
        try:
            subprocess.run(["sudo", "systemctl", "daemon-reload"], check=True)
            return ServiceResult(success=True, status="reloaded")
        except subprocess.CalledProcessError as e:
            return ServiceResult(success=False, status="error", error=f"Daemon reload failed: {e}")

    def install_engine_service(
        self, project_name: str, engine_path: Path, environment: str = "development", start_service: bool = True
    ) -> ServiceResult:
        """Install and optionally start an engine service."""

        # Create the service
        result = self.create_engine_service(project_name, engine_path, environment)
        if not result.success:
            return result

        # Reload systemd
        reload_result = self.reload_systemd()
        if not reload_result.success:
            return reload_result

        service_name = f"fleet-{project_name}-engine"

        # Enable service
        enable_result = self.manage_service(service_name, "enable")
        if not enable_result.success:
            return enable_result

        # Start service if requested
        if start_service:
            start_result = self.manage_service(service_name, "start")
            if not start_result.success:
                return start_result

        return ServiceResult(
            success=True,
            status="installed" + (" and started" if start_service else ""),
            service_file=result.service_file,
        )

    def get_service_logs(self, service_name: str, lines: int = 50) -> str:
        """Get logs for a service."""
        try:
            result = subprocess.run(
                ["journalctl", "-u", service_name, "-n", str(lines), "--no-pager"],
                capture_output=True,
                text=True,
                check=True,
            )

            return result.stdout

        except subprocess.CalledProcessError:
            return f"Could not retrieve logs for {service_name}"

    def list_fleet_services(self) -> List[Dict[str, Any]]:
        """List all FLEET-related systemd services."""
        try:
            result = subprocess.run(
                ["systemctl", "list-units", "fleet-*", "--no-pager", "--no-legend"], capture_output=True, text=True
            )

            services = []
            for line in result.stdout.strip().split("\n"):
                if line.strip():
                    parts = line.split()
                    if len(parts) >= 4:
                        services.append(
                            {
                                "name": parts[0],
                                "load": parts[1],
                                "active": parts[2],
                                "sub": parts[3],
                                "description": " ".join(parts[4:]) if len(parts) > 4 else "",
                            }
                        )

            return services

        except subprocess.CalledProcessError:
            return []
