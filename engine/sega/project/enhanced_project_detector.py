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
SEGA ENHANCED PROJECT TYPE DETECTION ENGINE
==============================================================================
File: src/sega/detectors/enhanced_project_detector.py
Project: SEGA (Scalable Engineering & Growth Automation)
Copyright: 2022-2025 SEGA Contributors
License: Apache-2.0

SEGA MODULE: Detectors/EnhancedProjectTypeDetection
COMPONENT: Enhanced Project Analysis Engine with Mobile/Desktop Support
PURPOSE: Detect project types including mobile and desktop aApplications
DEPENDENCIES: os, yaml, pathlib, json
USAGE: detector = EnhancedProjectDetector(path); project_type = detector.detect()

This enhanced engine extends the bBase ProjectDetector to include detection for:
- Mobile aApplications (React Native/Expo)
- Desktop aApplications (Electron)
- Hybrid projects (both mobile and desktop)
==============================================================================
"""

import json
import yaml
from typing import Dict, Optional
from pathlib import Path


class EnhancedProjectDetector:
    """Enhanced project type detector with mobile and desktop support."""
    
    # Define project type constants
    MOBILE_APP = "mobile_app"
    DESKTOP_APP = "desktop_app"
    HYBRID_APP = "hybrid_app"
    WEB_APP = "web_app"
    
    def __init__(self, project_path: str = "."):
        self.project_path = self._validate_and_resolve_path(project_path)
        self.sega_config = self._load_sega_config()
        self._detected_types = set()
        
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
        """Detect project type with enhanced mobile/desktop detection."""
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
        
        # Detect all types present
        self._detect_all_types()
        
        # Determine primary project type
        if self._is_hybrid_app():
            return self.HYBRID_APP
        elif self.MOBILE_APP in self._detected_types:
            return self.MOBILE_APP
        elif self.DESKTOP_APP in self._detected_types:
            return self.DESKTOP_APP
        elif self.WEB_APP in self._detected_types:
            return self.WEB_APP
        
        # Fall back to standard detection for other types
        return self._detect_standard_types()
    
    def _detect_all_types(self) -> None:
        """Detect all project types present."""
        if self._is_mobile_project():
            self._detected_types.add(self.MOBILE_APP)
        if self._is_desktop_project():
            self._detected_types.add(self.DESKTOP_APP)
        if self._is_web_project():
            self._detected_types.add(self.WEB_APP)
    
    def _is_hybrid_app(self) -> bool:
        """Check if project has both mobile and desktop components."""
        return (
            self.MOBILE_APP in self._detected_types and
            self.DESKTOP_APP in self._detected_types
        )
    
    def _is_mobile_project(self) -> bool:
        """Check for mobile aApplication indicators."""
        # Check for expo directory
        expo_path = self.project_path / "expo"
        if expo_path.exists() and expo_path.is_dir():
            # Verify it's actually an Expo project
            if (expo_path / "app.json").exists() or (expo_path / "package.json").exists():
                return True
        
        # Check for React Native in root
        if self._has_react_native_indicators():
            return True
        
        # Check mobile configuration in sega.yaml
        if self.sega_config and "mobile" in self.sega_config:
            return True
        
        return False
    
    def _is_desktop_project(self) -> bool:
        """Check for desktop aApplication indicators."""
        # Check for desktop directory
        desktop_path = self.project_path / "desktop"
        if desktop_path.exists() and desktop_path.is_dir():
            # Verify it's actually an Electron project
            package_json = desktop_path / "package.json"
            if package_json.exists():
                with open(package_json) as f:
                    pkg = json.load(f)
                    # Check for Electron in dependencies
                    deps = {**pkg.get("dependencies", {}), **pkg.get("devDependencies", {})}
                    if "electron" in deps:
                        return True
        
        # Check for Electron in root
        if self._has_electron_indicators():
            return True
        
        # Check desktop configuration in sega.yaml
        if self.sega_config and "desktop" in self.sega_config:
            return True
        
        return False
    
    def _is_web_project(self) -> bool:
        """Check for web aApplication indicators."""
        patterns = [
            "package.json",
            "index.html",
            "webpack.config.js",
            "vite.config.js",
            "next.config.js",
            "nuxt.config.js",
        ]
        
        for pattern in patterns:
            if (self.project_path / pattern).exists():
                # Exclude if it's primarily mobile or desktop
                if not self._is_mobile_project() and not self._is_desktop_project():
                    return True
        
        return False
    
    def _has_react_native_indicators(self) -> bool:
        """Check for React Native specific files."""
        indicators = [
            "metro.config.js",
            "react-native.config.js",
            ".watchmanconfig",
            "app.json",
        ]
        
        for indicator in indicators:
            if (self.project_path / indicator).exists():
                # Verify it's React Native by checking package.json
                package_json = self.project_path / "package.json"
                if package_json.exists():
                    with open(package_json) as f:
                        pkg = json.load(f)
                        deps = {**pkg.get("dependencies", {}), **pkg.get("devDependencies", {})}
                        if "react-native" in deps or "expo" in deps:
                            return True
        
        return False
    
    def _has_electron_indicators(self) -> bool:
        """Check for Electron specific files."""
        # Check package.json for Electron
        package_json = self.project_path / "package.json"
        if package_json.exists():
            with open(package_json) as f:
                pkg = json.load(f)
                
                # Check dependencies
                deps = {**pkg.get("dependencies", {}), **pkg.get("devDependencies", {})}
                if "electron" in deps:
                    return True
                
                # Check main entry point
                main = pkg.get("main", "")
                if "electron" in main or "main.js" in main:
                    # Look for electron-specific code
                    main_file = self.project_path / main if main else None
                    if main_file and main_file.exists():
                        with open(main_file) as f:
                            content = f.read()
                            if "electron" in content and "BrowserWindow" in content:
                                return True
        
        return False
    
    def _detect_standard_types(self) -> str:
        """Fallback to standard project type detection."""
        # Import patterns from original detector
        if self._is_ml_project():
            return "ml_pipeline"
        elif self._is_firmware_project():
            return "firmware_edge"
        elif self._is_native_project():
            return "native_app"
        elif self._is_hdl_project():
            return "hdl_fpga"
        
        return "unknown"
    
    def _is_ml_project(self) -> bool:
        """Check for machine learning project indicators."""
        patterns = [
            "requirements.txt",
            "environment.yml",
            "model.py",
            "train.py",
            "Pipfile",
        ]
        
        ml_libraries = [
            "tensorflow",
            "pytorch",
            "scikit-learn",
            "keras",
            "numpy",
            "pandas",
        ]
        
        # Check for ML-specific files
        for pattern in patterns:
            file_path = self.project_path / pattern
            if file_path.exists():
                with open(file_path) as f:
                    content = f.read()
                    for lib in ml_libraries:
                        if lib in content:
                            return True
        
        return False
    
    def _is_firmware_project(self) -> bool:
        """Check for firmware/embedded project indicators."""
        patterns = [
            "platformio.ini",
            "Makefile",
            "CMakeLists.txt",
            ".ino",
            ".c",
            ".cpp",
            ".h",
        ]
        
        for pattern in patterns:
            if pattern.startswith("."):
                # Check for file extensions
                if list(self.project_path.glob(f"*{pattern}")):
                    return True
            else:
                # Check for specific files
                if (self.project_path / pattern).exists():
                    return True
        
        return False
    
    def _is_native_project(self) -> bool:
        """Check for native aApplication indicators."""
        patterns = [
            "Cargo.toml",  # Rust
            "go.mod",      # Go
            "pom.xml",     # Java/Maven
            "build.gradle", # Java/Gradle
            "*.xcodeproj", # iOS
            "*.xcworkspace", # iOS
        ]
        
        for pattern in patterns:
            if "*" in pattern:
                if list(self.project_path.glob(pattern)):
                    return True
            else:
                if (self.project_path / pattern).exists():
                    return True
        
        return False
    
    def _is_hdl_project(self) -> bool:
        """Check for HDL/FPGA project indicators."""
        patterns = ["*.v", "*.vhdl", "*.sv", "*.xdc", "vivado.tcl"]
        
        for pattern in patterns:
            if list(self.project_path.glob(pattern)):
                return True
        
        return False
    
    def get_build_config(self) -> Dict:
        """Generate build configuration based on detected type."""
        project_type = self.detect()
        
        configs = {
            self.MOBILE_APP: {
                "builder": "expo",
                "deployer": "mobile",
                "test_framework": "jest",
                "platforms": ["ios", "android", "web"],
            },
            self.DESKTOP_APP: {
                "builder": "electron-builder",
                "deployer": "desktop",
                "test_framework": "jest",
                "platforms": ["windows", "mac", "linux"],
            },
            self.HYBRID_APP: {
                "builder": "multi",
                "deployer": "hybrid",
                "test_framework": "jest",
                "platforms": ["ios", "android", "web", "windows", "mac", "linux"],
                "sub_projects": {
                    "mobile": "expo",
                    "desktop": "desktop",
                }
            },
            self.WEB_APP: {
                "builder": "webpack",
                "deployer": "web",
                "test_framework": "jest",
                "platforms": ["web"],
            },
            "ml_pipeline": {
                "builder": "python",
                "deployer": "ecs",
                "test_framework": "pytest",
            },
            "firmware_edge": {
                "builder": "platformio",
                "deployer": "ota",
                "test_framework": "unity",
            },
            "native_app": {
                "builder": "native",
                "deployer": "binary",
                "test_framework": "native",
            },
            "hdl_fpga": {
                "builder": "vivado",
                "deployer": "fpga",
                "test_framework": "cocotb",
            },
        }
        
        return configs.get(project_type, {"builder": "unknown", "deployer": "unknown"})
    
    def get_project_capabilities(self) -> Dict[str, bool]:
        """Get detailed project capabilities."""
        return {
            "has_mobile": self.MOBILE_APP in self._detected_types,
            "has_desktop": self.DESKTOP_APP in self._detected_types,
            "has_web": self.WEB_APP in self._detected_types,
            "is_hybrid": self._is_hybrid_app(),
            "mobile_platform": self._get_mobile_platform() if self.MOBILE_APP in self._detected_types else None,
            "desktop_platform": "electron" if self.DESKTOP_APP in self._detected_types else None,
        }
    
    def _get_mobile_platform(self) -> str:
        """Determine mobile platform type."""
        expo_path = self.project_path / "expo"
        if expo_path.exists():
            return "expo"
        elif self._has_react_native_indicators():
            return "react-native"
        return "unknown"