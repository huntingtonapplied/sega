#!/usr/bin/env python3
# Copyright 2022-2026 the SEGA authors
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
File: scripts/validate_examples.py
Purpose: Provides validation utilities for example configurations and project setups
Dependencies: yaml, json, argparse, logging
Authors: SEGA Development Team
Copyright: 2022-2025 the SEGA authors. All rights reserved.
License: Apache-2.0
Last Modified: 2025-07-25
"""

import os
import sys
import yaml
import json
from pathlib import Path
from typing import Dict, List, Any
import argparse
import logging

logging.basiconfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

def find_examples(examples_dir: Path) -> List[Path]:
    """Find all example projects with sega.yaml files"""
    examples = []
    
    for category_dir in examples_dir.iterdir():
        if category_dir.is_dir() and category_dir.name != "test-integration":
            for example_dir in category_dir.iterdir():
                if example_dir.is_dir():
                    sega_yaml_path = example_dir / "sega.yaml"
                    if sega_yaml_path.exists():
                        examples.append(example_dir)
                        
    return sorted(examples)

def validate_yaml_syntax(yaml_path: Path) -> Dict[str, Any]:
    """Validate YAML syntax and basic structure"""
    try:
        with open(yaml_path, 'r') as f:
            content = f.read()
            
        # Check for template variables that should be replaced
        if '{{' in content or '}}' in content:
            logger.warning(f"Template variables found in {yaml_path.name} - this may be a template file")
            
        # Parse YAML
        config = yaml.safe_load(content)
        
        if not isinstance(config, dict):
            return {
                'valid': False,
                'errors': ['YAML root must be a dictionary'],
                'config': None
            }
            
        return {
            'valid': True,
            'errors': [],
            'config': config
        }
        
    except yaml.YAMLError as e:
        return {
            'valid': False,
            'errors': [f'YAML syntax error: {str(e)}'],
            'config': None
        }
    except Exception as e:
        return {
            'valid': False,
            'errors': [f'Error reading file: {str(e)}'],
            'config': None
        }

def validate_required_fields(config: Dict[str, Any]) -> List[str]:
    """Validate required fields in configuration"""
    errors = []
    
    # Top-level required fields
    required_top_level = ['version', 'project', 'build', 'deployment']
    for field in required_top_level:
        if field not in config:
            errors.append(f"Missing required field: {field}")
            
    # Project fields
    if 'project' in config:
        required_project = ['name', 'type', 'domain', 'team', 'description']
        for field in required_project:
            if field not in config['project']:
                errors.append(f"Missing required project field: {field}")
                
    # Build fields
    if 'build' in config:
        if 'strategy' not in config['build']:
            errors.append("Missing required build field: strategy")
        if 'commands' not in config['build']:
            errors.append("Missing required build field: commands")
            
    # Deployment fields
    if 'deployment' in config:
        if 'targets' not in config['deployment']:
            errors.append("Missing required deployment field: targets")
        elif not config['deployment']['targets']:
            errors.append("Deployment targets cannot be empty")
        else:
            # Check that development target exists
            if 'development' not in config['deployment']['targets']:
                errors.append("Missing required deployment target: development")
                
        if 'infrastructure' not in config['deployment']:
            errors.append("Missing required deployment field: infrastructure")
            
    return errors

def validate_project_type(config: Dict[str, Any]) -> List[str]:
    """Validate project type configuration"""
    errors = []
    
    if 'project' not in config:
        return errors
        
    project_type = config['project'].get('type')
    valid_types = [
        'web_app', 'ml_pipeline', 'firmware_edge', 
        'native_app', 'hdl_fpga', 'hybrid_system'
    ]
    
    if project_type not in valid_types:
        errors.append(f"Invalid project type: {project_type}. Valid types: {', '.join(valid_types)}")
        
    return errors

def validate_build_strategy(config: Dict[str, Any], example_path: Path) -> List[str]:
    """Validate build strategy configuration"""
    errors = []
    
    if 'build' not in config:
        return errors
        
    strategy = config['build'].get('strategy')
    
    if strategy == 'containerized':
        # Check for Dockerfile
        docker_config = config['build'].get('docker', {})
        dockerfile = docker_config.get('dockerfile', 'Dockerfile')
        dockerfile_path = example_path / dockerfile
        
        if not dockerfile_path.exists():
            errors.append(f"Dockerfile not found: {dockerfile}")
            
    elif strategy == 'native':
        # Check for build commands
        commands = config['build'].get('commands', {})
        if not commands:
            errors.append("Native build strategy requires build commands")
            
    return errors

def validate_security_config(config: Dict[str, Any]) -> List[str]:
    """Validate security configuration"""
    errors = []
    warnings = []
    
    security = config.get('security', {})
    
    if not security:
        warnings.append("No security configuration found - recommended for production")
        return warnings
        
    # Vulnerability scanning
    vuln_scan = security.get('vulnerability_scanning', {})
    if vuln_scan.get('enabled', False):
        scanners = vuln_scan.get('scanners', [])
        valid_scanners = ['dependency', 'static', 'container', 'dast']
        
        for scanner in scanners:
            if scanner not in valid_scanners:
                errors.append(f"Invalid security scanner: {scanner}")
                
    return errors + warnings

def validate_monitoring_config(config: Dict[str, Any]) -> List[str]:
    """Validate monitoring configuration"""
    warnings = []
    
    monitoring = config.get('monitoring', {})
    
    if not monitoring:
        warnings.append("No monitoring configuration - recommended for production")
        return warnings
        
    # Check metrics
    metrics = monitoring.get('metrics', {})
    if not metrics.get('enabled', False):
        warnings.append("Metrics collection not enabled")
        
    # Check logging
    logging_config = monitoring.get('logging', {})
    if not logging_config:
        warnings.append("No logging configuration found")
        
    return warnings

def validate_intelligence_config(config: Dict[str, Any]) -> List[str]:
    """Validate intelligence/AI configuration"""
    warnings = []
    
    intelligence = config.get('intelligence', {})
    
    if intelligence.get('enabled', False):
        features = intelligence.get('features', [])
        if not features:
            warnings.append("Intelligence enabled but no features specified")
            
        valid_features = [
            'anomaly_detection', 'predictive_scaling', 
            'optimization_suggestions', 'cost_analysis',
            'performance_insights'
        ]
        
        for feature in features:
            if feature not in valid_fFeatures:
                warnings.append(f"Unknown intelligence feature: {feature}")
                
    return warnings

def validate_example(example_path: Path) -> Dict[str, Any]:
    """Validate a single example"""
    result = {
        'name': example_path.name,
        'category': example_path.parent.name,
        'path': str(example_path),
        'valid': True,
        'errors': [],
        'warnings': []
    }
    
    sega_yaml_path = example_path / "sega.yaml"
    
    # Validate YAML syntax
    yaml_result = validate_yaml_syntax(sega_yaml_path)
    if not yaml_result['valid']:
        result['valid'] = False
        result['errors'].extend(yaml_result['errors'])
        return result
        
    config = yaml_result['config']
    
    # Validate required fields
    field_errors = validate_required_fields(config)
    if field_errors:
        result['valid'] = False
        result['errors'].extend(field_errors)
        
    # Validate project type
    type_errors = validate_project_type(config)
    if type_errors:
        result['valid'] = False
        result['errors'].extend(type_errors)
        
    # Validate build strategy
    build_errors = validate_build_strategy(config, example_path)
    if build_errors:
        result['valid'] = False
        result['errors'].extend(build_errors)
        
    # Validate security (warnings only)
    security_warnings = validate_security_config(config)
    result['warnings'].extend(security_warnings)
    
    # Validate monitoring (warnings only)
    monitoring_warnings = validate_monitoring_config(config)
    result['warnings'].extend(monitoring_warnings)
    
    # Validate intelligence (warnings only)
    intelligence_warnings = validate_intelligence_config(config)
    result['warnings'].extend(intelligence_warnings)
    
    return result

def main():
    """Main validation function"""
    parser = argparse.ArgumentParser(description='Validate SEGA example configurations')
    parser.add_argument('--examples-dir', type=Path, 
                       default=Path(__file__).parent.parent / 'examples',
                       help='Path to examples directory')
    parser.add_argument('--output', type=Path,
                       help='Output validation results to JSON file')
    parser.add_argument('--fail-on-warnings', action='store_true',
                       help='Treat warnings as errors')
    parser.add_argument('--quiet', action='store_true',
                       help='Only show errors and warnings')
    
    args = parser.parse_args()
    
    if args.quiet:
        logging.getLogger().setLevel(logging.WARNING)
        
    # Find examples
    examples = find_examples(args.examples_dir)
    
    if not examples:
        logger.error(f"No examples found in {args.examples_dir}")
        sys.exit(1)
        
    logger.info(f"Found {len(examples)} examples to validate")
    
    # Validate each example
    results = []
    total_errors = 0
    total_warnings = 0
    
    for example_path in examples:
        if not args.quiet:
            logger.info(f"Validating {example_path.name}...")
            
        result = validate_example(example_path)
        results.append(result)
        
        if result['errors']:
            total_errors += len(result['errors'])
            logger.error(f" {example_path.name}: {len(result['errors'])} errors")
            for error in result['errors']:
                logger.error(f"   - {error}")
        else:
            if not args.quiet:
                logger.info(f" {example_path.name}: Valid")
                
        if result['warnings']:
            total_warnings += len(result['warnings'])
            for warning in result['warnings']:
                logger.warning(f"  {example_path.name}: {warning}")
                
    # Summary
    valid_count = sum(1 for r in results if r['valid'])
    invalid_count = len(results) - valid_count
    
    print(f"\n Validation Results:")
    print(f"   Total Examples: {len(results)}")
    print(f"   Valid: {valid_count} ")
    print(f"   Invalid: {invalid_count} ")
    print(f"   Errors: {total_errors}")
    print(f"   Warnings: {total_warnings}")
    
    # Save results if requested
    if args.output:
        summary = {
            'timestamp': os.popen('date -Iseconds').read().strip(),
            'total': len(results),
            'valid': valid_count,
            'invalid': invalid_count,
            'total_errors': total_errors,
            'total_warnings': total_warnings,
            'results': results
        }
        
        with open(args.output, 'w') as f:
            json.dump(summary, f, indent=2)
            
        logger.info(f"Results saved to {args.output}")
        
    # Exit with appropriate code
    if invalid_count > 0:
        sys.exit(1)
    elif args.fail_on_warnings and total_warnings > 0:
        sys.exit(1)
    else:
        sys.exit(0)

if __name__ == "__main__":
    main()