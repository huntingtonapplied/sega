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
Workflow validation for SEGA

Validates that documented workflows match actual implementation.
Ported from scripts/validate_workflows.py with enhanced functionality.
"""

import os
import subprocess
import tempfile
import shutil
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple
import git
import logging

from .base import BaseValidator, ValidationResult

logger = logging.getLogger(__name__)


class WorkflowValidator(BaseValidator):
    """Validates SEGA workflows against documentation"""
    
    def __init__(self):
        super().__init__("WorkflowValidator")
        self.temp_workspace = None
    
    def validate(self, target: Any, **kwargs) -> ValidationResult:
        """Validate workflows"""
        if isinstance(target, (str, Path)):
            path = Path(target)
            if path.is_file():
                return self.validate_file(path, **kwargs)
            elif path.is_dir():
                return self.validate_directory(path, pattern="*.md", **kwargs)
        
        # Default: validate all documented workflows
        return self.validate_all_workflows(**kwargs)
    
    def _validate_file_content(self, filepath: Path, result: ValidationResult, **kwargs) -> ValidationResult:
        """Validate workflow documentation file"""
        # For now, just check that it's valid markdown
        # In the future, extract and validate workflow steps
        try:
            content = filepath.read_text()
            if not content.strip():
                result.add_warning(f"Empty workflow file: {filepath.name}")
            
            # Extract code blocks and validate commands
            code_blocks = self._extract_code_blocks(content)
            for i, block in enumerate(code_blocks):
                if block.get('language') in ['bash', 'shell', 'sh']:
                    self._validate_commands(block['content'], result, filepath, i)
                    
        except Exception as e:
            result.add_error(f"Error reading workflow file: {e}", path=str(filepath))
        
        return result
    
    def validate_all_workflows(self, **kwargs) -> ValidationResult:
        """Validate all documented workflows"""
        result = ValidationResult(
            valid=True,
            validator_name=self.name,
            target="All Workflows"
        )
        
        # Create test workspace
        self.temp_workspace = self._create_test_workspace()
        if not self.temp_workspace:
            result.add_error("Failed to create test workspace")
            return result
        
        try:
            # Run workflow tests
            test_results = [
                ("Portfolio Init", self._test_portfolio_init()),
                ("Workspace Commands", self._test_workspace_commands()),
                ("Configuration Structure", self._test_configuration_structure()),
                ("Project Detection", self._test_project_detection()),
                ("CLI Syntax", self._test_documented_cli_syntax()),
            ]
            
            # Aggregate results
            passed = 0
            for test_name, test_result in test_results:
                if test_result:
                    passed += 1
                    result.add_info(f"{test_name} test passed")
                else:
                    result.add_error(f"{test_name} test failed")
            
            result.metadata['total_tests'] = len(test_results)
            result.metadata['passed_tests'] = passed
            result.metadata['failed_tests'] = len(test_results) - passed
            
            if passed < len(test_results):
                result.valid = False
                
        finally:
            # Cleanup
            if self.temp_workspace and self.temp_workspace.exists():
                shutil.rmtree(self.temp_workspace.parent)
        
        return result
    
    def _extract_code_blocks(self, content: str) -> List[Dict[str, Any]]:
        """Extract code blocks from markdown content"""
        blocks = []
        lines = content.split('\n')
        in_block = False
        current_block = []
        language = None
        
        for line in lines:
            if line.startswith('```'):
                if in_block:
                    # End of block
                    blocks.append({
                        'language': language,
                        'content': '\n'.join(current_block)
                    })
                    current_block = []
                    in_block = False
                    language = None
                else:
                    # Start of block
                    in_block = True
                    language = line[3:].strip() or None
            elif in_block:
                current_block.append(line)
        
        return blocks
    
    def _validate_commands(self, commands: str, result: ValidationResult, 
                         filepath: Path, block_index: int) -> None:
        """Validate shell commands in documentation"""
        lines = commands.strip().split('\n')
        for i, line in enumerate(lines):
            line = line.strip()
            if not line or line.startswith('#'):
                continue
            
            # Check for common issues
            if line.startswith('sega '):
                # Validate SEGA command syntax
                if '--project' in line and line.count('--project') > 1:
                    # Multiple --project flags should be supported
                    pass
                
                # Check for deprecated commands
                if 'sega init --portfolio' in line:
                    result.add_info(
                        "Portfolio initialization command found",
                        path=str(filepath),
                        line=block_index
                    )
    
    def _create_test_workspace(self) -> Optional[Path]:
        """Create a test workspace with fake git projects"""
        try:
            temp_dir = tempfile.mkdtemp(prefix="sega_workflow_test_")
            workspace_dir = Path(temp_dir) / "projects"
            workspace_dir.mkdir()
            
            # Create fake team/project structure
            teams = {
                "barcelona": ["atlas", "vega"],
                "maiori": ["hermes"],
                "riviera": ["orion"]
            }
            
            for team, projects in teams.items():
                team_dir = workspace_dir / team
                team_dir.mkdir()
                
                for project in projects:
                    project_dir = team_dir / project
                    project_dir.mkdir()
                    
                    # Initialize git repo
                    repo = git.Repo.init(project_dir)
                    
                    # Create basic project files
                    self._create_project_files(project_dir, project)
                    
                    # Add and commit files
                    repo.index.add_to_index([
                        str(f.relative_to(project_dir)) 
                        for f in project_dir.rglob("*") 
                        if f.is_file()
                    ])
                    repo.index.commit("Initial commit")
            
            logger.info(f"Created test workspace: {workspace_dir}")
            return workspace_dir
            
        except Exception as e:
            logger.error(f"Failed to create test workspace: {e}")
            return None
    
    def _create_project_files(self, project_dir: Path, project_name: str) -> None:
        """Create project-specific files for testing"""
        if project_name == "atlas":
            # Web app
            (project_dir / "package.json").write_text(
                '{"name": "atlas", "version": "1.0.0"}'
            )
            (project_dir / "index.html").write_text(
                "<html><body>Hello</body></html>"
            )
        elif project_name == "vega":
            # Another web app
            (project_dir / "package.json").write_text(
                '{"name": "vega", "version": "1.0.0"}'
            )
            (project_dir / "dashboard").mkdir()
        elif project_name == "hermes":
            # Hybrid system
            (project_dir / "hermes_engine").mkdir()
            (project_dir / "hermes_firmware").mkdir()
            (project_dir / "hermes_ui").mkdir()
            (project_dir / "Makefile").write_text("all:\n\techo 'building'")
        elif project_name == "orion":
            # ML pipeline
            (project_dir / "requirements.txt").write_text("torch\nnumpy\npandas")
            (project_dir / "ml_engine").mkdir()
    
    def _run_command(self, cmd: str, cwd: Optional[Path] = None, 
                    check: bool = True) -> Tuple[int, str, str]:
        """Run a command and return (returncode, stdout, stderr)"""
        try:
            result = subprocess.run(
                cmd.split() if isinstance(cmd, str) else cmd,
                cwd=cwd,
                check=check,
                capture_output=True,
                text=True
            )
            return result.returncode, result.stdout, result.stderr
        except subprocess.CalledProcessError as e:
            return e.returncode, e.stdout or "", e.stderr or ""
        except Exception as e:
            return -1, "", str(e)
    
    def _test_portfolio_init(self) -> bool:
        """Test portfolio initialization workflow"""
        logger.info("Testing portfolio initialization")
        
        original_cwd = os.getcwd()
        os.chdir(self.temp_workspace)
        
        try:
            # Test dry run
            returncode, stdout, stderr = self._run_command("sega init --portfolio --dry-run")
            if returncode != 0:
                logger.error(f"Portfolio dry run failed: {stderr}")
                return False
            
            # Test actual initialization
            returncode, stdout, stderr = self._run_command("sega init --portfolio --force")
            if returncode != 0:
                logger.error(f"Portfolio initialization failed: {stderr}")
                return False
            
            # Check that files were created
            expected_files = [
                "sega-workspace.yaml",
                "sega-projects.yaml",
                "barcelona/atlas/sega.yaml",
                "barcelona/vega/sega.yaml",
                "maiori/hermes/sega.yaml",
                "riviera/orion/sega.yaml"
            ]
            
            for file_path in expected_files:
                if not (self.temp_workspace / file_path).exists():
                    logger.error(f"Expected file not created: {file_path}")
                    return False
            
            return True
            
        finally:
            os.chdir(original_cwd)
    
    def _test_workspace_commands(self) -> bool:
        """Test workspace management commands"""
        logger.info("Testing workspace commands")
        
        original_cwd = os.getcwd()
        os.chdir(self.temp_workspace)
        
        try:
            # Test workspace list
            returncode, stdout, stderr = self._run_command("sega workspace list")
            if returncode != 0:
                logger.error(f"Workspace list failed: {stderr}")
                return False
            
            # Test workspace list with filters
            returncode, stdout, stderr = self._run_command("sega workspace list --team barcelona")
            if returncode != 0:
                logger.error(f"Workspace list with team filter failed: {stderr}")
                return False
            
            # Test workspace validation
            returncode, stdout, stderr = self._run_command("sega workspace validate")
            if returncode != 0:
                logger.error(f"Workspace validation failed: {stderr}")
                return False
            
            return True
            
        finally:
            os.chdir(original_cwd)
    
    def _test_configuration_structure(self) -> bool:
        """Test that generated configurations match documentation"""
        logger.info("Testing configuration structure")
        
        # Check atlas configuration (web_app)
        fasci_config_path = self.temp_workspace / "barcelona/atlas/sega.yaml"
        if not fasci_config_path.exists():
            logger.error("Atlas config not found")
            return False
        
        config = self.load_yaml(fasci_config_path)
        if not config:
            return False
        
        # Validate structure matches documentation
        required_fields = {
            'version': str,
            'project': dict,
            'deployment': dict,
            'build': dict
        }
        
        for field, expected_type in required_fields.items():
            if field not in config:
                logger.error(f"Missing required field: {field}")
                return False
            if not isinstance(config[field], expected_type):
                logger.error(f"Invalid type for {field}: expected {expected_type}")
                return False
        
        return True
    
    def _test_project_detection(self) -> bool:
        """Test project type detection"""
        logger.info("Testing project detection")
        
        original_cwd = os.getcwd()
        
        try:
            # Test atlas (web_app)
            os.chdir(self.temp_workspace / "barcelona/atlas")
            returncode, stdout, stderr = self._run_command("sega detect")
            if returncode != 0 or "web_app" not in stdout:
                logger.error("Atlas project detection failed")
                return False
            
            # Test hermes (hybrid_system)
            os.chdir(self.temp_workspace / "maiori/hermes")
            returncode, stdout, stderr = self._run_command("sega detect")
            if returncode != 0 or "hybrid_system" not in stdout:
                logger.error("Hermes project detection failed")
                return False
            
            return True
            
        finally:
            os.chdir(original_cwd)
    
    def _test_documented_cli_syntax(self) -> bool:
        """Test that documented CLI syntax actually works"""
        logger.info("Testing documented CLI syntax")
        
        original_cwd = os.getcwd()
        os.chdir(self.temp_workspace)
        
        try:
            # Test multiple --project flags (documented syntax)
            cmd = [
                "sega", "workspace", "deploy", 
                "--project", "barcelona/atlas",
                "--project", "maiori/hermes", 
                "--target", "staging",
                "--dry-run"
            ]
            returncode, stdout, stderr = self._run_command(cmd)
            if returncode != 0:
                logger.error(f"Multiple --project flags failed: {stderr}")
                return False
            
            return True
            
        finally:
            os.chdir(original_cwd)