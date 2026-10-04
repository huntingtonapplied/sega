"""
VS Code Extension Packager Integration

Packages VS Code extensions using vsce (Visual Studio Code Extensions).
Produces .vsix files for distribution.
"""

import json
import logging
import shutil
import subprocess
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)


@dataclass
class VSCEConfig:
    """Configuration for VS Code Extension packaging."""

    # Package options
    pre_release: bool = False
    no_dependencies: bool = False
    no_git_tag_version: bool = True
    no_update_package_json: bool = True

    # Yarn/npm
    yarn: bool = False
    no_yarn: bool = False

    # Output
    output_dir: Optional[str] = None
    output_filename: Optional[str] = None

    # Publishing (optional)
    publish: bool = False
    pat: Optional[str] = None  # Personal Access Token

    extra_args: list[str] = field(default_factory=list)

    @classmethod
    def from_dict(cls, data: dict) -> "VSCEConfig":
        """Create config from dictionary."""
        return cls(
            pre_release=data.get("pre_release", False),
            no_dependencies=data.get("no_dependencies", False),
            no_git_tag_version=data.get("no_git_tag_version", True),
            no_update_package_json=data.get("no_update_package_json", True),
            yarn=data.get("yarn", False),
            no_yarn=data.get("no_yarn", False),
            output_dir=data.get("output_dir"),
            output_filename=data.get("output_filename"),
            publish=data.get("publish", False),
            pat=data.get("pat"),
            extra_args=data.get("extra_args", []),
        )


@dataclass
class PackagingResult:
    """Result of extension packaging."""

    success: bool
    vsix_path: Optional[Path] = None
    error_message: Optional[str] = None
    stdout: str = ""
    stderr: str = ""
    command: str = ""


class VSCodeExtensionPackager:
    """Packager for VS Code extensions using vsce."""

    def __init__(self, config: Optional[VSCEConfig] = None):
        self.config = config or VSCEConfig()
        self._vsce_path: Optional[Path] = None
        self._npx_path: Optional[Path] = None

    @property
    def npx_path(self) -> Optional[Path]:
        """Find npx executable."""
        if self._npx_path is None:
            npx = shutil.which("npx")
            if npx:
                self._npx_path = Path(npx)
        return self._npx_path

    @property
    def vsce_path(self) -> Optional[Path]:
        """Find vsce executable."""
        if self._vsce_path is None:
            vsce = shutil.which("vsce")
            if vsce:
                self._vsce_path = Path(vsce)
        return self._vsce_path

    def is_available(self) -> bool:
        """Check if vsce is available."""
        return self.vsce_path is not None or self.npx_path is not None

    def get_version(self) -> Optional[str]:
        """Get vsce version."""
        try:
            if self.vsce_path:
                cmd = [str(self.vsce_path), "--version"]
            elif self.npx_path:
                cmd = [str(self.npx_path), "@vscode/vsce", "--version"]
            else:
                return None

            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=30,
            )
            if result.returncode == 0:
                return result.stdout.strip()
        except (subprocess.TimeoutExpired, OSError):
            pass
        return None

    def _get_base_command(self) -> list[str]:
        """Get base vsce command."""
        if self.vsce_path:
            return [str(self.vsce_path)]
        elif self.npx_path:
            return [str(self.npx_path), "@vscode/vsce"]
        raise RuntimeError("vsce not found")

    def _detect_extension_project(self, extension_path: Path) -> bool:
        """Check if path is a VS Code extension project."""
        package_json = extension_path / "package.json"
        if not package_json.exists():
            return False

        try:
            with open(package_json) as f:
                pkg = json.load(f)
                # VS Code extensions have engines.vscode
                engines = pkg.get("engines", {})
                return "vscode" in engines
        except (json.JSONDecodeError, OSError):
            return False

    def _get_extension_info(self, extension_path: Path) -> dict:
        """Get extension name and version from package.json."""
        package_json = extension_path / "package.json"
        try:
            with open(package_json) as f:
                pkg = json.load(f)
                return {
                    "name": pkg.get("name", "extension"),
                    "version": pkg.get("version", "0.0.0"),
                    "publisher": pkg.get("publisher", "unknown"),
                    "displayName": pkg.get("displayName", pkg.get("name", "Extension")),
                }
        except (json.JSONDecodeError, OSError):
            return {"name": "extension", "version": "0.0.0", "publisher": "unknown"}

    def build_package_command(
        self,
        extension_path: Path,
        output_path: Optional[Path] = None,
    ) -> list[str]:
        """Build vsce package command."""
        cmd = self._get_base_command()
        cmd.append("package")

        # Pre-release
        if self.config.pre_release:
            cmd.append("--pre-release")

        # Dependencies
        if self.config.no_dependencies:
            cmd.append("--no-dependencies")

        # Git/version options
        if self.config.no_git_tag_version:
            cmd.append("--no-git-tag-version")
        if self.config.no_update_package_json:
            cmd.append("--no-update-package-json")

        # Yarn
        if self.config.yarn:
            cmd.append("--yarn")
        if self.config.no_yarn:
            cmd.append("--no-yarn")

        # Output
        if output_path:
            cmd.extend(["--out", str(output_path)])
        elif self.config.output_filename:
            out_dir = self.config.output_dir or "."
            output_path = Path(out_dir) / self.config.output_filename
            cmd.extend(["--out", str(output_path)])

        # Extra args
        cmd.extend(self.config.extra_args)

        return cmd

    def build_publish_command(self) -> list[str]:
        """Build vsce publish command."""
        cmd = self._get_base_command()
        cmd.append("publish")

        if self.config.pre_release:
            cmd.append("--pre-release")

        if self.config.pat:
            cmd.extend(["--pat", self.config.pat])

        if self.config.no_git_tag_version:
            cmd.append("--no-git-tag-version")
        if self.config.no_update_package_json:
            cmd.append("--no-update-package-json")

        if self.config.yarn:
            cmd.append("--yarn")
        if self.config.no_yarn:
            cmd.append("--no-yarn")

        return cmd

    def package(
        self,
        extension_path: Path,
        output_path: Optional[Path] = None,
        dry_run: bool = False,
    ) -> PackagingResult:
        """
        Package a VS Code extension.

        Args:
            extension_path: Path to the extension project
            output_path: Output path for .vsix file
            dry_run: If True, only return the command

        Returns:
            PackagingResult with vsix path
        """
        if not self.is_available():
            return PackagingResult(
                success=False,
                error_message=(
                    "vsce not available. Install with: npm install -g @vscode/vsce"
                ),
            )

        extension_path = Path(extension_path)
        if not extension_path.exists():
            return PackagingResult(
                success=False,
                error_message=f"Extension path not found: {extension_path}",
            )

        if not self._detect_extension_project(extension_path):
            return PackagingResult(
                success=False,
                error_message=f"Not a VS Code extension project: {extension_path}",
            )

        # Determine output path
        if output_path is None:
            info = self._get_extension_info(extension_path)
            filename = f"{info['name']}-{info['version']}.vsix"
            if self.config.output_dir:
                output_path = Path(self.config.output_dir) / filename
            else:
                output_path = extension_path / filename

        try:
            cmd = self.build_package_command(extension_path, output_path)
            command_str = " ".join(cmd)

            if dry_run:
                return PackagingResult(
                    success=True,
                    vsix_path=output_path,
                    command=command_str,
                    stdout=f"[DRY RUN] Would execute in {extension_path}:\n{command_str}",
                )

            logger.info(f"Packaging VS Code extension: {extension_path}")
            logger.debug(f"Command: {command_str}")

            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                cwd=extension_path,
            )

            if result.returncode == 0:
                # Find the actual vsix file
                if output_path and output_path.exists():
                    vsix_path = output_path
                else:
                    # Search for generated .vsix
                    vsix_files = list(extension_path.glob("*.vsix"))
                    vsix_path = vsix_files[0] if vsix_files else None

                return PackagingResult(
                    success=True,
                    vsix_path=vsix_path,
                    stdout=result.stdout,
                    stderr=result.stderr,
                    command=command_str,
                )
            else:
                return PackagingResult(
                    success=False,
                    error_message=f"vsce package failed with code {result.returncode}",
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
                error_message=f"Failed to execute vsce: {e}",
            )

    def publish(
        self,
        extension_path: Path,
        dry_run: bool = False,
    ) -> PackagingResult:
        """
        Publish extension to VS Code Marketplace.

        Args:
            extension_path: Path to the extension project
            dry_run: If True, only return the command

        Returns:
            PackagingResult with publish status
        """
        if not self.config.publish:
            return PackagingResult(
                success=False,
                error_message="Publishing not enabled in config",
            )

        if not self.config.pat:
            return PackagingResult(
                success=False,
                error_message="Personal Access Token (PAT) required for publishing",
            )

        try:
            cmd = self.build_publish_command()
            command_str = " ".join(cmd)

            if dry_run:
                # Don't show PAT in dry run
                safe_cmd = command_str.replace(self.config.pat, "***PAT***")
                return PackagingResult(
                    success=True,
                    command=safe_cmd,
                    stdout=f"[DRY RUN] Would execute in {extension_path}:\n{safe_cmd}",
                )

            logger.info(f"Publishing VS Code extension: {extension_path}")

            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                cwd=extension_path,
            )

            if result.returncode == 0:
                return PackagingResult(
                    success=True,
                    stdout=result.stdout,
                    stderr=result.stderr,
                    command=command_str.replace(self.config.pat, "***PAT***"),
                )
            else:
                return PackagingResult(
                    success=False,
                    error_message=f"vsce publish failed with code {result.returncode}",
                    stdout=result.stdout,
                    stderr=result.stderr,
                    command=command_str.replace(self.config.pat, "***PAT***"),
                )

        except subprocess.TimeoutExpired:
            return PackagingResult(
                success=False,
                error_message="Publishing timed out",
            )
        except OSError as e:
            return PackagingResult(
                success=False,
                error_message=f"Failed to publish: {e}",
            )

    def package_and_publish(
        self,
        extension_path: Path,
        dry_run: bool = False,
    ) -> PackagingResult:
        """
        Package and optionally publish extension.

        Args:
            extension_path: Path to the extension project
            dry_run: If True, only return commands

        Returns:
            PackagingResult
        """
        # First package
        result = self.package(extension_path, dry_run=dry_run)
        if not result.success:
            return result

        # Then publish if configured
        if self.config.publish:
            publish_result = self.publish(extension_path, dry_run=dry_run)
            if not publish_result.success:
                return publish_result
            result.stdout += "\n" + publish_result.stdout
            result.command += "\n" + publish_result.command

        return result
