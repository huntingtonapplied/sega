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
SEGA Unified Test Runner
========================
Orchestrates testing across all FLEET projects with dependency resolution
Based on SEGA Testing Infrastructure Strategy 2025-08-02
"""

import os
import subprocess
import yaml
from typing import Dict, List, Any, Optional
from pathlib import Path
from dataclasses import dataclass
from datetime import datetime
import json
from .build_tool_manager import BuildToolManager
from .dependency_resolver import DependencyResolver
from ..utils.paths import get_fleet_root


@dataclass
class TestResult:
    """Represents the result of a test run."""
    project: str
    success: bool
    coverage: float
    duration: float
    errors: List[str]
    warnings: List[str]


@dataclass
class TestConfiguration:
    """Test configuration for a project."""
    project_name: str
    test_commands: List[str]
    dependencies: List[str]
    coverage_threshold: float
    timeout: int
    environment: Dict[str, str]


class UnifiedTestRunner:
    """Orchestrates testing across all FLEET projects."""

    def __init__(self, fleet_root: Optional[str] = None):
        self.fleet_root = Path(fleet_root) if fleet_root else get_fleet_root()
        self.build_tool_manager = BuildToolManager()
        self.dependency_resolver = DependencyResolver()
        self.test_results: List[TestResult] = []
        self.shared_node_modules = self.fleet_root / "node_modules"
        self.progress_dir = Path("docs/progress")
        
    def run_ecosystem_tests(self, projects: Optional[List[str]] = None) -> Dict[str, Any]:
        """Run tests with dependency resolution across the ecosystem."""
        print("  Starting FLEET Ecosystem Test Suite")

        # 0. Check and restore previous progress
        self.check_previous_progress(projects)

        # 1. Start shared test infrastructure
        self.start_test_databases()
        self.setup_build_environments()
        
        # 2. Resolve dependencies
        self.resolve_frontend_conflicts()
        self.resolve_backend_conflicts()
        
        # 3. Run tests in dependency order
        test_configs = self.load_test_configurations(projects)
        ordered_configs = self.order_tests_by_dependencies(test_configs)

        results = []
        for config in ordered_configs:
            # Update progress before running test
            self.update_progress(config.project_name, "starting")
            result = self.run_project_tests(config)
            results.append(result)
            self.test_results.append(result)
            # Update progress after test completion
            self.update_progress(config.project_name, "completed", result)
            
        # 4. Generate unified report
        return self.generate_unified_report(results)
    
    def start_test_databases(self):
        """Start standardized test databases."""
        print("  Starting test databases...")
        test_env_path = self.fleet_root / "test-environments"
        
        if not test_env_path.exists():
            print("   Test environments not found, creating...")
            return
            
        try:
            subprocess.run([
                "docker-compose", "-f", 
                str(test_env_path / "docker-compose.test-base.yml"),
                "up", "-d"
            ], check=True, cwd=test_env_path)
            print("  Test databases started successfully")
        except subprocess.CalledProcessError as e:
            print(f"  Failed to start test databases: {e}")
            
    def check_previous_progress(self, projects: Optional[List[str]] = None):
        """Check and restore previous test progress."""
        progress_file = self.progress_dir / "CURRENT_DEVELOPMENT_STATUS.md"
        issues_file = Path("docs/ISSUES_TRACKER.md")

        print("\n  === Checking Previous Progress ===")

        # Check progress documentation
        if progress_file.exists():
            print(f"   Found progress at: {progress_file}")
            with open(progress_file, 'r') as f:
                lines = f.readlines()[:10]
                for line in lines:
                    if line.strip():
                        print(f"     {line.strip()}")

        # Check issue tracker
        if issues_file.exists():
            print(f"\n   Checking issues at: {issues_file}")
            with open(issues_file, 'r') as f:
                content = f.read()
                if "In Progress" in content:
                    print("     Active issues found - review before testing")

        # Check for character corruption
        self.check_for_corruption(projects)

    def check_for_corruption(self, projects: Optional[List[str]] = None):
        """Check for character corruption across projects."""
        print("\n   Checking for character corruption...")
        corruption_patterns = [
            b'\x00',  # Null bytes
            b'\xef\xbf\xbd',  # Replacement character
            b'\x1a',  # SUB character
        ]

        target_projects = projects or self.get_all_projects()
        corrupted_files = []

        for project_name in target_projects:
            project_path = self.fleet_root / project_name
            if project_path.exists():
                for file_path in project_path.rglob('*.py'):
                    try:
                        with open(file_path, 'rb') as f:
                            content = f.read()
                            for pattern in corruption_patterns:
                                if pattern in content:
                                    corrupted_files.append((project_name, file_path, pattern))
                                    break
                    except Exception:
                        pass

        if corrupted_files:
            print("\n   ⚠️  CHARACTER CORRUPTION DETECTED:")
            print("   MUST search ALL FLEET projects for similar cases")
            print("   All corruption must be fixed MANUALLY")
            for project, file_path, pattern in corrupted_files:
                print(f"     - {project}: {file_path.relative_to(self.fleet_root)}")
            self.log_corruption(corrupted_files)

    def log_corruption(self, corrupted_files: List[tuple]):
        """Log corruption detection to reports."""
        report_path = Path("docs/reports") / f"CORRUPTION_DETECTION_{datetime.now().strftime('%Y%m%d_%H%M%S')}.md"
        report_path.parent.mkdir(parents=True, exist_ok=True)

        with open(report_path, 'w') as f:
            f.write("# Character Corruption Detection Report\n")
            f.write(f"Date: {datetime.now().isoformat()}\n\n")
            f.write("## CRITICAL: Manual Fix Required\n")
            f.write("All corruption must be fixed MANUALLY across ALL FLEET projects\n\n")
            f.write("## Corrupted Files\n")
            for project, file_path, pattern in corrupted_files:
                f.write(f"- **{project}**: `{file_path.relative_to(self.fleet_root)}`\n")
            f.write("\n## Action Required\n")
            f.write("1. Search ALL FLEET projects for similar corruption\n")
            f.write("2. Fix each file manually\n")
            f.write("3. Document fixes in ISSUES_TRACKER.md\n")

    def update_progress(self, project_name: str, status: str, result: Optional[TestResult] = None):
        """Update test progress documentation."""
        self.progress_dir.mkdir(parents=True, exist_ok=True)
        progress_file = self.progress_dir / "CURRENT_DEVELOPMENT_STATUS.md"
        timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

        with open(progress_file, 'a') as f:
            if status == "starting":
                f.write(f"\n## {timestamp} - Testing {project_name}\n")
                f.write(f"- Status: Starting tests\n")
            elif status == "completed" and result:
                f.write(f"\n## {timestamp} - {project_name} Test Complete\n")
                f.write(f"- Success: {result.success}\n")
                f.write(f"- Coverage: {result.coverage:.1f}%\n")
                f.write(f"- Duration: {result.duration:.2f}s\n")
                if result.errors:
                    f.write(f"- Errors: {len(result.errors)}\n")
                if result.warnings:
                    f.write(f"- Warnings: {len(result.warnings)}\n")

    def get_all_projects(self) -> List[str]:
        """Get all FLEET projects."""
        projects = []
        for item in self.fleet_root.iterdir():
            if item.is_dir() and not item.name.startswith('.'):
                sega_yaml = item / "sega.yaml"
                if sega_yaml.exists():
                    projects.append(item.name)
        return projects

    def enforce_shared_node_modules(self, project_path: Path):
        """Ensure project uses shared node_modules."""
        frontend_paths = [
            project_path / "frontend",
            project_path / "client",
            project_path / "web",
            project_path / "app"
        ]

        for frontend_path in frontend_paths:
            if frontend_path.exists():
                package_json = frontend_path / "package.json"
                if package_json.exists():
                    # Check for local node_modules
                    local_modules = frontend_path / "node_modules"
                    if local_modules.exists():
                        print(f"\n   ⚠️  WARNING: Local node_modules detected in {frontend_path}")
                        print(f"      MUST use shared modules at {self.shared_node_modules}")
                        print("      Run: sega local up --project [name] to use shared modules")
                        return False

                    # Verify NODE_PATH is set
                    if 'NODE_PATH' not in os.environ:
                        os.environ['NODE_PATH'] = str(self.shared_node_modules)
                        print(f"   ✓ Set NODE_PATH to shared modules: {self.shared_node_modules}")
        return True

    def setup_build_environments(self):
        """Set up build environments with all required tools."""
        print("  Setting up build environments...")
        # Ensure shared node_modules exist
        if not self.shared_node_modules.exists():
            print(f"   ⚠️  Shared node_modules not found at {self.shared_node_modules}")
            print("      Run: sega local up to initialize shared modules")
        self.build_tool_manager.setup_all_tools()
        
    def resolve_frontend_conflicts(self):
        """Resolve frontend dependency conflicts."""
        print("  Resolving frontend conflicts...")
        self.dependency_resolver.resolve_frontend_conflicts()
        
    def resolve_backend_conflicts(self):
        """Resolve backend dependency conflicts."""
        print("  Resolving backend conflicts...")
        self.dependency_resolver.resolve_backend_conflicts()
        
    def load_test_configurations(self, projects: Optional[List[str]] = None) -> List[TestConfiguration]:
        """Load test configurations for specified projects."""
        configs = []
        
        if projects is None:
            # Auto-discover FLEET projects
            projects = self.discover_fleet_projects()
            
        for project in projects:
            config_path = self.fleet_root / project / ".sega" / "test-config.yml"
            if config_path.exists():
                with open(config_path, 'r') as f:
                    config_data = yaml.safe_load(f)
                    configs.append(self.parse_test_config(project, config_data))
            else:
                # Create default configuration
                configs.append(self.create_default_test_config(project))
                
        return configs
    
    def discover_fleet_projects(self) -> List[str]:
        """Discover all FLEET projects."""
        projects = []
        for item in self.fleet_root.iterdir():
            if (item.is_dir() and 
                not item.name.startswith('.') and 
                item.name not in ['docs', 'scripts', 'test-environments', 'social', 'design']):
                projects.append(item.name)
        return projects
    
    def parse_test_config(self, project: str, config_data: Dict) -> TestConfiguration:
        """Parse test configuration from YAML data."""
        test_config = config_data.get('test', {})
        
        return TestConfiguration(
            project_name=project,
            test_commands=test_config.get('commands', ['pytest', 'npm test']),
            dependencies=test_config.get('dependencies', []),
            coverage_threshold=test_config.get('coverage', {}).get('threshold', 80),
            timeout=test_config.get('timeout', 300),
            environment=test_config.get('environment', {})
        )
    
    def create_default_test_config(self, project: str) -> TestConfiguration:
        """Create default test configuration for a project."""
        project_path = self.fleet_root / project
        
        # Detect test commands based on project structure
        commands = []
        if (project_path / "pytest.ini").exists() or (project_path / "backend").exists():
            commands.append("pytest")
        if (project_path / "package.json").exists() or (project_path / "frontend").exists():
            commands.append("npm test")
            
        return TestConfiguration(
            project_name=project,
            test_commands=commands if commands else ["echo 'No tests configured'"],
            dependencies=[],
            coverage_threshold=80.0,
            timeout=300,
            environment={}
        )
    
    def order_tests_by_dependencies(self, configs: List[TestConfiguration]) -> List[TestConfiguration]:
        """Order test configurations by dependencies."""
        # Simple topological sort based on dependencies
        ordered = []
        remaining = configs.copy()
        
        while remaining:
            for config in remaining.copy():
                if all(dep in [c.project_name for c in ordered] for dep in config.dependencies):
                    ordered.append(config)
                    remaining.remove(config)
                    break
            else:
                # No progress made, add remaining without dependencies
                ordered.extend(remaining)
                break
                
        return ordered
    
    def run_project_tests(self, config: TestConfiguration) -> TestResult:
        """Run tests for a single project."""
        print(f"Testing {config.project_name}...")
        
        project_path = self.fleet_root / config.project_name
        errors = []
        warnings = []
        
        # Enforce shared node_modules
        self.enforce_shared_node_modules(project_path)

        # Set up environment
        env = os.environ.copy()
        env.update(config.environment)
        env['FLEET_TEST_MODE'] = 'true'
        env['DATABASE_URL'] = f'postgresql://test_user:test_pass@localhost:5433/fleet_test_{config.project_name}'
        env['REDIS_URL'] = 'redis://:test_pass@localhost:6380/0'
        env['NODE_PATH'] = str(self.shared_node_modules)  # Force shared node_modules
        
        success = True
        coverage = 0.0
        duration = 0.0
        
        try:
            import time
            start_time = time.time()
            
            for command in config.test_commands:
                result = subprocess.run(
                    command.split(),
                    cwd=project_path,
                    env=env,
                    timeout=config.timeout,
                    capture_output=True,
                    text=True
                )
                
                if result.returncode != 0:
                    success = False
                    errors.append(f"Command '{command}' failed: {result.stderr}")
                    
            duration = time.time() - start_time
            coverage = self.extract_coverage_info(project_path)
            
        except subprocess.TimeoutExpired:
            success = False
            errors.append(f"Tests timed out after {config.timeout} seconds")
        except Exception as e:
            success = False
            errors.append(f"Unexpected error: {str(e)}")
            
        if coverage < config.coverage_threshold:
            warnings.append(f"Coverage {coverage:.1f}% below threshold {config.coverage_threshold}%")
            
        return TestResult(
            project=config.project_name,
            success=success,
            coverage=coverage,
            duration=duration,
            errors=errors,
            warnings=warnings
        )
    
    def extract_coverage_info(self, project_path: Path) -> float:
        """Extract coverage information from test output."""
        # Try to find coverage files
        coverage_files = list(project_path.glob("**/coverage.xml")) + list(project_path.glob("**/coverage.json"))
        
        if coverage_files:
            # Parse coverage file (simplified)
            try:
                if coverage_files[0].suffix == '.xml':
                    # Parse XML coverage report
                    import xml.etree.ElementTree as ET
                    tree = ET.parse(coverage_files[0])
                    root = tree.getroot()
                    coverage_elem = root.find('.//coverage')
                    if coverage_elem is not None:
                        return float(coverage_elem.get('line-rate', 0)) * 100
                        
                elif coverage_files[0].suffix == '.json':
                    # Parse JSON coverage report
                    import json
                    with open(coverage_files[0], 'r') as f:
                        data = json.load(f)
                        if 'total' in data and 'lines' in data['total']:
                            return data['total']['lines']['pct']
            except Exception:
                pass
                
        return 0.0
    
    def generate_unified_report(self, results: List[TestResult]) -> Dict[str, Any]:
        """Generate unified test report."""
        total_projects = len(results)
        successful_projects = len([r for r in results if r.success])
        total_coverage = sum(r.coverage for r in results) / total_projects if total_projects > 0 else 0
        total_duration = sum(r.duration for r in results)
        
        report = {
            'summary': {
                'total_projects': total_projects,
                'successful_projects': successful_projects,
                'success_rate': (successful_projects / total_projects * 100) if total_projects > 0 else 0,
                'average_coverage': total_coverage,
                'total_duration': total_duration
            },
            'projects': [
                {
                    'name': r.project,
                    'success': r.success,
                    'coverage': r.coverage,
                    'duration': r.duration,
                    'errors': r.errors,
                    'warnings': r.warnings
                }
                for r in results
            ],
            'timestamp': os.popen('date -Iseconds').read().strip()
        }
        
        # Save report
        report_path = self.fleet_root / "docs" / "testing" / "unified_test_report.json"
        report_path.parent.mkdir(parents=True, exist_ok=True)
        
        import json
        with open(report_path, 'w') as f:
            json.dump(report, f, indent=2)
            
        print(f"  Test report saved to {report_path}")
        return report