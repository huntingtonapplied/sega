"""
Windows Code Signing (Authenticode)

Signs Windows executables using signtool or osslsigncode.
Supports both Windows SDK signtool and cross-platform osslsigncode.
"""

import logging
import os
import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)


@dataclass
class WindowsSigningConfig:
    """Configuration for Windows code signing."""

    # Certificate
    certificate_path: Optional[str] = None  # Path to .p12/.pfx file
    certificate_password: Optional[str] = None
    certificate_thumbprint: Optional[str] = None  # For certificate store

    # Timestamp
    timestamp_url: str = "http://timestamp.digicert.com"
    timestamp_algorithm: str = "sha256"

    # Signing
    algorithm: str = "sha256"
    description: Optional[str] = None
    description_url: Optional[str] = None

    # Tool preference
    prefer_signtool: bool = True  # Use signtool if on Windows

    @classmethod
    def from_dict(cls, data: dict) -> "WindowsSigningConfig":
        """Create config from dictionary."""
        return cls(
            certificate_path=data.get("certificate_path") or data.get("certificate"),
            certificate_password=data.get("certificate_password") or data.get("password"),
            certificate_thumbprint=data.get("certificate_thumbprint") or data.get("thumbprint"),
            timestamp_url=data.get("timestamp_url", "http://timestamp.digicert.com"),
            timestamp_algorithm=data.get("timestamp_algorithm", "sha256"),
            algorithm=data.get("algorithm", "sha256"),
            description=data.get("description"),
            description_url=data.get("description_url"),
            prefer_signtool=data.get("prefer_signtool", True),
        )

    @classmethod
    def from_env(cls) -> "WindowsSigningConfig":
        """Create config from environment variables."""
        return cls(
            certificate_path=os.environ.get("WINDOWS_CERT_PATH"),
            certificate_password=os.environ.get("WINDOWS_CERT_PASSWORD"),
            certificate_thumbprint=os.environ.get("WINDOWS_CERT_THUMBPRINT"),
            timestamp_url=os.environ.get(
                "WINDOWS_TIMESTAMP_URL", "http://timestamp.digicert.com"
            ),
        )


@dataclass
class SigningResult:
    """Result of Windows code signing."""

    success: bool
    signed_path: Optional[Path] = None
    error_message: Optional[str] = None
    stdout: str = ""
    stderr: str = ""
    command: str = ""


class WindowsSigner:
    """Windows Authenticode code signing."""

    def __init__(self, config: Optional[WindowsSigningConfig] = None):
        self.config = config or WindowsSigningConfig.from_env()
        self._signtool_path: Optional[Path] = None
        self._osslsigncode_path: Optional[Path] = None

    @property
    def signtool_path(self) -> Optional[Path]:
        """Find signtool executable."""
        if self._signtool_path is None:
            signtool = shutil.which("signtool")
            if signtool:
                self._signtool_path = Path(signtool)
            else:
                # Check common Windows SDK locations
                sdk_paths = [
                    r"C:\Program Files (x86)\Windows Kits\10\bin\x64",
                    r"C:\Program Files (x86)\Windows Kits\10\bin\10.0.19041.0\x64",
                    r"C:\Program Files (x86)\Windows Kits\8.1\bin\x64",
                ]
                for sdk_path in sdk_paths:
                    candidate = Path(sdk_path) / "signtool.exe"
                    if candidate.exists():
                        self._signtool_path = candidate
                        break
        return self._signtool_path

    @property
    def osslsigncode_path(self) -> Optional[Path]:
        """Find osslsigncode executable (cross-platform alternative)."""
        if self._osslsigncode_path is None:
            osslsigncode = shutil.which("osslsigncode")
            if osslsigncode:
                self._osslsigncode_path = Path(osslsigncode)
        return self._osslsigncode_path

    def is_available(self) -> bool:
        """Check if signing tools are available."""
        return self.signtool_path is not None or self.osslsigncode_path is not None

    def _use_signtool(self) -> bool:
        """Determine whether to use signtool or osslsigncode."""
        if self.config.prefer_signtool and self.signtool_path:
            return True
        return self.osslsigncode_path is None and self.signtool_path is not None

    def build_signtool_command(self, target: Path) -> list[str]:
        """Build signtool command."""
        if not self.signtool_path:
            raise RuntimeError("signtool not found")

        cmd = [str(self.signtool_path), "sign"]

        # Hash algorithm
        cmd.extend(["/fd", self.config.algorithm])

        # Certificate
        if self.config.certificate_path:
            cmd.extend(["/f", self.config.certificate_path])
            if self.config.certificate_password:
                cmd.extend(["/p", self.config.certificate_password])
        elif self.config.certificate_thumbprint:
            cmd.extend(["/sha1", self.config.certificate_thumbprint])

        # Timestamp
        if self.config.timestamp_url:
            cmd.extend(["/tr", self.config.timestamp_url])
            cmd.extend(["/td", self.config.timestamp_algorithm])

        # Description
        if self.config.description:
            cmd.extend(["/d", self.config.description])
        if self.config.description_url:
            cmd.extend(["/du", self.config.description_url])

        # Target
        cmd.append(str(target))

        return cmd

    def build_osslsigncode_command(
        self,
        target: Path,
        output: Optional[Path] = None,
    ) -> list[str]:
        """Build osslsigncode command."""
        if not self.osslsigncode_path:
            raise RuntimeError("osslsigncode not found")

        cmd = [str(self.osslsigncode_path), "sign"]

        # Hash algorithm
        cmd.extend(["-h", self.config.algorithm])

        # Certificate
        if self.config.certificate_path:
            cmd.extend(["-pkcs12", self.config.certificate_path])
            if self.config.certificate_password:
                cmd.extend(["-pass", self.config.certificate_password])

        # Timestamp
        if self.config.timestamp_url:
            cmd.extend(["-ts", self.config.timestamp_url])

        # Description
        if self.config.description:
            cmd.extend(["-n", self.config.description])
        if self.config.description_url:
            cmd.extend(["-i", self.config.description_url])

        # Input/Output
        cmd.extend(["-in", str(target)])
        if output:
            cmd.extend(["-out", str(output)])
        else:
            # Sign in place
            cmd.extend(["-out", str(target)])

        return cmd

    def sign(
        self,
        target: Path,
        output: Optional[Path] = None,
        dry_run: bool = False,
    ) -> SigningResult:
        """
        Sign a Windows executable.

        Args:
            target: Path to .exe, .dll, .msi, etc.
            output: Output path (osslsigncode only, signtool signs in-place)
            dry_run: If True, only return the command

        Returns:
            SigningResult with status
        """
        if not self.is_available():
            return SigningResult(
                success=False,
                error_message=(
                    "No signing tool available. "
                    "Install signtool (Windows SDK) or osslsigncode."
                ),
            )

        if not self.config.certificate_path and not self.config.certificate_thumbprint:
            return SigningResult(
                success=False,
                error_message="Certificate path or thumbprint required",
            )

        target = Path(target)
        if not target.exists():
            return SigningResult(
                success=False,
                error_message=f"Target not found: {target}",
            )

        try:
            if self._use_signtool():
                cmd = self.build_signtool_command(target)
                output_path = target
            else:
                cmd = self.build_osslsigncode_command(target, output)
                output_path = output or target

            # Mask password in command string
            command_str = " ".join(cmd)
            if self.config.certificate_password:
                command_str = command_str.replace(
                    self.config.certificate_password, "***PASSWORD***"
                )

            if dry_run:
                return SigningResult(
                    success=True,
                    signed_path=output_path,
                    command=command_str,
                    stdout=f"[DRY RUN] Would execute:\n{command_str}",
                )

            logger.info(f"Signing {target}")
            logger.debug(f"Command: {command_str}")

            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
            )

            if result.returncode == 0:
                return SigningResult(
                    success=True,
                    signed_path=output_path,
                    stdout=result.stdout,
                    stderr=result.stderr,
                    command=command_str,
                )
            else:
                return SigningResult(
                    success=False,
                    error_message=f"Signing failed with code {result.returncode}",
                    stdout=result.stdout,
                    stderr=result.stderr,
                    command=command_str,
                )

        except OSError as e:
            return SigningResult(
                success=False,
                error_message=f"Failed to execute signing tool: {e}",
            )

    def verify(self, target: Path) -> SigningResult:
        """Verify code signature."""
        target = Path(target)

        if self._use_signtool() and self.signtool_path:
            cmd = [str(self.signtool_path), "verify", "/pa", "/v", str(target)]
        elif self.osslsigncode_path:
            cmd = [str(self.osslsigncode_path), "verify", str(target)]
        else:
            return SigningResult(
                success=False,
                error_message="No verification tool available",
            )

        try:
            result = subprocess.run(cmd, capture_output=True, text=True)

            return SigningResult(
                success=result.returncode == 0,
                signed_path=target if result.returncode == 0 else None,
                error_message=None if result.returncode == 0 else "Signature invalid",
                stdout=result.stdout,
                stderr=result.stderr,
                command=" ".join(cmd),
            )

        except OSError as e:
            return SigningResult(
                success=False,
                error_message=f"Failed to verify: {e}",
            )

    def sign_directory(
        self,
        directory: Path,
        patterns: Optional[list[str]] = None,
        dry_run: bool = False,
    ) -> dict[Path, SigningResult]:
        """
        Sign all matching files in a directory.

        Args:
            directory: Directory to search
            patterns: File patterns to match (default: *.exe, *.dll, *.msi)
            dry_run: If True, only return commands

        Returns:
            Dictionary of file path -> SigningResult
        """
        patterns = patterns or ["*.exe", "*.dll", "*.msi"]
        results = {}

        directory = Path(directory)
        for pattern in patterns:
            for file in directory.glob(f"**/{pattern}"):
                results[file] = self.sign(file, dry_run=dry_run)

        return results
