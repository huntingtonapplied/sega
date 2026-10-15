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
# SEGA MODULE - AWS Amplify Deployer
# ===============================================================
# File: src/sega/ship/deployers/amplify_deployer.py
# Purpose: Deploy applications to AWS Amplify
#
# Description: Handles deployment of web applications to AWS Amplify.
# Supports both Amplify Hosting (CI/CD) and manual deployments.
# Uses AWS SDK (boto3) for API interactions.
#
# Dependencies:
# - External: boto3, json, os
# - Internal: base_deployer, deployment_result
#
# Used by: deployment_router for amplify project types
#

"""AWS Amplify platform deployer for SEGA."""

import json
import os
import time
import zipfile
import tempfile
from typing import Dict, Any, Optional, List
from pathlib import Path

try:
    import boto3
    from botocore.exceptions import ClientError
    HAS_BOTO3 = True
except ImportError:
    HAS_BOTO3 = False

from .base_deployer import BaseDeployer
from ...core.deployment_result import DeploymentResult


class AmplifyDeployer(BaseDeployer):
    """Deployer for AWS Amplify (Hosting, CI/CD)."""

    def __init__(self, config: Dict[str, Any] = None, entity: Optional[str] = None):
        super().__init__()
        self.config = config or {}
        self.entity = entity
        
        # Entity-aware credentials can be handled via AWS credential profiles
        # or environment variables with entity suffix
        self.region = config.get("region", "us-east-1") if config else "us-east-1"
        
        if HAS_BOTO3:
            self.amplify_client = boto3.client("amplify", region_name=self.region)
            self.s3_client = boto3.client("s3", region_name=self.region)
        else:
            self.amplify_client = None
            self.s3_client = None

    def deploy(
        self,
        target: str,
        strategy: str = "rolling",
        image_tag: str = "latest",
        force: bool = False,
        dry_run: bool = False,
        **kwargs,
    ) -> DeploymentResult:
        """Deploy to AWS Amplify.
        
        Args:
            target: Environment/branch (development, staging, production, main)
            strategy: Not used (Amplify manages deployment strategy)
            image_tag: Not used for Amplify
            force: Force deployment even with warnings
            dry_run: Preview what would be deployed
            
        Returns:
            DeploymentResult with deployment status
        """
        if not HAS_BOTO3:
            return self._create_deployment_result(
                success=False,
                message="AWS Amplify deployment failed",
                error="boto3 not installed. Run: pip install boto3",
            )
        
        project_path = kwargs.get("project_path")
        if project_path:
            project_path = os.path.expanduser(project_path)
        
        project_config = self._get_project_config(project_path)
        
        # Get Amplify-specific config from sega.yaml
        amplify_config = self._get_amplify_config(project_config)
        app_id = kwargs.get("app_id") or amplify_config.get("app_id")
        
        if not app_id:
            return self._create_deployment_result(
                success=False,
                message="AWS Amplify deployment failed",
                error="No Amplify app_id specified",
            )
        
        if dry_run:
            return self._dry_run_deployment(target, amplify_config, app_id)
        
        try:
            # Determine branch name from target
            branch_name = self._get_branch_name(target, amplify_config)
            
            # Check if we're doing a manual deployment or triggering CI/CD
            if kwargs.get("manual", False) or amplify_config.get("manual_deploy", False):
                # Manual deployment - upload built assets
                return self._manual_deploy(
                    app_id=app_id,
                    branch_name=branch_name,
                    source_dir=kwargs.get("source_dir", "dist"),
                )
            else:
                # Trigger CI/CD deployment
                return self._trigger_build(
                    app_id=app_id,
                    branch_name=branch_name,
                )
            
        except ClientError as e:
            return self._create_deployment_result(
                success=False,
                message="AWS Amplify deployment failed",
                error=str(e),
            )
        except Exception as e:
            return self._create_deployment_result(
                success=False,
                message="AWS Amplify deployment failed",
                error=str(e),
            )

    def get_deployment_status(self, target: str) -> Dict[str, Any]:
        """Get deployment status from AWS Amplify."""
        if not HAS_BOTO3:
            return {"status": "error", "error": "boto3 not installed"}
        
        try:
            # List apps
            response = self.amplify_client.list_apps()
            
            apps = []
            for app in response.get("apps", []):
                apps.append({
                    "app_id": app["appId"],
                    "name": app["name"],
                    "default_domain": app.get("defaultDomain"),
                    "repository": app.get("repository"),
                })
            
            return {
                "status": "available",
                "apps": apps,
            }
            
        except Exception as e:
            return {"status": "error", "error": str(e)}

    def rollback(
        self, target: str, to_version: Optional[str] = None
    ) -> DeploymentResult:
        """Rollback to a previous Amplify deployment.
        
        Args:
            target: Environment/branch to rollback
            to_version: Job ID to rollback to
        """
        # Amplify doesn't have a direct rollback API
        # You need to redeploy a previous commit
        return DeploymentResult(
            success=False,
            error="Amplify rollback requires redeploying a previous commit. "
                  "Trigger a new build with the specific commit/tag.",
        )

    def _trigger_build(
        self,
        app_id: str,
        branch_name: str,
    ) -> DeploymentResult:
        """Trigger a CI/CD build on Amplify."""
        try:
            response = self.amplify_client.start_job(
                appId=app_id,
                branchName=branch_name,
                jobType="RELEASE",
            )
            
            job_summary = response.get("jobSummary", {})
            job_id = job_summary.get("jobId")
            
            return self._create_deployment_result(
                success=True,
                message=f"Amplify build triggered: {job_id}",
                deployment_id=job_id,
                metadata={
                    "platform": "amplify",
                    "app_id": app_id,
                    "branch": branch_name,
                    "job_id": job_id,
                    "status": job_summary.get("status"),
                },
            )
            
        except ClientError as e:
            return self._create_deployment_result(
                success=False,
                message="Failed to trigger Amplify build",
                error=str(e),
            )

    def _manual_deploy(
        self,
        app_id: str,
        branch_name: str,
        source_dir: str,
    ) -> DeploymentResult:
        """Manually deploy built assets to Amplify."""
        try:
            # Create deployment
            response = self.amplify_client.create_deployment(
                appId=app_id,
                branchName=branch_name,
            )
            
            job_id = response.get("jobId")
            zip_upload_url = response.get("zipUploadUrl")
            
            if not zip_upload_url:
                return self._create_deployment_result(
                    success=False,
                    message="Failed to get upload URL",
                    error="No zipUploadUrl in response",
                )
            
            # Create zip of source directory
            source_path = Path(source_dir)
            if not source_path.exists():
                return self._create_deployment_result(
                    success=False,
                    message="Source directory not found",
                    error=f"Directory {source_dir} does not exist",
                )
            
            # Create temporary zip file
            with tempfile.NamedTemporaryFile(suffix=".zip", delete=False) as tmp:
                zip_path = tmp.name
            
            try:
                self._create_zip(source_path, zip_path)
                
                # Upload zip to presigned URL
                with open(zip_path, "rb") as f:
                    import requests
                    upload_response = requests.put(
                        zip_upload_url,
                        data=f,
                        headers={"Content-Type": "application/zip"},
                        timeout=300,
                    )
                    
                    if upload_response.status_code not in [200, 201]:
                        return self._create_deployment_result(
                            success=False,
                            message="Failed to upload deployment",
                            error=f"Upload failed: {upload_response.status_code}",
                        )
                
                # Start deployment
                self.amplify_client.start_deployment(
                    appId=app_id,
                    branchName=branch_name,
                    jobId=job_id,
                )
                
                return self._create_deployment_result(
                    success=True,
                    message=f"Manual deployment started: {job_id}",
                    deployment_id=job_id,
                    metadata={
                        "platform": "amplify",
                        "app_id": app_id,
                        "branch": branch_name,
                        "job_id": job_id,
                        "deploy_type": "manual",
                    },
                )
                
            finally:
                # Clean up temp file
                if os.path.exists(zip_path):
                    os.remove(zip_path)
            
        except ClientError as e:
            return self._create_deployment_result(
                success=False,
                message="Manual deployment failed",
                error=str(e),
            )

    def _create_zip(self, source_dir: Path, zip_path: str):
        """Create a zip file from a directory."""
        with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zipf:
            for file_path in source_dir.rglob("*"):
                if file_path.is_file():
                    arcname = file_path.relative_to(source_dir)
                    zipf.write(file_path, arcname)

    def _get_branch_name(self, target: str, amplify_config: Dict) -> str:
        """Map target environment to branch name."""
        branch_mapping = amplify_config.get("branch_mapping", {})
        
        # Default mappings
        default_mapping = {
            "development": "develop",
            "staging": "staging",
            "production": "main",
            "prod": "main",
        }
        
        # Merge with custom mapping
        mapping = {**default_mapping, **branch_mapping}
        
        return mapping.get(target.lower(), target)

    def _get_amplify_config(self, project_config: Dict) -> Dict[str, Any]:
        """Extract Amplify-specific configuration."""
        build_config = project_config.get("build_config", {})
        
        # Check for platforms.amplify in sega.yaml
        if "platforms" in build_config and "amplify" in build_config["platforms"]:
            return build_config["platforms"]["amplify"]
        
        # Return default config
        return {
            "region": "us-east-1",
            "branch": "main",
        }

    def _dry_run_deployment(
        self, target: str, amplify_config: Dict, app_id: str
    ) -> DeploymentResult:
        """Simulate deployment without executing."""
        branch_name = self._get_branch_name(target, amplify_config)
        
        return self._create_deployment_result(
            success=True,
            message=f"[DRY RUN] Would deploy to AWS Amplify ({target})",
            metadata={
                "platform": "amplify",
                "app_id": app_id,
                "branch": branch_name,
                "target": target,
                "dry_run": True,
                "config": amplify_config,
            },
        )

    def list_apps(self) -> List[Dict[str, Any]]:
        """List all Amplify apps."""
        if not HAS_BOTO3:
            return []
        
        try:
            response = self.amplify_client.list_apps()
            
            apps = []
            for app in response.get("apps", []):
                apps.append({
                    "app_id": app["appId"],
                    "name": app["name"],
                    "default_domain": app.get("defaultDomain"),
                    "repository": app.get("repository"),
                    "platform": app.get("platform"),
                    "create_time": str(app.get("createTime")),
                })
            
            return apps
            
        except Exception:
            return []

    def get_app_branches(self, app_id: str) -> List[Dict[str, Any]]:
        """List branches for an Amplify app."""
        if not HAS_BOTO3:
            return []
        
        try:
            response = self.amplify_client.list_branches(appId=app_id)
            
            branches = []
            for branch in response.get("branches", []):
                branches.append({
                    "branch_name": branch["branchName"],
                    "display_name": branch.get("displayName"),
                    "stage": branch.get("stage"),
                    "ttl": branch.get("ttl"),
                    "enable_auto_build": branch.get("enableAutoBuild"),
                })
            
            return branches
            
        except Exception:
            return []

    def get_job_status(
        self,
        app_id: str,
        branch_name: str,
        job_id: str,
    ) -> Dict[str, Any]:
        """Get status of a specific Amplify job."""
        if not HAS_BOTO3:
            return {"status": "error", "error": "boto3 not installed"}
        
        try:
            response = self.amplify_client.get_job(
                appId=app_id,
                branchName=branch_name,
                jobId=job_id,
            )
            
            job = response.get("job", {})
            summary = job.get("summary", {})
            
            return {
                "status": summary.get("status"),
                "start_time": str(summary.get("startTime")),
                "end_time": str(summary.get("endTime")) if summary.get("endTime") else None,
                "steps": [
                    {
                        "step_name": step.get("stepName"),
                        "status": step.get("status"),
                        "log_url": step.get("logUrl"),
                    }
                    for step in job.get("steps", [])
                ],
            }
            
        except Exception as e:
            return {"status": "error", "error": str(e)}

    def stop_job(
        self,
        app_id: str,
        branch_name: str,
        job_id: str,
    ) -> DeploymentResult:
        """Stop a running Amplify job."""
        if not HAS_BOTO3:
            return DeploymentResult(success=False, error="boto3 not installed")
        
        try:
            self.amplify_client.stop_job(
                appId=app_id,
                branchName=branch_name,
                jobId=job_id,
            )
            
            return self._create_deployment_result(
                success=True,
                message=f"Job {job_id} stopped",
            )
            
        except ClientError as e:
            return self._create_deployment_result(
                success=False,
                message="Failed to stop job",
                error=str(e),
            )
