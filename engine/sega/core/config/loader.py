# Copyright 2022-2026 Huntington Applied
# License: Apache-2.0
#
# SEGA Configuration Loader
# TOML-based configuration loading with environment variable support
#
# AUTHORITATIVE REFERENCES:
# - Port Allocation Standards: /docs/standards/infrastructure/PORT_ALLOCATION_STANDARDS.md
# - EC2 Instance Registry: /docs/operations/infrastructure/EC2_INSTANCE_REGISTRY.md

"""
SEGA Configuration Loader

Loads configuration from config/sega.toml with support for:
- Environment variable expansion (${VAR} syntax)
- SEGA_* prefix overrides
- Singleton caching for performance
- Python 3.11+ tomllib with fallback to toml package
"""

import logging
import os
import re
from pathlib import Path
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)

from .schema import (
    BuildConfig,
    CLIBuildEntry,
    CLIPackagingConfig,
    CORSConfig,
    CredentialsConfig,
    DeploymentTarget,
    DesktopPackagingConfig,
    DesktopSigningConfig,
    DistributionConfig,
    DomainConfig,
    EngineType,
    ExclusionsConfig,
    FleetConfig,
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
    NetworkFleetConfig,
    NodeProtectionConfig,
    PackagingConfig,
    PathRoutingConfig,
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
    SecretsMappingConfig,
    SecurityConfig,
    SegaConfig,
    SharedEnvironmentsConfig,
    ShipProductionConfig,
    SigningConfig,
    SSLConfig,
    StaticFilesConfig,
    SubdomainRoutingConfig,
    TelemetryConfig,
    UnifiedServerConfig,
    VSCEDistributionConfig,
    WindowsSigningEnvConfig,
)

# Try Python 3.11+ tomllib first, fall back to toml package
try:
    import tomllib

    _TOML_READER = "tomllib"
except ImportError:
    try:
        import toml as tomllib  # type: ignore

        _TOML_READER = "toml"
    except ImportError:
        tomllib = None  # type: ignore
        _TOML_READER = None


# Singleton instance cache
_config_instance: Optional[SegaConfig] = None
_config_path: Optional[Path] = None


class ConfigurationError(Exception):
    """Raised when configuration loading fails"""

    pass


def _find_config_file() -> Path:
    """
    Find the sega.toml configuration file.

    Search order:
    1. SEGA_CONFIG_PATH environment variable
    2. ./config/sega.toml (relative to CWD)
    3. src/sega/../../config/sega.toml (relative to this module)
    4. ~/fleet/sega/config/sega.toml (absolute fallback)

    Returns:
        Path to the configuration file

    Raises:
        ConfigurationError: If no configuration file is found
    """
    # Check environment variable first
    env_path = os.environ.get("SEGA_CONFIG_PATH")
    if env_path:
        path = Path(env_path).expanduser()
        if path.exists():
            return path

    # Check relative to CWD
    cwd_path = Path.cwd() / "config" / "sega.toml"
    if cwd_path.exists():
        return cwd_path

    # Check relative to this module
    module_path = Path(__file__).parent.parent.parent.parent.parent / "config" / "sega.toml"
    if module_path.exists():
        return module_path

    # Absolute fallback
    fallback_path = Path.home() / "fleet" / "sega" / "config" / "sega.toml"
    if fallback_path.exists():
        return fallback_path

    raise ConfigurationError("Could not find sega.toml. Set SEGA_CONFIG_PATH or create config/sega.toml")


def _expand_env_vars(value: Any) -> Any:
    """
    Recursively expand environment variables in configuration values.

    Supports ${VAR} and ${VAR:-default} syntax.

    Args:
        value: Configuration value (string, dict, list, or other)

    Returns:
        Value with environment variables expanded
    """
    if isinstance(value, str):
        # Match ${VAR} or ${VAR:-default}
        pattern = r"\$\{([^}:]+)(?::-([^}]*))?\}"

        def replacer(match):
            var_name = match.group(1)
            default = match.group(2) or ""
            return os.environ.get(var_name, default)

        return re.sub(pattern, replacer, value)

    elif isinstance(value, dict):
        return {k: _expand_env_vars(v) for k, v in value.items()}

    elif isinstance(value, list):
        return [_expand_env_vars(v) for v in value]

    return value


def _apply_env_overrides(data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Apply SEGA_* environment variable overrides to configuration.

    Override format: SEGA_<SECTION>_<KEY>=value
    Examples:
        SEGA_TELEMETRY_API_PORT=9003
        SEGA_META_VERSION=2.0.0

    Args:
        data: Parsed TOML configuration

    Returns:
        Configuration with environment overrides applied
    """
    prefix = "SEGA_"

    for key, value in os.environ.items():
        if not key.startswith(prefix):
            continue

        # Parse the key: SEGA_SECTION_KEY -> section.key
        parts = key[len(prefix) :].lower().split("_")
        if len(parts) < 2:
            continue

        section = parts[0]
        config_key = "_".join(parts[1:])

        # Apply override if section exists
        if section in data:
            # Try to convert to appropriate type
            try:
                # Try int first
                typed_value: Any = int(value)
            except ValueError:
                try:
                    # Try float
                    typed_value = float(value)
                except ValueError:
                    # Try bool
                    if value.lower() in ("true", "yes", "1"):
                        typed_value = True
                    elif value.lower() in ("false", "no", "0"):
                        typed_value = False
                    else:
                        typed_value = value

            if isinstance(data[section], dict):
                data[section][config_key] = typed_value

    return data


def _parse_engine_type(value: str) -> EngineType:
    """Parse engine type string to enum"""
    mapping = {
        "simulation": EngineType.SIMULATION,
        "workflow": EngineType.WORKFLOW,
        "utility": EngineType.UTILITY,
        "function_library": EngineType.FUNCTION_LIBRARY,
        "none": EngineType.NONE,
    }
    return mapping.get(value.lower(), EngineType.NONE)


def _parse_deployment_target(value: str) -> str:
    """Normalize a deployment-target string.

    Returns a reserved keyword ('local'/'not_served') or an instance name
    (resolved against config.instances at lookup time). No instance names are
    hardcoded here, so the deployment topology is fully config-driven.
    """
    if not value:
        return DeploymentTarget.LOCAL
    normalized = value.strip().lower()
    if normalized == "not-served":
        return DeploymentTarget.NOT_SERVED
    return normalized


def _build_config(data: Dict[str, Any], config_path: Path) -> SegaConfig:
    """
    Build SegaConfig from parsed TOML data.

    Args:
        data: Parsed and processed TOML data
        config_path: Path to the configuration file

    Returns:
        Fully constructed SegaConfig instance
    """
    # Parse metadata
    meta_data = data.get("meta", {})
    meta = MetaConfig(
        version=meta_data.get("version", "1.0.0"),
        config_path=str(config_path),
    )

    # Parse instances
    instances: Dict[str, InstanceConfig] = {}
    for name, inst_data in data.get("instances", {}).items():
        instances[name] = InstanceConfig(
            name=name,
            ip=inst_data.get("ip", ""),
            projects=inst_data.get("projects", []),
            ssh_user=inst_data.get("ssh_user", "ubuntu"),
            ssh_key_path=inst_data.get("ssh_key_path", "~/.ssh/id_rsa"),
        )

    # Parse projects
    projects: Dict[str, ProjectConfig] = {}
    for name, proj_data in data.get("projects", {}).items():
        projects[name] = ProjectConfig(
            id=proj_data.get("id", 0),
            name=name,
            engine_type=_parse_engine_type(proj_data.get("engine_type", "none")),
            deployment_target=_parse_deployment_target(proj_data.get("deployment_target", "local")),
            has_frontend=proj_data.get("has_frontend", True),
            has_mobile=proj_data.get("has_mobile", False),
            has_desktop=proj_data.get("has_desktop", False),
            has_shared_frontend_modules=proj_data.get("has_shared_frontend_modules", False),
            description=proj_data.get("description", ""),
        )

    # Parse domains: {project: {prod, dev, downloads}}. Domains are config data
    # (a project's public hostnames), not hardcoded in source.
    domains: Dict[str, DomainConfig] = {}
    for name, dom_data in data.get("domains", {}).items():
        if isinstance(dom_data, dict):
            domains[name.lower()] = DomainConfig(
                prod=dom_data.get("prod"),
                dev=dom_data.get("dev"),
                downloads=dom_data.get("downloads"),
            )
        elif isinstance(dom_data, str):
            # shorthand: project = "domain.com"
            domains[name.lower()] = DomainConfig(prod=dom_data)

    # Parse telemetry config
    telemetry_data = data.get("telemetry", {})
    telemetry = TelemetryConfig(
        api_port=telemetry_data.get("api_port", 8003),
        metrics_port=telemetry_data.get("metrics_port", 9003),
        tcp_protobuf_port=telemetry_data.get("tcp_protobuf_port", 3308),
        enabled=telemetry_data.get("enabled", True),
    )

    # Parse distribution config
    distribution = _parse_distribution_config(data)

    # Parse protection config
    protection = _parse_protection_config(data)

    # Parse packaging config
    packaging = _parse_packaging_config(data)

    # Parse signing config
    signing = _parse_signing_config(data)

    # Parse infrastructure config
    infrastructure = _parse_infrastructure_config(data)

    # Parse build config (curated build registries)
    build = _parse_build_config(data)

    # Parse fleet-operations config (curated project subsets; ships empty)
    fleet = _parse_fleet_config(data)

    # Parse secret-mapping config (curated project->keys maps; ships empty)
    secrets = _parse_secrets_config(data)

    # Parse the engine deployment registry (raw per-engine dicts; ships empty)
    engines: Dict[str, Dict] = {
        name: dict(entry) for name, entry in (data.get("engines", {}) or {}).items()
    }

    # Parse VPN network-orchestration config (ships empty)
    network = _parse_network_config(data)

    # Parse production-ship config (ships empty)
    ship = _parse_ship_config(data)

    # Parse credentials config (ships empty)
    cred_data = data.get("credentials", {}) or {}
    credentials = CredentialsConfig(
        entity_suffixes=dict(cred_data.get("entity_suffixes", {}) or {}),
    )

    # Validate deployment targets: each project's target must be a reserved
    # keyword or a known instance name. Warn (never fail) on a likely typo so a
    # mistyped target isn't silently treated as "served" while resolving to no host.
    _valid_targets = set(instances) | DeploymentTarget.RESERVED
    for _name, _proj in projects.items():
        if _proj.deployment_target not in _valid_targets:
            logger.warning(
                "project %r has deployment_target %r which is neither a reserved "
                "keyword (%s) nor a configured instance (%s); it will be treated "
                "as served but will not resolve to a host",
                _name,
                _proj.deployment_target,
                ", ".join(sorted(DeploymentTarget.RESERVED)),
                ", ".join(sorted(instances)) or "none",
            )

    return SegaConfig(
        meta=meta,
        instances=instances,
        projects=projects,
        domains=domains,
        telemetry=telemetry,
        distribution=distribution,
        protection=protection,
        packaging=packaging,
        signing=signing,
        infrastructure=infrastructure,
        build=build,
        critical_projects=data.get("critical_projects", []),
        fleet=fleet,
        secrets=secrets,
        engines=engines,
        network=network,
        ship=ship,
        credentials=credentials,
    )


def _parse_fleet_config(data: Dict[str, Any]) -> FleetConfig:
    """Parse the curated `[fleet]` section (all keys optional; ships empty)."""
    fleet_data = data.get("fleet", {}) or {}
    return FleetConfig(
        registry_projects=list(fleet_data.get("registry_projects", []) or []),
        deployment_tiers={
            k: list(v) for k, v in (fleet_data.get("deployment_tiers", {}) or {}).items()
        },
        port_allocations={
            k: dict(v) for k, v in (fleet_data.get("port_allocations", {}) or {}).items()
        },
        scan_groups={
            k: list(v) for k, v in (fleet_data.get("scan_groups", {}) or {}).items()
        },
        web_priority=list(fleet_data.get("web_priority", []) or []),
        app_projects=list(fleet_data.get("app_projects", []) or []),
        api_test_projects=list(fleet_data.get("api_test_projects", []) or []),
        probe_fallback_projects=list(fleet_data.get("probe_fallback_projects", []) or []),
        project_categories=dict(fleet_data.get("project_categories", {}) or {}),
        browser_test_ports=dict(fleet_data.get("browser_test_ports", {}) or {}),
        sysnc_groups={
            k: list(v) for k, v in (fleet_data.get("sysnc_groups", {}) or {}).items()
        },
        sysnc_categories=[list(p) for p in (fleet_data.get("sysnc_categories", []) or [])],
        frontend_merge_projects=list(fleet_data.get("frontend_merge_projects", []) or []),
        data_frontend_outputs=dict(fleet_data.get("data_frontend_outputs", {}) or {}),
        default_probe_project=fleet_data.get("default_probe_project", ""),
        telemetry_project=fleet_data.get("telemetry_project", ""),
        shared_setup_script=fleet_data.get("shared_setup_script", ""),
        project_registry_paths=list(fleet_data.get("project_registry_paths", []) or []),
        model_zoo_path=fleet_data.get("model_zoo_path", ""),
        engine_catalog_path=fleet_data.get("engine_catalog_path", ""),
    )


def _parse_secrets_config(data: Dict[str, Any]) -> SecretsMappingConfig:
    """Parse the curated `[secrets]` section (all keys optional; ships empty)."""
    sec_data = data.get("secrets", {}) or {}
    return SecretsMappingConfig(
        social_project_mappings={
            k: list(v)
            for k, v in (sec_data.get("social_project_mappings", {}) or {}).items()
        },
        project_required={
            k: list(v) for k, v in (sec_data.get("project_required", {}) or {}).items()
        },
        key_groups=dict(sec_data.get("key_groups", {}) or {}),
    )


def _parse_network_config(data: Dict[str, Any]) -> NetworkFleetConfig:
    """Parse the `[network]` section (VPN orchestration data; ships empty)."""
    net_data = data.get("network", {}) or {}
    discovery: Dict[str, list] = {}
    for category, nodes in (net_data.get("discovery", {}) or {}).items():
        discovery[category] = [dict(n) for n in (nodes or [])]
    return NetworkFleetConfig(
        service_ports=dict(net_data.get("service_ports", {}) or {}),
        default_service_port=net_data.get("default_service_port", 8000),
        discovery=discovery,
    )


def _parse_ship_config(data: Dict[str, Any]) -> ShipProductionConfig:
    """Parse the `[ship]` section (production-stack data; ships empty)."""
    ship_data = data.get("ship", {}) or {}
    return ShipProductionConfig(
        production_projects=list(ship_data.get("production_projects", []) or []),
        production_ports={
            k: [str(p) for p in v]
            for k, v in (ship_data.get("production_ports", {}) or {}).items()
        },
        nginx_ports=dict(ship_data.get("nginx_ports", {}) or {}),
    )


def _parse_distribution_config(data: Dict[str, Any]) -> DistributionConfig:
    """Parse distribution configuration from TOML data."""
    dist_data = data.get("distribution", {})

    # Parse exclusions
    excl_data = dist_data.get("exclusions", {})
    exclusions = ExclusionsConfig(
        telemetry_reporter=excl_data.get("telemetry_reporter", True),
        cloud_telemetry=excl_data.get("cloud_telemetry", True),
        remote_job_client=excl_data.get("remote_job_client", False),
    )

    # Parse S3 config
    s3_data = dist_data.get("s3", {})
    s3 = S3DistributionConfig(
        bucket=s3_data.get("bucket", "releases"),
        region=s3_data.get("region", "us-east-2"),
        access_key_env=s3_data.get("access_key_env", "AWS_ACCESS_KEY_ID"),
        secret_key_env=s3_data.get("secret_key_env", "AWS_SECRET_ACCESS_KEY"),
    )

    # Parse VSCE config
    vsce_data = dist_data.get("vsce", {})
    vsce = VSCEDistributionConfig(
        pat_env=vsce_data.get("pat_env", "VSCE_PAT"),
    )

    return DistributionConfig(
        default_mode=dist_data.get("default_mode", "cloud"),
        exclusions=exclusions,
        s3=s3,
        vsce=vsce,
        github_org=dist_data.get("github_org", ""),
    )


def _parse_protection_config(data: Dict[str, Any]) -> ProtectionConfig:
    """Parse code protection configuration from TOML data."""
    prot_data = data.get("protection", {})

    # Parse Python protection
    py_data = prot_data.get("python", {})
    python = PythonProtectionConfig(
        enabled=py_data.get("enabled", True),
        tool=py_data.get("tool", "nuitka"),
        options=py_data.get("options", "--standalone --onefile"),
        standalone_env=py_data.get(
            "standalone_env",
            {
                "FLEET_STANDALONE_BUILD": "true",
                "TELEMETRY_ENABLED": "false",
            },
        ),
    )

    # Parse Node protection
    node_data = prot_data.get("node", {})
    node = NodeProtectionConfig(
        enabled=node_data.get("enabled", True),
        tool=node_data.get("tool", "bytenode"),
        options=node_data.get("options", "--compress"),
        standalone_defines=node_data.get(
            "standalone_defines",
            {
                "STANDALONE_BUILD": "true",
                "TELEMETRY_ENABLED": "false",
            },
        ),
    )

    # Parse JS protection
    js_data = prot_data.get("js", {})
    js = JSProtectionConfig(
        enabled=js_data.get("enabled", False),
        tool=js_data.get("tool", "javascript-obfuscator"),
        options=js_data.get("options", "--compact true --self-defending true"),
    )

    # Parse Rust protection
    rust_data = prot_data.get("rust", {})
    rust = RustProtectionConfig(
        enabled=rust_data.get("enabled", True),
        standalone_features=rust_data.get("standalone_features", ["standalone"]),
        exclude_default_features=rust_data.get("exclude_default_features", True),
    )

    return ProtectionConfig(
        python=python,
        node=node,
        js=js,
        rust=rust,
    )


def _parse_packaging_config(data: Dict[str, Any]) -> PackagingConfig:
    """Parse packaging configuration from TOML data."""
    pkg_data = data.get("packaging", {})

    # Parse desktop packaging
    desktop_data = pkg_data.get("desktop", {})
    desktop_signing_data = desktop_data.get("signing", {})

    # Handle nested signing configs (mac, win, linux)
    mac_signing = desktop_signing_data.get("mac", {})
    win_signing = desktop_signing_data.get("win", {})
    linux_signing = desktop_signing_data.get("linux", {})

    desktop_signing = DesktopSigningConfig(
        mac_identity=mac_signing.get("identity", "Developer ID Application: Huntington Applied"),
        mac_notarize=mac_signing.get("notarize", True),
        win_certificate=win_signing.get("certificate", "${WINDOWS_CERT_PATH}"),
        win_timestamp=win_signing.get("timestamp", "http://timestamp.digicert.com"),
        linux_gpg_key=linux_signing.get("gpg_key", "${GPG_KEY_ID}"),
    )

    desktop = DesktopPackagingConfig(
        enabled=desktop_data.get("enabled", True),
        electron_builder=desktop_data.get("electron_builder", True),
        template=desktop_data.get("template", "docs/templates/desktop/electron_base"),
        platforms=desktop_data.get("platforms", ["mac", "win", "linux"]),
        signing=desktop_signing,
    )

    # Parse mobile packaging
    mobile_data = pkg_data.get("mobile", {})
    mobile_signing_data = mobile_data.get("signing", {})

    ios_signing = mobile_signing_data.get("ios", {})
    android_signing = mobile_signing_data.get("android", {})

    mobile_signing = MobileSigningConfig(
        ios_provisioning=ios_signing.get("provisioning", "${IOS_PROVISIONING_PROFILE}"),
        ios_certificate=ios_signing.get("certificate", "${IOS_DISTRIBUTION_CERT}"),
        android_keystore=android_signing.get("keystore", "${ANDROID_KEYSTORE_PATH}"),
        android_key_alias=android_signing.get("key_alias", "${ANDROID_KEY_ALIAS}"),
    )

    mobile = MobilePackagingConfig(
        enabled=mobile_data.get("enabled", True),
        expo=mobile_data.get("expo", True),
        template=mobile_data.get("template", "docs/templates/mobile"),
        platforms=mobile_data.get("platforms", ["ios", "android"]),
        signing=mobile_signing,
    )

    # Parse IDE packaging
    ide_data = pkg_data.get("ide", {})
    ide = IDEPackagingConfig(
        enabled=ide_data.get("enabled", False),
        template=ide_data.get("template", "docs/templates/IDE/vscode"),
        build_system=ide_data.get("build_system", "gulp"),
        platforms=ide_data.get("platforms", ["mac", "win", "linux"]),
    )

    # Parse extension packaging
    ext_data = pkg_data.get("extension", {})
    extension = ExtensionPackagingConfig(
        enabled=ext_data.get("enabled", False),
        tool=ext_data.get("tool", "vsce"),
        output=ext_data.get("output", ".vsix"),
    )

    # Parse CLI packaging
    cli_data = pkg_data.get("cli", {})
    cli = CLIPackagingConfig(
        enabled=cli_data.get("enabled", False),
        formats=cli_data.get("formats", ["binary", "cargo", "pip"]),
        platforms=cli_data.get("platforms", ["mac", "win", "linux"]),
    )

    return PackagingConfig(
        desktop=desktop,
        mobile=mobile,
        ide=ide,
        extension=extension,
        cli=cli,
    )


def _parse_signing_config(data: Dict[str, Any]) -> SigningConfig:
    """Parse signing configuration from TOML data."""
    sign_data = data.get("signing", {})

    # Parse Mac signing
    mac_data = sign_data.get("mac", {})
    mac = MacSigningEnvConfig(
        identity_env=mac_data.get("identity_env", "MAC_SIGNING_IDENTITY"),
        apple_id_env=mac_data.get("apple_id_env", "APPLE_ID"),
        apple_password_env=mac_data.get("apple_password_env", "APPLE_APP_SPECIFIC_PASSWORD"),
        team_id_env=mac_data.get("team_id_env", "APPLE_TEAM_ID"),
    )

    # Parse Windows signing
    win_data = sign_data.get("win", {})
    win = WindowsSigningEnvConfig(
        cert_path_env=win_data.get("cert_path_env", "WINDOWS_CERT_PATH"),
        cert_password_env=win_data.get("cert_password_env", "WINDOWS_CERT_PASSWORD"),
    )

    # Parse Linux signing
    linux_data = sign_data.get("linux", {})
    linux = LinuxSigningEnvConfig(
        gpg_key_env=linux_data.get("gpg_key_env", "GPG_KEY_ID"),
        gpg_passphrase_env=linux_data.get("gpg_passphrase_env", "GPG_PASSPHRASE"),
    )

    return SigningConfig(
        mac=mac,
        win=win,
        linux=linux,
    )


def _parse_infrastructure_config(data: Dict[str, Any]) -> InfrastructureConfig:
    """Parse infrastructure configuration from TOML data."""
    infra_data = data.get("infrastructure", {})

    # Parse shared environments
    shared_data = infra_data.get("shared_environments", {})
    shared_environments = SharedEnvironmentsConfig(
        root=shared_data.get("root", "${FLEET_ROOT}/environments"),
        node_modules=shared_data.get("node_modules", "${FLEET_ROOT}/environments/node_modules"),
        backend_venv=shared_data.get("backend_venv", "${FLEET_ROOT}/environments/backend_venv"),
        engine_venv=shared_data.get("engine_venv", "${FLEET_ROOT}/environments/engine_venv"),
        package_json=shared_data.get("package_json", "${FLEET_ROOT}/environments/package.json"),
    )

    # Parse frontend orchestration
    fe_data = infra_data.get("frontend_orchestration", {})
    build_data = fe_data.get("build", {})
    serve_data = fe_data.get("serve", {})
    parallel_data = fe_data.get("parallel", {})

    frontend_orchestration = FrontendOrchestrationConfig(
        default_mode=fe_data.get("default_mode", "shared"),
        build=FrontendBuildConfig(
            command=build_data.get("command", "npm run build"),
            output_dir=build_data.get("output_dir", ".next"),
            timeout=build_data.get("timeout", 300),
        ),
        serve=FrontendServeConfig(
            command=serve_data.get("command", "npm run start"),
            dev_command=serve_data.get("dev_command", "npm run dev"),
            health_check_path=serve_data.get("health_check_path", "/"),
            startup_timeout=serve_data.get("startup_timeout", 30),
        ),
        parallel=FrontendParallelConfig(
            max_concurrent=parallel_data.get("max_concurrent", 4),
            stagger_delay=parallel_data.get("stagger_delay", 2),
        ),
    )

    # Parse unified server config
    us_data = infra_data.get("unified_server", {})
    ssl_data = us_data.get("ssl", {})
    rp_data = us_data.get("reverse_proxy", {})
    sf_data = us_data.get("static_files", {})

    unified_server = UnifiedServerConfig(
        name=us_data.get("name", "unified-server"),
        description=us_data.get("description", "Single-server deployment for multiple FLEET projects"),
        strategy=us_data.get("strategy", "reverse-proxy"),
        domain=us_data.get("domain", "example.local"),
        ssl=SSLConfig(
            enabled=ssl_data.get("enabled", False),
            cert_path=ssl_data.get("cert_path", "/etc/ssl/certs/fleet.crt"),
            key_path=ssl_data.get("key_path", "/etc/ssl/private/fleet.key"),
        ),
        reverse_proxy=ReverseProxyConfig(
            type=rp_data.get("type", "nginx"),
            config_path=rp_data.get("config_path", "/etc/nginx/sites-available"),
            enabled_path=rp_data.get("enabled_path", "/etc/nginx/sites-enabled"),
            service_name=rp_data.get("service_name", "nginx"),
            proxy_connect_timeout=rp_data.get("proxy_connect_timeout", "60s"),
            proxy_send_timeout=rp_data.get("proxy_send_timeout", "60s"),
            proxy_read_timeout=rp_data.get("proxy_read_timeout", "60s"),
        ),
        static_files=StaticFilesConfig(
            enabled=sf_data.get("enabled", True),
            root_path=sf_data.get("root_path", "/var/www/fleet"),
            assets_path=sf_data.get("assets_path", "/var/www/fleet/assets"),
        ),
    )

    # Parse routing config
    routing_data = infra_data.get("routing", {})
    subdomain_data = routing_data.get("subdomain", {})
    path_data = routing_data.get("path", {})
    port_data = routing_data.get("port", {})

    routing = RoutingConfig(
        subdomain=SubdomainRoutingConfig(
            enabled=subdomain_data.get("enabled", True),
            pattern=subdomain_data.get("pattern", "{service}-{type}.{domain}"),
        ),
        path=PathRoutingConfig(
            enabled=path_data.get("enabled", True),
            api_prefix=path_data.get("api_prefix", "/api"),
            mobile_prefix=path_data.get("mobile_prefix", "/mobile"),
            desktop_prefix=path_data.get("desktop_prefix", "/desktop"),
        ),
        port=PortRoutingConfig(
            enabled=port_data.get("enabled", False),
            base_domain=port_data.get("base_domain", "localhost"),
        ),
    )

    # Parse monitoring config
    mon_data = infra_data.get("monitoring", {})
    ph_data = mon_data.get("project_health", {})

    monitoring = MonitoringConfig(
        enabled=mon_data.get("enabled", True),
        health_check_path=mon_data.get("health_check_path", "/health"),
        health_check_interval=mon_data.get("health_check_interval", "30s"),
        project_health=ProjectHealthConfig(
            enabled=ph_data.get("enabled", True),
            check_services=ph_data.get("check_services", ["api", "frontend"]),
            timeout=ph_data.get("timeout", "10s"),
        ),
    )

    # Parse security config
    sec_data = infra_data.get("security", {})
    rl_data = sec_data.get("rate_limiting", {})
    cors_data = sec_data.get("cors", {})

    security = SecurityConfig(
        rate_limiting=RateLimitingConfig(
            enabled=rl_data.get("enabled", True),
            requests_per_minute=rl_data.get("requests_per_minute", 100),
            burst_size=rl_data.get("burst_size", 20),
        ),
        cors=CORSConfig(
            enabled=cors_data.get("enabled", True),
            allowed_origins=cors_data.get("allowed_origins", ["*"]),
            allowed_methods=cors_data.get("allowed_methods", ["GET", "POST", "PUT", "DELETE", "OPTIONS"]),
            allowed_headers=cors_data.get("allowed_headers", ["*"]),
        ),
        headers=sec_data.get(
            "headers",
            [
                "X-Frame-Options DENY",
                "X-Content-Type-Options nosniff",
                "X-XSS-Protection 1; mode=block",
                "Referrer-Policy strict-origin-when-cross-origin",
            ],
        ),
    )

    # Parse logging config
    log_data = infra_data.get("logging", {})
    rot_data = log_data.get("rotation", {})

    logging_config = LoggingConfig(
        access_log=log_data.get("access_log", "/var/log/nginx/fleet_access.log"),
        error_log=log_data.get("error_log", "/var/log/nginx/fleet_error.log"),
        format=log_data.get("format", "combined"),
        rotation=LogRotationConfig(
            enabled=rot_data.get("enabled", True),
            retention_days=rot_data.get("retention_days", 30),
            compress=rot_data.get("compress", True),
        ),
    )

    return InfrastructureConfig(
        shared_environments=shared_environments,
        frontend_orchestration=frontend_orchestration,
        unified_server=unified_server,
        routing=routing,
        monitoring=monitoring,
        security=security,
        logging=logging_config,
    )


def _parse_build_config(data: Dict[str, Any]) -> BuildConfig:
    """Parse the curated `[build]` registries from TOML data.

    These are standalone config lists (desktop/ide/binary/cli/engine), transcribed
    from the previously-hardcoded build registries in the binaries command. They are
    NOT derived from project flags. Missing keys yield empty registries.
    """
    build_data = data.get("build", {})

    cli: Dict[str, CLIBuildEntry] = {}
    for name, entry in (build_data.get("cli", {}) or {}).items():
        cli[name] = CLIBuildEntry(
            cli_dir=entry.get("cli_dir", ""),
            package_name=entry.get("package_name", ""),
            binary_name=entry.get("binary_name", ""),
            install_script=entry.get("install_script", ""),
            source_dir=entry.get("source_dir", ""),
            tool=entry.get("tool", "python"),
        )

    # Engine registry stays a plain dict-of-dicts (heterogeneous per-lang keys:
    # python entries carry `package`, rust entries carry `binary_name`/`features`).
    engine: Dict[str, Dict] = {
        name: dict(entry) for name, entry in (build_data.get("engine", {}) or {}).items()
    }

    return BuildConfig(
        desktop=list(build_data.get("desktop", []) or []),
        ide=list(build_data.get("ide", []) or []),
        binary=dict(build_data.get("binary", {}) or {}),
        cli=cli,
        engine=engine,
    )


def load_config(config_path: Optional[Path] = None) -> SegaConfig:
    """
    Load SEGA configuration from TOML file.

    Args:
        config_path: Optional path to configuration file.
                    If not provided, searches standard locations.

    Returns:
        SegaConfig instance

    Raises:
        ConfigurationError: If TOML library not available or loading fails
    """
    if tomllib is None:
        raise ConfigurationError(
            "No TOML library available. Install 'toml' package or use Python 3.11+: pip install toml"
        )

    # Find config file. If none exists (fresh install / no fleet yet), start with
    # an empty fleet rather than crashing — the CLI must run without a config so a
    # newcomer can reach `sega init`. Parse errors below still raise.
    if config_path is None:
        try:
            config_path = _find_config_file()
        except ConfigurationError:
            logger.warning(
                "No sega.toml found — starting with an empty fleet. "
                "Run `sega fleet init` to create one, or set SEGA_CONFIG_PATH."
            )
            return SegaConfig()
    else:
        config_path = Path(config_path).expanduser()
        if not config_path.exists():
            raise ConfigurationError(f"Configuration file not found: {config_path}")

    # Load TOML
    try:
        if _TOML_READER == "tomllib":
            # Python 3.11+ tomllib requires binary mode
            with open(config_path, "rb") as f:
                data = tomllib.load(f)  # type: ignore
        else:
            # toml package uses text mode
            with open(config_path, "r") as f:
                data = tomllib.load(f)  # type: ignore
    except Exception as e:
        raise ConfigurationError(f"Failed to parse TOML: {e}") from e

    # Expand environment variables
    data = _expand_env_vars(data)

    # Apply SEGA_* overrides
    data = _apply_env_overrides(data)

    # Build and return config
    return _build_config(data, config_path)


def get_config(reload: bool = False) -> SegaConfig:
    """
    Get the singleton SegaConfig instance.

    This is the primary interface for accessing SEGA configuration.
    The configuration is loaded once and cached for performance.

    Args:
        reload: If True, force reload configuration from disk

    Returns:
        SegaConfig singleton instance

    Example:
        config = get_config()
        atlas = config.get_project("atlas")
        print(f"Atlas API port: {atlas.api_port}")
    """
    global _config_instance

    if _config_instance is None or reload:
        _config_instance = load_config()

    return _config_instance


def reload_config() -> SegaConfig:
    """
    Force reload configuration from disk.

    Equivalent to get_config(reload=True).

    Returns:
        Fresh SegaConfig instance
    """
    return get_config(reload=True)


def get_config_path() -> Optional[Path]:
    """
    Get the path to the currently loaded configuration file.

    Returns:
        Path to config file, or None if not yet loaded
    """
    config = get_config()
    if config.meta.config_path:
        return Path(config.meta.config_path)
    return None


# Utility functions for common operations


def get_project_api_url(project_name: str, host: str = "localhost") -> Optional[str]:
    """
    Get the API URL for a project.

    Args:
        project_name: Name of the project
        host: Hostname (default: localhost)

    Returns:
        API URL string or None if project not found
    """
    config = get_config()
    project = config.get_project(project_name)
    if project:
        return f"http://{host}:{project.api_port}"
    return None


def get_deployment_target(project_name: str) -> Optional[str]:
    """
    Get the deployment IP for a project.

    Args:
        project_name: Name of the project

    Returns:
        IP address string or None if not deployed
    """
    config = get_config()
    return config.get_instance_ip(project_name)
