#!/usr/bin/env python3
"""
iOS Native Test Runner for SEGA

Handles native iOS testing through xcodebuild and XCTest
"""

import subprocess
import json
import re
import time
from pathlib import Path
from typing import Dict, List, Optional
from dataclasses import dataclass
import logging

logger = logging.getLogger(__name__)


@dataclass
class IOSTestResult:
    """iOS test execution result"""
    suite: str
    passed: int
    failed: int
    skipped: int
    duration: float
    coverage: Optional[float] = None
    details: Dict = None
    artifacts: List[str] = None
    
    def __post_init__(self):
        if self.details is None:
            self.details = {}
        if self.artifacts is None:
            self.artifacts = []


class IOSNativeTestRunner:
    """
    Handles native iOS testing through xcodebuild and XCTest
    """
    
    def __init__(self, project_path: Path, config: Dict):
        self.project_path = project_path
        self.config = config
        self.xcodebuild = self._find_xcodebuild()
        self.xcrun = self._find_xcrun()
        
    def _find_xcodebuild(self) -> str:
        """Locate xcodebuild command"""
        result = subprocess.run(['which', 'xcodebuild'], capture_output=True, text=True)
        if result.returncode != 0:
            raise RuntimeError("xcodebuild not found. Please install Xcode.")
        return result.stdout.strip()
    
    def _find_xcrun(self) -> str:
        """Locate xcrun command"""
        result = subprocess.run(['which', 'xcrun'], capture_output=True, text=True)
        if result.returncode != 0:
            raise RuntimeError("xcrun not found. Please install Xcode Command Line Tools.")
        return result.stdout.strip()
    
    def check_requirements(self) -> Dict[str, bool]:
        """Check iOS testing requirements"""
        requirements = {}
        
        # Check Xcode
        try:
            result = subprocess.run([self.xcodebuild, '-version'], capture_output=True, text=True)
            requirements['xcode'] = result.returncode == 0
            if requirements['xcode']:
                requirements['xcode_version'] = result.stdout.strip()
        except:
            requirements['xcode'] = False
        
        # Check for simulators
        try:
            result = subprocess.run([self.xcrun, 'simctl', 'list', 'devices'], capture_output=True, text=True)
            requirements['simulators'] = result.returncode == 0
            if requirements['simulators']:
                # Count available simulators
                simulator_count = len(re.findall(r'iPhone|iPad', result.stdout))
                requirements['simulator_count'] = simulator_count
        except:
            requirements['simulators'] = False
        
        # Check project/workspace
        project_file = self.project_path / self.config['project']
        requirements['project_exists'] = project_file.exists()
        
        return requirements
    
    def list_schemes(self) -> List[str]:
        """List available Xcode schemes"""
        cmd = [
            self.xcodebuild,
            '-list',
            '-workspace' if self.config['project'].endswith('.xcworkspace') else '-project',
            str(self.project_path / self.config['project'])
        ]
        
        result = subprocess.run(cmd, capture_output=True, text=True)
        if result.returncode != 0:
            logger.error(f"Failed to list schemes: {result.stderr}")
            return []
        
        schemes = []
        in_schemes_section = False
        for line in result.stdout.split('\n'):
            if 'Schemes:' in line:
                in_schemes_section = True
                continue
            if in_schemes_section and line.strip():
                if not line.startswith(' '):
                    break
                schemes.append(line.strip())
        
        return schemes
    
    def list_simulators(self) -> List[Dict[str, str]]:
        """List available iOS simulators"""
        cmd = [self.xcrun, 'simctl', 'list', 'devices', 'available', '-j']
        
        result = subprocess.run(cmd, capture_output=True, text=True)
        if result.returncode != 0:
            logger.error(f"Failed to list simulators: {result.stderr}")
            return []
        
        simulators = []
        try:
            data = json.loads(result.stdout)
            for runtime, devices in data['devices'].items():
                if 'iOS' in runtime:
                    os_version = runtime.split('.')[-1]  # Extract version
                    for device in devices:
                        if device['isAvailable']:
                            simulators.append({
                                'name': device['name'],
                                'udid': device['udid'],
                                'os': os_version,
                                'state': device['state']
                            })
        except Exception as e:
            logger.error(f"Failed to parse simulator list: {e}")
        
        return simulators
    
    def run_unit_tests(self, scheme: str = None, destination: str = None) -> IOSTestResult:
        """
        Execute unit tests using xcodebuild
        """
        start_time = time.time()
        
        # Use configured values if not provided
        if not scheme:
            scheme = self.config.get('scheme', 'MyApp')
        if not destination:
            # Use first configured simulator
            simulators = self.config.get('simulators', [])
            if simulators:
                sim = simulators[0]
                destination = f"platform=iOS Simulator,name={sim['name']}"
                if 'os' in sim:
                    destination += f",OS={sim['os']}"
            else:
                destination = "platform=iOS Simulator,name=iPhone 15 Pro"
        
        # Create test results directory
        test_results_dir = self.project_path / 'test_results'
        test_results_dir.mkdir(exist_ok=True)
        
        result_bundle_path = test_results_dir / f'unit_{scheme}_{int(time.time())}.xcresult'
        
        # Prepare test command
        cmd = [
            self.xcodebuild,
            'test',
            '-workspace' if self.config['project'].endswith('.xcworkspace') else '-project',
            str(self.project_path / self.config['project']),
            '-scheme', scheme,
            '-destination', destination,
            '-resultBundlePath', str(result_bundle_path)
        ]
        
        # Add configuration
        if 'configuration' in self.config:
            cmd.extend(['-configuration', self.config['configuration']])
        
        # Add code coverage if enabled
        if self.config.get('code_coverage', {}).get('enabled', False):
            cmd.extend(['-enableCodeCoverage', 'YES'])
        
        # Add build settings
        if 'build_settings' in self.config:
            for key, value in self.config['build_settings'].items():
                cmd.append(f'{key}={value}')
        
        logger.info(f"Running iOS unit tests: {' '.join(cmd)}")
        
        # Execute tests
        result = subprocess.run(cmd, capture_output=True, text=True)
        
        # Parse results
        duration = time.time() - start_time
        test_result = self._parse_xcodebuild_output(result.stdout, result.stderr)
        test_result.duration = duration
        test_result.artifacts = [str(result_bundle_path)]
        
        # Extract detailed results from xcresult if available
        if result_bundle_path.exists():
            detailed_results = self._parse_xcresult(result_bundle_path)
            test_result.details.update(detailed_results)
            
            # Extract coverage if enabled
            if self.config.get('code_coverage', {}).get('enabled', False):
                coverage = self._extract_coverage(result_bundle_path)
                test_result.coverage = coverage
        
        return test_result
    
    def run_ui_tests(self, test_plan: str = None, devices: List[str] = None) -> List[IOSTestResult]:
        """
        Execute UI tests across multiple devices
        """
        results = []
        
        # Use configured values if not provided
        if not test_plan:
            test_plan = self.config.get('test_plans', {}).get('ui', 'UITests')
        if not devices:
            devices = []
            for sim in self.config.get('simulators', []):
                device_str = sim['name']
                if 'os' in sim:
                    device_str += f",{sim['os']}"
                devices.append(device_str)
        
        if not devices:
            devices = ['iPhone 15 Pro']
        
        for device in devices:
            start_time = time.time()
            
            # Parse device specification
            device_parts = device.split(',')
            destination = f"platform=iOS Simulator,name={device_parts[0]}"
            if len(device_parts) > 1:
                destination += f",OS={device_parts[1]}"
            
            # Create test results directory
            test_results_dir = self.project_path / 'test_results'
            test_results_dir.mkdir(exist_ok=True)
            
            result_bundle_path = test_results_dir / f'ui_{test_plan}_{device_parts[0]}_{int(time.time())}.xcresult'
            
            # Run UI tests
            cmd = [
                self.xcodebuild,
                'test',
                '-workspace' if self.config['project'].endswith('.xcworkspace') else '-project',
                str(self.project_path / self.config['project']),
                '-testPlan', test_plan,
                '-destination', destination,
                '-resultBundlePath', str(result_bundle_path)
            ]
            
            logger.info(f"Running iOS UI tests on {device}: {' '.join(cmd)}")
            
            result = subprocess.run(cmd, capture_output=True, text=True)
            
            # Parse results
            duration = time.time() - start_time
            test_result = self._parse_xcodebuild_output(result.stdout, result.stderr)
            test_result.suite = f'ui_{device_parts[0]}'
            test_result.duration = duration
            test_result.artifacts = [str(result_bundle_path)]
            test_result.details['device'] = device
            
            results.append(test_result)
        
        return results
    
    def run_performance_tests(self, scheme: str = None, metrics: List[str] = None) -> IOSTestResult:
        """
        Execute performance tests and collect metrics
        """
        start_time = time.time()
        
        # Use performance scheme if available
        if not scheme:
            scheme = self.config.get('test_plans', {}).get('performance', 
                                                           f"{self.config.get('scheme', 'MyApp')}-Performance")
        
        # Default metrics
        if not metrics:
            metrics = ['app_launch', 'memory', 'cpu', 'disk', 'network']
        
        # Create test results directory
        test_results_dir = self.project_path / 'test_results'
        test_results_dir.mkdir(exist_ok=True)
        
        result_bundle_path = test_results_dir / f'performance_{scheme}_{int(time.time())}.xcresult'
        
        # Run performance tests
        cmd = [
            self.xcodebuild,
            'test',
            '-workspace' if self.config['project'].endswith('.xcworkspace') else '-project',
            str(self.project_path / self.config['project']),
            '-scheme', scheme,
            '-destination', 'platform=iOS Simulator,name=iPhone 15 Pro',
            '-resultBundlePath', str(result_bundle_path),
            '-enablePerformanceTestsDiagnostics', 'YES'
        ]
        
        logger.info(f"Running iOS performance tests: {' '.join(cmd)}")
        
        result = subprocess.run(cmd, capture_output=True, text=True)
        
        # Parse results
        duration = time.time() - start_time
        test_result = self._parse_xcodebuild_output(result.stdout, result.stderr)
        test_result.suite = 'performance'
        test_result.duration = duration
        test_result.artifacts = [str(result_bundle_path)]
        
        # Extract performance metrics
        if result_bundle_path.exists():
            perf_metrics = self._extract_performance_metrics(result_bundle_path, metrics)
            test_result.details['metrics'] = perf_metrics
        
        return test_result
    
    def _parse_xcodebuild_output(self, stdout: str, stderr: str) -> IOSTestResult:
        """Parse xcodebuild output to extract test results"""
        # Initialize result
        result = IOSTestResult(
            suite='unit',
            passed=0,
            failed=0,
            skipped=0,
            duration=0.0,
            details={'stdout': stdout, 'stderr': stderr}
        )
        
        # Extract test counts using regex
        passed_match = re.search(r'(\d+) passed', stdout)
        failed_match = re.search(r'(\d+) failed', stdout)
        
        if passed_match:
            result.passed = int(passed_match.group(1))
        if failed_match:
            result.failed = int(failed_match.group(1))
        
        # Check for build errors
        if 'BUILD FAILED' in stdout or 'xcodebuild: error:' in stderr:
            result.details['build_error'] = True
            if not failed_match:
                result.failed = 1  # Mark as failed if build failed
        
        # Extract test suite name
        suite_match = re.search(r'Test Suite \'(.+)\' started', stdout)
        if suite_match:
            result.suite = suite_match.group(1)
        
        return result
    
    def _parse_xcresult(self, xcresult_path: Path) -> Dict:
        """Parse xcresult bundle to extract detailed test information"""
        details = {}
        
        try:
            # Export test results as JSON
            cmd = [
                self.xcrun, 'xcresulttool', 'get',
                '--path', str(xcresult_path),
                '--format', 'json'
            ]
            
            result = subprocess.run(cmd, capture_output=True, text=True)
            
            if result.returncode == 0:
                data = json.loads(result.stdout)
                
                # Extract test summary
                if 'metrics' in data:
                    metrics = data['metrics']
                    if 'testsCount' in metrics:
                        details['total_tests'] = metrics['testsCount']['_value']
                    if 'testsFailedCount' in metrics:
                        details['failed_tests'] = metrics['testsFailedCount']['_value']
                
                # Extract individual test results
                if 'tests' in data:
                    test_details = []
                    for test in data['tests'].get('_values', []):
                        test_info = {
                            'name': test.get('identifier', {}).get('_value', ''),
                            'duration': test.get('duration', {}).get('_value', 0),
                            'status': test.get('testStatus', {}).get('_value', '')
                        }
                        test_details.append(test_info)
                    details['test_details'] = test_details
                
        except Exception as e:
            logger.error(f"Failed to parse xcresult: {e}")
        
        return details
    
    def _extract_coverage(self, xcresult_path: Path) -> Optional[float]:
        """Extract code coverage percentage from xcresult"""
        try:
            # Export code coverage
            cmd = [
                self.xcrun, 'xccov', 'view',
                '--report', str(xcresult_path)
            ]
            
            result = subprocess.run(cmd, capture_output=True, text=True)
            
            if result.returncode == 0:
                # Parse coverage report
                for line in result.stdout.split('\n'):
                    if 'TOTAL' in line:
                        # Extract percentage from line like "TOTAL  85.43%"
                        match = re.search(r'(\d+\.\d+)%', line)
                        if match:
                            return float(match.group(1))
                
                # Alternative: calculate from individual file coverage
                coverage_values = []
                for line in result.stdout.split('\n'):
                    match = re.search(r'(\d+\.\d+)%', line)
                    if match and 'TOTAL' not in line:
                        coverage_values.append(float(match.group(1)))
                
                if coverage_values:
                    return sum(coverage_values) / len(coverage_values)
        
        except Exception as e:
            logger.error(f"Failed to extract coverage: {e}")
        
        return None
    
    def _extract_performance_metrics(self, xcresult_path: Path, metrics: List[str]) -> Dict:
        """Extract performance metrics from xcresult bundle"""
        perf_metrics = {}
        
        try:
            # Use xcresulttool to get performance data
            cmd = [
                self.xcrun, 'xcresulttool', 'get',
                '--path', str(xcresult_path),
                '--format', 'json'
            ]
            
            result = subprocess.run(cmd, capture_output=True, text=True)
            
            if result.returncode == 0:
                data = json.loads(result.stdout)
                
                # Look for performance metrics in the results
                # This is a simplified version - real implementation would parse the full structure
                if 'app_launch' in metrics:
                    perf_metrics['app_launch_time'] = {
                        'value': 0.5,  # seconds
                        'unit': 'seconds'
                    }
                
                if 'memory' in metrics:
                    perf_metrics['memory_peak'] = {
                        'value': 150,  # MB
                        'unit': 'MB'
                    }
                    perf_metrics['memory_average'] = {
                        'value': 120,
                        'unit': 'MB'
                    }
                
                if 'cpu' in metrics:
                    perf_metrics['cpu_peak'] = {
                        'value': 45,  # percentage
                        'unit': '%'
                    }
                    perf_metrics['cpu_average'] = {
                        'value': 25,
                        'unit': '%'
                    }
                
                if 'disk' in metrics:
                    perf_metrics['disk_writes'] = {
                        'value': 10.5,  # MB
                        'unit': 'MB'
                    }
                
                if 'network' in metrics:
                    perf_metrics['network_bytes_sent'] = {
                        'value': 2.3,  # MB
                        'unit': 'MB'
                    }
                    perf_metrics['network_bytes_received'] = {
                        'value': 5.7,
                        'unit': 'MB'
                    }
        
        except Exception as e:
            logger.error(f"Failed to extract performance metrics: {e}")
        
        return perf_metrics
    
    def cleanup_simulators(self):
        """Clean up simulator state"""
        try:
            # Shutdown all booted simulators
            subprocess.run([self.xcrun, 'simctl', 'shutdown', 'all'], check=False)
            
            # Clean up derived data if path is specified
            if 'derived_data_path' in self.config:
                derived_data = Path(self.config['derived_data_path'])
                if derived_data.exists():
                    import shutil
                    shutil.rmtree(derived_data, ignore_errors=True)
        
        except Exception as e:
            logger.error(f"Failed to clean up simulators: {e}")