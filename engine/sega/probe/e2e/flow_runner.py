#!/usr/bin/env python3
# Copyright 2025 SEGA
"""
E2E Test Flow Runner
====================
Executes configuration-driven E2E test flows using Playwright.

Projects define flows at: {project}/tests/e2e/flows.yaml
"""

import os
import re
import time
import yaml
from pathlib import Path
from datetime import datetime
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any, Tuple

from .flow_schema import FlowConfig, TestFlow, TestAction, ActionType


@dataclass
class ActionResult:
    """Result of executing a single action."""
    action: TestAction
    passed: bool
    duration_ms: float
    error_type: Optional[str] = None       # "not_found", "not_visible", "timeout", "click_intercepted"
    error_message: Optional[str] = None
    screenshot_path: Optional[str] = None
    element_visibility: Optional[str] = None
    suggested_fix: Optional[str] = None


@dataclass
class FlowResult:
    """Result of executing a complete flow."""
    flow_name: str
    description: str
    passed: bool
    skipped: bool = False
    skip_reason: Optional[str] = None
    actions_completed: int = 0
    actions_total: int = 0
    action_results: List[ActionResult] = field(default_factory=list)
    failed_action: Optional[TestAction] = None
    error_message: Optional[str] = None
    duration_ms: float = 0.0
    screenshots: List[str] = field(default_factory=list)
    console_errors: List[str] = field(default_factory=list)
    network_failures: List[Dict[str, Any]] = field(default_factory=list)


@dataclass
class E2ETestReport:
    """Complete E2E test report for a project."""
    project: str
    profile: str
    timestamp: datetime
    duration_ms: float
    flows_total: int
    flows_passed: int
    flows_failed: int
    flows_skipped: int
    flow_results: List[FlowResult]
    console_errors_total: int = 0
    network_failures_total: int = 0

    @property
    def passed(self) -> bool:
        """Overall test passed if all non-skipped flows passed."""
        return self.flows_failed == 0


class FlowRunner:
    """
    Executes E2E test flows defined in YAML configuration.

    Usage:
        runner = FlowRunner(project="atlas")
        report = await runner.run_all_flows()
    """

    def __init__(
        self,
        project: str,
        fleet_root: Optional[Path] = None,
        profile: str = "standard",
        headed: bool = False,
        debug: bool = False,
    ):
        self.project = project
        self.fleet_root = fleet_root or Path(os.environ.get("FLEET_ROOT", Path.home() / "fleet"))
        self.profile = profile
        self.headed = headed
        self.debug = debug

        # Load configuration
        self.config = self._load_config()
        self.screenshots_dir = self.fleet_root / project / "tests" / "e2e" / "screenshots"
        self.screenshots_dir.mkdir(parents=True, exist_ok=True)

        # Runtime state
        self._console_errors: List[str] = []
        self._network_failures: List[Dict[str, Any]] = []
        self._page = None
        self._browser = None
        self._context = None

    def _load_config(self) -> FlowConfig:
        """Load flow configuration from project's tests/e2e/flows.yaml."""
        config_path = self.fleet_root / self.project / "tests" / "e2e" / "flows.yaml"

        if not config_path.exists():
            raise FileNotFoundError(
                f"E2E config not found: {config_path}\n"
                f"Create it by copying the template:\n"
                f"  cp ~/fleet/sega/templates/e2e/flows.yaml.template {config_path}"
            )

        with open(config_path) as f:
            data = yaml.safe_load(f)

        return FlowConfig.from_yaml(data)

    def _interpolate(self, value: str) -> str:
        """Replace {{VAR}} with environment variable values."""
        if not value:
            return value

        def replacer(match):
            var_name = match.group(1)
            return os.environ.get(var_name, match.group(0))

        return re.sub(r"\{\{(\w+)\}\}", replacer, value)

    async def _setup_browser(self):
        """Initialize Playwright browser and page."""
        try:
            from playwright.async_api import async_playwright
        except ImportError:
            raise ImportError(
                "Playwright not installed. Install with:\n"
                "  pip install playwright && playwright install"
            )

        self._playwright = await async_playwright().start()
        self._browser = await self._playwright.chromium.launch(
            headless=not self.headed,
            slow_mo=100 if self.debug else 0,
        )
        self._context = await self._browser.new_context(
            viewport={"width": 1280, "height": 720},
        )
        self._page = await self._context.new_page()

        # Capture console errors
        self._page.on("console", self._on_console_message)
        self._page.on("requestfailed", self._on_request_failed)

    async def _teardown_browser(self):
        """Close browser resources."""
        if self._browser:
            await self._browser.close()
        if self._playwright:
            await self._playwright.stop()

    def _on_console_message(self, message):
        """Capture console errors."""
        if message.type == "error":
            self._console_errors.append(message.text)

    def _on_request_failed(self, request):
        """Capture failed network requests."""
        self._network_failures.append({
            "url": request.url,
            "method": request.method,
            "failure": request.failure,
        })

    async def _execute_action(self, action: TestAction, flow_name: str) -> ActionResult:
        """Execute a single action and return result."""
        start_time = time.time()
        result = ActionResult(action=action, passed=False, duration_ms=0.0)

        try:
            action_type = action.action_type

            if action_type == ActionType.NAVIGATE:
                url = self._interpolate(self.config.base_url.rstrip("/") + action.selector)
                await self._page.goto(url, timeout=action.timeout_ms)
                result.passed = True

            elif action_type == ActionType.CLICK:
                selector = action.selector
                try:
                    await self._page.wait_for_selector(selector, timeout=action.timeout_ms, state="visible")
                    await self._page.click(selector, timeout=action.timeout_ms)
                    result.passed = True
                except Exception as e:
                    result = await self._handle_element_error(action, flow_name, e, "click")

            elif action_type == ActionType.FILL:
                selector = action.selector
                value = self._interpolate(action.value or "")
                try:
                    await self._page.wait_for_selector(selector, timeout=action.timeout_ms, state="visible")
                    await self._page.fill(selector, value, timeout=action.timeout_ms)
                    result.passed = True
                except Exception as e:
                    result = await self._handle_element_error(action, flow_name, e, "fill")

            elif action_type == ActionType.VERIFY:
                selector = action.selector
                try:
                    await self._page.wait_for_selector(selector, timeout=action.timeout_ms, state="visible")
                    result.passed = True
                except Exception as e:
                    result = await self._handle_element_error(action, flow_name, e, "verify")

            elif action_type == ActionType.WAIT:
                wait_ms = int(action.selector)
                await self._page.wait_for_timeout(wait_ms)
                result.passed = True

            elif action_type == ActionType.SCREENSHOT:
                filename = f"{flow_name}_{action.selector}.png"
                path = self.screenshots_dir / filename
                await self._page.screenshot(path=str(path))
                result.screenshot_path = str(path)
                result.passed = True

        except Exception as e:
            result.error_message = str(e)
            result.error_type = "unknown"

        result.duration_ms = (time.time() - start_time) * 1000

        # Capture screenshot on failure
        if not result.passed and action.action_type != ActionType.SCREENSHOT:
            try:
                step_num = len([r for r in self._flow_results if r]) + 1
                filename = f"{flow_name}_step{step_num}_fail.png"
                path = self.screenshots_dir / filename
                await self._page.screenshot(path=str(path))
                result.screenshot_path = str(path)
            except Exception:
                pass

        return result

    async def _handle_element_error(
        self, action: TestAction, flow_name: str, error: Exception, action_verb: str
    ) -> ActionResult:
        """Handle element-related errors with DOM context."""
        error_str = str(error).lower()
        result = ActionResult(action=action, passed=False, duration_ms=0.0)

        # Determine error type
        if "timeout" in error_str:
            result.error_type = "timeout"
            result.error_message = f"Timeout waiting for selector: {action.selector}"
            result.suggested_fix = f"Increase timeout or check if element exists"

        elif "not found" in error_str or "no element" in error_str:
            result.error_type = "not_found"
            result.error_message = f"Element not found: {action.selector}"
            result.suggested_fix = f"Verify selector is correct or add data-testid"

        elif "not visible" in error_str or "hidden" in error_str:
            result.error_type = "not_visible"
            result.error_message = f"Element not visible: {action.selector}"
            result.suggested_fix = f"Wait for element visibility: await page.waitForSelector('{action.selector}', {{state: 'visible'}})"

        elif "intercept" in error_str or "other element" in error_str:
            result.error_type = "click_intercepted"
            result.error_message = f"Element covered by another element: {action.selector}"
            result.suggested_fix = f"Close modal/overlay before clicking, or scroll element into view"

        else:
            result.error_type = "unknown"
            result.error_message = str(error)

        # Try to get element visibility state
        try:
            element = await self._page.query_selector(action.selector)
            if element:
                is_visible = await element.is_visible()
                box = await element.bounding_box()
                result.element_visibility = "visible" if is_visible else "hidden"
                if box and (box["width"] == 0 or box["height"] == 0):
                    result.element_visibility = "zero-size"
            else:
                result.element_visibility = "not-in-dom"
        except Exception:
            result.element_visibility = "unknown"

        return result

    async def run_flow(self, flow_name: str) -> FlowResult:
        """Execute a single flow by name."""
        flow = self.config.get_flow(flow_name)
        if not flow:
            return FlowResult(
                flow_name=flow_name,
                description="",
                passed=False,
                skipped=True,
                skip_reason=f"Flow '{flow_name}' not found in config",
            )

        start_time = time.time()
        result = FlowResult(
            flow_name=flow_name,
            description=flow.description,
            passed=False,
            actions_total=len(flow.actions),
        )

        self._flow_results = []

        for i, action in enumerate(flow.actions):
            action_result = await self._execute_action(action, flow_name)
            result.action_results.append(action_result)
            self._flow_results.append(action_result)

            if action_result.screenshot_path:
                result.screenshots.append(action_result.screenshot_path)

            if action_result.passed:
                result.actions_completed += 1
            else:
                result.failed_action = action
                result.error_message = action_result.error_message
                break

        result.duration_ms = (time.time() - start_time) * 1000
        result.passed = result.actions_completed == result.actions_total
        result.console_errors = list(self._console_errors)
        result.network_failures = list(self._network_failures)

        # Clear per-flow errors
        self._console_errors = []
        self._network_failures = []

        return result

    async def run_all_flows(self, flow_names: Optional[List[str]] = None) -> E2ETestReport:
        """
        Execute all flows in dependency order.

        Args:
            flow_names: Optional list of specific flows to run. If None, runs all.

        Returns:
            E2ETestReport with complete results.
        """
        start_time = time.time()
        flow_results: List[FlowResult] = []
        passed_flows: set = set()
        failed_flows: set = set()

        await self._setup_browser()

        try:
            # Determine which flows to run
            if flow_names:
                execution_order = flow_names
            else:
                execution_order = self.config.get_execution_order()

            for flow_name in execution_order:
                flow = self.config.get_flow(flow_name)
                if not flow:
                    continue

                # Check preconditions
                unmet_preconditions = [
                    p for p in flow.preconditions
                    if p not in passed_flows
                ]

                if unmet_preconditions:
                    result = FlowResult(
                        flow_name=flow_name,
                        description=flow.description,
                        passed=False,
                        skipped=True,
                        skip_reason=f"Precondition '{unmet_preconditions[0]}' failed",
                        actions_total=len(flow.actions),
                    )
                else:
                    result = await self.run_flow(flow_name)

                flow_results.append(result)

                if result.passed:
                    passed_flows.add(flow_name)
                elif not result.skipped:
                    failed_flows.add(flow_name)

        finally:
            await self._teardown_browser()

        # Build report
        total_console_errors = sum(len(r.console_errors) for r in flow_results)
        total_network_failures = sum(len(r.network_failures) for r in flow_results)

        return E2ETestReport(
            project=self.project,
            profile=self.profile,
            timestamp=datetime.now(),
            duration_ms=(time.time() - start_time) * 1000,
            flows_total=len(flow_results),
            flows_passed=len(passed_flows),
            flows_failed=len(failed_flows),
            flows_skipped=len([r for r in flow_results if r.skipped]),
            flow_results=flow_results,
            console_errors_total=total_console_errors,
            network_failures_total=total_network_failures,
        )


def format_report(report: E2ETestReport) -> str:
    """Format E2E test report for CLI output."""
    lines = []
    lines.append("=" * 70)
    lines.append(f"{report.project.upper()} E2E TEST REPORT")
    lines.append("=" * 70)
    lines.append(f"Profile:   {report.profile}")
    lines.append(f"Flows:     {report.flows_total} defined, {report.flows_passed} passed, {report.flows_failed} failed")
    lines.append(f"Duration:  {report.duration_ms / 1000:.2f}s")
    lines.append("")

    for result in report.flow_results:
        status = "PASS" if result.passed else ("SKIPPED" if result.skipped else "FAIL")
        duration = f"({result.duration_ms / 1000:.1f}s)" if not result.skipped else ""
        lines.append(f"[FLOW: {result.flow_name}] {status} {duration}")
        lines.append("-" * 70)

        if result.skipped:
            lines.append(f"  Reason: {result.skip_reason}")
        else:
            for i, action_result in enumerate(result.action_results, 1):
                action = action_result.action
                status_icon = "PASS" if action_result.passed else "FAIL"
                duration = f"{action_result.duration_ms:.0f}ms"

                if action.action_type == ActionType.NAVIGATE:
                    desc = f"navigate {action.selector}"
                elif action.action_type == ActionType.FILL:
                    desc = f"fill {action.selector}"
                else:
                    desc = f"{action.action} {action.selector[:30]}"

                lines.append(f"  {i}. {desc:40} {status_icon:6} {duration}")

                if not action_result.passed:
                    lines.append("")
                    lines.append(f"  ERROR: {action_result.error_message}")
                    if action_result.element_visibility:
                        lines.append(f"  - Visibility: {action_result.element_visibility}")
                    if action_result.screenshot_path:
                        lines.append(f"  - Screenshot: {action_result.screenshot_path}")
                    if action_result.suggested_fix:
                        lines.append("")
                        lines.append(f"  Suggested Fix:")
                        lines.append(f"  {action_result.suggested_fix}")

            if result.console_errors:
                lines.append(f"\n  Console Errors: {len(result.console_errors)}")
            if result.network_failures:
                lines.append(f"  Network Failures: {len(result.network_failures)}")

        lines.append("")

    # Summary
    lines.append("=" * 70)
    lines.append(f"SUMMARY: {'PASS' if report.passed else 'FAIL'}")
    lines.append(f"  Flows: {report.flows_passed}/{report.flows_total} passed ({100 * report.flows_passed / max(report.flows_total, 1):.0f}%)")
    lines.append(f"  Console Errors: {report.console_errors_total}")
    lines.append(f"  Network Failures: {report.network_failures_total}")
    lines.append("=" * 70)

    return "\n".join(lines)
