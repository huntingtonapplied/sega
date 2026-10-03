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

"""ECS deployment strategies."""

import time
from abc import ABC, abstractmethod
from typing import Dict, Any, Optional
from ....core.deployment_result import DeploymentResult


class DeploymentStrategy(ABC):
    """Base class for deployment strategies."""

    def __init__(self, cluster_manager, task_manager, service_manager):
        self.cluster_manager = cluster_manager
        self.task_manager = task_manager
        self.service_manager = service_manager

    @abstractmethod
    def deploy(
        self, config: Dict[str, Any], image_tag: str, force: bool
    ) -> DeploymentResult:
        """Execute deployment strategy."""
        pass

    def _create_base_result(
        self, success: bool, message: str
    ) -> DeploymentResult:
        """Create bBase deployment result."""
        return DeploymentResult(
            success=success,
            message=message,
            deployment_id=f"ecs-{int(time.time())}",
            start_time=time.time(),
        )


class RollingDeploymentStrategy(DeploymentStrategy):
    """Rolling deployment strategy."""

    def deploy(
        self, config: Dict[str, Any], image_tag: str, force: bool
    ) -> DeploymentResult:
        """Execute rolling deployment."""
        result = self._create_base_result(False, "Rolling deployment started")

        try:
            # Ensure cluster exists
            cluster_arn = self.cluster_manager.ensure_cluster_exists(
                config["cluster_name"]
            )
            result.metadata["cluster_arn"] = cluster_arn

            # Create new task definition
            task_def_arn = self.task_manager.create_task_definition(
                config, image_tag
            )
            result.metadata["task_definition"] = task_def_arn

            # Update service
            service_arn = self.service_manager.create_or_update_service(
                config, task_def_arn, force
            )
            result.metadata["service_arn"] = service_arn

            # Wait for deployment
            deployment_success = self.service_manager.wait_for_deployment(
                config["cluster_name"],
                config["service_name"],
                timeout=config.get("deployment_timeout", 600),
            )

            if deployment_success:
                result.success = True
                result.message = f"Rolling deployment completed successfully for {config['service_name']}"

                # Get deployment info
                service_info = self.service_manager.get_service_info(
                    config["cluster_name"], config["service_name"]
                )
                result.metadata.update(service_info)
            else:
                result.message = "Rolling deployment timed out"

        except Exception as e:
            result.error = str(e)
            result.message = f"Rolling deployment failed: {str(e)}"

        result.end_time = time.time()
        result.duration = result.end_time - result.start_time

        return result


class BlueGreenDeploymentStrategy(DeploymentStrategy):
    """Blue-green deployment strategy."""

    def deploy(
        self, config: Dict[str, Any], image_tag: str, force: bool
    ) -> DeploymentResult:
        """Execute blue-green deployment."""
        result = self._create_base_result(
            False, "Blue-green deployment started"
        )

        try:
            # Ensure cluster exists
            cluster_arn = self.cluster_manager.ensure_cluster_exists(
                config["cluster_name"]
            )
            result.metadata["cluster_arn"] = cluster_arn

            # Create new task definition for green service
            task_def_arn = self.task_manager.create_task_definition(
                config, image_tag
            )
            result.metadata["task_definition"] = task_def_arn

            # Create green service name
            green_service_name = f"{config['service_name']}-green"
            green_config = config.copy()
            green_config["service_name"] = green_service_name

            # Deploy green service
            green_service_arn = self.service_manager.create_or_update_service(
                green_config, task_def_arn, force
            )
            result.metadata["green_service_arn"] = green_service_arn

            # Wait for green deployment
            deployment_success = self.service_manager.wait_for_deployment(
                config["cluster_name"],
                green_service_name,
                timeout=config.get("deployment_timeout", 600),
            )

            if deployment_success:
                # Switch load balancer target group to green service
                if "load_balancer" in config:
                    try:
                        import boto3
                        elbv2 = boto3.client('elbv2')
                        
                        # Get target group ARN
                        target_group_arn = config["load_balancer"].get("target_group_arn")
                        
                        if target_group_arn:
                            # Deregister old targets
                            response = elbv2.describe_target_health(
                                TargetGroupArn=target_group_arn
                            )
                            old_targets = [
                                {'Id': target['Target']['Id']} 
                                for target in response['TargetHealthDescriptions']
                            ]
                            
                            if old_targets:
                                elbv2.deregister_targets(
                                    TargetGroupArn=target_group_arn,
                                    Targets=old_targets
                                )
                            
                            # Register green service tasks as new targets
                            # Note: This assumes tasks are already registered via service configuration
                            self.logger.info("Switched load balancer to green service")
                    except Exception as e:
                        self.logger.warning(f"Failed to switch load balancer: {e}")

                # Update the main service
                main_service_arn = (
                    self.service_manager.create_or_update_service(
                        config, task_def_arn, force
                    )
                )
                result.metadata["service_arn"] = main_service_arn

                # Stop green service
                self.service_manager.stop_service(
                    config["cluster_name"], green_service_name
                )

                result.success = True
                result.message = f"Blue-green deployment completed successfully for {config['service_name']}"
            else:
                # Clean up green service on failure
                self.service_manager.delete_service(
                    config["cluster_name"], green_service_name
                )
                result.message = "Blue-green deployment failed"

        except Exception as e:
            result.error = str(e)
            result.message = f"Blue-green deployment failed: {str(e)}"

        result.end_time = time.time()
        result.duration = result.end_time - result.start_time

        return result


class CanaryDeploymentStrategy(DeploymentStrategy):
    """Canary deployment strategy."""

    def deploy(
        self, config: Dict[str, Any], image_tag: str, force: bool
    ) -> DeploymentResult:
        """Execute canary deployment."""
        result = self._create_base_result(False, "Canary deployment started")

        try:
            # Ensure cluster exists
            cluster_arn = self.cluster_manager.ensure_cluster_exists(
                config["cluster_name"]
            )
            result.metadata["cluster_arn"] = cluster_arn

            # Create new task definition
            task_def_arn = self.task_manager.create_task_definition(
                config, image_tag
            )
            result.metadata["task_definition"] = task_def_arn

            # Create canary service with reduced capacity
            canary_service_name = f"{config['service_name']}-canary"
            canary_config = config.copy()
            canary_config["service_name"] = canary_service_name
            canary_config["desired_count"] = 1  # Single canary instance

            # Deploy canary service
            canary_service_arn = self.service_manager.create_or_update_service(
                canary_config, task_def_arn, force
            )
            result.metadata["canary_service_arn"] = canary_service_arn

            # Wait for canary deployment
            deployment_success = self.service_manager.wait_for_deployment(
                config["cluster_name"],
                canary_service_name,
                timeout=config.get("canary_duration", 300),
            )

            if deployment_success:
                # Monitor canary for issues (simplified - real implementation would check metrics)
                canary_healthy = self._monitor_canary(
                    config["cluster_name"],
                    canary_service_name,
                    duration=config.get("canary_monitoring_duration", 300),
                )

                if canary_healthy:
                    # Deploy to main service
                    main_service_arn = (
                        self.service_manager.create_or_update_service(
                            config, task_def_arn, force
                        )
                    )
                    result.metadata["service_arn"] = main_service_arn

                    # Wait for main deployment
                    main_success = self.service_manager.wait_for_deployment(
                        config["cluster_name"],
                        config["service_name"],
                        timeout=config.get("deployment_timeout", 600),
                    )

                    if main_success:
                        result.success = True
                        result.message = f"Canary deployment completed successfully for {config['service_name']}"
                    else:
                        result.message = "Main service deployment failed after successful canary"
                else:
                    result.message = "Canary deployment failed health checks"

                # Clean up canary service
                self.service_manager.delete_service(
                    config["cluster_name"], canary_service_name
                )
            else:
                result.message = "Canary deployment failed to start"

        except Exception as e:
            result.error = str(e)
            result.message = f"Canary deployment failed: {str(e)}"

        result.end_time = time.time()
        result.duration = result.end_time - result.start_time

        return result

    def _monitor_canary(
        self, cluster_name: str, service_name: str, duration: int
    ) -> bool:
        """Monitor canary service health."""
        # Simplified monitoring - real implementation would check CloudWatch metrics
        start_time = time.time()

        while time.time() - start_time < duration:
            service_info = self.service_manager.get_service_info(
                cluster_name, service_name
            )

            if service_info.get("running_count") != service_info.get(
                "desired_count"
            ):
                return False  # Service unhealthy

            time.sleep(30)

        return True  # Canary period passed successfully


class MixedDeploymentStrategy(DeploymentStrategy):
    """Mixed deployment strategy that combines multiple deployment approaches."""

    def __init__(
        self,
        cluster_manager,
        task_manager,
        service_manager,
        strategy_config: Dict[str, Any] = None,
    ):
        super().__init__(cluster_manager, task_manager, service_manager)
        self.strategy_config = strategy_config or {}

        # Initialize individual strategies
        self.rolling_strategy = RollingDeploymentStrategy(
            cluster_manager, task_manager, service_manager
        )
        self.blue_green_strategy = BlueGreenDeploymentStrategy(
            cluster_manager, task_manager, service_manager
        )
        self.canary_strategy = CanaryDeploymentStrategy(
            cluster_manager, task_manager, service_manager
        )

    def deploy(
        self, config: Dict[str, Any], image_tag: str, force: bool
    ) -> DeploymentResult:
        """Execute mixed deployment strategy with multiple phases."""
        result = self._create_base_result(False, "Mixed deployment started")

        try:
            # Parse mixed strategy configuration
            phases = self.strategy_config.get("phases", [])
            if not phases:
                # Default mixed strategy: canary -> blue_green
                phases = [
                    {"type": "canary", "percentage": 10, "duration": 300},
                    {"type": "blue_green", "switch_traffic": True},
                ]

            result.metadata = {
                "phases": phases,
                "current_phBase": 0,
                "total_phBases": len(phases),
                "phase_results": [],
            }

            # Execute phases sequentially
            for phase_idx, phase in enumerate(phases):
                result.metadata["current_phBase"] = phase_idx + 1
                result.message = f"Executing phase {phase_idx + 1}/{len(phases)}: {phase['type']}"

                phase_result = self._execute_phBase(
                    phase, config, image_tag, force
                )
                result.metadata["phase_results"].append(
                    {
                        "phase": phase_idx + 1,
                        "type": phase["type"],
                        "success": phase_result.success,
                        "message": phase_result.message,
                        "duration": getattr(phase_result, "duration", 0),
                    }
                )

                if not phase_result.success:
                    result.success = False
                    result.message = f"Mixed deployment failed at phase {phase_idx + 1}: {phase_result.message}"

                    # Rollback if configured
                    if self.strategy_config.get("rollback_on_failure", True):
                        self._rollback_phBases(phases[:phase_idx], config)

                    return result

                # Add phase-specific metadata
                if hasattr(phase_result, "metadata") and phase_result.metadata:
                    result.metadata[
                        f"phase_{phase_idx + 1}_metadata"
                    ] = phase_result.metadata

            # All phases completed successfully
            result.success = True
            result.message = f"Mixed deployment completed successfully through {len(phases)} phases"

        except Exception as e:
            result.success = False
            result.message = (
                f"Mixed deployment failed with exception: {str(e)}"
            )

        result.end_time = time.time()
        result.duration = result.end_time - result.start_time

        return result

    def _execute_phBase(
        self,
        phase: Dict[str, Any],
        config: Dict[str, Any],
        image_tag: str,
        force: bool,
    ) -> DeploymentResult:
        """Execute a single phase of the mixed deployment."""
        phase_type = phase["type"]
        phase_config = config.copy()

        # Modify config based on phase parameters
        if phase_type == "canary":
            # Configure canary-specific settings
            phase_config["canary_percentage"] = phase.get("percentage", 10)
            phase_config["canary_monitoring_duration"] = phase.get(
                "duration", 300
            )
            return self.canary_strategy.deploy(phase_config, image_tag, force)

        elif phase_type == "blue_green":
            # Configure blue-green specific settings
            phase_config["switch_traffic"] = phase.get("switch_traffic", True)
            phase_config["keep_old_version"] = phase.get(
                "keep_old_version", False
            )
            return self.blue_green_strategy.deploy(
                phase_config, image_tag, force
            )

        elif phase_type == "rolling":
            # Configure rolling update settings
            phase_config["max_unavailable"] = phase.get(
                "max_unavailable", "25%"
            )
            phase_config["max_surge"] = phase.get("max_surge", "25%")
            return self.rolling_strategy.deploy(phase_config, image_tag, force)

        else:
            return DeploymentResult(
                success=False, message=f"Unknown phase type: {phase_type}"
            )

    def _rollback_phBases(self, completed_phBases: list, config: Dict[str, Any]):
        """Rollback completed phases in reverse order."""
        try:
            for phase in reversed(completed_phBases):
                phase_type = phase["type"]

                if phase_type == "blue_green":
                    # Switch traffic back to original version
                    self._rollback_blue_green(config)
                elif phase_type == "canary":
                    # Remove canary deployment
                    self._rollback_canary(config)
                elif phase_type == "rolling":
                    # Rollback to previous task definition
                    self._rollback_rolling(config)

        except Exception:
            # Log rollback failure but don't raise exception
            pass

    def _rollback_blue_green(self, config: Dict[str, Any]):
        """Rollback blue-green deployment."""
        # Switch traffic back to blue environment
        blue_service_name = f"{config['service_name']}-blue"
        self.service_manager.update_service_traffic(
            config["cluster_name"],
            config["service_name"],
            blue_service_name,
            100,
        )

    def _rollback_canary(self, config: Dict[str, Any]):
        """Rollback canary deployment."""
        # Delete canary service
        canary_service_name = f"{config['service_name']}-canary"
        self.service_manager.delete_service(
            config["cluster_name"], canary_service_name
        )

    def _rollback_rolling(self, config: Dict[str, Any]):
        """Rollback rolling deployment."""
        # Update service to use previous task definition
        previous_task_def = self._get_previous_task_definition(
            config["service_name"]
        )
        if previous_task_def:
            self.service_manager.update_service_task_definition(
                config["cluster_name"],
                config["service_name"],
                previous_task_def,
            )

    def _get_previous_task_definition(
        self, service_name: str
    ) -> Optional[str]:
        """Get the previous task definition for rollback."""
        # Implementation would query ECS for task definition history
        # Simplified for now
        return f"{service_name}-task:1"


def get_deployment_strategy(
    strategy_name: str,
    cluster_manager,
    task_manager,
    service_manager,
    **kwargs,
) -> DeploymentStrategy:
    """Factory function to get deployment strategy instance."""

    strategies = {
        "rolling": RollingDeploymentStrategy,
        "blue_green": BlueGreenDeploymentStrategy,
        "canary": CanaryDeploymentStrategy,
        "mixed": MixedDeploymentStrategy,
    }

    if strategy_name not in strategies:
        raise ValueError(f"Unknown deployment strategy: {strategy_name}")

    strategy_class = strategies[strategy_name]

    if strategy_name == "mixed":
        # Mixed strategy requires additional configuration
        strategy_config = kwargs.get("strategy_config", {})
        return strategy_class(
            cluster_manager, task_manager, service_manager, strategy_config
        )
    else:
        return strategy_class(cluster_manager, task_manager, service_manager)
