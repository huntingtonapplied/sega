#!/usr/bin/env python3
"""
SEGA SSH Utility Module
=======================
Provides SSH connection and remote command execution utilities.

Usage:
    from sega.utils.ssh import SSHExecutor

    executor = SSHExecutor(host="203.0.113.10", user="ubuntu", key_path="~/.ssh/id_rsa")
    result = executor.execute("curl -s http://localhost:8004/health")
"""

import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Optional, List, Tuple


@dataclass
class SSHResult:
    """Result of SSH command execution."""

    success: bool
    stdout: str
    stderr: str
    exit_code: int
    command: str


class SSHExecutor:
    """
    Execute commands on remote hosts via SSH.

    Uses subprocess with ssh command for maximum compatibility.
    """

    def __init__(
        self,
        host: str,
        user: str = "ubuntu",
        key_path: Optional[str] = None,
        timeout: int = 30,
        verbose: bool = False,
    ):
        """
        Initialize SSH executor.

        Args:
            host: Remote host IP or hostname
            user: SSH username
            key_path: Path to SSH private key (defaults to ~/.ssh/id_rsa)
            timeout: Command timeout in seconds
            verbose: Enable verbose output
        """
        self.host = host
        self.user = user
        self.timeout = timeout
        self.verbose = verbose

        # Resolve key path
        if key_path:
            self.key_path = Path(key_path).expanduser()
        else:
            self.key_path = Path("~/.ssh/id_rsa").expanduser()

        if not self.key_path.exists():
            raise FileNotFoundError(f"SSH key not found: {self.key_path}")

    def execute(self, command: str) -> SSHResult:
        """
        Execute command on remote host.

        Args:
            command: Shell command to execute

        Returns:
            SSHResult with command output and status
        """
        ssh_cmd = self._build_ssh_command(command)

        if self.verbose:
            print(f"SSH: {self.user}@{self.host} $ {command}")

        try:
            result = subprocess.run(
                ssh_cmd,
                capture_output=True,
                text=True,
                timeout=self.timeout,
            )

            return SSHResult(
                success=result.returncode == 0,
                stdout=result.stdout,
                stderr=result.stderr,
                exit_code=result.returncode,
                command=command,
            )

        except subprocess.TimeoutExpired:
            return SSHResult(
                success=False,
                stdout="",
                stderr=f"Command timed out after {self.timeout}s",
                exit_code=-1,
                command=command,
            )

        except Exception as e:
            return SSHResult(
                success=False,
                stdout="",
                stderr=str(e),
                exit_code=-1,
                command=command,
            )

    def test_connection(self) -> bool:
        """
        Test SSH connection to host.

        Returns:
            True if connection successful, False otherwise
        """
        result = self.execute("echo 'test'")
        return result.success and result.stdout.strip() == "test"

    def _build_ssh_command(self, remote_command: str) -> List[str]:
        """Build SSH command with all options."""
        cmd = [
            "ssh",
            "-i",
            str(self.key_path),
            "-o",
            "StrictHostKeyChecking=no",
            "-o",
            "UserKnownHostsFile=/dev/null",
            "-o",
            "LogLevel=ERROR",
            "-o",
            f"ConnectTimeout={self.timeout}",
            f"{self.user}@{self.host}",
            remote_command,
        ]
        return cmd


def test_ssh_connection(host: str, user: str = "ubuntu", key_path: Optional[str] = None) -> Tuple[bool, str]:
    """
    Test SSH connection to a host.

    Args:
        host: Remote host IP or hostname
        user: SSH username
        key_path: Path to SSH private key

    Returns:
        Tuple of (success, message)
    """
    try:
        executor = SSHExecutor(host=host, user=user, key_path=key_path)
        if executor.test_connection():
            return True, f"SSH connection to {user}@{host} successful"
        else:
            return False, f"SSH connection to {user}@{host} failed"
    except Exception as e:
        return False, f"SSH connection error: {e}"
