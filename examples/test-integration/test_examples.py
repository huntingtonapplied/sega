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
SEGA: Enterprise Deployment Framework
=====================================================
File: examples/test-integration/test_examples.py
Purpose: Provides test suite for example project validation and integration testing
Dependencies: subprocess, yaml, json, pytest
Authors: FLEET Development Team
Copyright: 2022-2025 FLEET. All rights reserved.
License: Apache-2.0
Last Modified: 2025-07-25
"""

import os
import sys
import subprocess
import yaml
import json
import tempfile
import shutil
from pathlib import Path
from typing import Dict, List, Any, Optional
import pytest
import logging

# Add src to path for importing SEGA modules
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "src"))

from sega.core.template_generator import TemplateGenerator
from sega.detectors.project_detector import ProjectDetector
from sega.commands.init import InitCommand
from sega.commands.build import BuildCommand
from sega.commands.test import TestCommand

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class ExampleTestRunner:
    """Test runner for SEGA examples"""
    
    def __init__(self):
        self.examples_dir = Path(__file__).parent.parent
        self.temp_dir = None
        self.failed_tests = []
        
    def setup(self):
        """Setup test environment"""
        self.temp_dir = tempfile.mkdtemp(prefix="sega_examples_")
        logger.info(f"Created temp directory: {self.temp_dir}")
        
    def teardown(self):
        """Cleanup test environment"""
        if self.temp_dir and os.path.exists(self.temp_dir):
            shutil.rmtree(self.temp_dir)
            logger.info(f"Cleaned up temp directory: {self.temp_dir}")
            
    def find_examples(self) -> List[Path]:
        """Find all example projects"""
        examples = []
        
        for category_dir in self.examples_dir.iterdir():
            if category_dir.is_dir() and category_dir.name != "test-integration":
                for example_dir in category_dir.iterdir():
                    if example_dir.is_dir():
                        sega_yaml_path = example_dir / "sega.yaml"
                        if sega_yaml_path.exists():
                            examples.append(example_dir)
                            
        return examples
        
    def validate_sega_yaml(self, example_path: Path) -> Dict[str, Any]:
        """Validate sega.yaml configuration"""
        sega_yaml_path = example_path / "sega.yaml"
        
        try:
            with open(sega_yaml_path, 'r') as f:
                config = yaml.safe_load(f)
                
            # Basic validation
            required_fields = ['version', 'project', 'build', 'deployment']
            for field in required_fields:
                if field not in config:
                    raise ValueError(f"Missing required field: {field}")
                    
            # Project validation
            project_required = ['name', 'type', 'domain', 'team', 'description']
            for field in project_required:
                if field not in config['project']:
                    raise ValueError(f"Missing required project field: {field}")
                    
            return {
                'valid': True,
                'config': config,
                'errors': []
            }
            
        except Exception as e:
            return {
                'valid': False,
                'config': None,
                'errors': [str(e)]
            }
            
    def test_project_detection(self, example_path: Path, config: Dict[str, Any]) -> bool:
        """Test project type detection"""
        try:
            detector = ProjectDetector()
            detected_type = detector.detect_project_type(str(example_path))
            expected_type = config['project']['type']
            
            if detected_type != expected_type:
                logger.warning(f"Type mismatch in {example_path.name}: detected={detected_type}, expected={expected_type}")
                return False
                
            return True
            
        except Exception as e:
            logger.error(f"Project detection failed for {example_path.name}: {e}")
            return False
            
    def test_configuration_loading(self, example_path: Path) -> bool:
        """Test configuration loading and parsing"""
        try:
            # Copy example to temp directory
            temp_example = Path(self.temp_dir) / example_path.name
            shutil.copytree(example_path, temp_example)
            
            # Test initialization
            init_cmd = InitCommand()
            result = init_cmd.run({
                'project_path': str(temp_example),
                'template': None,
                'force': True
            })
            
            return result.get('success', False)
            
        except Exception as e:
            logger.error(f"Configuration loading failed for {example_path.name}: {e}")
            return False
            
    def test_build_validation(self, example_path: Path, config: Dict[str, Any]) -> bool:
        """Test build configuration validation"""
        try:
            build_config = config.get('build', {})
            
            # Check required build fields
            if 'strategy' not in build_config:
                logger.error(f"Missing build strategy in {example_path.name}")
                return False
                
            if 'commands' not in build_config:
                logger.error(f"Missing build commands in {example_path.name}")
                return False
                
            # Validate Docker configuration if containerized
            if build_config['strategy'] == 'containerized':
                if 'docker' not in build_config:
                    logger.error(f"Missing Docker config for containerized build in {example_path.name}")
                    return False
                    
                dockerfile_path = example_path / build_config['docker'].get('dockerfile', 'Dockerfile')
                if not dockerfile_path.exists():
                    logger.error(f"Dockerfile not found in {example_path.name}")
                    return False
                    
            return True
            
        except Exception as e:
            logger.error(f"Build validation failed for {example_path.name}: {e}")
            return False
            
    def test_deployment_configuration(self, example_path: Path, config: Dict[str, Any]) -> bool:
        """Test deployment configuration"""
        try:
            deployment_config = config.get('deployment', {})
            
            # Check targets
            if 'targets' not in deployment_config:
                logger.error(f"Missing deployment targets in {example_path.name}")
                return False
                
            targets = deployment_config['targets']
            
            # Should have at least development target
            if 'development' not in targets:
                logger.error(f"Missing development target in {example_path.name}")
                return False
                
            # Validate infrastructure requirements
            if 'infrastructure' not in deployment_config:
                logger.error(f"Missing infrastructure config in {example_path.name}")
                return False
                
            infra = deployment_config['infrastructure']
            required_infra = ['compute', 'networking']
            
            for req in required_infra:
                if req not in infra:
                    logger.error(f"Missing infrastructure.{req} in {example_path.name}")
                    return False
                    
            return True
            
        except Exception as e:
            logger.error(f"Deployment validation failed for {example_path.name}: {e}")
            return False
            
    def test_security_configuration(self, example_path: Path, config: Dict[str, Any]) -> bool:
        """Test security configuration completeness"""
        try:
            security_config = config.get('security', {})
            
            # Check vulnerability scanning
            if 'vulnerability_scanning' not in security_config:
                logger.warning(f"No vulnerability scanning config in {example_path.name}")
                
            # Check policies
            if 'policies' not in security_config:
                logger.warning(f"No security policies in {example_path.name}")
                
            return True
            
        except Exception as e:
            logger.error(f"Security validation failed for {example_path.name}: {e}")
            return False
            
    def test_monitoring_configuration(self, example_path: Path, config: Dict[str, Any]) -> bool:
        """Test monitoring configuration"""
        try:
            monitoring_config = config.get('monitoring', {})
            
            if not monitoring_config:
                logger.warning(f"No monitoring configuration in {example_path.name}")
                return True
                
            # Check metrics
            if 'metrics' in monitoring_config:
                metrics = monitoring_config['metrics']
                if not metrics.get('enabled', False):
                    logger.warning(f"Metrics not enabled in {example_path.name}")
                    
            # Check logging
            if 'logging' in monitoring_config:
                logging_config = monitoring_config['logging']
                if 'level' not in logging_config:
                    logger.warning(f"No log level specified in {example_path.name}")
                    
            return True
            
        except Exception as e:
            logger.error(f"Monitoring validation failed for {example_path.name}: {e}")
            return False
            
    def run_example_tests(self, example_path: Path) -> Dict[str, Any]:
        """Run all tests for a single example"""
        logger.info(f"Testing example: {example_path.name}")
        
        results = {
            'example': example_path.name,
            'category': example_path.parent.name,
            'path': str(example_path),
            'tests': {},
            'overall_success': True
        }
        
        # Test 1: YAML validation
        yaml_result = self.validate_sega_yaml(example_path)
        results['tests']['yaml_validation'] = yaml_result
        
        if not yaml_result['valid']:
            results['overall_success'] = False
            logger.error(f"YAML validation failed for {example_path.name}: {yaml_result['errors']}")
            return results
            
        config = yaml_result['config']
        
        # Test 2: Project detection
        detection_result = self.test_project_detection(example_path, config)
        results['tests']['project_detection'] = detection_result
        if not detection_result:
            results['overall_success'] = False
            
        # Test 3: Configuration loading
        config_result = self.test_configuration_loading(example_path)
        results['tests']['configuration_loading'] = config_result
        if not config_result:
            results['overall_success'] = False
            
        # Test 4: Build validation
        build_result = self.test_build_validation(example_path, config)
        results['tests']['build_validation'] = build_result
        if not build_result:
            results['overall_success'] = False
            
        # Test 5: Deployment configuration
        deploy_result = self.test_deployment_configuration(example_path, config)
        results['tests']['deployment_configuration'] = deploy_result
        if not deploy_result:
            results['overall_success'] = False
            
        # Test 6: Security configuration
        security_result = self.test_security_configuration(example_path, config)
        results['tests']['security_configuration'] = security_result
        if not security_result:
            results['overall_success'] = False
            
        # Test 7: Monitoring configuration
        monitoring_result = self.test_monitoring_configuration(example_path, config)
        results['tests']['monitoring_configuration'] = monitoring_result
        if not monitoring_result:
            results['overall_success'] = False

        return results
        
    def run_all_tests(self) -> Dict[str, Any]:
        """Run tests for all examples"""
        logger.info("Starting SEGA examples test suite")
        
        self.setup()
        
        try:
            examples = self.find_examples()
            logger.info(f"Found {len(examples)} examples to test")
            
            all_results = {
                'summary': {
                    'total_examples': len(examples),
                    'passed': 0,
                    'failed': 0,
                    'categories': {}
                },
                'results': []
            }
            
            for example_path in examples:
                result = self.run_example_tests(example_path)
                all_results['results'].append(result)
                
                category = result['category']
                if category not in all_results['summary']['categories']:
                    all_results['summary']['categories'][category] = {'passed': 0, 'failed': 0}
                    
                if result['overall_success']:
                    all_results['summary']['passed'] += 1
                    all_results['summary']['categories'][category]['passed'] += 1
                    logger.info(f" {example_path.name} - PASSED")
                else:
                    all_results['summary']['failed'] += 1
                    all_results['summary']['categories'][category]['failed'] += 1
                    self.failed_tests.append(example_path.name)
                    logger.error(f" {example_path.name} - FAILED")
                    
            return all_results
            
        finally:
            self.teardown()
            
    def generate_report(self, results: Dict[str, Any]) -> str:
        """Generate test report"""
        report = []
        report.append("# SEGA Examples Test Report")
        report.append(f"Generated: {os.popen('date').read().strip()}")
        report.append("")
        
        summary = results['summary']
        report.append("## Summary")
        report.append(f"- Total Examples: {summary['total_examples']}")
        report.append(f"- Passed: {summary['passed']} ")
        report.append(f"- Failed: {summary['failed']} ")
        report.append(f"- Success Rate: {(summary['passed'] / summary['total_examples'] * 100):.1f}%")
        report.append("")
        
        # Category breakdown
        report.append("## Results by Category")
        for category, stats in summary['categories'].items():
            total = stats['passed'] + stats['failed']
            success_rate = (stats['passed'] / total * 100) if total > 0 else 0
            report.append(f"- **{category}**: {stats['passed']}/{total} ({success_rate:.1f}%)")
        report.append("")
        
        # Detailed results
        report.append("## Detailed Results")
        for result in results['results']:
            status = " PASSED" if result['overall_success'] else " FAILED"
            report.append(f"### {result['example']} - {status}")
            report.append(f"Category: {result['category']}")
            report.append("")
            
            for test_name, test_result in result['tests'].items():
                if isinstance(test_result, dict):
                    if test_result.get('valid', test_result):
                        report.append(f"-  {test_name}")
                    else:
                        report.append(f"-  {test_name}")
                        if 'errors' in test_result:
                            for error in test_result['errors']:
                                report.append(f"  - Error: {error}")
                elif test_result:
                    report.append(f"-  {test_name}")
                else:
                    report.append(f"-  {test_name}")
                    
            report.append("")
            
        return "\n".join(report)


def main():
    """Main test runner"""
    runner = ExampleTestRunner()
    results = runner.run_all_tests()
    
    # Generate and save report
    report = runner.generate_report(results)
    report_path = Path(__file__).parent / "test_results.md"
    
    with open(report_path, 'w') as f:
        f.write(report)
        
    print(f"Test report saved to: {report_path}")
    
    # Print summary
    summary = results['summary']
    print(f"\n SEGA Examples Test Results:")
    print(f"   Total: {summary['total_examples']}")
    print(f"   Passed: {summary['passed']} ")
    print(f"   Failed: {summary['failed']} ")
    print(f"   Success Rate: {(summary['passed'] / summary['total_examples'] * 100):.1f}%")
    
    if runner.failed_tests:
        print(f"\n Failed tests: {', '.join(runner.failed_tests)}")
        sys.exit(1)
    else:
        print("\n All examples passed!")
        sys.exit(0)


if __name__ == "__main__":
    main()