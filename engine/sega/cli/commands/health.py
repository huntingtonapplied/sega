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
SEGA HEALTH COMMAND - Service Health Checking
==============================================================================
File: src/sega/commands/health.py
Project: SEGA (Scalable Engineering & Growth Automation)
Copyright: 2022-2025 FLEET
License: Apache-2.0

SEGA MODULE: Commands/Health
COMPONENT: Health check CLI command
PURPOSE: Check health endpoints for deployed services
DEPENDENCIES: click, requests
==============================================================================
"""

import click
import sys
import time
from typing import Optional, Dict, Any, List
from pathlib import Path

try:
    import requests
    REQUESTS_AVAILABLE = True
except ImportError:
    REQUESTS_AVAILABLE = False

from ...core.config import get_config


# Project port mapping (api + frontend), fully derived from central config:
# --all-services iterates every configured project, with the standard port
# formulas (api = 8000 + id, frontend = 3000 + id).
# AUTHORITATIVE: /docs/standards/infrastructure/PORT_ALLOCATION_STANDARDS.md
def _build_project_ports() -> Dict[str, Dict[str, int]]:
    """Build {project: {"api": ..., "frontend": ...}} from central config."""
    cfg = get_config()
    return {
        proj.name: {"api": proj.ports.api, "frontend": proj.ports.frontend}
        for proj in cfg.projects.values()
    }


PROJECT_PORTS = _build_project_ports()


@click.command()
@click.option("--project", "-p", help="FLEET project name (uses standard ports)")
@click.option("--url", "-u", help="Direct URL to health endpoint")
@click.option("--host", "-H", help="Custom host/IP address (e.g., 192.168.1.100, api.example.com)")
@click.option("--environment", "-e", default="local",
              type=click.Choice(["local", "staging", "production"]),
              help="Deployment environment")
@click.option("--port", type=int, help="Override port number")
@click.option("--port-offset", type=int, default=0,
              help="Port offset (added to standard port)")
@click.option("--https", "use_https", is_flag=True,
              help="Use HTTPS instead of HTTP")
@click.option("--timeout", "-t", default=30, type=int,
              help="Timeout in seconds (default: 30)")
@click.option("--interval", "-i", default=5, type=int,
              help="Check interval in seconds (default: 5)")
@click.option("--wait", "-w", is_flag=True,
              help="Wait for service to become healthy")
@click.option("--all-services", is_flag=True,
              help="Check all FLEET project services")
@click.option("--json-output", is_flag=True,
              help="Output results as JSON")
@click.option("--verbose", "-v", is_flag=True,
              help="Show detailed output")
def health(project: Optional[str], url: Optional[str], host: Optional[str],
           environment: str, port: Optional[int], port_offset: int, use_https: bool,
           timeout: int, interval: int, wait: bool,
           all_services: bool, json_output: bool, verbose: bool):
    """Check health endpoints for deployed services.

    Verifies that services are running and responding to health checks.
    Uses FLEET port allocation standards for automatic URL construction.

    \b
    Examples:
        sega health --project atlas                    # Check atlas on localhost
        sega health --project atlas --environment staging
        sega health --project atlas --host 203.0.113.10  # Check on remote IP
        sega health --project atlas --host api.example.com --https  # Check with HTTPS
        sega health --project atlas --port-offset 100  # Check with port offset
        sega health --url http://localhost:8003/health
        sega health --project atlas --wait --timeout 60
        sega health --all-services                   # Check all FLEET projects
        sega health --all-services --host 203.0.113.10  # Check all on remote
    """
    if not REQUESTS_AVAILABLE:
        click.echo("Error: 'requests' library required. Install with: pip install requests", err=True)
        sys.exit(1)

    results = []

    if all_services:
        # Check all FLEET projects
        for proj_name in PROJECT_PORTS.keys():
            result = _check_project_health(
                proj_name, environment, None, timeout, verbose,
                host=host, port_offset=port_offset, use_https=use_https
            )
            results.append(result)
    elif project:
        # Check specific project
        result = _check_project_health(
            project, environment, port, timeout, verbose, wait, interval,
            host=host, port_offset=port_offset, use_https=use_https
        )
        results.append(result)
    elif url:
        # Check direct URL
        result = _check_url_health(url, timeout, verbose, wait, interval)
        results.append(result)
    else:
        # Try to detect project from current directory
        detected_project = _detect_current_project()
        if detected_project:
            click.echo(f"Detected project: {detected_project}")
            result = _check_project_health(
                detected_project, environment, port, timeout, verbose, wait, interval,
                host=host, port_offset=port_offset, use_https=use_https
            )
            results.append(result)
        else:
            click.echo("Error: Specify --project, --url, or --all-services", err=True)
            sys.exit(1)

    # Output results
    if json_output:
        import json
        click.echo(json.dumps(results, indent=2))
    else:
        _print_health_results(results)

    # Exit with appropriate code
    all_healthy = all(r.get("healthy", False) for r in results)
    if not all_healthy:
        sys.exit(1)


def _check_project_health(project: str, environment: str, port: Optional[int],
                          timeout: int, verbose: bool, wait: bool = False,
                          interval: int = 5, host: Optional[str] = None,
                          port_offset: int = 0, use_https: bool = False) -> Dict[str, Any]:
    """Check health of an FLEET project.

    Args:
        project: FLEET project name
        environment: Deployment environment (local, staging, production)
        port: Override port number
        timeout: Request timeout in seconds
        verbose: Enable verbose output
        wait: Wait for service to become healthy
        interval: Check interval when waiting
        host: Custom host/IP address (overrides environment-based host)
        port_offset: Offset to add to standard port
        use_https: Use HTTPS instead of HTTP
    """
    result = {
        "project": project,
        "environment": environment,
        "healthy": False,
        "endpoints": []
    }

    if project not in PROJECT_PORTS:
        result["error"] = f"Unknown project: {project}"
        return result

    ports = PROJECT_PORTS[project]
    api_port = port or (ports["api"] + port_offset)

    # Construct host based on environment or custom host
    if host:
        # Custom host provided - use it directly
        target_host = host
        result["host"] = host
    elif environment == "local":
        target_host = "localhost"
    elif environment == "staging":
        domain = get_config().get_domain(project, "dev")
        if not domain:
            result["error"] = f"No staging domain configured for {project} (add it to [domains] in sega.toml)"
            return result
        target_host = domain
    elif environment == "production":
        domain = get_config().get_domain(project, "prod")
        if not domain:
            result["error"] = f"No production domain configured for {project} (add it to [domains] in sega.toml)"
            return result
        target_host = domain
    else:
        target_host = "localhost"

    # Determine protocol
    protocol = "https" if use_https else "http"

    # For HTTPS on standard domains, typically port is omitted (443)
    if use_https and host and not port and port_offset == 0:
        api_url = f"{protocol}://{target_host}/health"
    else:
        api_url = f"{protocol}://{target_host}:{api_port}/health"

    if verbose:
        click.echo(f"  Checking: {api_url}")

    api_result = _check_url_health(api_url, timeout, verbose, wait, interval)
    result["endpoints"].append({
        "type": "api",
        "url": api_url,
        **api_result
    })

    # Overall health
    result["healthy"] = api_result.get("healthy", False)

    return result


def _check_url_health(url: str, timeout: int, verbose: bool,
                      wait: bool = False, interval: int = 5) -> Dict[str, Any]:
    """Check health of a specific URL."""
    result = {
        "url": url,
        "healthy": False,
        "response_time_ms": None,
        "status_code": None,
        "error": None
    }

    if wait:
        # Wait mode - keep checking until healthy or timeout
        start_time = time.time()
        attempts = 0

        while time.time() - start_time < timeout:
            attempts += 1
            check_result = _single_health_check(url, min(timeout, 10), verbose)

            if check_result["healthy"]:
                result.update(check_result)
                result["attempts"] = attempts
                result["wait_time_s"] = round(time.time() - start_time, 2)
                return result

            if verbose:
                click.echo(f"  Attempt {attempts}: {check_result.get('error', 'unhealthy')} - retrying in {interval}s")

            time.sleep(interval)

        result["error"] = f"Timeout after {timeout}s ({attempts} attempts)"
        result["attempts"] = attempts
    else:
        # Single check
        result.update(_single_health_check(url, timeout, verbose))

    return result


def _single_health_check(url: str, timeout: int, verbose: bool) -> Dict[str, Any]:
    """Perform a single health check."""
    result = {
        "healthy": False,
        "response_time_ms": None,
        "status_code": None,
        "error": None
    }

    try:
        start = time.time()
        response = requests.get(url, timeout=timeout)
        elapsed_ms = round((time.time() - start) * 1000, 2)

        result["status_code"] = response.status_code
        result["response_time_ms"] = elapsed_ms

        if response.status_code == 200:
            result["healthy"] = True

            # Try to parse response body for additional info
            try:
                body = response.json()
                if verbose:
                    result["response_body"] = body
                # Check for common health response patterns
                if isinstance(body, dict):
                    if body.get("status") in ["healthy", "ok", "UP"]:
                        result["healthy"] = True
                    elif body.get("status") in ["unhealthy", "error", "DOWN"]:
                        result["healthy"] = False
                        result["error"] = body.get("message", "Service unhealthy")
            except (ValueError, KeyError):
                # Response is not JSON or doesn't have expected fields
                pass
        else:
            result["error"] = f"HTTP {response.status_code}"

    except requests.ConnectionError:
        result["error"] = "Connection refused"
    except requests.Timeout:
        result["error"] = f"Timeout after {timeout}s"
    except requests.RequestException as e:
        result["error"] = str(e)

    return result


def _detect_current_project() -> Optional[str]:
    """Try to detect current project from directory."""
    cwd = Path.cwd()

    # Check if we're in an FLEET project directory
    for parent in [cwd] + list(cwd.parents):
        if parent.name in PROJECT_PORTS:
            return parent.name

        # Check for .sega directory or laboratory_config.yaml
        sega_config = parent / ".sega" / "laboratory_config.yaml"
        if sega_config.exists():
            try:
                import yaml
                with open(sega_config) as f:
                    config = yaml.safe_load(f)
                    if config and "project" in config:
                        return config["project"].get("name")
            except Exception:
                pass

    return None


def _print_health_results(results: List[Dict[str, Any]]):
    """Print health check results."""
    click.echo("SEGA Health Check Report")
    click.echo("=" * 60)

    healthy_count = 0
    unhealthy_count = 0

    for result in results:
        project = result.get("project", result.get("url", "unknown"))
        is_healthy = result.get("healthy", False)

        if is_healthy:
            status = "[OK]"
            healthy_count += 1
        else:
            status = "[FAIL]"
            unhealthy_count += 1

        click.echo(f"\n{status} {project}")

        if "environment" in result:
            click.echo(f"    Environment: {result['environment']}")

        if "error" in result and result["error"]:
            click.echo(f"    Error: {result['error']}")

        # Print endpoint details
        for endpoint in result.get("endpoints", []):
            endpoint_status = "[OK]" if endpoint.get("healthy") else "[FAIL]"
            click.echo(f"    {endpoint_status} {endpoint.get('type', 'unknown')}: {endpoint.get('url')}")

            if endpoint.get("response_time_ms"):
                click.echo(f"        Response time: {endpoint['response_time_ms']}ms")
            if endpoint.get("status_code"):
                click.echo(f"        Status code: {endpoint['status_code']}")
            if endpoint.get("error"):
                click.echo(f"        Error: {endpoint['error']}")
            if endpoint.get("attempts"):
                click.echo(f"        Attempts: {endpoint['attempts']}")
            if endpoint.get("wait_time_s"):
                click.echo(f"        Wait time: {endpoint['wait_time_s']}s")

        # Single URL check (not project-based)
        if "url" in result and "endpoints" not in result:
            if result.get("response_time_ms"):
                click.echo(f"    Response time: {result['response_time_ms']}ms")
            if result.get("status_code"):
                click.echo(f"    Status code: {result['status_code']}")
            if result.get("attempts"):
                click.echo(f"    Attempts: {result['attempts']}")

    click.echo("\n" + "=" * 60)
    click.echo(f"Summary: {healthy_count} healthy, {unhealthy_count} unhealthy")
