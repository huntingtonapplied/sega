#!/usr/bin/env python3
"""
SEGA Shared Infrastructure Manager
===============================================================================
File: engine/sega/local/shared_infrastructure_manager.py
Project: SEGA (Scalable Engineering & Growth Automation)
Purpose: Manage shared infrastructure preparation and setup for SEGA deployments
===============================================================================
"""

import subprocess
import json
import logging
from pathlib import Path
from typing import Dict, List, Optional, Any
import sys

logger = logging.getLogger(__name__)


class SharedInfrastructureManager:
    """Manages shared infrastructure preparation for SEGA deployments."""

    def __init__(self, fleet_root: Path, project: str):
        self.fleet_root = fleet_root
        self.project = project
        self.environments_dir = fleet_root / "environments"

        # Whether this project uses the shared frontend/IDE node_modules setup.
        # Config-driven capability flag (replaces the historical codename gate).
        self._shared_modules_enabled = self._resolve_shared_modules_enabled()

        # Component-specific paths
        self.frontend_shared = self.environments_dir / "boltzmann_frontend"
        self.ide_shared = self.environments_dir / "boltzmann_ide"
        self.data_dir = self.environments_dir / "data"
        self.configs_dir = self.environments_dir / "configs"

        # Shared environments
        self.backend_venv = self.environments_dir / "backend_venv"
        self.engine_venv = self.environments_dir / "engine_venv"
        self.node_modules = self.environments_dir / "node_modules"

    def _resolve_shared_modules_enabled(self) -> bool:
        """Resolve the shared-frontend-modules capability flag from config."""
        try:
            from sega.core.config import get_config

            _p = get_config().get_project(self.project)
            return bool(_p and _p.has_shared_frontend_modules)
        except Exception as e:
            logger.warning(f"Could not resolve shared-frontend-modules flag for {self.project}: {e}")
            return False

    def prepare_shared_infrastructure(self) -> bool:
        """Prepare shared infrastructure for projects with the shared-modules capability."""
        logger.info(f"Preparing shared infrastructure for {self.project}...")

        try:
            # 1. Create directory structure
            self._create_directories()

            # 2. Setup component-specific shared node_modules
            if self._shared_modules_enabled:
                self._setup_shared_frontend_modules()

            # 3. Create symlinks for shared environments
            self._setup_shared_symlinks()

            # 4. Validate setup
            if self._validate_setup():
                logger.info("Shared infrastructure prepared successfully")
                return True
            else:
                logger.error("Shared infrastructure validation failed")
                return False

        except Exception as e:
            logger.error(f"Failed to prepare shared infrastructure: {e}")
            return False

    def _create_directories(self) -> None:
        """Create necessary directory structure."""
        directories = [
            # Data directories for native databases
            self.data_dir / "postgres",
            self.data_dir / "timescale",
            self.data_dir / "redis",
            # Configuration directories
            self.configs_dir,
            # Shared-frontend-modules directories
            self.frontend_shared,
            self.frontend_shared / "node_modules",
            self.frontend_shared / "landing_deps",
            self.frontend_shared / "product_deps",
            self.ide_shared,
            self.ide_shared / "node_modules",
            self.ide_shared / "build_assets",
            self.ide_shared / "extensions",
        ]

        for directory in directories:
            directory.mkdir(parents=True, exist_ok=True)
            logger.debug(f"Created directory: {directory}")

    def _shared_modules_root(self):
        """Workspace root of the project hosting the shared-modules layout.

        Config-derived (first project with ``has_shared_frontend_modules``);
        None when the fleet has no such project.
        """
        from sega.core.config import get_config
        name = get_config().get_shared_modules_project()
        return (self.fleet_root / name) if name else None

    def _setup_script_path(self):
        """Path of the shared-modules setup script, from `[fleet] shared_setup_script`.

        None when unconfigured.
        """
        from sega.core.config import get_config
        rel = get_config().fleet.shared_setup_script
        return (self.fleet_root / rel) if rel else None

    def _setup_shared_frontend_modules(self) -> None:
        """Setup component-specific shared node_modules configuration."""
        shared_root = self._shared_modules_root()

        if shared_root is None or not shared_root.exists():
            logger.warning(f"Shared-modules project not found at {shared_root}")
            return

        # Run setup script to create package.json files
        setup_script = self._setup_script_path()

        if setup_script is not None and setup_script.exists():
            try:
                subprocess.run(
                    [sys.executable, str(setup_script), "--component", "frontend", "--fleet-root", str(self.fleet_root)],
                    check=True,
                    capture_output=True,
                )
                logger.info("Shared modules configuration created")
            except subprocess.CalledProcessError as e:
                logger.error(f"Failed to setup shared modules: {e}")
        else:
            logger.warning(f"Shared-modules setup script not found at {setup_script}")

    def _setup_shared_symlinks(self) -> None:
        """Setup symlinks for shared environments."""
        symlink_mappings = []

        shared_root = self._shared_modules_root() if self._shared_modules_enabled else None
        if shared_root is not None:
            # Shared frontend/IDE node_modules symlinks (shared-modules layout)
            symlink_mappings.extend(
                [
                    # Frontend symlinks
                    (
                        self.frontend_shared / "node_modules",
                        shared_root / "frontend" / "landing_app" / "node_modules",
                    ),
                    (
                        self.frontend_shared / "node_modules",
                        shared_root / "frontend" / "product_app" / "node_modules",
                    ),
                    (self.frontend_shared / "node_modules", shared_root / "frontend" / "node_modules"),
                    # IDE symlinks
                    (self.ide_shared / "node_modules", shared_root / "ide" / "node_modules"),
                    (self.ide_shared / "node_modules", shared_root / "ide" / "remote" / "node_modules"),
                ]
            )

        # Create symlinks safely
        for target, source in symlink_mappings:
            self._create_safe_symlink(target, source)

    def _create_safe_symlink(self, target: Path, source: Path) -> None:
        """Create symlink with proper conflict handling."""
        if source.exists():
            if source.is_symlink():
                # Remove existing symlink
                source.unlink()
                logger.debug(f"Removed existing symlink: {source}")
            else:
                # Backup existing directory
                backup = source.parent / f"{source.name}.backup"
                if backup.exists():
                    import shutil

                    shutil.rmtree(backup)
                source.rename(backup)
                logger.info(f"Backed up existing {source.name} to {backup}")

        try:
            source.symlink_to(target, target_is_directory=True)
            logger.debug(f"Created symlink: {source} -> {target}")
        except OSError as e:
            logger.error(f"Failed to create symlink {source} -> {target}: {e}")

    def _validate_setup(self) -> bool:
        """Validate that shared infrastructure is properly configured."""
        # Check that essential directories exist
        required_dirs = [
            self.data_dir,
            self.configs_dir,
            self.backend_venv,
            self.engine_venv,
            self.node_modules,
        ]

        if self._shared_modules_enabled:
            required_dirs.extend(
                [
                    self.frontend_shared,
                    self.ide_shared,
                ]
            )

        for directory in required_dirs:
            if not directory.exists():
                logger.error(f"Required directory missing: {directory}")
                return False

        # Check package.json files exist for shared-modules projects
        if self._shared_modules_enabled:
            package_files = [
                self.frontend_shared / "package.json",
                self.frontend_shared / "landing_deps" / "package.json",
                self.frontend_shared / "product_deps" / "package.json",
            ]

            for package_file in package_files:
                if not package_file.exists():
                    logger.error(f"Required package.json missing: {package_file}")
                    return False

        return True

    def prepare_shared_dependencies(self, components: List[str] = None) -> bool:
        """Prepare and install shared dependencies."""
        if components is None:
            components = ["frontend", "ide"]

        logger.info(f"Preparing shared dependencies for components: {components}")

        if self._shared_modules_enabled:
            # Setup shared frontend modules (configured setup script)
            setup_script = self._setup_script_path()

            if setup_script is not None and setup_script.exists():
                for component in components:
                    try:
                        subprocess.run(
                            [
                                sys.executable,
                                str(setup_script),
                                "--component",
                                component,
                                "--fleet-root",
                                str(self.fleet_root),
                            ],
                            check=True,
                            capture_output=True,
                        )
                        logger.info(f"Prepared {component} shared dependencies")
                    except subprocess.CalledProcessError as e:
                        logger.error(f"Failed to prepare {component} dependencies: {e}")
                        return False

        return True

    def get_status(self) -> Dict[str, Any]:
        """Get status of shared infrastructure."""
        status = {
            "project": self.project,
            "environments": {
                "backend_venv": self.backend_venv.exists(),
                "engine_venv": self.engine_venv.exists(),
                "node_modules": self.node_modules.exists(),
            },
            "data_directories": {
                "postgres": (self.data_dir / "postgres").exists(),
                "timescale": (self.data_dir / "timescale").exists(),
                "redis": (self.data_dir / "redis").exists(),
            },
        }

        if self._shared_modules_enabled:
            status["boltzmann_specific"] = {
                "frontend_shared": self.frontend_shared.exists(),
                "ide_shared": self.ide_shared.exists(),
                "frontend_package": (self.frontend_shared / "package.json").exists(),
                "landing_deps": (self.frontend_shared / "landing_deps" / "package.json").exists(),
                "product_deps": (self.frontend_shared / "product_deps" / "package.json").exists(),
            }

        return status
