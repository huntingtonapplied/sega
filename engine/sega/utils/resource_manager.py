# Copyright 2022-2026 Huntington Applied
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

"""
SEGA: Enterprise Deployment Framework
=====================================================
File: src/sega/utils/resource_manager.py
Purpose: Provides utility functions for resource management and safe subprocess operations
Dependencies: subprocess, logging, signal, contextlib, dataclasses
Authors: FLEET Development Team
Copyright: 2022-2026 Huntington Applied
License: Apache-2.0
Last Modified: 2025-07-25
"""

import subprocess
import logging
from typing import List, Optional, Dict
from contextlib import contextmanager
from dataclasses import dataclass


@dataclass
class SubprocessResult:
    """Result of subprocess execution with resource tracking."""

    returncode: int
    stdout: str
    stderr: str
    pid: Optional[int] = None
    duration: float = 0.0
    killed: bool = False


class ResourceManager:
    """Manages subprocess execution with proper cleanup and resource limits."""

    def __init__(self):
        self.logger = logging.getLogger(__name__)
        self.active_processes = set()

    def __enter__(self):
        """Context manager entry."""
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit with cleanup."""
        self.cleanup_all()

    def run_subprocess(
        self,
        cmd: List[str],
        timeout: Optional[int] = 120,
        capture_output: bool = True,
        text: bool = True,
        cwd: Optional[str] = None,
        env: Optional[Dict[str, str]] = None,
        **kwargs,
    ) -> SubprocessResult:
        """
        Run subprocess with proper resource management and cleanup.

        Args:
            cmd: Command to execute as list
            timeout: Timeout in seconds (default 120)
            capture_output: Whether to capture stdout/stderr
            text: Whether to return text output
            cwd: Working directory
            env: Environment variables
            **kwargs: Additional subprocess arguments

        Returns:
            SubprocessResult with execution details
        """
        import time

        start_time = time.time()

        try:
            # Create process with resource limits
            process = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE if capture_output else None,
                stderr=subprocess.PIPE if capture_output else None,
                text=text,
                cwd=cwd,
                env=env,
                **kwargs,
            )

            # Track active process
            self.active_processes.add(process)

            try:
                stdout, stderr = process.communicate(timeout=timeout)
                return SubprocessResult(
                    returncode=process.returncode,
                    stdout=stdout or "",
                    stderr=stderr or "",
                    pid=process.pid,
                    duration=time.time() - start_time,
                    killed=False,
                )
            except subprocess.TimeoutExpired:
                self.logger.warning(
                    f"Process {process.pid} timed out after {timeout}s, terminating"
                )
                process.terminate()

                # Give process 5 seconds to terminate gracefully
                try:
                    stdout, stderr = process.communicate(timeout=5)
                except subprocess.TimeoutExpired:
                    # Force kill if still running
                    self.logger.warning(f"Force killing process {process.pid}")
                    process.kill()
                    stdout, stderr = process.communicate()

                return SubprocessResult(
                    returncode=process.returncode or -1,
                    stdout=stdout or "",
                    stderr=stderr or "",
                    pid=process.pid,
                    duration=time.time() - start_time,
                    killed=True,
                )

        except Exception as e:
            self.logger.error(f"Subprocess execution failed: {e}")
            return SubprocessResult(
                returncode=-1,
                stdout="",
                stderr=str(e),
                duration=time.time() - start_time,
                killed=False,
            )
        finally:
            # Remove from tracking
            if "process" in locals():
                self.active_processes.discard(process)

    @contextmanager
    def docker_container(
        self,
        image: str,
        command: List[str],
        volumes: Optional[Dict[str, str]] = None,
        environment: Optional[Dict[str, str]] = None,
        remove: bool = True,
        timeout: int = 300,
    ):
        """
        Context manager for Docker container with automatic cleanup.

        Args:
            image: Docker image name
            command: Command to run in container
            volumes: Volume mappings {host_path: container_path}
            environment: Environment variables
            remove: Whether to remove container after use
            timeout: Container execution timeout
        """
        container_id = None
        try:
            # Build docker run command
            docker_cmd = ["docker", "run", "-d"]

            if remove:
                docker_cmd.append("--rm")

            # Add volumes
            if volumes:
                for host_path, container_path in volumes.items():
                    docker_cmd.extend(["-v", f"{host_path}:{container_path}"])

            # Add environment variables
            if environment:
                for key, value in environment.items():
                    docker_cmd.extend(["-e", f"{key}={value}"])

            docker_cmd.append(image)
            docker_cmd.extend(command)

            # Start container
            result = self.run_subprocess(docker_cmd, timeout=30)
            if result.returncode != 0:
                raise RuntimeError(
                    f"Failed to start container: {result.stderr}"
                )

            container_id = result.stdout.strip()
            self.logger.info(f"Started container {container_id[:12]}")

            yield container_id

        except Exception as e:
            self.logger.error(f"Container operation failed: {e}")
            raise
        finally:
            # Clean up container
            if container_id and not remove:
                try:
                    self.run_subprocess(
                        ["docker", "rm", "-f", container_id], timeout=30
                    )
                    self.logger.info(
                        f"Cleaned up container {container_id[:12]}"
                    )
                except Exception as e:
                    self.logger.warning(
                        f"Failed to cleanup container {container_id}: {e}"
                    )

    def cleanup_all(self):
        """Cleanup all active processes."""
        if not self.active_processes:
            return

        self.logger.info(
            f"Cleaning up {len(self.active_processes)} active processes"
        )

        for process in list(self.active_processes):
            try:
                if process.poll() is None:  # Still running
                    self.logger.warning(f"Terminating process {process.pid}")
                    process.terminate()

                    # Wait for graceful termination
                    try:
                        process.wait(timeout=5)
                    except subprocess.TimeoutExpired:
                        self.logger.warning(
                            f"Force killing process {process.pid}"
                        )
                        process.kill()
                        process.wait()

            except Exception as e:
                self.logger.error(
                    f"Error cleaning up process {process.pid}: {e}"
                )

        self.active_processes.clear()


# Global resource manager instance
resource_manager = ResourceManager()


def safe_subprocess(cmd: List[str], **kwargs) -> SubprocessResult:
    """Convenience function for safe subprocess execution."""
    return resource_manager.run_subprocess(cmd, **kwargs)
