#!/usr/bin/env python3
"""
Mobile Test Orchestrator for SEGA

Coordinates testing across iOS and Android platforms
"""

import json
import yaml
import time
from pathlib import Path
from typing import Dict, List, Optional
from dataclasses import dataclass, asdict
import logging
import concurrent.futures
from datetime import datetime

from .ios_native_runner import IOSNativeTestRunner, IOSTestResult
from .android_native_runner import AndroidNativeTestRunner, AndroidTestResult
from .device_manager import DeviceManager

logger = logging.getLogger(__name__)


@dataclass
class MobileTestReport:
    """Unified mobile test report"""
    timestamp: str
    total_duration: float
    platforms: Dict[str, Dict]
    summary: Dict[str, int]
    artifacts: List[str]
    
    def to_dict(self) -> Dict:
        return asdict(self)


class MobileTestOrchestrator:
    """
    Orchestrates testing across iOS and Android platforms
    """
    
    def __init__(self, config_path: Optional[Path] = None):
        self.config = {}
        self.ios_runner = None
        self.android_runner = None
        self.device_manager = DeviceManager()
        
        if config_path:
            self.load_config(config_path)
    
    def load_config(self, config_path: Path):
        """Load test configuration from file"""
        if not config_path.exists():
            raise FileNotFoundError(f"Configuration file not found: {config_path}")
        
        with open(config_path) as f:
            if config_path.suffix == '.json':
                self.config = json.load(f)
            elif config_path.suffix in ['.yaml', '.yml']:
                self.config = yaml.safe_load(f)
            else:
                raise ValueError(f"Unsupported config format: {config_path.suffix}")
        
        # Initialize platform runners based on config
        if 'platforms' in self.config:
            if 'ios' in self.config['platforms']:
                self.ios_runner = IOSNativeTestRunner(
                    Path.cwd(),
                    self.config['platforms']['ios']
                )
            
            if 'android' in self.config['platforms']:
                self.android_runner = AndroidNativeTestRunner(
                    Path.cwd(),
                    self.config['platforms']['android']
                )
    
    def check_environment(self) -> Dict[str, Dict]:
        """Check testing environment readiness"""
        environment = {
            'ios': {},
            'android': {},
            'devices': {}
        }
        
        # Check iOS environment
        if self.ios_runner:
            environment['ios'] = self.ios_runner.check_requirements()
        
        # Check Android environment
        if self.android_runner:
            environment['android'] = self.android_runner.check_requirements()
        
        # Check available devices
        all_devices = self.device_manager.list_all_devices()
        environment['devices'] = {
            'total': len(all_devices),
            'ios_simulators': len([d for d in all_devices if d.platform == 'ios']),
            'android_emulators': len([d for d in all_devices if d.platform == 'android' and d.device_type == 'emulator']),
            'android_physical': len([d for d in all_devices if d.platform == 'android' and d.device_type == 'physical'])
        }
        
        return environment
    
    def run_tests(self, platform: Optional[str] = None, suite: Optional[str] = None,
                  parallel: bool = False) -> MobileTestReport:
        """
        Run mobile tests
        
        Args:
            platform: 'ios', 'android', or None for both
            suite: 'unit', 'ui', 'performance', or None for all
            parallel: Run tests in parallel across platforms
        
        Returns:
            Unified test report
        """
        start_time = time.time()
        timestamp = datetime.now().isoformat()
        
        results = {}
        
        if parallel and platform is None:
            # Run iOS and Android tests in parallel
            with concurrent.futures.ThreadPoolExecutor(max_workers=2) as executor:
                futures = {}
                
                if self.ios_runner:
                    futures['ios'] = executor.submit(self._run_ios_tests, suite)
                
                if self.android_runner:
                    futures['android'] = executor.submit(self._run_android_tests, suite)
                
                for platform_name, future in futures.items():
                    try:
                        results[platform_name] = future.result()
                    except Exception as e:
                        logger.error(f"Failed to run {platform_name} tests: {e}")
                        results[platform_name] = []
        else:
            # Run tests sequentially
            if self.ios_runner and (platform is None or platform == 'ios'):
                results['ios'] = self._run_ios_tests(suite)
            
            if self.android_runner and (platform is None or platform == 'android'):
                results['android'] = self._run_android_tests(suite)
        
        # Generate report
        total_duration = time.time() - start_time
        report = self._generate_report(results, timestamp, total_duration)
        
        return report
    
    def _run_ios_tests(self, suite: Optional[str]) -> List[IOSTestResult]:
        """Run iOS tests based on configuration"""
        results = []
        config = self.config['platforms']['ios']
        shared_config = self.config.get('shared', {})
        
        try:
            # Get configured test suites
            test_suites = shared_config.get('test_suites', {})
            
            # Run unit tests
            if suite in [None, 'unit'] and self._should_run_suite('unit', test_suites):
                logger.info("Running iOS unit tests...")
                result = self.ios_runner.run_unit_tests()
                results.append(result)
            
            # Run UI tests
            if suite in [None, 'ui'] and self._should_run_suite('ui', test_suites):
                if 'test_plans' in config and 'ui' in config['test_plans']:
                    logger.info("Running iOS UI tests...")
                    ui_results = self.ios_runner.run_ui_tests()
                    results.extend(ui_results)
            
            # Run performance tests
            if suite in [None, 'performance'] and self._should_run_suite('performance', test_suites):
                if 'test_plans' in config and 'performance' in config['test_plans']:
                    logger.info("Running iOS performance tests...")
                    perf_result = self.ios_runner.run_performance_tests()
                    results.append(perf_result)
        
        except Exception as e:
            logger.error(f"iOS test execution failed: {e}")
            # Create a failed result
            results.append(IOSTestResult(
                suite='error',
                passed=0,
                failed=1,
                skipped=0,
                duration=0,
                details={'error': str(e)}
            ))
        
        return results
    
    def _run_android_tests(self, suite: Optional[str]) -> List[AndroidTestResult]:
        """Run Android tests based on configuration"""
        results = []
        config = self.config['platforms']['android']
        shared_config = self.config.get('shared', {})
        
        try:
            # Get configured test suites
            test_suites = shared_config.get('test_suites', {})
            
            # Run tests for each build variant
            variants = config.get('build_variants', ['debug'])
            
            for variant in variants:
                # Run unit tests
                if suite in [None, 'unit'] and self._should_run_suite('unit', test_suites):
                    logger.info(f"Running Android unit tests for {variant}...")
                    result = self.android_runner.run_unit_tests(variant)
                    results.append(result)
                
                # Run instrumentation tests
                if suite in [None, 'ui'] and self._should_run_suite('ui', test_suites):
                    logger.info(f"Running Android instrumentation tests for {variant}...")
                    result = self.android_runner.run_instrumentation_tests(variant)
                    results.append(result)
            
            # Run performance tests (typically only on one variant)
            if suite in [None, 'performance'] and self._should_run_suite('performance', test_suites):
                logger.info("Running Android performance tests...")
                perf_result = self.android_runner.run_performance_tests()
                results.append(perf_result)
        
        except Exception as e:
            logger.error(f"Android test execution failed: {e}")
            # Create a failed result
            results.append(AndroidTestResult(
                suite='error',
                passed=0,
                failed=1,
                skipped=0,
                duration=0,
                details={'error': str(e)}
            ))
        
        return results
    
    def _should_run_suite(self, suite_name: str, test_suites: Dict) -> bool:
        """Check if a test suite should be run based on configuration"""
        if suite_name not in test_suites:
            return True  # Run by default if not configured
        
        suite_config = test_suites[suite_name]
        return suite_config.get('enabled', True)
    
    def _generate_report(self, results: Dict[str, List], timestamp: str, 
                        total_duration: float) -> MobileTestReport:
        """Generate unified test report"""
        platforms = {}
        all_artifacts = []
        
        # Process results by platform
        for platform, platform_results in results.items():
            total_passed = 0
            total_failed = 0
            total_skipped = 0
            platform_duration = 0
            suites = []
            
            for result in platform_results:
                # Convert dataclass to dict
                if hasattr(result, '__dict__'):
                    result_dict = {
                        'suite': result.suite,
                        'passed': result.passed,
                        'failed': result.failed,
                        'skipped': result.skipped,
                        'duration': result.duration
                    }
                    
                    if result.coverage is not None:
                        result_dict['coverage'] = result.coverage
                    
                    if result.details:
                        result_dict['details'] = result.details
                    
                    suites.append(result_dict)
                    
                    # Aggregate counts
                    total_passed += result.passed
                    total_failed += result.failed
                    total_skipped += result.skipped
                    platform_duration += result.duration
                    
                    # Collect artifacts
                    if result.artifacts:
                        all_artifacts.extend(result.artifacts)
            
            platforms[platform] = {
                'total_passed': total_passed,
                'total_failed': total_failed,
                'total_skipped': total_skipped,
                'total_duration': platform_duration,
                'suites': suites
            }
        
        # Calculate summary
        summary = {
            'total_tests': sum(p['total_passed'] + p['total_failed'] + p['total_skipped'] 
                             for p in platforms.values()),
            'total_passed': sum(p['total_passed'] for p in platforms.values()),
            'total_failed': sum(p['total_failed'] for p in platforms.values()),
            'total_skipped': sum(p['total_skipped'] for p in platforms.values()),
            'pass_rate': 0.0
        }
        
        if summary['total_tests'] > 0:
            summary['pass_rate'] = (summary['total_passed'] / summary['total_tests']) * 100
        
        return MobileTestReport(
            timestamp=timestamp,
            total_duration=total_duration,
            platforms=platforms,
            summary=summary,
            artifacts=all_artifacts
        )
    
    def run_on_devices(self, test_suite: str, devices: List[str]) -> MobileTestReport:
        """Run tests on specific devices"""
        start_time = time.time()
        timestamp = datetime.now().isoformat()
        results = {'ios': [], 'android': []}
        
        # Get available devices
        available_devices = self.device_manager.list_all_devices()
        device_map = {d.name: d for d in available_devices}
        
        for device_name in devices:
            if device_name not in device_map:
                logger.warning(f"Device {device_name} not found")
                continue
            
            device = device_map[device_name]
            
            # Start device if needed
            if device.state not in ['booted', 'device']:
                logger.info(f"Starting device {device_name}...")
                if not self.device_manager.start_device(device):
                    logger.error(f"Failed to start device {device_name}")
                    continue
            
            # Run tests based on platform
            if device.platform == 'ios' and self.ios_runner:
                logger.info(f"Running {test_suite} tests on iOS device {device_name}")
                destination = f"id={device.id}"
                result = self.ios_runner.run_unit_tests(destination=destination)
                result.details['device'] = device_name
                results['ios'].append(result)
            
            elif device.platform == 'android' and self.android_runner:
                logger.info(f"Running {test_suite} tests on Android device {device_name}")
                result = self.android_runner.run_instrumentation_tests(device=device.id)
                result.details['device'] = device_name
                results['android'].append(result)
        
        # Generate report
        total_duration = time.time() - start_time
        report = self._generate_report(results, timestamp, total_duration)
        
        return report
    
    def generate_html_report(self, report: MobileTestReport, output_path: Path):
        """Generate HTML test report"""
        html_template = """
<!DOCTYPE html>
<html>
<head>
    <title>Mobile Test Report - {timestamp}</title>
    <style>
        body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; margin: 20px; background: #f5f5f5; }}
        .container {{ max-width: 1200px; margin: 0 auto; background: white; padding: 20px; border-radius: 8px; box-shadow: 0 2px 4px rgba(0,0,0,0.1); }}
        h1, h2, h3 {{ color: #333; }}
        .summary {{ display: flex; gap: 20px; margin: 20px 0; }}
        .summary-card {{ flex: 1; padding: 20px; background: #f8f9fa; border-radius: 8px; text-align: center; }}
        .summary-card h3 {{ margin: 0 0 10px 0; font-size: 14px; color: #666; }}
        .summary-card .value {{ font-size: 32px; font-weight: bold; }}
        .passed {{ color: #28a745; }}
        .failed {{ color: #dc3545; }}
        .skipped {{ color: #ffc107; }}
        .platform {{ margin: 30px 0; }}
        .platform-header {{ background: #007bff; color: white; padding: 10px 20px; border-radius: 4px; }}
        table {{ width: 100%; border-collapse: collapse; margin: 20px 0; }}
        th, td {{ padding: 12px; text-align: left; border-bottom: 1px solid #dee2e6; }}
        th {{ background: #f8f9fa; font-weight: 600; }}
        tr:hover {{ background: #f8f9fa; }}
        .coverage {{ display: inline-block; padding: 2px 8px; background: #e9ecef; border-radius: 4px; font-size: 12px; }}
        .duration {{ color: #6c757d; font-size: 14px; }}
        .artifacts {{ margin-top: 30px; padding: 20px; background: #f8f9fa; border-radius: 8px; }}
        .artifacts h3 {{ margin-top: 0; }}
        .artifacts ul {{ margin: 10px 0; padding-left: 20px; }}
        .footer {{ margin-top: 40px; padding-top: 20px; border-top: 1px solid #dee2e6; text-align: center; color: #6c757d; }}
    </style>
</head>
<body>
    <div class="container">
        <h1>Mobile Test Report</h1>
        <p>Generated: {timestamp} | Duration: {duration:.2f}s</p>
        
        <div class="summary">
            <div class="summary-card">
                <h3>Total Tests</h3>
                <div class="value">{total_tests}</div>
            </div>
            <div class="summary-card">
                <h3>Passed</h3>
                <div class="value passed">{total_passed}</div>
            </div>
            <div class="summary-card">
                <h3>Failed</h3>
                <div class="value failed">{total_failed}</div>
            </div>
            <div class="summary-card">
                <h3>Pass Rate</h3>
                <div class="value">{pass_rate:.1f}%</div>
            </div>
        </div>
        
        {platform_sections}
        
        {artifacts_section}
        
        <div class="footer">
            <p>Generated by SEGA Mobile Testing Framework</p>
        </div>
    </div>
</body>
</html>
        """
        
        # Generate platform sections
        platform_sections = []
        for platform, data in report.platforms.items():
            platform_html = f"""
        <div class="platform">
            <div class="platform-header">
                <h2>{platform.upper()} Tests</h2>
                <span class="duration">Total Duration: {data['total_duration']:.2f}s</span>
            </div>
            <table>
                <thead>
                    <tr>
                        <th>Suite</th>
                        <th>Passed</th>
                        <th>Failed</th>
                        <th>Skipped</th>
                        <th>Coverage</th>
                        <th>Duration</th>
                    </tr>
                </thead>
                <tbody>
            """
            
            for suite in data['suites']:
                coverage_html = f'<span class="coverage">{suite.get("coverage", 0):.1f}%</span>' if 'coverage' in suite else '-'
                platform_html += f"""
                    <tr>
                        <td>{suite['suite']}</td>
                        <td class="passed">{suite['passed']}</td>
                        <td class="failed">{suite['failed']}</td>
                        <td class="skipped">{suite['skipped']}</td>
                        <td>{coverage_html}</td>
                        <td class="duration">{suite['duration']:.2f}s</td>
                    </tr>
                """
            
            platform_html += """
                </tbody>
            </table>
        </div>
            """
            platform_sections.append(platform_html)
        
        # Generate artifacts section
        artifacts_section = ""
        if report.artifacts:
            artifacts_html = "<ul>"
            for artifact in report.artifacts:
                artifacts_html += f"<li>{artifact}</li>"
            artifacts_html += "</ul>"
            
            artifacts_section = f"""
        <div class="artifacts">
            <h3>Test Artifacts</h3>
            {artifacts_html}
        </div>
            """
        
        # Fill template
        html = html_template.format(
            timestamp=report.timestamp,
            duration=report.total_duration,
            total_tests=report.summary['total_tests'],
            total_passed=report.summary['total_passed'],
            total_failed=report.summary['total_failed'],
            pass_rate=report.summary['pass_rate'],
            platform_sections='\n'.join(platform_sections),
            artifacts_section=artifacts_section
        )
        
        # Write to file
        with open(output_path, 'w') as f:
            f.write(html)
    
    def generate_junit_report(self, report: MobileTestReport, output_path: Path):
        """Generate JUnit XML report"""
        import xml.etree.ElementTree as ET
        
        # Create root testsuites element
        testsuites = ET.Element('testsuites', {
            'name': 'Mobile Tests',
            'tests': str(report.summary['total_tests']),
            'failures': str(report.summary['total_failed']),
            'skipped': str(report.summary['total_skipped']),
            'time': str(report.total_duration),
            'timestamp': report.timestamp
        })
        
        # Add platform test suites
        for platform, data in report.platforms.items():
            testsuite = ET.SubElement(testsuites, 'testsuite', {
                'name': platform,
                'tests': str(data['total_passed'] + data['total_failed'] + data['total_skipped']),
                'failures': str(data['total_failed']),
                'skipped': str(data['total_skipped']),
                'time': str(data['total_duration'])
            })
            
            # Add test cBases for each suite
            for suite in data['suites']:
                # Create test cBases based on counts
                for i in range(suite['passed']):
                    testcBase = ET.SubElement(testsuite, 'testcBase', {
                        'name': f"{suite['suite']}_passed_{i+1}",
                        'classname': f"{platform}.{suite['suite']}",
                        'time': str(suite['duration'] / max(1, suite['passed'] + suite['failed'] + suite['skipped']))
                    })
                
                for i in range(suite['failed']):
                    testcBase = ET.SubElement(testsuite, 'testcBase', {
                        'name': f"{suite['suite']}_failed_{i+1}",
                        'classname': f"{platform}.{suite['suite']}",
                        'time': str(suite['duration'] / max(1, suite['passed'] + suite['failed'] + suite['skipped']))
                    })
                    failure = ET.SubElement(testcBase, 'failure', {
                        'message': 'Test failed',
                        'type': 'TestFailure'
                    })
                    if 'details' in suite and 'error' in suite['details']:
                        failure.text = str(suite['details']['error'])
                
                for i in range(suite['skipped']):
                    testcBase = ET.SubElement(testsuite, 'testcBase', {
                        'name': f"{suite['suite']}_skipped_{i+1}",
                        'classname': f"{platform}.{suite['suite']}",
                        'time': '0'
                    })
                    ET.SubElement(testcBase, 'skipped', {
                        'message': 'Test skipped'
                    })
        
        # Write XML to file
        tree = ET.ElementTree(testsuites)
        tree.write(output_path, encoding='utf-8', xml_declaration=True)
    
    def cleanup(self):
        """Clean up resources"""
        try:
            # Clean up device manager
            self.device_manager.cleanup_all_devices()
            
            # Clean up platform runners
            if self.ios_runner:
                self.ios_runner.cleanup_simulators()
            
            if self.android_runner:
                self.android_runner.cleanup()
        
        except Exception as e:
            logger.error(f"Cleanup failed: {e}")