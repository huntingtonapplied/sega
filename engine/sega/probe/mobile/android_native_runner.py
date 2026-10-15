#!/usr/bin/env python3
"""
Android Native Test Runner for SEGA

Handles native Android testing through Gradle and Android Test Orchestrator
"""

import subprocess
import json
import xml.etree.ElementTree as ET
import time
import os
from pathlib import Path
from typing import Dict, List, Optional
from dataclasses import dataclass
import logging
import re

logger = logging.getLogger(__name__)


@dataclass
class AndroidTestResult:
    """Android test execution result"""
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


class AndroidNativeTestRunner:
    """
    Handles native Android testing through Gradle and Android Test Orchestrator
    """
    
    def __init__(self, project_path: Path, config: Dict):
        self.project_path = project_path
        self.config = config
        self.gradle = self._find_gradle()
        self.adb = self._find_adb()
        self.android_home = self._find_android_home()
    
    def _find_gradle(self) -> str:
        """Locate gradle wrapper or gradle command"""
        # First check for gradle wrapper
        gradlew = self.project_path / 'gradlew'
        if gradlew.exists():
            # Make sure it's executable
            gradlew.chmod(0o755)
            return str(gradlew)
        
        # Fall back to system gradle
        result = subprocess.run(['which', 'gradle'], capture_output=True, text=True)
        if result.returncode != 0:
            raise RuntimeError("Gradle not found. Please install Gradle or use gradle wrapper.")
        return result.stdout.strip()
    
    def _find_adb(self) -> str:
        """Locate adb command"""
        # First try which
        result = subprocess.run(['which', 'adb'], capture_output=True, text=True)
        if result.returncode == 0:
            return result.stdout.strip()
        
        # Try Android SDK locations
        android_home = self._find_android_home()
        if android_home:
            adb_path = Path(android_home) / 'platform-tools' / 'adb'
            if adb_path.exists():
                return str(adb_path)
        
        raise RuntimeError("adb not found. Please install Android SDK and set ANDROID_HOME.")
    
    def _find_android_home(self) -> Optional[str]:
        """Find Android SDK location"""
        # Check environment variable
        android_home = os.environ.get('ANDROID_HOME')
        if android_home and Path(android_home).exists():
            return android_home
        
        # Check common locations
        common_locations = [
            Path.home() / 'Android' / 'Sdk',
            Path.home() / 'Library' / 'Android' / 'sdk',
            Path('/opt/android-sdk'),
            Path('/usr/local/android-sdk')
        ]
        
        for location in common_locations:
            if location.exists():
                return str(location)
        
        return None
    
    def check_requirements(self) -> Dict[str, bool]:
        """Check Android testing requirements"""
        requirements = {}
        
        # Check Gradle
        requirements['gradle'] = self.gradle is not None
        if requirements['gradle']:
            try:
                result = subprocess.run([self.gradle, '--version'], capture_output=True, text=True)
                if result.returncode == 0:
                    version_match = re.search(r'Gradle (\d+\.\d+)', result.stdout)
                    if version_match:
                        requirements['gradle_version'] = version_match.group(1)
            except:
                pass
        
        # Check ADB
        requirements['adb'] = self.adb is not None
        if requirements['adb']:
            try:
                result = subprocess.run([self.adb, 'version'], capture_output=True, text=True)
                if result.returncode == 0:
                    requirements['adb_version'] = result.stdout.strip()
            except:
                pass
        
        # Check Android SDK
        requirements['android_sdk'] = self.android_home is not None
        
        # Check for emulators
        if requirements['adb']:
            try:
                result = subprocess.run([self.adb, 'devices'], capture_output=True, text=True)
                devices = []
                for line in result.stdout.split('\n')[1:]:  # Skip header
                    if '\tdevice' in line or '\temulator' in line:
                        devices.append(line.split('\t')[0])
                requirements['connected_devices'] = len(devices)
                requirements['devices'] = devices
            except:
                requirements['connected_devices'] = 0
        
        # Check project structure
        build_gradle = self.project_path / 'build.gradle'
        build_gradle_kts = self.project_path / 'build.gradle.kts'
        requirements['gradle_project'] = build_gradle.exists() or build_gradle_kts.exists()
        
        # Check for app module
        app_gradle = self.project_path / self.config.get('module', 'app') / 'build.gradle'
        app_gradle_kts = self.project_path / self.config.get('module', 'app') / 'build.gradle.kts'
        requirements['app_module'] = app_gradle.exists() or app_gradle_kts.exists()
        
        return requirements
    
    def list_tasks(self) -> List[str]:
        """List available Gradle tasks"""
        cmd = [self.gradle, 'tasks', '--all']
        
        result = subprocess.run(cmd, capture_output=True, text=True, cwd=self.project_path)
        if result.returncode != 0:
            logger.error(f"Failed to list tasks: {result.stderr}")
            return []
        
        tasks = []
        for line in result.stdout.split('\n'):
            # Look for task lines (format: "taskName - Description")
            if ' - ' in line and not line.startswith(' '):
                task_name = line.split(' - ')[0].strip()
                if task_name:
                    tasks.append(task_name)
        
        return tasks
    
    def list_devices(self) -> List[Dict[str, str]]:
        """List connected devices and emulators"""
        devices = []
        
        try:
            # Get device list
            result = subprocess.run([self.adb, 'devices', '-l'], capture_output=True, text=True)
            if result.returncode != 0:
                return devices
            
            # Parse device list
            for line in result.stdout.split('\n')[1:]:  # Skip header
                if not line.strip():
                    continue
                
                parts = line.split()
                if len(parts) >= 2 and parts[1] in ['device', 'emulator']:
                    device_id = parts[0]
                    device_info = {'id': device_id, 'state': parts[1]}
                    
                    # Extract additional info
                    if 'model:' in line:
                        model_match = re.search(r'model:(\S+)', line)
                        if model_match:
                            device_info['model'] = model_match.group(1)
                    
                    if 'device:' in line:
                        device_match = re.search(r'device:(\S+)', line)
                        if device_match:
                            device_info['device'] = device_match.group(1)
                    
                    # Get Android version
                    version_cmd = [self.adb, '-s', device_id, 'shell', 'getprop', 'ro.build.version.releBase']
                    version_result = subprocess.run(version_cmd, capture_output=True, text=True)
                    if version_result.returncode == 0:
                        device_info['android_version'] = version_result.stdout.strip()
                    
                    devices.append(device_info)
        
        except Exception as e:
            logger.error(f"Failed to list devices: {e}")
        
        return devices
    
    def run_unit_tests(self, variant: str = None, module: str = None) -> AndroidTestResult:
        """
        Execute unit tests using Gradle
        """
        start_time = time.time()
        
        # Use configured values if not provided
        if not variant:
            variants = self.config.get('build_variants', ['debug'])
            variant = variants[0] if variants else 'debug'
        if not module:
            module = self.config.get('module', 'app')
        
        # Build test task name
        task_name = f"{module}:test{variant.capitalize()}UnitTest"
        
        # Build command
        cmd = [self.gradle, task_name, '--continue']
        
        # Add gradle options
        if 'gradle_options' in self.config:
            cmd.extend(self.config['gradle_options'])
        
        # Add coverage if enabled
        if self.config.get('coverage', {}).get('enabled', False):
            cmd.append(f"{module}:jacoco{variant.capitalize()}TestReport")
        
        logger.info(f"Running Android unit tests: {' '.join(cmd)}")
        
        # Execute tests
        result = subprocess.run(cmd, capture_output=True, text=True, cwd=self.project_path)
        
        # Parse test results
        duration = time.time() - start_time
        test_result = self._parse_unit_test_results(module, variant)
        test_result.duration = duration
        test_result.details['gradle_output'] = result.stdout
        test_result.details['gradle_errors'] = result.stderr
        test_result.details['return_code'] = result.returncode
        
        # Extract coverage if available
        if self.config.get('coverage', {}).get('enabled', False):
            coverage = self._extract_coverage(module, variant)
            test_result.coverage = coverage
        
        return test_result
    
    def run_instrumentation_tests(self, variant: str = None, device: str = None, 
                                 module: str = None) -> AndroidTestResult:
        """
        Execute instrumentation tests on connected device or emulator
        """
        start_time = time.time()
        
        # Use configured values if not provided
        if not variant:
            variants = self.config.get('build_variants', ['debug'])
            variant = variants[0] if variants else 'debug'
        if not module:
            module = self.config.get('module', 'app')
        
        # Ensure device is ready
        if device:
            if not self._ensure_device_ready(device):
                return AndroidTestResult(
                    suite='instrumentation',
                    passed=0,
                    failed=1,
                    skipped=0,
                    duration=0,
                    details={'error': f'Device {device} not ready'}
                )
        
        # Disable animations if requested
        animation_state = None
        if self.config.get('test_options', {}).get('animations_disabled', True):
            animation_state = self._get_animation_state(device)
            self._disable_animations(device)
        
        # Build command
        task_name = f"{module}:connected{variant.capitalize()}AndroidTest"
        cmd = [self.gradle, task_name]
        
        # Add test options
        test_options = self.config.get('test_options', {})
        
        if test_options.get('orchestrator', False):
            cmd.extend([
                '-Pandroid.testInstrumentationRunnerArguments.clearPackageData=true',
                '-Pandroid.testInstrumentationRunnerArguments.useTestStorageService=true'
            ])
        
        if test_options.get('clear_package_data', True):
            cmd.append('-Pandroid.testInstrumentationRunnerArguments.clearPackageData=true')
        
        # Add instrumentation args
        if 'instrumentation_args' in test_options:
            for key, value in test_options['instrumentation_args'].items():
                cmd.append(f'-Pandroid.testInstrumentationRunnerArguments.{key}={value}')
        
        # Specify device if provided
        if device:
            # Set ANDROID_SERIAL environment variable
            env = os.environ.copy()
            env['ANDROID_SERIAL'] = device
        else:
            env = None
        
        logger.info(f"Running Android instrumentation tests: {' '.join(cmd)}")
        
        # Execute tests
        result = subprocess.run(cmd, capture_output=True, text=True, cwd=self.project_path, env=env)
        
        # Re-enable animations if we disabled them
        if animation_state is not None:
            self._restore_animation_state(device, animation_state)
        
        # Parse test results
        duration = time.time() - start_time
        test_result = self._parse_instrumentation_results(module, variant)
        test_result.duration = duration
        test_result.details['gradle_output'] = result.stdout
        test_result.details['gradle_errors'] = result.stderr
        test_result.details['return_code'] = result.returncode
        if device:
            test_result.details['device'] = device
        
        return test_result
    
    def run_performance_tests(self, scenarios: List[str] = None, device: str = None) -> AndroidTestResult:
        """
        Execute performance tests using Macrobenchmark
        """
        start_time = time.time()
        
        # Default scenarios
        if not scenarios:
            scenarios = ['startup', 'scrolling', 'navigation']
        
        # Check if benchmark module exists
        benchmark_module = 'benchmark'
        benchmark_build = self.project_path / benchmark_module / 'build.gradle'
        if not benchmark_build.exists():
            benchmark_build = self.project_path / benchmark_module / 'build.gradle.kts'
        
        if not benchmark_build.exists():
            return AndroidTestResult(
                suite='performance',
                passed=0,
                failed=1,
                skipped=0,
                duration=0,
                details={'error': 'Benchmark module not found'}
            )
        
        # Build and install the app and benchmark APKs
        build_cmd = [
            self.gradle,
            f'{benchmark_module}:assembleBenchmark',
            f'{benchmark_module}:assembleBenchmarkAndroidTest'
        ]
        
        build_result = subprocess.run(build_cmd, capture_output=True, text=True, cwd=self.project_path)
        
        if build_result.returncode != 0:
            return AndroidTestResult(
                suite='performance',
                passed=0,
                failed=1,
                skipped=0,
                duration=time.time() - start_time,
                details={'error': 'Failed to build benchmark APKs', 'output': build_result.stderr}
            )
        
        # Run benchmark tests
        test_cmd = [self.gradle, f'{benchmark_module}:connectedBenchmarkAndroidTest']
        
        # Specify device if provided
        env = None
        if device:
            env = os.environ.copy()
            env['ANDROID_SERIAL'] = device
        
        logger.info(f"Running Android performance tests: {' '.join(test_cmd)}")
        
        result = subprocess.run(test_cmd, capture_output=True, text=True, cwd=self.project_path, env=env)
        
        # Parse benchmark results
        duration = time.time() - start_time
        test_result = self._parse_benchmark_results(benchmark_module)
        test_result.duration = duration
        test_result.details['gradle_output'] = result.stdout
        test_result.details['gradle_errors'] = result.stderr
        test_result.details['return_code'] = result.returncode
        
        return test_result
    
    def _ensure_device_ready(self, device: str) -> bool:
        """Ensure specified device/emulator is ready"""
        # Check if device is already connected
        result = subprocess.run([self.adb, 'devices'], capture_output=True, text=True)
        
        if device in result.stdout:
            # Device is connected, wait for it to be ready
            wait_cmd = [self.adb, '-s', device, 'wait-for-device']
            subprocess.run(wait_cmd, timeout=30)
            
            # Check if device is fully booted
            boot_cmd = [self.adb, '-s', device, 'shell', 'getprop', 'sys.boot_completed']
            for _ in range(60):  # Wait up to 60 seconds
                boot_result = subprocess.run(boot_cmd, capture_output=True, text=True)
                if boot_result.stdout.strip() == '1':
                    return True
                time.sleep(1)
        
        # Try to start emulator if it's an AVD
        emulators = self.config.get('emulators', [])
        for emu in emulators:
            if emu.get('name') == device:
                return self._start_emulator(emu)
        
        return False
    
    def _start_emulator(self, emulator_config: Dict) -> bool:
        """Start an Android emulator"""
        try:
            emulator_cmd = ['emulator', '-avd', emulator_config['name']]
            
            # Add common flags
            emulator_cmd.extend(['-no-audio', '-no-boot-anim'])
            
            # Start emulator in background
            subprocess.Popen(emulator_cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            
            # Wait for emulator to be ready
            time.sleep(5)  # Initial wait
            
            # Wait for device to appear
            for _ in range(120):  # Wait up to 2 minutes
                result = subprocess.run([self.adb, 'devices'], capture_output=True, text=True)
                if 'emulator' in result.stdout:
                    # Get emulator serial
                    for line in result.stdout.split('\n'):
                        if 'emulator' in line and '\tdevice' in line:
                            emulator_serial = line.split('\t')[0]
                            
                            # Wait for boot completion
                            boot_cmd = [self.adb, '-s', emulator_serial, 'shell', 'getprop', 'sys.boot_completed']
                            for _ in range(60):
                                boot_result = subprocess.run(boot_cmd, capture_output=True, text=True)
                                if boot_result.stdout.strip() == '1':
                                    return True
                                time.sleep(1)
                
                time.sleep(1)
        
        except Exception as e:
            logger.error(f"Failed to start emulator: {e}")
        
        return False
    
    def _get_animation_state(self, device: Optional[str] = None) -> Dict[str, str]:
        """Get current animation scale settings"""
        adb_prefix = [self.adb]
        if device:
            adb_prefix.extend(['-s', device])
        
        state = {}
        animation_scales = [
            'window_animation_scale',
            'transition_animation_scale',
            'animator_duration_scale'
        ]
        
        for scale in animation_scales:
            cmd = adb_prefix + ['shell', 'settings', 'get', 'global', scale]
            result = subprocess.run(cmd, capture_output=True, text=True)
            if result.returncode == 0:
                state[scale] = result.stdout.strip()
        
        return state
    
    def _disable_animations(self, device: Optional[str] = None):
        """Disable animations for testing"""
        adb_prefix = [self.adb]
        if device:
            adb_prefix.extend(['-s', device])
        
        animation_scales = [
            'window_animation_scale',
            'transition_animation_scale',
            'animator_duration_scale'
        ]
        
        for scale in animation_scales:
            cmd = adb_prefix + ['shell', 'settings', 'put', 'global', scale, '0']
            subprocess.run(cmd)
    
    def _restore_animation_state(self, device: Optional[str], state: Dict[str, str]):
        """Restore animation settings"""
        adb_prefix = [self.adb]
        if device:
            adb_prefix.extend(['-s', device])
        
        for scale, value in state.items():
            cmd = adb_prefix + ['shell', 'settings', 'put', 'global', scale, value]
            subprocess.run(cmd)
    
    def _parse_unit_test_results(self, module: str, variant: str) -> AndroidTestResult:
        """Parse JUnit XML test results from unit tests"""
        test_results_dir = self.project_path / module / 'build' / 'test-results' / f'test{variant.capitalize()}UnitTest'
        
        total_passed = 0
        total_failed = 0
        total_skipped = 0
        test_details = []
        artifacts = []
        
        if test_results_dir.exists():
            artifacts.append(str(test_results_dir))
            
            # Parse all XML files in results directory
            for xml_file in test_results_dir.glob('*.xml'):
                try:
                    tree = ET.parse(xml_file)
                    root = tree.getroot()
                    
                    # Handle both testsuite as root and testsuites as root
                    if root.tag == 'testsuites':
                        testsuites = root.findall('testsuite')
                    else:
                        testsuites = [root]
                    
                    for testsuite in testsuites:
                        tests = int(testsuite.get('tests', 0))
                        failures = int(testsuite.get('failures', 0))
                        errors = int(testsuite.get('errors', 0))
                        skipped = int(testsuite.get('skipped', 0))
                        
                        total_passed += tests - failures - errors - skipped
                        total_failed += failures + errors
                        total_skipped += skipped
                        
                        # Extract individual test cBases
                        for testcBase in testsuite.findall('testcBase'):
                            test_info = {
                                'name': testcBase.get('name'),
                                'classname': testcBase.get('classname'),
                                'time': float(testcBase.get('time', 0))
                            }
                            
                            # Check for failure or error
                            failure = testcBase.find('failure')
                            error = testcBase.find('error')
                            if failure is not None:
                                test_info['status'] = 'failed'
                                test_info['failure_message'] = failure.get('message', '')
                            elif error is not None:
                                test_info['status'] = 'error'
                                test_info['error_message'] = error.get('message', '')
                            elif testcBase.find('skipped') is not None:
                                test_info['status'] = 'skipped'
                            else:
                                test_info['status'] = 'passed'
                            
                            test_details.append(test_info)
                
                except Exception as e:
                    logger.error(f"Failed to parse XML file {xml_file}: {e}")
        
        return AndroidTestResult(
            suite=f'unit_{variant}',
            passed=total_passed,
            failed=total_failed,
            skipped=total_skipped,
            duration=0.0,
            details={'test_details': test_details, 'variant': variant},
            artifacts=artifacts
        )
    
    def _parse_instrumentation_results(self, module: str, variant: str) -> AndroidTestResult:
        """Parse instrumentation test results"""
        # Results are typically in connected test output directory
        test_results_dir = self.project_path / module / 'build' / 'outputs' / 'androidTest-results' / f'connected{variant.capitalize()}AndroidTest'
        
        # If that doesn't exist, try the alternative location
        if not test_results_dir.exists():
            test_results_dir = self.project_path / module / 'build' / 'outputs' / 'connected_android_test_additional_output'
        
        # Parse results similar to unit tests
        if test_results_dir.exists():
            # Look for XML files
            xml_files = list(test_results_dir.glob('**/*.xml'))
            if xml_files:
                # Parse the XML files
                return self._parse_unit_test_results(module, variant)
        
        # If no XML results, create a basic result
        return AndroidTestResult(
            suite=f'instrumentation_{variant}',
            passed=0,
            failed=0,
            skipped=0,
            duration=0.0,
            details={'variant': variant},
            artifacts=[str(test_results_dir)] if test_results_dir.exists() else []
        )
    
    def _parse_benchmark_results(self, module: str) -> AndroidTestResult:
        """Parse Macrobenchmark results"""
        benchmark_dir = self.project_path / module / 'build' / 'outputs' / 'connected_android_test_additional_output'
        
        metrics = {}
        artifacts = []
        test_count = 0
        
        if benchmark_dir.exists():
            artifacts.append(str(benchmark_dir))
            
            # Look for JSON result files
            for json_file in benchmark_dir.glob('**/*-benchmarkData.json'):
                try:
                    with open(json_file) as f:
                        data = json.load(f)
                    
                    # Extract benchmark metrics
                    if 'benchmarks' in data:
                        for benchmark in data['benchmarks']:
                            name = benchmark.get('name', 'unknown')
                            test_count += 1
                            
                            metrics[name] = {
                                'className': benchmark.get('className'),
                                'metrics': {}
                            }
                            
                            # Extract metric values
                            if 'metrics' in benchmark:
                                for metric_name, metric_data in benchmark['metrics'].items():
                                    if isinstance(metric_data, dict):
                                        metrics[name]['metrics'][metric_name] = {
                                            'median': metric_data.get('median'),
                                            'min': metric_data.get('min'),
                                            'max': metric_data.get('max'),
                                            'p90': metric_data.get('p90'),
                                            'p95': metric_data.get('p95'),
                                            'p99': metric_data.get('p99')
                                        }
                
                except Exception as e:
                    logger.error(f"Failed to parse benchmark JSON {json_file}: {e}")
        
        return AndroidTestResult(
            suite='performance',
            passed=test_count,
            failed=0,
            skipped=0,
            duration=0.0,
            details={'metrics': metrics},
            artifacts=artifacts
        )
    
    def _extract_coverage(self, module: str, variant: str) -> Optional[float]:
        """Extract code coverage percentage"""
        # Look for JaCoCo coverage report
        coverage_file = self.project_path / module / 'build' / 'reports' / 'coverage' / f'{variant}' / 'index.html'
        
        if not coverage_file.exists():
            # Try alternative location
            coverage_file = self.project_path / module / 'build' / 'reports' / 'jacoco' / f'test{variant.capitalize()}UnitTestCoverage' / 'html' / 'index.html'
        
        if coverage_file.exists():
            try:
                with open(coverage_file, 'r') as f:
                    content = f.read()
                
                # Extract coverage percentage from HTML
                # Look for pattern like "Total</td><td class="bar">95%</td>"
                match = re.search(r'Total.*?(\d+)%', content, re.DOTALL)
                if match:
                    return float(match.group(1))
            
            except Exception as e:
                logger.error(f"Failed to extract coverage: {e}")
        
        return None
    
    def cleanup(self):
        """Clean up test artifacts and resources"""
        try:
            # Kill any remaining emulators
            subprocess.run(['adb', 'emu', 'kill'], capture_output=True)
            
            # Clean gradle build cache if requested
            if self.config.get('clean_build_cache', False):
                subprocess.run([self.gradle, 'clean'], cwd=self.project_path)
        
        except Exception as e:
            logger.error(f"Failed to clean up: {e}")