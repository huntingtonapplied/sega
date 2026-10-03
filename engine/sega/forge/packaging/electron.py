"""
Electron Builder Integration

Packages desktop applications using electron-builder.
Supports macOS (.dmg), Windows (.exe), and Linux (.AppImage).
"""

import json
import logging
import shutil
import subprocess
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)


class Platform(Enum):
    """Target platform for Electron builds."""

    MAC = "mac"
    WIN = "win"
    LINUX = "linux"
    ALL = "all"


class MacTarget(Enum):
    """macOS build targets."""

    DMG = "dmg"
    PKG = "pkg"
    ZIP = "zip"
    MAS = "mas"  # Mac App Store


class WinTarget(Enum):
    """Windows build targets."""

    NSIS = "nsis"
    PORTABLE = "portable"
    MSI = "msi"
    APPX = "appx"


class LinuxTarget(Enum):
    """Linux build targets."""

    APPIMAGE = "AppImage"
    DEB = "deb"
    RPM = "rpm"
    SNAP = "snap"
    FLATPAK = "flatpak"


@dataclass
class ElectronConfig:
    """Configuration for Electron Builder."""

    # Build targets
    platforms: list[Platform] = field(default_factory=lambda: [Platform.ALL])
    mac_target: MacTarget = MacTarget.DMG
    win_target: WinTarget = WinTarget.NSIS
    linux_target: LinuxTarget = LinuxTarget.APPIMAGE

    # Build options
    publish: bool = False
    config_file: Optional[str] = None  # electron-builder.yml path

    # Output
    output_dir: Optional[str] = None

    # Architecture
    x64: bool = True
    arm64: bool = False
    universal: bool = False  # macOS universal binary

    extra_args: list[str] = field(default_factory=list)

    @classmethod
    def from_dict(cls, data: dict) -> "ElectronConfig":
        """Create config from dictionary."""
        platforms = []
        for p in data.get("platforms", ["all"]):
            try:
                platforms.append(Platform(p))
            except ValueError:
                logger.warning(f"Unknown platform: {p}")

        return cls(
            platforms=platforms or [Platform.ALL],
            mac_target=MacTarget(data.get("mac_target", "dmg")),
            win_target=WinTarget(data.get("win_target", "nsis")),
            linux_target=LinuxTarget(data.get("linux_target", "AppImage")),
            publish=data.get("publish", False),
            config_file=data.get("config_file"),
            output_dir=data.get("output_dir"),
            x64=data.get("x64", True),
            arm64=data.get("arm64", False),
            universal=data.get("universal", False),
            extra_args=data.get("extra_args", []),
        )


@dataclass
class PackagingResult:
    """Result of Electron packaging."""

    success: bool
    artifacts: list[Path] = field(default_factory=list)
    error_message: Optional[str] = None
    stdout: str = ""
    stderr: str = ""
    command: str = ""


class ElectronPackager:
    """Electron Builder packager for desktop applications."""

    # Default template path
    DEFAULT_TEMPLATE = Path.home() / "fleet/docs/templates/desktop/electron_base"

    def __init__(self, config: Optional[ElectronConfig] = None):
        self.config = config or ElectronConfig()
        self._npm_path: Optional[Path] = None
        self._npx_path: Optional[Path] = None

    @property
    def npm_path(self) -> Optional[Path]:
        """Find npm executable."""
        if self._npm_path is None:
            npm = shutil.which("npm")
            if npm:
                self._npm_path = Path(npm)
        return self._npm_path

    @property
    def npx_path(self) -> Optional[Path]:
        """Find npx executable."""
        if self._npx_path is None:
            npx = shutil.which("npx")
            if npx:
                self._npx_path = Path(npx)
        return self._npx_path

    def is_available(self) -> bool:
        """Check if electron-builder is available."""
        return self.npx_path is not None

    def get_version(self) -> Optional[str]:
        """Get electron-builder version."""
        if not self.npx_path:
            return None
        try:
            result = subprocess.run(
                [str(self.npx_path), "electron-builder", "--version"],
                capture_output=True,
                text=True,
                timeout=30,
            )
            if result.returncode == 0:
                return result.stdout.strip()
        except (subprocess.TimeoutExpired, OSError):
            pass
        return None

    def _detect_electron_project(self, project_path: Path) -> bool:
        """Check if path is an Electron project."""
        package_json = project_path / "package.json"
        if not package_json.exists():
            return False

        try:
            with open(package_json) as f:
                pkg = json.load(f)
                deps = pkg.get("dependencies", {})
                dev_deps = pkg.get("devDependencies", {})
                return "electron" in deps or "electron" in dev_deps
        except (json.JSONDecodeError, OSError):
            return False

    def build_command(
        self,
        project_path: Path,
        platforms: Optional[list[Platform]] = None,
    ) -> list[str]:
        """Build electron-builder command."""
        if not self.npx_path:
            raise RuntimeError("npx not found")

        cmd = [str(self.npx_path), "electron-builder"]

        # Platforms
        target_platforms = platforms or self.config.platforms
        for platform in target_platforms:
            if platform == Platform.ALL:
                cmd.append("--macos")
                cmd.append("--windows")
                cmd.append("--linux")
            elif platform == Platform.MAC:
                cmd.extend(["--mac", self.config.mac_target.value])
            elif platform == Platform.WIN:
                cmd.extend(["--win", self.config.win_target.value])
            elif platform == Platform.LINUX:
                cmd.extend(["--linux", self.config.linux_target.value])

        # Architecture
        if self.config.universal and Platform.MAC in target_platforms:
            cmd.append("--universal")
        else:
            if self.config.x64:
                cmd.append("--x64")
            if self.config.arm64:
                cmd.append("--arm64")

        # Config file
        if self.config.config_file:
            cmd.extend(["--config", self.config.config_file])

        # Output directory
        if self.config.output_dir:
            cmd.extend(["--output", self.config.output_dir])

        # Publish
        if self.config.publish:
            cmd.append("--publish=always")
        else:
            cmd.append("--publish=never")

        # Extra args
        cmd.extend(self.config.extra_args)

        return cmd

    def package(
        self,
        project_path: Path,
        platforms: Optional[list[Platform]] = None,
        dry_run: bool = False,
    ) -> PackagingResult:
        """
        Package an Electron application.

        Args:
            project_path: Path to the Electron project
            platforms: Target platforms (defaults to config)
            dry_run: If True, only return the command

        Returns:
            PackagingResult with artifacts and status
        """
        if not self.is_available():
            return PackagingResult(
                success=False,
                error_message="electron-builder not available. Run: npm install -g electron-builder",
            )

        project_path = Path(project_path)
        if not project_path.exists():
            return PackagingResult(
                success=False,
                error_message=f"Project path not found: {project_path}",
            )

        if not self._detect_electron_project(project_path):
            return PackagingResult(
                success=False,
                error_message=f"Not an Electron project: {project_path}",
            )

        try:
            cmd = self.build_command(project_path, platforms)
            command_str = " ".join(cmd)

            if dry_run:
                return PackagingResult(
                    success=True,
                    command=command_str,
                    stdout=f"[DRY RUN] Would execute in {project_path}:\n{command_str}",
                )

            logger.info(f"Packaging Electron app: {project_path}")
            logger.debug(f"Command: {command_str}")

            # Ensure dependencies are installed
            self._ensure_dependencies(project_path)

            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                cwd=project_path,
            )

            if result.returncode == 0:
                # Find artifacts
                artifacts = self._find_artifacts(project_path)

                return PackagingResult(
                    success=True,
                    artifacts=artifacts,
                    stdout=result.stdout,
                    stderr=result.stderr,
                    command=command_str,
                )
            else:
                return PackagingResult(
                    success=False,
                    error_message=f"electron-builder failed with code {result.returncode}",
                    stdout=result.stdout,
                    stderr=result.stderr,
                    command=command_str,
                )

        except subprocess.TimeoutExpired:
            return PackagingResult(
                success=False,
                error_message="Packaging timed out",
            )
        except OSError as e:
            return PackagingResult(
                success=False,
                error_message=f"Failed to execute electron-builder: {e}",
            )

    def _ensure_dependencies(self, project_path: Path) -> None:
        """Ensure npm dependencies are installed."""
        node_modules = project_path / "node_modules"
        if not node_modules.exists():
            logger.info("Installing npm dependencies...")
            if self.npm_path:
                subprocess.run(
                    [str(self.npm_path), "install"],
                    cwd=project_path,
                    capture_output=True,
                )

    def _find_artifacts(self, project_path: Path) -> list[Path]:
        """Find built artifacts in dist directory."""
        artifacts = []

        # Check common output directories
        output_dirs = [
            project_path / "dist",
            project_path / "dist-electron",
            project_path / "release",
            project_path / "out",
        ]

        if self.config.output_dir:
            output_dirs.insert(0, project_path / self.config.output_dir)

        for output_dir in output_dirs:
            if output_dir.exists():
                # Find installer files
                for pattern in [
                    "*.dmg",
                    "*.pkg",
                    "*.exe",
                    "*.msi",
                    "*.AppImage",
                    "*.deb",
                    "*.rpm",
                    "*.snap",
                    "*.zip",
                ]:
                    artifacts.extend(output_dir.glob(pattern))
                    artifacts.extend(output_dir.glob(f"**/{pattern}"))

        return list(set(artifacts))

    def package_from_template(
        self,
        template_path: Optional[Path] = None,
        project_name: str = "app",
        output_dir: Optional[Path] = None,
        platforms: Optional[list[Platform]] = None,
        dry_run: bool = False,
    ) -> PackagingResult:
        """
        Package using FLEET Electron template.

        Args:
            template_path: Path to Electron template (defaults to FLEET template)
            project_name: Name for the project
            output_dir: Output directory for artifacts
            platforms: Target platforms
            dry_run: If True, only return commands

        Returns:
            PackagingResult
        """
        template = template_path or self.DEFAULT_TEMPLATE

        if not template.exists():
            return PackagingResult(
                success=False,
                error_message=f"Template not found: {template}",
            )

        # For now, package directly from template
        # In production, would copy template and customize
        if output_dir:
            self.config.output_dir = str(output_dir)

        return self.package(template, platforms, dry_run)
