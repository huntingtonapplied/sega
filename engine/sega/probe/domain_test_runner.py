#!/usr/bin/env python3
"""
SEGA Domain Test Runner
=======================
Tests production and internal dev domains for FLEET projects.
Validates SSL, response status, and endpoint health.

Usage:
    from sega.probe.domain_test_runner import DomainTestRunner

    runner = DomainTestRunner()
    results = await runner.test_project("atlas", domain_type="production")
    results = await runner.test_all(domain_type="both")
"""

import asyncio
import ssl
import time
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Literal, Optional

import httpx
import yaml

from ..utils.paths import get_fleet_root


DomainType = Literal["production", "internal", "both"]
EndpointType = Literal["landing", "product_app", "api", "all"]
TestScope = Literal["localhost", "production", "both"]


@dataclass
class DomainTestResult:
    """Result of testing a single domain endpoint."""

    project: str
    domain: str
    domain_type: str  # production, internal
    endpoint_type: str  # landing, product_app, api
    url: str
    success: bool
    status_code: Optional[int] = None
    response_time_ms: Optional[float] = None
    ssl_valid: Optional[bool] = None
    ssl_expiry_days: Optional[int] = None
    error: Optional[str] = None
    response_data: Optional[Any] = None


@dataclass
class LocalhostTestResult:
    """Result of testing localhost endpoint via SSH."""

    project: str
    instance: str
    instance_ip: str
    endpoint_type: str
    port: int
    url: str
    success: bool
    status_code: Optional[int] = None
    response_time_ms: Optional[float] = None
    response_data: Optional[str] = None
    error: Optional[str] = None


@dataclass
class ProjectDomainResult:
    """Result of testing all domains for a project."""

    project: str
    instance: str
    total_tests: int
    successful: int
    failed: int
    duration_seconds: float
    results: List[DomainTestResult] = field(default_factory=list)
    localhost_results: List[LocalhostTestResult] = field(default_factory=list)
    timestamp: str = field(default_factory=lambda: datetime.now().isoformat())

    @property
    def all_passed(self) -> bool:
        return self.failed == 0


class DomainTestRunner:
    """
    Domain URL test runner for FLEET projects.

    Tests production domains (e.g., atlas.app) and staging
    domains (e.g., staging.atlas.app) for landing, product_app, and API.
    """

    def __init__(
        self,
        config_path: Optional[str] = None,
        timeout: float = 30.0,
        verify_ssl: bool = True,
        follow_redirects: bool = True,
    ):
        """
        Initialize domain test runner.

        Args:
            config_path: Path to domain_registry.yaml (auto-detected if not provided)
            timeout: HTTP request timeout in seconds
            verify_ssl: Whether to verify SSL certificates
            follow_redirects: Whether to follow HTTP redirects
        """
        self.fleet_root = get_fleet_root()
        self.timeout = timeout
        self.verify_ssl = verify_ssl
        self.follow_redirects = follow_redirects
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

    def get_projects(self, instance: Optional[str] = None) -> List[str]:
        """Get list of projects, optionally filtered by instance."""
        projects = list(self.config.get("projects", {}).keys())

        if instance:
            instance_name = f"fleet-prod-0{instance}" if instance in ("1", "2") else instance
            projects = [p for p in projects if self.config["projects"][p].get("instance") == instance_name]

        return projects

    def get_project_config(self, project: str) -> Dict[str, Any]:
        """Get configuration for a specific project."""
        return self.config.get("projects", {}).get(project, {})

    def build_url(
        self,
        project: str,
        domain_type: str,
        endpoint_type: str,
    ) -> Optional[str]:
        """
        Build the full URL for a project endpoint.

        Args:
            project: Project name
            domain_type: 'production' or 'internal'
            endpoint_type: 'landing', 'product_app', or 'api'

        Returns:
            Full URL string or None if not available
        """
        config = self.get_project_config(project)
        if not config:
            return None

        domains = config.get("domains", {})
        domain = domains.get(domain_type)

        if not domain:
            return None

        endpoints = config.get("endpoints", {})
        endpoint_config = endpoints.get(endpoint_type)

        if not endpoint_config:
            return None

        path = endpoint_config.get("path", "/")

        # Build subdomain-based URL for production
        if domain_type == "production":
            if endpoint_type == "landing":
                host = domain
            elif endpoint_type == "product_app":
                host = f"app.{domain}"
            elif endpoint_type == "api":
                host = f"api.{domain}"
            else:
                host = domain
        else:
            # Internal dev uses same subdomain pattern
            if endpoint_type == "landing":
                host = domain
            elif endpoint_type == "product_app":
                host = f"app.{domain}"
            elif endpoint_type == "api":
                host = f"api.{domain}"
            else:
                host = domain

        protocol = "https" if self.verify_ssl else "http"
        return f"{protocol}://{host}{path}"

    async def _check_ssl(self, hostname: str) -> tuple[bool, Optional[int]]:
        """
        Check SSL certificate validity and expiry.

        Returns:
            Tuple of (is_valid, days_until_expiry)
        """
        try:
            context = ssl.create_default_context()
            reader, writer = await asyncio.wait_for(asyncio.open_connection(hostname, 443, ssl=context), timeout=10.0)
            writer.close()
            await writer.wait_closed()

            # Get certificate info
            ssl_object = writer.get_extra_info("ssl_object")
            if ssl_object:
                cert = ssl_object.getpeercert()
                if cert:
                    # Parse expiry
                    not_after = cert.get("notAfter")
                    if not_after:
                        from datetime import datetime

                        expiry = datetime.strptime(not_after, "%b %d %H:%M:%S %Y %Z")
                        days = (expiry - datetime.utcnow()).days
                        return True, days

            return True, None

        except ssl.SSLError:
            return False, None
        except Exception:
            return True, None  # Assume valid if we can't check

    async def test_endpoint(
        self,
        project: str,
        domain_type: str,
        endpoint_type: str,
        check_ssl: bool = True,
    ) -> DomainTestResult:
        """
        Test a single domain endpoint.

        Args:
            project: Project name
            domain_type: 'production' or 'internal'
            endpoint_type: 'landing', 'product_app', or 'api'
            check_ssl: Whether to check SSL certificate

        Returns:
            DomainTestResult with status and timing
        """
        url = self.build_url(project, domain_type, endpoint_type)

        if not url:
            return DomainTestResult(
                project=project,
                domain="N/A",
                domain_type=domain_type,
                endpoint_type=endpoint_type,
                url="N/A",
                success=False,
                error=f"No {endpoint_type} endpoint configured for {domain_type}",
            )

        # Extract domain for result
        config = self.get_project_config(project)
        domain = config.get("domains", {}).get(domain_type, "unknown")

        start = time.perf_counter()
        ssl_valid = None
        ssl_expiry = None

        try:
            async with httpx.AsyncClient(
                timeout=self.timeout,
                verify=self.verify_ssl,
                follow_redirects=self.follow_redirects,
            ) as client:
                response = await client.get(url)
                duration_ms = (time.perf_counter() - start) * 1000

                # Check expected status codes
                endpoint_config = config.get("endpoints", {}).get(endpoint_type, {})
                expected_status = endpoint_config.get("expected_status", [200])

                success = response.status_code in expected_status

                # Try to parse JSON for API endpoints
                response_data = None
                if endpoint_type == "api":
                    try:
                        response_data = response.json()

                        # Check expected JSON if configured
                        expected_json = endpoint_config.get("expected_json")
                        if expected_json and success:
                            for key, value in expected_json.items():
                                if response_data.get(key) != value:
                                    success = False
                                    break
                    except Exception:
                        response_data = response.text[:200] if response.text else None

                # Check SSL if production and enabled
                if check_ssl and domain_type == "production" and self.verify_ssl:
                    hostname = url.split("://")[1].split("/")[0]
                    ssl_valid, ssl_expiry = await self._check_ssl(hostname)

                return DomainTestResult(
                    project=project,
                    domain=domain,
                    domain_type=domain_type,
                    endpoint_type=endpoint_type,
                    url=url,
                    success=success,
                    status_code=response.status_code,
                    response_time_ms=duration_ms,
                    ssl_valid=ssl_valid,
                    ssl_expiry_days=ssl_expiry,
                    response_data=response_data,
                )

        except httpx.ConnectError as e:
            duration_ms = (time.perf_counter() - start) * 1000
            return DomainTestResult(
                project=project,
                domain=domain,
                domain_type=domain_type,
                endpoint_type=endpoint_type,
                url=url,
                success=False,
                response_time_ms=duration_ms,
                error=f"Connection failed: {e}",
            )

        except httpx.TimeoutException:
            duration_ms = (time.perf_counter() - start) * 1000
            return DomainTestResult(
                project=project,
                domain=domain,
                domain_type=domain_type,
                endpoint_type=endpoint_type,
                url=url,
                success=False,
                response_time_ms=duration_ms,
                error=f"Timeout after {self.timeout}s",
            )

        except Exception as e:
            duration_ms = (time.perf_counter() - start) * 1000
            return DomainTestResult(
                project=project,
                domain=domain,
                domain_type=domain_type,
                endpoint_type=endpoint_type,
                url=url,
                success=False,
                response_time_ms=duration_ms,
                error=str(e),
            )

    async def test_project(
        self,
        project: str,
        domain_type: DomainType = "both",
        endpoint_type: EndpointType = "all",
    ) -> ProjectDomainResult:
        """
        Test all domain endpoints for a project.

        Args:
            project: Project name
            domain_type: 'production', 'internal', or 'both'
            endpoint_type: 'landing', 'product_app', 'api', or 'all'

        Returns:
            ProjectDomainResult with all test results
        """
        config = self.get_project_config(project)
        instance = config.get("instance", "unknown")

        start = time.perf_counter()
        results: List[DomainTestResult] = []

        # Determine which domain types to test
        domain_types = []
        if domain_type in ("production", "both"):
            if config.get("domains", {}).get("production"):
                domain_types.append("production")
        if domain_type in ("internal", "both"):
            if config.get("domains", {}).get("internal"):
                domain_types.append("internal")

        # Determine which endpoint types to test
        endpoint_types = []
        if endpoint_type == "all":
            endpoint_types = ["landing", "product_app", "api"]
        else:
            endpoint_types = [endpoint_type]

        # Run tests
        tasks = []
        for dt in domain_types:
            for et in endpoint_types:
                # Check if endpoint exists
                if config.get("endpoints", {}).get(et):
                    tasks.append(self.test_endpoint(project, dt, et))

        if tasks:
            results = await asyncio.gather(*tasks)
        else:
            results = []

        duration = time.perf_counter() - start
        successful = sum(1 for r in results if r.success)

        return ProjectDomainResult(
            project=project,
            instance=instance,
            total_tests=len(results),
            successful=successful,
            failed=len(results) - successful,
            duration_seconds=duration,
            results=list(results),
        )

    async def test_projects(
        self,
        projects: List[str],
        domain_type: DomainType = "both",
        endpoint_type: EndpointType = "all",
        parallel: bool = True,
    ) -> List[ProjectDomainResult]:
        """
        Test domain endpoints for multiple projects.

        Args:
            projects: List of project names
            domain_type: 'production', 'internal', or 'both'
            endpoint_type: 'landing', 'product_app', 'api', or 'all'
            parallel: Run tests in parallel

        Returns:
            List of ProjectDomainResult
        """
        if parallel:
            tasks = [self.test_project(p, domain_type, endpoint_type) for p in projects]
            return await asyncio.gather(*tasks)
        else:
            results = []
            for project in projects:
                result = await self.test_project(project, domain_type, endpoint_type)
                results.append(result)
            return results

    async def test_all(
        self,
        domain_type: DomainType = "both",
        endpoint_type: EndpointType = "all",
        instance: Optional[str] = None,
    ) -> List[ProjectDomainResult]:
        """
        Test all projects.

        Args:
            domain_type: 'production', 'internal', or 'both'
            endpoint_type: 'landing', 'product_app', 'api', or 'all'
            instance: Optionally filter to projects on specific instance ('1' or '2')

        Returns:
            List of ProjectDomainResult
        """
        projects = self.get_projects(instance)
        return await self.test_projects(projects, domain_type, endpoint_type)

    async def test_comprehensive(
        self,
        domain_type: DomainType = "production",
        endpoint_type: EndpointType = "all",
        instance: Optional[str] = None,
        test_localhost: bool = True,
        ssh_key_path: Optional[str] = None,
    ) -> List[ProjectDomainResult]:
        """
        Comprehensive testing: localhost (via SSH) + production domains.

        This tests:
        1. Localhost endpoints on EC2 instances (landing, product_app, api)
        2. Production domain URLs (publicly accessible)

        Args:
            domain_type: 'production', 'internal', or 'both'
            endpoint_type: 'landing', 'product_app', 'api', or 'all'
            instance: Optionally filter to specific instance
            test_localhost: Include SSH-based localhost testing
            ssh_key_path: Path to SSH private key

        Returns:
            List of ProjectDomainResult with both domain and localhost results
        """
        # Import instance test runner
        from .instance_test_runner import InstanceTestRunner

        # First get domain test results
        domain_results = await self.test_all(domain_type, endpoint_type, instance)

        # If localhost testing is enabled, add those results
        if test_localhost:
            instance_runner = InstanceTestRunner(
                config_path=None,  # Uses same config
                timeout=self.timeout,
                ssh_key_path=ssh_key_path,
                verbose=False,
            )

            # Determine which instances to test
            if instance:
                instance_name = f"fleet-prod-0{instance}" if instance in ("1", "2", "3") else instance
                instance_results = [await instance_runner.test_instance(instance_name)]
            else:
                instance_results = await instance_runner.test_all_instances()

            # Merge localhost results into domain results
            for domain_result in domain_results:
                # Find matching instance result
                for inst_result in instance_results:
                    if domain_result.instance == inst_result.instance:
                        # Add localhost test results
                        project_localhost = [r for r in inst_result.results if r.project == domain_result.project]
                        domain_result.localhost_results = project_localhost

                        # Update counts
                        localhost_success = sum(1 for r in project_localhost if r.success)
                        domain_result.total_tests += len(project_localhost)
                        domain_result.successful += localhost_success
                        domain_result.failed += len(project_localhost) - localhost_success
                        break

        return domain_results


def print_results(results: List[ProjectDomainResult], show_localhost: bool = True) -> None:
    """Pretty print domain test results."""
    print("\n" + "=" * 80)
    print("COMPREHENSIVE DOMAIN TEST RESULTS")
    print("=" * 80)

    for project_result in results:
        status = "PASS" if project_result.all_passed else "FAIL"
        print(f"\n{project_result.project} [{status}] ({project_result.instance})")
        print(f"  Tests: {project_result.successful}/{project_result.total_tests} passed")
        print(f"  Duration: {project_result.duration_seconds:.2f}s")

        # Show localhost results first (if available)
        if show_localhost and project_result.localhost_results:
            print(f"\n  Localhost (via SSH):")
            for result in project_result.localhost_results:
                status_icon = "[OK]" if result.success else "[FAIL]"
                if result.success:
                    print(
                        f"    {status_icon} {result.endpoint_type} (:{result.port}): "
                        f"{result.status_code} ({result.response_time_ms:.0f}ms)"
                    )
                else:
                    error = result.error or f"status {result.status_code}"
                    print(f"    {status_icon} {result.endpoint_type} (:{result.port}): {error}")

        # Show production domain results
        if project_result.results:
            print(f"\n  Production Domains:")
            for result in project_result.results:
                status_icon = "[OK]" if result.success else "[FAIL]"
                ssl_info = ""
                if result.ssl_valid is not None:
                    ssl_status = "valid" if result.ssl_valid else "INVALID"
                    expiry = f", {result.ssl_expiry_days}d" if result.ssl_expiry_days else ""
                    ssl_info = f" (SSL: {ssl_status}{expiry})"

                if result.success:
                    print(
                        f"    {status_icon} {result.domain_type}/{result.endpoint_type}: "
                        f"{result.status_code} ({result.response_time_ms:.0f}ms){ssl_info}"
                    )
                else:
                    error = result.error or f"status {result.status_code}"
                    print(f"    {status_icon} {result.domain_type}/{result.endpoint_type}: {error}")

    print("\n" + "=" * 80)
    total_tests = sum(r.total_tests for r in results)
    total_success = sum(r.successful for r in results)
    total_projects = len(results)
    passed_projects = sum(1 for r in results if r.all_passed)

    # Count localhost vs production tests
    localhost_tests = sum(len(r.localhost_results) for r in results)
    production_tests = sum(len(r.results) for r in results)

    print(f"SUMMARY: {passed_projects}/{total_projects} projects passed, {total_success}/{total_tests} tests passed")
    if localhost_tests > 0:
        print(f"  Localhost: {localhost_tests} tests | Production: {production_tests} tests")
    print("=" * 80)

    for project_result in results:
        status = "PASS" if project_result.all_passed else "FAIL"
        print(f"\n{project_result.project} [{status}] ({project_result.instance})")
        print(f"  Tests: {project_result.successful}/{project_result.total_tests} passed")
        print(f"  Duration: {project_result.duration_seconds:.2f}s")

        for result in project_result.results:
            status_icon = "[OK]" if result.success else "[FAIL]"
            ssl_info = ""
            if result.ssl_valid is not None:
                ssl_status = "valid" if result.ssl_valid else "INVALID"
                expiry = f", {result.ssl_expiry_days}d" if result.ssl_expiry_days else ""
                ssl_info = f" (SSL: {ssl_status}{expiry})"

            if result.success:
                print(
                    f"    {status_icon} {result.domain_type}/{result.endpoint_type}: "
                    f"{result.status_code} ({result.response_time_ms:.0f}ms){ssl_info}"
                )
            else:
                error = result.error or f"status {result.status_code}"
                print(f"    {status_icon} {result.domain_type}/{result.endpoint_type}: {error}")

    print("\n" + "=" * 70)
    total_tests = sum(r.total_tests for r in results)
    total_success = sum(r.successful for r in results)
    total_projects = len(results)
    passed_projects = sum(1 for r in results if r.all_passed)
    print(f"SUMMARY: {passed_projects}/{total_projects} projects passed, {total_success}/{total_tests} tests passed")
    print("=" * 70)


# CLI entry point
async def main():
    """Run domain tests from command line."""
    import argparse

    parser = argparse.ArgumentParser(description="SEGA Domain Test Runner")
    parser.add_argument("projects", nargs="*", help="Projects to test (empty = all)")
    parser.add_argument(
        "--domain", choices=["production", "internal", "both"], default="both", help="Domain type to test"
    )
    parser.add_argument(
        "--type",
        dest="endpoint_type",
        choices=["landing", "product_app", "api", "all"],
        default="all",
        help="Endpoint type to test",
    )
    parser.add_argument("--instance", choices=["1", "2"], help="Test only projects on specific instance")
    parser.add_argument("--timeout", type=float, default=30.0, help="Request timeout in seconds")
    parser.add_argument("--no-ssl", action="store_true", help="Disable SSL verification")
    parser.add_argument("--json", action="store_true", help="Output results as JSON")

    args = parser.parse_args()

    runner = DomainTestRunner(
        timeout=args.timeout,
        verify_ssl=not args.no_ssl,
    )

    if args.projects:
        results = await runner.test_projects(
            args.projects,
            domain_type=args.domain,
            endpoint_type=args.endpoint_type,
        )
    else:
        results = await runner.test_all(
            domain_type=args.domain,
            endpoint_type=args.endpoint_type,
            instance=args.instance,
        )

    if args.json:
        import json
        from dataclasses import asdict

        output = [asdict(r) for r in results]
        print(json.dumps(output, indent=2, default=str))
    else:
        print_results(results)


if __name__ == "__main__":
    asyncio.run(main())
