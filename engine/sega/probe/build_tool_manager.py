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
SEGA Build Tool Manager
=======================
Manages build tool availability across FLEET projects
Based on SEGA Testing Infrastructure Strategy 2025-08-02
"""

import os
import subprocess
from typing import Dict, List
from pathlib import Path
from ..utils.paths import get_fleet_root


class BuildToolManager:
    """Manages build tool availability and setup for testing."""
    
    def __init__(self):
        self.tools_status: Dict[str, bool] = {}
        self.required_tools = {
            'typescript': ['tsc', '--version'],
            'jest': ['jest', '--version'],
            'vitest': ['vitest', '--version'],
            'pytest': ['pytest', '--version'],
            'npm': ['npm', '--version'],
            'node': ['node', '--version'],
            'python': ['python3', '--version']
        }
        
    def setup_all_tools(self) -> bool:
        """Set up all required build tools."""
        print("  Setting up build tools...")
        
        # Check current tool availability
        self.check_tool_availability()
        
        # Install missing tools
        missing_tools = [tool for tool, available in self.tools_status.items() if not available]
        
        if missing_tools:
            print(f"Installing missing tools: {', '.join(missing_tools)}")
            return self.install_missing_tools(missing_tools)
        else:
            print("  All build tools are available")
            return True
            
    def check_tool_availability(self) -> Dict[str, bool]:
        """Check availability of all required tools."""
        for tool, command in self.required_tools.items():
            self.tools_status[tool] = self.is_tool_available(command)
            
        return self.tools_status
    
    def is_tool_available(self, command: List[str]) -> bool:
        """Check if a specific tool is available."""
        try:
            result = subprocess.run(
                command,
                capture_output=True,
                text=True,
                timeout=10
            )
            return result.returncode == 0
        except (subprocess.TimeoutExpired, subprocess.CalledProcessError, FileNotFoundError):
            return False
    
    def install_missing_tools(self, missing_tools: List[str]) -> bool:
        """Install missing build tools."""
        success = True
        
        for tool in missing_tools:
            if not self.install_tool(tool):
                success = False
                print(f"  Failed to install {tool}")
            else:
                print(f"  Successfully installed {tool}")
                
        return success
    
    def install_tool(self, tool: str) -> bool:
        """Install a specific tool."""
        install_commands = {
            'typescript': ['npm', 'install', '-g', 'typescript@5.2.2'],
            'jest': ['npm', 'install', '-g', 'jest@29'],
            'vitest': ['npm', 'install', '-g', 'vitest@0.34.0'],
            'pytest': ['pip3', 'install', 'pytest==7.4.0'],
        }
        
        if tool not in install_commands:
            print(f"   Don't know how to install {tool}")
            return False
            
        try:
            subprocess.run(
                install_commands[tool],
                check=True,
                timeout=300
            )
            
            # Verify installation
            return self.is_tool_available(self.required_tools[tool])
            
        except (subprocess.CalledProcessError, subprocess.TimeoutExpired) as e:
            print(f"  Failed to install {tool}: {e}")
            return False
    
    def setup_containerized_environment(self, project_type: str = "bBase") -> bool:
        """Set up containerized build environment."""
        print(f"Setting up containerized environment for {project_type}")
        
        fleet_root = get_fleet_root()
        test_env_path = fleet_root / "test-environments"
        
        if not test_env_path.exists():
            print("  Test environments not found")
            return False
            
        dockerfile_path = test_env_path / project_type / "Dockerfile"
        if not dockerfile_path.exists():
            print(f"  Dockerfile not found for {project_type}")
            return False
            
        try:
            # Build container
            subprocess.run([
                "docker", "build", 
                "-t", f"fleet-test-{project_type}",
                str(dockerfile_path.parent)
            ], check=True)
            
            print(f"  Built fleet-test-{project_type} container")
            return True
            
        except subprocess.CalledProcessError as e:
            print(f"  Failed to build container: {e}")
            return False
    
    def run_in_container(self, project_type: str, command: List[str], project_path: Path) -> subprocess.CompletedProcess:
        """Run a command in the appropriate test container."""
        container_command = [
            "docker", "run", "--rm",
            "-v", f"{project_path}:/test",
            "-w", "/test",
            f"fleet-test-{project_type}"
        ] + command
        
        return subprocess.run(container_command, capture_output=True, text=True)
    
    def ensure_shared_dependencies(self, project_path: Path) -> bool:
        """Ensure shared dependencies are available for a project."""
        fleet_root = project_path.parent
        shared_node_modules = fleet_root / "_internal" / "environments" / "node_modules"
        shared_venv = fleet_root / "environments" / "fleet_venv"
        
        success = True
        
        # Check for package.json and link to shared node_modules
        if (project_path / "package.json").exists():
            project_node_modules = project_path / "node_modules"
            if not project_node_modules.exists() and shared_node_modules.exists():
                try:
                    project_node_modules.symlink_to(shared_node_modules)
                    print(f"  Linked {project_path.name} to shared node_modules")
                except OSError as e:
                    print(f"   Failed to link node_modules: {e}")
                    success = False
        
        # Check for Python requirements and shared venv
        if any((project_path / f).exists() for f in ["requirements.txt", "pyproject.toml", "setup.py"]):
            if shared_venv.exists():
                # Activate shared venv by updating PATH
                venv_bin = shared_venv / "bin"
                if venv_bin.exists():
                    current_path = os.environ.get("PATH", "")
                    if str(venv_bin) not in current_path:
                        os.environ["PATH"] = f"{venv_bin}:{current_path}"
                        print(f"Activated shared Python environment for {project_path.name}")
        
        return success
    
    def get_tool_status_report(self) -> Dict[str, any]:
        """Generate a status report of all build tools."""
        self.check_tool_availability()
        
        return {
            'tools': self.tools_status,
            'summary': {
                'total_tools': len(self.tools_status),
                'available_tools': sum(self.tools_status.values()),
                'missing_tools': [tool for tool, available in self.tools_status.items() if not available]
            }
        }