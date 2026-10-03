# SEGA Project Detection
"""Project detection and configuration."""

from .project_detector import ProjectDetector
from .cached_project_detector import CachedProjectDetector
from .enhanced_project_detector import EnhancedProjectDetector
from .entity_config import (
    EntityConfig,
    EntityConfigDiscovery,
    get_entity_discovery,
    discover_entities,
    get_project_deployment_config,
)

__all__ = [
    # Project detection
    'ProjectDetector',
    'CachedProjectDetector',
    'EnhancedProjectDetector',
    # Entity configuration
    'EntityConfig',
    'EntityConfigDiscovery',
    'get_entity_discovery',
    'discover_entities',
    'get_project_deployment_config',
]
