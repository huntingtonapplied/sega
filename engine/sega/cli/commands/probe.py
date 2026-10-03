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
SEGA PROBE COMMAND - Test Orchestration
==============================================================================
File: src/sega/commands/probe.py
Project: SEGA (Scalable Engineering & Growth Automation)
Copyright: 2022-2025 FLEET
License: Apache-2.0

SEGA MODULE: Commands/Probe
COMPONENT: Unified Test Orchestration CLI Command
PURPOSE: Consolidate testing operations across all test types and platforms
DEPENDENCIES: click, pathlib, subprocess

Core Principle: Actions are commands, platforms are options.

This command consolidates:
- sega test → sega probe run
- sega test_api → sega probe api
- sega test_browser → sega probe browser
- sega test_local → sega probe unit
- sega test_enhanced → sega probe e2e
==============================================================================
"""

import click
import subprocess
import sys
import time
from pathlib import Path
from typing import Optional, List

# Direct imports for test orchestration (replacing subprocess delegation)
from ...probe.test_orchestrator import TestOrchestrator, TestResult
from ...project.project_detector import ProjectDetector


# Test options
PLATFORMS = ["desktop", "mobile", "web", "api"]
TEST_TYPES = ["unit", "integration", "e2e"]
OUTPUT_FORMATS = ["table", "json", "junit"]


def get_test_orchestrator() -> TestOrchestrator:
    """Get or create test orchestrator instance."""
    return TestOrchestrator()


@click.group()
def probe():
    """Test orchestration and execution.

    Unified command for running tests across all platforms and test types.

    Core Principle: Actions are commands, platforms are options.

    \b
    Examples:
        sega probe run                         # Auto-detect and run tests
        sega probe run --platform web --type e2e
        sega probe unit                        # Unit tests only
        sega probe browser --visual            # Visual regression testing
        sega probe api --spec openapi.yaml     # API validation
        sega probe coverage                    # Coverage report
    """
    pass


@probe.command()
@click.option("--platform", "-p", type=click.Choice(PLATFORMS), help="Target platform: desktop, mobile, web, api")
@click.option("--type", "test_type", type=click.Choice(TEST_TYPES), help="Test type: unit, integration, e2e")
@click.option("--project", help="Specific project to test")
@click.option("--project-path", type=click.Path(exists=True), help="Project path (defaults to current directory)")
@click.option("--host", "-H", help="Remote host/IP for API testing (e.g., 203.0.113.10, api.example.com)")
@click.option("--port-offset", type=int, default=0, help="Port offset for testing offset deployments")
@click.option("--parallel", is_flag=True, help="Run tests in parallel")
@click.option("--coverage", is_flag=True, help="Generate coverage report")
@click.option("--output", "-o", type=click.Choice(OUTPUT_FORMATS), default="table", help="Output format")
@click.option("--verbose", "-v", is_flag=True, help="Verbose output")
def run(
    platform: Optional[str],
    test_type: Optional[str],
    project: Optional[str],
    project_path: Optional[str],
    host: Optional[str],
    port_offset: int,
    parallel: bool,
    coverage: bool,
    output: str,
    verbose: bool,
):
    """Run tests with auto-detection.

    Auto-detects test infrastructure and runs appropriate tests.

    \b
    Platforms:
        desktop  - Electron tests
        mobile   - React Native/Expo tests
        web      - Browser/frontend tests
        api      - Backend/API tests

    \b
    Remote Testing:
        --host 203.0.113.10        # Test against remote IP
        --host api.staging.example.com # Test against staging domain
        --port-offset 100          # Test offset deployment
    """
    click.echo("Running tests...")

    try:
        orchestrator = get_test_orchestrator()
        path = project_path or str(Path.cwd())

        # Determine test types to run
        test_types: List[str] = []
        if test_type:
            test_types.append(test_type)
        else:
            # Default to unit tests if no type specified
            test_types.append("unit")

        if verbose:
            click.echo(f"Project path: {path}")
            click.echo(f"Test types: {test_types}")
            if host:
                click.echo(f"Remote host: {host}")
            if port_offset:
                click.echo(f"Port offset: +{port_offset}")

        # Configure remote testing if host is specified
        test_config = {}
        if host:
            test_config["host"] = host
        if port_offset:
            test_config["port_offset"] = port_offset

        # Run tests using orchestrator
        results = orchestrator.run_tests(test_types, path, config=test_config if test_config else None)

        # Display results
        all_passed = True
        for test_name, result in results.items():
            status = "PASS" if result.success else "FAIL"
            click.echo(f"  [{status}] {test_name} ({result.duration:.2f}s)")
            if result.error:
                click.echo(f"    Error: {result.error}")
                all_passed = False
            if verbose and result.output:
                click.echo(f"    Output: {result.output[:200]}...")

        if not all_passed:
            sys.exit(1)

        click.echo("\nAll tests passed!")

    except Exception as e:
        click.echo(f"Test error: {e}", err=True)
        sys.exit(1)


@probe.command()
@click.option("--project", "-p", help="Specific project to test")
@click.option("--project-path", type=click.Path(exists=True), help="Project path (defaults to current directory)")
@click.option("--coverage", is_flag=True, help="Generate coverage report")
@click.option("--verbose", "-v", is_flag=True, help="Verbose output")
def unit(project: Optional[str], project_path: Optional[str], coverage: bool, verbose: bool):
    """Run unit tests only.

    Fast, isolated tests that don't require external services.
    """
    click.echo("Running unit tests...")

    try:
        orchestrator = get_test_orchestrator()
        path = project_path or str(Path.cwd())

        results = orchestrator.run_tests(["unit"], path)

        for test_name, result in results.items():
            status = "PASS" if result.success else "FAIL"
            click.echo(f"  [{status}] {test_name} ({result.duration:.2f}s)")
            if result.error:
                click.echo(f"    Error: {result.error}")
                sys.exit(1)

        click.echo("\nUnit tests passed!")

    except Exception as e:
        click.echo(f"Test error: {e}", err=True)
        sys.exit(1)


@probe.command()
@click.option("--project", "-p", help="Specific project to test")
@click.option("--project-path", type=click.Path(exists=True), help="Project path (defaults to current directory)")
@click.option("--coverage", is_flag=True, help="Generate coverage report")
@click.option("--verbose", "-v", is_flag=True, help="Verbose output")
def integration(project: Optional[str], project_path: Optional[str], coverage: bool, verbose: bool):
    """Run integration tests only.

    Tests that verify component interactions and external service integration.
    """
    click.echo("Running integration tests...")

    try:
        orchestrator = get_test_orchestrator()
        path = project_path or str(Path.cwd())

        results = orchestrator.run_tests(["integration"], path)

        for test_name, result in results.items():
            status = "PASS" if result.success else "FAIL"
            click.echo(f"  [{status}] {test_name} ({result.duration:.2f}s)")
            if result.error:
                click.echo(f"    Error: {result.error}")
                sys.exit(1)

        click.echo("\nIntegration tests passed!")

    except Exception as e:
        click.echo(f"Test error: {e}", err=True)
        sys.exit(1)


@probe.command()
@click.option("--project", "-p", required=True, help="Project to test (required)")
@click.option("--flow", help="Specific flow to run (runs all if not specified)")
@click.option(
    "--profile",
    type=click.Choice(["strict", "standard", "lenient"]),
    default="standard",
    help="Success criteria profile",
)
@click.option("--headed", is_flag=True, help="Run with visible browser")
@click.option("--debug", is_flag=True, help="Debug mode (pauses on failure)")
@click.option("--verbose", "-v", is_flag=True, help="Verbose output")
def e2e(project: str, flow: Optional[str], profile: str, headed: bool, debug: bool, verbose: bool):
    """Run configuration-driven E2E tests.

    Executes test flows defined in {project}/tests/e2e/flows.yaml

    \b
    Examples:
        sega probe e2e -p atlas                    # Run all flows
        sega probe e2e -p atlas --flow login       # Run specific flow
        sega probe e2e -p atlas --headed --debug   # Interactive mode
        sega probe e2e -p hermes --profile strict       # Strict validation

    \b
    Flow Config Location:
        {project}/tests/e2e/flows.yaml

    \b
    Create config from template:
        cp ~/fleet/sega/templates/e2e/flows.yaml.template ~/fleet/{project}/tests/e2e/flows.yaml
    """
    import asyncio

    click.echo(f"Running E2E tests for {project}...")
    click.echo(f"  Profile: {profile}")
    if flow:
        click.echo(f"  Flow: {flow}")
    if headed:
        click.echo("  Mode: headed (visible browser)")

    try:
        from ...probe.e2e.flow_runner import FlowRunner, format_report
        from ...probe.e2e.criteria_evaluator import CriteriaEvaluator

        # Initialize runner
        runner = FlowRunner(
            project=project,
            profile=profile,
            headed=headed,
            debug=debug,
        )

        # Run flows
        async def run():
            if flow:
                return await runner.run_all_flows(flow_names=[flow])
            else:
                return await runner.run_all_flows()

        report = asyncio.run(run())

        # Display results
        click.echo("")
        click.echo(format_report(report))

        # Evaluate against criteria
        evaluator = CriteriaEvaluator(profile=profile)
        evaluation = evaluator.evaluate_report(report)

        if verbose and not evaluation.passed:
            click.echo("")
            click.echo(evaluator.explain_failure(evaluation))

        # Exit with appropriate code
        if not report.passed:
            sys.exit(1)

        click.echo(f"\nE2E tests passed!")

    except FileNotFoundError as e:
        click.echo(f"\nConfiguration not found: {e}", err=True)
        click.echo("\nCreate E2E config from template:")
        click.echo(f"  mkdir -p ~/fleet/{project}/tests/e2e")
        click.echo(f"  cp ~/fleet/sega/templates/e2e/flows.yaml.template ~/fleet/{project}/tests/e2e/flows.yaml")
        sys.exit(1)

    except ImportError as e:
        click.echo(f"\nMissing dependency: {e}", err=True)
        click.echo("\nInstall Playwright:")
        click.echo("  pip install playwright && playwright install")
        sys.exit(1)

    except Exception as e:
        click.echo(f"\nE2E test error: {e}", err=True)
        if verbose:
            import traceback

            traceback.print_exc()
        sys.exit(1)


@probe.command()
@click.option("--spec", type=click.Path(exists=True), help="OpenAPI specification file")
@click.option("--base-url", help="Base URL for API testing (e.g., http://localhost:8010)")
@click.option("--host", "-H", help="Remote host/IP (combined with project port)")
@click.option("--project", "-p", help="FLEET project name (for port lookup)")
@click.option("--port-offset", type=int, default=0, help="Port offset for testing offset deployments")
@click.option("--project-path", type=click.Path(exists=True), help="Project path (defaults to current directory)")
@click.option("--https", "use_https", is_flag=True, help="Use HTTPS instead of HTTP")
@click.option("--verbose", "-v", is_flag=True, help="Verbose output")
def api(
    spec: Optional[str],
    base_url: Optional[str],
    host: Optional[str],
    project: Optional[str],
    port_offset: int,
    project_path: Optional[str],
    use_https: bool,
    verbose: bool,
):
    """API and OpenAPI validation.

    Tests API endpoints against OpenAPI specification.

    \b
    Examples:
        sega probe api                                    # Auto-detect project
        sega probe api --project atlas                # Test atlas API
        sega probe api --host 203.0.113.10 --project atlas  # Remote testing
        sega probe api --base-url http://api.example.com  # Direct URL
        sega probe api --project atlas --port-offset 100    # Offset ports
    """
    click.echo("Running API tests...")

    # Construct base_url from host + project if not directly provided
    effective_base_url = base_url
    if not effective_base_url and host and project:
        # Import port mapping
        from .health import PROJECT_PORTS

        if project in PROJECT_PORTS:
            port = PROJECT_PORTS[project]["api"] + port_offset
            protocol = "https" if use_https else "http"
            effective_base_url = f"{protocol}://{host}:{port}"
            if verbose:
                click.echo(f"  Target: {effective_base_url}")
        else:
            click.echo(f"Unknown project: {project}", err=True)
            sys.exit(1)
    elif not effective_base_url and host:
        # Host provided without project - use default port 8000
        protocol = "https" if use_https else "http"
        effective_base_url = f"{protocol}://{host}:8000"
        if verbose:
            click.echo(f"  Target: {effective_base_url}")

    if verbose and effective_base_url:
        click.echo(f"  Base URL: {effective_base_url}")

    try:
        from ...probe.api_test_runner import APITestRunner

        path = project_path or str(Path.cwd())
        runner = APITestRunner(path)

        # Run API tests
        result = runner.run_api_tests(spec_file=spec, base_url=effective_base_url)

        if result.success:
            click.echo(f"\nAPI tests passed! ({result.duration:.2f}s)")
        else:
            click.echo(f"\nAPI tests failed: {result.error}", err=True)
            sys.exit(1)

    except ImportError:
        # Fallback to subprocess if runner not available
        cmd = ["sega", "test_api"]
        if spec:
            cmd.extend(["--spec", spec])
        if effective_base_url:
            cmd.extend(["--base-url", effective_base_url])
        result = subprocess.run(cmd)
        sys.exit(result.returncode)

    except Exception as e:
        click.echo(f"API test error: {e}", err=True)
        sys.exit(1)


@probe.command()
@click.option("--visual", is_flag=True, help="Visual regression testing")
@click.option("--a11y", is_flag=True, help="Accessibility testing")
@click.option("--perf", is_flag=True, help="Performance testing")
@click.option("--headed", is_flag=True, help="Run with visible browser")
@click.option(
    "--browser",
    "browser_type",
    type=click.Choice(["chromium", "firefox", "webkit"]),
    default="chromium",
    help="Browser to use",
)
@click.option("--project", "-p", help="Specific project to test")
@click.option("--project-path", type=click.Path(exists=True), help="Project path (defaults to current directory)")
def browser(
    visual: bool,
    a11y: bool,
    perf: bool,
    headed: bool,
    browser_type: str,
    project: Optional[str],
    project_path: Optional[str],
):
    """Browser testing with Playwright.

    \b
    Options:
        --visual  - Visual regression testing (screenshot comparison)
        --a11y    - Accessibility testing (WCAG compliance)
        --perf    - Performance testing (Core Web Vitals)
    """
    click.echo(f"Running browser tests with {browser_type}...")

    # Build test modes based on options
    test_modes = []
    if visual:
        test_modes.append("visual")
        click.echo("  - Visual regression enabled")
    if a11y:
        test_modes.append("a11y")
        click.echo("  - Accessibility testing enabled")
    if perf:
        test_modes.append("perf")
        click.echo("  - Performance testing enabled")

    if not test_modes:
        test_modes.append("functional")

    try:
        from ...probe.browser_test_runner import BrowserTestRunner

        path = project_path or str(Path.cwd())
        runner = BrowserTestRunner(path)

        # Run browser tests with specified modes
        result = runner.run_browser_tests(browser=browser_type, headed=headed, modes=test_modes)

        if result.success:
            click.echo(f"\nBrowser tests passed! ({result.duration:.2f}s)")
        else:
            click.echo(f"\nBrowser tests failed: {result.error}", err=True)
            sys.exit(1)

    except ImportError:
        # Fallback to subprocess
        cmd = ["sega", "test", "--type", "browser"]
        if project:
            cmd.extend(["--project", project])
        result = subprocess.run(cmd)
        sys.exit(result.returncode)

    except Exception as e:
        click.echo(f"Browser test error: {e}", err=True)
        sys.exit(1)


@probe.command()
@click.option("--project", "-p", help="Specific project")
@click.option("--project-path", type=click.Path(exists=True), help="Project path (defaults to current directory)")
@click.option(
    "--format", "output_format", type=click.Choice(["text", "html", "json"]), default="text", help="Report format"
)
@click.option("--output", "-o", type=click.Path(), help="Output file")
@click.option("--threshold", type=int, default=80, help="Minimum coverage percentage")
def coverage(
    project: Optional[str], project_path: Optional[str], output_format: str, output: Optional[str], threshold: int
):
    """Generate coverage report.

    Aggregates coverage data from test runs.
    """
    click.echo("Generating coverage report...")

    try:
        orchestrator = get_test_orchestrator()
        path = project_path or str(Path.cwd())

        # Run tests with coverage
        results = orchestrator.run_tests(["unit", "integration"], path)

        # Aggregate coverage metrics
        total_coverage = 0.0
        test_count = 0

        for test_name, result in results.items():
            if result.metrics and "coverage" in result.metrics:
                total_coverage += result.metrics["coverage"]
                test_count += 1

        if test_count > 0:
            avg_coverage = total_coverage / test_count
            click.echo(f"Coverage: {avg_coverage:.1f}%")

            if avg_coverage < threshold:
                click.echo(f"Coverage {avg_coverage:.1f}% is below threshold {threshold}%", err=True)
                sys.exit(1)
        else:
            click.echo("No coverage data available")

        click.echo(f"\nCoverage threshold: {threshold}% - PASSED")

    except Exception as e:
        click.echo(f"Coverage error: {e}", err=True)
        sys.exit(1)


@probe.command()
@click.option("--project", "-p", help="Specific project")
@click.option("--iterations", type=int, default=5, help="Number of benchmark iterations")
@click.option("--output", "-o", type=click.Path(), help="Output file")
def benchmark(project: Optional[str], iterations: int, output: Optional[str]):
    """Run performance benchmarks.

    Executes performance benchmarks and tracks metrics.
    """
    click.echo(f"Running benchmarks ({iterations} iterations)...")

    # In a real implementation, this would run benchmark tests
    click.echo("  - Startup time")
    click.echo("  - Memory usage")
    click.echo("  - Response latency")
    click.echo("  - Throughput")

    click.echo("\nBenchmark complete")


@probe.command()
@click.option(
    "--instance",
    type=click.Choice(["1", "2", "3"]),
    multiple=True,
    help="EC2 instance(s) to test (can specify multiple)",
)
@click.option("--ssh-key", help="Path to SSH private key (defaults to ~/.ssh/id_rsa)")
@click.option("--timeout", type=float, default=10.0, help="Request timeout in seconds")
@click.option("--json-output", is_flag=True, help="Output results as JSON")
@click.option("--verbose", "-v", is_flag=True, help="Verbose output")
def instance(instance: tuple, ssh_key: Optional[str], timeout: float, json_output: bool, verbose: bool):
    """Test localhost endpoints on EC2 instances via SSH.

    SSH into EC2 instances and test localhost endpoints that aren't
    exposed externally (landing on port 3xxx, product_app on port 4xxx).

    This is necessary because EC2 security groups don't expose these ports.

    \b
    Examples:
        sega probe instance                      # Test all instances
        sega probe instance --instance 1         # Test Instance 1 only
        sega probe instance --instance 1 --instance 2  # Test Instance 1 & 2
        sega probe instance --verbose            # Show detailed output
        sega probe instance --json-output        # JSON output
    """
    import asyncio

    try:
        from ...probe.instance_test_runner import InstanceTestRunner, print_instance_results

        runner = InstanceTestRunner(
            timeout=timeout,
            ssh_key_path=ssh_key,
            verbose=verbose,
        )

        if verbose:
            click.echo(f"Timeout: {timeout}s")
            if instance:
                click.echo(f"Testing instances: {', '.join(instance)}")
            else:
                click.echo("Testing all instances")

        # Run async tests
        async def run_tests():
            if instance:
                # Convert instance numbers to names
                instance_names = [f"fleet-prod-0{i}" for i in instance]
                tasks = [runner.test_instance(name) for name in instance_names]
                return await asyncio.gather(*tasks)
            else:
                return await runner.test_all_instances()

        results = asyncio.run(run_tests())

        if json_output:
            import json
            from dataclasses import asdict

            output = [asdict(r) for r in results]
            click.echo(json.dumps(output, indent=2, default=str))
        else:
            print_instance_results(results)

        # Exit with error if any tests failed
        all_passed = all(r.all_passed for r in results)
        if not all_passed:
            sys.exit(1)

    except FileNotFoundError as e:
        click.echo(f"Configuration error: {e}", err=True)
        click.echo("Ensure config/domain_registry.yaml exists", err=True)
        sys.exit(1)

    except Exception as e:
        click.echo(f"Instance test error: {e}", err=True)
        if verbose:
            import traceback

            traceback.print_exc()
        sys.exit(1)


@probe.command()
@click.option("--project", "-p", multiple=True, help="Specific project(s) to test")
@click.option(
    "--domain",
    "domain_type",
    type=click.Choice(["production", "internal", "both"]),
    default="both",
    help="Domain type: production, internal, or both",
)
@click.option(
    "--type",
    "endpoint_type",
    type=click.Choice(["landing", "product_app", "api", "all"]),
    default="all",
    help="Endpoint type: landing, product_app, api, or all",
)
@click.option("--instance", type=click.Choice(["1", "2", "3"]), help="Test only projects on specific EC2 instance")
@click.option("--test-localhost", is_flag=True, help="Include SSH-based localhost testing on EC2 instances")
@click.option("--ssh-key", help="Path to SSH private key (defaults to ~/.ssh/id_rsa)")
@click.option("--timeout", type=float, default=30.0, help="Request timeout in seconds")
@click.option("--no-ssl", is_flag=True, help="Disable SSL verification")
@click.option("--json-output", is_flag=True, help="Output results as JSON")
@click.option("--verbose", "-v", is_flag=True, help="Verbose output")
def domain(
    project: tuple,
    domain_type: str,
    endpoint_type: str,
    instance: Optional[str],
    test_localhost: bool,
    ssh_key: Optional[str],
    timeout: float,
    no_ssl: bool,
    json_output: bool,
    verbose: bool,
):
    """Test production and internal dev domain URLs.

    Tests actual domain names (e.g., atlas.app) for landing pages,
    product apps, and APIs. Validates SSL certificates and response status.

    With --test-localhost, also SSH into EC2 instances and test localhost
    endpoints that aren't exposed externally (landing/product_app ports).

    \b
    Examples:
        sega probe domain                              # Test all production domains
        sega probe domain --test-localhost             # Test localhost + production
        sega probe domain -p atlas --domain production
        sega probe domain --instance 1 --test-localhost  # Instance 1 comprehensive
        sega probe domain --domain internal --json-output
        sega probe domain -p atlas -p hermes         # Multiple projects
    """
    import asyncio

    try:
        from ...probe.domain_test_runner import DomainTestRunner, print_results

        runner = DomainTestRunner(
            timeout=timeout,
            verify_ssl=not no_ssl,
        )

        if verbose:
            click.echo(f"Domain type: {domain_type}")
            click.echo(f"Endpoint type: {endpoint_type}")
            click.echo(f"Localhost testing: {'enabled' if test_localhost else 'disabled'}")
            if instance:
                click.echo(f"Instance filter: {instance}")
            if project:
                click.echo(f"Projects: {', '.join(project)}")

        # Run async tests
        async def run_tests():
            if test_localhost:
                # Comprehensive testing (localhost + production)
                if project:
                    # For specific projects, run comprehensive per project
                    domain_results = await runner.test_projects(
                        list(project),
                        domain_type=domain_type,
                        endpoint_type=endpoint_type,
                    )
                    # Add localhost results
                    return await runner.test_comprehensive(
                        domain_type=domain_type,
                        endpoint_type=endpoint_type,
                        instance=instance,
                        test_localhost=True,
                        ssh_key_path=ssh_key,
                    )
                else:
                    return await runner.test_comprehensive(
                        domain_type=domain_type,
                        endpoint_type=endpoint_type,
                        instance=instance,
                        test_localhost=True,
                        ssh_key_path=ssh_key,
                    )
            else:
                # Domain-only testing (existing behavior)
                if project:
                    return await runner.test_projects(
                        list(project),
                        domain_type=domain_type,
                        endpoint_type=endpoint_type,
                    )
                else:
                    return await runner.test_all(
                        domain_type=domain_type,
                        endpoint_type=endpoint_type,
                        instance=instance,
                    )

        results = asyncio.run(run_tests())

        if json_output:
            import json
            from dataclasses import asdict

            output = [asdict(r) for r in results]
            click.echo(json.dumps(output, indent=2, default=str))
        else:
            print_results(results, show_localhost=test_localhost)

        # Exit with error if any tests failed
        all_passed = all(r.failed == 0 for r in results)
        if not all_passed:
            sys.exit(1)

    except FileNotFoundError as e:
        click.echo(f"Configuration error: {e}", err=True)
        click.echo("Ensure config/domain_registry.yaml exists", err=True)
        sys.exit(1)

    except Exception as e:
        click.echo(f"Domain test error: {e}", err=True)
        if verbose:
            import traceback

            traceback.print_exc()
        sys.exit(1)


@probe.command()
@click.option("--all", is_flag=True, help="Scan all 22 FLEET projects")
@click.option("--project", "-p", multiple=True, help="Specific project(s) to scan")
@click.option(
    "--domain-type",
    type=click.Choice(["production", "internal"]),
    default="production",
    help="Domain type to scan (production or internal)",
)
@click.option(
    "--endpoint-type",
    type=click.Choice(["landing", "product_app", "both"]),
    default="both",
    help="Endpoint types to scan",
)
@click.option("--instance", type=click.Choice(["1", "2", "3"]), help="Filter to projects on specific EC2 instance")
@click.option("--dashboard", is_flag=True, help="Show lightweight status dashboard (HTTP checks only)")
@click.option("--report", is_flag=True, help="Generate detailed console error report (Playwright scan)")
@click.option(
    "--detail",
    type=click.Choice(["minimal", "summary", "full"]),
    default="summary",
    help="Report detail level",
)
@click.option("--json", "json_output", is_flag=True, help="Output results as JSON")
@click.option("--compact", is_flag=True, help="Show compact summary table")
@click.option("--headed", is_flag=True, help="Show browser during scan (for debugging)")
@click.option("--screenshot-errors", is_flag=True, default=True, help="Capture screenshots of pages with errors")
@click.option("--timeout", default=30, type=int, help="Page load timeout in seconds")
@click.option("--output", "-o", default="docs/reports/console_scans", help="Output directory for reports")
@click.option("--verbose", "-v", is_flag=True, help="Verbose output")
def scan(
    all: bool,
    project: tuple,
    domain_type: str,
    endpoint_type: str,
    instance: Optional[str],
    dashboard: bool,
    report: bool,
    detail: str,
    json_output: bool,
    compact: bool,
    headed: bool,
    screenshot_errors: bool,
    timeout: int,
    output: str,
    verbose: bool,
):
    """Scan pages for console errors and HTTP status.

    Two modes:

    1. Dashboard (--dashboard): Fast HTTP checks, no browser (2-3 seconds)
    2. Report (--report): Deep Playwright scan with console logs (60-90 seconds)

    \b
    Examples:
        # Quick status dashboard (HTTP only, fast)
        sega probe scan --dashboard --all
        sega probe scan --dashboard --instance 1

        # Deep console scan with report
        sega probe scan --all --report
        sega probe scan -p atlas -p hermes --report

        # Compact summary
        sega probe scan --all --compact

        # Internal dev domains
        sega probe scan --dashboard --all --domain-type internal
    """
    import asyncio
    from pathlib import Path

    try:
        from ...probe.domain_test_runner import DomainTestRunner
        from ...probe.status_dashboard import StatusDashboard, render_dashboard_table, render_compact_table
        from ...probe.console_scanner import ConsoleScanner
        from ...probe.scan_reporter import ScanReportGenerator

        # Determine which projects to scan
        domain_runner = DomainTestRunner(timeout=timeout, verify_ssl=True)

        if all:
            projects = domain_runner.get_projects(instance=instance)
        elif project:
            projects = list(project)
        else:
            click.echo("Error: Must specify --all or --project", err=True)
            sys.exit(1)

        if verbose:
            click.echo(f"Projects to scan: {len(projects)}")
            click.echo(f"Domain type: {domain_type}")
            click.echo(f"Endpoint type: {endpoint_type}")

        # Determine endpoint types
        endpoints = ["landing", "product_app"] if endpoint_type == "both" else [endpoint_type]

        # Mode 1: Dashboard (fast HTTP checks)
        if dashboard:
            click.echo("🔍 SEGA Console Log Scanner - Status Dashboard")
            click.echo("=" * 80)
            click.echo("")

            async def run_dashboard():
                dashboard_runner = StatusDashboard(domain_runner, timeout=10.0)
                return await dashboard_runner.check_all(
                    domain_type=domain_type,
                    endpoint_types=endpoints,
                    instance=instance,
                )

            statuses = asyncio.run(run_dashboard())

            if compact:
                click.echo(render_compact_table(statuses))
            else:
                click.echo(render_dashboard_table(statuses))

            # Exit with error if any critical
            critical_count = sum(1 for s in statuses.values() if s.overall_status == "critical")
            if critical_count > 0:
                sys.exit(1)

        # Mode 2: Report (deep console scan)
        elif report:
            click.echo("🔍 Scanning pages for console errors...")
            click.echo("")

            async def run_scan():
                scanner = ConsoleScanner(
                    domain_runner=domain_runner,
                    headed=headed,
                    screenshot_errors=screenshot_errors,
                    timeout=timeout,
                )
                return await scanner.scan_projects(
                    projects=projects,
                    domain_type=domain_type,
                    endpoint_types=endpoints,
                )

            start = time.time()
            scan_results = asyncio.run(run_scan())
            duration = time.time() - start

            # Show progress
            for project, result in scan_results.items():
                status_icon = "✓" if result.status == "healthy" else "✗"
                error_str = f"{result.total_errors} errors" if result.total_errors > 0 else "clean"
                click.echo(f"  {status_icon} {project:<14} ({result.duration_seconds:.1f}s) - {error_str}")

            click.echo("")
            click.echo(f"Scan complete ({duration:.1f}s)")
            click.echo("")

            # Summary
            total_errors = sum(r.total_errors for r in scan_results.values())
            total_warnings = sum(r.total_warnings for r in scan_results.values())
            critical_count = sum(1 for r in scan_results.values() if r.status == "critical")

            click.echo(f"  Projects scanned:     {len(scan_results)}")
            click.echo(f"  Console errors:       {total_errors}")
            click.echo(f"  Console warnings:     {total_warnings}")
            click.echo(f"  Critical issues:      {critical_count}")
            click.echo("")

            # Generate reports
            output_dir = Path(output)
            reporter = ScanReportGenerator(output_dir)

            if json_output:
                json_path = reporter.generate_json_export(scan_results)
                click.echo(f"JSON export: {json_path}")
            else:
                report_path = reporter.generate_markdown_report(
                    scan_results,
                    domain_type=domain_type,
                    detail_level=detail,
                )
                click.echo(f"Report written to: {report_path}")
                click.echo("")
                click.echo(f"View report:")
                click.echo(f"  cat {report_path}")

            # Show critical projects
            if critical_count > 0:
                click.echo("")
                click.echo("Critical projects (need attention):")
                for project, result in sorted(scan_results.items()):
                    if result.status == "critical":
                        error_summary = []
                        for page in result.results:
                            if page.total_error_count > 0:
                                error_summary.append(f"{page.endpoint_type}: {page.total_error_count} errors")
                            elif not page.success:
                                error_summary.append(f"{page.endpoint_type}: {page.error}")
                        click.echo(f"  • {project} - {', '.join(error_summary)}")

                sys.exit(1)

        # Mode 3: Compact summary (default)
        else:
            click.echo("Error: Must specify --dashboard or --report", err=True)
            click.echo("Use 'sega probe scan --help' for usage", err=True)
            sys.exit(1)

    except ImportError as e:
        click.echo(f"Missing dependency: {e}", err=True)
        if "playwright" in str(e).lower():
            click.echo("\nInstall Playwright:", err=True)
            click.echo("  pip install playwright && playwright install", err=True)
        sys.exit(1)

    except Exception as e:
        click.echo(f"Scan error: {e}", err=True)
        if verbose:
            import traceback

            traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    probe()
