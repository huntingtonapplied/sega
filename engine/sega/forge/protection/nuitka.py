"""
Nuitka Compiler Integration

Compiles Python source code to standalone binaries using Nuitka.
Supports engines, backends, and CLI utilities.
"""

import logging
import platform as _platform
import shutil
import subprocess
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)


@dataclass
class NuitkaConfig:
    """Configuration for Nuitka compilation."""

    standalone: bool = True
    onefile: bool = True
    # module=True compiles a Python *package* into a single importable C-extension
    # (`<pkg>.so`/`.pyd`) instead of a standalone binary. This is the mode for shipping
    # an obfuscated engine that a customer still `import`s as a normal module — the source
    # is compiled to machine code, no `.py` is delivered. Mutually exclusive with onefile.
    module: bool = False
    follow_imports: bool = True
    include_data_dir: list[str] = field(default_factory=list)
    include_data_files: list[str] = field(default_factory=list)
    include_package: list[str] = field(default_factory=list)
    enable_plugins: list[str] = field(default_factory=list)
    disable_console: bool = False
    output_dir: Optional[str] = None
    output_filename: Optional[str] = None
    extra_args: list[str] = field(default_factory=list)

    @classmethod
    def from_dict(cls, data: dict) -> "NuitkaConfig":
        """Create config from dictionary (e.g., from sega.yaml)."""
        return cls(
            standalone=data.get("standalone", True),
            onefile=data.get("onefile", True),
            module=data.get("module", False),
            follow_imports=data.get("follow_imports", True),
            include_data_dir=data.get("include_data_dir", []),
            include_data_files=data.get("include_data_files", []),
            include_package=data.get("include_package", []),
            enable_plugins=data.get("enable_plugins", []),
            disable_console=data.get("disable_console", False),
            output_dir=data.get("output_dir"),
            output_filename=data.get("output_filename"),
            extra_args=data.get("extra_args", []),
        )

    @classmethod
    def from_options_string(cls, options: str) -> "NuitkaConfig":
        """Parse options string like '--standalone --onefile'."""
        config = cls()
        if "--module" in options:
            # Module mode is exclusive with the standalone-binary flags.
            config.module = True
            config.standalone = False
            config.onefile = False
        if "--standalone" in options:
            config.standalone = True
        if "--onefile" in options:
            config.onefile = True
        if "--no-follow-imports" in options:
            config.follow_imports = False
        if "--disable-console" in options or "--windows-disable-console" in options:
            config.disable_console = True
        return config


@dataclass
class CompilationResult:
    """Result of a Nuitka compilation."""

    success: bool
    output_path: Optional[Path] = None
    error_message: Optional[str] = None
    stdout: str = ""
    stderr: str = ""
    command: str = ""


class NuitkaCompiler:
    """Nuitka compiler for Python to binary conversion."""

    def __init__(self, config: Optional[NuitkaConfig] = None):
        self.config = config or NuitkaConfig()
        self._nuitka_path: Optional[Path] = None

    @property
    def nuitka_path(self) -> Optional[Path]:
        """Find nuitka executable."""
        if self._nuitka_path is None:
            nuitka = shutil.which("nuitka") or shutil.which("nuitka3")
            if nuitka:
                self._nuitka_path = Path(nuitka)
        return self._nuitka_path

    def is_available(self) -> bool:
        """Check if Nuitka is installed and available."""
        return self.nuitka_path is not None

    def get_version(self) -> Optional[str]:
        """Get Nuitka version."""
        if not self.is_available():
            return None
        try:
            result = subprocess.run(
                [str(self.nuitka_path), "--version"],
                capture_output=True,
                text=True,
                timeout=30,
            )
            if result.returncode == 0:
                return result.stdout.strip().split("\n")[0]
        except (subprocess.TimeoutExpired, OSError):
            pass
        return None

    def build_command(
        self,
        source_file: Path,
        output_dir: Optional[Path] = None,
        output_filename: Optional[str] = None,
    ) -> list[str]:
        """Build Nuitka command from configuration."""
        if not self.nuitka_path:
            raise RuntimeError("Nuitka not found")

        cmd = [str(self.nuitka_path)]

        # Core options
        if self.config.module:
            # Compile a package to one importable `<pkg>.so` (obfuscated, no source
            # shipped). Exclusive with --standalone/--onefile. Submodules are pulled in
            # via --include-package (set by the caller), not --follow-imports.
            cmd.append("--module")
        else:
            if self.config.standalone:
                cmd.append("--standalone")
            if self.config.onefile:
                cmd.append("--onefile")
            if self.config.follow_imports:
                cmd.append("--follow-imports")

        # Output configuration
        out_dir = output_dir or (
            Path(self.config.output_dir) if self.config.output_dir else None
        )
        if out_dir:
            cmd.extend(["--output-dir", str(out_dir)])

        out_name = output_filename or self.config.output_filename
        if out_name:
            cmd.extend(["--output-filename", out_name])

        # Data inclusion
        for data_dir in self.config.include_data_dir:
            cmd.extend(["--include-data-dir", data_dir])
        for data_file in self.config.include_data_files:
            cmd.extend(["--include-data-files", data_file])

        # Package inclusion
        for package in self.config.include_package:
            cmd.extend(["--include-package", package])

        # Plugins
        for plugin in self.config.enable_plugins:
            cmd.extend(["--enable-plugin", plugin])

        # Platform-specific
        if self.config.disable_console:
            cmd.append("--windows-disable-console")

        # Extra args
        cmd.extend(self.config.extra_args)

        # Source file
        cmd.append(str(source_file))

        return cmd

    def compile(
        self,
        source_file: Path,
        output_dir: Optional[Path] = None,
        output_filename: Optional[str] = None,
        dry_run: bool = False,
    ) -> CompilationResult:
        """
        Compile Python source to binary.

        Args:
            source_file: Path to the Python source file or directory
            output_dir: Output directory for compiled binary
            output_filename: Name for the output binary
            dry_run: If True, only return the command without executing

        Returns:
            CompilationResult with success status and output path
        """
        if not self.is_available():
            return CompilationResult(
                success=False,
                error_message="Nuitka is not installed. Install with: pip install nuitka",
            )

        source_path = Path(source_file)
        if not source_path.exists():
            return CompilationResult(
                success=False,
                error_message=f"Source file not found: {source_path}",
            )

        try:
            cmd = self.build_command(source_path, output_dir, output_filename)
            command_str = " ".join(cmd)

            if dry_run:
                return CompilationResult(
                    success=True,
                    command=command_str,
                    stdout=f"[DRY RUN] Would execute:\n{command_str}",
                )

            logger.info(f"Compiling {source_path} with Nuitka")
            logger.debug(f"Command: {command_str}")

            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                cwd=source_path.parent if source_path.is_file() else source_path,
            )

            if result.returncode == 0:
                # Determine output path
                out_dir = output_dir or Path(self.config.output_dir or ".")
                # For a package, Nuitka names the artifact after the package dir, not the
                # __init__.py file — use the parent dir name when the source is __init__.py.
                pkg_stem = (
                    source_path.parent.name
                    if source_path.name == "__init__.py"
                    else source_path.stem
                )
                if self.config.module:
                    # Nuitka emits `<pkg>.so` (or `.pyd` on Windows) for --module.
                    ext = ".pyd" if _platform.system() == "Windows" else ".so"
                    output_path = out_dir / f"{pkg_stem}{ext}"
                elif self.config.onefile:
                    binary_name = output_filename or source_path.stem
                    output_path = out_dir / binary_name
                else:
                    output_path = out_dir / f"{source_path.stem}.dist"

                return CompilationResult(
                    success=True,
                    output_path=output_path,
                    stdout=result.stdout,
                    stderr=result.stderr,
                    command=command_str,
                )
            else:
                return CompilationResult(
                    success=False,
                    error_message=f"Nuitka compilation failed with code {result.returncode}",
                    stdout=result.stdout,
                    stderr=result.stderr,
                    command=command_str,
                )

        except subprocess.TimeoutExpired:
            return CompilationResult(
                success=False,
                error_message="Nuitka compilation timed out",
            )
        except OSError as e:
            return CompilationResult(
                success=False,
                error_message=f"Failed to execute Nuitka: {e}",
            )

    def compile_project(
        self,
        project_path: Path,
        entry_point: str = "__main__.py",
        output_dir: Optional[Path] = None,
        dry_run: bool = False,
    ) -> CompilationResult:
        """
        Compile a Python project.

        Args:
            project_path: Path to the project directory
            entry_point: Entry point file relative to project_path
            output_dir: Output directory
            dry_run: If True, only return the command

        Returns:
            CompilationResult
        """
        source_file = project_path / entry_point
        if not source_file.exists():
            # Try common entry points
            for alt in ["main.py", "app.py", "cli.py", "__main__.py"]:
                alt_path = project_path / alt
                if alt_path.exists():
                    source_file = alt_path
                    break
            else:
                return CompilationResult(
                    success=False,
                    error_message=f"Entry point not found: {entry_point}",
                )

        return self.compile(source_file, output_dir, dry_run=dry_run)
