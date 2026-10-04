#!/usr/bin/env python3
# Copyright 2025 SEGA
"""
Scan Report Generator
=====================
Generate markdown and JSON reports from console scan results.
"""

import json
from datetime import datetime
from pathlib import Path
from typing import Dict, List

from .console_scanner import PageScanResult, ProjectScanResult


class ScanReportGenerator:
    """Generate comprehensive console scan reports."""

    def __init__(self, output_dir: Path):
        """
        Initialize report generator.

        Args:
            output_dir: Directory for report output
        """
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)

    def generate_markdown_report(
        self,
        scan_results: Dict[str, ProjectScanResult],
        domain_type: str = "production",
        detail_level: str = "summary",
    ) -> Path:
        """
        Generate markdown report.

        Args:
            scan_results: Dict of {project: ProjectScanResult}
            domain_type: production or internal
            detail_level: minimal, summary, or full

        Returns:
            Path to generated report file
        """
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"CONSOLE_SCAN_{timestamp}.md"
        filepath = self.output_dir / filename

        lines = []

        # Title
        lines.append(f"# Console Scan Report")
        lines.append("")
        lines.append(f"**Generated**: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        lines.append(f"**Domain Type**: {domain_type}")
        lines.append(f"**Projects Scanned**: {len(scan_results)}")
        lines.append("")

        # Summary statistics
        total_errors = sum(r.total_errors for r in scan_results.values())
        total_warnings = sum(r.total_warnings for r in scan_results.values())
        critical_count = sum(1 for r in scan_results.values() if r.status == "critical")
        warning_count = sum(1 for r in scan_results.values() if r.status == "warning")
        healthy_count = sum(1 for r in scan_results.values() if r.status == "healthy")

        lines.append("## Summary")
        lines.append("")
        lines.append(f"- **Total Errors**: {total_errors}")
        lines.append(f"- **Total Warnings**: {total_warnings}")
        lines.append(f"- **Critical Projects**: {critical_count}")
        lines.append(f"- **Warning Projects**: {warning_count}")
        lines.append(f"- **Healthy Projects**: {healthy_count}")
        lines.append("")

        # Critical issues (always show)
        critical_projects = [(name, result) for name, result in scan_results.items() if result.status == "critical"]

        if critical_projects:
            lines.append("## Critical Issues")
            lines.append("")

            for project, result in sorted(critical_projects):
                lines.append(f"### {project.capitalize()}")
                lines.append("")

                for page_result in result.results:
                    if page_result.total_error_count > 0 or not page_result.success:
                        lines.append(f"**{page_result.endpoint_type.replace('_', ' ').title()}** ({page_result.url})")
                        lines.append("")

                        if not page_result.success:
                            lines.append(f"- ❌ Page failed to load: {page_result.error}")
                            lines.append("")
                        elif page_result.console_errors:
                            for msg in page_result.console_errors[:5]:  # Top 5 errors
                                count_str = f" (×{msg.count})" if msg.count > 1 else ""
                                location_str = f" - `{msg.location}`" if msg.location else ""
                                lines.append(f"- [ERROR] {msg.message}{count_str}{location_str}")

                            if len(page_result.console_errors) > 5:
                                remaining = len(page_result.console_errors) - 5
                                lines.append(f"- ... and {remaining} more errors")
                            lines.append("")

                        if page_result.network_failures:
                            lines.append(f"**Network Failures**: {len(page_result.network_failures)}")
                            for nf in page_result.network_failures[:3]:
                                lines.append(f"- {nf.method} {nf.url} - {nf.error}")
                            lines.append("")

                        if page_result.screenshot_path:
                            lines.append(f"**Screenshot**: `{page_result.screenshot_path}`")
                            lines.append("")

            lines.append("---")
            lines.append("")

        # All projects (if detail_level allows)
        if detail_level in ["summary", "full"]:
            lines.append("## All Projects")
            lines.append("")

            for project in sorted(scan_results.keys()):
                result = scan_results[project]

                # Status icon
                if result.status == "healthy":
                    icon = "✓"
                elif result.status == "warning":
                    icon = "⚠️"
                else:
                    icon = "❌"

                lines.append(f"### {project.capitalize()} {icon}")
                lines.append("")

                if result.status == "healthy":
                    lines.append("- **Status**: All pages clean")
                    if detail_level == "minimal":
                        lines.append("")
                        continue

                for page_result in result.results:
                    endpoint_name = page_result.endpoint_type.replace("_", " ").title()
                    lines.append(f"**{endpoint_name}**: {page_result.url}")
                    lines.append("")

                    if not page_result.success:
                        lines.append(f"- ❌ Failed: {page_result.error}")
                    else:
                        lines.append(f"- Status: {page_result.status_code}")
                        lines.append(f"- Load Time: {page_result.load_time_ms:.0f}ms")

                        if page_result.total_error_count > 0:
                            lines.append(
                                f"- Console Errors: {page_result.total_error_count} ({len(page_result.console_errors)} unique)"
                            )

                            if detail_level == "full":
                                for msg in page_result.console_errors:
                                    count_str = f" (×{msg.count})" if msg.count > 1 else ""
                                    location_str = f" at `{msg.location}`" if msg.location else ""
                                    lines.append(f"  - {msg.message}{count_str}{location_str}")

                        if page_result.total_warning_count > 0:
                            lines.append(
                                f"- Console Warnings: {page_result.total_warning_count} ({len(page_result.console_warnings)} unique)"
                            )

                        if page_result.network_failures:
                            lines.append(f"- Network Failures: {len(page_result.network_failures)}")

                    lines.append("")

                lines.append("---")
                lines.append("")

        # Cross-project patterns
        if detail_level in ["summary", "full"] and total_errors > 0:
            patterns = self._analyze_patterns(scan_results)

            if patterns:
                lines.append("## Cross-Project Patterns")
                lines.append("")

                for i, (pattern, projects) in enumerate(patterns[:5], 1):
                    lines.append(f"### Pattern {i}: {pattern}")
                    lines.append(f"**Affected projects ({len(projects)})**: {', '.join(sorted(projects))}")
                    lines.append("")

        # Write report
        with open(filepath, "w") as f:
            f.write("\n".join(lines))

        return filepath

    def generate_json_export(
        self,
        scan_results: Dict[str, ProjectScanResult],
    ) -> Path:
        """
        Generate JSON export of scan results.

        Args:
            scan_results: Dict of {project: ProjectScanResult}

        Returns:
            Path to generated JSON file
        """
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"console_scan_{timestamp}.json"
        filepath = self.output_dir / filename

        # Convert to JSON-serializable format
        data = {
            "timestamp": datetime.now().isoformat(),
            "projects": {},
        }

        for project, result in scan_results.items():
            project_data = {
                "status": result.status,
                "total_errors": result.total_errors,
                "total_warnings": result.total_warnings,
                "duration_seconds": result.duration_seconds,
                "pages": [],
            }

            for page_result in result.results:
                page_data = {
                    "endpoint_type": page_result.endpoint_type,
                    "url": page_result.url,
                    "success": page_result.success,
                    "status_code": page_result.status_code,
                    "load_time_ms": page_result.load_time_ms,
                    "error_count": page_result.total_error_count,
                    "warning_count": page_result.total_warning_count,
                    "errors": [
                        {
                            "message": msg.message,
                            "location": msg.location,
                            "count": msg.count,
                        }
                        for msg in page_result.console_errors
                    ],
                    "warnings": [
                        {
                            "message": msg.message,
                            "location": msg.location,
                            "count": msg.count,
                        }
                        for msg in page_result.console_warnings
                    ],
                }

                if page_result.error:
                    page_data["error"] = page_result.error

                project_data["pages"].append(page_data)

            data["projects"][project] = project_data

        # Write JSON
        with open(filepath, "w") as f:
            json.dump(data, f, indent=2)

        return filepath

    def _analyze_patterns(
        self,
        scan_results: Dict[str, ProjectScanResult],
    ) -> List[tuple]:
        """
        Analyze cross-project error patterns.

        Args:
            scan_results: Dict of scan results

        Returns:
            List of (pattern_description, affected_projects)
        """
        patterns = {}

        # Look for common error messages across projects
        for project, result in scan_results.items():
            for page_result in result.results:
                for error in page_result.console_errors:
                    # Use first 50 chars as pattern key
                    pattern = error.message[:50]

                    if pattern not in patterns:
                        patterns[pattern] = set()
                    patterns[pattern].add(project)

        # Filter to patterns affecting 2+ projects
        cross_project = [(pattern, projects) for pattern, projects in patterns.items() if len(projects) >= 2]

        # Sort by number of affected projects (descending)
        cross_project.sort(key=lambda x: len(x[1]), reverse=True)

        return cross_project
