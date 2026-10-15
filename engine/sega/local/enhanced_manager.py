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
SEGA ENHANCED LOCAL DEPLOYMENT MANAGER
==============================================================================
File: src/sega/deployment/enhanced_local_deployment_manager.py
Project: SEGA (Scalable Engineering & Growth Automation)
Copyright: 2022-2025 SEGA Contributors
License: Apache-2.0

SEGA MODULE: Deployment/EnhancedLocalDeployment
COMPONENT: Enhanced Local Deployment Manager with Mobile/Desktop Support
PURPOSE: Manage local development deployments including web, mobile, and desktop
DEPENDENCIES: docker-compose, subprocess, pathlib
USAGE: Used by sega local commands for comprehensive local testing

This enhanced manager extends the bBase LocalDeploymentManager to include:
- Expo web deployment in Docker/local modes
- Desktop app management (local only, not Docker)
- Intelligent service ordering
- Port conflict detection
==============================================================================
"""

import subprocess
import os
from pathlib import Path
from typing import Dict, List, Optional, Tuple
import time
import yaml


class EnhancedLocalDeploymentManager:
    """Enhanced local deployment manager with mobile/desktop support."""
    
    def __init__(self, workspace_root: Optional[Path] = None, config: Optional[Dict] = None):
        self.workspace_root = workspace_root or Path.cwd()
        self.config = config or self._load_config()
        self.port_allocations = self._load_port_allocations()
        
    def _load_config(self) -> Dict:
        """Load workspace configuration."""
        config_path = self.workspace_root / ".sega.yml"
        if config_path.exists():
            with open(config_path) as f:
                return yaml.safe_load(f)
        return {"projects": []}
    
    def _load_port_allocations(self) -> Dict[str, Dict[str, int]]:
        """Load standard port allocations.

        AUTHORITATIVE: /docs/standards/infrastructure/PORT_ALLOCATION_STANDARDS.md
        API: 8xxx, Frontend: 3xxx, Desktop: 33xx, Mobile/Expo: 190xx

        This is a curated per-fleet subset (some projects have no mobile or
        desktop surface), sourced from the `[fleet.port_allocations]` config
        map. Ships empty for new installs.
        """
        from sega.core.config import get_config
        return {
            name: dict(ports)
            for name, ports in get_config().fleet.port_allocations.items()
        }
    
    def deploy_project(self, project_name: str, mode: str = "docker") -> bool:
        """Deploy a project with all its services."""
        project_path = self.workspace_root / project_name
        if not project_path.exists():
            print(f"[ERROR] Project {project_name} not found")
            return False
        
        os.chdir(project_path)
        
        # Detect project capabilities
        has_backend = (project_path / "backend").exists() or (project_path / "api").exists()
        has_frontend = (project_path / "frontend").exists()
        has_expo = (project_path / "expo").exists()
        has_desktop = (project_path / "desktop").exists()
        
        print(f"\n[INFO] Deploying {project_name} in {mode} mode")
        print(f"  Backend: {'' if has_backend else ''}")
        print(f"  Frontend: {'' if has_frontend else ''}")
        print(f"  Expo Web: {'' if has_expo else ''}")
        print(f"  Desktop: {'' if has_desktop else ''}")
        
        if mode == "docker":
            return self._deploy_docker(project_name, has_backend, has_frontend, has_expo, has_desktop)
        else:
            return self._deploy_shared(project_name, has_backend, has_frontend, has_expo, has_desktop)
    
    def _deploy_docker(self, project_name: str, has_backend: bool, has_frontend: bool, 
                      has_expo: bool, has_desktop: bool) -> bool:
        """Deploy using Docker Compose."""
        try:
            # Check if docker-compose.yml exists
            if not Path("docker-compose.yml").exists():
                print("[WARNING] No docker-compose.yml found, trying Makefile")
                return self._deploy_makefile(project_name, "up")
            
            # Start all services including expo-web
            cmd = ["docker-compose", "up", "-d"]
            
            # If desktop exists, warn that it won't run in Docker
            if has_desktop:
                print("[WARNING] Desktop aApps cannot run in Docker mode. Use 'sega local dev' for desktop support.")
            
            print(f"[INFO] Starting Docker services for {project_name}")
            result = subprocess.run(cmd, capture_output=True, text=True)
            
            if result.returncode != 0:
                print(f"[ERROR] Docker deployment failed: {result.stderr}")
                return False
            
            # Wait for services to be healthy
            time.sleep(3)
            
            # Show running services
            subprocess.run(["docker-compose", "ps"])
            
            # Display access URLs
            self._display_access_urls(project_name, has_backend, has_frontend, has_expo, False)
            
            return True
            
        except Exception as e:
            print(f"[ERROR] Failed to deploy {project_name}: {e}")
            return False
    
    def _deploy_shared(self, project_name: str, has_backend: bool, has_frontend: bool,
                      has_expo: bool, has_desktop: bool) -> bool:
        """Deploy using shared dependencies (dev mode)."""
        try:
            # Start in order: databases -> backend -> frontend -> expo web -> desktop
            
            # 1. Start databases in Docker
            print(f"[INFO] Starting databases for {project_name}")
            subprocess.run(["docker-compose", "up", "-d", "postgres", "redis"], check=True)
            time.sleep(2)
            
            # 2. Start backend
            if has_backend:
                print(f"[INFO] Starting backend for {project_name}")
                backend_process = self._start_backend_shared(project_name)
                if not backend_process:
                    return False
            
            # 3. Start frontend
            if has_frontend:
                print(f"[INFO] Starting frontend for {project_name}")
                frontend_process = self._start_frontend_shared(project_name)
                if not frontend_process:
                    return False
            
            # 4. Start Expo web
            if has_expo:
                print(f"[INFO] Starting Expo web for {project_name}")
                expo_process = self._start_expo_web_shared(project_name)
                if not expo_process:
                    return False
            
            # 5. Start desktop
            if has_desktop:
                print(f"[INFO] Starting desktop app for {project_name}")
                desktop_process = self._start_desktop_shared(project_name)
                if not desktop_process:
                    print("[WARNING] Desktop app failed to start, continuing anyway")
            
            # Display access URLs
            self._display_access_urls(project_name, has_backend, has_frontend, has_expo, has_desktop)
            
            return True
            
        except Exception as e:
            print(f"[ERROR] Failed to deploy {project_name}: {e}")
            return False
    
    def _start_backend_shared(self, project_name: str) -> Optional[subprocess.Popen]:
        """Start backend with shared venv."""
        ports = self.port_allocations.get(project_name, {})
        api_port = ports.get("api", 3001)
        
        # Check if using Django or FastAPI
        manage_py = Path("backend/manage.py")
        if manage_py.exists():
            # Django
            cmd = [
                "bash", "-c",
                f"cd backend && source {self.workspace_root}/.venv/bin/activate && "
                f"python manage.py runserver 0.0.0.0:{api_port}"
            ]
        else:
            # Assume FastAPI or similar
            cmd = [
                "bash", "-c", 
                f"cd backend && source {self.workspace_root}/.venv/bin/activate && "
                f"uvicorn main:app --host 0.0.0.0 --port {api_port} --reload"
            ]
        
        return subprocess.Popen(cmd)
    
    def _start_frontend_shared(self, project_name: str) -> Optional[subprocess.Popen]:
        """Start frontend with shared node_modules."""
        ports = self.port_allocations.get(project_name, {})
        frontend_port = ports.get("frontend", 3101)
        
        cmd = [
            "bash", "-c",
            f"cd frontend && npm run dev -- --port {frontend_port}"
        ]
        
        return subprocess.Popen(cmd)
    
    def _start_expo_web_shared(self, project_name: str) -> Optional[subprocess.Popen]:
        """Start Expo in web mode with shared node_modules."""
        ports = self.port_allocations.get(project_name, {})
        expo_port = ports.get("expo_web", 3201)
        
        cmd = [
            "bash", "-c",
            f"cd expo && npx expo start --web --port {expo_port}"
        ]
        
        return subprocess.Popen(cmd)
    
    def _start_desktop_shared(self, project_name: str) -> Optional[subprocess.Popen]:
        """Start desktop app with shared node_modules."""
        cmd = [
            "bash", "-c",
            "cd desktop && npm run dev"
        ]
        
        return subprocess.Popen(cmd)
    
    def _display_access_urls(self, project_name: str, has_backend: bool, has_frontend: bool,
                           has_expo: bool, has_desktop: bool) -> None:
        """Display access URLs for all services."""
        ports = self.port_allocations.get(project_name, {})
        
        print(f"\n[SUCCESS] {project_name} services running at:")
        
        if has_backend:
            print(f"  API:       http://localhost:{ports.get('api', 3001)}")
        
        if has_frontend:
            print(f"  Frontend:  http://localhost:{ports.get('frontend', 3101)}")
        
        if has_expo:
            print(f"  Expo Web:  http://localhost:{ports.get('expo_web', 3201)}")
        
        if has_desktop:
            print("  Desktop:   Running in Electron window")
            print("  DevTools:  http://localhost:9222 (if debug mode)")
    
    def _deploy_makefile(self, project_name: str, target: str) -> bool:
        """Fallback to Makefile deployment."""
        try:
            cmd = ["make", target]
            result = subprocess.run(cmd, capture_output=True, text=True)
            return result.returncode == 0
        except:
            return False
    
    def deploy_all(self, mode: str = "docker") -> Dict[str, bool]:
        """Deploy all projects in workspace."""
        results = {}
        
        # Get project order based on dependencies
        ordered_projects = self._get_deployment_order()
        
        print(f"\n[INFO] Deploying {len(ordered_projects)} projects in {mode} mode")
        print(f"[INFO] Order: {' -> '.join(ordered_projects)}")
        
        for project in ordered_projects:
            results[project] = self.deploy_project(project, mode)
            
            # Small delay between projects to avoid port conflicts
            time.sleep(2)
        
        return results
    
    def _get_deployment_order(self) -> List[str]:
        """Get optimal deployment order for projects."""
        # Curated deployment-ordering tiers (infrastructure first, then
        # services, then applications), sourced from the
        # `[fleet.deployment_tiers]` config map. Tiers deploy in declaration
        # order; ships empty for new installs.
        from sega.core.config import get_config
        order = []

        # Build final order based on what exists
        for category in get_config().fleet.deployment_tiers.values():
            for project in category:
                project_path = self.workspace_root / project
                if project_path.exists():
                    order.append(project)

        return order
    
    def check_port_conflicts(self) -> List[Tuple[str, int]]:
        """Check for port conflicts before deployment."""
        conflicts = []
        
        for project, ports in self.port_allocations.items():
            for service, port in ports.items():
                # Check if port is in use
                cmd = ["lsof", "-i", f":{port}"]
                result = subprocess.run(cmd, capture_output=True, text=True)
                
                if result.returncode == 0:  # Port is in use
                    conflicts.append((f"{project}/{service}", port))
        
        return conflicts
    
    def stop_project(self, project_name: str) -> bool:
        """Stop a project's services."""
        project_path = self.workspace_root / project_name
        if not project_path.exists():
            return False
        
        os.chdir(project_path)
        
        try:
            # Try docker-compose first
            subprocess.run(["docker-compose", "down"], check=True)
            
            # Kill any remaining processes on project ports
            ports = self.port_allocations.get(project_name, {})
            for port in ports.values():
                self._kill_port(port)
            
            return True
        except:
            return False
    
    def _kill_port(self, port: int) -> None:
        """Kill process using a specific port."""
        try:
            cmd = f"lsof -ti:{port} | xargs kill -9"
            subprocess.run(cmd, shell=True)
        except:
            pass