# SEGA Ship Strategies
"""Deployment strategies for the ship domain.

This module provides deployment strategy abstractions including:
- Rolling deployments
- Blue-green deployments
- Canary deployments
- Mixed/composite strategies

Platform-specific implementations can be found in deployers/<platform>/
"""

# Re-export strategy classes from ECS implementation (most comprehensive)
from ..deployers.ecs.deployment_strategies import (
    DeploymentStrategy,
    RollingDeploymentStrategy,
    BlueGreenDeploymentStrategy,
    CanaryDeploymentStrategy,
    MixedDeploymentStrategy,
    get_deployment_strategy,
)

__all__ = [
    'DeploymentStrategy',
    'RollingDeploymentStrategy',
    'BlueGreenDeploymentStrategy',
    'CanaryDeploymentStrategy',
    'MixedDeploymentStrategy',
    'get_deployment_strategy',
]
