#!/usr/bin/env python3
"""
SEGA CLI Entry Point Detector
==============================
Intelligently detects and tests CLI entry points in Python projects.
Part of SEGA's comprehensive testing infrastructure.
"""

import ast
import subprocess
import json
from pathlib import Path
from typing import Dict, List, Optional, Any
from dataclasses import dataclass
import logging

logger = logging.getLogger(__name__)


@dataclass
class CLIEntryPoint:
    """Represents a detected CLI entry point."""
    file_path: Path
    entry_type: str  # 'main', 'argparse', 'click', 'fire', 'custom'
    commands: List[str]
    arguments: Dict[str, Any]
    docstring: Optional[str]
    test_vectors: List[Dict[str, Any]]


@dataclass 
class CLITestResult:
    """Result of testing a CLI entry point."""
    entry_point: CLIEntryPoint
    command: str
    success: bool
    stdout: str
    stderr: str
    return_code: int
    duration: float
    validation_passed: bool


class CLIEntryDetector:
    """Detects and analyzes CLI entry points in Python projects."""
    
    def __init__(self, project_path: str = "."):
        self.project_path = Path(project_path).resolve()
        self.entry_points: List[CLIEntryPoint] = []
        
    def detect_all_entry_points(self) -> List[CLIEntryPoint]:
        """Scan project for all CLI entry points."""
        python_files = list(self.project_path.rglob("*.py"))
        
        for py_file in python_files:
            # Skip test files and migrations
            if any(skip in str(py_file) for skip in ['test_', '__pycache__', 'migrations']):
                continue
                
            try:
                entry_point = self.analyze_file(py_file)
                if entry_point:
                    self.entry_points.append(entry_point)
            except Exception as e:
                logger.debug(f"Could not analyze {py_file}: {e}")
                
        return self.entry_points
    
    def analyze_file(self, file_path: Path) -> Optional[CLIEntryPoint]:
        """Analyze a Python file for CLI entry points."""
        try:
            with open(file_path, 'r') as f:
                content = f.read()
                
            # Quick check for main entry
            if '__name__' not in content or '__main__' not in content:
                return None
                
            tree = ast.parse(content)
            
            # Detect CLI framework
            cli_type = self.detect_cli_framework(tree, content)
            if not cli_type:
                return None
                
            # Extract commands and arguments
            commands = self.extract_commands(tree, cli_type)
            arguments = self.extract_arguments(tree, cli_type)
            
            # Get module docstring
            docstring = ast.get_docstring(tree)
            
            # Generate test vectors
            test_vectors = self.generate_test_vectors(commands, arguments)
            
            return CLIEntryPoint(
                file_path=file_path,
                entry_type=cli_type,
                commands=commands,
                arguments=arguments,
                docstring=docstring,
                test_vectors=test_vectors
            )
            
        except Exception as e:
            logger.debug(f"Error analyzing {file_path}: {e}")
            return None
    
    def detect_cli_framework(self, tree: ast.AST, content: str) -> Optional[str]:
        """Detect which CLI framework is being used."""
        imports = self.get_imports(tree)
        
        # Check for various CLI frameworks
        if 'argparse' in imports or 'ArgumentParser' in content:
            return 'argparse'
        elif 'click' in imports or '@click.' in content:
            return 'click'
        elif 'fire' in imports or 'fire.Fire' in content:
            return 'fire'
        elif 'typer' in imports or 'typer.' in content:
            return 'typer'
        elif 'if __name__ == "__main__"' in content:
            return 'main'
        
        return None
    
    def get_imports(self, tree: ast.AST) -> set:
        """Extract all imports from AST."""
        imports = set()
        
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for name in node.names:
                    imports.add(name.name.split('.')[0])
            elif isinstance(node, ast.ImportFrom):
                if node.module:
                    imports.add(node.module.split('.')[0])
                    
        return imports
    
    def extract_commands(self, tree: ast.AST, cli_type: str) -> List[str]:
        """Extract available commands based on CLI framework."""
        commands = []
        
        if cli_type == 'argparse':
            commands = self.extract_argparse_commands(tree)
        elif cli_type == 'click':
            commands = self.extract_click_commands(tree)
        elif cli_type == 'fire':
            commands = self.extract_fire_commands(tree)
        else:
            # Default to basic commands
            commands = ['--help', '--version']
            
        return commands
    
    def extract_argparse_commands(self, tree: ast.AST) -> List[str]:
        """Extract commands from argparse-based CLI."""
        commands = []
        
        for node in ast.walk(tree):
            if isinstance(node, ast.Call):
                # Look for add_argument calls
                if (hasattr(node.func, 'attr') and 
                    node.func.attr == 'add_argument'):
                    for arg in node.args:
                        if isinstance(arg, ast.Constant):
                            cmd = arg.value
                            if isinstance(cmd, str) and cmd.startswith('-'):
                                commands.append(cmd)
                                
                # Look for add_subparsers
                elif (hasattr(node.func, 'attr') and 
                      node.func.attr == 'add_parser'):
                    if node.args and isinstance(node.args[0], ast.Constant):
                        commands.append(node.args[0].value)
                        
        return list(set(commands))
    
    def extract_click_commands(self, tree: ast.AST) -> List[str]:
        """Extract commands from click-based CLI."""
        commands = []
        
        for node in ast.walk(tree):
            if isinstance(node, ast.FunctionDef):
                # Check for click decorators
                for decorator in node.decorator_list:
                    if isinstance(decorator, ast.Attribute):
                        if decorator.attr == 'command':
                            commands.append(node.name)
                    elif isinstance(decorator, ast.Call):
                        if (hasattr(decorator.func, 'attr') and 
                            decorator.func.attr in ['command', 'group']):
                            commands.append(node.name)
                            
        return commands
    
    def extract_fire_commands(self, tree: ast.AST) -> List[str]:
        """Extract commands from fire-based CLI."""
        commands = []
        
        # In Fire, public methods become commands
        for node in ast.walk(tree):
            if isinstance(node, ast.ClassDef):
                for item in node.body:
                    if isinstance(item, ast.FunctionDef):
                        if not item.name.startswith('_'):
                            commands.append(item.name)
                            
        return commands
    
    def extract_arguments(self, tree: ast.AST, cli_type: str) -> Dict[str, Any]:
        """Extract CLI arguments and their properties."""
        arguments = {}
        
        if cli_type == 'argparse':
            arguments = self.extract_argparse_arguments(tree)
        elif cli_type == 'click':
            arguments = self.extract_click_arguments(tree)
            
        return arguments
    
    def extract_argparse_arguments(self, tree: ast.AST) -> Dict[str, Any]:
        """Extract arguments from argparse CLI."""
        arguments = {}
        
        for node in ast.walk(tree):
            if isinstance(node, ast.Call):
                if (hasattr(node.func, 'attr') and 
                    node.func.attr == 'add_argument'):
                    
                    # Get argument name
                    arg_name = None
                    if node.args and isinstance(node.args[0], ast.Constant):
                        arg_name = node.args[0].value
                        
                    if arg_name:
                        arg_info = {'name': arg_name}
                        
                        # Extract keyword arguments
                        for keyword in node.keywords:
                            if keyword.arg == 'type':
                                arg_info['type'] = 'type'
                            elif keyword.arg == 'help':
                                if isinstance(keyword.value, ast.Constant):
                                    arg_info['help'] = keyword.value.value
                            elif keyword.arg == 'default':
                                if isinstance(keyword.value, ast.Constant):
                                    arg_info['default'] = keyword.value.value
                            elif keyword.arg == 'required':
                                arg_info['required'] = True
                            elif keyword.arg == 'choices':
                                arg_info['choices'] = []
                                
                        arguments[arg_name] = arg_info
                        
        return arguments
    
    def extract_click_arguments(self, tree: ast.AST) -> Dict[str, Any]:
        """Extract arguments from click CLI."""
        arguments = {}
        
        for node in ast.walk(tree):
            if isinstance(node, ast.FunctionDef):
                for decorator in node.decorator_list:
                    if isinstance(decorator, ast.Call):
                        if (hasattr(decorator.func, 'attr') and 
                            decorator.func.attr in ['option', 'argument']):
                            
                            # Extract option/argument details
                            if decorator.args:
                                arg_name = None
                                if isinstance(decorator.args[0], ast.Constant):
                                    arg_name = decorator.args[0].value
                                    
                                if arg_name:
                                    arguments[arg_name] = {
                                        'name': arg_name,
                                        'type': decorator.func.attr
                                    }
                                    
        return arguments
    
    def generate_test_vectors(self, commands: List[str], 
                            arguments: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Generate test vectors for CLI testing."""
        test_vectors = []
        
        # Always test help
        test_vectors.append({
            'command': '--help',
            'expected_return': 0,
            'validate_output': lambda out: 'usage' in out.lower() or 'help' in out.lower()
        })
        
        # Test each command
        for cmd in commands:
            if cmd != '--help':
                test_vectors.append({
                    'command': cmd,
                    'args': '--help',
                    'expected_return': 0,
                    'validate_output': lambda out: cmd in out or 'help' in out.lower()
                })
                
        # Test with various argument combinations
        if arguments:
            # Test required arguments missing
            required_args = [arg for arg, info in arguments.items() 
                           if info.get('required')]
            if required_args:
                test_vectors.append({
                    'command': '',
                    'expected_return': 2,  # Typical argparse error code
                    'validate_output': lambda out: 'required' in out.lower() or 'error' in out.lower()
                })
                
        return test_vectors


class CLITestRunner:
    """Runs tests against detected CLI entry points."""
    
    def __init__(self, project_path: str = "."):
        self.project_path = Path(project_path).resolve()
        self.detector = CLIEntryDetector(project_path)
        
    def run_all_tests(self) -> List[CLITestResult]:
        """Detect and test all CLI entry points."""
        entry_points = self.detector.detect_all_entry_points()
        results = []
        
        for entry_point in entry_points:
            logger.info(f"Testing CLI: {entry_point.file_path}")
            
            for test_vector in entry_point.test_vectors:
                result = self.run_test(entry_point, test_vector)
                results.append(result)
                
        return results
    
    def run_test(self, entry_point: CLIEntryPoint, 
                test_vector: Dict[str, Any]) -> CLITestResult:
        """Run a single test against a CLI entry point."""
        import time
        
        # Build command
        cmd = ['python', str(entry_point.file_path)]
        
        if test_vector.get('command'):
            cmd.append(test_vector['command'])
        if test_vector.get('args'):
            if isinstance(test_vector['args'], list):
                cmd.extend(test_vector['args'])
            else:
                cmd.append(test_vector['args'])
                
        # Run the command
        start_time = time.time()
        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=30,
                cwd=self.project_path
            )
            duration = time.time() - start_time
            
            # Validate output if validator provided
            validation_passed = True
            if 'validate_output' in test_vector:
                validator = test_vector['validate_output']
                validation_passed = validator(result.stdout + result.stderr)
                
            # Check expected return code
            if 'expected_return' in test_vector:
                expected = test_vector['expected_return']
                if result.returncode != expected:
                    validation_passed = False
                    
            return CLITestResult(
                entry_point=entry_point,
                command=' '.join(cmd),
                success=result.returncode == 0 or validation_passed,
                stdout=result.stdout,
                stderr=result.stderr,
                return_code=result.returncode,
                duration=duration,
                validation_passed=validation_passed
            )
            
        except subprocess.TimeoutExpired:
            return CLITestResult(
                entry_point=entry_point,
                command=' '.join(cmd),
                success=False,
                stdout='',
                stderr='Command timed out after 30 seconds',
                return_code=-1,
                duration=30.0,
                validation_passed=False
            )
        except Exception as e:
            return CLITestResult(
                entry_point=entry_point,
                command=' '.join(cmd),
                success=False,
                stdout='',
                stderr=str(e),
                return_code=-1,
                duration=0.0,
                validation_passed=False
            )
    
    def generate_report(self, results: List[CLITestResult]) -> Dict[str, Any]:
        """Generate a comprehensive test report."""
        report = {
            'total_tests': len(results),
            'passed': sum(1 for r in results if r.success),
            'failed': sum(1 for r in results if not r.success),
            'entry_points': {},
            'summary': []
        }
        
        # Group by entry point
        for result in results:
            file_path = str(result.entry_point.file_path)
            if file_path not in report['entry_points']:
                report['entry_points'][file_path] = {
                    'type': result.entry_point.entry_type,
                    'commands': result.entry_point.commands,
                    'tests': []
                }
                
            report['entry_points'][file_path]['tests'].append({
                'command': result.command,
                'success': result.success,
                'return_code': result.return_code,
                'duration': result.duration,
                'validation': result.validation_passed
            })
            
        # Generate summary
        for path, info in report['entry_points'].items():
            passed = sum(1 for t in info['tests'] if t['success'])
            total = len(info['tests'])
            report['summary'].append(
                f"{Path(path).name}: {passed}/{total} tests passed"
            )
            
        return report


def main():
    """Main entry point for testing."""
    import argparse
    
    parser = argparse.ArgumentParser(description='SEGA CLI Entry Point Detector')
    parser.add_argument('path', nargs='?', default='.', 
                       help='Project path to analyze')
    parser.add_argument('--test', action='store_true',
                       help='Run tests on detected entry points')
    parser.add_argument('--json', action='store_true',
                       help='Output in JSON format')
    parser.add_argument('--verbose', action='store_true',
                       help='Verbose output')
    
    args = parser.parse_args()
    
    if args.verbose:
        logging.basicConfig(level=logging.DEBUG)
    else:
        logging.basicConfig(level=logging.INFO)
    
    if args.test:
        # Run tests
        runner = CLITestRunner(args.path)
        results = runner.run_all_tests()
        report = runner.generate_report(results)
        
        if args.json:
            print(json.dumps(report, indent=2))
        else:
            print("\nCLI Test Report")
            print("=" * 50)
            print(f"Total Tests: {report['total_tests']}")
            print(f"Passed: {report['passed']}")
            print(f"Failed: {report['failed']}")
            print("\nSummary:")
            for summary in report['summary']:
                print(f"  {summary}")
    else:
        # Just detect
        detector = CLIEntryDetector(args.path)
        entry_points = detector.detect_all_entry_points()
        
        if args.json:
            data = []
            for ep in entry_points:
                data.append({
                    'file': str(ep.file_path),
                    'type': ep.entry_type,
                    'commands': ep.commands,
                    'test_vectors': len(ep.test_vectors)
                })
            print(json.dumps(data, indent=2))
        else:
            print(f"\nDetected {len(entry_points)} CLI entry points:")
            for ep in entry_points:
                print(f"\n  File: {ep.file_path}")
                print(f"  Type: {ep.entry_type}")
                print(f"  Commands: {', '.join(ep.commands) if ep.commands else 'None'}")
                print(f"  Test Vectors: {len(ep.test_vectors)}")


if __name__ == '__main__':
    main()