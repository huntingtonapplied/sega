#!/usr/bin/env python3
"""
SEGA Structured Test Reporter
==============================
Produces formatted test reports with pass/fail status and error messages.

Usage:
    from sega.probe.structured_test_reporter import StructuredTestReporter, run_default_project_tests

    # Run full test suite
    await run_default_project_tests()

    # Custom reporter
    reporter = StructuredTestReporter()
    await reporter.run_and_report("atlas")

Report Format:
    ============================================================
    <PROJECT> API TEST REPORT
    ============================================================
    Timestamp: 2025-12-21 10:30:45
    Base URL:  http://localhost:8000
    ============================================================

    [HEALTH] Health Endpoints
    ------------------------------------------------------------
    PASS  GET  /health                    200    12ms
    PASS  GET  /api/                      200     8ms

    [SIMULATION] Simulation Execution
    ------------------------------------------------------------
    PASS  POST /api/api/run               201    45ms
    FAIL  GET  /api/api/simulations       401    15ms  Auth required

    ============================================================
    SUMMARY: 8/10 passed, 2 failed
    ============================================================
"""

import asyncio
import json
import time
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import httpx
import yaml


@dataclass
class EndpointResult:
    """Result of testing a single endpoint."""
    name: str
    path: str
    method: str
    category: str
    status_code: int
    success: bool
    duration_ms: float
    description: str = ""
    response_data: Optional[Any] = None
    error_message: Optional[str] = None


@dataclass
class CategoryResult:
    """Results for a category of endpoints."""
    name: str
    endpoints: List[EndpointResult] = field(default_factory=list)

    @property
    def passed(self) -> int:
        return sum(1 for e in self.endpoints if e.success)

    @property
    def failed(self) -> int:
        return sum(1 for e in self.endpoints if not e.success)

    @property
    def total(self) -> int:
        return len(self.endpoints)


@dataclass
class TestReport:
    """Complete test report for a project."""
    project: str
    base_url: str
    timestamp: datetime
    duration_seconds: float
    categories: Dict[str, CategoryResult] = field(default_factory=dict)

    @property
    def total_passed(self) -> int:
        return sum(c.passed for c in self.categories.values())

    @property
    def total_failed(self) -> int:
        return sum(c.failed for c in self.categories.values())

    @property
    def total_tests(self) -> int:
        return sum(c.total for c in self.categories.values())

    @property
    def success_rate(self) -> float:
        if self.total_tests == 0:
            return 0.0
        return (self.total_passed / self.total_tests) * 100


class StructuredTestReporter:
    """
    Structured test reporter with formatted output.

    Produces easy-to-read test reports with:
    - Category grouping
    - Pass/Fail status per endpoint
    - Error messages
    - Timing information
    - Summary statistics
    """

    def __init__(
        self,
        config_path: Optional[str] = None,
        timeout: float = 10.0,
    ):
        self.timeout = timeout
        self.config: Dict[str, Any] = {}

        # Load config
        if config_path:
            config_file = Path(config_path)
        else:
            # Default path
            config_file = Path(__file__).parent.parent.parent.parent / "config" / "api_test_config.yaml"

        if config_file.exists():
            with open(config_file) as f:
                self.config = yaml.safe_load(f) or {}

    async def test_endpoint(
        self,
        base_url: str,
        endpoint: Dict[str, Any],
        headers: Optional[Dict[str, str]] = None,
    ) -> EndpointResult:
        """Test a single endpoint."""
        path = endpoint["path"]
        method = endpoint.get("method", "GET").upper()
        name = endpoint.get("name", path)
        category = endpoint.get("category", "general")
        description = endpoint.get("description", "")
        body = endpoint.get("body")
        auth_required = endpoint.get("auth_required", False)

        url = f"{base_url}{path}"
        start = time.perf_counter()

        # Skip auth-required endpoints if no headers provided
        if auth_required and not headers:
            return EndpointResult(
                name=name,
                path=path,
                method=method,
                category=category,
                status_code=0,
                success=False,
                duration_ms=0,
                description=description,
                error_message="Skipped: Auth required but no token provided",
            )

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

                # Parse response
                try:
                    response_data = response.json()
                except Exception:
                    response_data = response.text[:200] if response.text else None

                # Determine success (2xx status codes)
                success = 200 <= response.status_code < 300

                # Build error message for failures
                error_message = None
                if not success:
                    if response.status_code == 401:
                        error_message = "Unauthorized - authentication required"
                    elif response.status_code == 403:
                        error_message = "Forbidden - insufficient permissions"
                    elif response.status_code == 404:
                        error_message = "Not Found - endpoint does not exist"
                    elif response.status_code == 500:
                        error_message = "Internal Server Error"
                        if isinstance(response_data, dict) and "detail" in response_data:
                            error_message = f"Server Error: {response_data['detail'][:100]}"
                    else:
                        error_message = f"HTTP {response.status_code}"

                return EndpointResult(
                    name=name,
                    path=path,
                    method=method,
                    category=category,
                    status_code=response.status_code,
                    success=success,
                    duration_ms=duration_ms,
                    description=description,
                    response_data=response_data,
                    error_message=error_message,
                )

        except httpx.ConnectError as e:
            duration_ms = (time.perf_counter() - start) * 1000
            return EndpointResult(
                name=name,
                path=path,
                method=method,
                category=category,
                status_code=0,
                success=False,
                duration_ms=duration_ms,
                description=description,
                error_message=f"Connection failed: {str(e)[:50]}",
            )
        except httpx.TimeoutException:
            duration_ms = (time.perf_counter() - start) * 1000
            return EndpointResult(
                name=name,
                path=path,
                method=method,
                category=category,
                status_code=0,
                success=False,
                duration_ms=duration_ms,
                description=description,
                error_message=f"Timeout after {self.timeout}s",
            )
        except Exception as e:
            duration_ms = (time.perf_counter() - start) * 1000
            return EndpointResult(
                name=name,
                path=path,
                method=method,
                category=category,
                status_code=0,
                success=False,
                duration_ms=duration_ms,
                description=description,
                error_message=str(e)[:100],
            )

    async def run_project_tests(
        self,
        project: str,
        host: str = "localhost",
        headers: Optional[Dict[str, str]] = None,
        categories: Optional[List[str]] = None,
    ) -> TestReport:
        """
        Run tests for a project and return structured report.

        Args:
            project: Project name
            host: Host where service is running
            headers: Optional auth headers
            categories: Optional list of categories to test (None = all)

        Returns:
            TestReport with all results
        """
        project_config = self.config.get(project, {})
        port = project_config.get("port", 8000)
        base_url = f"http://{host}:{port}"
        endpoints = project_config.get("endpoints", [])

        # Filter by categories if specified
        if categories:
            endpoints = [e for e in endpoints if e.get("category") in categories]

        start = time.perf_counter()
        timestamp = datetime.now()

        # Run all endpoint tests
        results: List[EndpointResult] = []
        for endpoint in endpoints:
            result = await self.test_endpoint(base_url, endpoint, headers)
            results.append(result)

        duration = time.perf_counter() - start

        # Group by category
        category_results: Dict[str, CategoryResult] = {}
        for result in results:
            cat_name = result.category
            if cat_name not in category_results:
                category_results[cat_name] = CategoryResult(name=cat_name)
            category_results[cat_name].endpoints.append(result)

        return TestReport(
            project=project,
            base_url=base_url,
            timestamp=timestamp,
            duration_seconds=duration,
            categories=category_results,
        )

    def format_report(self, report: TestReport) -> str:
        """Format test report as string."""
        lines = []
        width = 70

        # Header
        lines.append("=" * width)
        lines.append(f"{report.project.upper()} API TEST REPORT")
        lines.append("=" * width)
        lines.append(f"Timestamp: {report.timestamp.strftime('%Y-%m-%d %H:%M:%S')}")
        lines.append(f"Base URL:  {report.base_url}")
        lines.append(f"Duration:  {report.duration_seconds:.2f}s")
        lines.append("=" * width)
        lines.append("")

        # Results by category
        category_names = {
            "health": "Health Endpoints",
            "simulation": "Simulation Execution",
            "jobs": "Job Orchestration",
            "device": "Device Management",
            "session": "Session Management",
            "general": "General Endpoints",
        }

        for cat_key, cat_result in report.categories.items():
            cat_display = category_names.get(cat_key, cat_key.upper())
            lines.append(f"[{cat_key.upper()}] {cat_display}")
            lines.append("-" * width)

            for ep in cat_result.endpoints:
                status = "PASS" if ep.success else "FAIL"
                status_code = str(ep.status_code) if ep.status_code else "---"
                duration = f"{ep.duration_ms:>6.0f}ms" if ep.duration_ms else "     --"

                # Format: PASS  GET  /api/endpoint              200    12ms
                line = f"{status:4}  {ep.method:6} {ep.path:30} {status_code:>3}  {duration}"

                if ep.error_message:
                    line += f"  {ep.error_message}"

                lines.append(line)

            lines.append("")

        # Summary
        lines.append("=" * width)
        passed = report.total_passed
        failed = report.total_failed
        total = report.total_tests
        rate = report.success_rate

        status_word = "PASSED" if failed == 0 else "FAILED"
        lines.append(f"SUMMARY: {passed}/{total} passed, {failed} failed ({rate:.0f}%) - {status_word}")
        lines.append("=" * width)

        return "\n".join(lines)

    def format_json_report(self, report: TestReport) -> str:
        """Format test report as JSON."""
        data = {
            "project": report.project,
            "base_url": report.base_url,
            "timestamp": report.timestamp.isoformat(),
            "duration_seconds": report.duration_seconds,
            "summary": {
                "total": report.total_tests,
                "passed": report.total_passed,
                "failed": report.total_failed,
                "success_rate": report.success_rate,
            },
            "categories": {},
        }

        for cat_key, cat_result in report.categories.items():
            data["categories"][cat_key] = {
                "passed": cat_result.passed,
                "failed": cat_result.failed,
                "endpoints": [
                    {
                        "name": ep.name,
                        "path": ep.path,
                        "method": ep.method,
                        "status_code": ep.status_code,
                        "success": ep.success,
                        "duration_ms": ep.duration_ms,
                        "error": ep.error_message,
                    }
                    for ep in cat_result.endpoints
                ],
            }

        return json.dumps(data, indent=2)

    async def run_and_report(
        self,
        project: str,
        host: str = "localhost",
        headers: Optional[Dict[str, str]] = None,
        output_format: str = "text",
        categories: Optional[List[str]] = None,
    ) -> Tuple[TestReport, str]:
        """
        Run tests and return formatted report.

        Args:
            project: Project name
            host: Host where service is running
            headers: Optional auth headers
            output_format: "text" or "json"
            categories: Optional list of categories to test

        Returns:
            Tuple of (TestReport, formatted_string)
        """
        report = await self.run_project_tests(project, host, headers, categories)

        if output_format == "json":
            formatted = self.format_json_report(report)
        else:
            formatted = self.format_report(report)

        return report, formatted


def _default_probe_project() -> str:
    """Default probe project from `[fleet] default_probe_project` config."""
    from ..core.config import get_config
    return get_config().fleet.default_probe_project


async def run_default_project_tests(
    host: str = "localhost",
    with_auth: bool = True,
    categories: Optional[List[str]] = None,
    output_format: str = "text",
) -> TestReport:
    """
    Run API tests for the configured default probe project.

    Args:
        host: Host where the project is running
        with_auth: Include mock auth headers
        categories: Optional list of categories (health, simulation, jobs, device, session)
        output_format: "text" or "json"

    Returns:
        TestReport object
    """
    project = _default_probe_project()
    if not project:
        raise ValueError(
            "No default probe project configured; set [fleet] default_probe_project "
            "in sega.toml or call run_and_report(<project>) directly."
        )
    reporter = StructuredTestReporter()

    # Mock auth headers if requested
    headers = None
    if with_auth:
        from .auth import AuthMode, TestAuthManager
        auth_manager = TestAuthManager(mode=AuthMode.MOCK_JWT)
        headers = auth_manager.get_auth_headers()

    report, formatted = await reporter.run_and_report(
        project,
        host=host,
        headers=headers,
        output_format=output_format,
        categories=categories,
    )

    print(formatted)
    return report


# CLI entry point
async def main():
    """CLI entry point."""
    import argparse

    parser = argparse.ArgumentParser(description="SEGA Structured Test Reporter")
    parser.add_argument(
        "project", nargs="?", default=_default_probe_project() or None,
        help="Project to test (default: [fleet] default_probe_project)",
    )
    parser.add_argument("--host", default="localhost", help="Host running the service")
    parser.add_argument("--format", choices=["text", "json"], default="text", help="Output format")
    parser.add_argument("--category", "-c", action="append", help="Categories to test (can specify multiple)")
    parser.add_argument("--no-auth", action="store_true", help="Skip auth headers")
    parser.add_argument("--timeout", type=float, default=10.0, help="Request timeout")
    parser.add_argument("--save", help="Save report to file")

    args = parser.parse_args()

    if not args.project:
        parser.error("no project given and no [fleet] default_probe_project configured")

    reporter = StructuredTestReporter(timeout=args.timeout)

    # Auth headers
    headers = None
    if not args.no_auth:
        try:
            from .auth import AuthMode, TestAuthManager
            auth_manager = TestAuthManager(mode=AuthMode.MOCK_JWT)
            headers = auth_manager.get_auth_headers()
        except ImportError:
            pass  # Auth module not available

    report, formatted = await reporter.run_and_report(
        args.project,
        host=args.host,
        headers=headers,
        output_format=args.format,
        categories=args.category,
    )

    print(formatted)

    if args.save:
        with open(args.save, "w") as f:
            f.write(formatted)
        print(f"\nReport saved to: {args.save}")


if __name__ == "__main__":
    asyncio.run(main())
