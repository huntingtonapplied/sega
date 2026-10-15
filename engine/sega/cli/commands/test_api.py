#!/usr/bin/env python3
"""
SEGA API Test Command
=====================
Test API endpoints of running containers.

Usage:
    sega test-api                     # Test all projects
    sega test-api orion atlas   # Test specific projects
    sega test-api --health-only       # Quick health checks
    sega test-api --host 203.0.113.10 # Test remote host
    sega test-api --discover          # Auto-discover from OpenAPI
    sega test-api --discover --chain  # Discover and run intelligent chains
    sega test-api --auth mock         # Use mock JWT authentication
    sega test-api --auth real         # Use real token from environment
"""

import asyncio
import os
import click
from pathlib import Path
from typing import List, Optional

from ...probe.api_test_runner import ApiTestRunner, print_results, PROJECT_PORTS
from ...probe.openapi import OpenAPIDiscoverer
from ...probe.chaining import (
    TestChainBuilder,
    ChainedTestRunner,
    print_chains,
    print_chain_results,
)
from ...probe.auth import AuthMode, TestAuthManager


@click.command("test-api")
@click.argument("projects", nargs=-1)
@click.option("--host", default="localhost", help="Host running containers")
@click.option("--timeout", default=10.0, type=float, help="Request timeout in seconds")
@click.option("--health-only", is_flag=True, help="Only run health checks")
@click.option("--config", type=click.Path(exists=True), help="Custom config file")
@click.option("--json", "output_json", is_flag=True, help="Output as JSON")
@click.option("--discover", is_flag=True, help="Auto-discover endpoints from OpenAPI schemas")
@click.option("--chain", is_flag=True, help="Run intelligent test chains (requires --discover)")
@click.option("--parallel", is_flag=True, help="Run chains in parallel (with --chain)")
@click.option(
    "--auth",
    type=click.Choice(["none", "mock", "real"]),
    default="mock",
    help="Authentication mode: none (no auth), mock (test JWT), real (from SEGA_TEST_AUTH_TOKEN env)"
)
@click.option("--show-auth", is_flag=True, help="Show authentication info before running tests")
def test_api(
    projects: tuple,
    host: str,
    timeout: float,
    health_only: bool,
    config: Optional[str],
    output_json: bool,
    discover: bool,
    chain: bool,
    parallel: bool,
    auth: str,
    show_auth: bool,
):
    """
    Test API endpoints of running containers.

    Calls endpoints defined in config/api_test_config.yaml against
    running Docker containers. Useful for E2E API validation.

    Examples:

        # Test all projects on localhost
        sega test-api

        # Test specific projects
        sega test-api orion atlas hermes

        # Quick health check all projects
        sega test-api --health-only

        # Test against EC2 instance
        sega test-api --host 203.0.113.10

        # Test with custom timeout
        sega test-api atlas --timeout 30

        # Auto-discover endpoints from running backends
        sega test-api --discover atlas orion

        # Discover and run intelligent test chains
        sega test-api --discover --chain atlas

        # Run chains in parallel
        sega test-api --discover --chain --parallel atlas orion

        # Authentication modes
        sega test-api --auth none atlas          # No auth (public endpoints)
        sega test-api --auth mock --chain atlas  # Mock JWT (test mode)
        sega test-api --auth real --chain atlas  # Real token from env

        # Show auth info before testing
        sega test-api --show-auth --auth mock atlas
    """
    if chain and not discover:
        raise click.UsageError("--chain requires --discover flag")

    # Parse auth mode
    auth_mode = AuthMode(auth)

    asyncio.run(_run_tests(
        list(projects) if projects else None,
        host,
        timeout,
        health_only,
        config,
        output_json,
        discover,
        chain,
        parallel,
        auth_mode,
        show_auth,
    ))


async def _run_tests(
    projects: Optional[List[str]],
    host: str,
    timeout: float,
    health_only: bool,
    config: Optional[str],
    output_json: bool,
    discover: bool = False,
    chain: bool = False,
    parallel: bool = False,
    auth_mode: AuthMode = AuthMode.MOCK_JWT,
    show_auth: bool = False,
):
    """Run API tests asynchronously."""
    # Initialize auth manager
    auth_manager = TestAuthManager(mode=auth_mode)

    # Show auth info if requested
    if show_auth:
        _print_auth_info(auth_manager)

    # OpenAPI discovery mode
    if discover:
        await _run_discovery_tests(
            projects, host, timeout, output_json, chain, parallel, auth_manager
        )
        return

    # Get auth headers for static config tests
    auth_headers = auth_manager.get_auth_headers() if auth_mode != AuthMode.NONE else None

    runner = ApiTestRunner(timeout=timeout, config_path=config)

    if health_only:
        click.echo(f"\nRunning health checks against {host}...")
        results = await runner.health_check_all(host)

        if output_json:
            import json
            click.echo(json.dumps(results, indent=2))
        else:
            click.echo("\n" + "=" * 40)
            click.echo("HEALTH CHECK RESULTS")
            click.echo("=" * 40)

            up_count = sum(1 for v in results.values() if v)
            down_count = len(results) - up_count

            for project, healthy in sorted(results.items()):
                status = click.style("UP", fg="green") if healthy else click.style("DOWN", fg="red")
                click.echo(f"  {project:20} {status}")

            click.echo("=" * 40)
            click.echo(f"Summary: {up_count} up, {down_count} down")

    else:
        target_projects = projects or list(PROJECT_PORTS.keys())
        click.echo(f"\nRunning API tests against {host}...")
        click.echo(f"Projects: {', '.join(target_projects)}")

        results = await runner.run_projects(target_projects, host, headers=auth_headers)

        if output_json:
            import json
            output = []
            for r in results:
                output.append({
                    "project": r.project,
                    "base_url": r.base_url,
                    "total_calls": r.total_calls,
                    "successful": r.successful,
                    "failed": r.failed,
                    "duration_seconds": r.duration_seconds,
                    "calls": [
                        {
                            "endpoint": c.endpoint,
                            "method": c.method,
                            "status_code": c.status_code,
                            "success": c.success,
                            "duration_ms": c.duration_ms,
                            "error": c.error,
                        }
                        for c in r.calls
                    ],
                })
            click.echo(json.dumps(output, indent=2))
        else:
            print_results(results)

            # Summary
            total_passed = sum(r.failed == 0 for r in results)
            click.echo(f"\nProjects passing: {total_passed}/{len(results)}")


def _print_auth_info(auth_manager: TestAuthManager) -> None:
    """Print authentication configuration info."""
    info = auth_manager.get_user_info()
    click.echo("\n" + "=" * 50)
    click.echo("AUTHENTICATION CONFIGURATION")
    click.echo("=" * 50)
    click.echo(f"  Mode: {info.get('mode', 'unknown')}")

    if info.get('mode') == 'mock':
        click.echo(f"  Auth0 ID: {info.get('auth0_id')}")
        click.echo(f"  Email: {info.get('email')}")
        click.echo(f"  Name: {info.get('name')}")
        click.echo(f"  Admin: {info.get('is_admin')}")
        click.echo("\n  Note: Backends must run with SEGA_TEST_MODE=true to accept mock tokens")
    elif info.get('mode') == 'real':
        token_set = info.get('token_set', False)
        status = click.style("SET", fg="green") if token_set else click.style("NOT SET", fg="red")
        click.echo(f"  Token source: {info.get('source')}")
        click.echo(f"  Token status: {status}")
    elif info.get('mode') == 'none':
        click.echo("  No authentication will be used")

    click.echo("=" * 50 + "\n")


async def _run_discovery_tests(
    projects: Optional[List[str]],
    host: str,
    timeout: float,
    output_json: bool,
    chain: bool,
    parallel: bool,
    auth_manager: TestAuthManager,
):
    """Run OpenAPI discovery-based tests."""
    discoverer = OpenAPIDiscoverer(timeout=timeout)
    target_projects = projects or list(PROJECT_PORTS.keys())

    click.echo(f"\nDiscovering APIs from {host}...")
    click.echo(f"Projects: {', '.join(target_projects)}")
    click.echo(f"Auth mode: {auth_manager.config.mode.value}\n")

    # Get auth token from auth manager
    auth_token = auth_manager.get_token() if auth_manager.config.mode != AuthMode.NONE else None

    all_results = []
    discovery_results = []

    for project in target_projects:
        click.echo(f"Discovering {project}...")

        api = await discoverer.discover_project(project, host)

        if not api:
            click.echo(click.style(f"  Could not discover API for {project}", fg="yellow"))
            continue

        discovery_results.append({
            "project": project,
            "api": api,
        })

        click.echo(f"  Found {len(api.endpoints)} endpoints across {len(api.resources)} resources")

        if not chain:
            # Print discovered endpoints
            if not output_json:
                for ep in api.endpoints[:10]:
                    click.echo(f"    {ep.method.value:6} {ep.path}")
                if len(api.endpoints) > 10:
                    click.echo(f"    ... and {len(api.endpoints) - 10} more")

    if chain and discovery_results:
        click.echo("\n" + "=" * 70)
        click.echo("RUNNING TEST CHAINS")
        click.echo("=" * 70)

        chain_runner = ChainedTestRunner(timeout=timeout, auth_token=auth_token)

        for disc in discovery_results:
            project = disc["project"]
            api = disc["api"]

            click.echo(f"\nBuilding chains for {project}...")

            # Build chains from discovered API
            builder = TestChainBuilder(api)
            chains = builder.build_all_chains()

            if not chains:
                click.echo(f"  No testable chains found for {project}")
                continue

            click.echo(f"  Built {len(chains)} test chains")

            if not output_json:
                print_chains(chains)

            # Execute chains
            base_url = api.base_url
            results = await chain_runner.run_chains(chains, base_url, parallel=parallel)
            all_results.extend(results)

            if not output_json:
                print_chain_results(results)

    # JSON output
    if output_json:
        import json

        if chain:
            output = []
            for result in all_results:
                output.append({
                    "chain_name": result.chain_name,
                    "resource": result.resource,
                    "success": result.success,
                    "steps_executed": result.steps_executed,
                    "steps_passed": result.steps_passed,
                    "steps_failed": result.steps_failed,
                    "duration_seconds": result.duration_seconds,
                    "timestamp": result.timestamp,
                    "step_results": [
                        {
                            "step_name": s.step_name,
                            "endpoint": s.endpoint,
                            "method": s.method,
                            "status_code": s.status_code,
                            "success": s.success,
                            "duration_ms": s.duration_ms,
                            "extracted_values": s.extracted_values,
                            "error": s.error,
                        }
                        for s in result.step_results
                    ],
                })
            click.echo(json.dumps(output, indent=2))
        else:
            output = []
            for disc in discovery_results:
                api = disc["api"]
                output.append({
                    "project": disc["project"],
                    "base_url": api.base_url,
                    "title": api.title,
                    "version": api.version,
                    "endpoint_count": len(api.endpoints),
                    "resources": api.resources,
                    "endpoints": [
                        {
                            "path": ep.path,
                            "method": ep.method.value,
                            "operation_id": ep.operation_id,
                            "tags": ep.tags,
                            "requires_auth": ep.requires_auth,
                        }
                        for ep in api.endpoints
                    ],
                })
            click.echo(json.dumps(output, indent=2))

    # Summary
    if chain and all_results and not output_json:
        total_chains = len(all_results)
        passed_chains = sum(1 for r in all_results if r.success)
        total_steps = sum(r.steps_executed for r in all_results)
        passed_steps = sum(r.steps_passed for r in all_results)

        click.echo("\n" + "=" * 70)
        click.echo("OVERALL SUMMARY")
        click.echo("=" * 70)
        click.echo(f"Projects tested: {len(discovery_results)}")
        click.echo(f"Chains executed: {passed_chains}/{total_chains} passed")
        click.echo(f"Steps executed: {passed_steps}/{total_steps} passed")

        if passed_chains == total_chains:
            click.echo(click.style("\nALL TESTS PASSED", fg="green", bold=True))
        else:
            click.echo(click.style(f"\n{total_chains - passed_chains} CHAINS FAILED", fg="red", bold=True))


# For direct testing
if __name__ == "__main__":
    test_api()
