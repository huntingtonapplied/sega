#!/usr/bin/env python3
"""
Enhanced SEGA Engine Test Runner
=================================
Extends SEGA's engine testing with CLI entry point detection and testing.
"""

import os
import json
import asyncio
from pathlib import Path
from typing import Dict, List, Any
from dataclasses import dataclass, asdict

# Import the CLI detector
from cli_entry_detector import CLIEntryDetector, CLITestRunner

from ..utils.paths import get_fleet_root


@dataclass
class EnhancedEngineTestResult:
    """Enhanced test result including CLI testing."""
    project: str
    engine_type: str
    cli_tests_passed: int
    cli_tests_failed: int
    unit_tests_passed: int
    unit_tests_failed: int
    integration_tests_passed: int
    integration_tests_failed: int
    cli_entry_points: List[str]
    total_duration: float
    health_check_passed: bool
    service_connectivity: Dict[str, bool]


class EnhancedEngineTestRunner:
    """Extended engine test runner with CLI detection capabilities."""
    
    def __init__(self, fleet_root: str = None):
        self.fleet_root = Path(fleet_root) if fleet_root else get_fleet_root()
        self.cli_detector = CLIEntryDetector()
        self.cli_runner = CLITestRunner()
        
    async def run_comprehensive_engine_tests(self, project: str) -> EnhancedEngineTestResult:
        """Run comprehensive tests including CLI entry point testing."""
        project_path = self.fleet_root / project
        
        if not project_path.exists():
            raise ValueError(f"Project {project} not found at {project_path}")
            
        # Detect project type
        engine_type = self.detect_engine_type(project_path)
        
        # Run different test categories in parallel
        results = await asyncio.gather(
            self.run_cli_tests(project_path),
            self.run_unit_tests(project_path),
            self.run_integration_tests(project_path),
            self.run_health_checks(project_path),
            self.check_service_connectivity(project_path),
            return_exceptions=True
        )
        
        cli_results, unit_results, integration_results, health_results, connectivity = results
        
        # Process results
        cli_entry_points = []
        cli_passed = cli_failed = 0
        
        if not isinstance(cli_results, Exception):
            cli_entry_points = [str(ep.file_path) for ep in cli_results.get('entry_points', [])]
            cli_passed = cli_results.get('passed', 0)
            cli_failed = cli_results.get('failed', 0)
            
        unit_passed = unit_failed = 0
        if not isinstance(unit_results, Exception):
            unit_passed = unit_results.get('passed', 0)
            unit_failed = unit_results.get('failed', 0)
            
        integration_passed = integration_failed = 0
        if not isinstance(integration_results, Exception):
            integration_passed = integration_results.get('passed', 0)
            integration_failed = integration_results.get('failed', 0)
            
        health_passed = False if isinstance(health_results, Exception) else health_results
        service_conn = {} if isinstance(connectivity, Exception) else connectivity
        
        return EnhancedEngineTestResult(
            project=project,
            engine_type=engine_type,
            cli_tests_passed=cli_passed,
            cli_tests_failed=cli_failed,
            unit_tests_passed=unit_passed,
            unit_tests_failed=unit_failed,
            integration_tests_passed=integration_passed,
            integration_tests_failed=integration_failed,
            cli_entry_points=cli_entry_points,
            total_duration=0.0,  # Would sum individual durations
            health_check_passed=health_passed,
            service_connectivity=service_conn
        )
    
    def detect_engine_type(self, project_path: Path) -> str:
        """Detect the type of engine in the project."""
        # Check for various engine indicators
        if (project_path / "engine.py").exists():
            return "python"
        elif (project_path / "backend" / "engine.py").exists():
            return "python"
        elif (project_path / "src" / "engine.rs").exists():
            return "rust"
        elif (project_path / "engine" / "CMakeLists.txt").exists():
            return "cpp"
        elif (project_path / "engine.go").exists():
            return "go"
        else:
            # Check for CLI scripts
            cli_files = list(project_path.glob("*cli*.py"))
            if cli_files:
                return "python-cli"
            return "unknown"
    
    async def run_cli_tests(self, project_path: Path) -> Dict[str, Any]:
        """Run CLI entry point tests."""
        # Change to project directory
        original_dir = os.getcwd()
        os.chdir(project_path)
        
        try:
            # Detect CLI entry points
            self.cli_detector.project_path = project_path
            entry_points = self.cli_detector.detect_all_entry_points()
            
            if not entry_points:
                return {'entry_points': [], 'passed': 0, 'failed': 0}
            
            # Run tests on each entry point
            self.cli_runner.project_path = project_path
            results = []
            
            for ep in entry_points:
                for test_vector in ep.test_vectors:
                    result = self.cli_runner.run_test(ep, test_vector)
                    results.append(result)
                    
            # Generate report
            report = self.cli_runner.generate_report(results)
            report['entry_points'] = entry_points
            
            return report
            
        finally:
            os.chdir(original_dir)
    
    async def run_unit_tests(self, project_path: Path) -> Dict[str, Any]:
        """Run unit tests for the project."""
        # Check for test framework
        if (project_path / "pytest.ini").exists() or (project_path / "tests").exists():
            return await self.run_pytest(project_path)
        elif (project_path / "package.json").exists():
            return await self.run_npm_tests(project_path)
        else:
            return {'passed': 0, 'failed': 0}
    
    async def run_pytest(self, project_path: Path) -> Dict[str, Any]:
        """Run pytest tests."""
        try:
            result = await asyncio.create_subprocess_exec(
                'pytest', '--json-report', '--json-report-file=/tmp/pytest-report.json',
                cwd=project_path,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            
            await result.wait()
            
            # Parse report
            if Path('/tmp/pytest-report.json').exists():
                with open('/tmp/pytest-report.json') as f:
                    report = json.load(f)
                    summary = report.get('summary', {})
                    return {
                        'passed': summary.get('passed', 0),
                        'failed': summary.get('failed', 0)
                    }
        except Exception as e:
            print(f"Error running pytest: {e}")
            
        return {'passed': 0, 'failed': 0}
    
    async def run_npm_tests(self, project_path: Path) -> Dict[str, Any]:
        """Run npm tests."""
        try:
            result = await asyncio.create_subprocess_exec(
                'npm', 'test', '--', '--json',
                cwd=project_path,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            
            stdout, _ = await result.communicate()
            
            # Try to parse JSON output
            try:
                data = json.loads(stdout.decode())
                return {
                    'passed': data.get('numPassedTests', 0),
                    'failed': data.get('numFailedTests', 0)
                }
            except:
                # Fallback: check return code
                return {
                    'passed': 1 if result.returncode == 0 else 0,
                    'failed': 1 if result.returncode != 0 else 0
                }
        except Exception as e:
            print(f"Error running npm tests: {e}")
            
        return {'passed': 0, 'failed': 0}
    
    async def run_integration_tests(self, project_path: Path) -> Dict[str, Any]:
        """Run integration tests."""
        # Look for integration test markers
        integration_test_files = list(project_path.glob("**/test_integration*.py"))
        integration_test_files.extend(list(project_path.glob("**/integration_test*.py")))
        
        if integration_test_files:
            try:
                result = await asyncio.create_subprocess_exec(
                    'pytest', '-m', 'integration',
                    cwd=project_path,
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE
                )
                
                await result.wait()
                
                return {
                    'passed': 1 if result.returncode == 0 else 0,
                    'failed': 1 if result.returncode != 0 else 0
                }
            except:
                pass
                
        return {'passed': 0, 'failed': 0}
    
    async def run_health_checks(self, project_path: Path) -> bool:
        """Run health checks on the engine."""
        # Look for health check endpoints or scripts
        health_scripts = [
            project_path / "health_check.py",
            project_path / "scripts" / "health_check.sh",
            project_path / "bin" / "health"
        ]
        
        for script in health_scripts:
            if script.exists():
                try:
                    if script.suffix == '.py':
                        result = await asyncio.create_subprocess_exec(
                            'python', str(script),
                            stdout=asyncio.subprocess.PIPE,
                            stderr=asyncio.subprocess.PIPE
                        )
                    else:
                        result = await asyncio.create_subprocess_exec(
                            str(script),
                            stdout=asyncio.subprocess.PIPE,
                            stderr=asyncio.subprocess.PIPE
                        )
                    
                    await result.wait()
                    return result.returncode == 0
                except:
                    pass
                    
        # Try running the CLI with health command
        cli_files = list(project_path.glob("*cli*.py"))
        for cli_file in cli_files:
            try:
                result = await asyncio.create_subprocess_exec(
                    'python', str(cli_file), 'health',
                    cwd=project_path,
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE
                )
                
                stdout, _ = await result.communicate()
                
                # Check if output contains health info
                output = stdout.decode()
                if 'healthy' in output.lower() or 'status' in output.lower():
                    return True
            except:
                pass
                
        return False
    
    async def check_service_connectivity(self, project_path: Path) -> Dict[str, bool]:
        """Check connectivity to required services."""
        connectivity = {}
        
        # Check for configuration files
        config_files = [
            project_path / ".env",
            project_path / "config.json",
            project_path / "config.yaml"
        ]
        
        for config_file in config_files:
            if config_file.exists():
                # Parse configuration to find service endpoints
                if config_file.suffix == '.json':
                    with open(config_file) as f:
                        config = json.load(f)
                        
                    # Check database
                    if 'db_host' in config or 'database_host' in config:
                        connectivity['database'] = await self.check_port(
                            config.get('db_host', 'localhost'),
                            config.get('db_port', 5432)
                        )
                        
                    # Check Redis
                    if 'redis_host' in config:
                        connectivity['redis'] = await self.check_port(
                            config.get('redis_host', 'localhost'),
                            config.get('redis_port', 6379)
                        )
                        
        return connectivity
    
    async def check_port(self, host: str, port: int) -> bool:
        """Check if a port is open."""
        try:
            _, writer = await asyncio.wait_for(
                asyncio.open_connection(host, port),
                timeout=2.0
            )
            writer.close()
            await writer.wait_closed()
            return True
        except:
            return False
    
    def generate_comprehensive_report(self, results: List[EnhancedEngineTestResult]) -> str:
        """Generate a comprehensive test report."""
        report = []
        report.append("=" * 80)
        report.append("SEGA COMPREHENSIVE ENGINE TEST REPORT")
        report.append("=" * 80)
        
        for result in results:
            report.append(f"\nProject: {result.project}")
            report.append(f"Engine Type: {result.engine_type}")
            report.append("-" * 40)
            
            # CLI Tests
            report.append(f"CLI Tests: {result.cli_tests_passed} passed, {result.cli_tests_failed} failed")
            if result.cli_entry_points:
                report.append("  Entry Points:")
                for ep in result.cli_entry_points:
                    report.append(f"    - {Path(ep).name}")
                    
            # Unit Tests
            report.append(f"Unit Tests: {result.unit_tests_passed} passed, {result.unit_tests_failed} failed")
            
            # Integration Tests
            report.append(f"Integration Tests: {result.integration_tests_passed} passed, {result.integration_tests_failed} failed")
            
            # Health Check
            report.append(f"Health Check: {'PASSED' if result.health_check_passed else 'FAILED'}")
            
            # Service Connectivity
            if result.service_connectivity:
                report.append("Service Connectivity:")
                for service, connected in result.service_connectivity.items():
                    status = "Connected" if connected else "Not Connected"
                    report.append(f"  - {service}: {status}")
                    
        report.append("\n" + "=" * 80)
        
        # Summary
        total_cli_passed = sum(r.cli_tests_passed for r in results)
        total_cli_failed = sum(r.cli_tests_failed for r in results)
        total_unit_passed = sum(r.unit_tests_passed for r in results)
        total_unit_failed = sum(r.unit_tests_failed for r in results)
        
        report.append("SUMMARY")
        report.append("-" * 40)
        report.append(f"Total CLI Tests: {total_cli_passed} passed, {total_cli_failed} failed")
        report.append(f"Total Unit Tests: {total_unit_passed} passed, {total_unit_failed} failed")
        report.append(f"Health Checks: {sum(1 for r in results if r.health_check_passed)}/{len(results)} passed")
        
        return "\n".join(report)


async def main():
    """Main entry point for testing."""
    import argparse
    
    parser = argparse.ArgumentParser(description='Enhanced SEGA Engine Test Runner')
    parser.add_argument('projects', nargs='+', help='Projects to test')
    parser.add_argument('--fleet-root', default=str(get_fleet_root()),
                       help='FLEET root directory')
    parser.add_argument('--json', action='store_true',
                       help='Output in JSON format')
    
    args = parser.parse_args()
    
    runner = EnhancedEngineTestRunner(args.fleet_root)
    results = []
    
    for project in args.projects:
        print(f"Testing {project}...")
        try:
            result = await runner.run_comprehensive_engine_tests(project)
            results.append(result)
        except Exception as e:
            print(f"Error testing {project}: {e}")
            
    if args.json:
        # Convert to JSON-serializable format
        json_results = [asdict(r) for r in results]
        print(json.dumps(json_results, indent=2))
    else:
        report = runner.generate_comprehensive_report(results)
        print(report)


if __name__ == '__main__':
    asyncio.run(main())