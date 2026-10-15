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

"""ECS deployer using focused modular components."""

import os
import boto3
from botocore.exceptions import ClientError
from typing import Dict, Any, Optional, List
from ...project.project_detector import ProjectDetector
from ...core.deployment_result import DeploymentResult

from .ecs import (
    ECSClusterManager,
    ECSTaskDefinitionManager,
    ECServiceManager,
    RollingDeploymentStrategy,
    BlueGreenDeploymentStrategy,
    CanaryDeploymentStrategy,
    MixedDeploymentStrategy,
)


class ECSDeployer:
    """ECS deployer using focused management components."""

    def __init__(self, region: str = "us-east-1"):
        self.region = region
        self.ecs = boto3.client("ecs", region_name=region)
        self.ec2 = boto3.client("ec2", region_name=region)
        self.ecr = boto3.client("ecr", region_name=region)

        # Initialize focused managers
        self.cluster_manager = ECSClusterManager(self.ecs)
        self.task_manager = ECSTaskDefinitionManager(self.ecs, region)
        self.service_manager = ECServiceManager(self.ecs, self.ec2)

        # Initialize deployment strategies
        self.strategies = {
            "rolling": RollingDeploymentStrategy(
                self.cluster_manager, self.task_manager, self.service_manager
            ),
            "blue-green": BlueGreenDeploymentStrategy(
                self.cluster_manager, self.task_manager, self.service_manager
            ),
            "canary": CanaryDeploymentStrategy(
                self.cluster_manager, self.task_manager, self.service_manager
            ),
            "mixed": MixedDeploymentStrategy(
                self.cluster_manager, self.task_manager, self.service_manager
            ),
        }

    def deploy(
        self,
        target: str,
        strategy: str = "rolling",
        image_tag: str = "latest",
        force: bool = False,
        dry_run: bool = False,
    ) -> DeploymentResult:
        """Deploy to ECS using specified strategy."""
        # Detect project type
        detector = ProjectDetector()
        project_type = detector.detect()

        # Get deployment configuration
        config = self._get_deployment_config(target, project_type)
        if not config:
            return DeploymentResult(
                success=False,
                error=f"No ECS configuration found for target: {target}",
            )

        # Dry run check
        if dry_run:
            return self._dry_run_deployment(config, image_tag)

        # Get strategy
        deployment_strategy = self.strategies.get(strategy)
        if not deployment_strategy:
            return DeploymentResult(
                success=False, error=f"Unknown deployment strategy: {strategy}"
            )

        # Execute deployment
        return deployment_strategy.deploy(config, image_tag, force)

    def _get_deployment_config(
        self, target: str, project_type: str
    ) -> Optional[Dict[str, Any]]:
        """Get deployment configuration for target."""
        # Load configuration from sega.yaml or environment
        # This is simplified - real implementation would load from config files

        base_config = {
            "cluster_name": self._get_cluster_name(target),
            "service_name": self._get_service_name(target),
            "ecr_repository": self._get_ecr_repository_uri(
                self._get_repository_name(target)
            ),
            "port": self._safe_int_from_env("SEGA_DEFAULT_PORT", 8000),
            "health_check_path": "/health",
            "health_check_protocol": "http",
            "cpu": 256,
            "memory": 512,
            "desired_count": 1,
            "environment": {
                "ENVIRONMENT": target.upper(),
                "PROJECT_TYPE": project_type,
            },
        }

        # Customize based on project type
        if project_type == "web_application":
            base_config.update(
                {
                    "port": self._safe_int_from_env("SEGA_WEB_APP_PORT", 3000),
                    "health_check_path": "/",
                    "cpu": 512,
                    "memory": 1024,
                }
            )
        elif project_type == "ml_pipeline":
            base_config.update(
                {
                    "cpu": 1024,
                    "memory": 2048,
                    "environment": {
                        **base_config["environment"],
                        "PYTORCH_VERSION": "1.9.0",
                    },
                }
            )

        # Validate configuration before returning
        validation_errors = self._validate_deployment_config(base_config)
        if validation_errors:
            print(
                f"Warning: Configuration validation errors: {', '.join(validation_errors)}"
            )
            # Still return config but log warnings

        return base_config

    def _dry_run_deployment(
        self, config: Dict[str, Any], image_tag: str
    ) -> DeploymentResult:
        """Simulate deployment without making changes."""
        result = DeploymentResult(
            success=True, message="Dry run completed successfully"
        )

        result.metadata = {
            "dry_run": True,
            "target_cluster": config["cluster_name"],
            "target_service": config["service_name"],
            "image_tag": image_tag,
            "configuration": config,
        }

        # Check if cluster exists
        cluster_info = self.cluster_manager.get_cluster_info(
            config["cluster_name"]
        )
        if cluster_info:
            result.metadata["cluster_exists"] = True
            result.metadata["cluster_status"] = cluster_info["status"]
        else:
            result.metadata["cluster_exists"] = False
            result.metadata["actions_needed"] = ["Create ECS cluster"]

        # Check if service exists
        service_info = self.service_manager.get_service_info(
            config["cluster_name"], config["service_name"]
        )

        if service_info:
            result.metadata["service_exists"] = True
            result.metadata["current_task_definition"] = service_info.get(
                "task_definition"
            )
            result.metadata["actions_planned"] = [
                "Update service with new task definition"
            ]
        else:
            result.metadata["service_exists"] = False
            result.metadata["actions_planned"] = ["Create new service"]

        return result

    def _get_ecr_repository_uri(self, repository_name: str) -> str:
        """Get ECR repository URI."""
        try:
            response = self.ecr.describe_repositories(
                repositoryNames=[repository_name]
            )
            return response["repositories"][0]["repositoryUri"]
        except ClientError as e:
            if e.response["Error"]["Code"] == "RepositoryNotFoundException":
                # If repository doesn't exist, return expected URI format
                account_id = self._get_account_id()
                return f"{account_id}.dkr.ecr.{self.region}.amazonaws.com/{repository_name}"
            else:
                # Handle authentication and permission errors
                if e.response["Error"]["Code"] == "AccessDeniedException":
                    raise ValueError(
                        f"Access denied to ECR repository {repository_name}. Check AWS permissions."
                    )
                elif e.response["Error"]["Code"] == "UnrecognizedClientException":
                    raise ValueError(
                        "AWS authentication failed. Check credentials."
                    )
                else:
                    raise ValueError(f"Failed to access ECR repository: {e}")
        except (KeyError, IndexError) as e:
            raise ValueError(f"Unexpected ECR response format: {e}")

    def _safe_int_from_env(self, env_var: str, default: int) -> int:
        """Safely convert environment variable to integer with validation."""
        try:
            env_value = os.getenv(env_var)
            if env_value is None:
                return default

            # Validate that it's a valid integer
            value = int(env_value)

            # Additional validation for port numbers
            if env_var.endswith("_PORT") and not (1 <= value <= 65535):
                raise ValueError(
                    f"Port number must be between 1 and 65535, got {value}"
                )

            return value
        except (ValueError, TypeError) as e:
            raise ValueError(
                f"Invalid value for {env_var}: {env_value}. Using default {default}. Error: {e}"
            )

    def _validate_deployment_config(self, config: Dict[str, Any]) -> List[str]:
        """Validate deployment configuration and return list of errors."""
        errors = []

        # Required fields
        required_fields = [
            "cluster_name",
            "service_name",
            "ecr_repository",
            "port",
            "cpu",
            "memory",
            "desired_count",
        ]
        for field in required_fields:
            if field not in config:
                errors.append(f"Missing required field: {field}")

        # Validate numeric fields
        if "port" in config:
            if (
                not isinstance(config["port"], int)
                or config["port"] < 1
                or config["port"] > 65535
            ):
                errors.append(f"Invalid port: {config['port']}")

        if "cpu" in config:
            valid_cpu_values = [256, 512, 1024, 2048, 4096]
            if config["cpu"] not in valid_cpu_values:
                errors.append(
                    f"Invalid CPU value: {config['cpu']}. Must be one of {valid_cpu_values}"
                )

        if "memory" in config:
            if not isinstance(config["memory"], int) or config["memory"] < 512:
                errors.append(
                    f"Invalid memory: {config['memory']}. Must be at least 512"
                )

        if "desired_count" in config:
            if (
                not isinstance(config["desired_count"], int)
                or config["desired_count"] < 0
            ):
                errors.append(
                    f"Invalid desired_count: {config['desired_count']}"
                )

        # Validate health check
        if "health_check_protocol" in config:
            if config["health_check_protocol"] not in ["http", "https", "tcp"]:
                errors.append(
                    f"Invalid health_check_protocol: {config['health_check_protocol']}"
                )

        return errors

    def _get_repository_name(self, target: str) -> str:
        """Get ECR repository name using configurable naming convention."""
        # Allow custom naming pattern via environment variable
        naming_pattern = os.getenv("SEGA_ECR_NAMING_PATTERN", "sega-{target}")

        # Support different naming conventions
        replacements = {
            "{target}": target,
            "{env}": target,  # Alias for target
            "{project}": os.getenv("SEGA_PROJECT_NAME", "sega"),
            "{org}": os.getenv("SEGA_ORG_NAME", "default"),
        }

        repository_name = naming_pattern
        for placeholder, value in replacements.items():
            repository_name = repository_name.replace(placeholder, value)

        # Ensure ECR naming compliance (lowercBase, alphanumeric, hyphens, underscores)
        repository_name = repository_name.lower()
        repository_name = "".join(
            c if c.isalnum() or c in "-_" else "-" for c in repository_name
        )

        return repository_name

    def _get_cluster_name(self, target: str) -> str:
        """Get ECS cluster name using configurable pattern."""
        naming_pattern = os.getenv(
            "SEGA_CLUSTER_NAMING_PATTERN", "sega-{target}"
        )
        return naming_pattern.replace("{target}", target)

    def _get_service_name(self, target: str) -> str:
        """Get ECS service name using configurable pattern."""
        naming_pattern = os.getenv(
            "SEGA_SERVICE_NAMING_PATTERN", "sega-{target}-service"
        )
        return naming_pattern.replace("{target}", target)

    def _get_account_id(self) -> str:
        """Get AWS account ID."""
        try:
            sts = boto3.client("sts")
            return sts.get_caller_identity()["Account"]
        except ClientError as e:
            error_code = e.response.get("Error", {}).get("Code", "Unknown")
            if error_code in ["ExpiredToken", "InvalidClientTokenId", "TokenRefreshRequired"]:
                raise ValueError("AWS authentication failed: Token expired or invalid")
            elif error_code == "AccessDenied":
                raise ValueError("AWS authentication failed: Access denied to STS service")
            else:
                raise ValueError(f"AWS authentication failed: {error_code} - {str(e)}")
        except Exception as e:
            raise ValueError(f"Failed to get AWS account ID: {str(e)}")

    def get_deployment_status(self, target: str) -> Dict[str, Any]:
        """Get deployment status for target."""
        cluster_name = self._get_cluster_name(target)
        service_name = self._get_service_name(target)

        # Get cluster info
        cluster_info = self.cluster_manager.get_cluster_info(cluster_name)

        # Get service info
        service_info = self.service_manager.get_service_info(
            cluster_name, service_name
        )

        return {
            "cluster": cluster_info,
            "service": service_info,
            "overall_status": "healthy"
            if (
                cluster_info
                and cluster_info.get("status") == "ACTIVE"
                and service_info
                and service_info.get("status") == "ACTIVE"
            )
            else "unhealthy",
        }

    def rollback(
        self, target: str, to_version: Optional[str] = None
    ) -> DeploymentResult:
        """Rollback deployment to previous version."""
        service_name = self._get_service_name(target)

        # Get the latest task definition ARN first
        latest_arn = self.task_manager.get_latest_task_definition(service_name)
        if not latest_arn:
            return DeploymentResult(
                success=False,
                error="No task definition found for rollback",
            )

        # Parse the task definition ARN properly
        # ARN format: arn:aws:ecs:region:account:task-definition/name:version
        if ":" not in latest_arn or "task-definition/" not in latest_arn:
            return DeploymentResult(
                success=False,
                error=f"Invalid task definition ARN format: {latest_arn}",
            )

        # Split ARN to extract base and version
        arn_parts = latest_arn.rsplit(":", 1)
        if len(arn_parts) != 2:
            return DeploymentResult(
                success=False,
                error=f"Cannot parse task definition ARN: {latest_arn}",
            )

        base_arn, current_version_str = arn_parts
        
        # Validate base ARN format
        if not base_arn.startswith("arn:aws:ecs:") or "task-definition/" not in base_arn:
            return DeploymentResult(
                success=False,
                error=f"Invalid ARN base format: {base_arn}",
            )

        if to_version:
            # Rollback to specific version - validate version number
            try:
                target_version = int(to_version)
                if target_version < 1:
                    return DeploymentResult(
                        success=False,
                        error=f"Invalid version number: {to_version} (must be >= 1)",
                    )
                task_def_arn = f"{base_arn}:{target_version}"
            except ValueError:
                return DeploymentResult(
                    success=False,
                    error=f"Version must be a number, got: {to_version}",
                )
        else:
            # Rollback to previous version
            try:
                current_version = int(current_version_str)
                if current_version <= 1:
                    return DeploymentResult(
                        success=False,
                        error="Cannot rollback from version 1 (no previous version exists)",
                    )
                previous_version = current_version - 1
                task_def_arn = f"{base_arn}:{previous_version}"
            except ValueError:
                return DeploymentResult(
                    success=False,
                    error=f"Invalid version number in ARN: {current_version_str}",
                )

        # Update service with previous task definition
        config = self._get_deployment_config(target, "unknown")
        if not config:
            return DeploymentResult(
                success=False,
                error=f"No configuration found for target: {target}",
            )

        try:
            service_arn = self.service_manager.create_or_update_service(
                config, task_def_arn, force=True
            )

            return DeploymentResult(
                success=True,
                message=f"Rollback initiated for {service_name}",
                metadata={
                    "service_arn": service_arn,
                    "task_definition": task_def_arn,
                },
            )
        except Exception as e:
            return DeploymentResult(
                success=False, error=f"Rollback failed: {str(e)}"
            )
