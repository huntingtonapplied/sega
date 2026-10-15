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
File: scripts/validate_workflows.py
Purpose: Provides validation utilities for testing documented workflows against implementation
Dependencies: subprocess, yaml, git, tempfile
Authors: SEGA Development Team
Copyright: 2022-2025 the SEGA authors. All rights reserved.
License: Apache-2.0
Last Modified: 2025-07-25
"""

import os
import sys
import subprocess
import tempfile
import shutil
from pathlib import Path
import yaml
import git


def run_command(cmd, check=True, capture_output=True):
    """Run a command and return the result."""
    print(f"Running: {cmd}")
    try:
        result = subprocess.run(
            cmd.split() if isinstance(cmd, str) else cmd,
            check=check,
            capture_output=capture_output,
            text=True
        )
        if result.stdout:
            print(f"Output: {result.stdout}")
        return result
    except subprocess.CalledProcessError as e:
        print(f"Error: {e}")
        if e.stderr:
            print(f"Error output: {e.stderr}")
        return e


def create_test_workspace():
    """Create a test workspace with fake git projects."""
    temp_dir = tempfile.mkdtemp(prefix="sega_test_")
    workspace_dir = Path(temp_dir) / "projects"
    workspace_dir.mkdir()
    
    # Create fake team/project structure
    teams = {
        "barcelona": ["atlas", "hermes"],
        "maiori": ["orion"],
        "riviera": ["vega"]
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
            if project == "atlas":
                # Web app
                (project_dir / "package.json").write_text('{"name": "atlas", "version": "1.0.0"}')
                (project_dir / "index.html").write_text("<html><body>Hello</body></html>")
            elif project == "hermes":
                # Another web app
                (project_dir / "package.json").write_text('{"name": "hermes", "version": "1.0.0"}')
                (project_dir / "dashboard").mkdir()
            elif project == "orion":
                # Hybrid system
                (project_dir / "orion_engine").mkdir()
                (project_dir / "orion_firmware").mkdir()
                (project_dir / "orion_ui").mkdir()
                (project_dir / "Makefile").write_text("all:\n\techo 'building'")
            elif project == "vega":
                # ML pipeline
                (project_dir / "requirements.txt").write_text("torch\nnumpy\npandas")
                (project_dir / "ml_engine").mkdir()
            
            # Add and commit files
            repo.index.add_to_index([str(f.relative_to(project_dir)) for f in project_dir.rglob("*") if f.is_file()])
            repo.index.commit("Initial commit")
    
    print(f"Created test workspace: {workspace_dir}")
    return workspace_dir


def test_portfolio_init(workspace_dir):
    """Test portfolio initialization workflow."""
    print("\n=== Testing Portfolio Initialization ===")
    
    # Change to workspace directory
    original_cwd = os.getcwd()
    os.chdir(workspace_dir)
    
    try:
        # Test dry run
        result = run_command("sega init --portfolio --dry-run")
        if result.returncode != 0:
            print(" Portfolio dry run failed")
            return False
        
        # Test actual initialization
        result = run_command("sega init --portfolio --force")
        if result.returncode != 0:
            print(" Portfolio initialization failed")
            return False
        
        # Check that files were created
        expected_files = [
            "sega-workspace.yaml",
            "sega-projects.yaml",
            "barcelona/atlas/sega.yaml",
            "barcelona/hermes/sega.yaml",
            "maiori/orion/sega.yaml",
            "riviera/vega/sega.yaml"
        ]
        
        for file_path in expected_files:
            if not (workspace_dir / file_path).exists():
                print(f" Expected file not created: {file_path}")
                return False
        
        print(" Portfolio initialization test passed")
        return True
        
    finally:
        os.chdir(original_cwd)


def test_workspace_commands(workspace_dir):
    """Test workspace management commands."""
    print("\n=== Testing Workspace Commands ===")
    
    original_cwd = os.getcwd()
    os.chdir(workspace_dir)
    
    try:
        # Test workspace list
        result = run_command("sega workspace list")
        if result.returncode != 0:
            print(" Workspace list failed")
            return False
        
        # Test workspace list with filters
        result = run_command("sega workspace list --team barcelona")
        if result.returncode != 0:
            print(" Workspace list with team filter failed")
            return False
        
        # Test workspace validation
        result = run_command("sega workspace validate")
        if result.returncode != 0:
            print(" Workspace validation failed")
            return False
        
        # Test dependencies
        result = run_command("sega workspace dependencies")
        if result.returncode != 0:
            print(" Workspace dependencies failed")
            return False
        
        print(" Workspace commands test passed")
        return True
        
    finally:
        os.chdir(original_cwd)


def test_configuration_structure(workspace_dir):
    """Test that generated configurations match documentation."""
    print("\n=== Testing Configuration Structure ===")
    
    # Check atlas configuration (web_app)
    atlas_config_path = workspace_dir / "barcelona/atlas/sega.yaml"
    if not atlas_config_path.exists():
        print(" Atlas config not found")
        return False
    
    with open(atlas_config_path) as f:
        atlas_config = yaml.safe_load(f)
    
    # Validate structure matches documentation
    expected_structure = {
        'version': '2.1',
        'project': {
            'name': str,
            'type': str,
            'domain': str,
            'team': str
        },
        'deployment': {
            'targets': {
                'staging': {
                    'type': str,
                    'infrastructure': dict
                },
                'production': {
                    'type': str,
                    'infrastructure': dict
                }
            }
        },
        'build': {
            'strategy': str,
            'docker': dict
        }
    }
    
    def validate_structure(config, expected, path=""):
        for key, expected_type in expected.items():
            if key not in config:
                print(f" Missing key: {path}.{key}")
                return False
            
            if isinstance(expected_type, dict):
                if not isinstance(config[key], dict):
                    print(f" Expected dict at {path}.{key}, got {type(config[key])}")
                    return False
                if not validate_structure(config[key], expected_type, f"{path}.{key}"):
                    return False
            elif expected_type == str:
                if not isinstance(config[key], str):
                    print(f" Expected string at {path}.{key}, got {type(config[key])}")
                    return False
        
        return True
    
    if not validate_structure(atlas_config, expected_structure):
        print(" Configuration structure validation failed")
        return False
    
    # Check that infrastructure is nested correctly (not at top level)
    if 'infrastructure' in atlas_config.get('deployment', {}):
        print(" Infrastructure should be nested under targets, not at deployment level")
        return False
    
    print(" Configuration structure test passed")
    return True


def test_project_detection(workspace_dir):
    """Test project type detection."""
    print("\n=== Testing Project Detection ===")
    
    original_cwd = os.getcwd()
    
    # Test atlas (web_app)
    os.chdir(workspace_dir / "barcelona/atlas")
    result = run_command("sega detect")
    if result.returncode != 0 or "web_app" not in result.stdout:
        print(" Atlas project detection failed")
        return False
    
    # Test orion (hybrid_system)
    os.chdir(workspace_dir / "maiori/orion")
    result = run_command("sega detect")
    if result.returncode != 0 or "hybrid_system" not in result.stdout:
        print(" Orion project detection failed")
        return False
    
    # Test vega (ml_pipeline)
    os.chdir(workspace_dir / "riviera/vega")
    result = run_command("sega detect")
    if result.returncode != 0 or "ml_pipeline" not in result.stdout:
        print(" Vega project detection failed")
        return False
    
    os.chdir(original_cwd)
    print(" Project detection test passed")
    return True


def test_documented_cli_syntax(workspace_dir):
    """Test that documented CLI syntax actually works."""
    print("\n=== Testing Documented CLI Syntax ===")
    
    original_cwd = os.getcwd()
    os.chdir(workspace_dir)
    
    try:
        # Test multiple --project flags (documented syntax)
        result = run_command([
            "sega", "workspace", "deploy", 
            "--project", "barcelona/atlas",
            "--project", "maiori/orion", 
            "--target", "staging",
            "--dry-run"
        ])
        if result.returncode != 0:
            print(" Multiple --project flags failed")
            return False
        
        # Test --config option
        result = run_command("sega workspace list --config sega-projects.yaml")
        if result.returncode != 0:
            print(" --config option failed")
            return False
        
        # Test team filtering
        result = run_command("sega workspace list --team barcelona --format json")
        if result.returncode != 0:
            print(" Team filtering failed")
            return False
        
        print(" CLI syntax test passed")
        return True
        
    finally:
        os.chdir(original_cwd)


def main():
    """Run all validation tests."""
    print(" Starting SEGA workflow validation...")
    
    # Create test workspace
    workspace_dir = create_test_workspace()
    
    try:
        tests = [
            test_portfolio_init,
            test_workspace_commands,
            test_configuration_structure,
            test_project_detection,
            test_documented_cli_syntax
        ]
        
        passed = 0
        total = len(tests)
        
        for test_func in tests:
            if test_func(workspace_dir):
                passed += 1
            else:
                print(f" Test failed: {test_func.__name__}")
        
        print(f"\n Test Results: {passed}/{total} tests passed")
        
        if passed == total:
            print(" All tests passed! Documentation matches implementation.")
            return 0
        else:
            print("  Some tests failed. Documentation and implementation have discrepancies.")
            return 1
            
    finally:
        # Cleanup
        print(f" Cleaning up test workspace: {workspace_dir}")
        shutil.rmtree(workspace_dir.parent)


if __name__ == "__main__":
    sys.exit(main())