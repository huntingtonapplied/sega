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
Base validation framework for SEGA

Provides abstract base classes and common functionality for all validators.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Union
import json
import yaml
import logging

logger = logging.getLogger(__name__)


class ValidationLevel(Enum):
    """Severity levels for validation issues"""
    ERROR = "error"
    WARNING = "warning"
    INFO = "info"


@dataclass
class ValidationIssue:
    """Represents a single validation issue"""
    level: ValidationLevel
    message: str
    path: Optional[str] = None
    line: Optional[int] = None
    column: Optional[int] = None
    code: Optional[str] = None
    suggestion: Optional[str] = None


@dataclass
class ValidationResult:
    """Results of a validation operation"""
    valid: bool
    issues: List[ValidationIssue] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)
    timestamp: datetime = field(default_factory=datetime.now)
    validator_name: Optional[str] = None
    target: Optional[str] = None
    
    @property
    def errors(self) -> List[ValidationIssue]:
        """Get all error-level issues"""
        return [i for i in self.issues if i.level == ValidationLevel.ERROR]
    
    @property
    def warnings(self) -> List[ValidationIssue]:
        """Get all warning-level issues"""
        return [i for i in self.issues if i.level == ValidationLevel.WARNING]
    
    @property
    def error_count(self) -> int:
        """Get count of errors"""
        return len(self.errors)
    
    @property
    def warning_count(self) -> int:
        """Get count of warnings"""
        return len(self.warnings)
    
    def add_error(self, message: str, **kwargs) -> None:
        """Add an error issue"""
        self.issues.append(ValidationIssue(
            level=ValidationLevel.ERROR,
            message=message,
            **kwargs
        ))
        self.valid = False
    
    def add_warning(self, message: str, **kwargs) -> None:
        """Add a warning issue"""
        self.issues.append(ValidationIssue(
            level=ValidationLevel.WARNING,
            message=message,
            **kwargs
        ))
    
    def add_info(self, message: str, **kwargs) -> None:
        """Add an info issue"""
        self.issues.append(ValidationIssue(
            level=ValidationLevel.INFO,
            message=message,
            **kwargs
        ))
    
    def merge(self, other: 'ValidationResult') -> None:
        """Merge another validation result into this one"""
        self.issues.extend(other.issues)
        self.valid = self.valid and other.valid
        self.metadata.update(other.metadata)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary representation"""
        return {
            'valid': self.valid,
            'timestamp': self.timestamp.isoformat(),
            'validator_name': self.validator_name,
            'target': self.target,
            'error_count': self.error_count,
            'warning_count': self.warning_count,
            'issues': [
                {
                    'level': issue.level.value,
                    'message': issue.message,
                    'path': issue.path,
                    'line': issue.line,
                    'column': issue.column,
                    'code': issue.code,
                    'suggestion': issue.suggestion
                }
                for issue in self.issues
            ],
            'metadata': self.metadata
        }
    
    def to_json(self, indent: int = 2) -> str:
        """Convert to JSON string"""
        return json.dumps(self.to_dict(), indent=indent)
    
    def print_summary(self, verbose: bool = False) -> None:
        """Print a summary of validation results"""
        status = "[OK] VALID" if self.valid else "[ERROR] INVALID"
        print(f"\n{status} - {self.target or 'Validation'}")
        
        if self.error_count > 0:
            print(f"  Errors: {self.error_count}")
        if self.warning_count > 0:
            print(f"  Warnings: {self.warning_count}")
        
        if verbose or not self.valid:
            for issue in self.issues:
                level_symbol = {
                    ValidationLevel.ERROR: "[ERROR]",
                    ValidationLevel.WARNING: "[WARNING]",
                    ValidationLevel.INFO: "[INFO]"
                }[issue.level]
                
                location = ""
                if issue.path:
                    location = f" [{issue.path}"
                    if issue.line:
                        location += f":{issue.line}"
                        if issue.column:
                            location += f":{issue.column}"
                    location += "]"
                
                print(f"  {level_symbol} {issue.message}{location}")
                if issue.suggestion:
                    print(f"    → {issue.suggestion}")


class ValidationError(Exception):
    """Exception raised for validation errors"""
    pass


class ValidationWarning(Warning):
    """Warning raised for validation issues"""
    pass


class BaseValidator(ABC):
    """Abstract base class for all validators"""
    
    def __init__(self, name: Optional[str] = None):
        self.name = name or self.__class__.__name__
        self._cache: Dict[str, Any] = {}
        self._validated_paths: Set[Path] = set()
    
    @abstractmethod
    def validate(self, target: Any, **kwargs) -> ValidationResult:
        """Validate a target (file, directory, object, etc.)"""
        pass
    
    def validate_file(self, filepath: Path, **kwargs) -> ValidationResult:
        """Validate a single file"""
        if not isinstance(filepath, Path):
            filepath = Path(filepath)
        
        result = ValidationResult(
            valid=True,
            validator_name=self.name,
            target=str(filepath)
        )
        
        if not filepath.exists():
            result.add_error(f"File not found: {filepath}")
            return result
        
        if not filepath.is_file():
            result.add_error(f"Not a file: {filepath}")
            return result
        
        # Mark as validated
        self._validated_paths.add(filepath)
        
        # Delegate to specific validation logic
        return self._validate_file_content(filepath, result, **kwargs)
    
    def validate_directory(self, directory: Path, pattern: str = "*", 
                         recursive: bool = True, **kwargs) -> ValidationResult:
        """Validate all matching files in a directory"""
        if not isinstance(directory, Path):
            directory = Path(directory)
        
        result = ValidationResult(
            valid=True,
            validator_name=self.name,
            target=str(directory)
        )
        
        if not directory.exists():
            result.add_error(f"Directory not found: {directory}")
            return result
        
        if not directory.is_dir():
            result.add_error(f"Not a directory: {directory}")
            return result
        
        # Find matching files
        if recursive:
            files = list(directory.rglob(pattern))
        else:
            files = list(directory.glob(pattern))
        
        if not files:
            result.add_warning(f"No files matching pattern '{pattern}' found in {directory}")
            return result
        
        # Validate each file
        for filepath in files:
            if filepath.is_file():
                file_result = self.validate_file(filepath, **kwargs)
                result.merge(file_result)
        
        result.metadata['total_files'] = len(files)
        result.metadata['validated_files'] = len([f for f in files if f in self._validated_paths])
        
        return result
    
    @abstractmethod
    def _validate_file_content(self, filepath: Path, result: ValidationResult, **kwargs) -> ValidationResult:
        """Validate the content of a specific file"""
        pass
    
    def load_yaml(self, filepath: Path) -> Union[Dict[str, Any], None]:
        """Load and parse a YAML file"""
        try:
            with open(filepath, 'r') as f:
                return yaml.safe_load(f)
        except yaml.YAMLError as e:
            logger.error(f"YAML parse error in {filepath}: {e}")
            return None
        except Exception as e:
            logger.error(f"Error reading {filepath}: {e}")
            return None
    
    def load_json(self, filepath: Path) -> Union[Dict[str, Any], None]:
        """Load and parse a JSON file"""
        try:
            with open(filepath, 'r') as f:
                return json.load(f)
        except json.JSONDecodeError as e:
            logger.error(f"JSON parse error in {filepath}: {e}")
            return None
        except Exception as e:
            logger.error(f"Error reading {filepath}: {e}")
            return None
    
    def clear_cache(self) -> None:
        """Clear the validator cache"""
        self._cache.clear()
        self._validated_paths.clear()