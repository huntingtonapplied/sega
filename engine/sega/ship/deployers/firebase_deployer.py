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
# SEGA MODULE - Firebase Deployer
# ===============================================================
# File: src/sega/ship/deployers/firebase_deployer.py
# Purpose: Deploy applications to Firebase platform
#
# Description: Handles deployment of static sites, hosting,
# Firestore rules, Cloud Functions, and Storage to Firebase.
# Supports multi-site hosting and environment-based deployments.
#
# Dependencies:
# - External: subprocess, json, os
# - Internal: base_deployer, deployment_result
#
# Used by: deployment_router for firebase_app project types
#

"""Firebase platform deployer for SEGA."""

import json
import os
import subprocess
from typing import Dict, Any, Optional, List
from .base_deployer import BaseDeployer
from ...core.deployment_result import DeploymentResult


class FirebaseDeployer(BaseDeployer):
    """Deployer for Firebase platform (Hosting, Functions, Firestore, Storage)."""

    def __init__(self, config: Dict[str, Any] = None, entity: Optional[str] = None):
        super().__init__()
        self.config = config or {}
        self.entity = entity
        
        # Use credentials resolver for entity-aware token lookup
        if entity:
            from ...utils.credentials import get_credentials_resolver
            resolver = get_credentials_resolver()
            creds = resolver.get_credentials("firebase", entity)
            self.firebase_token = creds.token
        else:
            self.firebase_token = os.environ.get("FIREBASE_TOKEN")

    def deploy(
        self,
        target: str,
        strategy: str = "rolling",
        image_tag: str = "latest",
        force: bool = False,
        dry_run: bool = False,
        **kwargs,
    ) -> DeploymentResult:
        """Deploy to Firebase.
        
        Args:
            target: Environment (development, staging, production)
            strategy: Not used for Firebase
            image_tag: Not used for Firebase
            force: Force deployment
            dry_run: Preview what would be deployed
            
        Returns:
            DeploymentResult with deployment status
        """
        project_path = kwargs.get("project_path")
        if project_path:
            project_path = os.path.expanduser(project_path)
        
        project_config = self._get_project_config(project_path)
        
        # Get Firebase-specific config from sega.yaml
        firebase_config = self._get_firebase_config(project_config)
        project_id = kwargs.get("project_id") or firebase_config.get("project_id")
        
        if not project_id:
            return self._create_deployment_result(
                success=False,
                message="Firebase deployment failed",
                error="No Firebase project ID specified",
            )
        
        if dry_run:
            return self._dry_run_deployment(target, firebase_config, project_id)
        
        try:
            # Determine what to deploy
            deploy_targets = self._get_deploy_targets(firebase_config)
            
            # Build the Firebase CLI command
            cmd = self._build_deploy_command(
                project_id=project_id,
                targets=deploy_targets,
                force=force,
            )
            
            # Execute deployment
            result = self.resource_manager.run_subprocess(
                cmd,
                timeout=900,  # 15 minutes max (functions can take time)
                env=self._get_firebase_env(),
            )
            
            if result.returncode != 0:
                return self._create_deployment_result(
                    success=False,
                    message="Firebase deployment failed",
                    error=result.stderr or result.stdout or "Unknown error",
                )
            
            # Parse hosting URL from output
            hosting_url = self._parse_hosting_url(result.stdout, project_id)
            
            return self._create_deployment_result(
                success=True,
                message=f"Deployed to Firebase: {hosting_url}",
                deployment_id=f"firebase-{project_id}-{target}",
                metadata={
                    "platform": "firebase",
                    "project_id": project_id,
                    "url": hosting_url,
                    "target": target,
                    "deployed_targets": deploy_targets,
                },
            )
            
        except Exception as e:
            return self._create_deployment_result(
                success=False,
                message="Firebase deployment failed",
                error=str(e),
            )

    def get_deployment_status(self, target: str) -> Dict[str, Any]:
        """Get deployment status from Firebase."""
        try:
            # Get hosting releases
            cmd = ["firebase", "hosting:channel:list", "--json"]
            if self.firebase_token:
                cmd.extend(["--token", self.firebase_token])
            
            result = self.resource_manager.run_subprocess(cmd, timeout=30)
            
            if result.returncode == 0:
                try:
                    data = json.loads(result.stdout)
                    return {
                        "status": "available",
                        "channels": data.get("result", []),
                    }
                except json.JSONDecodeError:
                    return {"status": "available", "raw_output": result.stdout}
            
            return {"status": "error", "error": result.stderr}
            
        except Exception as e:
            return {"status": "error", "error": str(e)}

    def rollback(
        self, target: str, to_version: Optional[str] = None
    ) -> DeploymentResult:
        """Rollback to a previous Firebase hosting release.
        
        Args:
            target: Environment to rollback
            to_version: Release version to rollback to
        """
        if not to_version:
            return DeploymentResult(
                success=False,
                error="Firebase rollback requires a release version",
            )
        
        try:
            # Clone a previous release
            cmd = [
                "firebase",
                "hosting:clone",
                to_version,
                "live",  # Clone to live channel
            ]
            if self.firebase_token:
                cmd.extend(["--token", self.firebase_token])
            
            result = self.resource_manager.run_subprocess(cmd, timeout=120)
            
            if result.returncode == 0:
                return self._create_deployment_result(
                    success=True,
                    message=f"Rolled back to release {to_version}",
                    metadata={"rollback_target": to_version},
                )
            
            return self._create_deployment_result(
                success=False,
                message="Rollback failed",
                error=result.stderr,
            )
            
        except Exception as e:
            return DeploymentResult(success=False, error=str(e))

    def deploy_hosting(
        self,
        project_id: str,
        site: Optional[str] = None,
        channel: Optional[str] = None,
    ) -> DeploymentResult:
        """Deploy only Firebase Hosting."""
        cmd = ["firebase", "deploy", "--only", "hosting"]
        
        if project_id:
            cmd.extend(["--project", project_id])
        
        if site:
            cmd[3] = f"hosting:{site}"
        
        if channel:
            cmd = ["firebase", "hosting:channel:deploy", channel]
            if project_id:
                cmd.extend(["--project", project_id])
        
        if self.firebase_token:
            cmd.extend(["--token", self.firebase_token])
        
        try:
            result = self.resource_manager.run_subprocess(cmd, timeout=300)
            
            if result.returncode == 0:
                return self._create_deployment_result(
                    success=True,
                    message="Firebase Hosting deployed successfully",
                    metadata={
                        "platform": "firebase",
                        "service": "hosting",
                        "project_id": project_id,
                        "site": site,
                        "channel": channel,
                    },
                )
            
            return self._create_deployment_result(
                success=False,
                message="Firebase Hosting deployment failed",
                error=result.stderr,
            )
            
        except Exception as e:
            return DeploymentResult(success=False, error=str(e))

    def deploy_functions(self, project_id: str) -> DeploymentResult:
        """Deploy only Cloud Functions."""
        cmd = ["firebase", "deploy", "--only", "functions"]
        
        if project_id:
            cmd.extend(["--project", project_id])
        
        if self.firebase_token:
            cmd.extend(["--token", self.firebase_token])
        
        try:
            result = self.resource_manager.run_subprocess(cmd, timeout=600)
            
            if result.returncode == 0:
                return self._create_deployment_result(
                    success=True,
                    message="Cloud Functions deployed successfully",
                    metadata={
                        "platform": "firebase",
                        "service": "functions",
                        "project_id": project_id,
                    },
                )
            
            return self._create_deployment_result(
                success=False,
                message="Cloud Functions deployment failed",
                error=result.stderr,
            )
            
        except Exception as e:
            return DeploymentResult(success=False, error=str(e))

    def deploy_rules(
        self,
        project_id: str,
        services: List[str] = None,
    ) -> DeploymentResult:
        """Deploy Firestore/Storage rules."""
        services = services or ["firestore", "storage"]
        
        only_flag = ",".join([f"{s}:rules" for s in services])
        cmd = ["firebase", "deploy", "--only", only_flag]
        
        if project_id:
            cmd.extend(["--project", project_id])
        
        if self.firebase_token:
            cmd.extend(["--token", self.firebase_token])
        
        try:
            result = self.resource_manager.run_subprocess(cmd, timeout=120)
            
            if result.returncode == 0:
                return self._create_deployment_result(
                    success=True,
                    message="Security rules deployed successfully",
                    metadata={
                        "platform": "firebase",
                        "service": "rules",
                        "services": services,
                        "project_id": project_id,
                    },
                )
            
            return self._create_deployment_result(
                success=False,
                message="Rules deployment failed",
                error=result.stderr,
            )
            
        except Exception as e:
            return DeploymentResult(success=False, error=str(e))

    def _get_firebase_config(self, project_config: Dict) -> Dict[str, Any]:
        """Extract Firebase-specific configuration."""
        build_config = project_config.get("build_config", {})
        
        # Check for platforms.firebase in sega.yaml
        if "platforms" in build_config and "firebase" in build_config["platforms"]:
            return build_config["platforms"]["firebase"]
        
        # Return default config
        return {
            "hosting": {"public": "dist"},
            "firestore": {"enabled": False},
            "functions": {"enabled": False},
            "storage": {"enabled": False},
        }

    def _get_deploy_targets(self, firebase_config: Dict) -> List[str]:
        """Determine which Firebase services to deploy."""
        targets = []
        
        # Always deploy hosting if configured
        if firebase_config.get("hosting", {}).get("enabled", True):
            targets.append("hosting")
        
        # Optional services
        if firebase_config.get("firestore", {}).get("enabled"):
            targets.append("firestore")
        
        if firebase_config.get("functions", {}).get("enabled"):
            targets.append("functions")
        
        if firebase_config.get("storage", {}).get("enabled"):
            targets.append("storage")
        
        if firebase_config.get("auth", {}).get("enabled"):
            # Auth rules are part of the project setup, not deployment
            pass
        
        return targets if targets else ["hosting"]

    def _build_deploy_command(
        self,
        project_id: str,
        targets: List[str],
        force: bool,
    ) -> List[str]:
        """Build the Firebase CLI deployment command."""
        cmd = ["firebase", "deploy"]
        
        if targets:
            cmd.extend(["--only", ",".join(targets)])
        
        if project_id:
            cmd.extend(["--project", project_id])
        
        if force:
            cmd.append("--force")
        
        if self.firebase_token:
            cmd.extend(["--token", self.firebase_token])
        
        return cmd

    def _get_firebase_env(self) -> Dict[str, str]:
        """Get environment variables for Firebase deployment."""
        env = os.environ.copy()
        
        # Ensure CI mode for non-interactive deployment
        env["CI"] = "true"
        
        return env

    def _parse_hosting_url(self, output: str, project_id: str) -> str:
        """Parse hosting URL from Firebase CLI output."""
        # Look for hosting URL in output
        for line in output.split("\n"):
            if "Hosting URL:" in line:
                return line.split("Hosting URL:")[-1].strip()
            if f"{project_id}.web.app" in line:
                return f"https://{project_id}.web.app"
            if f"{project_id}.firebaseapp.com" in line:
                return f"https://{project_id}.firebaseapp.com"
        
        # Default URL
        return f"https://{project_id}.web.app"

    def _dry_run_deployment(
        self, target: str, firebase_config: Dict, project_id: str
    ) -> DeploymentResult:
        """Simulate deployment without executing."""
        targets = self._get_deploy_targets(firebase_config)
        
        return self._create_deployment_result(
            success=True,
            message=f"[DRY RUN] Would deploy to Firebase ({target})",
            metadata={
                "platform": "firebase",
                "project_id": project_id,
                "target": target,
                "dry_run": True,
                "deploy_targets": targets,
                "config": firebase_config,
            },
        )

    def create_preview_channel(
        self,
        project_id: str,
        channel_name: str,
        expires: str = "7d",
    ) -> DeploymentResult:
        """Create a preview channel for testing."""
        cmd = [
            "firebase",
            "hosting:channel:deploy",
            channel_name,
            "--expires",
            expires,
        ]
        
        if project_id:
            cmd.extend(["--project", project_id])
        
        if self.firebase_token:
            cmd.extend(["--token", self.firebase_token])
        
        try:
            result = self.resource_manager.run_subprocess(cmd, timeout=300)
            
            if result.returncode == 0:
                # Parse preview URL
                preview_url = self._parse_channel_url(result.stdout, channel_name)
                
                return self._create_deployment_result(
                    success=True,
                    message=f"Preview channel created: {preview_url}",
                    metadata={
                        "platform": "firebase",
                        "channel": channel_name,
                        "preview_url": preview_url,
                        "expires": expires,
                    },
                )
            
            return self._create_deployment_result(
                success=False,
                message="Preview channel creation failed",
                error=result.stderr,
            )
            
        except Exception as e:
            return DeploymentResult(success=False, error=str(e))

    def _parse_channel_url(self, output: str, channel_name: str) -> str:
        """Parse preview channel URL from output."""
        for line in output.split("\n"):
            if "Channel URL:" in line or channel_name in line:
                # Extract URL
                if "https://" in line:
                    start = line.index("https://")
                    end = line.find(" ", start)
                    return line[start:end] if end > start else line[start:]
        return "unknown"

    # =========================================================================
    # Project Creation & Management
    # =========================================================================

    def create_project(
        self,
        project_id: str,
        display_name: Optional[str] = None,
        default_bucket: Optional[str] = None,
    ) -> DeploymentResult:
        """Create a new Firebase project.
        
        Note: Firebase project creation requires Google Cloud billing.
        This uses the Firebase CLI which must be authenticated.
        
        Args:
            project_id: Unique project ID (lowercase, hyphens allowed)
            display_name: Human-readable project name
            default_bucket: Default Cloud Storage bucket name
            
        Returns:
            DeploymentResult with project details
        """
        # Firebase project creation via CLI
        cmd = ["firebase", "projects:create", project_id]
        
        if display_name:
            cmd.extend(["--display-name", display_name])
        
        if self.firebase_token:
            cmd.extend(["--token", self.firebase_token])
        
        try:
            result = self.resource_manager.run_subprocess(cmd, timeout=120)
            
            if result.returncode == 0:
                # Initialize Firebase in the project directory
                return self._create_deployment_result(
                    success=True,
                    message=f"Created Firebase project: {project_id}",
                    deployment_id=project_id,
                    metadata={
                        "platform": "firebase",
                        "project_id": project_id,
                        "display_name": display_name or project_id,
                        "console_url": f"https://console.firebase.google.com/project/{project_id}",
                    },
                )
            else:
                return self._create_deployment_result(
                    success=False,
                    message="Failed to create Firebase project",
                    error=result.stderr or result.stdout,
                )
                
        except Exception as e:
            return self._create_deployment_result(
                success=False,
                message="Failed to create Firebase project",
                error=str(e),
            )

    def init_project(
        self,
        project_id: str,
        features: Optional[List[str]] = None,
        project_path: Optional[str] = None,
    ) -> DeploymentResult:
        """Initialize Firebase in a project directory.
        
        Creates firebase.json and enables specified features.
        
        Args:
            project_id: Firebase project ID to use
            features: Features to enable (hosting, firestore, functions, storage)
            project_path: Directory to initialize (defaults to current)
            
        Returns:
            DeploymentResult with initialization status
        """
        features = features or ["hosting"]
        
        # Build init command
        cmd = ["firebase", "init", "--project", project_id]
        
        # Add features
        for feature in features:
            cmd.append(feature)
        
        if self.firebase_token:
            cmd.extend(["--token", self.firebase_token])
        
        # Non-interactive mode
        cmd.append("--non-interactive")
        
        try:
            # Run in project directory if specified
            env = os.environ.copy()
            env["CI"] = "true"
            
            result = self.resource_manager.run_subprocess(
                cmd,
                timeout=120,
                env=env,
            )
            
            if result.returncode == 0:
                return self._create_deployment_result(
                    success=True,
                    message=f"Initialized Firebase project with: {', '.join(features)}",
                    metadata={
                        "platform": "firebase",
                        "project_id": project_id,
                        "features": features,
                    },
                )
            else:
                return self._create_deployment_result(
                    success=False,
                    message="Failed to initialize Firebase",
                    error=result.stderr or result.stdout,
                )
                
        except Exception as e:
            return self._create_deployment_result(
                success=False,
                message="Failed to initialize Firebase",
                error=str(e),
            )

    def add_webapp(
        self,
        project_id: str,
        app_name: str,
    ) -> DeploymentResult:
        """Add a web app to a Firebase project.
        
        Args:
            project_id: Firebase project ID
            app_name: Display name for the web app
            
        Returns:
            DeploymentResult with web app config
        """
        cmd = [
            "firebase",
            "apps:create",
            "web",
            app_name,
            "--project",
            project_id,
        ]
        
        if self.firebase_token:
            cmd.extend(["--token", self.firebase_token])
        
        try:
            result = self.resource_manager.run_subprocess(cmd, timeout=60)
            
            if result.returncode == 0:
                # Get SDK config
                config_result = self._get_webapp_config(project_id)
                
                return self._create_deployment_result(
                    success=True,
                    message=f"Created web app: {app_name}",
                    metadata={
                        "platform": "firebase",
                        "project_id": project_id,
                        "app_name": app_name,
                        "sdk_config": config_result,
                    },
                )
            else:
                return self._create_deployment_result(
                    success=False,
                    message="Failed to create web app",
                    error=result.stderr,
                )
                
        except Exception as e:
            return self._create_deployment_result(
                success=False,
                message="Failed to create web app",
                error=str(e),
            )

    def _get_webapp_config(self, project_id: str) -> Optional[Dict[str, Any]]:
        """Get Firebase web app SDK configuration."""
        cmd = [
            "firebase",
            "apps:sdkconfig",
            "web",
            "--project",
            project_id,
            "--json",
        ]
        
        if self.firebase_token:
            cmd.extend(["--token", self.firebase_token])
        
        try:
            result = self.resource_manager.run_subprocess(cmd, timeout=30)
            
            if result.returncode == 0:
                return json.loads(result.stdout)
            return None
            
        except Exception:
            return None

    def list_projects(self) -> List[Dict[str, Any]]:
        """List all Firebase projects."""
        cmd = ["firebase", "projects:list", "--json"]
        
        if self.firebase_token:
            cmd.extend(["--token", self.firebase_token])
        
        try:
            result = self.resource_manager.run_subprocess(cmd, timeout=30)
            
            if result.returncode == 0:
                data = json.loads(result.stdout)
                return [
                    {
                        "project_id": p.get("projectId"),
                        "display_name": p.get("displayName"),
                        "project_number": p.get("projectNumber"),
                    }
                    for p in data.get("result", [])
                ]
            return []
            
        except Exception:
            return []

    def setup_hosting_site(
        self,
        project_id: str,
        site_id: str,
    ) -> DeploymentResult:
        """Create a new Firebase Hosting site (for multi-site hosting).
        
        Args:
            project_id: Firebase project ID
            site_id: Unique site ID (will be available at site_id.web.app)
            
        Returns:
            DeploymentResult with site details
        """
        cmd = [
            "firebase",
            "hosting:sites:create",
            site_id,
            "--project",
            project_id,
        ]
        
        if self.firebase_token:
            cmd.extend(["--token", self.firebase_token])
        
        try:
            result = self.resource_manager.run_subprocess(cmd, timeout=60)
            
            if result.returncode == 0:
                return self._create_deployment_result(
                    success=True,
                    message=f"Created hosting site: {site_id}",
                    metadata={
                        "platform": "firebase",
                        "project_id": project_id,
                        "site_id": site_id,
                        "url": f"https://{site_id}.web.app",
                    },
                )
            else:
                return self._create_deployment_result(
                    success=False,
                    message="Failed to create hosting site",
                    error=result.stderr,
                )
                
        except Exception as e:
            return self._create_deployment_result(
                success=False,
                message="Failed to create hosting site",
                error=str(e),
            )
