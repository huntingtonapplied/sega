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
Example validation for SEGA

Validates example projects and configurations.
Ported from scripts/validate_examples.py with enhanced functionality.
"""

from pathlib import Path
from typing import Any, List, Optional
import logging

from .base import BaseValidator, ValidationResult
from .config_validator import ConfigValidator

logger = logging.getLogger(__name__)


class ExampleValidator(BaseValidator):
    """Validates SEGA example projects"""
    
    def __init__(self):
        super().__init__("ExampleValidator")
        self.config_validator = ConfigValidator()
    
    def validate(self, target: Any, **kwargs) -> ValidationResult:
        """Validate examples"""
        if isinstance(target, (str, Path)):
            path = Path(target)
            if path.is_file():
                # Single example validation
                return self.validate_file(path, **kwargs)
            elif path.is_dir():
                # Check if it's an example directory or examples root
                if (path / "sega.yaml").exists():
                    # Single example directory
                    return self.validate_example(path)
                else:
                    # Examples root directory
                    return self.validate_examples_directory(path)
        
        # Invalid target
        result = ValidationResult(
            valid=False,
            validator_name=self.name,
            target=str(target)
        )
        result.add_error(f"Invalid validation target: {target}")
        return result
    
    def _validate_file_content(self, filepath: Path, result: ValidationResult, **kwargs) -> ValidationResult:
        """Validate a file within an example"""
        # Delegate to config validator for sega.yaml files
        if filepath.name == "sega.yaml":
            config_result = self.config_validator.validate_file(filepath, **kwargs)
            result.merge(config_result)
        
        return result
    
    def validate_examples_directory(self, examples_dir: Path) -> ValidationResult:
        """Validate all examples in a directory"""
        result = ValidationResult(
            valid=True,
            validator_name=self.name,
            target=str(examples_dir)
        )
        
        if not examples_dir.exists():
            result.add_error(f"Examples directory not found: {examples_dir}")
            return result
        
        # Find all example projects
        examples = self._find_examples(examples_dir)
        
        if not examples:
            result.add_warning(f"No examples found in {examples_dir}")
            return result
        
        logger.info(f"Found {len(examples)} examples to validate")
        
        # Validate each example
        valid_count = 0
        for example_path in examples:
            example_result = self.validate_example(example_path)
            
            if example_result.valid:
                valid_count += 1
                logger.info(f" {example_path.name}: Valid")
            else:
                logger.error(f" {example_path.name}: {example_result.error_count} errors")
            
            result.merge(example_result)
        
        # Add summary metadata
        result.metadata['total_examples'] = len(examples)
        result.metadata['valid_examples'] = valid_count
        result.metadata['invalid_examples'] = len(examples) - valid_count
        
        return result
    
    def validate_example(self, example_path: Path) -> ValidationResult:
        """Validate a single example project"""
        result = ValidationResult(
            valid=True,
            validator_name=self.name,
            target=str(example_path)
        )
        
        result.metadata['name'] = example_path.name
        result.metadata['category'] = example_path.parent.name
        
        if not example_path.exists():
            result.add_error(f"Example path not found: {example_path}")
            return result
        
        if not example_path.is_dir():
            result.add_error(f"Example path is not a directory: {example_path}")
            return result
        
        # Check for sega.yaml
        sega_yaml_path = example_path / "sega.yaml"
        if not sega_yaml_path.exists():
            result.add_error("Missing sega.yaml configuration file")
            return result
        
        # Validate sega.yaml
        config_result = self.config_validator.validate_file(sega_yaml_path)
        result.merge(config_result)
        
        # Validate example structure
        self._validate_example_structure(example_path, result)
        
        # Validate example completeness
        self._validate_example_completeness(example_path, result)
        
        return result
    
    def _find_examples(self, examples_dir: Path) -> List[Path]:
        """Find all example projects with sega.yaml files"""
        examples = []
        
        # Look for category directories
        for category_dir in examples_dir.iterdir():
            if category_dir.is_dir() and not category_dir.name.startswith('.'):
                # Skip test directories
                if category_dir.name in ['test-integration', 'tests', '__pycache__']:
                    continue
                
                # Look for example projects
                for example_dir in category_dir.iterdir():
                    if example_dir.is_dir() and not example_dir.name.startswith('.'):
                        sega_yaml_path = example_dir / "sega.yaml"
                        if sega_yaml_path.exists():
                            examples.append(example_dir)
        
        return sorted(examples)
    
    def _validate_example_structure(self, example_path: Path, result: ValidationResult) -> None:
        """Validate example project structure"""
        # Check for README
        readme_files = ['README.md', 'readme.md', 'README.rst', 'readme.rst']
        has_readme = any((example_path / f).exists() for f in readme_files)
        
        if not has_readme:
            result.add_warning(
                "No README file found",
                suggestion="Add a README.md to explain the example"
            )
        
        # Check for common project files based on project type
        config = self.config_validator.load_yaml(example_path / "sega.yaml")
        if config and 'project' in config:
            project_type = config['project'].get('type')
            self._validate_project_type_structure(example_path, project_type, result)
    
    def _validate_project_type_structure(self, example_path: Path, 
                                       project_type: Optional[str], 
                                       result: ValidationResult) -> None:
        """Validate structure based on project type"""
        if not project_type:
            return
        
        expected_files = {
            'web_app': ['package.json', 'Dockerfile', 'src/', 'public/'],
            'ml_pipeline': ['requirements.txt', 'Dockerfile', 'src/', 'models/'],
            'firmware_edge': ['Makefile', 'src/', 'include/', 'platformio.ini'],
            'native_app': ['Makefile', 'CMakeLists.txt', 'src/', 'include/'],
            'hdl_fpga': ['Makefile', 'src/', 'constraints/', 'testbench/'],
            'hybrid_system': ['Makefile', 'components/', 'docker-compose.yml']
        }
        
        if project_type in expected_files:
            for expected in expected_files[project_type]:
                path = example_path / expected
                if not path.exists():
                    # This is just informational - not all files are required
                    logger.debug(f"Expected file/dir not found for {project_type}: {expected}")
    
    def _validate_example_completeness(self, example_path: Path, result: ValidationResult) -> None:
        """Validate that example is complete and runnable"""
        config = self.config_validator.load_yaml(example_path / "sega.yaml")
        if not config:
            return
        
        # Check build configuration
        build = config.get('build', {})
        if build.get('strategy') == 'containerized':
            dockerfile = build.get('docker', {}).get('dockerfile', 'Dockerfile')
            if not (example_path / dockerfile).exists():
                result.add_error(
                    f"Dockerfile not found: {dockerfile}",
                    suggestion="Add Dockerfile or update build configuration"
                )
        
        # Check for .gitignore
        if not (example_path / '.gitignore').exists():
            result.add_warning(
                "No .gitignore file found",
                suggestion="Add .gitignore to exclude build artifacts"
            )
        
        # Check for tests
        test_dirs = ['tests', 'test', 'spec']
        has_tests = any((example_path / d).exists() for d in test_dirs)
        
        if not has_tests:
            # Check for test files
            test_patterns = ['*_test.py', 'test_*.py', '*_spec.js', '*.test.js']
            has_test_files = False
            for pattern in test_patterns:
                if list(example_path.rglob(pattern)):
                    has_test_files = True
                    break
            
            if not has_test_files:
                result.add_warning(
                    "No tests found",
                    suggestion="Add tests to demonstrate testing approach"
                )