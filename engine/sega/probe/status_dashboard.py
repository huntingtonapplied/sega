#!/usr/bin/env python3
# Copyright 2025 SEGA
"""
Status Dashboard
================
Lightweight HTTP-based status dashboard for quick health checks.
No Playwright - just fast HTTP requests to check if pages are up.
"""

import asyncio
import time
from dataclasses import dataclass
from typing import Dict, List, Optional

import httpx

from .domain_test_runner import DomainTestRunner


@dataclass
class QuickStatusResult:
    """Quick HTTP status check result."""

    project: str
    endpoint_type: str  # landing, product_app, api
    url: str
    status_code: Optional[int] = None
    ok: bool = False
    response_time_ms: Optional[float] = None
    error: Optional[str] = None


@dataclass
class ProjectStatus:
    """Overall project status."""

    project: str
    landing: Optional[QuickStatusResult] = None
    product_app: Optional[QuickStatusResult] = None
    api: Optional[QuickStatusResult] = None

    @property
    def overall_status(self) -> str:
        """Get overall status: healthy, warning, critical."""
        results = [r for r in [self.landing, self.product_app, self.api] if r]

        if not results:
            return "unknown"

        if all(r.ok for r in results):
            return "healthy"
        elif any(r.ok for r in results):
            return "warning"
        else:
            return "critical"

    @property
    def status_icon(self) -> str:
        """Get status icon."""
        status = self.overall_status
        if status == "healthy":
            return "🟢"
        elif status == "warning":
            return "🟡"
        elif status == "critical":
            return "🔴"
        else:
            return "⚪"


class StatusDashboard:
    """
    Lightweight status dashboard.

    Uses fast HTTP requests (no browser) to check if pages are responding.
    """

    def __init__(
        self,
        domain_runner: DomainTestRunner,
        timeout: float = 10.0,
    ):
        """
        Initialize status dashboard.

        Args:
            domain_runner: DomainTestRunner for URL building
            timeout: HTTP request timeout in seconds
        """
        self.domain_runner = domain_runner
        self.timeout = timeout

    async def check_url(
        self,
        url: str,
        project: str,
        endpoint_type: str,
    ) -> QuickStatusResult:
        """
        Quick HTTP check for a single URL.

        Args:
            url: URL to check
            project: Project name
            endpoint_type: landing, product_app, or api

        Returns:
            QuickStatusResult with status code and timing
        """
        start = time.perf_counter()

        try:
            async with httpx.AsyncClient(timeout=self.timeout, follow_redirects=True) as client:
                response = await client.get(url)
                duration_ms = (time.perf_counter() - start) * 1000

                return QuickStatusResult(
                    project=project,
                    endpoint_type=endpoint_type,
                    url=url,
                    status_code=response.status_code,
                    ok=response.status_code == 200,
                    response_time_ms=duration_ms,
                )

        except httpx.TimeoutException:
            duration_ms = (time.perf_counter() - start) * 1000
            return QuickStatusResult(
                project=project,
                endpoint_type=endpoint_type,
                url=url,
                ok=False,
                response_time_ms=duration_ms,
                error="Timeout",
            )

        except httpx.ConnectError as e:
            duration_ms = (time.perf_counter() - start) * 1000
            return QuickStatusResult(
                project=project,
                endpoint_type=endpoint_type,
                url=url,
                ok=False,
                response_time_ms=duration_ms,
                error=f"Connection failed: {str(e)[:50]}",
            )

        except Exception as e:
            duration_ms = (time.perf_counter() - start) * 1000
            return QuickStatusResult(
                project=project,
                endpoint_type=endpoint_type,
                url=url,
                ok=False,
                response_time_ms=duration_ms,
                error=str(e)[:50],
            )

    async def check_project(
        self,
        project: str,
        domain_type: str = "production",
        endpoint_types: Optional[List[str]] = None,
    ) -> ProjectStatus:
        """
        Check all endpoints for a project.

        Args:
            project: Project name
            domain_type: production or internal
            endpoint_types: List of endpoints to check (default: all)

        Returns:
            ProjectStatus with all endpoint results
        """
        if endpoint_types is None:
            endpoint_types = ["landing", "product_app", "api"]

        status = ProjectStatus(project=project)

        # Check each endpoint
        tasks = []
        for endpoint_type in endpoint_types:
            url = self.domain_runner.build_url(project, domain_type, endpoint_type)
            if url:
                tasks.append((endpoint_type, self.check_url(url, project, endpoint_type)))

        # Run checks in parallel
        for endpoint_type, task in tasks:
            result = await task
            setattr(status, endpoint_type, result)

        return status

    async def check_all(
        self,
        domain_type: str = "production",
        endpoint_types: Optional[List[str]] = None,
        instance: Optional[str] = None,
    ) -> Dict[str, ProjectStatus]:
        """
        Check status for all projects.

        Args:
            domain_type: production or internal
            endpoint_types: List of endpoints to check
            instance: Optional filter to projects on specific instance

        Returns:
            Dict of {project: ProjectStatus}
        """
        projects = self.domain_runner.get_projects(instance=instance)

        # Check all projects in parallel
        tasks = [self.check_project(p, domain_type, endpoint_types) for p in projects]
        results = await asyncio.gather(*tasks)

        return {r.project: r for r in results}


def render_dashboard_table(statuses: Dict[str, ProjectStatus]) -> str:
    """
    Render status dashboard as ASCII table.

    Args:
        statuses: Dict of project statuses

    Returns:
        Formatted ASCII table string
    """
    lines = []

    # Header
    lines.append("┌" + "─" * 78 + "┐")
    lines.append("│" + "PROBE STATUS DASHBOARD".center(78) + "│")
    lines.append("├" + "─" * 78 + "┤")
    lines.append("│" + " " * 78 + "│")

    # Column headers
    header = f"  {'PROJECT':<14}  {'LANDING':<18}  {'PRODUCT APP':<18}  {'STATUS':<8}"
    lines.append("│" + header + "  │")
    lines.append("│  " + "─" * 74 + "  │")

    # Sort projects alphabetically
    sorted_projects = sorted(statuses.keys())

    # Project rows
    for project in sorted_projects:
        status = statuses[project]

        # Format landing
        if status.landing:
            if status.landing.ok:
                landing = f"✓ {status.landing.status_code} ({status.landing.response_time_ms:.1f}ms)"
            else:
                landing = f"✗ {status.landing.error or 'Error'}"
            landing = landing[:18]
        else:
            landing = "N/A"

        # Format product_app
        if status.product_app:
            if status.product_app.ok:
                product = f"✓ {status.product_app.status_code} ({status.product_app.response_time_ms:.1f}ms)"
            else:
                product = f"✗ {status.product_app.error or 'Error'}"
            product = product[:18]
        else:
            product = "N/A"

        # Status icon
        icon = status.status_icon

        row = f"  {project:<14}  {landing:<18}  {product:<18}  {icon}       "
        lines.append("│" + row + "│")

    # Footer
    lines.append("│" + " " * 78 + "│")
    lines.append("├" + "─" * 78 + "┤")

    # Summary
    healthy = sum(1 for s in statuses.values() if s.overall_status == "healthy")
    warning = sum(1 for s in statuses.values() if s.overall_status == "warning")
    critical = sum(1 for s in statuses.values() if s.overall_status == "critical")
    total = len(statuses)

    summary = f"HEALTHY: {healthy}/{total}  │  WARNING: {warning}  │  CRITICAL: {critical}  │  [r] Refresh  [q] Quit"
    lines.append("│ " + summary.ljust(77) + "│")
    lines.append("└" + "─" * 78 + "┘")

    return "\n".join(lines)


def render_compact_table(statuses: Dict[str, ProjectStatus]) -> str:
    """
    Render compact status table (for quick checks).

    Args:
        statuses: Dict of project statuses

    Returns:
        Compact table string
    """
    lines = []

    # Count statuses
    healthy = sum(1 for s in statuses.values() if s.overall_status == "healthy")
    warning = sum(1 for s in statuses.values() if s.overall_status == "warning")
    critical = sum(1 for s in statuses.values() if s.overall_status == "critical")
    total = len(statuses)

    # One-liner summary
    summary = f"✓ {healthy}/{total} healthy │ ⚠ {warning} warning │ ✗ {critical} critical"
    lines.append(summary)

    # Show critical/warning projects
    if critical > 0:
        lines.append("\nCritical projects:")
        for project, status in sorted(statuses.items()):
            if status.overall_status == "critical":
                lines.append(f"  • {project}")

    if warning > 0:
        lines.append("\nWarning projects:")
        for project, status in sorted(statuses.items()):
            if status.overall_status == "warning":
                issues = []
                if status.landing and not status.landing.ok:
                    issues.append("landing")
                if status.product_app and not status.product_app.ok:
                    issues.append("product")
                lines.append(f"  • {project} ({', '.join(issues)})")

    return "\n".join(lines)
