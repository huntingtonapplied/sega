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
# SEGA MODULE - DEPLOYMENT ROUTER
# ===============================================================
# File: src/sega/deployers/deployment_router.py
# Purpose: Routes deployments to appropriate infrastructure based on project type
#
# Description: Central routing component that maps project types to deployment
# strategies and selects the appropriate deployer (K8s, Ansible, FPGA). Manages
# deployment delegation based on detected project characteristics and target.
#
# Dependencies:
# - External: typing
# - Internal: core.deployment_result, k8s_deployer, ansible_deployer, fpga_deployer
#
# Used by: deployment_service, enterprise_orchestrator, CLI deploy command
#

"""Routes deployments to appropriate infrastructure based on project type."""

from typing import List, Optional, Dict, Any
from ...core.deployment_result import DeploymentResult
from .k8s_deployer import K8sDeployer
from .ansible_deployer import AnsibleDeployer
from .fpga_deployer import FPGADeployer
from .multi_region_deployer import MultiRegionDeployer
from .ecs_deployer import ECSDeployer
from .swarm_deployer import SwarmDeployer
from .mobile_deployer import MobileDeployer
from .desktop_deployer import DesktopDeployer

# Platform deployers
from .vercel_deployer import VercelDeployer
from .firebase_deployer import FirebaseDeployer
from .supabase_deployer import SupabaseDeployer
from .render_deployer import RenderDeployer
from .amplify_deployer import AmplifyDeployer


class DeploymentRouter:
    """Routes deployments based on project type and target infrastructure."""

    def __init__(self):
        # Default configurations for deployers
        default_config = {"project_path": "."}
        
        self.deployers = {
            # Infrastructure deployers
            "helm_k8s": K8sDeployer(),
            "helm_gpu_k8s": K8sDeployer(gpu_enabled=True),
            "ansible_flash": AnsibleDeployer(mode="flash"),
            "ansible_systemd": AnsibleDeployer(mode="systemd"),
            "fpga_flash": FPGADeployer(),
            "ecs_single": ECSDeployer(),
            # Distributed swarm fleet (continuous train/sim on Docker Swarm)
            "swarm": SwarmDeployer(),
            "mobile_app": MobileDeployer(default_config),
            "desktop_app": DesktopDeployer(default_config),
            # Platform deployers
            "vercel": VercelDeployer(),
            "firebase": FirebaseDeployer(),
            "supabase": SupabaseDeployer(),
            "render": RenderDeployer(),
            "amplify": AmplifyDeployer(),
        }

        # Multi-region deployers
        self.multi_region_deployers = {}

    def deploy(
        self,
        project_type: str,
        target: str,
        strategy: str,
        dry_run: bool = False,
        force: bool = False,
        regions: Optional[List[str]] = None,
        multi_region: bool = False,
        **kwargs,
    ) -> DeploymentResult:
        """Execute deployment using appropriate deployer."""

        # If multi-region deployment is requested
        if multi_region and regions:
            return self._deploy_multi_region(
                project_type,
                target,
                strategy,
                regions,
                dry_run,
                force,
                **kwargs,
            )

        # Single region deployment
        return self._deploy_single_region(
            project_type, target, strategy, dry_run, force, **kwargs
        )

    def _deploy_single_region(
        self,
        project_type: str,
        target: str,
        strategy: str,
        dry_run: bool = False,
        force: bool = False,
        **kwargs,
    ) -> DeploymentResult:
        """Execute single region deployment."""

        # Check if a specific platform is requested
        platform = kwargs.get("platform")
        if platform and platform in self.deployers:
            deployer = self.deployers[platform]
            try:
                if hasattr(deployer, "deploy"):
                    return deployer.deploy(
                        target=target,
                        strategy=strategy,
                        dry_run=dry_run,
                        force=force,
                        **kwargs,
                    )
            except Exception as e:
                return DeploymentResult(success=False, error=str(e))

        # Map project types to deployment strategies
        deployment_map = {
            # Infrastructure targets
            "web_app": "helm_k8s",
            "ml_pipeline": "helm_gpu_k8s",
            "firmware_edge": "ansible_flash",
            "native_app": "ansible_systemd",
            "hdl_fpga": "fpga_flash",
            "containerized_app": "ecs_single",
            "mobile_app": "mobile_app",
            "desktop_app": "desktop_app",
            "hybrid_app": "mobile_app",  # Hybrid apps use mobile deployer for both platforms
            # Platform targets
            "static_web": "vercel",
            "nextjs_app": "vercel",
            "firebase_app": "firebase",
            "firebase_hosting": "firebase",
            "supabase_app": "supabase",
            "render_service": "render",
            "amplify_app": "amplify",
        }

        deployer_type = deployment_map.get(project_type, "helm_k8s")
        deployer = self.deployers.get(deployer_type)
        
        if not deployer:
            return DeploymentResult(
                success=False,
                error=f"No deployer found for type: {deployer_type}",
            )

        try:
            if hasattr(deployer, "deploy"):
                return deployer.deploy(
                    target=target,
                    strategy=strategy,
                    dry_run=dry_run,
                    force=force,
                    **kwargs,
                )
            else:
                return DeploymentResult(
                    success=False,
                    error=f"Deployer {deployer_type} does not support deployment",
                )
        except Exception as e:
            return DeploymentResult(success=False, error=str(e))

    def _deploy_multi_region(
        self,
        project_type: str,
        target: str,
        strategy: str,
        regions: List[str],
        dry_run: bool = False,
        force: bool = False,
        **kwargs,
    ) -> DeploymentResult:
        """Execute multi-region deployment."""

        # Determine deployment type for multi-region
        if project_type in ["web_app", "containerized_app"]:
            deployment_type = "ecs"
        elif project_type in ["ml_pipeline"]:
            deployment_type = "k8s"
        else:
            return DeploymentResult(
                success=False,
                error=f"Multi-region deployment not supported for project type: {project_type}",
            )

        # Create or get cached multi-region deployer
        deployer_key = f"{deployment_type}_{'-'.join(regions)}"
        if deployer_key not in self.multi_region_deployers:
            self.multi_region_deployers[deployer_key] = MultiRegionDeployer(
                regions=regions,
                deployment_type=deployment_type,
                primary_region=regions[0] if regions else "us-east-1",
            )

        deployer = self.multi_region_deployers[deployer_key]

        try:
            # Multi-region deployer returns MultiRegionDeploymentResult
            # We need to convert it to DeploymentResult for compatibility
            mr_result = deployer.deploy(
                project_path=kwargs.get("project_path", "."),
                target=target,
                strategy=strategy,
                **kwargs,
            )

            # Convert MultiRegionDeploymentResult to DeploymentResult
            return DeploymentResult(
                success=mr_result.success,
                error=mr_result.error,
                message=f"Multi-region deployment: {len(mr_result.successful_regions)}/{len(mr_result.regions)} regions successful",
                deployment_id=f"multi-region-{target}",
                metadata={
                    "deployment_type": "multi_region",
                    "regions": mr_result.regions,
                    "successful_regions": mr_result.successful_regions,
                    "failed_regions": mr_result.failed_regions,
                    "primary_region": mr_result.primary_region,
                    "total_duration": mr_result.total_duration,
                    "rollback_performed": mr_result.rollback_performed,
                },
            )

        except Exception as e:
            return DeploymentResult(
                success=False,
                error=f"Multi-region deployment failed: {str(e)}",
            )

    def get_supported_project_types(self) -> List[str]:
        """Get list of supported project types."""
        return [
            # Infrastructure types
            "web_app",
            "ml_pipeline",
            "firmware_edge",
            "native_app",
            "hdl_fpga",
            "containerized_app",
            "mobile_app",
            "desktop_app",
            "hybrid_app",
            # Platform types
            "static_web",
            "nextjs_app",
            "firebase_app",
            "firebase_hosting",
            "supabase_app",
            "render_service",
            "amplify_app",
        ]

    def get_supported_platforms(self) -> List[str]:
        """Get list of supported deployment platforms."""
        return [
            "helm_k8s",
            "ecs_single",
            "vercel",
            "firebase",
            "supabase",
            "render",
            "amplify",
            "ansible_flash",
            "ansible_systemd",
            "fpga_flash",
            "mobile_app",
            "desktop_app",
        ]

    def get_multi_region_capable_types(self) -> List[str]:
        """Get list of project types that support multi-region deployment."""
        return ["web_app", "containerized_app", "ml_pipeline"]

    def get_platform_deployer(self, platform: str) -> Optional[Any]:
        """Get a specific platform deployer by name."""
        return self.deployers.get(platform)

    def deploy_to_platform(
        self,
        platform: str,
        target: str,
        dry_run: bool = False,
        force: bool = False,
        entity: Optional[str] = None,
        **kwargs,
    ) -> DeploymentResult:
        """Deploy directly to a specific platform.
        
        This bypasses project type detection and deploys directly to the
        specified platform (vercel, firebase, supabase, render, amplify, etc.)
        
        Args:
            platform: Target platform (vercel, firebase, supabase, etc.)
            target: Environment (staging, production)
            dry_run: Preview without deploying
            force: Force deployment
            entity: Entity name for entity-specific credentials
            **kwargs: Additional deployer arguments
        """
        # Create entity-aware deployer if entity specified
        if entity:
            deployer = self._get_entity_deployer(platform, entity)
        else:
            deployer = self.deployers.get(platform)
        
        if not deployer:
            return DeploymentResult(
                success=False,
                error=f"Unknown platform: {platform}. Supported: {', '.join(self.get_supported_platforms())}",
            )
        
        try:
            return deployer.deploy(
                target=target,
                strategy="rolling",
                dry_run=dry_run,
                force=force,
                **kwargs,
            )
        except Exception as e:
            return DeploymentResult(success=False, error=str(e))
    
    def _get_entity_deployer(self, platform: str, entity: str):
        """Get a deployer configured for a specific entity's credentials."""
        if platform == "vercel":
            return VercelDeployer(entity=entity)
        elif platform == "firebase":
            return FirebaseDeployer(entity=entity)
        elif platform == "supabase":
            return SupabaseDeployer(entity=entity)
        elif platform == "render":
            return RenderDeployer(entity=entity)
        elif platform == "amplify":
            return AmplifyDeployer(entity=entity)
        else:
            # Fall back to generic deployer
            return self.deployers.get(platform)
