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
SEGA COMPREHENSIVE TESTING COMMAND - ENHANCED
==============================================================================
File: src/sega/commands/test_enhanced.py
Project: SEGA (Scalable Engineering & Growth Automation)
Copyright: 2022-2025 FLEET
License: Apache-2.0

SEGA MODULE: Commands/ComprehensiveTesting
COMPONENT: Multi-Type Test Runner with Docker Support
PURPOSE: Execute comprehensive test suites with Docker orchestration
DEPENDENCIES: click, json, TestOrchestrator, ProjectDetector
USAGE: sega test [OPTIONS] [--project PROJECT] [--suite SUITE]

This enhanced test command provides:
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
from tabulate import tabulate
from ...probe.test_orchestrator import TestOrchestrator, TestResult
from ...project.project_detector import ProjectDetector
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
                import json
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
                
        # Check for Electron test infrastructure
        desktop_path = project_path / 'desktop'
        if desktop_path.exists():
            desktop_package = desktop_path / 'package.json'
            if desktop_package.exists():
                try:
                    import json
                    with open(desktop_package) as f:
                        package_data = json.load(f)
                        
                    if 'test' in package_data.get('scripts', {}):
                        infrastructure['has_electron_test'] = True
                        infrastructure['test_commands'].append('cd desktop && npm test')
                        
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
        
    def run_docker_tests(self, project_path: Path, compose_file: str = None) -> TestResult:
        """Run tests using Docker Compose."""
        start_time = time.time()
        
        if not compose_file:
            # Find docker-compose.test.yml
            possible_files = [
                'docker-compose.test.yml',
                'docker/docker-compose.test.yml',
                'deployment/docker-compose.test.yml'
            ]
            
            for f in possible_files:
                if (project_path / f).exists():
                    compose_file = f
                    break
                    
        if not compose_file:
            return TestResult(
                success=False,
                test_type='docker',
                duration=time.time() - start_time,
                output='',
                error='No docker-compose.test.yml found'
            )
            
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
                return TestResult(
                    success=False,
                    test_type='docker',
                    duration=time.time() - start_time,
                    output=build_result.stdout,
                    error=f'Build failed: {build_result.stderr}'
                )
                
            # Run tests
            test_result = subprocess.run(
                ['docker-compose', '-f', compose_file, 'run', '--rm', 'test'],
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
            
            return TestResult(
                success=test_result.returncode == 0,
                test_type='docker',
                duration=time.time() - start_time,
                output=test_result.stdout,
                error=test_result.stderr if test_result.returncode != 0 else None
            )
            
        except subprocess.TimeoutExpired as e:
            return TestResult(
                success=False,
                test_type='docker',
                duration=time.time() - start_time,
                output='',
                error=f'Test timed out after {e.timeout} seconds'
            )
            
        except Exception as e:
            return TestResult(
                success=False,
                test_type='docker',
                duration=time.time() - start_time,
                output='',
                error=str(e)
            )
            
    def run_makefile_tests(self, project_path: Path, target: str = 'test') -> TestResult:
        """Run tests using Makefile targets."""
        start_time = time.time()
        
        try:
            result = subprocess.run(
                ['make', target],
                capture_output=True,
                text=True,
                cwd=project_path,
                timeout=600
            )
            
            return TestResult(
                success=result.returncode == 0,
                test_type=f'make_{target}',
                duration=time.time() - start_time,
                output=result.stdout,
                error=result.stderr if result.returncode != 0 else None
            )
            
        except subprocess.TimeoutExpired as e:
            return TestResult(
                success=False,
                test_type=f'make_{target}',
                duration=time.time() - start_time,
                output='',
                error=f'Test timed out after {e.timeout} seconds'
            )
            
        except Exception as e:
            return TestResult(
                success=False,
                test_type=f'make_{target}',
                duration=time.time() - start_time,
                output='',
                error=str(e)
            )
            
    def run_coverage_tests(self, project_path: Path, framework: str = None) -> TestResult:
        """Run tests with coverage reporting."""
        start_time = time.time()
        
        if not framework:
            # Detect framework
            infrastructure = self.detect_test_infrastructure(project_path)
            framework = infrastructure.get('framework')
            
        coverage_commands = {
            'pytest': ['python', '-m', 'pytest', '--cov=.', '--cov-report=term-missing', '--cov-report=html'],
            'jest': ['npm', 'run', 'test:coverage'],
            'go': ['go', 'test', '-cover', './...'],
            'cargo': ['cargo', 'tarpaulin', '--out', 'Html']
        }
        
        command = coverage_commands.get(framework)
        if not command:
            # Try make coverage
            return self.run_makefile_tests(project_path, 'test-coverage')
            
        try:
            result = subprocess.run(
                command,
                capture_output=True,
                text=True,
                cwd=project_path,
                timeout=600
            )
            
            # Parse coverage percentage from output
            coverage_percent = None
            if framework == 'pytest' and 'TOTAL' in result.stdout:
                # Extract coverage from pytest output
                for line in result.stdout.split('\n'):
                    if 'TOTAL' in line:
                        parts = line.split()
                        for part in parts:
                            if '%' in part:
                                coverage_percent = part
                                break
                                
            return TestResult(
                success=result.returncode == 0,
                test_type='coverage',
                duration=time.time() - start_time,
                output=result.stdout,
                error=result.stderr if result.returncode != 0 else None,
                metrics={'coverage': coverage_percent} if coverage_percent else None
            )
            
        except subprocess.TimeoutExpired as e:
            return TestResult(
                success=False,
                test_type='coverage',
                duration=time.time() - start_time,
                output='',
                error=f'Coverage test timed out after {e.timeout} seconds'
            )
            
        except Exception as e:
            return TestResult(
                success=False,
                test_type='coverage',
                duration=time.time() - start_time,
                output='',
                error=str(e)
            )
            
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
        results = {}
        
        # If coverage requested, run coverage tests
        if coverage:
            results['coverage'] = self.run_coverage_tests(project_path, infrastructure.get('framework'))
            return results
            
        # If specific suite requested
        if suite:
            if suite in ['unit', 'integration', 'e2e']:
                # Try Makefile target first
                make_target = f'test-{suite}'
                if suite in infrastructure.get('test_suites', []):
                    results[suite] = self.run_makefile_tests(project_path, make_target)
                else:
                    # Fall back to bBase orchestrator
                    results[suite] = self.bBase_orchestrator._run_unit_tests(
                        str(project_path),
                        ProjectDetector(str(project_path)).detect()
                    )
            else:
                results['error'] = TestResult(
                    success=False,
                    test_type='error',
                    duration=0.0,
                    output='',
                    error=f'Unknown test suite: {suite}'
                )
            return results
            
        # Run all available tests
        if infrastructure['has_docker_test']:
            results['docker'] = self.run_docker_tests(project_path)
            
        elif infrastructure['has_makefile_test']:
            results['make'] = self.run_makefile_tests(project_path)
            
        elif infrastructure['has_pytest']:
            results['pytest'] = self.bBase_orchestrator._run_python_unit_tests(str(project_path))
            
        elif infrastructure['has_jest']:
            results['jest'] = self.bBase_orchestrator._run_web_unit_tests(str(project_path))
            
        elif infrastructure['has_native_test']:
            results['native'] = self.bBase_orchestrator._run_native_unit_tests(str(project_path))
            
        else:
            results['generic'] = self.bBase_orchestrator._run_generic_unit_tests(str(project_path))
            
        return results
        
    def run_all_projects(self, suite: str = None, coverage: bool = False) -> Dict[str, Dict[str, TestResult]]:
        """Run tests for all projects in workspace."""
        all_results = {}
        
        # Get all projects with test infrastructure
        for project_dir in self.workspace_root.iterdir():
            if project_dir.is_dir() and not project_dir.name.startswith('.'):
                infrastructure = self.detect_test_infrastructure(project_dir)
                
                # Skip projects without test infrastructure
                if not any([
                    infrastructure['has_docker_test'],
                    infrastructure['has_makefile_test'],
                    infrastructure['has_pytest'],
                    infrastructure['has_jest'],
                    infrastructure['has_native_test']
                ]):
                    continue
                    
                all_results[project_dir.name] = self.run_project_tests(
                    project_dir.name,
                    suite=suite,
                    coverage=coverage
                )
                
        return all_results


@click.group(invoke_without_command=True)
@click.pass_context
@click.option('--project', '-p', help='Specific project to test')
@click.option('--suite', type=click.Choice(['unit', 'integration', 'e2e']), help='Test suite to run')
@click.option('--coverage', is_flag=True, help='Run tests with coverage reporting')
@click.option('--parallel', is_flag=True, help='Run tests in parallel')
@click.option('--output', type=click.Choice(['table', 'json', 'junit']), default='table', help='Output format')
def test(ctx, project, suite, coverage, parallel, output):
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
        
    # Run tests directly
    workspace_root = Path.cwd()
    orchestrator = EnhancedTestOrchestrator(workspace_root)
    
    click.echo("[INFO] Running comprehensive tests...")
    
    if project:
        # Test specific project
        click.echo(f"[INFO] Testing project: {project}")
        results = {project: orchestrator.run_project_tests(project, suite=suite, coverage=coverage)}
    else:
        # Test all projects
        click.echo("[INFO] Testing all projects in workspace...")
        results = orchestrator.run_all_projects(suite=suite, coverage=coverage)
        
    # Output results
    _output_results(results, output)
    
    # Calculate overall success
    total_tests = sum(len(project_results) for project_results in results.values())
    failed_tests = sum(
        1 for project_results in results.values()
        for result in project_results.values()
        if not result.success
    )
    
    if failed_tests > 0:
        click.echo(f"\n[ERROR] {failed_tests}/{total_tests} tests failed")
        ctx.exit(1)
    else:
        click.echo(f"\n[OK] All {total_tests} tests passed!")


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
        results = {project: orchestrator.run_docker_tests(Path.cwd() / project)}
    else:
        click.echo("[INFO] Running all tests in Docker environment...")
        results = {}
        
        for project_dir in Path.cwd().iterdir():
            if project_dir.is_dir() and not project_dir.name.startswith('.'):
                compose_test = project_dir / 'docker-compose.test.yml'
                if compose_test.exists():
                    results[project_dir.name] = orchestrator.run_docker_tests(project_dir)
                    
    # Output results
    _output_results({k: {'docker': v} for k, v in results.items()}, 'table')


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


def _output_results(results: Dict[str, Dict[str, TestResult]], format: str):
    """Output test results in specified format."""
    if format == 'json':
        json_output = {}
        for project, project_results in results.items():
            json_output[project] = {}
            for test_type, result in project_results.items():
                json_output[project][test_type] = {
                    'success': result.success,
                    'duration': result.duration,
                    'output': result.output[:500] if result.output else '',
                    'error': result.error,
                    'metrics': result.metrics
                }
        click.echo(json.dumps(json_output, indent=2))
        
    elif format == 'junit':
        import xml.etree.ElementTree as ET
        from datetime import datetime
        
        testsuite = ET.Element('testsuite')
        testsuite.set('name', 'SEGA Tests')
        testsuite.set('timestamp', datetime.now().isoformat())
        
        total_tests = 0
        total_failures = 0
        total_time = 0.0
        
        for project, project_results in results.items():
            for test_type, result in project_results.items():
                total_tests += 1
                total_time += result.duration
                
                if not result.success:
                    total_failures += 1
                    
                testcBase = ET.SubElement(testsuite, 'testcBase')
                testcBase.set('name', f'{project}.{test_type}')
                testcBase.set('classname', f'sega.test.{project}')
                testcBase.set('time', f'{result.duration:.2f}')
                
                if not result.success:
                    failure = ET.SubElement(testcBase, 'failure')
                    failure.set('message', result.error or 'Test failed')
                    failure.text = result.output
                    
        testsuite.set('tests', str(total_tests))
        testsuite.set('failures', str(total_failures))
        testsuite.set('time', f'{total_time:.2f}')
        
        ET.indent(testsuite, space='  ')
        click.echo(ET.toString(testsuite, encoding='unicode'))
        
    else:  # table format
        all_rows = []
        
        for project, project_results in sorted(results.items()):
            for test_type, result in sorted(project_results.items()):
                status = '[OK]' if result.success else '[FAIL]'
                duration = f'{result.duration:.2f}s'
                
                # Extract key metrics
                metrics_str = ''
                if result.metrics:
                    if 'coverage' in result.metrics:
                        metrics_str = f"Coverage: {result.metrics['coverage']}"
                    else:
                        metrics_str = ', '.join(f'{k}: {v}' for k, v in result.metrics.items())
                        
                error_str = result.error[:50] + '...' if result.error and len(result.error) > 50 else result.error or ''
                
                all_rows.append([
                    project,
                    test_type,
                    status,
                    duration,
                    metrics_str,
                    error_str
                ])
                
        if all_rows:
            headers = ['Project', 'Test Type', 'Status', 'Duration', 'Metrics', 'Error']
            click.echo('\n' + tabulate(all_rows, headers=headers, tablefmt='grid'))
            
            # Summary statistics
            total = len(all_rows)
            passed = sum(1 for row in all_rows if row[2] == '[OK]')
            failed = total - passed
            
            click.echo(f"\nSummary: {passed}/{total} passed, {failed} failed")


# Register the enhanced test command
if __name__ == '__main__':
    test()