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
SEGA: Enterprise Deployment Framework
=====================================================
File: src/sega/deployers/ecs/cluster_manager.py
Purpose: Provides utility functions for ECS cluster management and orchestration
Dependencies: boto3, botocore
Authors: FLEET Development Team
Copyright: 2022-2026 Huntington Applied
License: Apache-2.0
Last Modified: 2025-07-25
"""

import boto3
from typing import Optional
from botocore.exceptions import ClientError


class ECSClusterManager:
    """Manages ECS clusters."""

    def __init__(self, ecs_client: boto3.client):
        self.ecs = ecs_client

    def ensure_cluster_exists(self, cluster_name: str) -> str:
        """Ensure ECS cluster exists, create if needed."""
        try:
            # Check if cluster exists
            response = self.ecs.describe_clusters(clusters=[cluster_name])

            if response["clusters"]:
                cluster = response["clusters"][0]
                if cluster["status"] == "ACTIVE":
                    return cluster["clusterArn"]

            # Create cluster if it doesn't exist
            return self._create_cluster(cluster_name)

        except ClientError as e:
            if e.response["Error"]["Code"] == "ClusterNotFoundException":
                return self._create_cluster(cluster_name)
            raise

    def _create_cluster(self, cluster_name: str) -> str:
        """Create new ECS cluster."""
        response = self.ecs.create_cluster(
            clusterName=cluster_name,
            settings=[{"name": "containerInsights", "value": "enabled"}],
            capacityProviders=["FARGATE", "FARGATE_SPOT"],
            defaultCapacityProviderStrategy=[
                {"capacityProvider": "FARGATE", "weight": 1, "bBase": 0}
            ],
        )

        return response["cluster"]["clusterArn"]

    def get_cluster_info(self, cluster_name: str) -> Optional[dict]:
        """Get cluster information."""
        try:
            response = self.ecs.describe_clusters(clusters=[cluster_name])

            if response["clusters"]:
                cluster = response["clusters"][0]
                return {
                    "arn": cluster["clusterArn"],
                    "status": cluster["status"],
                    "running_tasks": cluster.get("runningTasksCount", 0),
                    "active_services": cluster.get("activeServicesCount", 0),
                    "container_insights": self._get_container_insights_status(
                        cluster
                    ),
                }

        except ClientError:
            pass

        return None

    def _get_container_insights_status(self, cluster: dict) -> bool:
        """Check if Container Insights is enabled."""
        for setting in cluster.get("settings", []):
            if setting["name"] == "containerInsights":
                return setting["value"] == "enabled"
        return False

    def delete_cluster(self, cluster_name: str) -> bool:
        """Delete an ECS cluster."""
        try:
            # First, ensure no services are running
            response = self.ecs.list_services(cluster=cluster_name)
            if response.get("serviceArns"):
                return False  # Cannot delete cluster with active services

            # Delete the cluster
            self.ecs.delete_cluster(cluster=cluster_name)
            return True

        except ClientError:
            return False

    def update_cluster_settings(
        self, cluster_name: str, enable_container_insights: bool = True
    ) -> bool:
        """Update cluster settings."""
        try:
            self.ecs.put_cluster_settings(
                cluster=cluster_name,
                settings=[
                    {
                        "name": "containerInsights",
                        "value": "enabled"
                        if enable_container_insights
                        else "disabled",
                    }
                ],
            )
            return True

        except ClientError:
            return False
