"""
VS Code IDE Builder Integration

Builds full VS Code fork/custom IDE distributions.
Uses the VS Code gulp-based build system.
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
    """Target platform for VS Code builds."""

    MAC = "darwin"
    WIN = "win32"
    LINUX = "linux"


class Architecture(Enum):
    """Target architecture."""

    X64 = "x64"
    ARM64 = "arm64"
    ARMHF = "armhf"


@dataclass
class VSCodeBuildConfig:
    """Configuration for VS Code IDE builds."""

    platform: Platform = Platform.LINUX
    arch: Architecture = Architecture.X64
    quality: str = "stable"  # stable, insider
    skip_extensions: bool = False
    skip_compile: bool = False
    minify: bool = True
    output_dir: Optional[str] = None
    extra_args: list[str] = field(default_factory=list)

    @classmethod
    def from_dict(cls, data: dict) -> "VSCodeBuildConfig":
        """Create config from dictionary."""
        platform = Platform.LINUX
        if data.get("platform"):
            try:
                platform = Platform(data["platform"])
            except ValueError:
                # Try common names
                p = data["platform"].lower()
                if p in ["mac", "macos", "darwin"]:
                    platform = Platform.MAC
                elif p in ["win", "windows", "win32"]:
                    platform = Platform.WIN
                elif p in ["linux"]:
                    platform = Platform.LINUX

        return cls(
            platform=platform,
            arch=Architecture(data.get("arch", "x64")),
            quality=data.get("quality", "stable"),
            skip_extensions=data.get("skip_extensions", False),
            skip_compile=data.get("skip_compile", False),
            minify=data.get("minify", True),
            output_dir=data.get("output_dir"),
            extra_args=data.get("extra_args", []),
        )


@dataclass
class BuildResult:
    """Result of VS Code IDE build."""

    success: bool
    output_path: Optional[Path] = None
    error_message: Optional[str] = None
    stdout: str = ""
    stderr: str = ""
    command: str = ""


class VSCodeIDEBuilder:
    """Builder for custom VS Code IDE distributions."""

    # Default VS Code template path
    DEFAULT_TEMPLATE = Path.home() / "fleet/docs/templates/IDE/vscode"

    def __init__(self, config: Optional[VSCodeBuildConfig] = None):
        self.config = config or VSCodeBuildConfig()
        self._yarn_path: Optional[Path] = None
        self._npm_path: Optional[Path] = None
        self._gulp_path: Optional[Path] = None

    @property
    def yarn_path(self) -> Optional[Path]:
        """Find yarn executable."""
        if self._yarn_path is None:
            yarn = shutil.which("yarn")
            if yarn:
                self._yarn_path = Path(yarn)
        return self._yarn_path

    @property
    def npm_path(self) -> Optional[Path]:
        """Find npm executable."""
        if self._npm_path is None:
            npm = shutil.which("npm")
            if npm:
                self._npm_path = Path(npm)
        return self._npm_path

    def is_available(self) -> bool:
        """Check if build tools are available."""
        return self.yarn_path is not None or self.npm_path is not None

    def _detect_vscode_source(self, source_path: Path) -> bool:
        """Check if path contains VS Code source."""
        package_json = source_path / "package.json"
        if not package_json.exists():
            return False

        try:
            with open(package_json) as f:
                pkg = json.load(f)
                name = pkg.get("name", "")
                return "code" in name.lower() or "vscode" in name.lower()
        except (json.JSONDecodeError, OSError):
            return False

    def _get_build_target(self) -> str:
        """Get gulp build target based on platform and quality."""
        platform = self.config.platform.value
        arch = self.config.arch.value

        if self.config.minify:
            return f"vscode-{platform}-{arch}-min"
        return f"vscode-{platform}-{arch}"

    def build_command(self, source_path: Path) -> list[str]:
        """Build the gulp command for VS Code compilation."""
        # VS Code uses yarn and gulp
        cmd = []

        if self.yarn_path:
            cmd = [str(self.yarn_path), "gulp"]
        elif self.npm_path:
            cmd = [str(self.npm_path), "run", "gulp"]
        else:
            raise RuntimeError("Neither yarn nor npm found")

        # Build target
        target = self._get_build_target()
        cmd.append(target)

        # Extra args
        cmd.extend(self.config.extra_args)

        return cmd

    def install_dependencies(
        self,
        source_path: Path,
        dry_run: bool = False,
    ) -> BuildResult:
        """Install VS Code dependencies."""
        if dry_run:
            cmd = f"yarn install (in {source_path})"
            return BuildResult(
                success=True,
                command=cmd,
                stdout=f"[DRY RUN] Would execute:\n{cmd}",
            )

        logger.info("Installing VS Code dependencies...")

        try:
            if self.yarn_path:
                cmd = [str(self.yarn_path), "install"]
            elif self.npm_path:
                cmd = [str(self.npm_path), "install"]
            else:
                return BuildResult(
                    success=False,
                    error_message="Neither yarn nor npm found",
                )

            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                cwd=source_path,
            )

            return BuildResult(
                success=result.returncode == 0,
                error_message=(
                    f"Dependency installation failed"
                    if result.returncode != 0
                    else None
                ),
                stdout=result.stdout,
                stderr=result.stderr,
                command=" ".join(cmd),
            )

        except subprocess.TimeoutExpired:
            return BuildResult(
                success=False,
                error_message="Dependency installation timed out",
            )
        except OSError as e:
            return BuildResult(
                success=False,
                error_message=f"Failed to install dependencies: {e}",
            )

    def compile(
        self,
        source_path: Path,
        dry_run: bool = False,
    ) -> BuildResult:
        """
        Compile VS Code source.

        Args:
            source_path: Path to VS Code source
            dry_run: If True, only return the command

        Returns:
            BuildResult with compilation status
        """
        if not self.config.skip_compile:
            logger.info("Compiling VS Code...")

            if self.yarn_path:
                cmd = [str(self.yarn_path), "compile"]
            elif self.npm_path:
                cmd = [str(self.npm_path), "run", "compile"]
            else:
                return BuildResult(
                    success=False,
                    error_message="Neither yarn nor npm found",
                )

            if dry_run:
                return BuildResult(
                    success=True,
                    command=" ".join(cmd),
                    stdout=f"[DRY RUN] Would execute:\n{' '.join(cmd)}",
                )

            try:
                result = subprocess.run(
                    cmd,
                    capture_output=True,
                    text=True,
                    cwd=source_path,
                )

                if result.returncode != 0:
                    return BuildResult(
                        success=False,
                        error_message="Compilation failed",
                        stdout=result.stdout,
                        stderr=result.stderr,
                        command=" ".join(cmd),
                    )

            except subprocess.TimeoutExpired:
                return BuildResult(
                    success=False,
                    error_message="Compilation timed out",
                )
            except OSError as e:
                return BuildResult(
                    success=False,
                    error_message=f"Failed to compile: {e}",
                )

        return BuildResult(success=True)

    def build(
        self,
        source_path: Path,
        dry_run: bool = False,
    ) -> BuildResult:
        """
        Build VS Code IDE distribution.

        Args:
            source_path: Path to VS Code source
            dry_run: If True, only return commands

        Returns:
            BuildResult with output path
        """
        if not self.is_available():
            return BuildResult(
                success=False,
                error_message="Build tools not available. Install yarn or npm.",
            )

        source_path = Path(source_path)
        if not source_path.exists():
            return BuildResult(
                success=False,
                error_message=f"Source path not found: {source_path}",
            )

        if not self._detect_vscode_source(source_path):
            return BuildResult(
                success=False,
                error_message=f"Not a VS Code source directory: {source_path}",
            )

        try:
            cmd = self.build_command(source_path)
            command_str = " ".join(cmd)

            if dry_run:
                steps = [
                    "1. Install dependencies: yarn install",
                    "2. Compile: yarn compile",
                    f"3. Build: {command_str}",
                ]
                return BuildResult(
                    success=True,
                    command=command_str,
                    stdout=f"[DRY RUN] Build steps:\n" + "\n".join(steps),
                )

            # Install dependencies
            dep_result = self.install_dependencies(source_path)
            if not dep_result.success:
                return dep_result

            # Compile
            compile_result = self.compile(source_path)
            if not compile_result.success:
                return compile_result

            # Build
            logger.info(f"Building VS Code for {self.config.platform.value}")
            logger.debug(f"Command: {command_str}")

            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                cwd=source_path,
            )

            if result.returncode == 0:
                # Find output
                output_path = self._find_output(source_path)

                return BuildResult(
                    success=True,
                    output_path=output_path,
                    stdout=result.stdout,
                    stderr=result.stderr,
                    command=command_str,
                )
            else:
                return BuildResult(
                    success=False,
                    error_message=f"Build failed with code {result.returncode}",
                    stdout=result.stdout,
                    stderr=result.stderr,
                    command=command_str,
                )

        except subprocess.TimeoutExpired:
            return BuildResult(
                success=False,
                error_message="Build timed out",
            )
        except OSError as e:
            return BuildResult(
                success=False,
                error_message=f"Failed to build: {e}",
            )

    def _find_output(self, source_path: Path) -> Optional[Path]:
        """Find the built VS Code output directory."""
        platform = self.config.platform.value
        arch = self.config.arch.value

        # Check common output locations
        candidates = [
            source_path / f"VSCode-{platform}-{arch}",
            source_path / f"vscode-{platform}-{arch}",
            source_path / ".build" / f"VSCode-{platform}-{arch}",
            source_path / "out" / f"vscode-{platform}-{arch}",
        ]

        if self.config.output_dir:
            candidates.insert(0, Path(self.config.output_dir))

        for candidate in candidates:
            if candidate.exists():
                return candidate

        return None

    def build_all_platforms(
        self,
        source_path: Path,
        platforms: Optional[list[Platform]] = None,
        dry_run: bool = False,
    ) -> dict[Platform, BuildResult]:
        """
        Build VS Code for multiple platforms.

        Args:
            source_path: Path to VS Code source
            platforms: List of target platforms
            dry_run: If True, only return commands

        Returns:
            Dictionary of platform -> BuildResult
        """
        platforms = platforms or [Platform.MAC, Platform.WIN, Platform.LINUX]
        results = {}

        original_platform = self.config.platform

        for platform in platforms:
            self.config.platform = platform
            results[platform] = self.build(source_path, dry_run)

        self.config.platform = original_platform
        return results
