# SEGA Local Domain
"""Local development deployment management."""

import sys

from .manager import LocalDeploymentManager
from .shared_infra import SharedInfrastructureManager
from .native_infra import NativeInfrastructureManager
from .nginx import NginxManager

# macOS-specific imports
if sys.platform == "darwin":
    from .macos_native_infra import MacOSNativeInfraManager
else:
    MacOSNativeInfraManager = None  # Not available on non-macOS

__all__ = [
    "LocalDeploymentManager",
    "SharedInfrastructureManager",
    "NativeInfrastructureManager",
    "NginxManager",
    "MacOSNativeInfraManager",
]
