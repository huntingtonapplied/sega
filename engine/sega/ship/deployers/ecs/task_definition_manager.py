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
File: src/sega/deployers/ecs/task_definition_manager.py
Purpose: Provides utility functions for ECS task definition management and configuration
Dependencies: boto3, botocore
Authors: FLEET Development Team
Copyright: 2022-2026 Huntington Applied
License: Apache-2.0
Last Modified: 2025-07-25
"""

import boto3
from typing import Dict, Any, Optional, List
from botocore.exceptions import ClientError


class ECSTaskDefinitionManager:
    """Manages ECS task definitions."""

    def __init__(self, ecs_client: boto3.client, region: str = "us-east-1"):
        self.ecs = ecs_client
        self.region = region

    def create_task_definition(
        self, config: Dict[str, Any], image_tag: str
    ) -> str:
        """Create ECS task definition from configuration."""
        container_name = config.get("container_name", config["service_name"])

        task_def = {
            "family": config["service_name"],
            "networkMode": "awsvpc",
            "requiresCompatibilities": ["FARGATE"],
            "cpu": str(config.get("cpu", 256)),
            "memory": str(config.get("memory", 512)),
            "containerDefinitions": [
                {
                    "name": container_name,
                    "image": f"{config['ecr_repository']}:{image_tag}",
                    "cpu": config.get("cpu", 256),
                    "memory": config.get("memory", 512),
                    "essential": True,
                    "portMappings": [
                        {"containerPort": config["port"], "protocol": "tcp"}
                    ],
                    "environment": self._format_environment_variables(config),
                    "logConfiguration": self._create_log_configuration(config),
                    "healthCheck": self._create_health_check(config),
                }
            ],
        }

        # Add task role if specified
        if config.get("task_role_arn"):
            task_def["taskRoleArn"] = config["task_role_arn"]

        # Add execution role
        task_def["executionRoleArn"] = config.get(
            "execution_role_arn",
            f"arn:aws:iam::{self._get_account_id()}:role/ecsTaskExecutionRole",
        )

        # Register task definition
        response = self.ecs.register_task_definition(**task_def)
        return response["taskDefinition"]["taskDefinitionArn"]

    def _format_environment_variables(
        self, config: Dict[str, Any]
    ) -> List[Dict[str, str]]:
        """Format environment variables for task definition."""
        env_vars = []
        for key, value in config.get("environment", {}).items():
            env_vars.append({"name": key, "value": str(value)})
        return env_vars

    def _create_log_configuration(
        self, config: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Create CloudWatch logs configuration."""
        return {
            "logDriver": "awslogs",
            "options": {
                "awslogs-group": f"/ecs/{config['service_name']}",
                "awslogs-region": self.region,
                "awslogs-stream-prefix": "ecs",
            },
        }

    def _create_health_check(self, config: Dict[str, Any]) -> Dict[str, Any]:
        """Create container health check configuration."""
        return {
            "command": [
                "CMD-SHELL",
                f"curl -f {config.get('health_check_protocol', 'http')}://localhost:{config['port']}{config['health_check_path']} || exit 1",
            ],
            "interval": 30,
            "timeout": 5,
            "retries": 3,
            "startPeriod": 60,
        }

    def get_latest_task_definition(self, family: str) -> Optional[str]:
        """Get the latest task definition ARN for a family."""
        try:
            response = self.ecs.list_task_definitions(
                familyPrefix=family, sort="DESC", maxResults=1
            )

            if response.get("taskDefinitionArns"):
                return response["taskDefinitionArns"][0]
            return None

        except ClientError:
            return None

    def deregister_old_definitions(self, family: str, keep_count: int = 5):
        """Deregister old task definitions, keeping the latest N."""
        try:
            response = self.ecs.list_task_definitions(
                familyPrefix=family, sort="DESC"
            )

            task_defs = response.get("taskDefinitionArns", [])

            # Keep the latest N definitions
            for task_def in task_defs[keep_count:]:
                self.ecs.deregister_task_definition(taskDefinition=task_def)

        except ClientError:
            pass

    def _get_account_id(self) -> str:
        """Get AWS account ID."""
        import boto3

        sts = boto3.client("sts")
        return sts.get_caller_identity()["Account"]
