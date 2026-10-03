"""
macOS Code Signing and Notarization

Signs macOS applications using codesign and handles
Apple notarization for distribution outside the App Store.
"""

import logging
import os
import plistlib
import shutil
import subprocess
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)


@dataclass
class MacSigningConfig:
    """Configuration for macOS code signing."""

    # Signing identity
    identity: str = ""  # "Developer ID Application: Company Name (TEAMID)"
    team_id: Optional[str] = None

    # Notarization
    notarize: bool = False
    apple_id: Optional[str] = None
    app_specific_password: Optional[str] = None
    notarization_team_id: Optional[str] = None

    # Options
    entitlements: Optional[str] = None
    hardened_runtime: bool = True
    timestamp: bool = True
    deep: bool = True
    force: bool = True
    options: list[str] = field(default_factory=lambda: ["runtime"])

    @classmethod
    def from_dict(cls, data: dict) -> "MacSigningConfig":
        """Create config from dictionary."""
        return cls(
            identity=data.get("identity", ""),
            team_id=data.get("team_id"),
            notarize=data.get("notarize", False),
            apple_id=data.get("apple_id"),
            app_specific_password=data.get("app_specific_password"),
            notarization_team_id=data.get("notarization_team_id"),
            entitlements=data.get("entitlements"),
            hardened_runtime=data.get("hardened_runtime", True),
            timestamp=data.get("timestamp", True),
            deep=data.get("deep", True),
            force=data.get("force", True),
            options=data.get("options", ["runtime"]),
        )

    @classmethod
    def from_env(cls) -> "MacSigningConfig":
        """Create config from environment variables."""
        return cls(
            identity=os.environ.get("MAC_SIGNING_IDENTITY", ""),
            team_id=os.environ.get("APPLE_TEAM_ID"),
            notarize=os.environ.get("MAC_NOTARIZE", "").lower() == "true",
            apple_id=os.environ.get("APPLE_ID"),
            app_specific_password=os.environ.get("APPLE_APP_SPECIFIC_PASSWORD"),
            notarization_team_id=os.environ.get("APPLE_TEAM_ID"),
        )


@dataclass
class SigningResult:
    """Result of code signing operation."""

    success: bool
    signed_path: Optional[Path] = None
    error_message: Optional[str] = None
    stdout: str = ""
    stderr: str = ""
    command: str = ""
    notarization_status: Optional[str] = None


class MacSigner:
    """macOS code signing and notarization."""

    def __init__(self, config: Optional[MacSigningConfig] = None):
        self.config = config or MacSigningConfig.from_env()
        self._codesign_path: Optional[Path] = None
        self._xcrun_path: Optional[Path] = None

    @property
    def codesign_path(self) -> Optional[Path]:
        """Find codesign executable."""
        if self._codesign_path is None:
            codesign = shutil.which("codesign")
            if codesign:
                self._codesign_path = Path(codesign)
        return self._codesign_path

    @property
    def xcrun_path(self) -> Optional[Path]:
        """Find xcrun executable."""
        if self._xcrun_path is None:
            xcrun = shutil.which("xcrun")
            if xcrun:
                self._xcrun_path = Path(xcrun)
        return self._xcrun_path

    def is_available(self) -> bool:
        """Check if signing tools are available."""
        return self.codesign_path is not None

    def list_identities(self) -> list[str]:
        """List available signing identities."""
        try:
            result = subprocess.run(
                ["security", "find-identity", "-v", "-p", "codesigning"],
                capture_output=True,
                text=True,
            )
            if result.returncode == 0:
                identities = []
                for line in result.stdout.strip().split("\n"):
                    if ")" in line and '"' in line:
                        # Extract identity name
                        start = line.find('"') + 1
                        end = line.rfind('"')
                        if start < end:
                            identities.append(line[start:end])
                return identities
        except OSError:
            pass
        return []

    def build_sign_command(
        self,
        target: Path,
        identity: Optional[str] = None,
    ) -> list[str]:
        """Build codesign command."""
        if not self.codesign_path:
            raise RuntimeError("codesign not found")

        cmd = [str(self.codesign_path)]

        # Force re-sign
        if self.config.force:
            cmd.append("--force")

        # Deep signing (sign nested code)
        if self.config.deep:
            cmd.append("--deep")

        # Timestamp
        if self.config.timestamp:
            cmd.append("--timestamp")

        # Options (e.g., runtime for hardened runtime)
        for opt in self.config.options:
            cmd.extend(["--options", opt])

        # Entitlements
        if self.config.entitlements:
            cmd.extend(["--entitlements", self.config.entitlements])

        # Identity
        signing_identity = identity or self.config.identity
        if signing_identity:
            cmd.extend(["--sign", signing_identity])
        else:
            cmd.extend(["--sign", "-"])  # Ad-hoc signing

        # Target
        cmd.append(str(target))

        return cmd

    def sign(
        self,
        target: Path,
        identity: Optional[str] = None,
        dry_run: bool = False,
    ) -> SigningResult:
        """
        Sign a macOS application or binary.

        Args:
            target: Path to .app bundle or binary
            identity: Signing identity (uses config default if not provided)
            dry_run: If True, only return the command

        Returns:
            SigningResult with status
        """
        if not self.is_available():
            return SigningResult(
                success=False,
                error_message="codesign not available (not on macOS?)",
            )

        target = Path(target)
        if not target.exists():
            return SigningResult(
                success=False,
                error_message=f"Target not found: {target}",
            )

        try:
            cmd = self.build_sign_command(target, identity)
            command_str = " ".join(cmd)

            if dry_run:
                return SigningResult(
                    success=True,
                    signed_path=target,
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
                    signed_path=target,
                    stdout=result.stdout,
                    stderr=result.stderr,
                    command=command_str,
                )
            else:
                return SigningResult(
                    success=False,
                    error_message=f"codesign failed with code {result.returncode}",
                    stdout=result.stdout,
                    stderr=result.stderr,
                    command=command_str,
                )

        except OSError as e:
            return SigningResult(
                success=False,
                error_message=f"Failed to execute codesign: {e}",
            )

    def verify(self, target: Path) -> SigningResult:
        """Verify code signature."""
        if not self.codesign_path:
            return SigningResult(
                success=False,
                error_message="codesign not available",
            )

        try:
            cmd = [
                str(self.codesign_path),
                "--verify",
                "--deep",
                "--strict",
                "--verbose=2",
                str(target),
            ]

            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
            )

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

    def notarize(
        self,
        target: Path,
        dry_run: bool = False,
    ) -> SigningResult:
        """
        Submit app for Apple notarization.

        Args:
            target: Path to .app, .dmg, or .zip to notarize
            dry_run: If True, only return the command

        Returns:
            SigningResult with notarization status
        """
        if not self.config.notarize:
            return SigningResult(
                success=False,
                error_message="Notarization not enabled in config",
            )

        if not self.config.apple_id or not self.config.app_specific_password:
            return SigningResult(
                success=False,
                error_message="Apple ID and app-specific password required for notarization",
            )

        if not self.xcrun_path:
            return SigningResult(
                success=False,
                error_message="xcrun not available",
            )

        target = Path(target)

        # Build notarytool command
        cmd = [
            str(self.xcrun_path),
            "notarytool",
            "submit",
            str(target),
            "--apple-id",
            self.config.apple_id,
            "--password",
            self.config.app_specific_password,
            "--wait",
        ]

        if self.config.notarization_team_id:
            cmd.extend(["--team-id", self.config.notarization_team_id])

        # Mask password in command string
        command_str = " ".join(cmd).replace(
            self.config.app_specific_password, "***PASSWORD***"
        )

        if dry_run:
            return SigningResult(
                success=True,
                command=command_str,
                stdout=f"[DRY RUN] Would execute:\n{command_str}",
            )

        try:
            logger.info(f"Notarizing {target}")

            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
            )

            if result.returncode == 0:
                return SigningResult(
                    success=True,
                    signed_path=target,
                    stdout=result.stdout,
                    stderr=result.stderr,
                    command=command_str,
                    notarization_status="Accepted",
                )
            else:
                return SigningResult(
                    success=False,
                    error_message="Notarization failed",
                    stdout=result.stdout,
                    stderr=result.stderr,
                    command=command_str,
                    notarization_status="Rejected",
                )

        except OSError as e:
            return SigningResult(
                success=False,
                error_message=f"Failed to notarize: {e}",
            )

    def staple(self, target: Path, dry_run: bool = False) -> SigningResult:
        """Staple notarization ticket to the app."""
        if not self.xcrun_path:
            return SigningResult(
                success=False,
                error_message="xcrun not available",
            )

        cmd = [str(self.xcrun_path), "stapler", "staple", str(target)]
        command_str = " ".join(cmd)

        if dry_run:
            return SigningResult(
                success=True,
                command=command_str,
                stdout=f"[DRY RUN] Would execute:\n{command_str}",
            )

        try:
            result = subprocess.run(cmd, capture_output=True, text=True)

            return SigningResult(
                success=result.returncode == 0,
                signed_path=target if result.returncode == 0 else None,
                error_message=None if result.returncode == 0 else "Stapling failed",
                stdout=result.stdout,
                stderr=result.stderr,
                command=command_str,
            )

        except OSError as e:
            return SigningResult(
                success=False,
                error_message=f"Failed to staple: {e}",
            )

    def sign_and_notarize(
        self,
        target: Path,
        identity: Optional[str] = None,
        dry_run: bool = False,
    ) -> SigningResult:
        """
        Sign and notarize an application.

        Args:
            target: Path to .app bundle
            identity: Signing identity
            dry_run: If True, only return commands

        Returns:
            SigningResult
        """
        # Sign
        sign_result = self.sign(target, identity, dry_run)
        if not sign_result.success:
            return sign_result

        # Notarize if configured
        if self.config.notarize:
            notarize_result = self.notarize(target, dry_run)
            if not notarize_result.success:
                return notarize_result

            # Staple
            staple_result = self.staple(target, dry_run)
            sign_result.stdout += f"\n{notarize_result.stdout}\n{staple_result.stdout}"
            sign_result.command += f"\n{notarize_result.command}\n{staple_result.command}"
            sign_result.notarization_status = notarize_result.notarization_status

        return sign_result
