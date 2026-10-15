#!/usr/bin/env python3
"""
XCResult Parser for iOS Test Results

Parses .xcresult bundles from xcodebuild test runs
"""

import subprocess
import json
from pathlib import Path
from typing import Dict, List, Optional, Any
from dataclasses import dataclass
import logging

logger = logging.getLogger(__name__)


@dataclass
class TestCBase:
    """Individual test cBase result"""
    identifier: str
    name: str
    duration: float
    status: str  # 'passed', 'failed', 'skipped'
    failure_message: Optional[str] = None
    failure_file: Optional[str] = None
    failure_line: Optional[int] = None


@dataclass
class TestSuite:
    """Test suite result"""
    identifier: str
    name: str
    duration: float
    test_cBases: List[TestCBase]
    
    @property
    def passed_count(self) -> int:
        return len([tc for tc in self.test_cBases if tc.status == 'passed'])
    
    @property
    def failed_count(self) -> int:
        return len([tc for tc in self.test_cBases if tc.status == 'failed'])
    
    @property
    def skipped_count(self) -> int:
        return len([tc for tc in self.test_cBases if tc.status == 'skipped'])


class XCResultParser:
    """
    Parses .xcresult bundles to extract detailed test information
    """
    
    def __init__(self):
        self.xcrun = self._find_xcrun()
    
    def _find_xcrun(self) -> str:
        """Find xcrun command"""
        result = subprocess.run(['which', 'xcrun'], capture_output=True, text=True)
        if result.returncode != 0:
            raise RuntimeError("xcrun not found. Please install Xcode Command Line Tools.")
        return result.stdout.strip()
    
    def parse(self, xcresult_path: Path) -> Dict[str, Any]:
        """
        Parse an .xcresult bundle
        
        Returns:
            Dictionary containing test results, metrics, and coverage
        """
        if not xcresult_path.exists():
            raise FileNotFoundError(f"XCResult bundle not found: {xcresult_path}")
        
        result = {
            'test_suites': [],
            'metrics': {},
            'coverage': None,
            'issues': [],
            'performance_metrics': {}
        }
        
        # Export xcresult as JSON
        json_data = self._export_as_json(xcresult_path)
        if json_data:
            # Parse test results
            result['test_suites'] = self._parse_test_suites(json_data)
            
            # Parse metrics
            result['metrics'] = self._parse_metrics(json_data)
            
            # Parse issues (warnings, errors)
            result['issues'] = self._parse_issues(json_data)
        
        # Parse coverage separately
        result['coverage'] = self._parse_coverage(xcresult_path)
        
        # Parse performance metrics
        result['performance_metrics'] = self._parse_performance_metrics(xcresult_path)
        
        return result
    
    def _export_as_json(self, xcresult_path: Path) -> Optional[Dict]:
        """Export xcresult bundle as JSON"""
        try:
            cmd = [
                self.xcrun, 'xcresulttool', 'get',
                '--path', str(xcresult_path),
                '--format', 'json'
            ]
            
            result = subprocess.run(cmd, capture_output=True, text=True)
            
            if result.returncode == 0:
                return json.loads(result.stdout)
            else:
                logger.error(f"Failed to export xcresult: {result.stderr}")
                return None
        
        except Exception as e:
            logger.error(f"Failed to parse xcresult JSON: {e}")
            return None
    
    def _parse_test_suites(self, data: Dict) -> List[TestSuite]:
        """Parse test suites from JSON data"""
        suites = []
        
        # Navigate through the complex xcresult structure
        if 'actions' in data:
            actions = data['actions'].get('_values', [])
            
            for action in actions:
                if action.get('_type', {}).get('_name') == 'ActionRecord':
                    # Look for test action
                    action_result = action.get('actionResult', {})
                    
                    if 'testsRef' in action_result:
                        # Get test results
                        tests_ref = action_result['testsRef']
                        test_data = self._get_object_by_id(data, tests_ref.get('id', {}).get('_value'))
                        
                        if test_data:
                            suites.extend(self._parse_test_hierarchy(test_data))
        
        return suites
    
    def _parse_test_hierarchy(self, test_data: Dict) -> List[TestSuite]:
        """Parse test hierarchy into test suites"""
        suites = []
        
        # Handle different test summary structures
        if 'summaries' in test_data:
            summaries = test_data['summaries'].get('_values', [])
            
            for summary in summaries:
                if summary.get('_type', {}).get('_name') == 'ActionTestPlanRunSummary':
                    # Parse test plan summaries
                    testableSummaries = summary.get('testableSummaries', {}).get('_values', [])
                    
                    for testable in testableSummaries:
                        suite = self._parse_testable_summary(testable)
                        if suite:
                            suites.append(suite)
        
        return suites
    
    def _parse_testable_summary(self, testable: Dict) -> Optional[TestSuite]:
        """Parse a testable summary into a test suite"""
        name = testable.get('name', {}).get('_value', 'Unknown')
        
        test_cBases = []
        tests = testable.get('tests', {}).get('_values', [])
        
        for test in tests:
            test_cBase = self._parse_test(test)
            if test_cBase:
                test_cBases.append(test_cBase)
        
        if test_cBases:
            # Calculate suite duration
            duration = sum(tc.duration for tc in test_cBases)
            
            return TestSuite(
                identifier=testable.get('targetName', {}).get('_value', name),
                name=name,
                duration=duration,
                test_cBases=test_cBases
            )
        
        return None
    
    def _parse_test(self, test: Dict, parent_name: str = '') -> Optional[TestCBase]:
        """Parse individual test or test group"""
        test_type = test.get('_type', {}).get('_name', '')
        
        if test_type == 'ActionTestMetadata':
            # Individual test cBase
            identifier = test.get('identifier', {}).get('_value', '')
            name = test.get('name', {}).get('_value', '')
            duration = test.get('duration', {}).get('_value', 0.0)
            test_status = test.get('testStatus', {}).get('_value', '')
            
            # Map test status
            status_map = {
                'Success': 'passed',
                'Failure': 'failed',
                'Skipped': 'skipped'
            }
            status = status_map.get(test_status, 'unknown')
            
            # Extract failure information if present
            failure_message = None
            failure_file = None
            failure_line = None
            
            if status == 'failed':
                summaries = test.get('summaries', {}).get('_values', [])
                for summary in summaries:
                    failure_summaries = summary.get('failureSummaries', {}).get('_values', [])
                    if failure_summaries:
                        failure = failure_summaries[0]
                        failure_message = failure.get('message', {}).get('_value', '')
                        
                        # Extract file and line from source code context
                        source_code_context = failure.get('sourceCodeContext', {})
                        if source_code_context:
                            location = source_code_context.get('location', {})
                            failure_file = location.get('filePath', {}).get('_value', '')
                            failure_line = location.get('lineNumber', {}).get('_value')
            
            return TestCBase(
                identifier=identifier,
                name=name if name else identifier.split('/')[-1],
                duration=duration,
                status=status,
                failure_message=failure_message,
                failure_file=failure_file,
                failure_line=failure_line
            )
        
        elif test_type == 'ActionTestSummaryGroup':
            # Test group - recursively parse subtests
            subtests = test.get('subtests', {}).get('_values', [])
            test_cBases = []
            
            for subtest in subtests:
                test_cBase = self._parse_test(subtest, parent_name)
                if test_cBase:
                    test_cBases.append(test_cBase)
            
            # If this is a leaf group with actual tests, return the first one
            # In a more complete implementation, we'd handle groups properly
            return test_cBases[0] if test_cBases else None
        
        return None
    
    def _parse_metrics(self, data: Dict) -> Dict[str, Any]:
        """Parse test metrics from JSON data"""
        metrics = {}
        
        if 'metrics' in data:
            metrics_data = data['metrics']
            
            # Extract test counts
            if 'testsCount' in metrics_data:
                metrics['total_tests'] = metrics_data['testsCount'].get('_value', 0)
            
            if 'testsFailedCount' in metrics_data:
                metrics['failed_tests'] = metrics_data['testsFailedCount'].get('_value', 0)
            
            # Calculate derived metrics
            if 'total_tests' in metrics and 'failed_tests' in metrics:
                metrics['passed_tests'] = metrics['total_tests'] - metrics['failed_tests']
                if metrics['total_tests'] > 0:
                    metrics['pass_rate'] = (metrics['passed_tests'] / metrics['total_tests']) * 100
        
        return metrics
    
    def _parse_issues(self, data: Dict) -> List[Dict[str, str]]:
        """Parse issues (warnings, errors) from JSON data"""
        issues = []
        
        if 'issues' in data:
            issues_data = data['issues'].get('_values', [])
            
            for issue in issues_data:
                issue_type = issue.get('type', {}).get('_value', '')
                message = issue.get('message', {}).get('_value', '')
                
                issue_dict = {
                    'type': issue_type,
                    'message': message
                }
                
                # Add location information if available
                location = issue.get('sourceCodeContext', {}).get('location', {})
                if location:
                    issue_dict['file'] = location.get('filePath', {}).get('_value', '')
                    issue_dict['line'] = location.get('lineNumber', {}).get('_value', 0)
                
                issues.append(issue_dict)
        
        return issues
    
    def _parse_coverage(self, xcresult_path: Path) -> Optional[Dict[str, Any]]:
        """Parse code coverage from xcresult"""
        try:
            # Export coverage report
            cmd = [
                self.xcrun, 'xccov', 'view',
                '--report', str(xcresult_path),
                '--json'
            ]
            
            result = subprocess.run(cmd, capture_output=True, text=True)
            
            if result.returncode == 0:
                coverage_data = json.loads(result.stdout)
                
                # Extract overall coverage
                coverage = {
                    'line_coverage': coverage_data.get('lineCoverage', 0) * 100,
                    'targets': []
                }
                
                # Extract per-target coverage
                for target in coverage_data.get('targets', []):
                    target_coverage = {
                        'name': target.get('name', ''),
                        'line_coverage': target.get('lineCoverage', 0) * 100,
                        'files': []
                    }
                    
                    # Extract per-file coverage
                    for file in target.get('files', []):
                        file_coverage = {
                            'path': file.get('path', ''),
                            'line_coverage': file.get('lineCoverage', 0) * 100,
                            'covered_lines': file.get('coveredLines', 0),
                            'executable_lines': file.get('executableLines', 0)
                        }
                        target_coverage['files'].append(file_coverage)
                    
                    coverage['targets'].append(target_coverage)
                
                return coverage
            
        except Exception as e:
            logger.error(f"Failed to parse coverage: {e}")
        
        return None
    
    def _parse_performance_metrics(self, xcresult_path: Path) -> Dict[str, Any]:
        """Parse performance metrics from xcresult"""
        performance = {}
        
        # This would require parsing XCTest performance results
        # For now, return a placeholder structure
        performance['app_launch'] = {
            'average': 0.0,
            'min': 0.0,
            'max': 0.0,
            'standard_deviation': 0.0
        }
        
        return performance
    
    def _get_object_by_id(self, data: Dict, object_id: str) -> Optional[Dict]:
        """Get object by ID from xcresult data"""
        # In a real implementation, this would navigate the object graph
        # For now, return None
        return None
    
    def generate_summary(self, parsed_data: Dict) -> str:
        """Generate a human-readable summary of test results"""
        lines = ["iOS Test Results Summary", "=" * 50]
        
        # Overall metrics
        metrics = parsed_data.get('metrics', {})
        if metrics:
            lines.append(f"Total Tests: {metrics.get('total_tests', 0)}")
            lines.append(f"Passed: {metrics.get('passed_tests', 0)}")
            lines.append(f"Failed: {metrics.get('failed_tests', 0)}")
            lines.append(f"Pass Rate: {metrics.get('pass_rate', 0):.1f}%")
            lines.append("")
        
        # Test suites
        lines.append("Test Suites:")
        for suite in parsed_data.get('test_suites', []):
            lines.append(f"  {suite.name}:")
            lines.append(f"    Passed: {suite.passed_count}")
            lines.append(f"    Failed: {suite.failed_count}")
            lines.append(f"    Skipped: {suite.skipped_count}")
            lines.append(f"    Duration: {suite.duration:.2f}s")
            
            # Show failed tests
            failed_tests = [tc for tc in suite.test_cBases if tc.status == 'failed']
            if failed_tests:
                lines.append("    Failed Tests:")
                for test in failed_tests:
                    lines.append(f"      - {test.name}")
                    if test.failure_message:
                        lines.append(f"        {test.failure_message}")
            lines.append("")
        
        # Coverage
        coverage = parsed_data.get('coverage')
        if coverage:
            lines.append(f"Code Coverage: {coverage.get('line_coverage', 0):.1f}%")
            lines.append("")
        
        # Issues
        issues = parsed_data.get('issues', [])
        if issues:
            lines.append(f"Issues: {len(issues)}")
            for issue in issues[:5]:  # Show first 5 issues
                lines.append(f"  - {issue['type']}: {issue['message']}")
            if len(issues) > 5:
                lines.append(f"  ... and {len(issues) - 5} more")
        
        return '\n'.join(lines)