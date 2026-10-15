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
SEGA PROJECT TYPE DETECTION ENGINE
==============================================================================
File: src/sega/detectors/project_detector.py
Project: SEGA (Scalable Engineering & Growth Automation)
Copyright: 2022-2025 FLEET
License: Apache-2.0

SEGA MODULE: Detectors/ProjectTypeDetection
COMPONENT: Intelligent Project Analysis Engine
PURPOSE: Detect project types based on file patterns and repository structure
DEPENDENCIES: os, yaml, pathlib
USAGE: detector = ProjectDetector(path); project_type = detector.detect()

This engine analyzes file patterns, dependencies, and repository structure to
automatically determine project types and generate appropriate build configurations.
==============================================================================
"""

import os
import json
import yaml
from typing import Dict, Optional, List
from pathlib import Path


class ProjectDetector:
    """Detects project type based on file patterns and repository structure."""

    def __init__(self, project_path: str = "."):
        self.project_path = self._validate_and_resolve_path(project_path)
        self.sega_config = self._load_sega_config()

    def _validate_and_resolve_path(self, path: str) -> Path:
        """Validate and resolve project path to prevent directory traversal."""
        try:
            # Convert to Path object and resolve
            project_path = Path(path).resolve()

            # Ensure the path is absolute
            if not project_path.is_absolute():
                project_path = Path.cwd() / project_path
                project_path = project_path.resolve()

            # Check for directory traversal patterns
            path_str = str(project_path)
            if ".." in str(Path(path)) or not project_path.exists():
                # Only allow paths that exist and don't contain traversal patterns
                if not project_path.exists():
                    raise ValueError(f"Project path does not exist: {path}")

            # Ensure the resolved path is within reasonable bounds
            # (not allowing access to system directories)
            system_dirs = {
                "/etc",
                "/usr",
                "/var",
                "/proc",
                "/sys",
                "/dev",
                "/root",
            }
            for sys_dir in system_dirs:
                if path_str.startswith(sys_dir):
                    raise ValueError(
                        f"Access to system directory not allowed: {path}"
                    )

            return project_path

        except (OSError, ValueError) as e:
            raise ValueError(f"Invalid project path: {e}")

    def _load_sega_config(self) -> Optional[Dict]:
        """Load sega.yaml configuration if it exists."""
        # Check for sega.yaml first (new format)
        config_path = self.project_path / "sega.yaml"
        if config_path.exists():
            with open(config_path) as f:
                return yaml.safe_load(f)

        # Fallback to .sega.yml (legacy format)
        config_path = self.project_path / ".sega.yml"
        if config_path.exists():
            with open(config_path) as f:
                return yaml.safe_load(f)

        return None

    def detect(self) -> str:
        """Detect project type based on file patterns and configuration."""
        # Override from sega.yaml configuration
        if self.sega_config:
            # New format: project.type
            if (
                "project" in self.sega_config
                and "type" in self.sega_config["project"]
            ):
                return self.sega_config["project"]["type"]
            # Legacy format: project_type
            elif "project_type" in self.sega_config:
                return self.sega_config["project_type"]

        # Platform-specific detection (Vercel, Firebase, Supabase, etc.)
        if self._is_vercel_project():
            return "nextjs_app"
        elif self._is_firebase_project():
            return "firebase_app"
        elif self._is_supabase_project():
            return "supabase_app"
        elif self._is_amplify_project():
            return "amplify_app"

        # FLEET-specific detection patterns
        if self._is_fleet_hybrid_project():
            return "hybrid_system"
        elif self._is_fleet_hardware_project():
            return "firmware_edge"
        elif self._is_fleet_web_project():
            return "web_app"
        elif self._is_fleet_ml_project():
            return "ml_pipeline"

        # Standard detection patterns
        elif self._is_electron_project():
            return "electron_app"
        elif self._is_web_project():
            return "web_app"
        elif self._is_ml_project():
            return "ml_pipeline"
        elif self._is_firmware_project():
            return "firmware_edge"
        elif self._is_native_project():
            return "native_app"
        elif self._is_hdl_project():
            return "hdl_fpga"

        return "unknown"

    def _is_web_project(self) -> bool:
        """Check for web aApplication indicators."""
        patterns = [
            "package.json",
            "requirements.txt",
            "index.html",
            "Dockerfile",
            "docker-compose.yml",
        ]
        return any((self.project_path / p).exists() for p in patterns)

    def _is_ml_project(self) -> bool:
        """Check for ML pipeline indicators."""
        if not (self.project_path / "requirements.txt").exists():
            return False

        try:
            with open(self.project_path / "requirements.txt") as f:
                content = f.read().lower()
                ml_libs = ["torch", "tensorflow", "sklearn", "numpy", "pandas"]
                return any(lib in content for lib in ml_libs)
        except (FileNotFoundError, PermissionError, OSError):
            return False

    def _is_firmware_project(self) -> bool:
        """Check for firmware/embedded indicators."""
        patterns = [
            "*.c",
            "*.cpp",
            "*.h",
            "*.ino",
            "*.elf",
            "Makefile",
            "CMakeLists.txt",
            "platformio.ini",
        ]
        return any(list(self.project_path.glob(p)) for p in patterns)

    def _is_native_project(self) -> bool:
        """Check for native aApplication indicators."""
        patterns = ["Cargo.toml", "go.mod", "Makefile", "CMakeLists.txt"]
        return any((self.project_path / p).exists() for p in patterns)

    def _is_hdl_project(self) -> bool:
        """Check for HDL/FPGA indicators."""
        patterns = ["*.vhd", "*.v", "*.sv", "*.xdc", "*.tcl"]
        # Check both root and recursive patterns
        for pattern in patterns:
            if list(self.project_path.glob(pattern)) or list(
                self.project_path.glob(f"**/{pattern}")
            ):
                return True
        return False

    def _is_electron_project(self) -> bool:
        """Check for Electron desktop aApplication indicators."""
        # Check for desktop directory with Electron app
        desktop_path = self.project_path / "desktop"
        if desktop_path.exists() and desktop_path.is_dir():
            desktop_package_json = desktop_path / "package.json"
            if desktop_package_json.exists():
                try:
                    import json
                    with open(desktop_package_json) as f:
                        package_data = json.load(f)
                        
                    # Check for electron dependency
                    dependencies = package_data.get("dependencies", {})
                    dev_dependencies = package_data.get("devDependencies", {})
                    
                    if "electron" in dependencies or "electron" in dev_dependencies:
                        return True
                        
                    # Check for electron scripts
                    scripts = package_data.get("scripts", {})
                    electron_scripts = ["electron", "dev", "start"]
                    for script_name, script_cmd in scripts.items():
                        if any(cmd in script_cmd.lower() for cmd in ["electron", "main.js"]):
                            return True
                            
                except (json.JSONDecodeError, FileNotFoundError, PermissionError, OSError):
                    pass
        
        # Check for Electron patterns in root directory
        root_package_json = self.project_path / "package.json"
        if root_package_json.exists():
            try:
                import json
                with open(root_package_json) as f:
                    package_data = json.load(f)
                    
                dependencies = package_data.get("dependencies", {})
                dev_dependencies = package_data.get("devDependencies", {})
                
                return "electron" in dependencies or "electron" in dev_dependencies
                
            except (json.JSONDecodeError, FileNotFoundError, PermissionError, OSError):
                pass
        
        return False

    def _is_fleet_hybrid_project(self) -> bool:
        """Check for FLEET hybrid system indicators (multiple domains)."""
        domains = {
            "web": ["frontend", "backend", "dashboard", "ui"],
            "firmware": ["firmware", "embedded"],
            "fpga": ["gateware", "fpga", "hdl"],
            "ai": ["ai", "ml", "engine"],
            "rf": ["rf", "radio"],
        }

        found_domains = 0
        for domain, indicators in domains.items():
            if any(
                (self.project_path / indicator).exists()
                for indicator in indicators
            ):
                found_domains += 1

        return found_domains >= 2

    def _is_fleet_hardware_project(self) -> bool:
        """Check for FLEET hardware project patterns."""
        # Check for specific FLEET hardware patterns
        fleet_hardware_patterns = [
            "*_engine",
            "*_firmware",
            "*_rf",
            "*_ui",
            "gateware",
            "firmware",
            "hardware",
            "fpga",
        ]

        # Check for hardware-specific files
        hardware_files = [
            "*.ino",
            "*.hex",
            "*.bin",
            "*.elf",
            "platformio.ini",
            "arduino.json",
        ]

        return any(
            (self.project_path / p).exists() for p in fleet_hardware_patterns
        ) or any(list(self.project_path.glob(p)) for p in hardware_files)

    def _is_fleet_web_project(self) -> bool:
        """Check for FLEET web aApplication patterns."""
        # Check for typical FLEET web structure
        fleet_web_patterns = [
            "frontend",
            "backend",
            "dashboard",
            "ui",
            "aApplication",
            "server",
            "api",
        ]

        web_indicators = [
            "package.json",
            "requirements.txt",
            "docker-compose.yml",
            "Dockerfile",
            "index.html",
            "app.py",
            "main.py",
        ]

        return any(
            (self.project_path / p).exists() for p in fleet_web_patterns
        ) and any((self.project_path / p).exists() for p in web_indicators)

    def _is_fleet_ml_project(self) -> bool:
        """Check for FLEET ML/AI project patterns."""
        # Check for AI/ML specific directories
        ml_patterns = ["ai", "ml", "engine", "pipeline", "models"]

        # Check for ML-specific files
        ml_files = [
            "requirements.txt",
            "environment.yml",
            "conda.yml",
            "model.py",
            "train.py",
            "inference.py",
        ]

        has_ml_structure = any(
            (self.project_path / p).exists() for p in ml_patterns
        )
        has_ml_files = any((self.project_path / p).exists() for p in ml_files)

        if has_ml_structure or has_ml_files:
            # Check for ML libraries in requirements
            try:
                req_files = [
                    "requirements.txt",
                    "environment.yml",
                    "conda.yml",
                ]
                for req_file in req_files:
                    req_path = self.project_path / req_file
                    if req_path.exists():
                        with open(req_path) as f:
                            content = f.read().lower()
                            ml_libs = [
                                "torch",
                                "tensorflow",
                                "sklearn",
                                "numpy",
                                "pandas",
                                "jupyter",
                            ]
                            if any(lib in content for lib in ml_libs):
                                return True
            except (FileNotFoundError, PermissionError, OSError):
                pass

        return has_ml_structure

    def get_build_config(self) -> Dict:
        """Get build configuration for detected project type."""
        project_type = self.detect()

        configs = {
            # Infrastructure targets
            "web_app": {
                "builder": "docker",
                "tester": "playwright",
                "deployer": "helm_k8s",
                "monitor": "k8s_prometheus",
            },
            "ml_pipeline": {
                "builder": "docker_gpu",
                "tester": "model_validation",
                "deployer": "helm_gpu_k8s",
                "monitor": "k8s_gpu_prometheus",
            },
            "firmware_edge": {
                "builder": "cross_compile",
                "tester": "hardware_emulation",
                "deployer": "ansible_flash",
                "monitor": "vpn_edge_prometheus",
            },
            "native_app": {
                "builder": "native_make",
                "tester": "unit_integration",
                "deployer": "ansible_systemd",
                "monitor": "node_prometheus",
            },
            "hdl_fpga": {
                "builder": "hdl_synthesis",
                "tester": "simulation",
                "deployer": "fpga_flash",
                "monitor": "hardware_telemetry",
            },
            "hybrid_system": {
                "builder": "multi_domain",
                "tester": "comprehensive",
                "deployer": "orchestrated",
                "monitor": "unified_dashboard",
            },
            # Platform targets
            "nextjs_app": {
                "builder": "npm",
                "tester": "jest",
                "deployer": "vercel",
                "monitor": "vercel_analytics",
            },
            "static_web": {
                "builder": "npm",
                "tester": "jest",
                "deployer": "vercel",
                "monitor": "vercel_analytics",
            },
            "firebase_app": {
                "builder": "npm",
                "tester": "jest",
                "deployer": "firebase",
                "monitor": "firebase_analytics",
            },
            "supabase_app": {
                "builder": "npm",
                "tester": "jest",
                "deployer": "supabase",
                "monitor": "supabase_dashboard",
            },
            "amplify_app": {
                "builder": "npm",
                "tester": "jest",
                "deployer": "amplify",
                "monitor": "cloudwatch",
            },
            "render_service": {
                "builder": "docker",
                "tester": "pytest",
                "deployer": "render",
                "monitor": "render_dashboard",
            },
        }

        return configs.get(project_type, configs["web_app"])

    def get_components(self) -> List[Dict]:
        """Get components for multi-component projects."""
        if self.sega_config and "components" in self.sega_config:
            return self.sega_config["components"]

        # Auto-detect components for FLEET projects
        components = []

        # Common FLEET component patterns
        component_patterns = {
            "frontend": "web_app",
            "backend": "web_app",
            "dashboard": "web_app",
            "ui": "web_app",
            "firmware": "firmware_edge",
            "gateware": "hdl_fpga",
            "engine": "native_app",
            "ai": "ml_pipeline",
            "ml": "ml_pipeline",
            "rf": "firmware_edge",
        }

        for component_name, component_type in component_patterns.items():
            component_path = self.project_path / component_name
            if component_path.exists() and component_path.is_dir():
                components.append(
                    {
                        "name": component_name,
                        "type": component_type,
                        "path": f"./{component_name}",
                    }
                )

        return components

    def get_fleet_metadata(self) -> Dict:
        """Get FLEET-specific project metadata."""
        metadata = {
            "domain": "fleet",
            "is_multi_component": len(self.get_components()) > 1,
            "detected_patterns": [],
        }

        # Detect FLEET-specific patterns
        if self._is_fleet_hybrid_project():
            metadata["detected_patterns"].append("hybrid_system")
        if self._is_fleet_hardware_project():
            metadata["detected_patterns"].append("hardware")
        if self._is_fleet_web_project():
            metadata["detected_patterns"].append("web_aApplication")
        if self._is_fleet_ml_project():
            metadata["detected_patterns"].append("ml_pipeline")

        # Extract team from path if following FLEET structure
        try:
            path_parts = str(self.project_path.absolute()).split(os.sep)
            if "projects" in path_parts:
                projects_idx = path_parts.index("projects")
                if projects_idx + 1 < len(path_parts):
                    metadata["team"] = path_parts[projects_idx + 1]
                if projects_idx + 2 < len(path_parts):
                    metadata["project_name"] = path_parts[projects_idx + 2]
        except (IndexError, ValueError):
            pass

        return metadata

    # =========================================================================
    # Platform-specific detection methods (Vercel, Firebase, Supabase, etc.)
    # =========================================================================

    def _is_vercel_project(self) -> bool:
        """Check for Vercel project indicators."""
        # Check for vercel.json
        if (self.project_path / "vercel.json").exists():
            return True
        
        # Check for .vercel directory
        if (self.project_path / ".vercel").exists():
            return True
        
        # Check for Next.js project (common Vercel target)
        if self._is_nextjs_project():
            return True
        
        return False

    def _is_nextjs_project(self) -> bool:
        """Check for Next.js project indicators."""
        # Check for next.config.js or next.config.mjs
        next_configs = ["next.config.js", "next.config.mjs", "next.config.ts"]
        if any((self.project_path / cfg).exists() for cfg in next_configs):
            return True
        
        # Check package.json for next dependency
        package_json = self.project_path / "package.json"
        if package_json.exists():
            try:
                with open(package_json) as f:
                    data = json.load(f)
                deps = data.get("dependencies", {})
                dev_deps = data.get("devDependencies", {})
                if "next" in deps or "next" in dev_deps:
                    return True
            except (json.JSONDecodeError, IOError):
                pass
        
        return False

    def _is_firebase_project(self) -> bool:
        """Check for Firebase project indicators."""
        # Check for firebase.json
        if (self.project_path / "firebase.json").exists():
            return True
        
        # Check for .firebaserc
        if (self.project_path / ".firebaserc").exists():
            return True
        
        # Check for firestore.rules or storage.rules
        if (self.project_path / "firestore.rules").exists():
            return True
        if (self.project_path / "storage.rules").exists():
            return True
        
        return False

    def _is_supabase_project(self) -> bool:
        """Check for Supabase project indicators."""
        # Check for supabase directory
        if (self.project_path / "supabase").exists():
            return True
        
        # Check for .supabase directory
        if (self.project_path / ".supabase").exists():
            return True
        
        # Check for supabase config
        if (self.project_path / "supabase" / "config.toml").exists():
            return True
        
        return False

    def _is_amplify_project(self) -> bool:
        """Check for AWS Amplify project indicators."""
        # Check for amplify directory
        if (self.project_path / "amplify").exists():
            return True
        
        # Check for amplify.yml
        if (self.project_path / "amplify.yml").exists():
            return True
        
        # Check for aws-exports.js (Amplify generated)
        aws_exports = [
            "aws-exports.js",
            "src/aws-exports.js",
            "aws-exports.ts",
            "src/aws-exports.ts",
        ]
        if any((self.project_path / exp).exists() for exp in aws_exports):
            return True
        
        return False

    def get_detected_platform(self) -> Optional[str]:
        """Get the detected deployment platform for this project.
        
        Returns:
            Platform name if detected, None otherwise
        """
        # Check sega.yaml for explicit platform
        if self.sega_config:
            # Check for platforms section with enabled platforms
            platforms = self.sega_config.get("platforms", {})
            for platform, config in platforms.items():
                if config.get("enabled", False):
                    return platform
            
            # Check for primary_platform in project config
            project = self.sega_config.get("project", {})
            if "primary_platform" in project:
                return project["primary_platform"]
        
        # Auto-detect platform
        if self._is_vercel_project():
            return "vercel"
        elif self._is_firebase_project():
            return "firebase"
        elif self._is_supabase_project():
            return "supabase"
        elif self._is_amplify_project():
            return "amplify"
        
        # Default to container-based for web apps
        project_type = self.detect()
        if project_type in ["web_app", "containerized_app"]:
            return "ecs_single"
        elif project_type == "hybrid_system":
            return "helm_k8s"
        
        return None
