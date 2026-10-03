#!/usr/bin/env python3
# Copyright 2025 SEGA
"""
Console Scanner
===============
Playwright-based console log scanner for FLEET project pages.
Scans landing and product app pages for console errors/warnings.
"""

import asyncio
import time
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional

from .console_message import (
    ConsoleMessage,
    ConsoleMessageCollector,
    NetworkFailure,
)
from .domain_test_runner import DomainTestRunner


@dataclass
class PageScanResult:
    """Result of scanning a single page."""

    project: str
    domain: str
    domain_type: str  # production, internal
    endpoint_type: str  # landing, product_app
    url: str
    success: bool  # True if page loaded

    # HTTP
    status_code: Optional[int] = None
    load_time_ms: Optional[float] = None

    # Console messages
    console_errors: List[ConsoleMessage] = field(default_factory=list)
    console_warnings: List[ConsoleMessage] = field(default_factory=list)
    total_error_count: int = 0
    total_warning_count: int = 0

    # Network
    network_failures: List[NetworkFailure] = field(default_factory=list)

    # Performance
    fcp_ms: Optional[float] = None  # First Contentful Paint
    lcp_ms: Optional[float] = None  # Largest Contentful Paint

    # Error info
    error: Optional[str] = None
    screenshot_path: Optional[str] = None
    timestamp: str = field(default_factory=lambda: datetime.now().isoformat())


@dataclass
class ProjectScanResult:
    """Result of scanning all pages for a project."""

    project: str
    domain_type: str
    results: List[PageScanResult] = field(default_factory=list)
    total_errors: int = 0
    total_warnings: int = 0
    duration_seconds: float = 0.0

    @property
    def has_errors(self) -> bool:
        """Check if any page has errors."""
        return self.total_errors > 0

    @property
    def status(self) -> str:
        """Get overall status: healthy, warning, critical."""
        if self.total_errors > 0:
            return "critical"
        elif self.total_warnings > 0:
            return "warning"
        else:
            return "healthy"


class ConsoleScanner:
    """
    Playwright-based console log scanner.

    Scans project pages for console errors, warnings, and network failures.
    """

    def __init__(
        self,
        domain_runner: DomainTestRunner,
        headed: bool = False,
        screenshot_errors: bool = True,
        timeout: int = 30,
        ignore_patterns: Optional[List[str]] = None,
    ):
        """
        Initialize console scanner.

        Args:
            domain_runner: DomainTestRunner for URL building
            headed: Run browser in headed mode
            screenshot_errors: Capture screenshots on errors
            timeout: Page load timeout in seconds
            ignore_patterns: Console message patterns to ignore
        """
        self.domain_runner = domain_runner
        self.headed = headed
        self.screenshot_errors = screenshot_errors
        self.timeout = timeout * 1000  # Convert to ms
        self.ignore_patterns = ignore_patterns or []

        # Screenshot directory
        self.screenshots_dir = Path.home() / "fleet" / "sega" / "docs" / "reports" / "console_scans" / "screenshots"
        self.screenshots_dir.mkdir(parents=True, exist_ok=True)

    async def _setup_browser(self):
        """Initialize Playwright browser."""
        try:
            from playwright.async_api import async_playwright
        except ImportError:
            raise ImportError("Playwright not installed. Install with:\n  pip install playwright && playwright install")

        self._playwright = await async_playwright().start()
        self._browser = await self._playwright.chromium.launch(
            headless=not self.headed,
        )
        self._context = await self._browser.new_context(
            viewport={"width": 1280, "height": 720},
        )

    async def _teardown_browser(self):
        """Close browser resources."""
        if hasattr(self, "_browser") and self._browser:
            await self._browser.close()
        if hasattr(self, "_playwright") and self._playwright:
            await self._playwright.stop()

    async def scan_page(
        self,
        url: str,
        project: str,
        domain: str,
        domain_type: str,
        endpoint_type: str,
    ) -> PageScanResult:
        """
        Scan a single page with Playwright.

        Args:
            url: Page URL to scan
            project: Project name
            domain: Domain name
            domain_type: production or internal
            endpoint_type: landing or product_app

        Returns:
            PageScanResult with console logs and performance data
        """
        result = PageScanResult(
            project=project,
            domain=domain,
            domain_type=domain_type,
            endpoint_type=endpoint_type,
            url=url,
            success=False,
        )

        # Create message collector
        collector = ConsoleMessageCollector(ignore_patterns=self.ignore_patterns)
        network_failures = []

        # Create new page
        page = await self._context.new_page()

        # Set up console listener
        def on_console(msg):
            if msg.type in ["error", "warning"]:
                collector.add_message(msg)

        # Set up network failure listener
        def on_request_failed(request):
            network_failures.append(
                NetworkFailure(
                    url=request.url,
                    method=request.method,
                    error=request.failure,
                )
            )

        page.on("console", on_console)
        page.on("requestfailed", on_request_failed)

        start = time.perf_counter()

        try:
            # Navigate to page
            response = await page.goto(url, timeout=self.timeout, wait_until="networkidle")
            duration_ms = (time.perf_counter() - start) * 1000

            result.success = True
            result.status_code = response.status if response else None
            result.load_time_ms = duration_ms

            # Capture performance metrics
            try:
                metrics = await page.evaluate("""() => {
                    const navigation = performance.getEntriesByType('navigation')[0];
                    const paint = performance.getEntriesByType('paint');
                    
                    return {
                        fcp: paint.find(p => p.name === 'first-contentful-paint')?.startTime || null,
                        lcp: null  // Would need PerformanceObserver for LCP
                    };
                }""")

                result.fcp_ms = metrics.get("fcp")
                result.lcp_ms = metrics.get("lcp")
            except Exception:
                pass  # Performance metrics are optional

            # Get collected messages
            result.console_errors = [m for m in collector.get_summary() if m.type == "error"]
            result.console_warnings = [m for m in collector.get_summary() if m.type == "warning"]

            counts = collector.get_counts()
            result.total_error_count = counts["error"]
            result.total_warning_count = counts["warning"]

            result.network_failures = network_failures

            # Screenshot on errors
            if self.screenshot_errors and result.total_error_count > 0:
                screenshot_name = f"{project}_{endpoint_type}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.png"
                screenshot_path = self.screenshots_dir / screenshot_name
                await page.screenshot(path=str(screenshot_path))
                result.screenshot_path = str(screenshot_path)

        except Exception as e:
            duration_ms = (time.perf_counter() - start) * 1000
            result.success = False
            result.error = str(e)
            result.load_time_ms = duration_ms

            # Screenshot on failure
            if self.screenshot_errors:
                try:
                    screenshot_name = f"{project}_{endpoint_type}_error_{datetime.now().strftime('%Y%m%d_%H%M%S')}.png"
                    screenshot_path = self.screenshots_dir / screenshot_name
                    await page.screenshot(path=str(screenshot_path))
                    result.screenshot_path = str(screenshot_path)
                except Exception:
                    pass  # Screenshot failed, continue

        finally:
            await page.close()

        return result

    async def scan_project(
        self,
        project: str,
        domain_type: str = "production",
        endpoint_types: Optional[List[str]] = None,
    ) -> ProjectScanResult:
        """
        Scan all pages for a project.

        Args:
            project: Project name
            domain_type: production or internal
            endpoint_types: List of endpoints to scan (default: ['landing', 'product_app'])

        Returns:
            ProjectScanResult with all page scan results
        """
        if endpoint_types is None:
            endpoint_types = ["landing", "product_app"]

        start = time.perf_counter()
        results = []

        config = self.domain_runner.get_project_config(project)
        if not config:
            return ProjectScanResult(
                project=project,
                domain_type=domain_type,
                duration_seconds=0.0,
            )

        domain = config.get("domains", {}).get(domain_type)
        if not domain:
            return ProjectScanResult(
                project=project,
                domain_type=domain_type,
                duration_seconds=0.0,
            )

        # Scan each endpoint type
        for endpoint_type in endpoint_types:
            url = self.domain_runner.build_url(project, domain_type, endpoint_type)
            if url:
                result = await self.scan_page(url, project, domain, domain_type, endpoint_type)
                results.append(result)

        duration = time.perf_counter() - start

        # Aggregate totals
        total_errors = sum(r.total_error_count for r in results)
        total_warnings = sum(r.total_warning_count for r in results)

        return ProjectScanResult(
            project=project,
            domain_type=domain_type,
            results=results,
            total_errors=total_errors,
            total_warnings=total_warnings,
            duration_seconds=duration,
        )

    async def scan_projects(
        self,
        projects: List[str],
        domain_type: str = "production",
        endpoint_types: Optional[List[str]] = None,
    ) -> Dict[str, ProjectScanResult]:
        """
        Scan multiple projects.

        Args:
            projects: List of project names
            domain_type: production or internal
            endpoint_types: List of endpoints to scan

        Returns:
            Dict of {project: ProjectScanResult}
        """
        await self._setup_browser()

        results = {}

        try:
            for project in projects:
                result = await self.scan_project(project, domain_type, endpoint_types)
                results[project] = result
        finally:
            await self._teardown_browser()

        return results

    async def scan_all(
        self,
        domain_type: str = "production",
        endpoint_types: Optional[List[str]] = None,
        instance: Optional[str] = None,
    ) -> Dict[str, ProjectScanResult]:
        """
        Scan all projects.

        Args:
            domain_type: production or internal
            endpoint_types: List of endpoints to scan
            instance: Optional filter to projects on specific instance

        Returns:
            Dict of {project: ProjectScanResult}
        """
        projects = self.domain_runner.get_projects(instance=instance)
        return await self.scan_projects(projects, domain_type, endpoint_types)
