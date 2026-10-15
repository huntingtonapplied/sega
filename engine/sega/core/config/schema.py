# Copyright 2022-2026 Huntington Applied
# License: Apache-2.0
#
# SEGA Central Configuration Schema
# Typed dataclass definitions for SEGA configuration
#
# AUTHORITATIVE REFERENCES:
# - Port Allocation Standards: /docs/standards/infrastructure/PORT_ALLOCATION_STANDARDS.md
# - URL & Addressing Registry: /docs/standards/infrastructure/URL_AND_ADDRESSING_REGISTRY.md
# - Domain Registry: /docs/architecture/infrastructure/dns/FLEET_DOMAIN_REGISTRY.md
# - EC2 Instance Registry: /docs/operations/infrastructure/EC2_INSTANCE_REGISTRY.md

"""
SEGA Configuration Schema

Provides typed dataclass definitions for SEGA's central configuration system.
All port calculations follow PORT_ALLOCATION_STANDARDS.md formulas.
"""

from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, List, Optional


class EngineType(Enum):
    """Project engine type classification per FLEET_ECOSYSTEM_GROUPINGS.md"""
    SIMULATION = "simulation"
    WORKFLOW = "workflow"
    UTILITY = "utility"
    FUNCTION_LIBRARY = "function_library"
    NONE = "none"


class DeploymentTarget:
    """Reserved deployment-target keywords.

    A project's ``deployment_target`` is a string that is either one of these
    reserved keywords or the name of an instance defined in ``config.instances``
    (resolved at runtime). Instance names are therefore fully config-driven and
    are never hardcoded here — the platform supports any number of instances.
    """
    LOCAL = "local"
    NOT_SERVED = "not_served"
    RESERVED = frozenset({LOCAL, NOT_SERVED})


@dataclass
class PortConfig:
    """
    Port configuration for a project.

    All ports are computed from project_id using standardized formulas
    from PORT_ALLOCATION_STANDARDS.md:

    - api_port = 8000 + project_id
    - frontend_port = 3000 + project_id
    - product_app_port = 4000 + project_id
    - desktop_port = 3300 + project_id
    - mobile_port = 19000 + project_id
    - database_port = 5000 + project_id
    - redis_port = 6000 + project_id
    - metrics_port = 9000 + project_id
    - grpc_port = api_port + 100
    - admin_port = api_port + 200
    - test ports = production_port + 20000
    """
    project_id: int

    @property
    def api(self) -> int:
        """HTTP REST API port (8000 + project_id)"""
        return 8000 + self.project_id

    @property
    def frontend(self) -> int:
        """Frontend development server port (3000 + project_id)"""
        return 3000 + self.project_id

    @property
    def product_app(self) -> int:
        """Product application port (4000 + project_id)"""
        return 4000 + self.project_id

    @property
    def desktop(self) -> int:
        """Desktop application port (3300 + project_id)"""
        return 3300 + self.project_id

    @property
    def mobile(self) -> int:
        """Mobile development port (19000 + project_id)"""
        return 19000 + self.project_id

    @property
    def database(self) -> int:
        """PostgreSQL port (5000 + project_id)"""
        return 5000 + self.project_id

    @property
    def redis(self) -> int:
        """Redis port (6000 + project_id)"""
        return 6000 + self.project_id

    @property
    def metrics(self) -> int:
        """Prometheus metrics port (9000 + project_id)"""
        return 9000 + self.project_id

    @property
    def grpc(self) -> int:
        """gRPC port (api + 100)"""
        return self.api + 100

    @property
    def admin(self) -> int:
        """Admin interface port (api + 200)"""
        return self.api + 200

    # Test environment ports (add 20000 to production ports)
    @property
    def test_api(self) -> int:
        """Test API port (api + 20000)"""
        return self.api + 20000

    @property
    def test_frontend(self) -> int:
        """Test frontend port (frontend + 20000)"""
        return self.frontend + 20000

    @property
    def test_database(self) -> int:
        """Test database port (database + 20000)"""
        return self.database + 20000

    @property
    def test_redis(self) -> int:
        """Test redis port (redis + 20000)"""
        return self.redis + 20000

    @property
    def test_metrics(self) -> int:
        """Test metrics port (metrics + 20000)"""
        return self.metrics + 20000

    def to_dict(self) -> Dict[str, int]:
        """Convert to dictionary for backward compatibility"""
        return {
            "api": self.api,
            "frontend": self.frontend,
            "product_app": self.product_app,
            "desktop": self.desktop,
            "mobile": self.mobile,
            "database": self.database,
            "redis": self.redis,
            "metrics": self.metrics,
            "grpc": self.grpc,
            "admin": self.admin,
            "test_api": self.test_api,
            "test_frontend": self.test_frontend,
            "test_database": self.test_database,
            "test_redis": self.test_redis,
            "test_metrics": self.test_metrics,
        }


@dataclass
class ProjectConfig:
    """
    Configuration for an FLEET project.

    Attributes:
        id: Project ID (0-21) used for port calculation
        name: Project name (lowercase)
        engine_type: Type of engine (simulation, workflow, utility, etc.)
        deployment_target: Where the project is deployed
        has_frontend: Whether project has a frontend component
        has_mobile: Whether project has mobile apps
        has_desktop: Whether project has desktop app
        has_shared_frontend_modules: Whether project uses the shared frontend/IDE
            node_modules setup (symlinks for landing_app/product_app, shared-dir
            validation, status reporting)
        description: Brief project description
    """
    id: int
    name: str
    engine_type: EngineType = EngineType.NONE
    deployment_target: str = DeploymentTarget.LOCAL
    has_frontend: bool = True
    has_mobile: bool = False
    has_desktop: bool = False
    has_shared_frontend_modules: bool = False
    description: str = ""

    @property
    def ports(self) -> PortConfig:
        """Get computed port configuration for this project"""
        return PortConfig(self.id)

    @property
    def api_port(self) -> int:
        """Shortcut for API port"""
        return self.ports.api

    @property
    def frontend_port(self) -> int:
        """Shortcut for frontend port"""
        return self.ports.frontend

    @property
    def database_port(self) -> int:
        """Shortcut for database port"""
        return self.ports.database

    @property
    def redis_port(self) -> int:
        """Shortcut for redis port"""
        return self.ports.redis

    @property
    def metrics_port(self) -> int:
        """Shortcut for metrics port"""
        return self.ports.metrics

    @property
    def is_served(self) -> bool:
        """Whether this project is served (deployed to a remote instance)"""
        return self.deployment_target not in DeploymentTarget.RESERVED

    def to_dict(self) -> Dict:
        """Convert to dictionary for backward compatibility"""
        return {
            "id": self.id,
            "name": self.name,
            "engine_type": self.engine_type.value,
            "deployment_target": self.deployment_target,
            "has_frontend": self.has_frontend,
            "has_mobile": self.has_mobile,
            "has_desktop": self.has_desktop,
            "has_shared_frontend_modules": self.has_shared_frontend_modules,
            "description": self.description,
            "ports": self.ports.to_dict(),
        }


@dataclass
class InstanceConfig:
    """
    Configuration for an EC2 instance.

    Attributes:
        name: Instance identifier (e.g., "fleet-prod-01")
        ip: Public IP address
        projects: List of project names deployed to this instance
        ssh_user: SSH username (default: ubuntu)
        ssh_key_path: Path to SSH key file
    """
    name: str
    ip: str
    projects: List[str] = field(default_factory=list)
    ssh_user: str = "ubuntu"
    ssh_key_path: str = "~/.ssh/id_rsa"

    @property
    def ssh_connection(self) -> str:
        """Full SSH connection string"""
        return f"{self.ssh_user}@{self.ip}"

    def to_dict(self) -> Dict:
        """Convert to dictionary for backward compatibility"""
        return {
            "name": self.name,
            "ip": self.ip,
            "projects": self.projects,
            "ssh_user": self.ssh_user,
            "ssh_key_path": self.ssh_key_path,
            "ssh_connection": self.ssh_connection,
        }


@dataclass
class TelemetryConfig:
    """Telemetry backend integration configuration"""
    api_port: int = 8003
    metrics_port: int = 9003
    tcp_protobuf_port: int = 3308
    enabled: bool = True


# =============================================================================
# DISTRIBUTION & PACKAGING CONFIGURATION
# =============================================================================


@dataclass
class ExclusionsConfig:
    """
    Compile-time feature exclusions for standalone builds.

    These features are excluded when building for desktop/CLI distribution
    to remove dependencies on central infrastructure.
    """
    telemetry_reporter: bool = True
    cloud_telemetry: bool = True
    remote_job_client: bool = False


@dataclass
class PythonProtectionConfig:
    """Python code protection configuration (Nuitka)"""
    enabled: bool = True
    tool: str = "nuitka"
    options: str = "--standalone --onefile"
    standalone_env: Dict[str, str] = field(default_factory=lambda: {
        "FLEET_STANDALONE_BUILD": "true",
        "TELEMETRY_ENABLED": "false",
    })


@dataclass
class NodeProtectionConfig:
    """Node.js code protection configuration (Bytenode)"""
    enabled: bool = True
    tool: str = "bytenode"
    options: str = "--compress"
    standalone_defines: Dict[str, str] = field(default_factory=lambda: {
        "STANDALONE_BUILD": "true",
        "TELEMETRY_ENABLED": "false",
    })


@dataclass
class JSProtectionConfig:
    """JavaScript code protection configuration (obfuscator)"""
    enabled: bool = False
    tool: str = "javascript-obfuscator"
    options: str = "--compact true --self-defending true"


@dataclass
class RustProtectionConfig:
    """Rust code protection configuration"""
    enabled: bool = True
    standalone_features: List[str] = field(default_factory=lambda: ["standalone"])
    exclude_default_features: bool = True


@dataclass
class ProtectionConfig:
    """Aggregated code protection configuration"""
    python: PythonProtectionConfig = field(default_factory=PythonProtectionConfig)
    node: NodeProtectionConfig = field(default_factory=NodeProtectionConfig)
    js: JSProtectionConfig = field(default_factory=JSProtectionConfig)
    rust: RustProtectionConfig = field(default_factory=RustProtectionConfig)


@dataclass
class DesktopSigningConfig:
    """Platform-specific desktop signing configuration"""
    mac_identity: str = "Developer ID Application: Huntington Applied"
    mac_notarize: bool = True
    win_certificate: str = "${WINDOWS_CERT_PATH}"
    win_timestamp: str = "http://timestamp.digicert.com"
    linux_gpg_key: str = "${GPG_KEY_ID}"


@dataclass
class DesktopPackagingConfig:
    """Desktop packaging configuration (Electron)"""
    enabled: bool = True
    electron_builder: bool = True
    template: str = "docs/templates/desktop/electron_base"
    platforms: List[str] = field(default_factory=lambda: ["mac", "win", "linux"])
    signing: DesktopSigningConfig = field(default_factory=DesktopSigningConfig)


@dataclass
class MobileSigningConfig:
    """Platform-specific mobile signing configuration"""
    ios_provisioning: str = "${IOS_PROVISIONING_PROFILE}"
    ios_certificate: str = "${IOS_DISTRIBUTION_CERT}"
    android_keystore: str = "${ANDROID_KEYSTORE_PATH}"
    android_key_alias: str = "${ANDROID_KEY_ALIAS}"


@dataclass
class MobilePackagingConfig:
    """Mobile packaging configuration (Expo EAS)"""
    enabled: bool = True
    expo: bool = True
    template: str = "docs/templates/mobile"
    platforms: List[str] = field(default_factory=lambda: ["ios", "android"])
    signing: MobileSigningConfig = field(default_factory=MobileSigningConfig)


@dataclass
class IDEPackagingConfig:
    """IDE packaging configuration (VS Code fork)"""
    enabled: bool = False
    template: str = "docs/templates/IDE/vscode"
    build_system: str = "gulp"
    platforms: List[str] = field(default_factory=lambda: ["mac", "win", "linux"])


@dataclass
class ExtensionPackagingConfig:
    """VS Code extension packaging configuration"""
    enabled: bool = False
    tool: str = "vsce"
    output: str = ".vsix"


@dataclass
class CLIPackagingConfig:
    """CLI distribution packaging configuration"""
    enabled: bool = False
    formats: List[str] = field(default_factory=lambda: ["binary", "cargo", "pip"])
    platforms: List[str] = field(default_factory=lambda: ["mac", "win", "linux"])


@dataclass
class PackagingConfig:
    """Aggregated packaging configuration"""
    desktop: DesktopPackagingConfig = field(default_factory=DesktopPackagingConfig)
    mobile: MobilePackagingConfig = field(default_factory=MobilePackagingConfig)
    ide: IDEPackagingConfig = field(default_factory=IDEPackagingConfig)
    extension: ExtensionPackagingConfig = field(default_factory=ExtensionPackagingConfig)
    cli: CLIPackagingConfig = field(default_factory=CLIPackagingConfig)


@dataclass
class MacSigningEnvConfig:
    """macOS signing environment variable references"""
    identity_env: str = "MAC_SIGNING_IDENTITY"
    apple_id_env: str = "APPLE_ID"
    apple_password_env: str = "APPLE_APP_SPECIFIC_PASSWORD"
    team_id_env: str = "APPLE_TEAM_ID"


@dataclass
class WindowsSigningEnvConfig:
    """Windows signing environment variable references"""
    cert_path_env: str = "WINDOWS_CERT_PATH"
    cert_password_env: str = "WINDOWS_CERT_PASSWORD"


@dataclass
class LinuxSigningEnvConfig:
    """Linux signing environment variable references"""
    gpg_key_env: str = "GPG_KEY_ID"
    gpg_passphrase_env: str = "GPG_PASSPHRASE"


@dataclass
class SigningConfig:
    """Aggregated signing configuration"""
    mac: MacSigningEnvConfig = field(default_factory=MacSigningEnvConfig)
    win: WindowsSigningEnvConfig = field(default_factory=WindowsSigningEnvConfig)
    linux: LinuxSigningEnvConfig = field(default_factory=LinuxSigningEnvConfig)


@dataclass
class S3DistributionConfig:
    """S3 distribution configuration"""
    bucket: str = "releases"
    region: str = "us-east-2"
    access_key_env: str = "AWS_ACCESS_KEY_ID"
    secret_key_env: str = "AWS_SECRET_ACCESS_KEY"


@dataclass
class VSCEDistributionConfig:
    """VS Code Marketplace distribution configuration"""
    pat_env: str = "VSCE_PAT"


@dataclass
class DistributionConfig:
    """
    Distribution and packaging configuration.

    Controls how projects are compiled, packaged, and distributed.
    """
    default_mode: str = "cloud"  # 'standalone' for desktop/CLI, 'cloud' for infrastructure
    exclusions: ExclusionsConfig = field(default_factory=ExclusionsConfig)
    s3: S3DistributionConfig = field(default_factory=S3DistributionConfig)
    vsce: VSCEDistributionConfig = field(default_factory=VSCEDistributionConfig)
    # GitHub org used for release distribution (empty = not configured).
    github_org: str = ""


@dataclass
class CLIBuildEntry:
    """Build metadata for one CLI project (the `[build.cli.<project>]` table).

    Curated per-project build config for the standalone CLI binary. `tool` is the
    build type — "python" (Nuitka) or "rust" (cargo) — defaulting to the historical
    default of "python". Paths are relative to the FLEET workspace root (get_fleet_root()).
    """
    cli_dir: str
    package_name: str
    binary_name: str = ""
    install_script: str = ""
    source_dir: str = ""
    tool: str = "python"


@dataclass
class BuildConfig:
    """Curated build registries (the `[build]` section).

    Standalone config data (NOT derived from project `has_desktop` flags — that flag
    is incomplete and some build entries aren't `[projects]` keys).
    Each field mirrors a curated build list that previously lived hardcoded in
    engine/sega/cli/commands/binaries.py:

    - desktop: Electron desktop-app build set (list of project names).
    - ide: VS Code fork IDE build set (list of project names).
    - binary: CLI-binary language map {project -> "rust"|"python"}.
    - cli: per-project CLI build metadata {project -> CLIBuildEntry}.
    - engine: per-project obfuscated-engine build metadata {project -> dict}.
    """
    desktop: List[str] = field(default_factory=list)
    ide: List[str] = field(default_factory=list)
    binary: Dict[str, str] = field(default_factory=dict)
    cli: Dict[str, CLIBuildEntry] = field(default_factory=dict)
    engine: Dict[str, Dict] = field(default_factory=dict)


@dataclass
class MetaConfig:
    """Configuration metadata"""
    version: str = "1.0.0"
    config_path: Optional[str] = None


@dataclass
class FleetConfig:
    """Curated fleet-operations data (the `[fleet]` section).

    These are operator-curated project subsets and per-deployment data that
    match no config predicate (deployment ordering, scan groups, presentation
    order, legacy port maps, catalog file locations). They are pure config
    data: the engine ships with EMPTY defaults and behaves sanely without
    them; a fleet operator fills them in for their own portfolio.
    """
    # Default project set for registry-based deployment (ship/registry).
    registry_projects: List[str] = field(default_factory=list)
    # Deployment-ordering tiers, e.g. {"infrastructure": [...], "services": [...],
    # "applications": [...]}; tiers deploy in declaration order.
    deployment_tiers: Dict[str, List[str]] = field(default_factory=dict)
    # Legacy per-project port maps for the enhanced local manager, e.g.
    # {project: {"api": 8000, "frontend": 3000, "expo_web": 19000, "desktop": 3300}}.
    port_allocations: Dict[str, Dict[str, int]] = field(default_factory=dict)
    # Instance scan groups for `local open --scan --remote N`, keyed "group1"/"group2".
    scan_groups: Dict[str, List[str]] = field(default_factory=dict)
    # Presentation/priority order for browser-opening of web projects.
    web_priority: List[str] = field(default_factory=list)
    # Core application project set (mobile builds, probe/browser tests,
    # ecosystem health ports, `secrets apply --project all`).
    app_projects: List[str] = field(default_factory=list)
    # Default project set for API test runs / OpenAPI discovery.
    api_test_projects: List[str] = field(default_factory=list)
    # Project set for the probe backend-test fallback config (superset of
    # app_projects that includes CLI-only projects).
    probe_fallback_projects: List[str] = field(default_factory=list)
    # Probe project categories, e.g. {"myproject": "ml"}; unlisted projects
    # default to "infrastructure".
    project_categories: Dict[str, str] = field(default_factory=dict)
    # Legacy browser-test frontend port overrides {project: port}.
    browser_test_ports: Dict[str, int] = field(default_factory=dict)
    # Conflict-analysis project groups for the sysnc tooling.
    sysnc_groups: Dict[str, List[str]] = field(default_factory=dict)
    # Ordered [path_prefix, label] pairs for sysnc conflict categorization.
    sysnc_categories: List[List[str]] = field(default_factory=list)
    # Projects whose frontend package.json files are merged into the shared env.
    frontend_merge_projects: List[str] = field(default_factory=list)
    # Where generated data-catalog frontends are written, {project: relative_path}.
    data_frontend_outputs: Dict[str, str] = field(default_factory=dict)
    # Default project for the standalone structured test reporter CLI.
    default_probe_project: str = ""
    # Project that hosts the fleet telemetry/metrics backend (empty = none).
    telemetry_project: str = ""
    # Workspace-relative path of the shared frontend-modules setup script.
    shared_setup_script: str = ""
    # Workspace-relative candidate paths for the projects-registry JSON.
    project_registry_paths: List[str] = field(default_factory=list)
    # Workspace-relative path of the merged model-zoo catalog.
    model_zoo_path: str = ""
    # Workspace-relative path of the merged engine catalog.
    engine_catalog_path: str = ""


@dataclass
class SecretsMappingConfig:
    """Curated secret-to-project mappings (the `[secrets]` section).

    Operator data: which secret keys each project consumes. Ships EMPTY;
    the secrets commands simply manage no per-project keys until configured.
    """
    # {project: [secret key names]} for the social secrets manager.
    social_project_mappings: Dict[str, List[str]] = field(default_factory=dict)
    # {project: [required secret key names]} for validation.
    project_required: Dict[str, List[str]] = field(default_factory=dict)
    # Extra {SECRET_KEY: group} entries merged over the generic platform map.
    key_groups: Dict[str, str] = field(default_factory=dict)


@dataclass
class NetworkFleetConfig:
    """VPN network-orchestration data (the `[network]` section). Ships EMPTY."""
    # {service: port} defaults for VPN-deployed services.
    service_ports: Dict[str, int] = field(default_factory=dict)
    # Fallback port when a service has no entry above.
    default_service_port: int = 8000
    # Example/known topology for discovery, e.g. {"backends": [{ip, service, port}], ...}.
    discovery: Dict[str, List[Dict]] = field(default_factory=dict)


@dataclass
class ShipProductionConfig:
    """Production-ship deployment data (the `[ship]` section). Ships EMPTY."""
    # Default project set for generated production compose stacks.
    production_projects: List[str] = field(default_factory=list)
    # {project: [port strings]} published in the generated compose file.
    production_ports: Dict[str, List[str]] = field(default_factory=dict)
    # {project: port} upstream ports for the generated nginx site config.
    nginx_ports: Dict[str, int] = field(default_factory=dict)


@dataclass
class CredentialsConfig:
    """Deployment-credential lookup data (the `[credentials]` section). Ships EMPTY."""
    # {entity: ENV_VAR_SUFFIX} for entity-scoped platform credentials.
    entity_suffixes: Dict[str, str] = field(default_factory=dict)


# =============================================================================
# INFRASTRUCTURE CONFIGURATION
# =============================================================================


@dataclass
class SharedEnvironmentsConfig:
    """Shared environments paths for dependency management."""
    root: str = "${FLEET_ROOT}/environments"
    node_modules: str = "${FLEET_ROOT}/environments/node_modules"
    backend_venv: str = "${FLEET_ROOT}/environments/backend_venv"
    engine_venv: str = "${FLEET_ROOT}/environments/engine_venv"
    package_json: str = "${FLEET_ROOT}/environments/package.json"


@dataclass
class FrontendBuildConfig:
    """Frontend build settings."""
    command: str = "npm run build"
    output_dir: str = ".next"
    timeout: int = 300


@dataclass
class FrontendServeConfig:
    """Frontend serve settings."""
    command: str = "npm run start"
    dev_command: str = "npm run dev"
    health_check_path: str = "/"
    startup_timeout: int = 30


@dataclass
class FrontendParallelConfig:
    """Frontend parallel execution settings."""
    max_concurrent: int = 4
    stagger_delay: int = 2


@dataclass
class FrontendOrchestrationConfig:
    """Frontend orchestration configuration."""
    default_mode: str = "shared"
    build: FrontendBuildConfig = field(default_factory=FrontendBuildConfig)
    serve: FrontendServeConfig = field(default_factory=FrontendServeConfig)
    parallel: FrontendParallelConfig = field(default_factory=FrontendParallelConfig)


@dataclass
class SSLConfig:
    """SSL certificate configuration."""
    enabled: bool = False
    cert_path: str = "/etc/ssl/certs/fleet.crt"
    key_path: str = "/etc/ssl/private/fleet.key"


@dataclass
class ReverseProxyConfig:
    """Nginx reverse proxy configuration."""
    type: str = "nginx"
    config_path: str = "/etc/nginx/sites-available"
    enabled_path: str = "/etc/nginx/sites-enabled"
    service_name: str = "nginx"
    proxy_connect_timeout: str = "60s"
    proxy_send_timeout: str = "60s"
    proxy_read_timeout: str = "60s"


@dataclass
class StaticFilesConfig:
    """Static file serving configuration."""
    enabled: bool = True
    root_path: str = "/var/www/fleet"
    assets_path: str = "/var/www/fleet/assets"


@dataclass
class UnifiedServerConfig:
    """Unified server infrastructure configuration."""
    name: str = "unified-server"
    description: str = "Single-server deployment for multiple FLEET projects"
    strategy: str = "reverse-proxy"
    domain: str = "example.local"
    ssl: SSLConfig = field(default_factory=SSLConfig)
    reverse_proxy: ReverseProxyConfig = field(default_factory=ReverseProxyConfig)
    static_files: StaticFilesConfig = field(default_factory=StaticFilesConfig)


@dataclass
class SubdomainRoutingConfig:
    """Subdomain-based routing configuration."""
    enabled: bool = True
    pattern: str = "{service}-{type}.{domain}"


@dataclass
class PathRoutingConfig:
    """Path-based routing configuration."""
    enabled: bool = True
    api_prefix: str = "/api"
    mobile_prefix: str = "/mobile"
    desktop_prefix: str = "/desktop"


@dataclass
class PortRoutingConfig:
    """Port-based routing configuration."""
    enabled: bool = False
    base_domain: str = "localhost"


@dataclass
class RoutingConfig:
    """URL routing strategies configuration."""
    subdomain: SubdomainRoutingConfig = field(default_factory=SubdomainRoutingConfig)
    path: PathRoutingConfig = field(default_factory=PathRoutingConfig)
    port: PortRoutingConfig = field(default_factory=PortRoutingConfig)


@dataclass
class ProjectHealthConfig:
    """Project health check configuration."""
    enabled: bool = True
    check_services: List[str] = field(default_factory=lambda: ["api", "frontend"])
    timeout: str = "10s"


@dataclass
class MonitoringConfig:
    """Monitoring configuration."""
    enabled: bool = True
    health_check_path: str = "/health"
    health_check_interval: str = "30s"
    project_health: ProjectHealthConfig = field(default_factory=ProjectHealthConfig)


@dataclass
class RateLimitingConfig:
    """Rate limiting configuration."""
    enabled: bool = True
    requests_per_minute: int = 100
    burst_size: int = 20


@dataclass
class CORSConfig:
    """CORS configuration."""
    enabled: bool = True
    allowed_origins: List[str] = field(default_factory=lambda: ["*"])
    allowed_methods: List[str] = field(default_factory=lambda: ["GET", "POST", "PUT", "DELETE", "OPTIONS"])
    allowed_headers: List[str] = field(default_factory=lambda: ["*"])


@dataclass
class SecurityConfig:
    """Security configuration."""
    rate_limiting: RateLimitingConfig = field(default_factory=RateLimitingConfig)
    cors: CORSConfig = field(default_factory=CORSConfig)
    headers: List[str] = field(default_factory=lambda: [
        "X-Frame-Options DENY",
        "X-Content-Type-Options nosniff",
        "X-XSS-Protection 1; mode=block",
        "Referrer-Policy strict-origin-when-cross-origin",
    ])


@dataclass
class LogRotationConfig:
    """Log rotation configuration."""
    enabled: bool = True
    retention_days: int = 30
    compress: bool = True


@dataclass
class LoggingConfig:
    """Logging configuration."""
    access_log: str = "/var/log/nginx/fleet_access.log"
    error_log: str = "/var/log/nginx/fleet_error.log"
    format: str = "combined"
    rotation: LogRotationConfig = field(default_factory=LogRotationConfig)


@dataclass
class InfrastructureConfig:
    """Aggregated infrastructure configuration."""
    shared_environments: SharedEnvironmentsConfig = field(default_factory=SharedEnvironmentsConfig)
    frontend_orchestration: FrontendOrchestrationConfig = field(default_factory=FrontendOrchestrationConfig)
    unified_server: UnifiedServerConfig = field(default_factory=UnifiedServerConfig)
    routing: RoutingConfig = field(default_factory=RoutingConfig)
    monitoring: MonitoringConfig = field(default_factory=MonitoringConfig)
    security: SecurityConfig = field(default_factory=SecurityConfig)
    logging: LoggingConfig = field(default_factory=LoggingConfig)


@dataclass
class DomainConfig:
    """Per-project domain mapping (production + optional dev/staging).

    ``downloads`` covers projects whose downloads/product site lives on a
    domain distinct from their primary app domain.
    """

    prod: Optional[str] = None
    dev: Optional[str] = None
    downloads: Optional[str] = None


@dataclass
class SegaConfig:
    """
    Central SEGA configuration.

    Consolidates all configuration for SEGA including:
    - All portfolio projects with computed ports
    - Instance assignments
    - Telemetry backend integration
    - Distribution and packaging configuration
    - Code protection configuration
    - Signing configuration
    - Configuration metadata

    Example usage:
        config = get_config()

        # Get a project
        atlas = config.get_project("atlas")
        print(atlas.api_port)  # 8000

        # Get instance for deployment
        instance = config.get_instance_for_project("atlas")
        print(instance.ip)  # 203.0.113.10

        # Get all projects for an instance
        projects = config.get_projects_for_instance("prod-01")

        # Get packaging configuration
        print(config.packaging.desktop.enabled)  # True

        # Get protection configuration
        print(config.protection.python.tool)  # nuitka

        # Check if the telemetry reporter is excluded in standalone builds
        print(config.distribution.exclusions.telemetry_reporter)  # True
    """
    meta: MetaConfig = field(default_factory=MetaConfig)
    instances: Dict[str, InstanceConfig] = field(default_factory=dict)
    projects: Dict[str, ProjectConfig] = field(default_factory=dict)
    domains: Dict[str, DomainConfig] = field(default_factory=dict)
    telemetry: TelemetryConfig = field(default_factory=TelemetryConfig)
    distribution: DistributionConfig = field(default_factory=DistributionConfig)
    protection: ProtectionConfig = field(default_factory=ProtectionConfig)
    packaging: PackagingConfig = field(default_factory=PackagingConfig)
    signing: SigningConfig = field(default_factory=SigningConfig)
    infrastructure: InfrastructureConfig = field(default_factory=InfrastructureConfig)
    build: BuildConfig = field(default_factory=BuildConfig)
    critical_projects: List[str] = field(default_factory=list)
    fleet: FleetConfig = field(default_factory=FleetConfig)
    secrets: SecretsMappingConfig = field(default_factory=SecretsMappingConfig)
    # Per-engine deployment registry (the `[engines.<name>]` tables): image,
    # ports, capabilities, resources, env, endpoint URL templates, host pools.
    # Kept as raw dicts (heterogeneous per-engine keys). Ships EMPTY.
    engines: Dict[str, Dict] = field(default_factory=dict)
    network: NetworkFleetConfig = field(default_factory=NetworkFleetConfig)
    ship: ShipProductionConfig = field(default_factory=ShipProductionConfig)
    credentials: CredentialsConfig = field(default_factory=CredentialsConfig)

    def get_project(self, name: str) -> Optional[ProjectConfig]:
        """Get project configuration by name"""
        return self.projects.get(name.lower())

    def get_instance(self, name: str) -> Optional[InstanceConfig]:
        """Get instance configuration by name"""
        return self.instances.get(name)

    def get_instance_for_project(self, project_name: str) -> Optional[InstanceConfig]:
        """Get the instance that hosts a given project (None if local/not served)"""
        project = self.get_project(project_name)
        if not project:
            return None

        # deployment_target is either a reserved keyword (local/not_served) or an
        # instance name; resolve it directly against the config-driven instances.
        return self.instances.get(project.deployment_target)

    def get_domain(self, project_name: str, env: str = "prod") -> Optional[str]:
        """Get the configured domain for a project.

        Args:
            project_name: Name of the project.
            env: "prod" (default) or "dev"/"staging".

        Returns:
            The domain string, or None if the project has no configured domain.
        """
        domain = self.domains.get(project_name.lower())
        if not domain:
            return None
        return domain.dev if env in ("dev", "staging") else domain.prod

    def get_projects_for_instance(self, instance_name: str) -> List[ProjectConfig]:
        """Get all projects deployed to a specific instance"""
        instance = self.instances.get(instance_name)
        if not instance:
            return []

        return [
            self.projects[name]
            for name in instance.projects
            if name in self.projects
        ]

    def get_served_projects(self) -> List[ProjectConfig]:
        """Get all projects that are served (deployed to EC2)"""
        return [p for p in self.projects.values() if p.is_served]

    def get_local_projects(self) -> List[ProjectConfig]:
        """Get all projects that run locally only"""
        return [
            p for p in self.projects.values()
            if p.deployment_target in DeploymentTarget.RESERVED
        ]

    def get_projects_by_engine_type(self, engine_type: EngineType) -> List[ProjectConfig]:
        """Get all projects with a specific engine type"""
        return [p for p in self.projects.values() if p.engine_type == engine_type]

    def get_shared_modules_project(self) -> Optional[str]:
        """Name of the project hosting the shared frontend/IDE modules layout.

        Derived from the ``has_shared_frontend_modules`` capability flag
        (first configured project with the flag set, in config order).
        """
        for p in self.projects.values():
            if p.has_shared_frontend_modules:
                return p.name
        return None

    def to_dict(self) -> Dict:
        """Convert entire config to dictionary for backward compatibility"""
        return {
            "meta": {
                "version": self.meta.version,
                "config_path": self.meta.config_path,
            },
            "instances": {
                name: inst.to_dict() for name, inst in self.instances.items()
            },
            "projects": {
                name: proj.to_dict() for name, proj in self.projects.items()
            },
            "telemetry": {
                "api_port": self.telemetry.api_port,
                "metrics_port": self.telemetry.metrics_port,
                "tcp_protobuf_port": self.telemetry.tcp_protobuf_port,
                "enabled": self.telemetry.enabled,
            },
        }

    # Backward compatibility methods for existing code
    def get_project_port(self, project_name: str, port_type: str = "api") -> Optional[int]:
        """
        Get a specific port for a project.

        Backward compatible method for code expecting dict-style access.

        Args:
            project_name: Name of the project
            port_type: Type of port (api, frontend, database, redis, metrics, etc.)

        Returns:
            Port number or None if project not found
        """
        project = self.get_project(project_name)
        if not project:
            return None

        ports = project.ports
        return getattr(ports, port_type, None)

    def get_instance_ip(self, project_name: str) -> Optional[str]:
        """
        Get the IP address for a project's deployment instance.

        Backward compatible method for deployment commands.
        """
        instance = self.get_instance_for_project(project_name)
        return instance.ip if instance else None
