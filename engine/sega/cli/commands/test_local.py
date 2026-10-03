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
SEGA TEST LOCAL ENVIRONMENT MANAGEMENT
==============================================================================
File: src/sega/commands/test_local.py
Project: SEGA (Scalable Engineering & Growth Automation)
Copyright: 2022-2025 FLEET
License: Apache-2.0

SEGA MODULE: Commands/TestLocalEnvironment
COMPONENT: Local Test Environment Management CLI
PURPOSE: Manage local test environments with Docker orchestration
DEPENDENCIES: click, docker-compose, TestOrchestrator
USAGE: sega test local [COMMAND] [--project PROJECT]

This command manages local test environments, paralleling sega local for deployment.
Orchestrates test databases, services, and environments using docker-compose.test.yml files.
==============================================================================
"""

import click
import subprocess
from pathlib import Path
from ...probe.test_orchestrator import TestOrchestrator
from ...project.project_detector import ProjectDetector


@click.group()
def test_local():
    """Manage local test environments and execution."""
    pass


@test_local.command()
@click.option(
    "--project", "-p",
    help="Specific project to test (auto-detects current directory if not specified)",
)
@click.option(
    "--suite", "-s",
    type=click.Choice(["unit", "integration", "e2e", "all"]),
    default="all",
    help="Test suite to run",
)
@click.option("--coverage", is_flag=True, help="Generate coverage report")
@click.option("--parallel", is_flag=True, help="Run tests in parallel")
def run(project, suite, coverage, parallel):
    """Run tests in local Docker environment."""
    project_path = _get_project_path(project)
    
    click.echo(" Running tests in local environment...")
    if project:
        click.echo(f"Project: {project}")
    click.echo(f"Test suite: {suite}")
    
    # Check for docker-compose.test.yml
    test_compose_file = Path(project_path) / "docker-compose.test.yml"
    if not test_compose_file.exists():
        click.echo("  No docker-compose.test.yml found")
        click.echo("Creating basic test environment...")
        _create_basic_test_compose(project_path)
    
    # Start test environment
    click.echo("  Starting test environment...")
    _run_docker_compose_test(project_path, "up", ["-d"])
    
    # Wait for services to be ready
    click.echo(" Waiting for test services...")
    _wait_for_test_services(project_path)
    
    # Run tests
    orchestrator = TestOrchestrator()
    test_types = _suite_to_test_types(suite)
    
    try:
        results = orchestrator.run_tests_in_docker(
            test_types, project_path, coverage=coverage, parallel=parallel
        )
        
        # Output results
        _output_test_results(results)
        
        # Check if any tests failed
        failed_tests = sum(1 for r in results.values() if not r.success)
        if failed_tests > 0:
            click.echo(f"\n  {failed_tests} test(s) failed")
            exit(1)
        else:
            click.echo("\n  All tests passed!")
            
    finally:
        # Cleanup is handled by down command or user choice
        click.echo("\n  Use 'sega test local down' to stop test environment")


@test_local.command()
@click.option(
    "--project", "-p",
    help="Specific project (auto-detects current directory if not specified)",
)
def up(project):
    """Start test environment services."""
    project_path = _get_project_path(project)
    
    click.echo("  Starting test environment...")
    if project:
        click.echo(f"Project: {project}")
    
    test_compose_file = Path(project_path) / "docker-compose.test.yml"
    if not test_compose_file.exists():
        click.echo("  No docker-compose.test.yml found")
        click.echo("Creating basic test environment...")
        _create_basic_test_compose(project_path)
    
    _run_docker_compose_test(project_path, "up", ["-d"])
    _wait_for_test_services(project_path)
    
    click.echo("  Test environment ready")
    click.echo("  Use 'sega test local run' to execute tests")


@test_local.command()
@click.option(
    "--project", "-p",
    help="Specific project (auto-detects current directory if not specified)",
)
def down(project):
    """Stop test environment services."""
    project_path = _get_project_path(project)
    
    click.echo(" Stopping test environment...")
    if project:
        click.echo(f"Project: {project}")
    
    _run_docker_compose_test(project_path, "down", [])
    click.echo("  Test environment stopped")


@test_local.command()
@click.option(
    "--project", "-p",
    help="Specific project (auto-detects current directory if not specified)",
)
def status(project):
    """Show test environment status."""
    project_path = _get_project_path(project)
    
    click.echo("  Test environment status:")
    if project:
        click.echo(f"Project: {project}")
    
    test_compose_file = Path(project_path) / "docker-compose.test.yml"
    if not test_compose_file.exists():
        click.echo("  No docker-compose.test.yml found")
        return
    
    _run_docker_compose_test(project_path, "ps", [])


@test_local.command()
@click.option(
    "--project", "-p",
    help="Specific project (auto-detects current directory if not specified)",
)
def logs(project):
    """View test environment logs."""
    project_path = _get_project_path(project)
    
    click.echo("  Test environment logs:")
    if project:
        click.echo(f"Project: {project}")
    
    _run_docker_compose_test(project_path, "logs", ["-f"])


# Helper functions

def _get_project_path(project):
    """Get project path from project name or current directory."""
    if project:
        from ...utils.paths import get_fleet_root
        return str(get_fleet_root() / project)
    else:
        return "."


def _run_docker_compose_test(project_path, command, args):
    """Run docker-compose command with test file."""
    cmd = ["docker-compose", "-f", "docker-compose.test.yml", command] + args
    
    try:
        result = subprocess.run(
            cmd,
            cwd=project_path,
            check=True,
            capture_output=False
        )
    except subprocess.CalledProcessError as e:
        click.echo(f"  Docker compose command failed: {e}")
        exit(1)


def _wait_for_test_services(project_path):
    """Wait for test services to be ready."""
    # Simple implementation - wait for common services
    services_to_check = ["test-postgres", "test-redis"]
    
    for service in services_to_check:
        # Check if service exists in compose file
        test_compose_file = Path(project_path) / "docker-compose.test.yml"
        if test_compose_file.exists():
            with open(test_compose_file) as f:
                content = f.read()
                if service in content:
                    click.echo(f" Waiting for {service}...")
                    import time
                    import subprocess
                    
                    # Implement proper health checks based on service type
                    max_retries = 30
                    retry_interval = 2
                    
                    for attempt in range(max_retries):
                        try:
                            # Check if container is running
                            result = subprocess.run(
                                ["docker", "compose", "-f", str(test_compose_file), 
                                 "ps", service],
                                capture_output=True,
                                text=True,
                                check=False
                            )
                            
                            if "Up" in result.stdout or "running" in result.stdout.lower():
                                # Container is running, check if it's healthy
                                health_result = subprocess.run(
                                    ["docker", "inspect", "--format='{{.State.Health.Status}}'",
                                     f"{project_path.name}_{service}_1"],
                                    capture_output=True,
                                    text=True,
                                    check=False
                                )
                                
                                if "healthy" in health_result.stdout or attempt > 5:
                                    click.echo(f" {service} is ready")
                                    break
                            
                        except Exception:
                            pass
                        
                        if attempt < max_retries - 1:
                            time.sleep(retry_interval)
                    else:
                        click.echo(f"  {service} may not be fully ready")


def _suite_to_test_types(suite):
    """Convert suite name to test types."""
    if suite == "unit":
        return ["unit"]
    elif suite == "integration":
        return ["integration"]
    elif suite == "e2e":
        return ["e2e"]
    else:
        return ["unit", "integration"]


def _create_basic_test_compose(project_path):
    """Create a basic docker-compose.test.yml if none exists."""
    detector = ProjectDetector(project_path)
    project_type = detector.detect()
    
    # Basic template based on project type
    basic_compose = """# Docker Compose for Testing Infrastructure
# Auto-generated by SEGA - customize as needed

services:
  test-db:
    image: postgres:13-alpine
    environment:
      POSTGRES_DB: test_db
      POSTGRES_USER: test
      POSTGRES_PASSWORD: test
    ports:
      - "5433:5432"
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U test -d test_db"]
      interval: 5s
      timeout: 5s
      retries: 5
    networks:
      - test-network

  test-redis:
    image: redis:6-alpine
    ports:
      - "6380:6379"
    healthcheck:
      test: ["CMD", "redis-cli", "ping"]
      interval: 5s
      timeout: 3s
      retries: 5
    networks:
      - test-network

networks:
  test-network:
    driver: bridge
"""
    
    compose_file = Path(project_path) / "docker-compose.test.yml"
    with open(compose_file, 'w') as f:
        f.write(basic_compose)
    
    click.echo("  Created basic docker-compose.test.yml")


def _output_test_results(results):
    """Output test results in a formatted way."""
    click.echo("\n  Test Results:")
    
    total_tests = len(results)
    passed_tests = sum(1 for r in results.values() if r.success)
    failed_tests = total_tests - passed_tests
    
    for test_type, result in results.items():
        status = " " if result.success else " "
        duration = f"{result.duration:.2f}s"
        click.echo(f"  {status} {test_type}: {duration}")
        
        if not result.success and result.error:
            click.echo(f"    Error: {result.error}")
    
    click.echo(f"\nSummary: {passed_tests}/{total_tests} passed")