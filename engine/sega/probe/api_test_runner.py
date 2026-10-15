#!/usr/bin/env python3
"""
SEGA API Test Runner
====================
Lightweight API testing that calls running containers.
Mirrors frontend service endpoints for validation.

Usage:
    from sega.testing.api_test_runner import ApiTestRunner

    runner = ApiTestRunner()
    results = await runner.run_project("atlas")
    results = await runner.run_all()
"""

import asyncio
import time
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

import httpx
import yaml

from ..utils.paths import get_fleet_root
from ..core.config import get_config


@dataclass
class ApiCallResult:
    """Result of a single API call."""
    endpoint: str
    method: str
    status_code: int
    success: bool
    duration_ms: float
    response_data: Optional[Any] = None
    error: Optional[str] = None


@dataclass
class ProjectTestResult:
    """Result of testing a project's API."""
    project: str
    base_url: str
    total_calls: int
    successful: int
    failed: int
    duration_seconds: float
    calls: List[ApiCallResult] = field(default_factory=list)
    timestamp: str = field(default_factory=lambda: datetime.now().isoformat())


# Default port mapping (api port), derived from central config.
# AUTHORITATIVE: /docs/standards/infrastructure/PORT_ALLOCATION_STANDARDS.md
# The project set is the curated `[fleet] api_test_projects` config list, so
# run_all()/health_check_all() default to the operator-configured set; the
# port VALUES come from config (api port = 8000 + id).
_API_TEST_PROJECTS = list(get_config().fleet.api_test_projects)


def _build_api_ports() -> Dict[str, int]:
    """Build {project: api_port} from central config (api port = 8000 + id)."""
    cfg = get_config()
    ports: Dict[str, int] = {}
    for name in _API_TEST_PROJECTS:
        proj = cfg.get_project(name)
        if proj is None:
            continue
        ports[name] = proj.ports.api
    return ports


PROJECT_PORTS = _build_api_ports()

# Common endpoints all projects should have
COMMON_ENDPOINTS = [
    {"path": "/health", "method": "GET", "name": "health_check"},
    {"path": "/api/v1/health", "method": "GET", "name": "api_health"},
]


class ApiTestRunner:
    """
    Lightweight API test runner for FLEET projects.

    Makes HTTP calls to running containers and returns results.
    Response validation is optional (plug your own handler).
    """

    def __init__(
        self,
        fleet_root: Optional[str] = None,
        config_path: Optional[str] = None,
        timeout: float = 10.0,
        response_handler: Optional[Callable[[ApiCallResult], None]] = None,
    ):
        """
        Initialize API test runner.

        Args:
            fleet_root: FLEET root directory (auto-detected if not provided)
            config_path: Path to projects config YAML (optional)
            timeout: HTTP request timeout in seconds
            response_handler: Optional callback for each response (for validation)
        """
        self.fleet_root = Path(fleet_root) if fleet_root else get_fleet_root()
        self.config_path = config_path
        self.timeout = timeout
        self.response_handler = response_handler
        self.projects_config: Dict[str, Any] = {}

        self._load_config()

    def _load_config(self):
        """Load project configuration."""
        # Try to load from config file if provided
        if self.config_path and Path(self.config_path).exists():
            with open(self.config_path) as f:
                self.projects_config = yaml.safe_load(f) or {}
        else:
            # Use default config path
            default_config = self.fleet_root / "sega" / "config" / "api_test_config.yaml"
            if default_config.exists():
                with open(default_config) as f:
                    self.projects_config = yaml.safe_load(f) or {}

    def get_base_url(self, project: str, host: str = "localhost") -> str:
        """Get base URL for a project."""
        # Check config first
        if project in self.projects_config:
            port = self.projects_config[project].get("port", PROJECT_PORTS.get(project, 8000))
        else:
            port = PROJECT_PORTS.get(project, 8000)

        return f"http://{host}:{port}"

    def get_endpoints(self, project: str) -> List[Dict[str, str]]:
        """
        Get endpoints to test for a project.

        Reads from config, or uses common endpoints as fallback.
        """
        if project in self.projects_config:
            endpoints = self.projects_config[project].get("endpoints", [])
            if endpoints:
                return endpoints

        # Fallback to common endpoints
        return COMMON_ENDPOINTS.copy()

    async def call_endpoint(
        self,
        base_url: str,
        endpoint: Dict[str, str],
        headers: Optional[Dict[str, str]] = None,
    ) -> ApiCallResult:
        """
        Make a single API call.

        Args:
            base_url: Base URL (e.g., http://localhost:8009)
            endpoint: Endpoint definition {path, method, name, body?}
            headers: Optional headers (e.g., auth token)

        Returns:
            ApiCallResult with status and timing
        """
        path = endpoint["path"]
        method = endpoint.get("method", "GET").upper()
        body = endpoint.get("body")
        url = f"{base_url}{path}"

        start = time.perf_counter()

        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                if method == "GET":
                    response = await client.get(url, headers=headers)
                elif method == "POST":
                    response = await client.post(url, json=body, headers=headers)
                elif method == "PUT":
                    response = await client.put(url, json=body, headers=headers)
                elif method == "PATCH":
                    response = await client.patch(url, json=body, headers=headers)
                elif method == "DELETE":
                    response = await client.delete(url, headers=headers)
                else:
                    raise ValueError(f"Unsupported method: {method}")

                duration_ms = (time.perf_counter() - start) * 1000

                # Try to parse JSON response
                try:
                    response_data = response.json()
                except Exception:
                    response_data = response.text[:500] if response.text else None

                result = ApiCallResult(
                    endpoint=path,
                    method=method,
                    status_code=response.status_code,
                    success=200 <= response.status_code < 300,
                    duration_ms=duration_ms,
                    response_data=response_data,
                )

        except httpx.ConnectError as e:
            duration_ms = (time.perf_counter() - start) * 1000
            result = ApiCallResult(
                endpoint=path,
                method=method,
                status_code=0,
                success=False,
                duration_ms=duration_ms,
                error=f"Connection failed: {e}",
            )
        except httpx.TimeoutException:
            duration_ms = (time.perf_counter() - start) * 1000
            result = ApiCallResult(
                endpoint=path,
                method=method,
                status_code=0,
                success=False,
                duration_ms=duration_ms,
                error=f"Timeout after {self.timeout}s",
            )
        except Exception as e:
            duration_ms = (time.perf_counter() - start) * 1000
            result = ApiCallResult(
                endpoint=path,
                method=method,
                status_code=0,
                success=False,
                duration_ms=duration_ms,
                error=str(e),
            )

        # Call response handler if provided (for validation)
        if self.response_handler:
            self.response_handler(result)

        return result

    async def run_project(
        self,
        project: str,
        host: str = "localhost",
        headers: Optional[Dict[str, str]] = None,
        endpoints: Optional[List[Dict[str, str]]] = None,
    ) -> ProjectTestResult:
        """
        Run API tests for a single project.

        Args:
            project: Project name (e.g., "atlas")
            host: Host where container is running
            headers: Optional auth headers
            endpoints: Override endpoints to test

        Returns:
            ProjectTestResult with all call results
        """
        base_url = self.get_base_url(project, host)
        test_endpoints = endpoints or self.get_endpoints(project)

        start = time.perf_counter()
        calls: List[ApiCallResult] = []

        for endpoint in test_endpoints:
            result = await self.call_endpoint(base_url, endpoint, headers)
            calls.append(result)

        duration = time.perf_counter() - start
        successful = sum(1 for c in calls if c.success)

        return ProjectTestResult(
            project=project,
            base_url=base_url,
            total_calls=len(calls),
            successful=successful,
            failed=len(calls) - successful,
            duration_seconds=duration,
            calls=calls,
        )

    async def run_projects(
        self,
        projects: List[str],
        host: str = "localhost",
        headers: Optional[Dict[str, str]] = None,
        parallel: bool = True,
    ) -> List[ProjectTestResult]:
        """
        Run API tests for multiple projects.

        Args:
            projects: List of project names
            host: Host where containers are running
            headers: Optional auth headers
            parallel: Run tests in parallel (default True)

        Returns:
            List of ProjectTestResult
        """
        if parallel:
            tasks = [self.run_project(p, host, headers) for p in projects]
            return await asyncio.gather(*tasks)
        else:
            results = []
            for project in projects:
                result = await self.run_project(project, host, headers)
                results.append(result)
            return results

    async def run_all(
        self,
        host: str = "localhost",
        headers: Optional[Dict[str, str]] = None,
    ) -> List[ProjectTestResult]:
        """Run API tests for all known projects."""
        return await self.run_projects(list(PROJECT_PORTS.keys()), host, headers)

    async def health_check_all(
        self,
        host: str = "localhost",
    ) -> Dict[str, bool]:
        """
        Quick health check for all projects.

        Returns:
            Dict mapping project name to healthy status
        """
        results = {}

        async def check_one(project: str) -> tuple:
            base_url = self.get_base_url(project, host)
            result = await self.call_endpoint(
                base_url,
                {"path": "/health", "method": "GET", "name": "health"},
            )
            return project, result.success

        tasks = [check_one(p) for p in PROJECT_PORTS.keys()]
        checks = await asyncio.gather(*tasks)

        for project, healthy in checks:
            results[project] = healthy

        return results


def print_results(results: List[ProjectTestResult]):
    """Pretty print test results."""
    print("\n" + "=" * 60)
    print("API TEST RESULTS")
    print("=" * 60)

    for result in results:
        status = "PASS" if result.failed == 0 else "FAIL"
        print(f"\n{result.project} [{status}]")
        print(f"  URL: {result.base_url}")
        print(f"  Calls: {result.successful}/{result.total_calls} successful")
        print(f"  Duration: {result.duration_seconds:.2f}s")

        if result.failed > 0:
            print("  Failed calls:")
            for call in result.calls:
                if not call.success:
                    print(f"    - {call.method} {call.endpoint}: {call.error or call.status_code}")

    print("\n" + "=" * 60)
    total_success = sum(r.successful for r in results)
    total_calls = sum(r.total_calls for r in results)
    print(f"TOTAL: {total_success}/{total_calls} calls successful")
    print("=" * 60)


# CLI entry point
async def main():
    """Run API tests from command line."""
    import argparse

    parser = argparse.ArgumentParser(description="SEGA API Test Runner")
    parser.add_argument("projects", nargs="*", help="Projects to test (empty = all)")
    parser.add_argument("--host", default="localhost", help="Host running containers")
    parser.add_argument("--timeout", type=float, default=10.0, help="Request timeout")
    parser.add_argument("--health-only", action="store_true", help="Only run health checks")

    args = parser.parse_args()

    runner = ApiTestRunner(timeout=args.timeout)

    if args.health_only:
        results = await runner.health_check_all(args.host)
        print("\nHealth Check Results:")
        for project, healthy in sorted(results.items()):
            status = "UP" if healthy else "DOWN"
            print(f"  {project}: {status}")
    else:
        projects = args.projects or list(PROJECT_PORTS.keys())
        results = await runner.run_projects(projects, args.host)
        print_results(results)


if __name__ == "__main__":
    asyncio.run(main())
