"""
JavaScript Obfuscator Integration

Obfuscates JavaScript source code using javascript-obfuscator.
Used for protecting function libraries like scanner_app.
"""

import logging
import shutil
import subprocess
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)


@dataclass
class JSObfuscatorConfig:
    """Configuration for JavaScript Obfuscator."""

    # Basic options
    compact: bool = True
    control_flow_flattening: bool = False
    control_flow_flattening_threshold: float = 0.75
    dead_code_injection: bool = False
    dead_code_injection_threshold: float = 0.4

    # String options
    string_array: bool = True
    string_array_encoding: list[str] = field(default_factory=lambda: ["base64"])
    string_array_threshold: float = 0.75
    split_strings: bool = False
    split_strings_chunk_length: int = 10

    # Security options
    self_defending: bool = True
    debug_protection: bool = False
    disable_console_output: bool = False

    # Identifier options
    identifier_names_generator: str = "hexadecimal"
    rename_globals: bool = False
    rename_properties: bool = False

    # Output options
    source_map: bool = False
    output_dir: Optional[str] = None

    extra_args: list[str] = field(default_factory=list)

    @classmethod
    def from_dict(cls, data: dict) -> "JSObfuscatorConfig":
        """Create config from dictionary."""
        return cls(
            compact=data.get("compact", True),
            control_flow_flattening=data.get("control_flow_flattening", False),
            control_flow_flattening_threshold=data.get(
                "control_flow_flattening_threshold", 0.75
            ),
            dead_code_injection=data.get("dead_code_injection", False),
            dead_code_injection_threshold=data.get("dead_code_injection_threshold", 0.4),
            string_array=data.get("string_array", True),
            string_array_encoding=data.get("string_array_encoding", ["base64"]),
            string_array_threshold=data.get("string_array_threshold", 0.75),
            split_strings=data.get("split_strings", False),
            split_strings_chunk_length=data.get("split_strings_chunk_length", 10),
            self_defending=data.get("self_defending", True),
            debug_protection=data.get("debug_protection", False),
            disable_console_output=data.get("disable_console_output", False),
            identifier_names_generator=data.get(
                "identifier_names_generator", "hexadecimal"
            ),
            rename_globals=data.get("rename_globals", False),
            rename_properties=data.get("rename_properties", False),
            source_map=data.get("source_map", False),
            output_dir=data.get("output_dir"),
            extra_args=data.get("extra_args", []),
        )

    @classmethod
    def from_options_string(cls, options: str) -> "JSObfuscatorConfig":
        """Parse options string."""
        config = cls()
        if "--compact true" in options or "--compact=true" in options:
            config.compact = True
        if "--self-defending true" in options or "--self-defending=true" in options:
            config.self_defending = True
        if "--debug-protection true" in options:
            config.debug_protection = True
        if "--control-flow-flattening true" in options:
            config.control_flow_flattening = True
        return config

    @classmethod
    def preset_low(cls) -> "JSObfuscatorConfig":
        """Low obfuscation preset - minimal performance impact."""
        return cls(
            compact=True,
            control_flow_flattening=False,
            dead_code_injection=False,
            string_array=True,
            self_defending=False,
        )

    @classmethod
    def preset_medium(cls) -> "JSObfuscatorConfig":
        """Medium obfuscation preset - balanced."""
        return cls(
            compact=True,
            control_flow_flattening=True,
            control_flow_flattening_threshold=0.5,
            dead_code_injection=False,
            string_array=True,
            string_array_encoding=["base64"],
            self_defending=True,
        )

    @classmethod
    def preset_high(cls) -> "JSObfuscatorConfig":
        """High obfuscation preset - maximum protection, higher performance cost."""
        return cls(
            compact=True,
            control_flow_flattening=True,
            control_flow_flattening_threshold=0.75,
            dead_code_injection=True,
            dead_code_injection_threshold=0.4,
            string_array=True,
            string_array_encoding=["rc4"],
            string_array_threshold=0.75,
            split_strings=True,
            split_strings_chunk_length=5,
            self_defending=True,
            debug_protection=True,
            disable_console_output=True,
        )


@dataclass
class ObfuscationResult:
    """Result of a JavaScript obfuscation."""

    success: bool
    output_files: list[Path] = field(default_factory=list)
    error_message: Optional[str] = None
    stdout: str = ""
    stderr: str = ""
    command: str = ""


class JSObfuscator:
    """JavaScript Obfuscator for code protection."""

    def __init__(self, config: Optional[JSObfuscatorConfig] = None):
        self.config = config or JSObfuscatorConfig()
        self._obfuscator_path: Optional[Path] = None
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
    def obfuscator_path(self) -> Optional[Path]:
        """Find javascript-obfuscator executable."""
        if self._obfuscator_path is None:
            obf = shutil.which("javascript-obfuscator")
            if obf:
                self._obfuscator_path = Path(obf)
        return self._obfuscator_path

    def is_available(self) -> bool:
        """Check if javascript-obfuscator is installed and available."""
        return self.obfuscator_path is not None or self.npx_path is not None

    def get_version(self) -> Optional[str]:
        """Get javascript-obfuscator version."""
        try:
            if self.obfuscator_path:
                cmd = [str(self.obfuscator_path), "--version"]
            elif self.npx_path:
                cmd = [str(self.npx_path), "javascript-obfuscator", "--version"]
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
        """Get base command for javascript-obfuscator."""
        if self.obfuscator_path:
            return [str(self.obfuscator_path)]
        elif self.npx_path:
            return [str(self.npx_path), "javascript-obfuscator"]
        raise RuntimeError("javascript-obfuscator not found")

    def build_command(
        self,
        source: Path,
        output: Optional[Path] = None,
    ) -> list[str]:
        """Build javascript-obfuscator command from configuration."""
        cmd = self._get_base_command()

        # Input
        cmd.append(str(source))

        # Output
        if output:
            cmd.extend(["--output", str(output)])

        # Basic options
        cmd.extend(["--compact", str(self.config.compact).lower()])

        # Control flow
        if self.config.control_flow_flattening:
            cmd.extend(["--control-flow-flattening", "true"])
            cmd.extend([
                "--control-flow-flattening-threshold",
                str(self.config.control_flow_flattening_threshold),
            ])

        # Dead code
        if self.config.dead_code_injection:
            cmd.extend(["--dead-code-injection", "true"])
            cmd.extend([
                "--dead-code-injection-threshold",
                str(self.config.dead_code_injection_threshold),
            ])

        # String array
        if self.config.string_array:
            cmd.extend(["--string-array", "true"])
            cmd.extend([
                "--string-array-threshold",
                str(self.config.string_array_threshold),
            ])
            for encoding in self.config.string_array_encoding:
                cmd.extend(["--string-array-encoding", encoding])

        # Split strings
        if self.config.split_strings:
            cmd.extend(["--split-strings", "true"])
            cmd.extend([
                "--split-strings-chunk-length",
                str(self.config.split_strings_chunk_length),
            ])

        # Security
        if self.config.self_defending:
            cmd.extend(["--self-defending", "true"])
        if self.config.debug_protection:
            cmd.extend(["--debug-protection", "true"])
        if self.config.disable_console_output:
            cmd.extend(["--disable-console-output", "true"])

        # Identifiers
        cmd.extend([
            "--identifier-names-generator",
            self.config.identifier_names_generator,
        ])
        if self.config.rename_globals:
            cmd.extend(["--rename-globals", "true"])
        if self.config.rename_properties:
            cmd.extend(["--rename-properties", "true"])

        # Source map
        if self.config.source_map:
            cmd.extend(["--source-map", "true"])

        # Extra args
        cmd.extend(self.config.extra_args)

        return cmd

    def obfuscate(
        self,
        source_file: Path,
        output_file: Optional[Path] = None,
        dry_run: bool = False,
    ) -> ObfuscationResult:
        """
        Obfuscate a JavaScript file.

        Args:
            source_file: Path to the JS file
            output_file: Output path (defaults to source with .obfuscated.js)
            dry_run: If True, only return the command without executing

        Returns:
            ObfuscationResult with success status and output path
        """
        if not self.is_available():
            return ObfuscationResult(
                success=False,
                error_message=(
                    "javascript-obfuscator is not installed. "
                    "Install with: npm install -g javascript-obfuscator"
                ),
            )

        source_path = Path(source_file)
        if not source_path.exists():
            return ObfuscationResult(
                success=False,
                error_message=f"Source file not found: {source_path}",
            )

        if source_path.suffix not in [".js", ".mjs", ".cjs"]:
            return ObfuscationResult(
                success=False,
                error_message=f"Not a JavaScript file: {source_path}",
            )

        # Determine output path
        if output_file is None:
            output_file = source_path.with_suffix(".obfuscated.js")

        try:
            cmd = self.build_command(source_path, output_file)
            command_str = " ".join(cmd)

            if dry_run:
                return ObfuscationResult(
                    success=True,
                    command=command_str,
                    stdout=f"[DRY RUN] Would execute:\n{command_str}",
                )

            logger.info(f"Obfuscating {source_path}")
            logger.debug(f"Command: {command_str}")

            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
            )

            if result.returncode == 0:
                return ObfuscationResult(
                    success=True,
                    output_files=[Path(output_file)],
                    stdout=result.stdout,
                    stderr=result.stderr,
                    command=command_str,
                )
            else:
                return ObfuscationResult(
                    success=False,
                    error_message=f"Obfuscation failed with code {result.returncode}",
                    stdout=result.stdout,
                    stderr=result.stderr,
                    command=command_str,
                )

        except subprocess.TimeoutExpired:
            return ObfuscationResult(
                success=False,
                error_message="Obfuscation timed out",
            )
        except OSError as e:
            return ObfuscationResult(
                success=False,
                error_message=f"Failed to execute javascript-obfuscator: {e}",
            )

    def obfuscate_directory(
        self,
        directory: Path,
        output_dir: Optional[Path] = None,
        recursive: bool = True,
        exclude_patterns: Optional[list[str]] = None,
        dry_run: bool = False,
    ) -> ObfuscationResult:
        """
        Obfuscate all JavaScript files in a directory.

        Args:
            directory: Directory containing JS files
            output_dir: Output directory (mirrors structure)
            recursive: Search subdirectories
            exclude_patterns: Patterns to exclude
            dry_run: If True, only return commands

        Returns:
            ObfuscationResult
        """
        directory = Path(directory)
        if not directory.exists():
            return ObfuscationResult(
                success=False,
                error_message=f"Directory not found: {directory}",
            )

        exclude_patterns = exclude_patterns or [
            "node_modules",
            "*.test.js",
            "*.spec.js",
            "*.min.js",
            "*.obfuscated.js",
        ]

        # Find JS files
        pattern = "**/*.js" if recursive else "*.js"
        js_files = []
        for js_file in directory.glob(pattern):
            skip = False
            for exc in exclude_patterns:
                if exc.startswith("*"):
                    if js_file.name.endswith(exc[1:]):
                        skip = True
                        break
                elif exc in str(js_file):
                    skip = True
                    break
            if not skip:
                js_files.append(js_file)

        if not js_files:
            return ObfuscationResult(
                success=False,
                error_message=f"No JavaScript files found in {directory}",
            )

        logger.info(f"Found {len(js_files)} JavaScript files to obfuscate")

        output_files = []
        errors = []
        commands = []

        for js_file in js_files:
            # Calculate output path
            if output_dir:
                rel_path = js_file.relative_to(directory)
                out_file = output_dir / rel_path
                out_file.parent.mkdir(parents=True, exist_ok=True)
            else:
                out_file = js_file.with_suffix(".obfuscated.js")

            result = self.obfuscate(js_file, out_file, dry_run)
            commands.append(result.command)

            if result.success:
                output_files.extend(result.output_files)
            else:
                errors.append(f"{js_file}: {result.error_message}")

        if errors:
            return ObfuscationResult(
                success=False,
                output_files=output_files,
                error_message=f"Some files failed: {'; '.join(errors)}",
                command="\n".join(commands),
            )

        return ObfuscationResult(
            success=True,
            output_files=output_files,
            command="\n".join(commands),
        )
