"""
Bytenode Compiler Integration

Compiles Node.js/JavaScript source code to V8 bytecode.
Used for protecting frontend applications in Electron.
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
class BytenodeConfig:
    """Configuration for Bytenode compilation."""

    compress: bool = True
    electron: bool = False
    electron_version: Optional[str] = None
    no_source_map: bool = True
    output_dir: Optional[str] = None
    extra_args: list[str] = field(default_factory=list)

    @classmethod
    def from_dict(cls, data: dict) -> "BytenodeConfig":
        """Create config from dictionary."""
        return cls(
            compress=data.get("compress", True),
            electron=data.get("electron", False),
            electron_version=data.get("electron_version"),
            no_source_map=data.get("no_source_map", True),
            output_dir=data.get("output_dir"),
            extra_args=data.get("extra_args", []),
        )

    @classmethod
    def from_options_string(cls, options: str) -> "BytenodeConfig":
        """Parse options string like '--compress'."""
        config = cls()
        if "--compress" in options:
            config.compress = True
        if "--electron" in options:
            config.electron = True
        if "--no-source-map" in options:
            config.no_source_map = True
        return config


@dataclass
class CompilationResult:
    """Result of a Bytenode compilation."""

    success: bool
    output_files: list[Path] = field(default_factory=list)
    error_message: Optional[str] = None
    stdout: str = ""
    stderr: str = ""
    command: str = ""


class BytenodeCompiler:
    """Bytenode compiler for Node.js to V8 bytecode conversion."""

    def __init__(self, config: Optional[BytenodeConfig] = None):
        self.config = config or BytenodeConfig()
        self._bytenode_path: Optional[Path] = None
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
    def bytenode_path(self) -> Optional[Path]:
        """Find bytenode executable."""
        if self._bytenode_path is None:
            bytenode = shutil.which("bytenode")
            if bytenode:
                self._bytenode_path = Path(bytenode)
        return self._bytenode_path

    def is_available(self) -> bool:
        """Check if Bytenode is installed and available."""
        return self.bytenode_path is not None or self.npx_path is not None

    def get_version(self) -> Optional[str]:
        """Get Bytenode version."""
        try:
            if self.bytenode_path:
                cmd = [str(self.bytenode_path), "--version"]
            elif self.npx_path:
                cmd = [str(self.npx_path), "bytenode", "--version"]
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
        """Get base command for bytenode."""
        if self.bytenode_path:
            return [str(self.bytenode_path)]
        elif self.npx_path:
            return [str(self.npx_path), "bytenode"]
        raise RuntimeError("Bytenode not found")

    def build_command(
        self,
        source_files: list[Path],
        output_dir: Optional[Path] = None,
    ) -> list[str]:
        """Build Bytenode command from configuration."""
        cmd = self._get_base_command()
        cmd.append("--compile")

        # Options
        if self.config.compress:
            cmd.append("--compress")

        if self.config.electron:
            cmd.append("--electron")
            if self.config.electron_version:
                cmd.extend(["--electron-version", self.config.electron_version])

        if self.config.no_source_map:
            cmd.append("--no-source-map")

        # Output directory
        out_dir = output_dir or (
            Path(self.config.output_dir) if self.config.output_dir else None
        )
        if out_dir:
            cmd.extend(["--out", str(out_dir)])

        # Extra args
        cmd.extend(self.config.extra_args)

        # Source files
        for source in source_files:
            cmd.append(str(source))

        return cmd

    def compile(
        self,
        source_files: list[Path],
        output_dir: Optional[Path] = None,
        dry_run: bool = False,
    ) -> CompilationResult:
        """
        Compile JavaScript files to V8 bytecode.

        Args:
            source_files: List of JS files to compile
            output_dir: Output directory for .jsc files
            dry_run: If True, only return the command without executing

        Returns:
            CompilationResult with success status and output files
        """
        if not self.is_available():
            return CompilationResult(
                success=False,
                error_message="Bytenode is not installed. Install with: npm install -g bytenode",
            )

        # Validate source files
        valid_sources = []
        for source in source_files:
            path = Path(source)
            if not path.exists():
                logger.warning(f"Source file not found: {path}")
                continue
            if path.suffix not in [".js", ".mjs", ".cjs"]:
                logger.warning(f"Skipping non-JS file: {path}")
                continue
            valid_sources.append(path)

        if not valid_sources:
            return CompilationResult(
                success=False,
                error_message="No valid JavaScript files to compile",
            )

        try:
            cmd = self.build_command(valid_sources, output_dir)
            command_str = " ".join(cmd)

            if dry_run:
                return CompilationResult(
                    success=True,
                    command=command_str,
                    stdout=f"[DRY RUN] Would execute:\n{command_str}",
                )

            logger.info(f"Compiling {len(valid_sources)} files with Bytenode")
            logger.debug(f"Command: {command_str}")

            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
            )

            if result.returncode == 0:
                # Determine output files
                out_dir = output_dir or Path(".")
                output_files = []
                for source in valid_sources:
                    jsc_file = out_dir / f"{source.stem}.jsc"
                    if jsc_file.exists():
                        output_files.append(jsc_file)
                    else:
                        # Check in same directory as source
                        jsc_in_place = source.with_suffix(".jsc")
                        if jsc_in_place.exists():
                            output_files.append(jsc_in_place)

                return CompilationResult(
                    success=True,
                    output_files=output_files,
                    stdout=result.stdout,
                    stderr=result.stderr,
                    command=command_str,
                )
            else:
                return CompilationResult(
                    success=False,
                    error_message=f"Bytenode compilation failed with code {result.returncode}",
                    stdout=result.stdout,
                    stderr=result.stderr,
                    command=command_str,
                )

        except subprocess.TimeoutExpired:
            return CompilationResult(
                success=False,
                error_message="Bytenode compilation timed out",
            )
        except OSError as e:
            return CompilationResult(
                success=False,
                error_message=f"Failed to execute Bytenode: {e}",
            )

    def compile_directory(
        self,
        directory: Path,
        output_dir: Optional[Path] = None,
        recursive: bool = True,
        exclude_patterns: Optional[list[str]] = None,
        dry_run: bool = False,
    ) -> CompilationResult:
        """
        Compile all JavaScript files in a directory.

        Args:
            directory: Directory containing JS files
            output_dir: Output directory for .jsc files
            recursive: Search subdirectories
            exclude_patterns: Patterns to exclude (e.g., ['*.test.js', 'node_modules'])
            dry_run: If True, only return the command

        Returns:
            CompilationResult
        """
        directory = Path(directory)
        if not directory.exists():
            return CompilationResult(
                success=False,
                error_message=f"Directory not found: {directory}",
            )

        exclude_patterns = exclude_patterns or ["node_modules", "*.test.js", "*.spec.js"]

        # Find JS files
        pattern = "**/*.js" if recursive else "*.js"
        js_files = []
        for js_file in directory.glob(pattern):
            # Check exclusions
            skip = False
            for exc in exclude_patterns:
                if exc in str(js_file):
                    skip = True
                    break
            if not skip:
                js_files.append(js_file)

        if not js_files:
            return CompilationResult(
                success=False,
                error_message=f"No JavaScript files found in {directory}",
            )

        logger.info(f"Found {len(js_files)} JavaScript files to compile")
        return self.compile(js_files, output_dir, dry_run)

    def compile_electron_app(
        self,
        app_path: Path,
        output_dir: Optional[Path] = None,
        dry_run: bool = False,
    ) -> CompilationResult:
        """
        Compile an Electron application's renderer process.

        Args:
            app_path: Path to Electron app directory
            output_dir: Output directory
            dry_run: If True, only return the command

        Returns:
            CompilationResult
        """
        # Enable Electron mode
        original_electron = self.config.electron
        self.config.electron = True

        # Try to detect Electron version from package.json
        package_json = app_path / "package.json"
        if package_json.exists() and not self.config.electron_version:
            try:
                with open(package_json) as f:
                    pkg = json.load(f)
                    deps = pkg.get("dependencies", {})
                    dev_deps = pkg.get("devDependencies", {})
                    electron_ver = deps.get("electron") or dev_deps.get("electron")
                    if electron_ver:
                        # Strip leading ^ or ~
                        self.config.electron_version = electron_ver.lstrip("^~")
            except (json.JSONDecodeError, OSError):
                pass

        # Compile renderer files
        renderer_dirs = [
            app_path / "src" / "renderer",
            app_path / "renderer",
            app_path / "dist" / "renderer",
        ]

        for renderer_dir in renderer_dirs:
            if renderer_dir.exists():
                result = self.compile_directory(
                    renderer_dir,
                    output_dir,
                    exclude_patterns=["node_modules", "*.test.js", "*.d.ts"],
                    dry_run=dry_run,
                )
                self.config.electron = original_electron
                return result

        self.config.electron = original_electron
        return CompilationResult(
            success=False,
            error_message="No renderer directory found in Electron app",
        )
