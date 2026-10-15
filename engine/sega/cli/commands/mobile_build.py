#!/usr/bin/env python3
"""
SEGA Mobile Build Infrastructure
Enhanced commands for building and testing mobile apps with backend connectivity
"""

import os
import json
import subprocess
import socket
import time
from pathlib import Path
from typing import Optional, Dict, Any

from ...utils.console import console
from ...utils.project_detector import ProjectDetector
from ...core.config import get_config
from .base import BaseCommand


# Standard mobile/expo port mapping for projects, derived from central config.
# AUTHORITATIVE: /docs/standards/infrastructure/PORT_ALLOCATION_STANDARDS.md
# The project set is the curated `[fleet] app_projects` config list; the port
# VALUES come from config (mobile/expo port = 19000 + id).
_MOBILE_PROJECTS = list(get_config().fleet.app_projects)


def _build_mobile_ports():
    """Build {project: expo_port} from central config (ports.mobile = 19000+id)."""
    cfg = get_config()
    ports = {}
    for name in _MOBILE_PROJECTS:
        proj = cfg.get_project(name)
        if proj is None:
            continue
        ports[name] = proj.ports.mobile
    return ports


class MobileBuildCommand(BaseCommand):
    """Enhanced mobile build and test infrastructure"""

    # Standard mobile/expo port mapping for projects (config-derived).
    PROJECT_PORTS = _build_mobile_ports()

    def __init__(self):
        super().__init__()
        self.detector = ProjectDetector()
    
    def prebuild(self, project: Optional[str] = None, platform: Optional[str] = None, clean: bool = True):
        """
        Generate native code with cross-platform standards
        
        Args:
            project: Project name (auto-detected if None)
            platform: 'ios', 'android', or None for both
            clean: Whether to clean before prebuild
        """
        project = project or self.detector.detect_project()
        if not project:
            console.print("[red]Could not detect project[/red]")
            return False
        
        expo_dir = Path(project) / "expo"
        if not expo_dir.exists():
            console.print(f"[red]No expo directory found in {project}[/red]")
            return False
        
        console.print(f"[cyan]Prebuilding {project} for {platform or 'all platforms'}[/cyan]")
        
        # Step 1: Apply cross-platform standards
        self._apply_cross_platform_standards(expo_dir)
        
        # Step 2: Prebuild
        cmd = ["npx", "expo", "prebuild"]
        if platform:
            cmd.extend(["--platform", platform])
        if clean:
            cmd.append("--clean")
        
        result = subprocess.run(cmd, cwd=expo_dir)
        if result.returncode != 0:
            console.print("[red]Prebuild failed[/red]")
            return False
        
        # Step 3: Apply native patches
        self._apply_native_patches(expo_dir, platform)
        
        console.print("[green]Prebuild complete![/green]")
        return True
    
    def start_with_backend(self, project: Optional[str] = None):
        """
        Start backend and Expo with proper network configuration
        
        Args:
            project: Project name (auto-detected if None)
        """
        project = project or self.detector.detect_project()
        if not project:
            console.print("[red]Could not detect project[/red]")
            return False
        
        expo_dir = Path(project) / "expo"
        if not expo_dir.exists():
            console.print(f"[red]No expo directory found in {project}[/red]")
            return False
        
        # Step 1: Start backend
        console.print(f"[cyan]Starting backend for {project}...[/cyan]")
        backend_process = self._start_backend(project)
        
        # Step 2: Get network configuration
        backend_port = self.PROJECT_PORTS.get(project, 3001)
        local_ip = self._get_local_ip()
        
        console.print(f"[green]Backend running on port {backend_port}[/green]")
        console.print(f"[green]Local IP: {local_ip}[/green]")
        
        # Step 3: Create backend configuration
        backend_config = {
            "android_emulator": f"http://10.0.2.2:{backend_port}/api",
            "ios_simulator": f"http://localhost:{backend_port}/api",
            "physical_device": f"http://{local_ip}:{backend_port}/api",
            "localhost": f"http://localhost:{backend_port}/api"
        }
        
        config_file = expo_dir / ".backend-config.json"
        with open(config_file, "w") as f:
            json.dump(backend_config, f, indent=2)
        
        console.print("[cyan]Backend configuration:[/cyan]")
        console.print(f"  Android Emulator: {backend_config['android_emulator']}")
        console.print(f"  iOS Simulator: {backend_config['ios_simulator']}")
        console.print(f"  Physical Device: {backend_config['physical_device']}")
        
        # Step 4: Start Expo
        console.print("[cyan]Starting Expo...[/cyan]")
        env = os.environ.copy()
        env['EXPO_PUBLIC_DEVICE_API_URL'] = backend_config['physical_device']
        env['EXPO_PUBLIC_API_URL'] = backend_config['localhost']
        
        try:
            subprocess.run([
                "npx", "expo", "start",
                "--lan",
                "--localhost", 
                "--port", "19000"
            ], cwd=expo_dir, env=env)
        except KeyboardInterrupt:
            console.print("\n[yellow]Shutting down...[/yellow]")
            if backend_process:
                backend_process.terminate()
    
    def build_dev(self, project: Optional[str] = None, platform: str = "android", device: bool = False):
        """
        Build development client for testing
        
        Args:
            project: Project name
            platform: 'ios' or 'android'
            device: Build for device (vs emulator/simulator)
        """
        project = project or self.detector.detect_project()
        if not project:
            console.print("[red]Could not detect project[/red]")
            return False
        
        expo_dir = Path(project) / "expo"
        
        # Configure backend URL
        backend_port = self.PROJECT_PORTS.get(project, 3001)
        local_ip = self._get_local_ip()
        
        env = os.environ.copy()
        if platform == "android":
            if device:
                env['EXPO_PUBLIC_API_URL'] = f"http://{local_ip}:{backend_port}/api"
            else:
                env['EXPO_PUBLIC_API_URL'] = f"http://10.0.2.2:{backend_port}/api"
            
            cmd = ["npx", "expo", "run:android"]
            if device:
                cmd.append("--device")
            else:
                cmd.append("--emulator")
        
        elif platform == "ios":
            if device:
                env['EXPO_PUBLIC_API_URL'] = f"http://{local_ip}:{backend_port}/api"
            else:
                env['EXPO_PUBLIC_API_URL'] = f"http://localhost:{backend_port}/api"
            
            cmd = ["npx", "expo", "run:ios"]
            if device:
                cmd.append("--device")
            else:
                cmd.append("--simulator")
        
        console.print(f"[cyan]Building {platform} development client...[/cyan]")
        console.print(f"[cyan]Backend URL: {env['EXPO_PUBLIC_API_URL']}[/cyan]")
        
        subprocess.run(cmd, cwd=expo_dir, env=env)
    
    def test_with_backend(self, project: Optional[str] = None, platform: Optional[str] = None):
        """
        Run mobile tests with backend running
        
        Args:
            project: Project name
            platform: Optional platform to test
        """
        project = project or self.detector.detect_project()
        if not project:
            console.print("[red]Could not detect project[/red]")
            return False
        
        # Start backend
        console.print(f"[cyan]Starting backend for testing...[/cyan]")
        backend_process = self._start_backend(project)
        
        # Wait for backend to be ready
        time.sleep(5)
        
        # Run tests
        expo_dir = Path(project) / "expo"
        
        try:
            if platform:
                console.print(f"[cyan]Running {platform} tests...[/cyan]")
                subprocess.run(["npm", "test", f"--platform={platform}"], cwd=expo_dir)
            else:
                console.print("[cyan]Running all tests...[/cyan]")
                subprocess.run(["npm", "test"], cwd=expo_dir)
        finally:
            if backend_process:
                backend_process.terminate()
    
    # Helper methods
    
    def _apply_cross_platform_standards(self, expo_dir: Path):
        """Apply cross-platform version standards"""
        settings_file = expo_dir / "expo-settings.json"
        
        if not settings_file.exists():
            settings = {
                "crossPlatformTarget": {
                    "expo": "52.0.47",
                    "react": "18.3.1",
                    "reactNative": "0.76.9",
                    "metro": "0.81.5"
                },
                "appliedAt": time.strftime("%Y-%m-%d %H:%M:%S")
            }
            
            with open(settings_file, "w") as f:
                json.dump(settings, f, indent=2)
            
            console.print("[green]Cross-platform standards applied[/green]")
    
    def _apply_native_patches(self, expo_dir: Path, platform: Optional[str]):
        """Apply native patches after prebuild"""
        patches_dir = expo_dir / "native-patches"
        
        if not patches_dir.exists():
            return
        
        if platform in [None, "android"]:
            android_script = patches_dir / "android" / "post-prebuild.sh"
            if android_script.exists():
                console.print("[cyan]Applying Android patches...[/cyan]")
                subprocess.run(["bash", str(android_script)], cwd=expo_dir)
        
        if platform in [None, "ios"]:
            ios_script = patches_dir / "ios" / "post-prebuild.sh"
            if ios_script.exists():
                console.print("[cyan]Applying iOS patches...[/cyan]")
                subprocess.run(["bash", str(ios_script)], cwd=expo_dir)
    
    def _start_backend(self, project: str) -> Optional[subprocess.Popen]:
        """Start backend service for project"""
        project_dir = Path(project)
        
        # Try docker-compose first
        compose_file = project_dir / "docker-compose.yml"
        if compose_file.exists():
            console.print("[cyan]Starting backend with docker-compose...[/cyan]")
            return subprocess.Popen(
                ["docker-compose", "up", "api", "db", "redis"],
                cwd=project_dir
            )
        
        # Try make dev-shared
        makefile = project_dir / "Makefile"
        if makefile.exists():
            console.print("[cyan]Starting backend with make dev-shared...[/cyan]")
            return subprocess.Popen(
                ["make", "dev-shared"],
                cwd=project_dir
            )
        
        console.print("[yellow]No backend start method found[/yellow]")
        return None
    
    def _get_local_ip(self) -> str:
        """Get local IP address for device access"""
        try:
            # Create a socket to external address to get local IP
            s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            s.connect(("8.8.8.8", 80))
            local_ip = s.getsockname()[0]
            s.close()
            return local_ip
        except:
            # Fallback to hostname resolution
            hostname = socket.gethostname()
            return socket.gethostbyname(hostname)


# Integration with main SEGA mobile command
def register_commands(mobile_cmd):
    """Register mobile build commands with SEGA"""
    build_cmd = MobileBuildCommand()
    
    # Add subcommands
    mobile_cmd.add_command("prebuild", build_cmd.prebuild)
    mobile_cmd.add_command("start-with-backend", build_cmd.start_with_backend)
    mobile_cmd.add_command("build-dev", build_cmd.build_dev)
    mobile_cmd.add_command("test-with-backend", build_cmd.test_with_backend)