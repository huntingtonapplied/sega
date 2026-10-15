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
# SEGA MODULE - Render Deployer
# ===============================================================
# File: src/sega/ship/deployers/render_deployer.py
# Purpose: Deploy applications to Render platform
#
# Description: Handles deployment of web services, static sites,
# background workers, and cron jobs to Render. Uses the Render
# API for deployments and service management.
#
# Dependencies:
# - External: requests, json, os
# - Internal: base_deployer, deployment_result
#
# Used by: deployment_router for render project types
#

"""Render platform deployer for SEGA."""

import json
import os
import time
from typing import Dict, Any, Optional, List
import requests
from .base_deployer import BaseDeployer
from ...core.deployment_result import DeploymentResult


class RenderDeployer(BaseDeployer):
    """Deployer for Render platform (Web Services, Static Sites, Workers)."""

    RENDER_API_BASE = "https://api.render.com/v1"

    def __init__(self, config: Dict[str, Any] = None, entity: Optional[str] = None):
        super().__init__()
        self.config = config or {}
        self.entity = entity
        
        # Use credentials resolver for entity-aware token lookup
        if entity:
            from ...utils.credentials import get_credentials_resolver
            resolver = get_credentials_resolver()
            creds = resolver.get_credentials("render", entity)
            self.api_key = creds.api_key
        else:
            self.api_key = os.environ.get("RENDER_API_KEY")

    def deploy(
        self,
        target: str,
        strategy: str = "rolling",
        image_tag: str = "latest",
        force: bool = False,
        dry_run: bool = False,
        **kwargs,
    ) -> DeploymentResult:
        """Deploy to Render.
        
        Args:
            target: Environment (development, staging, production)
            strategy: Not directly used (Render handles deployment strategy)
            image_tag: Docker image tag or git ref
            force: Clear build cache
            dry_run: Preview what would be deployed
            
        Returns:
            DeploymentResult with deployment status
        """
        if not self.api_key:
            return self._create_deployment_result(
                success=False,
                message="Render deployment failed",
                error="RENDER_API_KEY environment variable not set",
            )
        
        project_path = kwargs.get("project_path")
        if project_path:
            project_path = os.path.expanduser(project_path)
        
        project_config = self._get_project_config(project_path)
        
        # Get Render-specific config from sega.yaml
        render_config = self._get_render_config(project_config)
        service_id = kwargs.get("service_id") or render_config.get("service_id")
        
        if not service_id:
            return self._create_deployment_result(
                success=False,
                message="Render deployment failed",
                error="No Render service_id specified",
            )
        
        if dry_run:
            return self._dry_run_deployment(target, render_config, service_id)
        
        try:
            # Trigger deployment via API
            deploy_response = self._trigger_deploy(
                service_id=service_id,
                clear_cache=force,
            )
            
            if not deploy_response:
                return self._create_deployment_result(
                    success=False,
                    message="Render deployment failed",
                    error="Failed to trigger deployment",
                )
            
            deploy_id = deploy_response.get("id")
            
            # Wait for deployment to complete (optional)
            if kwargs.get("wait", True):
                final_status = self._wait_for_deployment(service_id, deploy_id)
                success = final_status in ["live", "succeeded"]
            else:
                success = True
                final_status = "triggered"
            
            # Get service URL
            service_url = self._get_service_url(service_id)
            
            return self._create_deployment_result(
                success=success,
                message=f"Deployed to Render: {service_url}",
                deployment_id=deploy_id,
                metadata={
                    "platform": "render",
                    "service_id": service_id,
                    "url": service_url,
                    "target": target,
                    "status": final_status,
                },
            )
            
        except Exception as e:
            return self._create_deployment_result(
                success=False,
                message="Render deployment failed",
                error=str(e),
            )

    def get_deployment_status(self, target: str) -> Dict[str, Any]:
        """Get deployment status from Render."""
        if not self.api_key:
            return {"status": "error", "error": "No API key"}
        
        try:
            # List services
            response = requests.get(
                f"{self.RENDER_API_BASE}/services",
                headers=self._get_headers(),
                timeout=30,
            )
            
            if response.status_code == 200:
                services = response.json()
                return {
                    "status": "available",
                    "services": services,
                }
            
            return {"status": "error", "error": response.text}
            
        except Exception as e:
            return {"status": "error", "error": str(e)}

    def rollback(
        self, target: str, to_version: Optional[str] = None
    ) -> DeploymentResult:
        """Rollback to a previous Render deployment.
        
        Args:
            target: Environment to rollback
            to_version: Deploy ID to rollback to
        """
        # Render doesn't have a direct rollback API
        # You can redeploy a previous commit
        return DeploymentResult(
            success=False,
            error="Render rollback requires redeploying a previous commit. "
                  "Use deploy with the specific git ref instead.",
        )

    def _trigger_deploy(
        self,
        service_id: str,
        clear_cache: bool = False,
    ) -> Optional[Dict[str, Any]]:
        """Trigger a deployment via Render API."""
        try:
            payload = {}
            if clear_cache:
                payload["clearCache"] = "clear"
            
            response = requests.post(
                f"{self.RENDER_API_BASE}/services/{service_id}/deploys",
                headers=self._get_headers(),
                json=payload,
                timeout=60,
            )
            
            if response.status_code in [200, 201]:
                return response.json()
            
            return None
            
        except Exception:
            return None

    def _wait_for_deployment(
        self,
        service_id: str,
        deploy_id: str,
        timeout: int = 600,
        poll_interval: int = 10,
    ) -> str:
        """Wait for deployment to complete."""
        start_time = time.time()
        
        while time.time() - start_time < timeout:
            try:
                response = requests.get(
                    f"{self.RENDER_API_BASE}/services/{service_id}/deploys/{deploy_id}",
                    headers=self._get_headers(),
                    timeout=30,
                )
                
                if response.status_code == 200:
                    deploy = response.json()
                    status = deploy.get("status")
                    
                    if status in ["live", "succeeded", "failed", "canceled"]:
                        return status
                
            except Exception:
                pass
            
            time.sleep(poll_interval)
        
        return "timeout"

    def _get_service_url(self, service_id: str) -> str:
        """Get the URL for a Render service."""
        try:
            response = requests.get(
                f"{self.RENDER_API_BASE}/services/{service_id}",
                headers=self._get_headers(),
                timeout=30,
            )
            
            if response.status_code == 200:
                service = response.json()
                return service.get("serviceDetails", {}).get("url", "unknown")
            
            return "unknown"
            
        except Exception:
            return "unknown"

    def _get_headers(self) -> Dict[str, str]:
        """Get API request headers."""
        return {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }

    def _get_render_config(self, project_config: Dict) -> Dict[str, Any]:
        """Extract Render-specific configuration."""
        build_config = project_config.get("build_config", {})
        
        # Check for platforms.render in sega.yaml
        if "platforms" in build_config and "render" in build_config["platforms"]:
            return build_config["platforms"]["render"]
        
        # Return default config
        return {
            "plan": "starter",
            "region": "oregon",
            "auto_deploy": True,
        }

    def _dry_run_deployment(
        self, target: str, render_config: Dict, service_id: str
    ) -> DeploymentResult:
        """Simulate deployment without executing."""
        return self._create_deployment_result(
            success=True,
            message=f"[DRY RUN] Would deploy to Render ({target})",
            metadata={
                "platform": "render",
                "service_id": service_id,
                "target": target,
                "dry_run": True,
                "config": render_config,
            },
        )

    def list_services(self) -> List[Dict[str, Any]]:
        """List all Render services."""
        if not self.api_key:
            return []
        
        try:
            response = requests.get(
                f"{self.RENDER_API_BASE}/services",
                headers=self._get_headers(),
                timeout=30,
            )
            
            if response.status_code == 200:
                return response.json()
            
            return []
            
        except Exception:
            return []

    def get_service_logs(
        self,
        service_id: str,
        limit: int = 100,
    ) -> str:
        """Get logs for a Render service."""
        if not self.api_key:
            return "No API key"
        
        try:
            response = requests.get(
                f"{self.RENDER_API_BASE}/services/{service_id}/logs",
                headers=self._get_headers(),
                params={"limit": limit},
                timeout=30,
            )
            
            if response.status_code == 200:
                logs = response.json()
                return "\n".join([log.get("message", "") for log in logs])
            
            return f"Error: {response.text}"
            
        except Exception as e:
            return f"Error: {e}"

    def suspend_service(self, service_id: str) -> DeploymentResult:
        """Suspend a Render service."""
        if not self.api_key:
            return DeploymentResult(success=False, error="No API key")
        
        try:
            response = requests.post(
                f"{self.RENDER_API_BASE}/services/{service_id}/suspend",
                headers=self._get_headers(),
                timeout=30,
            )
            
            if response.status_code in [200, 202]:
                return self._create_deployment_result(
                    success=True,
                    message=f"Service {service_id} suspended",
                )
            
            return self._create_deployment_result(
                success=False,
                message="Failed to suspend service",
                error=response.text,
            )
            
        except Exception as e:
            return DeploymentResult(success=False, error=str(e))

    def resume_service(self, service_id: str) -> DeploymentResult:
        """Resume a suspended Render service."""
        if not self.api_key:
            return DeploymentResult(success=False, error="No API key")
        
        try:
            response = requests.post(
                f"{self.RENDER_API_BASE}/services/{service_id}/resume",
                headers=self._get_headers(),
                timeout=30,
            )
            
            if response.status_code in [200, 202]:
                return self._create_deployment_result(
                    success=True,
                    message=f"Service {service_id} resumed",
                )
            
            return self._create_deployment_result(
                success=False,
                message="Failed to resume service",
                error=response.text,
            )
            
        except Exception as e:
            return DeploymentResult(success=False, error=str(e))
