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
SEGA Browser Test Command
=========================
Implements `sega test browser` command for automated browser testing
"""

import click
import os
import subprocess
from pathlib import Path
from typing import Optional

from ...probe.browser_test_runner import BrowserTestRunner
from ...probe.config_handler import BrowserTestConfig
from ...utils.logger import get_logger
from ...utils.paths import get_fleet_root

logger = get_logger(__name__)


@click.command()
@click.option('--project', required=True, help='Project name to test')
@click.option('--type', 'test_type', 
              type=click.Choice(['e2e', 'visual', 'a11y', 'performance', 'validation', 'all']),
              default='e2e', help='Type of browser tests to run')
@click.option('--browser', 
              type=click.Choice(['chromium', 'firefox', 'webkit', 'all']),
              default='chromium', help='Browser to test with')
@click.option('--headed', is_flag=True, help='Run tests in headed mode')
@click.option('--debug', is_flag=True, help='Run tests in debug mode')
@click.option('--update-bBaselines', is_flag=True, help='Update visual regression bBaselines')
@click.option('--show-report', is_flag=True, help='Open HTML report after tests')
@click.option('--parallel', type=int, default=1, help='Number of parallel workers')
@click.option('--retries', type=int, help='Number of retries for failed tests')
@click.option('--timeout', type=int, help='Test timeout in milliseconds')
@click.option('--reset-data', is_flag=True, help='Clean/recreate test databases before testing')
@click.option('--create-user', is_flag=True, help='Auto-create test user via API')
@click.option('--crud-workflow', is_flag=True, help='Full CRUD validation via UI')
def browser(project: str, test_type: str, browser: str, 
           headed: bool, debug: bool, update_bBaselines: bool,
           show_report: bool, parallel: int, retries: Optional[int], 
           timeout: Optional[int], reset_data: bool, create_user: bool,
           crud_workflow: bool):
    """Run browser-based UI tests for a project."""
    
    logger.info(f"Running browser tests for {project}")
    
    # Find project path
    fleet_root = get_fleet_root()
    project_path = fleet_root / project
    
    if not project_path.exists():
        logger.error(f"Project '{project}' not found")
        raise click.ClickException(f"Project '{project}' not found at {project_path}")
    
    # Check if browser tests exist
    browser_test_path = project_path / 'tests' / 'browser'
    if not browser_test_path.exists():
        logger.warning(f"No browser tests found for {project}")
        logger.info("Run 'setup-browser-testing.sh' to create browser test structure")
        raise click.ClickException(f"No browser tests found at {browser_test_path}")
    
    # Load project config with enhanced handler
    browser_config = BrowserTestConfig(project)
    config = browser_config.config
    
    # Validate configuration
    validation = browser_config.validate()
    if not validation['valid']:
        for issue in validation['issues']:
            logger.warning(f"Config issue: {issue}")
    
    # Check if services need to be started
    if 'services' in config and config['services'].get('start'):
        logger.info("Starting project services...")
        start_cmd = config['services']['start']
        
        # Run in project directory
        result = subprocess.run(
            start_cmd, 
            shell=True, 
            cwd=project_path,
            capture_output=True,
            text=True
        )
        
        if result.returncode != 0:
            logger.error(f"Failed to start services: {result.stderr}")
            raise click.ClickException("Failed to start project services")
        
        # Wait for health check
        if config['services'].get('healthCheck'):
            logger.info("Waiting for services to be ready...")
            health_url = config['services']['healthCheck']
            wait_cmd = f"npx wait-on {health_url} -t 30000"
            
            subprocess.run(wait_cmd, shell=True, check=True)
    
    # Prepare test runner options
    options = {
        'browser': browser,
        'headed': headed,
        'debug': debug,
        'update_bBaseline': update_bBaselines,
        'parallel': parallel,
        'project_config': config,
        'reset_data': reset_data,
        'create_user': create_user,
        'crud_workflow': crud_workflow
    }
    
    if retries is not None:
        options['retries'] = retries
    if timeout is not None:
        options['timeout'] = timeout
    
    # Run tests based on type
    runner = BrowserTestRunner(str(fleet_root))
    
    try:
        if test_type == 'all':
            # Run all test types
            test_types = ['e2e', 'visual', 'a11y', 'performance', 'validation']
            all_results = []
            
            for t in test_types:
                logger.info(f"Running {t} tests...")
                try:
                    result = runner.run_browser_tests(project, {**options, 'type': t})
                    all_results.append(result)
                except Exception as e:
                    logger.warning(f"Failed to run {t} tests: {e}")
            
            # Aggregate results
            total_passed = sum(r.passed for r in all_results)
            total_failed = sum(r.failed for r in all_results)
            
            logger.info(f"All tests completed: {total_passed} passed, {total_failed} failed")
            
        else:
            # Run specific test type
            result = runner.run_browser_tests(project, {**options, 'type': test_type})
            
            logger.info(f"Tests completed: {result.passed} passed, {result.failed} failed")
            
            # Show artifacts if any failures
            if result.failed > 0:
                if result.screenshots:
                    logger.info(f"Screenshots saved: {', '.join(result.screenshots)}")
                if result.videos:
                    logger.info(f"Videos saved: {', '.join(result.videos)}")
                if result.traces:
                    logger.info(f"Traces saved: {', '.join(result.traces)}")
    
    finally:
        # Stop services if configured
        if 'services' in config and config['services'].get('stop'):
            logger.info("Stopping project services...")
            stop_cmd = config['services']['stop']
            subprocess.run(stop_cmd, shell=True, cwd=project_path)
    
    # Show report if requested
    if show_report:
        report_path = browser_test_path / 'results' / 'report.html'
        if report_path.exists():
            logger.info("Opening test report...")
            subprocess.run(['npx', 'playwright', 'show-report'], cwd=project_path)
        else:
            logger.warning("No test report found")
    
    # Exit with appropriate code
    if test_type == 'all':
        exit_code = 0 if all(r.failed == 0 for r in all_results) else 1
    else:
        exit_code = 0 if result.failed == 0 else 1
    
    raise SystemExit(exit_code)


@click.command()
@click.option('--project', required=True, help='Project name')
@click.option('--engine', 'engine_type',
              type=click.Choice(['rust', 'cpp', 'python', 'cuda', 'auto']),
              default='auto', help='Engine type to test')
@click.option('--releBase', is_flag=True, help='Run tests in releBase mode')
@click.option('--benchmark', is_flag=True, help='Run performance benchmarks')
@click.option('--memory-profile', is_flag=True, help='Profile memory usage')
@click.option('--coverage', is_flag=True, help='Generate code coverage')
@click.option('--threads', type=int, default=1, help='Number of test threads')
@click.option('--verbose', is_flag=True, help='Verbose output')
def engine(project: str, engine_type: str, releBase: bool,
          benchmark: bool, memory_profile: bool, coverage: bool,
          threads: int, verbose: bool):
    """Run low-level engine tests for a project."""
    
    from ...probe.engine_test_runner import EngineTestRunner
    
    logger.info(f"Running engine tests for {project}")
    
    # Auto-detect engine type if needed
    if engine_type == 'auto':
        fleet_root = get_fleet_root()
        project_path = fleet_root / project
        
        if (project_path / 'engine' / 'Cargo.toml').exists():
            engine_type = 'rust'
        elif (project_path / 'engine' / 'CMakeLists.txt').exists():
            engine_type = 'cpp'
        else:
            engine_type = 'python'
        
        logger.info(f"Auto-detected engine type: {engine_type}")
    
    # Prepare options
    options = {
        'releBase': releBase,
        'benchmark': benchmark,
        'memory_profile': memory_profile,
        'coverage': coverage,
        'threads': threads,
        'verbose': verbose
    }
    
    # Run engine tests
    runner = EngineTestRunner()
    result = runner.run_engine_tests(project, engine_type, options)
    
    # Display results
    logger.info(f"Engine tests completed: {result.passed} passed, {result.failed} failed")
    logger.info(f"Duration: {result.duration:.2f}s")
    
    if result.benchmarks:
        logger.info("Benchmark results:")
        for name, time in result.benchmarks.items():
            logger.info(f"  {name}: {time:.2f}ms")
    
    if result.memory_usage:
        logger.info(f"Peak memory usage: {result.memory_usage / 1024 / 1024:.2f} MB")
    
    if result.coverage:
        logger.info(f"Code coverage: {result.coverage:.1f}%")
    
    # Exit with appropriate code
    exit_code = 0 if result.failed == 0 else 1
    raise SystemExit(exit_code)