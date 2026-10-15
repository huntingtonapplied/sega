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
SEGA COMPREHENSIVE TESTING COMMAND
==============================================================================
File: src/sega/commands/test.py
Project: SEGA (Scalable Engineering & Growth Automation)
Copyright: 2022-2025 FLEET
License: Apache-2.0

SEGA MODULE: Commands/ComprehensiveTesting
COMPONENT: Multi-Type Test Runner CLI Command with Docker Support
PURPOSE: Execute comprehensive test suites with Docker orchestration
DEPENDENCIES: click, json, TestOrchestrator, ProjectDetector
USAGE: sega test [OPTIONS] [--project PROJECT] [--suite SUITE]

This enhanced command provides:
- Unified testing orchestration across all FLEET projects
- Docker-based test environment management
- Intelligent test detection for multiple frameworks
- Comprehensive coverage reporting
- Integration with existing test infrastructure
==============================================================================
"""

import click
import json
import subprocess
import time
from pathlib import Path
from typing import Dict, Any
from ...probe.test_orchestrator import TestOrchestrator, TestResult
from ...local import LocalDeploymentManager, SharedInfrastructureManager


class EnhancedTestOrchestrator:
    """Enhanced test orchestration with Docker support and intelligent detection."""
    
    def __init__(self, workspace_root: Path = None):
        self.workspace_root = workspace_root or Path.cwd()
        self.bBase_orchestrator = TestOrchestrator()
        
    def detect_test_infrastructure(self, project_path: Path) -> Dict[str, Any]:
        """Detect available test infrastructure in a project."""
        infrastructure = {
            'has_docker_test': False,
            'has_makefile_test': False,
            'has_pytest': False,
            'has_jest': False,
            'has_electron_test': False,
            'has_native_test': False,
            'test_commands': [],
            'test_suites': [],
            'docker_compose_files': [],
            'framework': None
        }
        
        # Check for docker-compose.test.yml
        docker_test_files = [
            'docker-compose.test.yml',
            'docker/docker-compose.test.yml',
            'deployment/docker-compose.test.yml'
        ]
        
        for test_file in docker_test_files:
            if (project_path / test_file).exists():
                infrastructure['has_docker_test'] = True
                infrastructure['docker_compose_files'].append(test_file)
                
        # Check for Makefile test targets
        makefile = project_path / 'Makefile'
        if makefile.exists():
            try:
                result = subprocess.run(
                    ['make', '-n', 'test'],
                    capture_output=True,
                    text=True,
                    cwd=project_path,
                    timeout=5
                )
                if result.returncode == 0:
                    infrastructure['has_makefile_test'] = True
                    infrastructure['test_commands'].append('make test')
                    
                # Check for other test targets
                for target in ['test-unit', 'test-integration', 'test-e2e', 'test-coverage']:
                    result = subprocess.run(
                        ['make', '-n', target],
                        capture_output=True,
                        text=True,
                        cwd=project_path,
                        timeout=5
                    )
                    if result.returncode == 0:
                        infrastructure['test_suites'].append(target.replace('test-', ''))
                        
            except (subprocess.TimeoutExpired, subprocess.SubprocessError):
                pass
                
        # Check for Python test infrastructure
        pytest_indicators = [
            'pytest.ini',
            'setup.cfg',
            'pyproject.toml',
            'tests/',
            'test/',
            'test_*.py'
        ]
        
        for indicator in pytest_indicators:
            if (project_path / indicator).exists() or list(project_path.glob(indicator)):
                infrastructure['has_pytest'] = True
                infrastructure['framework'] = 'pytest'
                infrastructure['test_commands'].append('python -m pytest')
                break
                
        # Check for JavaScript test infrastructure
        package_json = project_path / 'package.json'
        if package_json.exists():
            try:
                with open(package_json) as f:
                    package_data = json.load(f)
                    
                scripts = package_data.get('scripts', {})
                if 'test' in scripts:
                    infrastructure['has_jest'] = True
                    infrastructure['framework'] = 'jest'
                    infrastructure['test_commands'].append('npm test')
                    
                # Check for specific test scripts
                for script_name in ['test:unit', 'test:integration', 'test:e2e', 'test:coverage']:
                    if script_name in scripts:
                        suite_name = script_name.split(':')[1]
                        if suite_name not in infrastructure['test_suites']:
                            infrastructure['test_suites'].append(suite_name)
                            
            except (json.JSONDecodeError, FileNotFoundError):
                pass
                
        # Check for native test infrastructure (Go, Rust, etc.)
        if (project_path / 'go.mod').exists():
            infrastructure['has_native_test'] = True
            infrastructure['framework'] = 'go'
            infrastructure['test_commands'].append('go test ./...')
            
        elif (project_path / 'Cargo.toml').exists():
            infrastructure['has_native_test'] = True
            infrastructure['framework'] = 'cargo'
            infrastructure['test_commands'].append('cargo test')
            
        return infrastructure
        
    def run_project_tests(self, project_name: str, suite: str = None, coverage: bool = False) -> Dict[str, TestResult]:
        """Run tests for a specific project."""
        project_path = self.workspace_root / project_name
        
        if not project_path.exists():
            return {
                'error': TestResult(
                    success=False,
                    test_type='error',
                    duration=0.0,
                    output='',
                    error=f'Project {project_name} not found'
                )
            }
            
        # Detect test infrastructure
        infrastructure = self.detect_test_infrastructure(project_path)
        
        # Determine which test runner to use
        if infrastructure['has_docker_test']:
            # Prefer Docker-based testing
            compose_file = infrastructure['docker_compose_files'][0]
            return self._run_docker_tests(project_path, compose_file, suite, coverage)
        elif infrastructure['has_makefile_test']:
            # Use Makefile targets
            return self._run_makefile_tests(project_path, suite, coverage)
        else:
            # Fall back to bBase orchestrator
            test_types = [suite] if suite else ['unit']
            return self.bBase_orchestrator.run_tests(test_types, str(project_path))
            
    def _run_docker_tests(self, project_path: Path, compose_file: str, suite: str = None, coverage: bool = False) -> Dict[str, TestResult]:
        """Run tests using Docker Compose."""
        start_time = time.time()
        
        try:
            # Build test containers
            build_result = subprocess.run(
                ['docker-compose', '-f', compose_file, 'build'],
                capture_output=True,
                text=True,
                cwd=project_path,
                timeout=300
            )
            
            if build_result.returncode != 0:
                return {
                    'docker': TestResult(
                        success=False,
                        test_type='docker',
                        duration=time.time() - start_time,
                        output=build_result.stdout,
                        error=f'Build failed: {build_result.stderr}'
                    )
                }
                
            # Determine test command
            test_service = 'test'
            if suite:
                test_service = f'test-{suite}'
            elif coverage:
                test_service = 'test-coverage'
                
            # Run tests
            test_result = subprocess.run(
                ['docker-compose', '-f', compose_file, 'run', '--rm', test_service],
                capture_output=True,
                text=True,
                cwd=project_path,
                timeout=600
            )
            
            # Clean up
            subprocess.run(
                ['docker-compose', '-f', compose_file, 'down', '-v'],
                capture_output=True,
                text=True,
                cwd=project_path,
                timeout=30
            )
            
            return {
                'docker': TestResult(
                    success=test_result.returncode == 0,
                    test_type='docker',
                    duration=time.time() - start_time,
                    output=test_result.stdout,
                    error=test_result.stderr if test_result.returncode != 0 else None
                )
            }
            
        except subprocess.TimeoutExpired as e:
            return {
                'docker': TestResult(
                    success=False,
                    test_type='docker',
                    duration=time.time() - start_time,
                    output='',
                    error=f'Test timed out after {e.timeout} seconds'
                )
            }
            
        except Exception as e:
            return {
                'docker': TestResult(
                    success=False,
                    test_type='docker',
                    duration=time.time() - start_time,
                    output='',
                    error=str(e)
                )
            }
            
    def _run_makefile_tests(self, project_path: Path, suite: str = None, coverage: bool = False) -> Dict[str, TestResult]:
        """Run tests using Makefile targets."""
        start_time = time.time()
        
        # Determine target
        if coverage:
            target = 'test-coverage'
        elif suite:
            target = f'test-{suite}'
        else:
            target = 'test'
            
        try:
            result = subprocess.run(
                ['make', target],
                capture_output=True,
                text=True,
                cwd=project_path,
                timeout=600
            )
            
            return {
                'make': TestResult(
                    success=result.returncode == 0,
                    test_type=f'make_{target}',
                    duration=time.time() - start_time,
                    output=result.stdout,
                    error=result.stderr if result.returncode != 0 else None
                )
            }
            
        except subprocess.TimeoutExpired as e:
            return {
                'make': TestResult(
                    success=False,
                    test_type=f'make_{target}',
                    duration=time.time() - start_time,
                    output='',
                    error=f'Test timed out after {e.timeout} seconds'
                )
            }
            
        except Exception as e:
            return {
                'make': TestResult(
                    success=False,
                    test_type=f'make_{target}',
                    duration=time.time() - start_time,
                    output='',
                    error=str(e)
                )
            }


@click.group(invoke_without_command=True)
@click.pass_context
@click.option('--project', '-p', help='Specific project to test')
@click.option('--suite', type=click.Choice(['unit', 'integration', 'e2e']), help='Test suite to run')
@click.option('--coverage', is_flag=True, help='Run tests with coverage reporting')
@click.option('--output', type=click.Choice(['table', 'json', 'junit']), default='table', help='Output format')
@click.option('--type', 'test_types', multiple=True, help='Legacy: Test types to run')
@click.option('--parallel', is_flag=True, help='Run tests in parallel')
@click.option('--fail-fast', is_flag=True, help='Stop on first test failure')
def test(ctx, project, suite, coverage, output, test_types, parallel, fail_fast):
    """Run comprehensive tests with Docker orchestration.
    
    This enhanced test command provides unified testing across all FLEET projects,
    with automatic detection of test infrastructure and Docker-based test environments.
    
    Examples:
        sega test                        # Auto-detect and run all tests
        sega test --project orion     # Test specific project
        sega test --suite unit          # Run unit tests only
        sega test --coverage            # Generate coverage reports
        sega test local up              # Start test infrastructure
        sega test local run             # Run tests in Docker environment
    """

    # If subcommand is invoked, let it handle
    if ctx.invoked_subcommand is not None:
        return
        
    # Legacy support for --type option
    if test_types:
        # Use original TestOrchestrator for legacy behavior
        orchestrator = TestOrchestrator()
        
        click.echo("[INFO] Running tests (legacy mode)...")
        click.echo(f"Test types: {', '.join(test_types)}")
        
        if parallel:
            click.echo("Running tests in parallel...")
            from concurrent.futures import ThreadPoolExecutor, as_completed
            
            with ThreadPoolExecutor(max_workers=4) as executor:
                futures = {
                    executor.submit(orchestrator.run_tests, [test_type]): test_type 
                    for test_type in test_types
                }
                
                results = {'passed': [], 'failed': []}
                for future in as_completed(futures):
                    test_type = futures[future]
                    try:
                        result = future.result()
                        if result.get('passed'):
                            results['passed'].extend(result['passed'])
                        if result.get('failed'):
                            results['failed'].extend(result['failed'])
                    except Exception as e:
                        results['failed'].append({
                            'test': test_type,
                            'error': str(e)
                        })
        else:
            click.echo("Running tests sequentially...")
            results = orchestrator.run_tests(test_types)
    else:
        # Use enhanced orchestrator
        workspace_root = Path.cwd()
        orchestrator = EnhancedTestOrchestrator(workspace_root)
        
        click.echo("[INFO] Running comprehensive tests...")
        
        if project:
            # Test specific project
            click.echo(f"[INFO] Testing project: {project}")
            project_results = orchestrator.run_project_tests(project, suite=suite, coverage=coverage)
            results = project_results
        else:
            # Auto-detect and test all projects
            click.echo("[INFO] Auto-detecting and testing all projects...")
            results = {}
            
            for project_dir in workspace_root.iterdir():
                if project_dir.is_dir() and not project_dir.name.startswith('.'):
                    infrastructure = orchestrator.detect_test_infrastructure(project_dir)
                    
                    # Skip projects without test infrastructure
                    if not any([
                        infrastructure['has_docker_test'],
                        infrastructure['has_makefile_test'],
                        infrastructure['has_pytest'],
                        infrastructure['has_jest'],
                        infrastructure['has_native_test']
                    ]):
                        continue
                        
                    click.echo(f"[INFO] Testing {project_dir.name}...")
                    project_results = orchestrator.run_project_tests(
                        project_dir.name,
                        suite=suite,
                        coverage=coverage
                    )
                    
                    # Merge results
                    for test_type, result in project_results.items():
                        results[f"{project_dir.name}_{test_type}"] = result

    # Output results
    if output == "table":
        _output_table(results, fail_fast)
    elif output == "json":
        _output_json(results)
    elif output == "junit":
        _output_junit(results)

    # Summary
    total_tests = len(results)
    passed_tests = sum(1 for r in results.values() if r.success)
    failed_tests = total_tests - passed_tests

    click.echo("\n[INFO] Test Summary:")
    click.echo(f"Total: {total_tests}")
    click.echo(f"Passed: {passed_tests}")
    click.echo(f"Failed: {failed_tests}")

    if failed_tests > 0:
        click.echo(f"\n[ERROR] {failed_tests} test(s) failed")
        ctx.exit(1)
    else:
        click.echo("\n[OK] All tests passed!")


def _output_table(results, fail_fast):
    """Output test results in table format."""
    click.echo("\n" + "=" * 80)
    click.echo("Test Results")
    click.echo("=" * 80)

    for test_type, result in results.items():
        status_icon = "[OK]" if result.success else "[FAIL]"
        duration_str = (
            f"{result.duration:.2f}s" if result.duration > 0 else "N/A"
        )

        click.echo(f"{status_icon} {test_type.upper()} - {duration_str}")

        if result.output:
            # Show first few lines of output
            output_lines = result.output.split("\n")[:5]
            for line in output_lines:
                if line.strip():
                    click.echo(f"   {line}")

        if result.error:
            click.echo(f"   Error: {result.error}")

        if result.metrics:
            click.echo(f"   Metrics: {result.metrics}")

        click.echo()

        if fail_fast and not result.success:
            click.echo("Stopping due to --fail-fast")
            break


def _output_json(results):
    """Output test results in JSON format."""

    json_results = {}
    for test_type, result in results.items():
        json_results[test_type] = {
            "success": result.success,
            "duration": result.duration,
            "output": result.output,
            "error": result.error,
            "metrics": result.metrics,
        }

    click.echo(json.dumps(json_results, indent=2))


def _output_junit(results):
    """Output test results in JUnit XML format."""
    import xml.etree.ElementTree as ET
    from datetime import datetime

    # Create JUnit XML structure
    testsuite = ET.Element("testsuite")
    testsuite.set("name", "SEGA Tests")
    testsuite.set("tests", str(len(results)))
    testsuite.set(
        "failures", str(sum(1 for r in results.values() if not r.success))
    )
    testsuite.set("timestamp", datetime.now().isoformat())

    total_time = sum(r.duration for r in results.values())
    testsuite.set("time", f"{total_time:.2f}")

    for test_type, result in results.items():
        testcBase = ET.SubElement(testsuite, "testcBase")
        testcBase.set("name", test_type)
        testcBase.set("classname", "sega.test")
        testcBase.set("time", f"{result.duration:.2f}")

        if not result.success:
            failure = ET.SubElement(testcBase, "failure")
            failure.set("message", result.error or "Test failed")
            failure.text = result.output

        if result.output:
            system_out = ET.SubElement(testcBase, "system-out")
            system_out.text = result.output

    # Pretty print XML
    ET.indent(testsuite, space="  ")
    click.echo(ET.toString(testsuite, encoding="unicode"))


# Add local subgroup for test environment management
@test.group()
def local():
    """Manage local test environments.
    
    Similar to 'sega local' but specifically for test infrastructure.
    """
    pass


@local.command()
@click.option('--project', '-p', multiple=True, help='Specific project(s) to setup')
@click.option('--all', 'setup_all', is_flag=True, help='Setup all project test environments')
def up(project, setup_all):
    """Start test infrastructure.
    
    Examples:
        sega test local up               # Start shared test databases
        sega test local up --all         # Start all test environments
        sega test local up -p orion   # Start specific project test env
    """
    manager = LocalDeploymentManager()
    infra_manager = SharedInfrastructureManager(
        workspace_root=manager.workspace_root,
        config=manager.config
    )
    
    # Start test infrastructure (databases, redis, etc.)
    click.echo("[INFO] Starting test infrastructure...")
    if not infra_manager.start(profile='testing'):
        click.echo("[WARNING] Failed to start test infrastructure")
        return
        
    if setup_all or project:
        # Start project-specific test containers
        projects_to_setup = project if project else manager.get_projects_with_compose()
        
        for proj in projects_to_setup:
            project_path = manager.workspace_root / proj
            compose_file = project_path / 'docker-compose.test.yml'
            
            if compose_file.exists():
                click.echo(f"[INFO] Starting test environment for {proj}...")
                result = subprocess.run(
                    ['docker-compose', '-f', 'docker-compose.test.yml', 'up', '-d'],
                    capture_output=True,
                    text=True,
                    cwd=project_path
                )
                
                if result.returncode == 0:
                    click.echo(f"[OK] Test environment for {proj} started")
                else:
                    click.echo(f"[ERROR] Failed to start test environment for {proj}")
                    
    click.echo("\n[OK] Test infrastructure is ready")
    click.echo("Run 'sega test local run' to execute tests")


@local.command()
@click.option('--project', '-p', multiple=True, help='Specific project(s) to stop')
@click.option('--all', 'stop_all', is_flag=True, help='Stop all test environments')
def down(project, stop_all):
    """Stop test infrastructure.
    
    Examples:
        sega test local down             # Stop test infrastructure
        sega test local down --all       # Stop all test environments
        sega test local down -p orion # Stop specific project test env
    """
    manager = LocalDeploymentManager()
    infra_manager = SharedInfrastructureManager(
        workspace_root=manager.workspace_root,
        config=manager.config
    )
    
    if stop_all or project:
        # Stop project-specific test containers
        projects_to_stop = project if project else manager.get_projects_with_compose()
        
        for proj in projects_to_stop:
            project_path = manager.workspace_root / proj
            compose_file = project_path / 'docker-compose.test.yml'
            
            if compose_file.exists():
                click.echo(f"[INFO] Stopping test environment for {proj}...")
                subprocess.run(
                    ['docker-compose', '-f', 'docker-compose.test.yml', 'down', '-v'],
                    capture_output=True,
                    text=True,
                    cwd=project_path
                )
                
    # Stop test infrastructure
    click.echo("[INFO] Stopping test infrastructure...")
    infra_manager.stop()
    
    click.echo("[OK] Test infrastructure stopped")


@local.command()
@click.option('--project', '-p', help='Specific project to test')
@click.option('--suite', type=click.Choice(['unit', 'integration', 'e2e']), help='Test suite to run')
@click.option('--coverage', is_flag=True, help='Run with coverage')
def run(project, suite, coverage):
    """Run tests in Docker environment.
    
    Examples:
        sega test local run              # Run all tests
        sega test local run -p orion  # Run tests for specific project
        sega test local run --coverage   # Run with coverage reporting
    """
    orchestrator = EnhancedTestOrchestrator(Path.cwd())
    
    if project:
        click.echo(f"[INFO] Running tests for {project} in Docker environment...")
        results = orchestrator.run_project_tests(project, suite=suite, coverage=coverage)
    else:
        click.echo("[INFO] Running all tests in Docker environment...")
        results = {}
        
        for project_dir in Path.cwd().iterdir():
            if project_dir.is_dir() and not project_dir.name.startswith('.'):
                infrastructure = orchestrator.detect_test_infrastructure(project_dir)
                
                if infrastructure['has_docker_test']:
                    project_results = orchestrator.run_project_tests(
                        project_dir.name,
                        suite=suite,
                        coverage=coverage
                    )
                    
                    for test_type, result in project_results.items():
                        results[f"{project_dir.name}_{test_type}"] = result
                        
    # Output results
    _output_table(results, False)
    
    # Summary
    total_tests = len(results)
    passed_tests = sum(1 for r in results.values() if r.success)
    failed_tests = total_tests - passed_tests
    
    if failed_tests > 0:
        click.echo(f"\n[ERROR] {failed_tests}/{total_tests} tests failed")
    else:
        click.echo(f"\n[OK] All {total_tests} tests passed!")


@local.command()
def status():
    """Show status of test infrastructure.
    
    Example:
        sega test local status
    """
    manager = LocalDeploymentManager()
    infra_manager = SharedInfrastructureManager(
        workspace_root=manager.workspace_root,
        config=manager.config
    )
    
    # Get infrastructure status
    infra_status = infra_manager.get_status()
    
    click.echo("\n[INFO] Test Infrastructure Status")
    click.echo("=" * 60)
    
    # Show test environment status
    test_env = infra_status.get('testing', {})
    if test_env:
        click.echo("\nTest Environment:")
        for service, info in test_env.items():
            status_icon = "[OK]" if info['running'] else "[--]"
            health = info.get('health', 'unknown')
            port = info.get('port', 'N/A')
            click.echo(f"  {status_icon} {service:<15} Port: {port:<6} Health: {health}")
    else:
        click.echo("\n[WARNING] No test infrastructure running")
        
    # Check for project test containers
    click.echo("\nProject Test Environments:")
    has_test_envs = False
    
    for project_dir in manager.workspace_root.iterdir():
        if project_dir.is_dir() and not project_dir.name.startswith('.'):
            compose_test = project_dir / 'docker-compose.test.yml'
            if compose_test.exists():
                # Check if containers are running
                result = subprocess.run(
                    ['docker-compose', '-f', 'docker-compose.test.yml', 'ps', '-q'],
                    capture_output=True,
                    text=True,
                    cwd=project_dir
                )
                
                if result.stdout.strip():
                    click.echo(f"  [OK] {project_dir.name}")
                    has_test_envs = True
                    
    if not has_test_envs:
        click.echo("  [--] No project test environments running")
        
    click.echo("\nRun 'sega test local up' to start test infrastructure")
