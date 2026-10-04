"""
Linux Code Signing (GPG)

Signs Linux binaries and packages using GPG.
Produces detached signatures for verification.
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
class LinuxSigningConfig:
    """Configuration for Linux GPG signing."""

    # GPG key
    key_id: Optional[str] = None  # Key ID or email
    passphrase: Optional[str] = None

    # Options
    armor: bool = True  # ASCII armor output
    detach_sign: bool = True  # Detached signature
    digest_algo: str = "SHA256"

    # GPG home directory (optional)
    gnupg_home: Optional[str] = None

    @classmethod
    def from_dict(cls, data: dict) -> "LinuxSigningConfig":
        """Create config from dictionary."""
        return cls(
            key_id=data.get("key_id") or data.get("gpg_key"),
            passphrase=data.get("passphrase") or data.get("gpg_passphrase"),
            armor=data.get("armor", True),
            detach_sign=data.get("detach_sign", True),
            digest_algo=data.get("digest_algo", "SHA256"),
            gnupg_home=data.get("gnupg_home"),
        )

    @classmethod
    def from_env(cls) -> "LinuxSigningConfig":
        """Create config from environment variables."""
        return cls(
            key_id=os.environ.get("GPG_KEY_ID"),
            passphrase=os.environ.get("GPG_PASSPHRASE"),
            gnupg_home=os.environ.get("GNUPGHOME"),
        )


@dataclass
class SigningResult:
    """Result of GPG signing operation."""

    success: bool
    signature_path: Optional[Path] = None
    error_message: Optional[str] = None
    stdout: str = ""
    stderr: str = ""
    command: str = ""


class LinuxSigner:
    """Linux GPG code signing."""

    def __init__(self, config: Optional[LinuxSigningConfig] = None):
        self.config = config or LinuxSigningConfig.from_env()
        self._gpg_path: Optional[Path] = None

    @property
    def gpg_path(self) -> Optional[Path]:
        """Find gpg executable."""
        if self._gpg_path is None:
            gpg = shutil.which("gpg") or shutil.which("gpg2")
            if gpg:
                self._gpg_path = Path(gpg)
        return self._gpg_path

    def is_available(self) -> bool:
        """Check if GPG is available."""
        return self.gpg_path is not None

    def get_version(self) -> Optional[str]:
        """Get GPG version."""
        if not self.gpg_path:
            return None
        try:
            result = subprocess.run(
                [str(self.gpg_path), "--version"],
                capture_output=True,
                text=True,
                timeout=10,
            )
            if result.returncode == 0:
                return result.stdout.split("\n")[0]
        except (subprocess.TimeoutExpired, OSError):
            pass
        return None

    def list_keys(self) -> list[dict]:
        """List available GPG keys."""
        if not self.gpg_path:
            return []

        cmd = [str(self.gpg_path), "--list-keys", "--keyid-format", "long"]
        if self.config.gnupg_home:
            cmd.extend(["--homedir", self.config.gnupg_home])

        try:
            result = subprocess.run(cmd, capture_output=True, text=True)
            if result.returncode == 0:
                keys = []
                lines = result.stdout.strip().split("\n")
                for i, line in enumerate(lines):
                    if line.startswith("pub"):
                        parts = line.split()
                        if len(parts) >= 2:
                            # Extract key info
                            key_info = parts[1].split("/")
                            uid = ""
                            if i + 1 < len(lines) and lines[i + 1].strip().startswith("uid"):
                                uid = lines[i + 1].split("]")[-1].strip()
                            keys.append({
                                "type": key_info[0] if len(key_info) > 0 else "",
                                "id": key_info[1] if len(key_info) > 1 else parts[1],
                                "uid": uid,
                            })
                return keys
        except OSError:
            pass
        return []

    def build_sign_command(
        self,
        target: Path,
        output: Optional[Path] = None,
    ) -> list[str]:
        """Build GPG sign command."""
        if not self.gpg_path:
            raise RuntimeError("gpg not found")

        cmd = [str(self.gpg_path)]

        # GPG home
        if self.config.gnupg_home:
            cmd.extend(["--homedir", self.config.gnupg_home])

        # Batch mode for non-interactive
        cmd.append("--batch")

        # Passphrase
        if self.config.passphrase:
            cmd.extend(["--passphrase-fd", "0"])
            cmd.append("--pinentry-mode=loopback")

        # Key
        if self.config.key_id:
            cmd.extend(["--local-user", self.config.key_id])

        # Digest algorithm
        cmd.extend(["--digest-algo", self.config.digest_algo])

        # Signature type
        if self.config.detach_sign:
            cmd.append("--detach-sign")
        else:
            cmd.append("--sign")

        # Armor (ASCII output)
        if self.config.armor:
            cmd.append("--armor")

        # Output
        if output:
            cmd.extend(["--output", str(output)])

        # Input
        cmd.append(str(target))

        return cmd

    def sign(
        self,
        target: Path,
        output: Optional[Path] = None,
        dry_run: bool = False,
    ) -> SigningResult:
        """
        Sign a file with GPG.

        Args:
            target: Path to file to sign
            output: Output path for signature (default: target.asc or target.sig)
            dry_run: If True, only return the command

        Returns:
            SigningResult with signature path
        """
        if not self.is_available():
            return SigningResult(
                success=False,
                error_message="GPG not available. Install gnupg.",
            )

        target = Path(target)
        if not target.exists():
            return SigningResult(
                success=False,
                error_message=f"Target not found: {target}",
            )

        # Determine output path
        if output is None:
            if self.config.armor:
                output = target.with_suffix(target.suffix + ".asc")
            else:
                output = target.with_suffix(target.suffix + ".sig")

        try:
            cmd = self.build_sign_command(target, output)

            # Mask passphrase in command string
            command_str = " ".join(cmd)

            if dry_run:
                return SigningResult(
                    success=True,
                    signature_path=output,
                    command=command_str,
                    stdout=f"[DRY RUN] Would execute:\n{command_str}",
                )

            logger.info(f"Signing {target}")
            logger.debug(f"Command: {command_str}")

            # Run with passphrase on stdin if provided
            if self.config.passphrase:
                result = subprocess.run(
                    cmd,
                    input=self.config.passphrase,
                    capture_output=True,
                    text=True,
                )
            else:
                result = subprocess.run(
                    cmd,
                    capture_output=True,
                    text=True,
                )

            if result.returncode == 0:
                return SigningResult(
                    success=True,
                    signature_path=output,
                    stdout=result.stdout,
                    stderr=result.stderr,
                    command=command_str,
                )
            else:
                return SigningResult(
                    success=False,
                    error_message=f"GPG signing failed with code {result.returncode}",
                    stdout=result.stdout,
                    stderr=result.stderr,
                    command=command_str,
                )

        except OSError as e:
            return SigningResult(
                success=False,
                error_message=f"Failed to execute GPG: {e}",
            )

    def verify(
        self,
        target: Path,
        signature: Optional[Path] = None,
    ) -> SigningResult:
        """
        Verify a GPG signature.

        Args:
            target: Path to the signed file
            signature: Path to signature file (default: target.asc or target.sig)

        Returns:
            SigningResult with verification status
        """
        if not self.gpg_path:
            return SigningResult(
                success=False,
                error_message="GPG not available",
            )

        target = Path(target)

        # Find signature file
        if signature is None:
            for ext in [".asc", ".sig", ".gpg"]:
                candidate = target.with_suffix(target.suffix + ext)
                if candidate.exists():
                    signature = candidate
                    break

        if signature is None or not Path(signature).exists():
            return SigningResult(
                success=False,
                error_message="Signature file not found",
            )

        cmd = [str(self.gpg_path), "--verify", str(signature), str(target)]
        if self.config.gnupg_home:
            cmd.insert(1, f"--homedir={self.config.gnupg_home}")

        try:
            result = subprocess.run(cmd, capture_output=True, text=True)

            return SigningResult(
                success=result.returncode == 0,
                signature_path=signature if result.returncode == 0 else None,
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
            patterns: File patterns to match
            dry_run: If True, only return commands

        Returns:
            Dictionary of file path -> SigningResult
        """
        patterns = patterns or ["*.tar.gz", "*.tar.xz", "*.deb", "*.rpm", "*.AppImage"]
        results = {}

        directory = Path(directory)
        for pattern in patterns:
            for file in directory.glob(f"**/{pattern}"):
                results[file] = self.sign(file, dry_run=dry_run)

        return results

    def create_checksum(
        self,
        target: Path,
        algorithms: Optional[list[str]] = None,
    ) -> dict[str, str]:
        """
        Create checksums for a file (commonly used alongside GPG signatures).

        Args:
            target: Path to file
            algorithms: Hash algorithms (default: sha256, sha512)

        Returns:
            Dictionary of algorithm -> hash value
        """
        import hashlib

        algorithms = algorithms or ["sha256", "sha512"]
        checksums = {}

        target = Path(target)
        if not target.exists():
            return checksums

        for algo in algorithms:
            try:
                hasher = hashlib.new(algo)
                with open(target, "rb") as f:
                    for chunk in iter(lambda: f.read(8192), b""):
                        hasher.update(chunk)
                checksums[algo] = hasher.hexdigest()
            except (ValueError, OSError):
                pass

        return checksums

    def write_checksum_file(
        self,
        target: Path,
        algorithms: Optional[list[str]] = None,
    ) -> Optional[Path]:
        """
        Write checksums to a file (e.g., SHA256SUMS).

        Args:
            target: Path to file
            algorithms: Hash algorithms

        Returns:
            Path to checksum file
        """
        checksums = self.create_checksum(target, algorithms)
        if not checksums:
            return None

        target = Path(target)
        for algo, hash_value in checksums.items():
            checksum_file = target.parent / f"{algo.upper()}SUMS"
            line = f"{hash_value}  {target.name}\n"

            # Append or create
            mode = "a" if checksum_file.exists() else "w"
            with open(checksum_file, mode) as f:
                f.write(line)

        # Return path to first checksum file
        return target.parent / f"{list(checksums.keys())[0].upper()}SUMS"
