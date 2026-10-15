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
SEGA VALIDATE COMMAND - Dockerfile & Deployment Validation
==============================================================================
File: src/sega/commands/validate.py
Project: SEGA (Scalable Engineering & Growth Automation)
Copyright: 2022-2025 FLEET
License: Apache-2.0

SEGA MODULE: Commands/Validate
COMPONENT: Pre-deployment validation CLI command
PURPOSE: Validate Dockerfiles, deployment configurations, and SEGA compatibility
DEPENDENCIES: click, pathlib, re
==============================================================================
"""

import click
import re
import sys
from pathlib import Path
from typing import Optional, Dict, Any, List


@click.command()
@click.option("--dockerfile", "-d", type=click.Path(exists=True),
              help="Path to Dockerfile to validate")
@click.option("--project-type", "-t",
              type=click.Choice(["web_app", "api", "engine", "worker", "mobile", "desktop"]),
              help="Expected project type for validation rules")
@click.option("--compose", "-c", type=click.Path(exists=True),
              help="Path to docker-compose.yml to validate")
@click.option("--config", type=click.Path(exists=True),
              help="Path to SEGA config file (.sega.yml)")
@click.option("--strict", is_flag=True,
              help="Fail on warnings (not just errors)")
@click.option("--json-output", is_flag=True,
              help="Output results as JSON")
def validate(dockerfile: Optional[str], project_type: Optional[str],
             compose: Optional[str], config: Optional[str],
             strict: bool, json_output: bool):
    """Validate Dockerfile and deployment configurations for SEGA compatibility.

    Checks for:
    - Required health check endpoints
    - Non-root user configuration
    - Port standards compliance
    - Environment variable compatibility
    - Security best practices

    \b
    Examples:
        sega validate --dockerfile Dockerfile
        sega validate --dockerfile Dockerfile --project-type web_app
        sega validate --compose docker-compose.yml
        sega validate --dockerfile Dockerfile --strict
    """
    results = {
        "errors": [],
        "warnings": [],
        "info": [],
        "passed": True
    }

    # Auto-detect Dockerfile if not specified
    if not dockerfile and not compose and not config:
        if Path("Dockerfile").exists():
            dockerfile = "Dockerfile"
        elif Path("docker-compose.yml").exists():
            compose = "docker-compose.yml"
        else:
            click.echo("Error: No Dockerfile or docker-compose.yml found", err=True)
            click.echo("Use --dockerfile or --compose to specify the file")
            sys.exit(1)

    # Validate Dockerfile
    if dockerfile:
        dockerfile_results = _validate_dockerfile(dockerfile, project_type)
        results["errors"].extend(dockerfile_results["errors"])
        results["warnings"].extend(dockerfile_results["warnings"])
        results["info"].extend(dockerfile_results["info"])

    # Validate docker-compose.yml
    if compose:
        compose_results = _validate_compose(compose)
        results["errors"].extend(compose_results["errors"])
        results["warnings"].extend(compose_results["warnings"])
        results["info"].extend(compose_results["info"])

    # Validate SEGA config
    if config:
        config_results = _validate_sega_config(config)
        results["errors"].extend(config_results["errors"])
        results["warnings"].extend(config_results["warnings"])
        results["info"].extend(config_results["info"])

    # Determine pass/fail
    results["passed"] = len(results["errors"]) == 0
    if strict:
        results["passed"] = results["passed"] and len(results["warnings"]) == 0

    # Output results
    if json_output:
        import json
        click.echo(json.dumps(results, indent=2))
    else:
        _print_results(results, dockerfile, compose, config)

    # Exit with appropriate code
    if not results["passed"]:
        sys.exit(1)


def _validate_dockerfile(dockerfile_path: str, project_type: Optional[str]) -> Dict[str, List[str]]:
    """Validate Dockerfile for SEGA compatibility."""
    results = {"errors": [], "warnings": [], "info": []}

    content = Path(dockerfile_path).read_text()
    lines = content.split("\n")

    # Track what we find
    has_healthcheck = False
    has_user = False
    has_expose = False
    exposed_ports = []
    base_image = None
    has_nonroot_user = False

    for i, line in enumerate(lines, 1):
        line_stripped = line.strip()

        # Check base image
        if line_stripped.startswith("FROM "):
            base_image = line_stripped.split()[1] if len(line_stripped.split()) > 1 else None
            if base_image and ":latest" in base_image:
                results["warnings"].append(
                    f"Line {i}: Using ':latest' tag is not recommended for reproducibility"
                )

        # Check HEALTHCHECK instruction
        if line_stripped.startswith("HEALTHCHECK "):
            has_healthcheck = True
            if "CMD" not in line_stripped and "NONE" not in line_stripped:
                # Multi-line HEALTHCHECK
                pass
            results["info"].append(f"Line {i}: HEALTHCHECK instruction found")

        # Check USER instruction
        if line_stripped.startswith("USER "):
            has_user = True
            user = line_stripped.split()[1] if len(line_stripped.split()) > 1 else ""
            if user and user != "root" and user != "0":
                has_nonroot_user = True
                results["info"].append(f"Line {i}: Non-root USER '{user}' configured")
            elif user in ["root", "0"]:
                results["warnings"].append(
                    f"Line {i}: Running as root user - consider using non-root (UID 10001-19999)"
                )

        # Check EXPOSE instruction
        if line_stripped.startswith("EXPOSE "):
            has_expose = True
            ports = line_stripped.replace("EXPOSE ", "").split()
            exposed_ports.extend(ports)

        # Check for hardcoded secrets (basic check)
        secret_patterns = [
            r'PASSWORD\s*=\s*["\'][^"\']+["\']',
            r'SECRET\s*=\s*["\'][^"\']+["\']',
            r'API_KEY\s*=\s*["\'][^"\']+["\']',
            r'TOKEN\s*=\s*["\'][^"\']+["\']',
        ]
        for pattern in secret_patterns:
            if re.search(pattern, line_stripped, re.IGNORECASE):
                results["errors"].append(
                    f"Line {i}: Potential hardcoded secret detected - use environment variables"
                )

        # Check for ADD with remote URLs (security concern)
        if line_stripped.startswith("ADD ") and ("http://" in line_stripped or "https://" in line_stripped):
            results["warnings"].append(
                f"Line {i}: ADD with remote URL - consider using COPY with explicit download step"
            )

    # SEGA requirement checks
    if not has_healthcheck:
        results["warnings"].append(
            "No HEALTHCHECK instruction found - SEGA requires /health endpoint for deployments"
        )

    if not has_user:
        results["warnings"].append(
            "No USER instruction found - containers should run as non-root (UID 10001-19999)"
        )
    elif not has_nonroot_user:
        results["errors"].append(
            "Container configured to run as root - SEGA requires non-root user"
        )

    # Port validation for FLEET standards
    if exposed_ports:
        for port in exposed_ports:
            port_num = int(port.split("/")[0]) if "/" in port else int(port)
            if port_num < 3000 or port_num > 9999:
                results["warnings"].append(
                    f"Port {port_num} outside FLEET standard range (3000-9999)"
                )

    # Project type specific checks
    if project_type == "web_app":
        if not any(p.startswith("3") for p in [str(p).split("/")[0] for p in exposed_ports]):
            results["warnings"].append(
                "web_app should expose frontend port in 30xx range"
            )

    results["info"].append(f"Base image: {base_image or 'unknown'}")
    results["info"].append(f"Exposed ports: {', '.join(exposed_ports) or 'none'}")

    return results


def _validate_compose(compose_path: str) -> Dict[str, List[str]]:
    """Validate docker-compose.yml for SEGA compatibility."""
    results = {"errors": [], "warnings": [], "info": []}

    try:
        import yaml
    except ImportError:
        results["warnings"].append("PyYAML not installed - skipping compose validation")
        return results

    content = Path(compose_path).read_text()

    try:
        compose_data = yaml.safe_load(content)
    except yaml.YAMLError as e:
        results["errors"].append(f"Invalid YAML syntax: {e}")
        return results

    if not compose_data:
        results["errors"].append("Empty docker-compose.yml")
        return results

    services = compose_data.get("services", {})

    if not services:
        results["errors"].append("No services defined in docker-compose.yml")
        return results

    results["info"].append(f"Found {len(services)} service(s)")

    for service_name, service_config in services.items():
        if not isinstance(service_config, dict):
            continue

        # Check for healthcheck
        if "healthcheck" not in service_config:
            results["warnings"].append(
                f"Service '{service_name}': No healthcheck configured"
            )

        # Check for user
        user = service_config.get("user")
        if not user:
            results["warnings"].append(
                f"Service '{service_name}': No user specified - may run as root"
            )
        elif user in ["root", "0"]:
            results["errors"].append(
                f"Service '{service_name}': Configured to run as root"
            )

        # Check for restart policy
        if "restart" not in service_config:
            results["warnings"].append(
                f"Service '{service_name}': No restart policy configured"
            )

        # Check ports
        ports = service_config.get("ports", [])
        for port_mapping in ports:
            if isinstance(port_mapping, str) and ":" in port_mapping:
                host_port = port_mapping.split(":")[0]
                if host_port.isdigit():
                    port_num = int(host_port)
                    if port_num < 1024:
                        results["warnings"].append(
                            f"Service '{service_name}': Privileged port {port_num} - requires root"
                        )

        # Check environment variables
        env_vars = service_config.get("environment", [])
        if isinstance(env_vars, list):
            for env in env_vars:
                if isinstance(env, str) and "=" in env:
                    key, value = env.split("=", 1)
                    if any(secret in key.upper() for secret in ["PASSWORD", "SECRET", "KEY", "TOKEN"]):
                        if not value.startswith("${"):
                            results["warnings"].append(
                                f"Service '{service_name}': Potential hardcoded secret in {key}"
                            )

    return results


def _validate_sega_config(config_path: str) -> Dict[str, List[str]]:
    """Validate SEGA configuration file."""
    results = {"errors": [], "warnings": [], "info": []}

    try:
        import yaml
    except ImportError:
        results["warnings"].append("PyYAML not installed - skipping config validation")
        return results

    content = Path(config_path).read_text()

    try:
        config_data = yaml.safe_load(content)
    except yaml.YAMLError as e:
        results["errors"].append(f"Invalid YAML syntax: {e}")
        return results

    if not config_data:
        results["errors"].append("Empty SEGA config file")
        return results

    # Check required fields
    required_fields = ["project", "deployment"]
    for field in required_fields:
        if field not in config_data:
            results["warnings"].append(f"Missing recommended field: {field}")

    # Check project configuration
    project = config_data.get("project", {})
    if project:
        if "name" not in project:
            results["warnings"].append("Project name not specified")
        if "type" not in project:
            results["warnings"].append("Project type not specified")
        results["info"].append(f"Project: {project.get('name', 'unnamed')}")

    # Check deployment configuration
    deployment = config_data.get("deployment", {})
    if deployment:
        if "health_check" not in deployment:
            results["warnings"].append("No health_check configuration - SEGA requires health endpoints")
        results["info"].append(f"Deployment target: {deployment.get('target', 'not specified')}")

    return results


def _print_results(results: Dict[str, Any], dockerfile: Optional[str],
                   compose: Optional[str], config: Optional[str]):
    """Print validation results in human-readable format."""
    click.echo("SEGA Validation Report")
    click.echo("=" * 50)

    if dockerfile:
        click.echo(f"Dockerfile: {dockerfile}")
    if compose:
        click.echo(f"Compose: {compose}")
    if config:
        click.echo(f"Config: {config}")

    click.echo()

    # Print errors
    if results["errors"]:
        click.echo("[ERRORS]")
        for error in results["errors"]:
            click.echo(f"  [X] {error}")
        click.echo()

    # Print warnings
    if results["warnings"]:
        click.echo("[WARNINGS]")
        for warning in results["warnings"]:
            click.echo(f"  [!] {warning}")
        click.echo()

    # Print info
    if results["info"]:
        click.echo("[INFO]")
        for info in results["info"]:
            click.echo(f"  [i] {info}")
        click.echo()

    click.echo("=" * 50)
    if results["passed"]:
        click.echo("[OK] Validation passed")
    else:
        click.echo("[FAIL] Validation failed - fix errors before deployment")
