#!/usr/bin/env python3
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
SEGA SECURITY SCANNING COMMAND
==============================================================================
File: src/sega/commands/scan.py
Project: SEGA (Scalable Engineering & Growth Automation)
Copyright: 2022-2025 FLEET
License: Apache-2.0

SEGA MODULE: Commands/SecurityScanning
COMPONENT: Multi-Type Security Scanner CLI Command
PURPOSE: Execute comprehensive security scans on projects and infrastructure
DEPENDENCIES: click, SecurityScanner
USAGE: sega scan [--type TYPE] [--severity LEVEL] [--output FORMAT] [--fail-on LEVEL]

This command runs multiple security scan types including dependency, static analysis,
container, infrastructure, and secrets scanning with configurable output formats.
==============================================================================
"""

import click
import os
from ...doctor.scanner import SecurityScanner
from ...core.portfolio_manager import PortfolioManager


@click.command()
@click.option(
    "--type",
    "scan_types",
    multiple=True,
    help="Scan types to run (dependency, static, container, infrastructure, secrets)",
)
@click.option(
    "--severity",
    default="medium",
    help="Minimum severity level to report (low, medium, high, critical)",
)
@click.option(
    "--output",
    type=click.Choice(["table", "json", "sarif"]),
    default="table",
    help="Output format",
)
@click.option(
    "--fail-on",
    type=click.Choice(["low", "medium", "high", "critical"]),
    default="high",
    help="Fail build on this severity level or higher",
)
@click.option(
    "--exclude", multiple=True, help="Exclude specific findings by ID"
)
@click.option(
    "--portfolio",
    is_flag=True,
    help="Scan all projects in the portfolio (workspace-wide scanning)",
)
@click.option("--team", help="Filter portfolio scan to specific team")
@click.option(
    "--project-type", help="Filter portfolio scan to specific project type"
)
def scan(
    scan_types,
    severity,
    output,
    fail_on,
    exclude,
    portfolio,
    team,
    project_type,
):
    """Run security scans on the project."""

    # Default to all scan types if none specified
    if not scan_types:
        scan_types = [
            "dependency",
            "static",
            "container",
            "infrastructure",
            "secrets",
        ]

    click.echo(" Running security scans...")
    click.echo(f"Scan types: {', '.join(scan_types)}")
    click.echo(f"Minimum severity: {severity}")

    if portfolio:
        # Portfolio-wide scanning
        click.echo(" Portfolio-wide scanning enabled")
        results = _scan_portfolio(scan_types, team, project_type)
    else:
        # Single project scanning
        scanner = SecurityScanner()
        all_results = scanner.scan_all()
        results = {
            "current_project": {
                k: v for k, v in all_results.items() if k in scan_types
            }
        }

    # Process all results from portfolio or single project
    _process_scan_results(
        results, scan_types, severity, output, fail_on, exclude
    )


def _scan_portfolio(scan_types, team_filter=None, project_type_filter=None):
    """Scan all projects in the portfolio."""
    portfolio_manager = PortfolioManager()

    click.echo(" Discovering projects in portfolio...")
    projects = portfolio_manager.discover_git_projects()

    # Apply filters
    filtered_projects = {}
    for project_path, project_info in projects.items():
        # Filter by team if specified
        if (
            team_filter
            and project_info.get("team", "").lower() != team_filter.lower()
        ):
            continue

        # Filter by project type if specified
        if (
            project_type_filter
            and project_info.get("detected_type", "").lower()
            != project_type_filter.lower()
        ):
            continue

        filtered_projects[project_path] = project_info

    click.echo(f" Found {len(filtered_projects)} projects to scan")
    if team_filter:
        click.echo(f"   Team filter: {team_filter}")
    if project_type_filter:
        click.echo(f"   Project type filter: {project_type_filter}")

    # Scan each project
    portfolio_results = {}
    current_dir = os.getcwd()

    try:
        for project_path, project_info in filtered_projects.items():
            project_full_path = str(project_info["path"])
            click.echo(
                f"\n Scanning {project_path} ({project_info.get('detected_type', 'unknown')})"
            )

            try:
                # Change to project directory
                os.chdir(project_full_path)

                # Run security scan
                scanner = SecurityScanner()
                scan_results = scanner.scan_all()

                # Store results with project context
                portfolio_results[project_path] = {
                    "project_info": project_info,
                    "scan_results": {
                        k: v
                        for k, v in scan_results.items()
                        if k in scan_types
                    },
                }

            except Exception as e:
                click.echo(f" Failed to scan {project_path}: {str(e)}")
                portfolio_results[project_path] = {
                    "project_info": project_info,
                    "scan_results": {},
                    "error": str(e),
                }

    finally:
        # Always return to original directory
        os.chdir(current_dir)

    return portfolio_results


def _process_scan_results(
    results, scan_types, severity, output, fail_on, exclude
):
    """Process and display scan results."""
    severity_levels = {"low": 0, "medium": 1, "high": 2, "critical": 3}
    min_severity = severity_levels[severity]

    total_findings = 0
    critical_findings = 0
    high_findings = 0
    total_projects_scanned = 0
    projects_with_issues = 0

    # Handle both single project and portfolio results
    if (
        isinstance(list(results.values())[0], dict)
        and "scan_results" in list(results.values())[0]
    ):
        # Portfolio results
        for project_path, project_data in results.items():
            total_projects_scanned += 1

            if "error" in project_data:
                click.echo(f" {project_path}: {project_data['error']}")
                continue

            project_has_issues = False
            project_info = project_data["project_info"]
            scan_results = project_data["scan_results"]

            click.echo(f"\n Project: {project_path}")
            click.echo(
                f"   Type: {project_info.get('detected_type', 'unknown')}"
            )
            click.echo(f"   Team: {project_info.get('team', 'unknown')}")

            for scan_type, result in scan_results.items():
                if not result.success:
                    click.echo(f" {scan_type} scan failed: {result.error}")
                    continue

                # Filter findings by severity
                filtered_findings = _filter_findings(
                    result.findings, min_severity, exclude, severity_levels
                )

                if filtered_findings:
                    project_has_issues = True
                    total_findings += len(filtered_findings)

                    for finding in filtered_findings:
                        if finding.severity == "critical":
                            critical_findings += 1
                        elif finding.severity == "high":
                            high_findings += 1

                    # Output results for this project/scan type
                    if output == "table":
                        _output_table(
                            f"{project_path}/{scan_type}", filtered_findings
                        )
                    elif output == "json":
                        _output_json_portfolio(
                            project_path,
                            scan_type,
                            filtered_findings,
                            project_info,
                        )
                    elif output == "sarif":
                        _output_sarif(
                            f"{project_path}/{scan_type}", filtered_findings
                        )

            if project_has_issues:
                projects_with_issues += 1
    else:
        # Single project results
        total_projects_scanned = 1
        for scan_type, result in results.get("current_project", {}).items():
            if not result.success:
                click.echo(f" {scan_type} scan failed: {result.error}")
                continue

            # Filter findings by severity
            filtered_findings = _filter_findings(
                result.findings, min_severity, exclude, severity_levels
            )

            if filtered_findings:
                projects_with_issues = 1
                total_findings += len(filtered_findings)

                for finding in filtered_findings:
                    if finding.severity == "critical":
                        critical_findings += 1
                    elif finding.severity == "high":
                        high_findings += 1

                # Output results
                if output == "table":
                    _output_table(scan_type, filtered_findings)
                elif output == "json":
                    _output_json(scan_type, filtered_findings)
                elif output == "sarif":
                    _output_sarif(scan_type, filtered_findings)

    # Summary
    if total_projects_scanned > 1:
        click.echo("\n Portfolio Security Scan Summary:")
        click.echo(f"Projects scanned: {total_projects_scanned}")
        click.echo(f"Projects with issues: {projects_with_issues}")
    else:
        click.echo("\n Security Scan Summary:")

    click.echo(f"Total findings: {total_findings}")
    click.echo(f"Critical: {critical_findings}")
    click.echo(f"High: {high_findings}")

    # Determine if build should fail
    fail_level = severity_levels[fail_on]
    should_fail = False

    if fail_level <= 3 and critical_findings > 0:
        should_fail = True
    elif fail_level <= 2 and high_findings > 0:
        should_fail = True

    if should_fail:
        click.echo(
            f"\n Build failed due to {fail_on} or higher severity findings"
        )
        exit(1)
    else:
        click.echo("\n Security scan completed successfully")


def _filter_findings(findings, min_severity, exclude, severity_levels):
    """Filter findings by severity and exclusions."""
    filtered_findings = []
    for finding in findings:
        if finding.title.split(":")[0] in exclude:
            continue

        finding_severity = severity_levels.get(finding.severity, 0)
        if finding_severity >= min_severity:
            filtered_findings.append(finding)

    return filtered_findings


def _output_json_portfolio(project_path, scan_type, findings, project_info):
    """Output portfolio findings in JSON format."""
    import json

    findings_data = []
    for finding in findings:
        finding_dict = {
            "severity": finding.severity,
            "title": finding.title,
            "description": finding.description,
            "file_path": finding.file_path,
            "line_number": finding.line_number,
            "cve_id": finding.cve_id,
            "fix_suggestion": finding.fix_suggestion,
        }
        findings_data.append(finding_dict)

    result = {
        "project_path": project_path,
        "project_info": {
            "team": project_info.get("team"),
            "project_name": project_info.get("project_name"),
            "detected_type": project_info.get("detected_type"),
            "git_url": project_info.get("git_url"),
            "current_branch": project_info.get("current_branch"),
        },
        "scan_type": scan_type,
        "findings": findings_data,
    }

    click.echo(json.dumps(result, indent=2))


def _output_table(scan_type, findings):
    """Output findings in table format."""
    if not findings:
        click.echo(f" {scan_type}: No issues found")
        return

    click.echo(f"\n {scan_type.title()} Scan Results:")
    click.echo("-" * 80)

    for finding in findings:
        severity_icon = {
            "critical": "",
            "high": "",
            "medium": "",
            "low": "",
        }.get(finding.severity, "")

        click.echo(
            f"{severity_icon} {finding.severity.upper()}: {finding.title}"
        )
        click.echo(f"   File: {finding.file_path}:{finding.line_number}")
        click.echo(f"   Description: {finding.description}")
        if finding.fix_suggestion:
            click.echo(f"   Fix: {finding.fix_suggestion}")
        if finding.cve_id:
            click.echo(f"   CVE: {finding.cve_id}")
        click.echo()


def _output_json(scan_type, findings):
    """Output findings in JSON format."""
    import json

    findings_data = []
    for finding in findings:
        finding_dict = {
            "severity": finding.severity,
            "title": finding.title,
            "description": finding.description,
            "file_path": finding.file_path,
            "line_number": finding.line_number,
            "cve_id": finding.cve_id,
            "fix_suggestion": finding.fix_suggestion,
        }
        findings_data.append(finding_dict)

    result = {"scan_type": scan_type, "findings": findings_data}

    click.echo(json.dumps(result, indent=2))


def _output_sarif(scan_type, findings):
    """Output findings in SARIF format."""
    import json

    # SARIF (Static Analysis Results Interchange Format)
    sarif_report = {
        "version": "2.1.0",
        "runs": [
            {
                "tool": {
                    "driver": {
                        "name": "SEGA Security Scanner",
                        "version": "0.1.0",
                    }
                },
                "results": [],
            }
        ],
    }

    for finding in findings:
        sarif_result = {
            "ruleId": finding.title.split(":")[0],
            "message": {"text": finding.description},
            "level": _severity_to_sarif_level(finding.severity),
            "locations": [
                {
                    "physicalLocation": {
                        "artifactLocation": {"uri": finding.file_path},
                        "region": {"startLine": finding.line_number},
                    }
                }
            ],
        }

        if finding.cve_id:
            sarif_result["properties"] = {"cve": finding.cve_id}

        sarif_report["runs"][0]["results"].append(sarif_result)

    click.echo(json.dumps(sarif_report, indent=2))


def _severity_to_sarif_level(severity):
    """Convert severity to SARIF level."""
    mapping = {
        "critical": "error",
        "high": "error",
        "medium": "warning",
        "low": "note",
    }
    return mapping.get(severity, "note")
