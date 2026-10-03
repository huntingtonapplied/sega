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
SEGA TEST RESULT AGGREGATION AND REPORTING
==============================================================================
File: src/sega/testing/test_aggregator.py
Project: SEGA (Scalable Engineering & Growth Automation)
Copyright: 2022-2025 FLEET
License: Apache-2.0

SEGA MODULE: Testing/ResultAggregation
COMPONENT: Test Result Aggregator and Reporter
PURPOSE: Aggregate test results from multiple sources and generate reports
DEPENDENCIES: json, xml, datetime, pathlib
USAGE: aggregator = TestAggregator(); report = aggregator.aggregate_results(results)

This module provides comprehensive test result aggregation, coverage merging,
and multi-format reporting capabilities.
==============================================================================
"""

import json
import xml.etree.ElementTree as ET
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, field


@dataclass
class AggregatedTestResult:
    """Aggregated test results across multiple projects and suites."""
    
    total_projects: int = 0
    total_tests: int = 0
    passed_tests: int = 0
    failed_tests: int = 0
    skipped_tests: int = 0
    total_duration: float = 0.0
    
    # Per-project results
    project_results: Dict[str, Dict] = field(default_factory=dict)
    
    # Per-suite results
    suite_results: Dict[str, Dict] = field(default_factory=dict)
    
    # Coverage data
    overall_coverage: Optional[float] = None
    project_coverage: Dict[str, float] = field(default_factory=dict)
    
    # Failure details
    failures: List[Dict] = field(default_factory=list)
    
    # Performance metrics
    slowest_tests: List[Dict] = field(default_factory=list)
    
    # Timestamps
    start_time: Optional[datetime] = None
    end_time: Optional[datetime] = None


class TestAggregator:
    """Aggregates test results from multiple sources."""
    
    def __init__(self, workspace_root: Path = None):
        self.workspace_root = workspace_root or Path.cwd()
        self.results_dir = self.workspace_root / '.sega' / 'test-results'
        self.results_dir.mkdir(parents=True, exist_ok=True)
        
    def aggregate_results(self, results: Dict[str, Any]) -> AggregatedTestResult:
        """Aggregate test results from multiple projects and suites."""
        aggregated = AggregatedTestResult()
        aggregated.start_time = datetime.now()
        
        # Process each project's results
        for project_name, project_results in results.items():
            if isinstance(project_results, dict):
                self._process_project_results(aggregated, project_name, project_results)
                
        aggregated.end_time = datetime.now()
        
        # Calculate overall metrics
        self._calculate_overall_metrics(aggregated)
        
        # Sort slowest tests
        aggregated.slowest_tests.sort(key=lambda x: x['duration'], reverse=True)
        aggregated.slowest_tests = aggregated.slowest_tests[:10]  # Keep top 10
        
        return aggregated
        
    def _process_project_results(self, aggregated: AggregatedTestResult, 
                                 project_name: str, results: Dict):
        """Process results for a single project."""
        project_summary = {
            'total_tests': 0,
            'passed': 0,
            'failed': 0,
            'skipped': 0,
            'duration': 0.0,
            'suites': {}
        }
        
        for suite_name, result in results.items():
            if hasattr(result, 'success'):
                # Process test result
                project_summary['total_tests'] += 1
                aggregated.total_tests += 1
                
                if result.success:
                    project_summary['passed'] += 1
                    aggregated.passed_tests += 1
                else:
                    project_summary['failed'] += 1
                    aggregated.failed_tests += 1
                    
                    # Record failure details
                    aggregated.failures.append({
                        'project': project_name,
                        'suite': suite_name,
                        'error': result.error,
                        'output': result.output[:500] if result.output else None
                    })
                    
                # Track duration
                duration = result.duration if result.duration else 0.0
                project_summary['duration'] += duration
                aggregated.total_duration += duration
                
                # Track slowest tests
                if duration > 1.0:  # Only track tests > 1 second
                    aggregated.slowest_tests.append({
                        'project': project_name,
                        'suite': suite_name,
                        'duration': duration
                    })
                    
                # Track coverage if available
                if result.metrics and 'coverage' in result.metrics:
                    coverage_str = result.metrics['coverage']
                    if isinstance(coverage_str, str) and '%' in coverage_str:
                        try:
                            coverage_value = float(coverage_str.replace('%', ''))
                            aggregated.project_coverage[project_name] = coverage_value
                        except ValueError:
                            pass
                            
                # Update suite results
                if suite_name not in aggregated.suite_results:
                    aggregated.suite_results[suite_name] = {
                        'total': 0,
                        'passed': 0,
                        'failed': 0,
                        'projects': []
                    }
                    
                aggregated.suite_results[suite_name]['total'] += 1
                if result.success:
                    aggregated.suite_results[suite_name]['passed'] += 1
                else:
                    aggregated.suite_results[suite_name]['failed'] += 1
                    
                if project_name not in aggregated.suite_results[suite_name]['projects']:
                    aggregated.suite_results[suite_name]['projects'].append(project_name)
                    
                # Store suite details
                project_summary['suites'][suite_name] = {
                    'success': result.success,
                    'duration': duration,
                    'error': result.error if not result.success else None
                }
                
        aggregated.project_results[project_name] = project_summary
        aggregated.total_projects += 1
        
    def _calculate_overall_metrics(self, aggregated: AggregatedTestResult):
        """Calculate overall metrics from aggregated data."""
        # Calculate overall coverage
        if aggregated.project_coverage:
            coverage_values = list(aggregated.project_coverage.values())
            aggregated.overall_coverage = sum(coverage_values) / len(coverage_values)
            
    def generate_report(self, aggregated: AggregatedTestResult, 
                        format: str = 'text') -> str:
        """Generate test report in specified format."""
        if format == 'text':
            return self._generate_text_report(aggregated)
        elif format == 'json':
            return self._generate_json_report(aggregated)
        elif format == 'junit':
            return self._generate_junit_report(aggregated)
        elif format == 'html':
            return self._generate_html_report(aggregated)
        else:
            raise ValueError(f"Unknown report format: {format}")
            
    def _generate_text_report(self, aggregated: AggregatedTestResult) -> str:
        """Generate human-readable text report."""
        lines = []
        
        # Header
        lines.append("=" * 80)
        lines.append("SEGA COMPREHENSIVE TEST REPORT")
        lines.append("=" * 80)
        
        # Timestamp
        if aggregated.start_time and aggregated.end_time:
            duration = (aggregated.end_time - aggregated.start_time).total_seconds()
            lines.append(f"Test Run: {aggregated.start_time.strftime('%Y-%m-%d %H:%M:%S')}")
            lines.append(f"Duration: {duration:.2f} seconds")
            lines.append("")
            
        # Overall Summary
        lines.append("OVERALL SUMMARY")
        lines.append("-" * 40)
        lines.append(f"Projects Tested: {aggregated.total_projects}")
        lines.append(f"Total Tests: {aggregated.total_tests}")
        lines.append(f"Passed: {aggregated.passed_tests} ({self._percentage(aggregated.passed_tests, aggregated.total_tests)}%)")
        lines.append(f"Failed: {aggregated.failed_tests} ({self._percentage(aggregated.failed_tests, aggregated.total_tests)}%)")
        
        if aggregated.skipped_tests > 0:
            lines.append(f"Skipped: {aggregated.skipped_tests}")
            
        lines.append(f"Total Duration: {aggregated.total_duration:.2f}s")
        
        if aggregated.overall_coverage:
            lines.append(f"Overall Coverage: {aggregated.overall_coverage:.1f}%")
            
        lines.append("")
        
        # Project Summary
        if aggregated.project_results:
            lines.append("PROJECT SUMMARY")
            lines.append("-" * 40)
            
            for project, summary in sorted(aggregated.project_results.items()):
                status = "PASS" if summary['failed'] == 0 else "FAIL"
                lines.append(f"[{status}] {project}: {summary['passed']}/{summary['total_tests']} passed ({summary['duration']:.2f}s)")
                
                # Show coverage if available
                if project in aggregated.project_coverage:
                    lines.append(f"     Coverage: {aggregated.project_coverage[project]:.1f}%")
                    
                # Show failed suites
                failed_suites = [suite for suite, info in summary['suites'].items() 
                               if not info['success']]
                if failed_suites:
                    lines.append(f"     Failed: {', '.join(failed_suites)}")
                    
            lines.append("")
            
        # Suite Summary
        if aggregated.suite_results:
            lines.append("SUITE SUMMARY")
            lines.append("-" * 40)
            
            for suite, info in sorted(aggregated.suite_results.items()):
                status = "PASS" if info['failed'] == 0 else "FAIL"
                lines.append(f"[{status}] {suite}: {info['passed']}/{info['total']} passed")
                lines.append(f"     Projects: {', '.join(info['projects'])}")
                
            lines.append("")
            
        # Failures
        if aggregated.failures:
            lines.append("FAILURES")
            lines.append("-" * 40)
            
            for i, failure in enumerate(aggregated.failures, 1):
                lines.append(f"{i}. {failure['project']}/{failure['suite']}")
                if failure['error']:
                    lines.append(f"   Error: {failure['error']}")
                if failure['output']:
                    lines.append(f"   Output: {failure['output'][:200]}...")
                lines.append("")
                
        # Slowest Tests
        if aggregated.slowest_tests:
            lines.append("SLOWEST TESTS")
            lines.append("-" * 40)
            
            for test in aggregated.slowest_tests[:5]:
                lines.append(f"{test['project']}/{test['suite']}: {test['duration']:.2f}s")
                
            lines.append("")
            
        # Footer
        lines.append("=" * 80)
        
        if aggregated.failed_tests > 0:
            lines.append(f"TEST RUN FAILED: {aggregated.failed_tests} test(s) failed")
        else:
            lines.append("TEST RUN SUCCESSFUL: All tests passed!")
            
        lines.append("=" * 80)
        
        return "\n".join(lines)
        
    def _generate_json_report(self, aggregated: AggregatedTestResult) -> str:
        """Generate JSON report."""
        report = {
            'summary': {
                'total_projects': aggregated.total_projects,
                'total_tests': aggregated.total_tests,
                'passed': aggregated.passed_tests,
                'failed': aggregated.failed_tests,
                'skipped': aggregated.skipped_tests,
                'duration': aggregated.total_duration,
                'overall_coverage': aggregated.overall_coverage,
                'start_time': aggregated.start_time.isoformat() if aggregated.start_time else None,
                'end_time': aggregated.end_time.isoformat() if aggregated.end_time else None
            },
            'projects': aggregated.project_results,
            'suites': aggregated.suite_results,
            'coverage': aggregated.project_coverage,
            'failures': aggregated.failures,
            'slowest_tests': aggregated.slowest_tests
        }
        
        return json.dumps(report, indent=2)
        
    def _generate_junit_report(self, aggregated: AggregatedTestResult) -> str:
        """Generate JUnit XML report."""
        testsuites = ET.Element('testsuites')
        testsuites.set('name', 'SEGA Tests')
        testsuites.set('tests', str(aggregated.total_tests))
        testsuites.set('failures', str(aggregated.failed_tests))
        testsuites.set('skipped', str(aggregated.skipped_tests))
        testsuites.set('time', f"{aggregated.total_duration:.2f}")
        
        if aggregated.start_time:
            testsuites.set('timestamp', aggregated.start_time.isoformat())
            
        # Create testsuite for each project
        for project_name, project_summary in aggregated.project_results.items():
            testsuite = ET.SubElement(testsuites, 'testsuite')
            testsuite.set('name', project_name)
            testsuite.set('tests', str(project_summary['total_tests']))
            testsuite.set('failures', str(project_summary['failed']))
            testsuite.set('time', f"{project_summary['duration']:.2f}")
            
            # Add testcBases for each suite
            for suite_name, suite_info in project_summary['suites'].items():
                testcBase = ET.SubElement(testsuite, 'testcBase')
                testcBase.set('name', suite_name)
                testcBase.set('classname', f"{project_name}.{suite_name}")
                testcBase.set('time', f"{suite_info['duration']:.2f}")
                
                if not suite_info['success']:
                    failure = ET.SubElement(testcBase, 'failure')
                    failure.set('message', suite_info.get('error', 'Test failed'))
                    
        ET.indent(testsuites, space='  ')
        return ET.toString(testsuites, encoding='unicode')
        
    def _generate_html_report(self, aggregated: AggregatedTestResult) -> str:
        """Generate HTML report."""
        html = f"""
<!DOCTYPE html>
<html>
<head>
    <title>SEGA Test Report</title>
    <style>
        body {{ font-family: Arial, sans-serif; margin: 20px; }}
        h1 {{ color: #333; }}
        .summary {{ background: #f5f5f5; padding: 15px; border-radius: 5px; margin: 20px 0; }}
        .pass {{ color: green; font-weight: bold; }}
        .fail {{ color: red; font-weight: bold; }}
        table {{ border-collapse: collapse; width: 100%; margin: 20px 0; }}
        th, td {{ border: 1px solid #ddd; padding: 8px; text-align: left; }}
        th {{ background: #f5f5f5; }}
        .progress {{ background: #e0e0e0; border-radius: 5px; overflow: hidden; height: 20px; }}
        .progress-bar {{ background: green; height: 100%; }}
    </style>
</head>
<body>
    <h1>SEGA Comprehensive Test Report</h1>
    
    <div class="summary">
        <h2>Overall Summary</h2>
        <p>Projects Tested: {aggregated.total_projects}</p>
        <p>Total Tests: {aggregated.total_tests}</p>
        <p>Passed: <span class="pass">{aggregated.passed_tests}</span> ({self._percentage(aggregated.passed_tests, aggregated.total_tests)}%)</p>
        <p>Failed: <span class="fail">{aggregated.failed_tests}</span> ({self._percentage(aggregated.failed_tests, aggregated.total_tests)}%)</p>
        <p>Duration: {aggregated.total_duration:.2f} seconds</p>
        {"<p>Overall Coverage: {:.1f}%</p>".format(aggregated.overall_coverage) if aggregated.overall_coverage else ""}
        
        <div class="progress">
            <div class="progress-bar" style="width: {self._percentage(aggregated.passed_tests, aggregated.total_tests)}%"></div>
        </div>
    </div>
    
    <h2>Project Results</h2>
    <table>
        <tr>
            <th>Project</th>
            <th>Status</th>
            <th>Tests</th>
            <th>Passed</th>
            <th>Failed</th>
            <th>Duration</th>
            <th>Coverage</th>
        </tr>
"""
        
        for project, summary in sorted(aggregated.project_results.items()):
            status_class = "pass" if summary['failed'] == 0 else "fail"
            status_text = "PASS" if summary['failed'] == 0 else "FAIL"
            coverage = f"{aggregated.project_coverage[project]:.1f}%" if project in aggregated.project_coverage else "N/A"
            
            html += f"""
        <tr>
            <td>{project}</td>
            <td class="{status_class}">{status_text}</td>
            <td>{summary['total_tests']}</td>
            <td>{summary['passed']}</td>
            <td>{summary['failed']}</td>
            <td>{summary['duration']:.2f}s</td>
            <td>{coverage}</td>
        </tr>
"""
            
        html += """
    </table>
    
"""
        
        if aggregated.failures:
            html += """
    <h2>Failures</h2>
    <table>
        <tr>
            <th>Project</th>
            <th>Suite</th>
            <th>Error</th>
        </tr>
"""
            for failure in aggregated.failures:
                error = failure['error'] or 'Unknown error'
                html += f"""
        <tr>
            <td>{failure['project']}</td>
            <td>{failure['suite']}</td>
            <td>{error[:200]}</td>
        </tr>
"""
                
            html += """
    </table>
"""
            
        html += """
</body>
</html>
"""
        
        return html
        
    def _percentage(self, part: int, total: int) -> float:
        """Calculate percentage."""
        if total == 0:
            return 0.0
        return round((part / total) * 100, 1)
        
    def save_report(self, aggregated: AggregatedTestResult, 
                   filename: str = None, format: str = 'text'):
        """Save report to file."""
        if not filename:
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            filename = f"test_report_{timestamp}.{self._get_extension(format)}"
            
        report_path = self.results_dir / filename
        report_content = self.generate_report(aggregated, format)
        
        with open(report_path, 'w') as f:
            f.write(report_content)
            
        return report_path
        
    def _get_extension(self, format: str) -> str:
        """Get file extension for format."""
        extensions = {
            'text': 'txt',
            'json': 'json',
            'junit': 'xml',
            'html': 'html'
        }
        return extensions.get(format, 'txt')