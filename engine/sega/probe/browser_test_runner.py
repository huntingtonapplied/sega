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
SEGA Browser Test Runner
========================
Orchestrates browser-based UI testing using Playwright
"""

import os
import json
import subprocess
import time
import requests
import yaml
from pathlib import Path
from typing import Dict, List, Any, Optional
from dataclasses import dataclass, field
from datetime import datetime
from ..utils.paths import get_fleet_root

@dataclass
class BrowserTestResult:
    """Result of browser test execution."""
    project: str
    test_type: str
    passed: int
    failed: int
    skipped: int
    duration: float
    screenshots: List[str]
    videos: List[str]
    traces: List[str]
    console_errors: List[str] = field(default_factory=list)
    network_logs: List[str] = field(default_factory=list)
    validation_results: Dict[str, Any] = field(default_factory=dict)
    error_report_path: Optional[str] = None

class BrowserTestRunner:
    """Orchestrates browser-based UI testing across FLEET projects."""
    
    def __init__(self, fleet_root: Optional[str] = None):
        self.fleet_root = Path(fleet_root) if fleet_root else get_fleet_root()
        self.test_env_path = self.fleet_root / "test-environments" / "browser"
        self.console_errors = []
        self.network_logs = []
        
    def run_browser_tests(self, project: str, options: Dict[str, Any]) -> BrowserTestResult:
        """Run browser tests for a specific project."""
        test_type = options.get('type', 'e2e')
        
        test_runners = {
            'e2e': self.run_e2e_tests,
            'visual': self.run_visual_regression,
            'accessibility': self.run_accessibility_tests,
            'a11y': self.run_accessibility_tests,
            'performance': self.run_performance_tests,
            'validation': self.run_validation_tests,
        }
        
        if test_type not in test_runners:
            raise ValueError(f"Unknown test type: {test_type}")
            
        return test_runners[test_type](project, options)
    
    def run_e2e_tests(self, project: str, options: Dict[str, Any]) -> BrowserTestResult:
        """Run end-to-end browser tests."""
        project_path = self.fleet_root / project
        test_dir = project_path / "tests" / "browser" / "e2e"
        
        if not test_dir.exists():
            print(f"No E2E tests found for {project}")
            return self._empty_result(project, "e2e")
        
        # Run Playwright tests
        env = os.environ.copy()
        env['BASE_URL'] = f"http://localhost:{self._get_project_port(project)}"
        env['PROJECT_NAME'] = project
        
        cmd = [
            "npx", "playwright", "test",
            "--config", str(self.test_env_path / "playwright.config.ts"),
            "--project", options.get('browser', 'chromium'),
            str(test_dir)
        ]
        
        if options.get('headed', False):
            cmd.append('--headed')
            
        if options.get('debug', False):
            cmd.append('--debug')
            
        result = subprocess.run(cmd, env=env, capture_output=True, text=True)
        
        return self._parse_playwright_results(project, "e2e", result)
    
    def run_visual_regression(self, project: str, options: Dict[str, Any]) -> BrowserTestResult:
        """Run visual regression tests."""
        project_path = self.fleet_root / project
        test_dir = project_path / "tests" / "browser" / "visual"
        
        if not test_dir.exists():
            print(f"No visual tests found for {project}")
            return self._empty_result(project, "visual")
        
        cmd = [
            "npx", "playwright", "test",
            "--config", str(self.test_env_path / "playwright.config.ts"),
            "--project", "chromium",  # Visual tests typically run on one browser
            "--update-snapshots" if options.get('update_bBaseline', False) else "",
            str(test_dir)
        ]
        
        result = subprocess.run([c for c in cmd if c], capture_output=True, text=True)
        
        return self._parse_playwright_results(project, "visual", result)
    
    def run_accessibility_tests(self, project: str, options: Dict[str, Any]) -> BrowserTestResult:
        """Run accessibility tests using axe-core."""
        project_path = self.fleet_root / project
        test_dir = project_path / "tests" / "browser" / "accessibility"
        
        if not test_dir.exists():
            # Run default accessibility scan
            return self._run_default_a11y_scan(project)
        
        cmd = [
            "npx", "playwright", "test",
            "--config", str(self.test_env_path / "playwright.config.ts"),
            str(test_dir)
        ]
        
        result = subprocess.run(cmd, capture_output=True, text=True)
        
        return self._parse_playwright_results(project, "accessibility", result)
    
    def run_performance_tests(self, project: str, options: Dict[str, Any]) -> BrowserTestResult:
        """Run performance tests using Lighthouse."""
        # Implementation would integrate Lighthouse or similar tools
        print(f"Running performance tests for {project}")
        
        # Placeholder for Lighthouse integration
        cmd = [
            "npx", "lighthouse",
            f"http://localhost:{self._get_project_port(project)}",
            "--output", "json",
            "--output-path", f"/tmp/{project}-lighthouse.json",
            "--chrome-flags='--headless'"
        ]
        
        result = subprocess.run(cmd, capture_output=True, text=True)
        
        # Parse Lighthouse results
        return self._parse_lighthouse_results(project, result)
    
    def run_validation_tests(self, project: str, options: Dict[str, Any]) -> BrowserTestResult:
        """Run comprehensive 3-tier validation tests."""
        print(f"Running validation tests for {project}")
        
        project_path = self.fleet_root / project
        config = options.get('project_config', {})
        
        # Handle data management options
        if options.get('reset_data'):
            self._reset_test_data(project, config)
            
        if options.get('create_user'):
            self._create_test_user(project, config)
        
        # Run 3-tier validation
        validation_results = {}
        total_passed = 0
        total_failed = 0
        start_time = time.time()
        
        # Tier 1: Static Validation
        static_result = self._run_static_validation(project, options)
        validation_results['static'] = static_result
        total_passed += static_result['passed']
        total_failed += static_result['failed']
        
        # Tier 2: Dynamic Validation (only if static passes)
        if static_result['passed'] > 0:
            dynamic_result = self._run_dynamic_validation(project, options)
            validation_results['dynamic'] = dynamic_result
            total_passed += dynamic_result['passed']
            total_failed += dynamic_result['failed']
            
            # Tier 3: Integration Validation (only if dynamic passes)
            if dynamic_result['passed'] > 0:
                integration_result = self._run_integration_validation(project, options)
                validation_results['integration'] = integration_result
                total_passed += integration_result['passed']
                total_failed += integration_result['failed']
        
        duration = time.time() - start_time
        
        # Generate error documentation
        error_report_path = self._generate_error_report(project, validation_results)
        
        return BrowserTestResult(
            project=project,
            test_type="validation",
            passed=total_passed,
            failed=total_failed,
            skipped=0,
            duration=duration,
            screenshots=[],
            videos=[],
            traces=[],
            console_errors=self.console_errors,
            network_logs=self.network_logs,
            validation_results=validation_results,
            error_report_path=error_report_path
        )
    
    def _get_project_port(self, project: str) -> int:
        """Get the frontend port for a project.

        Legacy browser-test port overrides are curated per-fleet data sourced
        from the `[fleet.browser_test_ports]` config map (ships empty).
        """
        from ..core.config import get_config
        project_ports = get_config().fleet.browser_test_ports
        return project_ports.get(project, 3000)
    
    def _parse_playwright_results(self, project: str, test_type: str, 
                                 result: subprocess.CompletedProcess) -> BrowserTestResult:
        """Parse Playwright test results."""
        # Parse the JSON reporter output
        report_path = self.test_env_path / "test-results" / "browser-tests.json"
        
        if report_path.exists():
            with open(report_path, 'r') as f:
                report = json.load(f)
                
            passed = sum(1 for t in report['tests'] if t['outcome'] == 'passed')
            failed = sum(1 for t in report['tests'] if t['outcome'] == 'failed')
            skipped = sum(1 for t in report['tests'] if t['outcome'] == 'skipped')
            duration = report.get('duration', 0) / 1000.0  # Convert to seconds
            
            # Collect artifacts
            artifacts_dir = self.test_env_path / "test-results"
            screenshots = list(artifacts_dir.glob("**/*.png"))
            videos = list(artifacts_dir.glob("**/*.webm"))
            traces = list(artifacts_dir.glob("**/*.zip"))
            
            return BrowserTestResult(
                project=project,
                test_type=test_type,
                passed=passed,
                failed=failed,
                skipped=skipped,
                duration=duration,
                screenshots=[str(s) for s in screenshots],
                videos=[str(v) for v in videos],
                traces=[str(t) for t in traces]
            )
        else:
            # Fallback parsing from stdout
            lines = result.stdout.split('\n')
            passed = failed = skipped = 0
            
            for line in lines:
                if 'passed' in line:
                    passed = int(line.split()[0])
                elif 'failed' in line:
                    failed = int(line.split()[0])
                elif 'skipped' in line:
                    skipped = int(line.split()[0])
                    
            return BrowserTestResult(
                project=project,
                test_type=test_type,
                passed=passed,
                failed=failed,
                skipped=skipped,
                duration=0.0,
                screenshots=[],
                videos=[],
                traces=[]
            )
    
    def _empty_result(self, project: str, test_type: str) -> BrowserTestResult:
        """Return empty test result."""
        return BrowserTestResult(
            project=project,
            test_type=test_type,
            passed=0,
            failed=0,
            skipped=0,
            duration=0.0,
            screenshots=[],
            videos=[],
            traces=[]
        )
    
    def _run_default_a11y_scan(self, project: str) -> BrowserTestResult:
        """Run default accessibility scan on project homepage."""
        # This would run a basic axe-core scan
        print(f"Running default accessibility scan for {project}")
        return self._empty_result(project, "accessibility")
    
    def _parse_lighthouse_results(self, project: str, 
                                 result: subprocess.CompletedProcess) -> BrowserTestResult:
        """Parse Lighthouse performance results."""
        report_path = f"/tmp/{project}-lighthouse.json"
        
        if Path(report_path).exists():
            with open(report_path, 'r') as f:
                report = json.load(f)
                
            # Extract key metrics
            performance_score = report['categories']['performance']['score']
            
            # Consider test passed if performance score > 0.8
            passed = 1 if performance_score > 0.8 else 0
            failed = 1 - passed
            
            return BrowserTestResult(
                project=project,
                test_type="performance",
                passed=passed,
                failed=failed,
                skipped=0,
                duration=report.get('timing', {}).get('total', 0) / 1000.0,
                screenshots=[],
                videos=[],
                traces=[]
            )
        else:
            return self._empty_result(project, "performance")
    
    def _reset_test_data(self, project: str, config: Dict[str, Any]):
        """Reset test data for a project."""
        print(f"Resetting test data for {project}")
        
        test_data_config = config.get('testData', {})
        reset_command = test_data_config.get('resetCommand')
        
        if reset_command:
            try:
                result = subprocess.run(reset_command, shell=True, capture_output=True, text=True)
                if result.returncode != 0:
                    print(f"Warning: Reset command failed: {result.stderr}")
            except Exception as e:
                print(f"Error resetting test data: {e}")
    
    def _create_test_user(self, project: str, config: Dict[str, Any]):
        """Create a test user via API."""
        print(f"Creating test user for {project}")

        test_data_config = config.get('testData', {})
        api_base_url = test_data_config.get('apiBaseUrl', 'http://localhost:3001/api')
        auth_config = config.get('authentication', {})
        test_user = auth_config.get('testUser', {})
        
        # Try to create a test user
        try:
            user_data = {
                "email": test_user.get('email', 'test@example.com'),
                "password": test_user.get('password', 'testpassword123'),
                "name": "Test User"
            }
            
            response = requests.post(f"{api_base_url}/users", json=user_data)
            if response.status_code in [200, 201]:
                print("Test user created successfully")
            else:
                print(f"Warning: Could not create test user: {response.status_code}")
        except Exception as e:
            print(f"Error creating test user: {e}")
    
    def _run_static_validation(self, project: str, options: Dict[str, Any]) -> Dict[str, Any]:
        """Run Tier 1: Static validation tests."""
        print("Running Tier 1: Static validation")
        
        config = options.get('project_config', {})
        services_config = config.get('services', {})
        health_check_url = services_config.get('healthCheck', 'http://localhost:3001/health')
        
        # Extract base URL from health check URL
        import re
        base_url_match = re.match(r'(https?://[^/]+)', health_check_url)
        base_url = base_url_match.group(1) if base_url_match else 'http://localhost:3001'
        
        results = {
            'passed': 0,
            'failed': 0,
            'tests': []
        }
        
        # Test 1: App starts without crashes
        try:
            response = requests.get(health_check_url, timeout=30)
            if response.status_code == 200:
                results['passed'] += 1
                results['tests'].append({
                    'test': 'App starts without crashes',
                    'status': 'passed'
                })
            else:
                results['failed'] += 1
                results['tests'].append({
                    'test': 'App starts without crashes',
                    'status': 'failed',
                    'error': f'HTTP {response.status_code}'
                })
        except Exception as e:
            results['failed'] += 1
            results['tests'].append({
                'test': 'App starts without crashes',
                'status': 'failed',
                'error': str(e)
            })
        
        # Test 2: Frontend renders without JavaScript errors
        try:
            cmd = [
                "npx", "playwright", "test",
                "--config", str(self.test_env_path / "static-validation.config.ts"),
                "--project", "chromium"
            ]
            
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=60)
            
            if result.returncode == 0:
                results['passed'] += 1
                results['tests'].append({
                    'test': 'Frontend renders without JavaScript errors',
                    'status': 'passed'
                })
            else:
                results['failed'] += 1
                results['tests'].append({
                    'test': 'Frontend renders without JavaScript errors',
                    'status': 'failed',
                    'error': result.stderr or result.stdout
                })
        except Exception as e:
            results['failed'] += 1
            results['tests'].append({
                'test': 'Frontend renders without JavaScript errors',
                'status': 'failed',
                'error': str(e)
            })
        
        return results
    
    def _run_dynamic_validation(self, project: str, options: Dict[str, Any]) -> Dict[str, Any]:
        """Run Tier 2: Dynamic validation tests (API + UI)."""
        print("Running Tier 2: Dynamic validation")
        
        config = options.get('project_config', {})
        test_data_config = config.get('testData', {})
        api_base_url = test_data_config.get('apiBaseUrl', 'http://localhost:3001/api')
        
        # Extract base URL for UI testing
        import re
        base_url_match = re.match(r'(https?://[^/]+)', api_base_url)
        base_url = base_url_match.group(1) if base_url_match else 'http://localhost:3001'
        
        results = {
            'passed': 0,
            'failed': 0,
            'tests': []
        }
        
        # Test 1: Create record via API, verify in UI
        try:
            # Create test entity via API
            test_entity = {
                "name": f"Test Entity {int(time.time())}",
                "description": "Created via automated test"
            }
            
            response = requests.post(f"{api_base_url}/entities", json=test_entity)
            
            if response.status_code in [200, 201]:
                entity_id = response.json().get('id')
                
                # Now verify it appears in UI using Playwright
                cmd = [
                    "npx", "playwright", "test",
                    "--config", str(self.test_env_path / "dynamic-validation.config.ts"),
                    "--project", "chromium",
                    "--grep", "verify-created-entity"
                ]
                
                env = os.environ.copy()
                env['TEST_ENTITY_ID'] = str(entity_id)
                env['BASE_URL'] = base_url
                
                result = subprocess.run(cmd, env=env, capture_output=True, text=True, timeout=60)
                
                if result.returncode == 0:
                    results['passed'] += 1
                    results['tests'].append({
                        'test': 'Create record via API, verify in UI',
                        'status': 'passed'
                    })
                else:
                    results['failed'] += 1
                    results['tests'].append({
                        'test': 'Create record via API, verify in UI',
                        'status': 'failed',
                        'error': 'UI verification failed'
                    })
            else:
                results['failed'] += 1
                results['tests'].append({
                    'test': 'Create record via API, verify in UI',
                    'status': 'failed',
                    'error': f'API creation failed: {response.status_code}'
                })
                
        except Exception as e:
            results['failed'] += 1
            results['tests'].append({
                'test': 'Create record via API, verify in UI',
                'status': 'failed',
                'error': str(e)
            })
        
        return results
    
    def _run_integration_validation(self, project: str, options: Dict[str, Any]) -> Dict[str, Any]:
        """Run Tier 3: Integration validation tests."""
        print("Running Tier 3: Integration validation")
        
        config = options.get('project_config', {})
        
        results = {
            'passed': 0,
            'failed': 0,
            'tests': []
        }
        
        # Test 1: Authentication flow
        try:
            cmd = [
                "npx", "playwright", "test",
                "--config", str(self.test_env_path / "integration-validation.config.ts"),
                "--project", "chromium",
                "--grep", "authentication-flow"
            ]
            
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
            
            if result.returncode == 0:
                results['passed'] += 1
                results['tests'].append({
                    'test': 'Authentication flow',
                    'status': 'passed'
                })
            else:
                results['failed'] += 1
                results['tests'].append({
                    'test': 'Authentication flow',
                    'status': 'failed',
                    'error': result.stderr or result.stdout
                })
                
        except Exception as e:
            results['failed'] += 1
            results['tests'].append({
                'test': 'Authentication flow',
                'status': 'failed',
                'error': str(e)
            })
        
        return results
    
    def _generate_error_report(self, project: str, validation_results: Dict[str, Any]) -> str:
        """Generate comprehensive error documentation."""
        timestamp = datetime.now().isoformat()
        report_path = self.test_env_path / "results" / f"{project}-validation-{timestamp}.yaml"
        
        # Ensure results directory exists
        report_path.parent.mkdir(parents=True, exist_ok=True)
        
        error_report = {
            'validation_results': {
                'project': project,
                'timestamp': timestamp,
                'environment': 'shared',  # Could be configured
                'static_validation': validation_results.get('static', {}),
                'dynamic_validation': validation_results.get('dynamic', {}),
                'integration_validation': validation_results.get('integration', {}),
                'console_errors': self.console_errors,
                'network_logs': self.network_logs
            }
        }
        
        with open(report_path, 'w') as f:
            yaml.dump(error_report, f, default_flow_style=False)
        
        print(f"Error report generated: {report_path}")
        return str(report_path)