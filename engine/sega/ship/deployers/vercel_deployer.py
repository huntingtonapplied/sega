#!/usr/bin/env python
# -*- coding: utf-8 -*-
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

# ===============================================================
# SEGA MODULE - Vercel Deployer
# ===============================================================
# File: src/sega/ship/deployers/vercel_deployer.py
# Purpose: Deploy applications to Vercel platform
#
# Description: Handles deployment of Next.js, static sites, and
# serverless functions to Vercel using the Vercel CLI and API.
# Supports preview deployments, production deployments, and
# environment variable management.
#
# Dependencies:
# - External: subprocess, json, os
# - Internal: base_deployer, deployment_result
#
# Used by: deployment_router for vercel/static_web project types
#

"""Vercel platform deployer for SEGA."""

import json
import os
import subprocess
from typing import Dict, Any, Optional, List
from .base_deployer import BaseDeployer
from ...core.deployment_result import DeploymentResult
from ...utils.credentials import get_credentials_resolver


class VercelDeployer(BaseDeployer):
    """Deployer for Vercel platform (Next.js, static sites, serverless)."""

    def __init__(self, config: Optional[Dict[str, Any]] = None, entity: Optional[str] = None):
        super().__init__()
        self.config = config or {}
        self.entity = entity
        
        # Use credentials resolver for entity-aware token lookup
        if entity:
            resolver = get_credentials_resolver()
            creds = resolver.get_credentials("vercel", entity)
            self.vercel_token = creds.token
            self.vercel_org_id = creds.org_id
            self.vercel_project_id = creds.project_id
        else:
            # Fall back to generic env vars
            self.vercel_token = os.environ.get("VERCEL_TOKEN")
            self.vercel_org_id = os.environ.get("VERCEL_ORG_ID")
            self.vercel_project_id = os.environ.get("VERCEL_PROJECT_ID")

    def deploy(
        self,
        target: str,
        strategy: str = "rolling",
        image_tag: str = "latest",
        force: bool = False,
        dry_run: bool = False,
        **kwargs,
    ) -> DeploymentResult:
        """Deploy to Vercel.
        
        Args:
            target: Environment (development, staging, production)
            strategy: Not used for Vercel (always instant)
            image_tag: Git ref or commit to deploy
            force: Force deployment even with warnings
            dry_run: Preview what would be deployed
            
        Returns:
            DeploymentResult with deployment URL and status
        """
        # Get project path - this is where the Vercel CLI needs to run from
        project_path = kwargs.get("project_path")
        if project_path:
            project_path = os.path.expanduser(project_path)
        
        project_config = self._get_project_config(project_path)
        
        # Get Vercel-specific config from sega.yaml
        vercel_config = self._get_vercel_config(project_config)
        
        if dry_run:
            return self._dry_run_deployment(target, vercel_config)
        
        # Determine if this is a production deployment
        is_production = target.lower() in ["production", "prod"]
        
        # Validate project path exists
        if project_path and not os.path.isdir(project_path):
            return self._create_deployment_result(
                success=False,
                message="Deployment failed",
                error=f"Project path does not exist: {project_path}",
            )
        
        try:
            # Build the Vercel CLI command
            cmd = self._build_deploy_command(
                is_production=is_production,
                vercel_config=vercel_config,
                force=force,
            )
            
            # Execute deployment from the project directory
            result = self.resource_manager.run_subprocess(
                cmd,
                timeout=600,  # 10 minutes max
                env=self._get_vercel_env(vercel_config),
                cwd=project_path,  # Run from project directory
            )
            
            if result.returncode != 0:
                return self._create_deployment_result(
                    success=False,
                    message="Vercel deployment failed",
                    error=result.stderr or "Unknown error",
                )
            
            # Parse deployment URL from output
            deployment_url = self._parse_deployment_url(result.stdout)
            
            return self._create_deployment_result(
                success=True,
                message=f"Deployed to Vercel: {deployment_url}",
                deployment_id=self._extract_deployment_id(deployment_url),
                metadata={
                    "platform": "vercel",
                    "url": deployment_url,
                    "target": target,
                    "production": is_production,
                    "framework": vercel_config.get("framework", "auto"),
                },
            )
            
        except Exception as e:
            return self._create_deployment_result(
                success=False,
                message="Vercel deployment failed",
                error=str(e),
            )

    def get_deployment_status(self, target: str) -> Dict[str, Any]:
        """Get deployment status from Vercel."""
        try:
            cmd = ["vercel", "ls", "--json"]
            if self.vercel_token:
                cmd.extend(["--token", self.vercel_token])
            
            result = self.resource_manager.run_subprocess(cmd, timeout=30)
            
            if result.returncode == 0:
                deployments = json.loads(result.stdout)
                return {
                    "status": "available",
                    "deployments": deployments[:5],  # Last 5 deployments
                }
            
            return {"status": "error", "error": result.stderr}
            
        except Exception as e:
            return {"status": "error", "error": str(e)}

    def rollback(
        self, target: str, to_version: Optional[str] = None
    ) -> DeploymentResult:
        """Rollback to a previous Vercel deployment.
        
        Args:
            target: Environment to rollback
            to_version: Deployment URL or ID to rollback to
        """
        if not to_version:
            return DeploymentResult(
                success=False,
                error="Vercel rollback requires a deployment URL or ID",
            )
        
        try:
            # Promote a previous deployment to production
            cmd = ["vercel", "promote", to_version]
            if self.vercel_token:
                cmd.extend(["--token", self.vercel_token])
            
            result = self.resource_manager.run_subprocess(cmd, timeout=120)
            
            if result.returncode == 0:
                return self._create_deployment_result(
                    success=True,
                    message=f"Rolled back to {to_version}",
                    metadata={"rollback_target": to_version},
                )
            
            return self._create_deployment_result(
                success=False,
                message="Rollback failed",
                error=result.stderr,
            )
            
        except Exception as e:
            return DeploymentResult(success=False, error=str(e))

    def _get_vercel_config(self, project_config: Dict) -> Dict[str, Any]:
        """Extract Vercel-specific configuration."""
        build_config = project_config.get("build_config", {})
        
        # Check for platforms.vercel in sega.yaml
        if "platforms" in build_config and "vercel" in build_config["platforms"]:
            return build_config["platforms"]["vercel"].get("defaults", {})
        
        # Fall back to detecting framework
        return {
            "framework": self._detect_framework(project_config),
            "build_command": "npm run build",
            "output_directory": ".next",
            "install_command": "npm install",
        }

    def _detect_framework(self, project_config: Dict) -> str:
        """Auto-detect the framework for Vercel."""
        project_type = project_config.get("project_type", "")
        
        framework_map = {
            "web_app": "nextjs",
            "static_web": "static",
            "react_app": "create-react-app",
            "vue_app": "vue",
            "svelte_app": "svelte",
        }
        
        return framework_map.get(project_type, "nextjs")

    def _build_deploy_command(
        self,
        is_production: bool,
        vercel_config: Dict,
        force: bool,
    ) -> List[str]:
        """Build the Vercel CLI deployment command."""
        cmd = ["vercel"]
        
        if is_production:
            cmd.append("--prod")
        
        if force:
            cmd.append("--force")
        
        # Add token if available
        if self.vercel_token:
            cmd.extend(["--token", self.vercel_token])
        
        # Confirm deployment without prompts
        cmd.append("--yes")
        
        return cmd

    def _get_vercel_env(self, vercel_config: Dict) -> Dict[str, str]:
        """Get environment variables for Vercel deployment."""
        env = os.environ.copy()
        
        # Add any environment variables from config
        env_vars = vercel_config.get("environment_variables", [])
        for var in env_vars:
            if var in os.environ:
                env[var] = os.environ[var]
        
        return env

    def _parse_deployment_url(self, output: str) -> str:
        """Parse deployment URL from Vercel CLI output."""
        # Vercel outputs the URL on the last non-empty line
        lines = output.strip().split("\n")
        for line in reversed(lines):
            line = line.strip()
            if line.startswith("https://"):
                return line
        return "unknown"

    def _extract_deployment_id(self, url: str) -> str:
        """Extract deployment ID from Vercel URL."""
        # URL format: https://project-xxxx.vercel.app
        if ".vercel.app" in url:
            return url.replace("https://", "").replace(".vercel.app", "")
        return url

    def _dry_run_deployment(
        self, target: str, vercel_config: Dict
    ) -> DeploymentResult:
        """Simulate deployment without executing."""
        return self._create_deployment_result(
            success=True,
            message=f"[DRY RUN] Would deploy to Vercel ({target})",
            metadata={
                "platform": "vercel",
                "target": target,
                "dry_run": True,
                "framework": vercel_config.get("framework", "auto"),
                "config": vercel_config,
            },
        )

    def list_deployments(self, limit: int = 10) -> List[Dict[str, Any]]:
        """List recent Vercel deployments."""
        try:
            cmd = ["vercel", "ls", "--json"]
            if self.vercel_token:
                cmd.extend(["--token", self.vercel_token])
            
            result = self.resource_manager.run_subprocess(cmd, timeout=30)
            
            if result.returncode == 0:
                deployments = json.loads(result.stdout)
                return deployments[:limit]
            
            return []
            
        except Exception:
            return []

    def get_deployment_logs(self, deployment_id: str) -> str:
        """Get logs for a specific deployment."""
        try:
            cmd = ["vercel", "logs", deployment_id]
            if self.vercel_token:
                cmd.extend(["--token", self.vercel_token])
            
            result = self.resource_manager.run_subprocess(cmd, timeout=60)
            return result.stdout if result.returncode == 0 else result.stderr
            
        except Exception as e:
            return f"Error fetching logs: {e}"

    # =========================================================================
    # Project Creation & Management
    # =========================================================================

    def create_project(
        self,
        name: str,
        framework: str = "nextjs",
        git_repo: Optional[str] = None,
        root_directory: Optional[str] = None,
        build_command: Optional[str] = None,
        output_directory: Optional[str] = None,
        install_command: Optional[str] = None,
        env_vars: Optional[Dict[str, str]] = None,
    ) -> DeploymentResult:
        """Create a new Vercel project.
        
        Args:
            name: Project name (will be used in URL: name.vercel.app)
            framework: Framework preset (nextjs, vite, create-react-app, etc.)
            git_repo: Git repository URL to connect (optional)
            root_directory: Root directory if monorepo
            build_command: Custom build command
            output_directory: Build output directory
            install_command: Custom install command
            env_vars: Environment variables to set
            
        Returns:
            DeploymentResult with project details
        """
        if not self.vercel_token:
            return self._create_deployment_result(
                success=False,
                message="Cannot create project",
                error="VERCEL_TOKEN not set",
            )
        
        try:
            import requests
            
            # Vercel API endpoint for creating projects
            api_url = "https://api.vercel.com/v9/projects"
            
            headers = {
                "Authorization": f"Bearer {self.vercel_token}",
                "Content-Type": "application/json",
            }
            
            # Build project payload
            payload: Dict[str, Any] = {
                "name": name,
                "framework": framework,
            }
            
            # Add optional settings
            if git_repo:
                payload["gitRepository"] = {
                    "type": "github",  # or gitlab, bitbucket
                    "repo": git_repo,
                }
            
            if root_directory:
                payload["rootDirectory"] = root_directory
            
            if build_command:
                payload["buildCommand"] = build_command
            
            if output_directory:
                payload["outputDirectory"] = output_directory
            
            if install_command:
                payload["installCommand"] = install_command
            
            # Add team/org if configured
            params = {}
            if self.vercel_org_id:
                params["teamId"] = self.vercel_org_id
            
            response = requests.post(
                api_url,
                headers=headers,
                json=payload,
                params=params,
                timeout=30,
            )
            
            if response.status_code in [200, 201]:
                project_data = response.json()
                project_id = project_data.get("id")
                
                # Set environment variables if provided
                if env_vars and project_id:
                    self._set_env_vars(project_id, env_vars)
                
                return self._create_deployment_result(
                    success=True,
                    message=f"Created Vercel project: {name}",
                    deployment_id=project_id,
                    metadata={
                        "platform": "vercel",
                        "project_id": project_id,
                        "project_name": name,
                        "framework": framework,
                        "url": f"https://{name}.vercel.app",
                        "dashboard": f"https://vercel.com/{name}",
                    },
                )
            else:
                error_data = response.json()
                return self._create_deployment_result(
                    success=False,
                    message="Failed to create Vercel project",
                    error=error_data.get("error", {}).get("message", response.text),
                )
                
        except Exception as e:
            return self._create_deployment_result(
                success=False,
                message="Failed to create Vercel project",
                error=str(e),
            )

    def _set_env_vars(
        self,
        project_id: str,
        env_vars: Dict[str, str],
        target: str = "production",
    ) -> bool:
        """Set environment variables for a project."""
        try:
            import requests
            
            api_url = f"https://api.vercel.com/v10/projects/{project_id}/env"
            
            headers = {
                "Authorization": f"Bearer {self.vercel_token}",
                "Content-Type": "application/json",
            }
            
            params = {}
            if self.vercel_org_id:
                params["teamId"] = self.vercel_org_id
            
            # Add each environment variable
            for key, value in env_vars.items():
                payload = {
                    "key": key,
                    "value": value,
                    "type": "encrypted",
                    "target": [target, "preview", "development"],
                }
                
                response = requests.post(
                    api_url,
                    headers=headers,
                    json=payload,
                    params=params,
                    timeout=30,
                )
                
                if response.status_code not in [200, 201]:
                    return False
            
            return True
            
        except Exception:
            return False

    def delete_project(self, project_id: str) -> DeploymentResult:
        """Delete a Vercel project."""
        if not self.vercel_token:
            return self._create_deployment_result(
                success=False,
                message="Cannot delete project",
                error="VERCEL_TOKEN not set",
            )
        
        try:
            import requests
            
            api_url = f"https://api.vercel.com/v9/projects/{project_id}"
            
            headers = {
                "Authorization": f"Bearer {self.vercel_token}",
            }
            
            params = {}
            if self.vercel_org_id:
                params["teamId"] = self.vercel_org_id
            
            response = requests.delete(
                api_url,
                headers=headers,
                params=params,
                timeout=30,
            )
            
            if response.status_code in [200, 204]:
                return self._create_deployment_result(
                    success=True,
                    message=f"Deleted Vercel project: {project_id}",
                )
            else:
                return self._create_deployment_result(
                    success=False,
                    message="Failed to delete project",
                    error=response.text,
                )
                
        except Exception as e:
            return self._create_deployment_result(
                success=False,
                message="Failed to delete project",
                error=str(e),
            )

    def list_projects(self) -> List[Dict[str, Any]]:
        """List all Vercel projects."""
        if not self.vercel_token:
            return []
        
        try:
            import requests
            
            api_url = "https://api.vercel.com/v9/projects"
            
            headers = {
                "Authorization": f"Bearer {self.vercel_token}",
            }
            
            params = {}
            if self.vercel_org_id:
                params["teamId"] = self.vercel_org_id
            
            response = requests.get(
                api_url,
                headers=headers,
                params=params,
                timeout=30,
            )
            
            if response.status_code == 200:
                data = response.json()
                return [
                    {
                        "id": p.get("id"),
                        "name": p.get("name"),
                        "framework": p.get("framework"),
                        "url": f"https://{p.get('name')}.vercel.app",
                    }
                    for p in data.get("projects", [])
                ]
            
            return []
            
        except Exception:
            return []

    def link_domain(
        self,
        project_id: str,
        domain: str,
    ) -> DeploymentResult:
        """Link a custom domain to a Vercel project."""
        if not self.vercel_token:
            return self._create_deployment_result(
                success=False,
                message="Cannot link domain",
                error="VERCEL_TOKEN not set",
            )
        
        try:
            import requests
            
            api_url = f"https://api.vercel.com/v10/projects/{project_id}/domains"
            
            headers = {
                "Authorization": f"Bearer {self.vercel_token}",
                "Content-Type": "application/json",
            }
            
            params = {}
            if self.vercel_org_id:
                params["teamId"] = self.vercel_org_id
            
            payload = {"name": domain}
            
            response = requests.post(
                api_url,
                headers=headers,
                json=payload,
                params=params,
                timeout=30,
            )
            
            if response.status_code in [200, 201]:
                return self._create_deployment_result(
                    success=True,
                    message=f"Linked domain {domain} to project",
                    metadata={"domain": domain, "project_id": project_id},
                )
            else:
                error_data = response.json()
                return self._create_deployment_result(
                    success=False,
                    message="Failed to link domain",
                    error=error_data.get("error", {}).get("message", response.text),
                )
                
        except Exception as e:
            return self._create_deployment_result(
                success=False,
                message="Failed to link domain",
                error=str(e),
            )
