#!/usr/bin/env python3
"""
SEGA Instance Localhost Test Runner
====================================
Tests localhost endpoints on EC2 instances via SSH.

EC2 instances don't expose landing (3xxx) and product_app (4xxx) ports externally,
so we must SSH into each instance and test localhost.

Usage:
    from sega.probe.instance_test_runner import InstanceTestRunner

    runner = InstanceTestRunner()
    results = await runner.test_instance("fleet-prod-01")
    results = await runner.test_all_instances()
"""

import asyncio
import json
import time
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

import yaml

from ..utils.paths import get_fleet_root
from ..utils.ssh import SSHExecutor, SSHResult


@dataclass
class LocalhostTestResult:
    """Result of testing a localhost endpoint on an instance."""

    project: str
    instance: str
    instance_ip: str
    endpoint_type: str  # landing, product_app, api
    port: int
    url: str
    success: bool
    status_code: Optional[int] = None
    response_time_ms: Optional[float] = None
    response_data: Optional[str] = None
    error: Optional[str] = None


@dataclass
class InstanceTestResult:
    """Result of testing all projects on an instance."""

    instance: str
    instance_ip: str
    total_tests: int
    successful: int
    failed: int
    duration_seconds: float
    ssh_connected: bool
    results: List[LocalhostTestResult] = field(default_factory=list)
    timestamp: str = field(default_factory=lambda: datetime.now().isoformat())

    @property
    def all_passed(self) -> bool:
        return self.failed == 0 and self.ssh_connected


class InstanceTestRunner:
    """
    Test localhost endpoints on EC2 instances via SSH.

    Tests landing (3xxx) and product_app (4xxx) ports that aren't exposed externally.
    """

    def __init__(
        self,
        config_path: Optional[str] = None,
        timeout: float = 10.0,
        ssh_key_path: Optional[str] = None,
        verbose: bool = False,
    ):
        """
        Initialize instance test runner.

        Args:
            config_path: Path to domain_registry.yaml
            timeout: HTTP request timeout in seconds
            ssh_key_path: Path to SSH private key
            verbose: Enable verbose output
        """
        self.fleet_root = get_fleet_root()
        self.timeout = timeout
        self.ssh_key_path = ssh_key_path
        self.verbose = verbose
        self.config: Dict[str, Any] = {}

        # Load config
        if config_path:
            self._load_config(Path(config_path))
        else:
            default_path = self.fleet_root / "sega" / "config" / "domain_registry.yaml"
            self._load_config(default_path)

    def _load_config(self, path: Path) -> None:
        """Load domain registry configuration."""
        if path.exists():
            with open(path) as f:
                self.config = yaml.safe_load(f) or {}
        else:
            raise FileNotFoundError(f"Domain registry not found: {path}")

    def get_instance_config(self, instance: str) -> Optional[Dict[str, Any]]:
        """Get configuration for a specific instance."""
        return self.config.get("instances", {}).get(instance)

    def get_instance_projects(self, instance: str) -> List[str]:
        """Get list of projects on an instance."""
        projects = []
        for project, config in self.config.get("projects", {}).items():
            if config.get("instance") == instance:
                projects.append(project)
        return projects

    async def test_localhost_endpoint(
        self,
        executor: SSHExecutor,
        project: str,
        instance: str,
        instance_ip: str,
        endpoint_type: str,
        port: int,
        path: str = "/",
    ) -> LocalhostTestResult:
        """
        Test a single localhost endpoint via SSH.

        Args:
            executor: SSH executor for the instance
            project: Project name
            instance: Instance name
            instance_ip: Instance IP address
            endpoint_type: Endpoint type (landing, product_app, api)
            port: Port number
            path: URL path

        Returns:
            LocalhostTestResult
        """
        url = f"http://localhost:{port}{path}"

        # Build curl command with timeout and response code capture
        curl_cmd = f"curl -s -w '\\n%{{http_code}}' -m {self.timeout} '{url}'"

        start = time.perf_counter()

        # Execute via SSH in background async
        loop = asyncio.get_event_loop()
        result = await loop.run_in_executor(None, executor.execute, curl_cmd)

        duration_ms = (time.perf_counter() - start) * 1000

        if not result.success:
            return LocalhostTestResult(
                project=project,
                instance=instance,
                instance_ip=instance_ip,
                endpoint_type=endpoint_type,
                port=port,
                url=url,
                success=False,
                response_time_ms=duration_ms,
                error=f"SSH command failed: {result.stderr}",
            )

        # Parse curl output (last line is status code)
        lines = result.stdout.strip().split("\n")
        if len(lines) >= 1:
            status_code_str = lines[-1]
            response_body = "\n".join(lines[:-1]) if len(lines) > 1 else ""

            try:
                status_code = int(status_code_str)
                success = status_code == 200

                # Truncate response for display
                response_preview = response_body[:200] if response_body else None

                return LocalhostTestResult(
                    project=project,
                    instance=instance,
                    instance_ip=instance_ip,
                    endpoint_type=endpoint_type,
                    port=port,
                    url=url,
                    success=success,
                    status_code=status_code,
                    response_time_ms=duration_ms,
                    response_data=response_preview,
                )

            except ValueError:
                return LocalhostTestResult(
                    project=project,
                    instance=instance,
                    instance_ip=instance_ip,
                    endpoint_type=endpoint_type,
                    port=port,
                    url=url,
                    success=False,
                    response_time_ms=duration_ms,
                    error=f"Invalid curl response: {result.stdout[:100]}",
                )
        else:
            return LocalhostTestResult(
                project=project,
                instance=instance,
                instance_ip=instance_ip,
                endpoint_type=endpoint_type,
                port=port,
                url=url,
                success=False,
                response_time_ms=duration_ms,
                error="Empty curl response",
            )

    async def test_project_on_instance(
        self,
        executor: SSHExecutor,
        project: str,
        instance: str,
        instance_ip: str,
    ) -> List[LocalhostTestResult]:
        """
        Test all localhost endpoints for a project.

        Args:
            executor: SSH executor
            project: Project name
            instance: Instance name
            instance_ip: Instance IP

        Returns:
            List of LocalhostTestResult
        """
        project_config = self.config.get("projects", {}).get(project, {})
        endpoints = project_config.get("endpoints", {})

        results = []
        tasks = []

        # Test each endpoint that has a port
        for endpoint_type, endpoint_config in endpoints.items():
            if "port" in endpoint_config:
                port = endpoint_config["port"]
                path = endpoint_config.get("path", "/")

                task = self.test_localhost_endpoint(executor, project, instance, instance_ip, endpoint_type, port, path)
                tasks.append(task)

        if tasks:
            results = await asyncio.gather(*tasks)

        return list(results)

    async def test_instance(self, instance: str) -> InstanceTestResult:
        """
        Test all projects on an instance.

        Args:
            instance: Instance name (e.g., "fleet-prod-01")

        Returns:
            InstanceTestResult
        """
        instance_config = self.get_instance_config(instance)

        if not instance_config:
            return InstanceTestResult(
                instance=instance,
                instance_ip="unknown",
                total_tests=0,
                successful=0,
                failed=1,
                duration_seconds=0,
                ssh_connected=False,
                results=[],
            )

        instance_ip = instance_config.get("ip", "")

        if not instance_ip:
            return InstanceTestResult(
                instance=instance,
                instance_ip="not configured",
                total_tests=0,
                successful=0,
                failed=1,
                duration_seconds=0,
                ssh_connected=False,
                results=[],
            )

        start = time.perf_counter()

        # Create SSH executor
        try:
            ssh_user = instance_config.get("ssh_user", "ubuntu")
            ssh_key = self.ssh_key_path or instance_config.get("ssh_key")

            executor = SSHExecutor(
                host=instance_ip,
                user=ssh_user,
                key_path=ssh_key,
                timeout=int(self.timeout),
                verbose=self.verbose,
            )

            # Test SSH connection
            loop = asyncio.get_event_loop()
            ssh_test = await loop.run_in_executor(None, executor.test_connection)

            if not ssh_test:
                return InstanceTestResult(
                    instance=instance,
                    instance_ip=instance_ip,
                    total_tests=0,
                    successful=0,
                    failed=1,
                    duration_seconds=time.perf_counter() - start,
                    ssh_connected=False,
                    results=[],
                )

        except Exception as e:
            return InstanceTestResult(
                instance=instance,
                instance_ip=instance_ip,
                total_tests=0,
                successful=0,
                failed=1,
                duration_seconds=time.perf_counter() - start,
                ssh_connected=False,
                results=[],
            )

        # Get projects on this instance
        projects = self.get_instance_projects(instance)

        # Test all projects
        all_results = []
        for project in projects:
            project_results = await self.test_project_on_instance(executor, project, instance, instance_ip)
            all_results.extend(project_results)

        duration = time.perf_counter() - start
        successful = sum(1 for r in all_results if r.success)

        return InstanceTestResult(
            instance=instance,
            instance_ip=instance_ip,
            total_tests=len(all_results),
            successful=successful,
            failed=len(all_results) - successful,
            duration_seconds=duration,
            ssh_connected=True,
            results=all_results,
        )

    async def test_all_instances(self) -> List[InstanceTestResult]:
        """
        Test all EC2 instances.

        Returns:
            List of InstanceTestResult
        """
        instances = self.config.get("instances", {}).keys()

        # Filter out local instance
        ec2_instances = [i for i in instances if not i == "local"]

        tasks = [self.test_instance(instance) for instance in ec2_instances]
        results = await asyncio.gather(*tasks)

        return list(results)


def print_instance_results(results: List[InstanceTestResult]) -> None:
    """Pretty print instance test results."""
    print("\n" + "=" * 80)
    print("INSTANCE LOCALHOST TEST RESULTS")
    print("=" * 80)

    for instance_result in results:
        status = "PASS" if instance_result.all_passed else "FAIL"
        ssh_status = "connected" if instance_result.ssh_connected else "FAILED"

        print(f"\n{instance_result.instance} [{status}] ({instance_result.instance_ip})")
        print(f"  SSH: {ssh_status}")
        print(f"  Tests: {instance_result.successful}/{instance_result.total_tests} passed")
        print(f"  Duration: {instance_result.duration_seconds:.2f}s")

        # Group results by project
        projects = {}
        for result in instance_result.results:
            if result.project not in projects:
                projects[result.project] = []
            projects[result.project].append(result)

        # Print results grouped by project
        for project, project_results in sorted(projects.items()):
            project_passed = all(r.success for r in project_results)
            project_status = "[OK]" if project_passed else "[FAIL]"
            print(f"\n  {project_status} {project}")

            for result in project_results:
                status_icon = "[OK]" if result.success else "[FAIL]"
                if result.success:
                    print(
                        f"      {status_icon} {result.endpoint_type} (:{result.port}): "
                        f"{result.status_code} ({result.response_time_ms:.0f}ms)"
                    )
                else:
                    error = result.error or f"status {result.status_code}"
                    print(f"      {status_icon} {result.endpoint_type} (:{result.port}): {error}")

    print("\n" + "=" * 80)
    total_tests = sum(r.total_tests for r in results)
    total_success = sum(r.successful for r in results)
    total_instances = len(results)
    passed_instances = sum(1 for r in results if r.all_passed)
    print(f"SUMMARY: {passed_instances}/{total_instances} instances passed, {total_success}/{total_tests} tests passed")
    print("=" * 80)


# CLI entry point
async def main():
    """Run instance tests from command line."""
    import argparse

    parser = argparse.ArgumentParser(description="SEGA Instance Localhost Test Runner")
    parser.add_argument("instances", nargs="*", help="Instances to test (empty = all)")
    parser.add_argument("--timeout", type=float, default=10.0, help="Request timeout in seconds")
    parser.add_argument("--ssh-key", help="Path to SSH private key")
    parser.add_argument("--json", action="store_true", help="Output results as JSON")
    parser.add_argument("--verbose", "-v", action="store_true", help="Verbose output")

    args = parser.parse_args()

    runner = InstanceTestRunner(
        timeout=args.timeout,
        ssh_key_path=args.ssh_key,
        verbose=args.verbose,
    )

    if args.instances:
        tasks = [runner.test_instance(instance) for instance in args.instances]
        results = await asyncio.gather(*tasks)
    else:
        results = await runner.test_all_instances()

    if args.json:
        from dataclasses import asdict

        output = [asdict(r) for r in results]
        print(json.dumps(output, indent=2, default=str))
    else:
        print_instance_results(results)


if __name__ == "__main__":
    asyncio.run(main())
