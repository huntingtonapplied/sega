#!/usr/bin/env python3
"""
SEGA CLI Integration for Shared Infrastructure
===============================================================================
File: engine/sega/local/integration.py
Project: SEGA (Scalable Engineering & Growth Automation)
Purpose: Integration layer for shared infrastructure with existing SEGA CLI
===============================================================================
"""

import logging
from pathlib import Path
from typing import Dict, List, Optional, Any
import click

from .shared_infrastructure_manager import SharedInfrastructureManager
from .manager import LocalDeploymentManager

logger = logging.getLogger(__name__)


class SEGAInfrastructureIntegration:
    """Integration layer for shared infrastructure with existing SEGA CLI."""

    def __init__(self, fleet_root: Path, project: str):
        self.fleet_root = fleet_root
        self.project = project
        self.shared_manager = SharedInfrastructureManager(fleet_root, project)

        # Initialize local deployment manager for integration
        self.local_manager = LocalDeploymentManager(
            workspace_root=fleet_root,
            config={},  # Will use default config
        )

    def prepare_shared_infrastructure(self, components: List[str] = None) -> bool:
        """Prepare shared infrastructure for the project."""
        if components is None:
            components = ["frontend", "ide", "backend", "engine"]

        click.echo(f"🚀 Preparing shared infrastructure for {self.project}...")
        click.echo(f"🔧 Components: {', '.join(components)}")

        try:
            # Prepare basic infrastructure
            if not self.shared_manager.prepare_shared_infrastructure():
                click.echo("❌ Failed to prepare basic infrastructure", err=True)
                return False

            # Prepare component-specific dependencies
            if not self.shared_manager.prepare_shared_dependencies(components):
                click.echo("❌ Failed to prepare component dependencies", err=True)
                return False

            # Setup symlinks for efficient development
            self._setup_development_symlinks()

            click.echo("✅ Shared infrastructure prepared successfully")
            return True

        except Exception as e:
            click.echo(f"❌ Error preparing infrastructure: {e}", err=True)
            logger.error(f"Infrastructure preparation failed: {e}")
            return False

    def _setup_development_symlinks(self) -> None:
        """Setup development symlinks for efficient workflow."""
        from sega.core.config import get_config

        _cfg = get_config()
        _p = _cfg.get_project(self.project)
        _shared_project = _cfg.get_shared_modules_project()
        if _p and _p.has_shared_frontend_modules and _shared_project:
            shared_root = self.fleet_root / _shared_project

            # Frontend symlinks
            frontend_shared = self.fleet_root / "environments" / "frontend_shared"
            if frontend_shared.exists():
                self._create_symlink(
                    frontend_shared / "node_modules", shared_root / "frontend" / "landing_app" / "node_modules"
                )
                self._create_symlink(
                    frontend_shared / "node_modules", shared_root / "frontend" / "product_app" / "node_modules"
                )

            # IDE symlinks
            ide_shared = self.fleet_root / "environments" / "ide_shared"
            if ide_shared.exists():
                self._create_symlink(ide_shared / "node_modules", shared_root / "ide" / "node_modules")

    def _create_symlink(self, target: Path, source: Path) -> bool:
        """Create a symlink with proper error handling."""
        try:
            if source.exists():
                if source.is_symlink():
                    source.unlink()
                else:
                    # Backup existing directory
                    backup = source.parent / f"{source.name}.backup"
                    if backup.exists():
                        import shutil

                        shutil.rmtree(backup)
                    source.rename(backup)
                    click.echo(f"📦 Backed up existing {source.name}")

            source.symlink_to(target, target_is_directory=True)
            return True

        except OSError as e:
            click.echo(f"⚠️  Failed to create symlink {source} -> {target}: {e}")
            return False

    def integrate_with_local_deployment(self) -> None:
        """Integrate shared infrastructure with local deployment manager."""
        # Enhance local deployment manager with shared infrastructure capabilities
        self._enhance_local_manager()

        # Add shared infrastructure status reporting
        self._add_status_reporting()

    def _enhance_local_manager(self) -> None:
        """Enhance local deployment manager with shared infrastructure features."""
        # Add shared infrastructure methods to local manager
        original_deploy_with_native = self.local_manager._deploy_with_native

        def enhanced_deploy_with_native(project: str, env_mode: Dict[str, str], port_offset: int = 0):
            """Enhanced native deployment with shared infrastructure support."""
            # First prepare shared infrastructure
            self.prepare_shared_infrastructure()

            # Then proceed with original deployment
            return original_deploy_with_native(project, env_mode, port_offset)

        # Replace the method
        self.local_manager._deploy_with_native = enhanced_deploy_with_native

    def _add_status_reporting(self) -> None:
        """Add shared infrastructure status reporting to local manager."""

        def get_shared_status() -> Dict[str, Any]:
            """Get enhanced status including shared infrastructure."""
            status = self.shared_manager.get_status()

            # Add deployment readiness info
            status["deployment_readiness"] = {
                "shared_infrastructure_ready": all(
                    [
                        status.get("environments", {}).get("backend_venv", False),
                        status.get("environments", {}).get("engine_venv", False),
                    ]
                ),
                "component_support": {
                    "frontend": status.get("boltzmann_specific", {}).get("frontend_shared", False),
                    "ide": status.get("boltzmann_specific", {}).get("ide_shared", False),
                },
                "native_databases_ready": all(
                    [
                        status.get("data_directories", {}).get("postgres", False),
                        status.get("data_directories", {}).get("redis", False),
                    ]
                ),
            }

            return status

        # Add to local manager (if it has status capabilities)
        if hasattr(self.local_manager, "get_status"):
            original_get_status = self.local_manager.get_status

            def enhanced_get_status():
                base_status = original_get_status()
                base_status["shared_infrastructure"] = get_shared_status()
                return base_status

            self.local_manager.get_status = enhanced_get_status

    def create_integration_commands(self) -> Dict[str, Any]:
        """Create integration commands for CLI."""
        return {
            "prepare": {
                "function": self.prepare_shared_infrastructure,
                "help": "Prepare shared infrastructure for project deployment",
                "options": {"components": {"type": List[str], "default": ["frontend", "ide"]}},
            },
            "status": {
                "function": self.shared_manager.get_status,
                "help": "Show shared infrastructure status",
                "options": {},
            },
        }


# Global integration instance for CLI use
_integration_instance: Optional[SEGAInfrastructureIntegration] = None


def get_integration(fleet_root: Path = None, project: str = None) -> SEGAInfrastructureIntegration:
    """Get or create global integration instance."""
    global _integration_instance

    if _integration_instance is None:
        if fleet_root is None:
            fleet_root = Path.home() / "fleet"
        if project is None:
            # Default to the shared-frontend-modules project, if one is configured
            from sega.core.config import get_config
            project = get_config().get_shared_modules_project() or ""

        _integration_instance = SEGAInfrastructureIntegration(fleet_root, project)

    return _integration_instance


def initialize_integration(fleet_root: Path = None, project: str = None) -> SEGAInfrastructureIntegration:
    """Initialize SEGA infrastructure integration."""
    integration = get_integration(fleet_root, project)
    integration.integrate_with_local_deployment()
    return integration
