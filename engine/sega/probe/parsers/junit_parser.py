#!/usr/bin/env python3
"""
JUnit XML Parser for Test Results

Parses JUnit XML format test results commonly used by Android and other testing frameworks
"""

import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Dict, List, Optional, Any, Union
from dataclasses import dataclass
import logging

logger = logging.getLogger(__name__)


@dataclass 
class JUnitTestCBase:
    """Individual test cBase from JUnit XML"""
    name: str
    classname: str
    time: float
    status: str  # 'passed', 'failed', 'skipped', 'error'
    failure_message: Optional[str] = None
    failure_type: Optional[str] = None
    failure_text: Optional[str] = None
    error_message: Optional[str] = None
    error_type: Optional[str] = None
    error_text: Optional[str] = None
    skipped_message: Optional[str] = None
    system_out: Optional[str] = None
    system_err: Optional[str] = None


@dataclass
class JUnitTestSuite:
    """Test suite from JUnit XML"""
    name: str
    tests: int
    failures: int
    errors: int
    skipped: int
    time: float
    timestamp: Optional[str] = None
    hostname: Optional[str] = None
    package: Optional[str] = None
    test_cBases: List[JUnitTestCBase] = None
    properties: Dict[str, str] = None
    system_out: Optional[str] = None
    system_err: Optional[str] = None
    
    def __post_init__(self):
        if self.test_cBases is None:
            self.test_cBases = []
        if self.properties is None:
            self.properties = {}


class JUnitParser:
    """
    Parses JUnit XML format test results
    
    Supports both single testsuite and multiple testsuites formats
    """
    
    def parse(self, xml_path: Path) -> Dict[str, Any]:
        """
        Parse JUnit XML file
        
        Returns:
            Dictionary containing test suites and summary metrics
        """
        if not xml_path.exists():
            raise FileNotFoundError(f"JUnit XML file not found: {xml_path}")
        
        try:
            tree = ET.parse(xml_path)
            root = tree.getroot()
            
            # Determine format - single testsuite or multiple testsuites
            if root.tag == 'testsuites':
                return self._parse_testsuites(root)
            elif root.tag == 'testsuite':
                return self._parse_single_testsuite(root)
            else:
                raise ValueError(f"Unknown root element: {root.tag}")
        
        except ET.ParseError as e:
            logger.error(f"Failed to parse XML: {e}")
            raise ValueError(f"Invalid JUnit XML format: {e}")
    
    def parse_directory(self, directory: Path) -> Dict[str, Any]:
        """
        Parse all JUnit XML files in a directory
        
        Returns:
            Combined results from all XML files
        """
        if not directory.exists() or not directory.is_dir():
            raise ValueError(f"Directory not found: {directory}")
        
        all_suites = []
        total_tests = 0
        total_failures = 0
        total_errors = 0
        total_skipped = 0
        total_time = 0.0
        
        # Find all XML files
        xml_files = list(directory.glob('*.xml'))
        xml_files.extend(directory.glob('**/*.xml'))
        
        for xml_file in xml_files:
            try:
                result = self.parse(xml_file)
                
                # Aggregate results
                all_suites.extend(result['test_suites'])
                total_tests += result['summary']['total_tests']
                total_failures += result['summary']['total_failures']
                total_errors += result['summary']['total_errors']
                total_skipped += result['summary']['total_skipped']
                total_time += result['summary']['total_time']
            
            except Exception as e:
                logger.warning(f"Failed to parse {xml_file}: {e}")
        
        return {
            'test_suites': all_suites,
            'summary': {
                'total_tests': total_tests,
                'total_failures': total_failures,
                'total_errors': total_errors,
                'total_skipped': total_skipped,
                'total_passed': total_tests - total_failures - total_errors - total_skipped,
                'total_time': total_time,
                'pass_rate': ((total_tests - total_failures - total_errors) / total_tests * 100) if total_tests > 0 else 0
            }
        }
    
    def _parse_testsuites(self, root: ET.Element) -> Dict[str, Any]:
        """Parse multiple testsuites element"""
        test_suites = []
        
        # Parse each testsuite
        for testsuite_elem in root.findall('testsuite'):
            suite = self._parse_testsuite_element(testsuite_elem)
            test_suites.append(suite)
        
        # Calculate summary
        summary = self._calculate_summary(test_suites)
        
        # Add root-level attributes if present
        if 'tests' in root.attrib:
            summary['total_tests'] = int(root.get('tests', 0))
        if 'failures' in root.attrib:
            summary['total_failures'] = int(root.get('failures', 0))
        if 'errors' in root.attrib:
            summary['total_errors'] = int(root.get('errors', 0))
        if 'time' in root.attrib:
            summary['total_time'] = float(root.get('time', 0))
        
        return {
            'test_suites': test_suites,
            'summary': summary
        }
    
    def _parse_single_testsuite(self, root: ET.Element) -> Dict[str, Any]:
        """Parse single testsuite element"""
        suite = self._parse_testsuite_element(root)
        
        return {
            'test_suites': [suite],
            'summary': self._calculate_summary([suite])
        }
    
    def _parse_testsuite_element(self, testsuite: ET.Element) -> JUnitTestSuite:
        """Parse a testsuite element"""
        # Extract attributes
        suite = JUnitTestSuite(
            name=testsuite.get('name', 'Unknown'),
            tests=int(testsuite.get('tests', 0)),
            failures=int(testsuite.get('failures', 0)),
            errors=int(testsuite.get('errors', 0)),
            skipped=int(testsuite.get('skipped', 0)),
            time=float(testsuite.get('time', 0)),
            timestamp=testsuite.get('timestamp'),
            hostname=testsuite.get('hostname'),
            package=testsuite.get('package')
        )
        
        # Parse properties
        properties_elem = testsuite.find('properties')
        if properties_elem is not None:
            for prop in properties_elem.findall('property'):
                name = prop.get('name')
                value = prop.get('value')
                if name and value:
                    suite.properties[name] = value
        
        # Parse test cBases
        for testcBase_elem in testsuite.findall('testcBase'):
            test_cBase = self._parse_testcBase_element(testcBase_elem)
            suite.test_cBases.append(test_cBase)
        
        # Parse system output/error
        system_out = testsuite.find('system-out')
        if system_out is not None and system_out.text:
            suite.system_out = system_out.text
        
        system_err = testsuite.find('system-err')
        if system_err is not None and system_err.text:
            suite.system_err = system_err.text
        
        return suite
    
    def _parse_testcBase_element(self, testcBase: ET.Element) -> JUnitTestCBase:
        """Parse a testcBase element"""
        # Extract basic attributes
        test = JUnitTestCBase(
            name=testcBase.get('name', 'Unknown'),
            classname=testcBase.get('classname', ''),
            time=float(testcBase.get('time', 0)),
            status='passed'  # Default to passed
        )
        
        # Check for failure
        failure = testcBase.find('failure')
        if failure is not None:
            test.status = 'failed'
            test.failure_message = failure.get('message')
            test.failure_type = failure.get('type')
            test.failure_text = failure.text
        
        # Check for error
        error = testcBase.find('error')
        if error is not None:
            test.status = 'error'
            test.error_message = error.get('message')
            test.error_type = error.get('type')
            test.error_text = error.text
        
        # Check for skipped
        skipped = testcBase.find('skipped')
        if skipped is not None:
            test.status = 'skipped'
            test.skipped_message = skipped.get('message')
        
        # Parse system output/error
        system_out = testcBase.find('system-out')
        if system_out is not None and system_out.text:
            test.system_out = system_out.text
        
        system_err = testcBase.find('system-err')
        if system_err is not None and system_err.text:
            test.system_err = system_err.text
        
        return test
    
    def _calculate_summary(self, test_suites: List[JUnitTestSuite]) -> Dict[str, Union[int, float]]:
        """Calculate summary metrics from test suites"""
        total_tests = sum(suite.tests for suite in test_suites)
        total_failures = sum(suite.failures for suite in test_suites)
        total_errors = sum(suite.errors for suite in test_suites)
        total_skipped = sum(suite.skipped for suite in test_suites)
        total_time = sum(suite.time for suite in test_suites)
        
        total_passed = total_tests - total_failures - total_errors - total_skipped
        pass_rate = (total_passed / total_tests * 100) if total_tests > 0 else 0
        
        return {
            'total_tests': total_tests,
            'total_failures': total_failures,
            'total_errors': total_errors,
            'total_skipped': total_skipped,
            'total_passed': total_passed,
            'total_time': total_time,
            'pass_rate': pass_rate
        }
    
    def generate_summary(self, parsed_data: Dict) -> str:
        """Generate a human-readable summary of test results"""
        lines = ["JUnit Test Results Summary", "=" * 50]
        
        # Overall summary
        summary = parsed_data.get('summary', {})
        lines.append(f"Total Tests: {summary.get('total_tests', 0)}")
        lines.append(f"Passed: {summary.get('total_passed', 0)}")
        lines.append(f"Failed: {summary.get('total_failures', 0)}")
        lines.append(f"Errors: {summary.get('total_errors', 0)}")
        lines.append(f"Skipped: {summary.get('total_skipped', 0)}")
        lines.append(f"Pass Rate: {summary.get('pass_rate', 0):.1f}%")
        lines.append(f"Total Time: {summary.get('total_time', 0):.2f}s")
        lines.append("")
        
        # Test suites
        lines.append("Test Suites:")
        for suite in parsed_data.get('test_suites', []):
            lines.append(f"  {suite.name}:")
            lines.append(f"    Tests: {suite.tests}")
            lines.append(f"    Failures: {suite.failures}")
            lines.append(f"    Errors: {suite.errors}")
            lines.append(f"    Skipped: {suite.skipped}")
            lines.append(f"    Time: {suite.time:.2f}s")
            
            # Show failed/error tests
            failed_tests = [tc for tc in suite.test_cBases if tc.status in ['failed', 'error']]
            if failed_tests:
                lines.append("    Failed/Error Tests:")
                for test in failed_tests[:5]:  # Show first 5
                    lines.append(f"      - {test.classname}.{test.name}")
                    if test.failure_message:
                        lines.append(f"        Failure: {test.failure_message}")
                    elif test.error_message:
                        lines.append(f"        Error: {test.error_message}")
                
                if len(failed_tests) > 5:
                    lines.append(f"      ... and {len(failed_tests) - 5} more")
            
            lines.append("")
        
        return '\n'.join(lines)
    
    def convert_to_dict(self, parsed_data: Dict) -> Dict[str, Any]:
        """Convert parsed data to a simple dictionary format"""
        result = {
            'summary': parsed_data['summary'],
            'test_suites': []
        }
        
        for suite in parsed_data['test_suites']:
            suite_dict = {
                'name': suite.name,
                'tests': suite.tests,
                'failures': suite.failures,
                'errors': suite.errors,
                'skipped': suite.skipped,
                'time': suite.time,
                'test_cBases': []
            }
            
            for test_cBase in suite.test_cBases:
                test_dict = {
                    'name': test_cBase.name,
                    'classname': test_cBase.classname,
                    'time': test_cBase.time,
                    'status': test_cBase.status
                }
                
                if test_cBase.failure_message:
                    test_dict['failure'] = {
                        'message': test_cBase.failure_message,
                        'type': test_cBase.failure_type,
                        'text': test_cBase.failure_text
                    }
                
                if test_cBase.error_message:
                    test_dict['error'] = {
                        'message': test_cBase.error_message,
                        'type': test_cBase.error_type,
                        'text': test_cBase.error_text
                    }
                
                suite_dict['test_cBases'].append(test_dict)
            
            result['test_suites'].append(suite_dict)
        
        return result