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
# SEGA MODULE - Supabase Deployer
# ===============================================================
# File: src/sega/ship/deployers/supabase_deployer.py
# Purpose: Deploy applications and infrastructure to Supabase
#
# Description: Handles deployment of database migrations, Edge Functions,
# storage buckets, and RLS policies to Supabase. Supports local development
# linking and production deployments.
#
# Dependencies:
# - External: subprocess, json, os
# - Internal: base_deployer, deployment_result
#
# Used by: deployment_router for supabase project types
#

"""Supabase platform deployer for SEGA."""

import json
import os
from typing import Dict, Any, Optional, List
from .base_deployer import BaseDeployer
from ...core.deployment_result import DeploymentResult


class SupabaseDeployer(BaseDeployer):
    """Deployer for Supabase platform (Database, Auth, Storage, Edge Functions)."""

    def __init__(self, config: Dict[str, Any] = None, entity: Optional[str] = None):
        super().__init__()
        self.config = config or {}
        self.entity = entity
        
        # Use credentials resolver for entity-aware token lookup
        if entity:
            from ...utils.credentials import get_credentials_resolver
            resolver = get_credentials_resolver()
            creds = resolver.get_credentials("supabase", entity)
            self.supabase_access_token = creds.token
            self.supabase_db_password = creds.extra.get("db_password") if creds.extra else None
        else:
            self.supabase_access_token = os.environ.get("SUPABASE_ACCESS_TOKEN")
            self.supabase_db_password = os.environ.get("SUPABASE_DB_PASSWORD")

    def deploy(
        self,
        target: str,
        strategy: str = "rolling",
        image_tag: str = "latest",
        force: bool = False,
        dry_run: bool = False,
        **kwargs,
    ) -> DeploymentResult:
        """Deploy to Supabase.
        
        Args:
            target: Environment (development, staging, production)
            strategy: Not used for Supabase
            image_tag: Not used for Supabase
            force: Force deployment (skip confirmations)
            dry_run: Preview what would be deployed
            
        Returns:
            DeploymentResult with deployment status
        """
        project_path = kwargs.get("project_path")
        if project_path:
            project_path = os.path.expanduser(project_path)
        
        project_config = self._get_project_config(project_path)
        
        # Get Supabase-specific config from sega.yaml
        supabase_config = self._get_supabase_config(project_config)
        project_ref = kwargs.get("project_ref") or supabase_config.get("project_ref")
        
        if dry_run:
            return self._dry_run_deployment(target, supabase_config, project_ref)
        
        # Ensure we're linked to a project
        if not self._is_linked():
            if project_ref:
                link_result = self._link_project(project_ref)
                if not link_result.success:
                    return link_result
            else:
                return self._create_deployment_result(
                    success=False,
                    message="Supabase deployment failed",
                    error="No Supabase project linked. Run 'supabase link' or provide project_ref",
                )
        
        try:
            results = []
            
            # Deploy database migrations
            if supabase_config.get("database", {}).get("migrations", True):
                db_result = self._deploy_migrations(force=force)
                results.append(("migrations", db_result))
                if not db_result.success:
                    return db_result
            
            # Deploy Edge Functions
            if supabase_config.get("functions", {}).get("enabled", False):
                func_result = self._deploy_functions()
                results.append(("functions", func_result))
            
            # Deploy storage configuration
            if supabase_config.get("storage", {}).get("enabled", False):
                # Storage buckets are typically created via migrations
                pass
            
            # Push database schema changes (if using db push instead of migrations)
            if supabase_config.get("database", {}).get("push", False):
                push_result = self._push_database(force=force)
                results.append(("db_push", push_result))
            
            # Summarize results
            all_success = all(r[1].success for r in results)
            deployed_components = [r[0] for r in results if r[1].success]
            
            return self._create_deployment_result(
                success=all_success,
                message=f"Deployed to Supabase: {', '.join(deployed_components)}",
                deployment_id=f"supabase-{project_ref or 'local'}-{target}",
                metadata={
                    "platform": "supabase",
                    "project_ref": project_ref,
                    "target": target,
                    "deployed_components": deployed_components,
                    "results": {r[0]: r[1].success for r in results},
                },
            )
            
        except Exception as e:
            return self._create_deployment_result(
                success=False,
                message="Supabase deployment failed",
                error=str(e),
            )

    def get_deployment_status(self, target: str) -> Dict[str, Any]:
        """Get deployment status from Supabase."""
        try:
            # Get project status
            cmd = ["supabase", "status"]
            result = self.resource_manager.run_subprocess(cmd, timeout=30)
            
            if result.returncode == 0:
                return {
                    "status": "available",
                    "raw_output": result.stdout,
                }
            
            return {"status": "error", "error": result.stderr}
            
        except Exception as e:
            return {"status": "error", "error": str(e)}

    def rollback(
        self, target: str, to_version: Optional[str] = None
    ) -> DeploymentResult:
        """Rollback database migrations.
        
        Args:
            target: Environment to rollback
            to_version: Migration version to rollback to
        """
        try:
            cmd = ["supabase", "db", "reset"]
            
            if to_version:
                # Rollback to specific version
                cmd = ["supabase", "migration", "repair", "--status", "reverted"]
            
            result = self.resource_manager.run_subprocess(cmd, timeout=300)
            
            if result.returncode == 0:
                return self._create_deployment_result(
                    success=True,
                    message=f"Rolled back database to {to_version or 'initial state'}",
                    metadata={"rollback_target": to_version},
                )
            
            return self._create_deployment_result(
                success=False,
                message="Rollback failed",
                error=result.stderr,
            )
            
        except Exception as e:
            return DeploymentResult(success=False, error=str(e))

    def _deploy_migrations(self, force: bool = False) -> DeploymentResult:
        """Deploy database migrations to remote."""
        cmd = ["supabase", "db", "push"]
        
        if force:
            cmd.append("--include-all")
        
        try:
            result = self.resource_manager.run_subprocess(cmd, timeout=300)
            
            if result.returncode == 0:
                return self._create_deployment_result(
                    success=True,
                    message="Database migrations deployed successfully",
                    metadata={"service": "migrations"},
                )
            
            return self._create_deployment_result(
                success=False,
                message="Migration deployment failed",
                error=result.stderr or result.stdout,
            )
            
        except Exception as e:
            return DeploymentResult(success=False, error=str(e))

    def _deploy_functions(
        self, functions: Optional[List[str]] = None
    ) -> DeploymentResult:
        """Deploy Edge Functions."""
        cmd = ["supabase", "functions", "deploy"]
        
        if functions:
            # Deploy specific functions
            cmd.extend(functions)
        else:
            # Deploy all functions
            cmd.append("--all")
        
        try:
            result = self.resource_manager.run_subprocess(cmd, timeout=300)
            
            if result.returncode == 0:
                return self._create_deployment_result(
                    success=True,
                    message="Edge Functions deployed successfully",
                    metadata={
                        "service": "functions",
                        "functions": functions or "all",
                    },
                )
            
            return self._create_deployment_result(
                success=False,
                message="Edge Functions deployment failed",
                error=result.stderr or result.stdout,
            )
            
        except Exception as e:
            return DeploymentResult(success=False, error=str(e))

    def _push_database(self, force: bool = False) -> DeploymentResult:
        """Push database schema changes directly."""
        cmd = ["supabase", "db", "push"]
        
        if force:
            cmd.append("--include-all")
        
        try:
            result = self.resource_manager.run_subprocess(cmd, timeout=300)
            
            if result.returncode == 0:
                return self._create_deployment_result(
                    success=True,
                    message="Database schema pushed successfully",
                    metadata={"service": "db_push"},
                )
            
            return self._create_deployment_result(
                success=False,
                message="Database push failed",
                error=result.stderr,
            )
            
        except Exception as e:
            return DeploymentResult(success=False, error=str(e))

    def _link_project(self, project_ref: str) -> DeploymentResult:
        """Link to a Supabase project."""
        cmd = ["supabase", "link", "--project-ref", project_ref]
        
        if self.supabase_db_password:
            cmd.extend(["--password", self.supabase_db_password])
        
        try:
            result = self.resource_manager.run_subprocess(cmd, timeout=60)
            
            if result.returncode == 0:
                return self._create_deployment_result(
                    success=True,
                    message=f"Linked to Supabase project: {project_ref}",
                )
            
            return self._create_deployment_result(
                success=False,
                message="Failed to link Supabase project",
                error=result.stderr,
            )
            
        except Exception as e:
            return DeploymentResult(success=False, error=str(e))

    def _is_linked(self) -> bool:
        """Check if we're linked to a Supabase project."""
        # Check for .supabase directory with project ref
        supabase_dir = self.project_detector.project_path / ".supabase"
        if supabase_dir.exists():
            # Check for project ref in config
            config_file = supabase_dir / "config.toml"
            if config_file.exists():
                return True
        return False

    def _get_supabase_config(self, project_config: Dict) -> Dict[str, Any]:
        """Extract Supabase-specific configuration."""
        build_config = project_config.get("build_config", {})
        
        # Check for platforms.supabase in sega.yaml
        if "platforms" in build_config and "supabase" in build_config["platforms"]:
            return build_config["platforms"]["supabase"]
        
        # Return default config
        return {
            "database": {"migrations": True, "push": False},
            "functions": {"enabled": False},
            "storage": {"enabled": False},
        }

    def _dry_run_deployment(
        self, target: str, supabase_config: Dict, project_ref: Optional[str]
    ) -> DeploymentResult:
        """Simulate deployment without executing."""
        components = []
        
        if supabase_config.get("database", {}).get("migrations", True):
            components.append("migrations")
        if supabase_config.get("functions", {}).get("enabled"):
            components.append("functions")
        if supabase_config.get("storage", {}).get("enabled"):
            components.append("storage")
        
        return self._create_deployment_result(
            success=True,
            message=f"[DRY RUN] Would deploy to Supabase ({target})",
            metadata={
                "platform": "supabase",
                "project_ref": project_ref,
                "target": target,
                "dry_run": True,
                "components": components,
                "config": supabase_config,
            },
        )

    def create_migration(self, name: str) -> DeploymentResult:
        """Create a new migration file."""
        cmd = ["supabase", "migration", "new", name]
        
        try:
            result = self.resource_manager.run_subprocess(cmd, timeout=30)
            
            if result.returncode == 0:
                return self._create_deployment_result(
                    success=True,
                    message=f"Created migration: {name}",
                    metadata={"migration_name": name},
                )
            
            return self._create_deployment_result(
                success=False,
                message="Migration creation failed",
                error=result.stderr,
            )
            
        except Exception as e:
            return DeploymentResult(success=False, error=str(e))

    def diff_database(self) -> DeploymentResult:
        """Generate migration from schema diff."""
        cmd = ["supabase", "db", "diff", "--use-migra"]
        
        try:
            result = self.resource_manager.run_subprocess(cmd, timeout=60)
            
            return self._create_deployment_result(
                success=result.returncode == 0,
                message="Database diff completed",
                metadata={
                    "diff": result.stdout,
                    "has_changes": bool(result.stdout.strip()),
                },
            )
            
        except Exception as e:
            return DeploymentResult(success=False, error=str(e))

    def start_local(self) -> DeploymentResult:
        """Start local Supabase development environment."""
        cmd = ["supabase", "start"]
        
        try:
            result = self.resource_manager.run_subprocess(cmd, timeout=300)
            
            if result.returncode == 0:
                # Parse local URLs from output
                urls = self._parse_local_urls(result.stdout)
                
                return self._create_deployment_result(
                    success=True,
                    message="Local Supabase started",
                    metadata={"local_urls": urls},
                )
            
            return self._create_deployment_result(
                success=False,
                message="Failed to start local Supabase",
                error=result.stderr,
            )
            
        except Exception as e:
            return DeploymentResult(success=False, error=str(e))

    def stop_local(self) -> DeploymentResult:
        """Stop local Supabase development environment."""
        cmd = ["supabase", "stop"]
        
        try:
            result = self.resource_manager.run_subprocess(cmd, timeout=60)
            
            return self._create_deployment_result(
                success=result.returncode == 0,
                message="Local Supabase stopped" if result.returncode == 0 else "Stop failed",
                error=result.stderr if result.returncode != 0 else None,
            )
            
        except Exception as e:
            return DeploymentResult(success=False, error=str(e))

    def _parse_local_urls(self, output: str) -> Dict[str, str]:
        """Parse local Supabase URLs from start output."""
        urls = {}
        
        for line in output.split("\n"):
            if "API URL:" in line:
                urls["api"] = line.split("API URL:")[-1].strip()
            elif "DB URL:" in line:
                urls["db"] = line.split("DB URL:")[-1].strip()
            elif "Studio URL:" in line:
                urls["studio"] = line.split("Studio URL:")[-1].strip()
            elif "anon key:" in line:
                urls["anon_key"] = line.split("anon key:")[-1].strip()
        
        return urls

    # =========================================================================
    # Project Creation & Management
    # =========================================================================

    def create_project(
        self,
        name: str,
        organization_id: str,
        region: str = "us-east-1",
        db_password: Optional[str] = None,
        plan: str = "free",
    ) -> DeploymentResult:
        """Create a new Supabase project.
        
        Requires SUPABASE_ACCESS_TOKEN with project creation permissions.
        
        Args:
            name: Project name
            organization_id: Supabase organization ID
            region: Database region (us-east-1, us-west-1, eu-west-1, etc.)
            db_password: Database password (generated if not provided)
            plan: Pricing plan (free, pro)
            
        Returns:
            DeploymentResult with project details
        """
        if not self.supabase_access_token:
            return self._create_deployment_result(
                success=False,
                message="Cannot create project",
                error="SUPABASE_ACCESS_TOKEN not set",
            )
        
        try:
            import requests
            import secrets
            
            # Generate password if not provided
            if not db_password:
                db_password = secrets.token_urlsafe(24)
            
            api_url = "https://api.supabase.com/v1/projects"
            
            headers = {
                "Authorization": f"Bearer {self.supabase_access_token}",
                "Content-Type": "application/json",
            }
            
            payload = {
                "name": name,
                "organization_id": organization_id,
                "region": region,
                "db_pass": db_password,
                "plan": plan,
            }
            
            response = requests.post(
                api_url,
                headers=headers,
                json=payload,
                timeout=120,  # Project creation can take time
            )
            
            if response.status_code in [200, 201]:
                project_data = response.json()
                project_ref = project_data.get("id")
                
                return self._create_deployment_result(
                    success=True,
                    message=f"Created Supabase project: {name}",
                    deployment_id=project_ref,
                    metadata={
                        "platform": "supabase",
                        "project_ref": project_ref,
                        "project_name": name,
                        "region": region,
                        "db_password": db_password,  # Store securely!
                        "api_url": f"https://{project_ref}.supabase.co",
                        "studio_url": f"https://supabase.com/dashboard/project/{project_ref}",
                    },
                )
            else:
                error_data = response.json()
                return self._create_deployment_result(
                    success=False,
                    message="Failed to create Supabase project",
                    error=error_data.get("message", response.text),
                )
                
        except Exception as e:
            return self._create_deployment_result(
                success=False,
                message="Failed to create Supabase project",
                error=str(e),
            )

    def init_project(
        self,
        project_path: Optional[str] = None,
    ) -> DeploymentResult:
        """Initialize Supabase in a project directory.
        
        Creates supabase/ directory with config.toml and initial migrations.
        
        Args:
            project_path: Directory to initialize (defaults to current)
            
        Returns:
            DeploymentResult with initialization status
        """
        cmd = ["supabase", "init"]
        
        try:
            result = self.resource_manager.run_subprocess(cmd, timeout=60)
            
            if result.returncode == 0:
                return self._create_deployment_result(
                    success=True,
                    message="Initialized Supabase project",
                    metadata={
                        "platform": "supabase",
                        "config_path": "supabase/config.toml",
                    },
                )
            else:
                return self._create_deployment_result(
                    success=False,
                    message="Failed to initialize Supabase",
                    error=result.stderr or result.stdout,
                )
                
        except Exception as e:
            return self._create_deployment_result(
                success=False,
                message="Failed to initialize Supabase",
                error=str(e),
            )

    def get_project_api_keys(self, project_ref: str) -> Dict[str, str]:
        """Get API keys for a Supabase project."""
        if not self.supabase_access_token:
            return {}
        
        try:
            import requests
            
            api_url = f"https://api.supabase.com/v1/projects/{project_ref}/api-keys"
            
            headers = {
                "Authorization": f"Bearer {self.supabase_access_token}",
            }
            
            response = requests.get(
                api_url,
                headers=headers,
                timeout=30,
            )
            
            if response.status_code == 200:
                keys = response.json()
                return {
                    key.get("name"): key.get("api_key")
                    for key in keys
                }
            
            return {}
            
        except Exception:
            return {}

    def list_projects(self) -> List[Dict[str, Any]]:
        """List all Supabase projects."""
        if not self.supabase_access_token:
            return []
        
        try:
            import requests
            
            api_url = "https://api.supabase.com/v1/projects"
            
            headers = {
                "Authorization": f"Bearer {self.supabase_access_token}",
            }
            
            response = requests.get(
                api_url,
                headers=headers,
                timeout=30,
            )
            
            if response.status_code == 200:
                projects = response.json()
                return [
                    {
                        "project_ref": p.get("id"),
                        "name": p.get("name"),
                        "region": p.get("region"),
                        "status": p.get("status"),
                        "api_url": f"https://{p.get('id')}.supabase.co",
                    }
                    for p in projects
                ]
            
            return []
            
        except Exception:
            return []

    def list_organizations(self) -> List[Dict[str, Any]]:
        """List Supabase organizations (needed for project creation)."""
        if not self.supabase_access_token:
            return []
        
        try:
            import requests
            
            api_url = "https://api.supabase.com/v1/organizations"
            
            headers = {
                "Authorization": f"Bearer {self.supabase_access_token}",
            }
            
            response = requests.get(
                api_url,
                headers=headers,
                timeout=30,
            )
            
            if response.status_code == 200:
                orgs = response.json()
                return [
                    {
                        "id": o.get("id"),
                        "name": o.get("name"),
                    }
                    for o in orgs
                ]
            
            return []
            
        except Exception:
            return []

    def delete_project(self, project_ref: str) -> DeploymentResult:
        """Delete a Supabase project.
        
        WARNING: This is irreversible!
        """
        if not self.supabase_access_token:
            return self._create_deployment_result(
                success=False,
                message="Cannot delete project",
                error="SUPABASE_ACCESS_TOKEN not set",
            )
        
        try:
            import requests
            
            api_url = f"https://api.supabase.com/v1/projects/{project_ref}"
            
            headers = {
                "Authorization": f"Bearer {self.supabase_access_token}",
            }
            
            response = requests.delete(
                api_url,
                headers=headers,
                timeout=60,
            )
            
            if response.status_code in [200, 204]:
                return self._create_deployment_result(
                    success=True,
                    message=f"Deleted Supabase project: {project_ref}",
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
