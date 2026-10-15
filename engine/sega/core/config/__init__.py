# Copyright 2022-2026 Huntington Applied
# License: Apache-2.0
#
# SEGA Central Configuration Module
#
# AUTHORITATIVE REFERENCES:
# - Port Allocation Standards: /docs/standards/infrastructure/PORT_ALLOCATION_STANDARDS.md
# - URL & Addressing Registry: /docs/standards/infrastructure/URL_AND_ADDRESSING_REGISTRY.md
# - Domain Registry: /docs/architecture/infrastructure/dns/FLEET_DOMAIN_REGISTRY.md
# - EC2 Instance Registry: /docs/operations/infrastructure/EC2_INSTANCE_REGISTRY.md

"""
SEGA Central Configuration

Provides a typed, TOML-based configuration system for SEGA.

Quick Start:
    from sega.core.config import get_config

    config = get_config()

    # Get project info
    orion = config.get_project("orion")
    print(orion.api_port)  # 8000

    # Get deployment target
    instance = config.get_instance_for_project("orion")
    print(instance.ip)  # 203.0.113.10

Configuration File:
    The configuration is loaded from config/sega.toml. The search order is:
    1. SEGA_CONFIG_PATH environment variable
    2. ./config/sega.toml (relative to CWD)
    3. ~/fleet/sega/config/sega.toml (fallback)

Environment Overrides:
    Use SEGA_* prefix to override configuration values:
    - SEGA_TELEMETRY_API_PORT=9003
    - SEGA_META_VERSION=2.0.0

Port Calculations:
    All ports are computed from project ID using standardized formulas:
    - api_port = 8000 + project_id
    - frontend_port = 3000 + project_id
    - database_port = 5000 + project_id
    - redis_port = 6000 + project_id
    - metrics_port = 9000 + project_id
"""

from .loader import (
    ConfigurationError,
    get_config,
    get_config_path,
    get_deployment_target,
    get_project_api_url,
    load_config,
    reload_config,
)
from .project_config import ProjectConfigError, ProjectConfigManager
from .validators import ConfigValidator, ValidationResult
from .schema import (
    CLIPackagingConfig,
    CORSConfig,
    DeploymentTarget,
    DesktopPackagingConfig,
    DesktopSigningConfig,
    DistributionConfig,
    EngineType,
    ExclusionsConfig,
    ExtensionPackagingConfig,
    FrontendBuildConfig,
    FrontendOrchestrationConfig,
    FrontendParallelConfig,
    FrontendServeConfig,
    IDEPackagingConfig,
    InfrastructureConfig,
    InstanceConfig,
    JSProtectionConfig,
    LinuxSigningEnvConfig,
    LoggingConfig,
    LogRotationConfig,
    MacSigningEnvConfig,
    MetaConfig,
    MobilePackagingConfig,
    MobileSigningConfig,
    MonitoringConfig,
    NodeProtectionConfig,
    PackagingConfig,
    PathRoutingConfig,
    PortConfig,
    PortRoutingConfig,
    ProjectConfig,
    ProjectHealthConfig,
    ProtectionConfig,
    PythonProtectionConfig,
    RateLimitingConfig,
    ReverseProxyConfig,
    RoutingConfig,
    RustProtectionConfig,
    S3DistributionConfig,
    SecurityConfig,
    SegaConfig,
    SharedEnvironmentsConfig,
    SigningConfig,
    SSLConfig,
    StaticFilesConfig,
    SubdomainRoutingConfig,
    TelemetryConfig,
    UnifiedServerConfig,
    VSCEDistributionConfig,
    WindowsSigningEnvConfig,
)

__all__ = [
    # Main interface
    "get_config",
    "reload_config",
    "load_config",
    "get_config_path",
    # Utility functions
    "get_project_api_url",
    "get_deployment_target",
    # Project config management
    "ProjectConfigManager",
    "ConfigValidator",
    "ValidationResult",
    "ProjectConfigError",
    # Schema classes - Core
    "SegaConfig",
    "ProjectConfig",
    "InstanceConfig",
    "PortConfig",
    "TelemetryConfig",
    "MetaConfig",
    # Schema classes - Distribution
    "DistributionConfig",
    "ExclusionsConfig",
    "S3DistributionConfig",
    "VSCEDistributionConfig",
    # Schema classes - Protection
    "ProtectionConfig",
    "PythonProtectionConfig",
    "NodeProtectionConfig",
    "JSProtectionConfig",
    "RustProtectionConfig",
    # Schema classes - Packaging
    "PackagingConfig",
    "DesktopPackagingConfig",
    "DesktopSigningConfig",
    "MobilePackagingConfig",
    "MobileSigningConfig",
    "IDEPackagingConfig",
    "ExtensionPackagingConfig",
    "CLIPackagingConfig",
    # Schema classes - Signing
    "SigningConfig",
    "MacSigningEnvConfig",
    "WindowsSigningEnvConfig",
    "LinuxSigningEnvConfig",
    # Schema classes - Infrastructure
    "InfrastructureConfig",
    "SharedEnvironmentsConfig",
    "FrontendOrchestrationConfig",
    "FrontendBuildConfig",
    "FrontendServeConfig",
    "FrontendParallelConfig",
    "UnifiedServerConfig",
    "SSLConfig",
    "ReverseProxyConfig",
    "StaticFilesConfig",
    "RoutingConfig",
    "SubdomainRoutingConfig",
    "PathRoutingConfig",
    "PortRoutingConfig",
    "MonitoringConfig",
    "ProjectHealthConfig",
    "SecurityConfig",
    "RateLimitingConfig",
    "CORSConfig",
    "LoggingConfig",
    "LogRotationConfig",
    # Enums
    "EngineType",
    "DeploymentTarget",
    # Exceptions
    "ConfigurationError",
]
