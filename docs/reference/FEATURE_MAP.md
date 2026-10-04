# SEGA Feature Map

**Last Updated**: 2025-12-15 (command consolidation: forge, ship, probe, doctor expansion)
**Purpose**: Comprehensive mapping of SEGA features to their codebase locations
**Audience**: Developers, maintainers, and contributors

---

## Quick Navigation

| Section | Description |
|---------|-------------|
| [CLI Commands](#1-cli-commands) | All available CLI commands |
| [Command Groups](#consolidated-command-groups) | New action-first command structure |
| [System Utilities](#14-system-utilities-operational) | sysmon, sysnc |
| [Command Consolidation](#16-command-consolidation-implemented) | forge, ship, probe, doctor |
| [Engine Restructure](#17-engine-restructure-implemented) | Domain-based architecture (implemented) |

**Related Documentation**:
- [CLI Reference](cli-reference.md) - Detailed command usage

---

## Overview

This document provides a complete reference of SEGA's capabilities and their implementation locations. Use this as your primary navigation guide when working with the SEGA codebase.

**Core Principle**: Actions are commands, platforms are options.

---

## 1. CLI Commands

All CLI commands are implemented in `engine/sega/cli/commands/`.

### Consolidated Command Groups

| Command | File | Description |
|---------|------|-------------|
| `sega forge` | `forge.py` | Build, package & distribute (consolidates desktop/mobile/frontend) |
| `sega ship` | `ship.py` | Deployment lifecycle (consolidates deploy/rollback) |
| `sega probe` | `probe.py` | Test orchestration (consolidates all test commands) |
| `sega doctor` | `doctor.py` | Diagnostics & repair (expanded with subcommands) |

### Established Command Groups

| Command | File | Description |
|---------|------|-------------|
| `sega local` | `local.py` | Local development lifecycle |
| `sega infrastructure` | `infrastructure.py` | Infrastructure provisioning |
| `sega secrets` | `secrets.py` | Secrets management |
| `sega sysmon` | `sysmon.py` | System monitoring |
| `sega sysnc` | `sysnc.py` | Multi-system git sync |

### Standalone Commands

| Command | File | Description |
|---------|------|-------------|
| `sega local` | `local.py` | Local development orchestration (up/down/status/logs) |
| `sega infrastructure` | `infrastructure.py` | Infrastructure provisioning (vpn, engine, runner, network) |
| `sega secrets` | `secrets.py` | GitLab CI/CD secrets management |
| `sega install` | `install.py` | System installation and configuration |
| `sega detect` | `detect.py` | Project type auto-detection |
| `sega init` | `init.py` | Project initialization and scaffolding |
| `sega flash` | `flash.py` | Firmware flashing to devices |
| `sega program` | `program.py` | FPGA bitstream programming |
| `sega nginx` | `nginx.py` | Nginx configuration management and SSL validation |
| `sega monitor` | `monitor.py` | Real-time monitoring |
| `sega logs` | `logs.py` | Log viewing and aggregation |
| `sega workspace` | `workspace.py` | Workspace management |
| `sega unified-server` | `unified_server.py` | Unified development server |
| `sega ledger` | `ledger.py` | Project ledger operations |
| `sega fleet` | `fleet.py` | Fleet-wide operations |
| `sega api` | `api.py` | API server management |
| `sega grpc` | `grpc.py` | gRPC service management |
| `sega project` | `project.py` | Project management |
| `sega social` | `social.py` | Social/secrets integration |
| `sega sysmon` | `sysmon.py` | System monitoring (disk, memory, Docker, EC2) |
| `sega sysnc` | `sysnc.py` | Multi-system git synchronization |
| `sega validate` | `validate.py` | Dockerfile/deployment configuration validation |
| `sega health` | `health.py` | Service health endpoint checking |

---

## 2. Deployers

Platform-specific deployment engines in `engine/sega/ship/deployers/`.

| Deployer | File | Target Platform |
|----------|------|-----------------|
| Base Deployer | `base_deployer.py` | Abstract interface for all deployers |
| Deployment Router | `deployment_router.py` | Intelligent deployment target selection |
| Ansible | `ansible_deployer.py` | Configuration management deployments |
| Kubernetes | `k8s_deployer.py` | K8s cluster deployments via kubectl/helm |
| AWS ECS | `ecs_deployer.py` | AWS ECS container deployments |
| ECS v2 | `ecs_deployer_v2.py` | Enhanced ECS with advanced features |
| Mobile | `mobile_deployer.py` | iOS/Android app deployment |
| Desktop | `desktop_deployer.py` | Electron multi-platform deployment |
| FPGA | `fpga_deployer.py` | FPGA bitstream deployment |
| Multi-Region | `multi_region_deployer.py` | Cross-region AWS deployments |

**Subdirectories**:
- `ecs/` - ECS-specific utilities and configurations

---

## 3. Testing Framework

Testing infrastructure in `engine/sega/probe/`.

> **Usage Guide**: See [TESTING_PROCEDURE.md](TESTING_PROCEDURE.md) for step-by-step testing commands.

| Component | File | Capability |
|-----------|------|------------|
| Browser Test Runner | `browser_test_runner.py` | Playwright E2E, visual regression, a11y |
| Enhanced Browser | `enhanced_browser_runner.py` | 3-tier validation (static/dynamic/integration) |
| API Test Runner | `api_test_runner.py` | OpenAPI validation, endpoint testing |
| Backend Test Runners | `backend_test_runners.py` | Unit/integration test execution |
| Engine Test Runner | `engine_test_runner.py` | Hardware/simulation engine testing |
| Enhanced Engine | `enhanced_engine_test_runner.py` | Advanced engine validation |
| Unified Test Runner | `unified_test_runner.py` | Multi-type test orchestration |
| Test Aggregator | `test_aggregator.py` | Results consolidation and reporting |
| Test Orchestrator | `test_orchestrator.py` | Parallel test execution |
| Config Handler | `config_handler.py` | Project-specific test configuration |
| Dependency Resolver | `dependency_resolver.py` | Test dependency management |
| Build Tool Manager | `build_tool_manager.py` | Build system detection and management |
| CLI Entry Detector | `cli_entry_detector.py` | CLI entry point detection |

**Subdirectories**:
- `auth/` - Authentication testing utilities
- `chaining/` - Test chaining and sequencing
- `mobile/` - Mobile-specific test runners
- `openapi/` - OpenAPI validation tools
- `parsers/` - Test output parsers

---

## 4. Core Infrastructure

Core platform components in `engine/sega/core/`.

| Component | File | Purpose |
|-----------|------|---------|
| Parallel Execution | `parallel_execution_manager.py` | Concurrent operation management |
| Resource Manager | `optimized_resource_manager.py` | Resource allocation and optimization |
| Enterprise Orchestrator | `enterprise_orchestrator.py` | Multi-project coordination |
| Error Reporter | `ecosystem_error_reporter.py` | Fleet error reporting standards |
| Template Generator | `template_generator.py` | Project scaffolding |
| Workspace Manager | `workspace_manager.py` | Development environment management |
| Project Ledger | `project_ledger.py` | Project tracking and state |
| Portfolio Manager | `portfolio_manager.py` | Multi-project portfolio management |
| Dependency Injection | `dependency_injection.py` | DI container for services |
| Deployment Result | `deployment_result.py` | Deployment outcome tracking |
| Connection Manager | `enhanced_connection_manager.py` | Service connection management |
| Lazy Command Registry | `lazy_command_registry.py` | CLI command lazy loading |
| Infrastructure Manager | `infrastructure_manager_v2.py` | Infrastructure lifecycle |

**Subdirectories**:
- `infrastructure/` - Infrastructure-specific utilities

---

## 5. Local Development

Local deployment management in `engine/sega/local/`.

| Component | File | Purpose |
|-----------|------|---------|
| Local Deployment Manager | `manager.py` | Docker Compose orchestration, native deployment |
| Shared Infrastructure | `shared_infra.py` | PostgreSQL/Redis/TimescaleDB management |
| Nginx Manager | `nginx.py` | Nginx configuration and reverse proxy |
| Nginx Checker | `nginx_checker.py` | Infrastructure validation (SSL, certbot, domains) |

### Key Features

| Feature | Description |
|---------|-------------|
| `--shared` | Use shared environments (~/portfolio/environments/) |
| `--project-env` | Use project-local environments |
| `--port-offset` | Offset all ports for running multiple instances |
| `--agent-id` | Agent ID for concurrent testing coordination |
| Port Allocation | Per-project port assignments (80XX API, 30XX frontend) |

### Port Offset

The `--port-offset` option enables running multiple instances of the same project simultaneously:

```bash
sega local up -p my-project                    # Standard ports (8010, 3010)
sega local up -p my-project --port-offset 100  # Offset ports (8110, 3110)
```

Environment variables set: `SEGA_PORT_OFFSET`, `PORT_OFFSET`, `PORT`, `API_PORT`

---

## 6. Supporting Modules

### Detectors (`engine/sega/project/`)
Project type detection and analysis.

### Services (`engine/sega/services/`)
Background services and daemons.

### Validation (`engine/sega/doctor/validation/`)
Input and configuration validation.

### Security (`engine/sega/doctor/`)
Security scanning and vulnerability detection.

### Monitoring (`engine/sega/monitoring/`)
Metrics collection and real-time monitoring.

### API (`engine/sega/api/`)
REST API endpoints and FastAPI integration.

### Utils (`engine/sega/utils/`)
Shared utilities (paths, logging, helpers).

### Installation (`engine/sega/installation/`)
System installation and setup routines.

### Workspace (`engine/sega/project/`)
Workspace configuration management.

### Scripts (`scripts/`)
Internal automation scripts.

---

## 7. Infrastructure as Code

### Ansible (`infrastructure/ansible/`)

```
infrastructure/ansible/
├── ansible.cfg                    # Ansible configuration
├── host.ini                       # Inventory file
├── 00-playbook-setup-devops.yml   # DevOps setup playbook
├── 01-playbook-setup-cloud.yml    # Cloud setup playbook
└── roles/
    ├── add_data_volume/           # Data volume mounting
    ├── add_repositories/          # APT repository setup
    ├── add_ssh_keys/              # SSH key deployment
    ├── configure_aws/             # AWS CLI configuration
    ├── configure_debug_node/      # Debug environment setup
    ├── configure_firewall/        # UFW/iptables rules
    ├── configure_hardware_access/ # Hardware permissions
    ├── configure_x310/            # USRP X310 setup
    ├── install_engine/            # Engine deployment
    ├── install_platform/          # Platform deployment
    ├── install_fleet_engine/        # engine deployment (formerly the sensor-net engine role; generalized)
    ├── install_aws/               # AWS tools installation
    ├── install_devops_packages/   # DevOps toolchain
    ├── install_gitlab_runner/     # GitLab runner setup
    ├── install_packages/          # System packages
    ├── install_rust_engine/       # Rust engine deployment
    ├── openvpn_client/            # VPN client setup
    └── openvpn_server/            # VPN server setup
```

### Terraform (`infrastructure/terraform/`)

```
infrastructure/terraform/
├── modules/
│   ├── vpc/                       # VPC networking
│   ├── ecs/                       # ECS cluster (container service)
│   ├── eks/                       # EKS cluster (Kubernetes + GPU nodes)
│   ├── keda/                      # KEDA autoscaling for K8s
│   ├── rds/                       # RDS databases
│   ├── devops/                    # DevOps infrastructure
│   └── aws_full_deployment/       # Complete AWS stack
│       ├── alarms.tf              # CloudWatch alarms
│       ├── dashboard.tf           # CloudWatch dashboard
│       ├── ec2_instance.tf        # EC2 instances
│       ├── network.tf             # Networking
│       └── s3_bucket.tf           # S3 buckets
├── deployments/
│   ├── mcentire/                  # McEntire deployment
│   ├── slava/                     # Slava deployment
│   ├── devops/                    # DevOps deployment
│   ├── ukr/                       # UKR deployment
│   └── benchy/                    # Benchmark deployment
└── aws/ecs/                       # AWS ECS specific
```

**Simulation Orchestration Infrastructure** (EKS + KEDA):

| Module | Purpose | Architecture Reference |
|--------|---------|----------------------|
| `eks/` | GPU-enabled Kubernetes cluster | [K8s Autoscaling Architecture](/docs/architecture/orchestration/KUBERNETES_AUTOSCALING_ARCHITECTURE.md) |
| `keda/` | Event-driven pod autoscaling | [Distributed Job Orchestration](/docs/architecture/orchestration/DISTRIBUTED_JOB_ORCHESTRATION.md) |

These modules provision infrastructure for simulation job orchestration. Projects contain the orchestration code in `common/simulation/orchestrator/`.

### Hardware Build Configuration (`config/hardware-builds.yaml`)

Hardware toolchain build specifications are now consolidated in a single YAML configuration file.

**Components**: engine, gnuradio, custom GNU Radio OOT modules, uhd, volk, openFPGAloader, rfnoc modules, and project-specific toolchain tools

---

## 8. Templates

Project templates in `templates/`.

| Template | Purpose |
|----------|---------|
| `browser/` | Browser testing setup (Playwright configs, validation specs) |
| `desktop/` | Electron application scaffolding |
| `default/` | Default project templates |
| `gitlab-ci/` | CI/CD pipeline templates (composable, modular architecture) |
| `nginx/` | Reverse proxy configurations |
| `systemd/` | Service unit files |

### GitLab CI/CD Templates Architecture

**Design Principle**: Composable modular pipelines. GitLab CI orchestrates WHEN things run; SEGA commands execute WHAT runs. Runners install and execute SEGA.

```
templates/gitlab-ci/
├── core/                          # Shared across all projects
│   ├── validate.yml               # Lint, type check, static analysis
│   └── test.yml                   # Unit, integration, e2e patterns
│
├── deploy/                        # Service deployment (continuous, branch-triggered)
│   ├── docker-registry.yml        # Build + push Docker image to GitLab Registry
│   ├── kubernetes.yml             # K8s/Helm deployment
│   └── ec2-ansible.yml            # EC2 via Ansible
│
└── release/                       # Artifact releases (discrete, tag-triggered)
    ├── _base.yml                  # Common: version tagging, changelog, notifications
    ├── api.yml                    # API container release
    ├── desktop.yml                # Electron (.dmg/.exe/.AppImage)
    ├── cli.yml                    # Binary CLI tools (Python/Rust)
    ├── mobile-ios.yml             # iOS (App Store / TestFlight)
    └── mobile-android.yml         # Android (Play Store)
```

**GitLab CI/CD + SEGA Relationship**:
- GitLab CI/CD: Orchestrates pipelines, manages triggers, artifacts, environments
- SEGA commands: Execute actual build/test/deploy logic on runners
- Runners install SEGA via `curl -sSL .../install | bash`

**Event-Based Activation**:

| Event | Validate | Build | Deploy Staging | Deploy Prod | Release |
|-------|----------|-------|----------------|-------------|---------|
| Push to feature branch | ✅ | ❌ | ❌ | ❌ | ❌ |
| Merge request | ✅ | ✅ | Manual | ❌ | ❌ |
| Push to main branch | ✅ | ✅ | ✅ (auto) | Manual | ❌ |
| Git tag (v*.*.*) | ✅ | ✅ | ✅ | Manual | ✅ (manual) |

**Why Separate Release Templates Per Platform**:

| Concern | Desktop | CLI | Mobile iOS | Mobile Android |
|---------|---------|-----|------------|----------------|
| Build tool | electron-builder | Nuitka/cargo | Xcode/EAS | Gradle/EAS |
| Runner | macOS | Linux | macOS | Linux |
| Signing | Apple + Windows | GPG | Apple Developer | Play signing key |
| Publish | GitHub/S3 | PyPI/GitHub | App Store Connect | Play Console |

**Project Composition Pattern**:
```yaml
# Example: web-app/.gitlab-ci.yml (has API + Desktop)
include:
  - project: 'your-org/sega'
    file:
      - '/templates/gitlab-ci/core/validate.yml'
      - '/templates/gitlab-ci/core/test.yml'
      - '/templates/gitlab-ci/deploy/docker-registry.yml'
      - '/templates/gitlab-ci/release/desktop.yml'

variables:
  PROJECT_NAME: "web-app"
```

---

## 9. Scripts

Automation scripts in `scripts/`.

| Directory | Purpose |
|-----------|---------|
| `testing/frontend-testing/` | Frontend route verification |
| `docker/` | Container build scripts |
| `install/` | System installation scripts |
| `dev/` | Developer utilities |
| `sql/` | Database migrations |

---

## 10. Configuration

### Project Configuration Files

| File | Location | Purpose |
|------|----------|---------|
| `sega.yaml` | Project root | Project-specific SEGA configuration |
| `.sega/laboratory_config.yaml` | Project root | Laboratory integration config |
| `pyproject.toml` | SEGA root | Package configuration (flit-based) |
| `config/port_mapping.yaml` | SEGA config/ | SEGA service port mappings |
| `config/unified_server.yaml` | SEGA config/ | Multi-project unified server config |

### Environment Configuration

| Directory | Purpose |
|-----------|---------|
| `config/` | Infrastructure configuration (port mapping, unified server) |

### Authoritative Infrastructure References

All SEGA configuration files link to these ecosystem-wide standards:

| Document | Path | Purpose |
|----------|------|---------|
| **Port Allocation Standards** | `/docs/standards/infrastructure/PORT_ALLOCATION_STANDARDS.md` | Definitive port assignments for all projects |
| **URL & Addressing Registry** | `/docs/standards/infrastructure/URL_AND_ADDRESSING_REGISTRY.md` | Central URL conventions, ports, paths, callbacks |
| **Domain Registry** | `/docs/architecture/infrastructure/dns/DOMAIN_REGISTRY.md` | Project-to-domain mapping |
| **EC2 Instance Registry** | `/docs/operations/infrastructure/EC2_INSTANCE_REGISTRY.md` | Project-to-instance/IP mapping |

---

## 11. Lifecycle Coverage

| Phase | Status | Primary Components |
|-------|--------|-------------------|
| **Local Testing** | Complete | `local.py`, `local_deployment_manager.py`, `testing/*` |
| **CI/CD Infrastructure** | Complete | `secrets.py`, `templates/gitlab-ci/`, `infrastructure/*` |
| **Consumer Packaging** | **Phase 1 Complete** | `compile.py`, `package.py`, `sign.py`, `protection/*`, `packaging/*`, `signing/*` |
| **Deployment** | Complete | `deployers/*`, `deploy.py`, terraform, ansible |
| **Deployment Testing** | Complete | `browser_test_runner.py`, `api_test_runner.py`, validation tiers |

---

## 12. Consumer Packaging

**Directive**: [SEGA_COMPILE_PACKAGING_DIRECTIVE.md](/sega/docs/plans/SEGA_COMPILE_PACKAGING_DIRECTIVE.md)
**Status**: Phase 1 Complete (compile, package, sign) | Phase 2 Pending (distribute, release)

### CLI Commands

| Command | File | Status | Description |
|---------|------|--------|-------------|
| `sega compile` | `compile.py` | **Complete** | Compile source to protected binaries (Nuitka, Bytenode, JS Obfuscator) |
| `sega package` | `package.py` | **Complete** | Package for desktop/mobile/IDE/extension platforms |
| `sega sign` | `sign.py` | **Complete** | Code signing (macOS, Windows, Linux) |
| `sega sign-list` | `sign.py` | **Complete** | List available signing identities/keys |
| `sega distribute` | `distribute.py` | Planned | Upload to S3/registry/store |
| `sega release` | `release.py` | Planned | Orchestrates compile → package → sign → distribute |

### Protection Module (`engine/sega/forge/protection/`) - Implemented

| Component | File | Purpose | Tool |
|-----------|------|---------|------|
| Nuitka | `nuitka.py` | Python → standalone binary | Nuitka |
| Bytenode | `bytenode.py` | Node.js → V8 bytecode | bytenode |
| JS Obfuscator | `jsobfuscator.py` | JavaScript obfuscation | javascript-obfuscator |

**Use Cases by Project Type**:

| Project Type | Python | Node.js Frontend | JS Functions |
|--------------|--------|------------------|--------------|
| Simulation Engines | Nuitka | Bytenode | - |
| Remote Backend (thin clients) | - | Bytenode | - |
| Function Libraries | Nuitka | - | javascript-obfuscator |
| Utility Binaries | Nuitka/Rust | - | - |

### Packaging Module (`engine/sega/forge/packaging/`) - Implemented

| Component | File | Purpose | Tool | Output |
|-----------|------|---------|------|--------|
| Electron | `electron.py` | Desktop apps | electron-builder | .dmg, .exe, .AppImage |
| VS Code IDE | `vscode_ide.py` | Full IDE fork builds | gulp (VS Code build) | Custom IDE |
| VS Code Extension | `vscode_extension.py` | VS Code extensions | vsce | .vsix |

*Note: Mobile (Expo) packaging is handled directly in `package.py` command.*

**Template References**:

| Platform | Template Location | Build System |
|----------|-------------------|--------------|
| Desktop (Electron) | `templates/desktop/electron_base/` | electron-builder |
| IDE (VS Code Fork) | `templates/IDE/vscode/` | gulp |
| Mobile (Expo) | `templates/mobile/` | Expo EAS |

### Signing Module (`engine/sega/forge/signing/`) - Implemented

| Component | File | Purpose |
|-----------|------|---------|
| macOS | `mac.py` | Apple code signing + notarization (codesign, notarytool) |
| Windows | `windows.py` | Authenticode signing (signtool, osslsigncode) |
| Linux | `linux.py` | GPG signing + checksums |

### Distribution Module (`engine/sega/forge/distribution/`) - Planned

| Component | File | Purpose |
|-----------|------|---------|
| S3 | `s3.py` | AWS S3 upload for releases |
| Registry | `registry.py` | Container/package registry uploads |

### Implementation Phases

| Phase | Components | Status |
|-------|------------|--------|
| **Phase 1** | `compile.py`, `protection/*`, `package.py`, `packaging/*`, `sign.py`, `signing/*` | **COMPLETE** |
| **Phase 2** | `distribute.py`, `distribution/*`, `release.py` | Pending |
| **Phase 3** | CI/CD templates in `templates/gitlab-ci/` (see [Templates Architecture](#gitlab-cicd-templates-architecture)) | Pending |

### CLI Commands (Phase 1)

| Command | File | Description |
|---------|------|-------------|
| `sega compile` | `commands/compile.py` | Compile source to protected binaries (Nuitka, Bytenode, JS Obfuscator) |
| `sega package` | `commands/package.py` | Package for desktop/mobile/IDE/extension platforms |
| `sega sign` | `commands/sign.py` | Code signing (macOS codesign, Windows signtool, Linux GPG) |
| `sega sign-list` | `commands/sign.py` | List available signing identities/keys |

---

## 13. Test Suite

Test files in `tests/`.

| Test File | Coverage |
|-----------|----------|
| `test_browser_framework.py` | Browser testing infrastructure |
| `test_optimization_integration.py` | Optimization features |
| `test_project_detector.py` | Project detection |
| `BROWSER_TESTING_VALIDATION_REPORT.md` | Browser test validation |
| `REAL_WORLD_VERIFICATION_RESULTS.md` | Real-world test results |

**Test Count**: 298 comprehensive tests

---

## 14. Entry Points

| Entry Point | Location | Purpose |
|-------------|----------|---------|
| CLI | `engine/sega/__main__.py` | Main CLI entry (`sega` command) |
| CLI Main | `engine/sega/cli/main.py` | Click group and command registration |
| Package | `engine/sega/__init__.py` | Package initialization |

---

## 15. System Utilities

System monitoring and multi-instance synchronization utilities integrated from `utilities/`.

### CLI Commands

| Command | File | Description |
|---------|------|-------------|
| `sega sysmon` | `commands/sysmon.py` | System monitoring for local and EC2 instances |
| `sega sysnc` | `commands/sysnc.py` | Multi-system git synchronization |

### sysmon Subcommands

| Subcommand | Description |
|------------|-------------|
| `sega sysmon status` | Quick status check (disk, memory, Docker, sessions) |
| `sega sysmon analyze` | Deep disk analysis with cleanup recommendations |
| `sega sysmon dashboard` | Multi-instance overview with 4-table layout |
| `sega sysmon projects` | Project-based metrics dashboard |
| `sega sysmon cleanup docker` | Docker cleanup (dangling images, stopped containers, cache) |
| `sega sysmon cleanup builds` | Build artifact cleanup (.next, dist, __pycache__) |
| `sega sysmon report` | Generate markdown or JSON reports |

### sysnc Subcommands

| Subcommand | Description |
|------------|-------------|
| `sega sysnc inspect` | Inspect changes across all 3 systems |
| `sega sysnc analyze` | Analyze 3-way conflicts before consolidation |
| `sega sysnc run` | Execute consolidation workflow (stash-pull-pop-push) |
| `sega sysnc bulk` | Run bulk sync on current system |
| `sega sysnc settings` | Sync Claude settings to EC2 instances |

### Embedded Scripts

Scripts are embedded in `engine/sega/system/` for self-contained operation:

```
engine/sega/system/
├── sysmon/           # System monitoring scripts
│   ├── sysmon        # Main dispatcher
│   ├── lib/          # Shared libraries (common, config, collectors)
│   └── commands/     # Command implementations
└── sysnc/            # Synchronization scripts
    ├── bulk-stash-pull-pop-push.sh
    ├── analyze-3way-conflicts.py
    ├── inspect-ec2-changes*.sh
    └── consolidate-with-submodules.sh
```

### Configuration

| Config | Location | Purpose |
|--------|----------|---------|
| EC2 Instances | `engine/sega/infrastructure/ec2_config.py` | Instance IPs, projects, SSH config |
| Port Standards | `/docs/standards/infrastructure/PORT_ALLOCATION_STANDARDS.md` | Authoritative port assignments |
| EC2 Registry | `/docs/operations/infrastructure/EC2_INSTANCE_REGISTRY.md` | Full instance documentation |

---

## Quick Reference

### Finding Implementation

```
Feature needed → Check this location
─────────────────────────────────────
CLI command      → engine/sega/cli/commands/{command}.py
Deployer         → engine/sega/ship/deployers/{platform}_deployer.py
Test runner      → engine/sega/probe/runners/{type}_test_runner.py
Core service     → engine/sega/core/{service}.py
Protection       → engine/sega/forge/protection/{tool}.py
Packaging        → engine/sega/forge/packaging/{platform}.py
Signing          → engine/sega/forge/signing/{os}.py
Distribution     → engine/sega/forge/distribution/{target}.py (planned)
System utilities → engine/sega/system/{sysmon,sysnc}/
EC2 config       → engine/sega/infrastructure/ec2_config.py
IaC (Ansible)    → infrastructure/ansible/roles/{role}/
IaC (Terraform)  → infrastructure/terraform/modules/{module}/
Templates        → templates/{type}/
```

### Adding New Features

1. **New CLI command**: Create `engine/sega/cli/commands/{name}.py`, register in `cli/main.py`
2. **New deployer**: Extend `base_deployer.py` in `engine/sega/ship/deployers/`
3. **New test type**: Create runner in `engine/sega/probe/runners/`
4. **New protection tool**: Add to `engine/sega/forge/protection/`
5. **New packaging platform**: Add to `engine/sega/forge/packaging/`
6. **New Ansible role**: Add to `infrastructure/ansible/roles/`
7. **New Terraform module**: Add to `infrastructure/terraform/modules/`

---

## 16. Command Consolidation (Implemented)

**Status**: Implemented | 2025-12-15
**Core Principle**: Actions are commands, platforms are options.

### New Command Groups

| Command | Purpose | Consolidates |
|---------|---------|--------------|
| `sega forge` | Build, package & distribute | `desktop`, `mobile`, `frontend`, `compile`, `package`, `sign`, `distribute` |
| `sega ship` | Deployment lifecycle | `deploy`, `rollback`, `status` |
| `sega probe` | Test orchestration | `test`, `test_api`, `test_browser`, `test_local`, `test_enhanced` |
| `sega doctor` | Diagnostics & repair | `doctor`, `optimize`, `scan`, `optimization_status` |

### `sega forge` - Build, Package & Distribute

```
sega forge
├── build       --platform desktop|mobile|web|api
├── dev         --platform desktop|mobile|web
├── compile     --lang python|node|js|rust
├── package     --platform desktop|mobile|cli|extension
├── sign        --os mac|windows|linux
├── publish     --target instance|s3|github|appstore|playstore|registry
└── release     --platform <> --target <>  (full workflow)
```

**Implementation**: `engine/sega/cli/commands/forge.py` → `engine/sega/forge/`

### `sega ship` - Deployment Lifecycle

```
sega ship
├── deploy      --platform api|web --target staging|production --strategy rolling|blue-green|canary
├── rollback    --version|--steps
├── status      --watch
├── promote     (staging → production)
└── validate    (health checks)
```

**Implementation**: `engine/sega/cli/commands/ship.py` → `engine/sega/ship/`

### `sega probe` - Test Orchestration

```
sega probe
├── run         --platform desktop|mobile|web|api --type unit|integration|e2e
├── unit
├── integration
├── e2e         --project <project> --flow <flow-name>
├── api         --spec <openapi.yaml>
├── browser     --visual|--a11y|--perf
├── domain      --test-localhost --instance 1|2|3
├── scan        --dashboard|--report --all|--project <name>
├── coverage
└── benchmark
```

**Implementation**: `engine/sega/cli/commands/probe.py` → `engine/sega/probe/`

**New in v1.8 (2026-01-07)**: `sega probe scan` - Console error scanning and status dashboard

| Subcommand | Purpose | Mode |
|------------|---------|------|
| `scan --dashboard` | Fast HTTP status checks (2-3s for all projects) | Lightweight |
| `scan --report` | Deep Playwright console scanning (60-90s) | Comprehensive |

**Files**:
- `probe/console_message.py` - Message processing, truncation, deduplication
- `probe/console_scanner.py` - Playwright-based scanning engine
- `probe/status_dashboard.py` - HTTP-based status checks
- `probe/scan_reporter.py` - Markdown & JSON report generation

**Integration**: Reuses existing `probe/domain_test_runner.py` for domain URL building

### `sega doctor` - Diagnostics & Repair (Expanded)

```
sega doctor
├── check       (quick health check)
├── diagnose    --deps|--config|--network
├── repair      (auto-fix issues)
├── optimize    --analyze
├── scan        --type deps|secrets|code
└── report      (generate health report)
```

**Implementation**: `engine/sega/cli/commands/doctor.py` → `engine/sega/doctor/`

### Command Migration Reference

| Old Command | New Command |
|-------------|-------------|
| `sega desktop build` | `sega forge build --platform desktop` |
| `sega mobile build` | `sega forge build --platform mobile` |
| `sega frontend build` | `sega forge build --platform web` |
| `sega compile` | `sega forge compile` |
| `sega package` | `sega forge package` |
| `sega sign` | `sega forge sign` |
| `sega deploy` | `sega ship deploy` |
| `sega rollback` | `sega ship rollback` |
| `sega status` | `sega ship status` |
| `sega test` | `sega probe run` |
| `sega test_api` | `sega probe api` |
| `sega test_browser` | `sega probe browser` |
| `sega doctor` | `sega doctor check` |
| `sega optimize` | `sega doctor optimize` |
| `sega scan` | `sega doctor scan` |

### Commands Unchanged

| Command Group | Reason |
|---------------|--------|
| `sega local` | Already action-oriented |
| `sega infrastructure` | Infrastructure provisioning scope |
| `sega secrets` | Secrets management scope |
| `sega sysmon` | System monitoring scope |
| `sega sysnc` | Synchronization scope |

---

## 17. Engine Restructure (Implemented)

**Status**: Implemented | **Date**: 2025-12-15
**Plan Document**: [ENGINE_RESTRUCTURE_PLAN.md](../architecture/ENGINE_RESTRUCTURE_PLAN.md)

### Overview

SEGA has migrated from flat `src/sega/` layout to domain-based `engine/sega/` architecture:
- Separates CLI commands from implementation
- Organizes implementation by CLI command groups
- Follows a standard Python engine pattern (reference implementation)

### Current Structure

```
sega/
└── engine/sega/
    ├── cli/                    # CLI Layer (separate)
    │   ├── main.py             # Click group, logging, DI
    │   └── commands/           # All CLI command modules
    │
    ├── local/                  # sega local implementation
    ├── forge/                  # sega forge (protection, packaging, signing)
    ├── ship/                   # sega ship (deployers, strategies)
    ├── probe/                  # sega probe (test runners)
    ├── doctor/                 # sega doctor (health, validation)
    ├── infrastructure/         # sega infrastructure (vpn, cloud)
    ├── secrets/                # sega secrets (gitlab, social)
    ├── system/                 # sega sysmon + sysnc
    │
    ├── project/                # Shared: detection, ledger, workspace
    ├── core/                   # Shared: DI, config, logging
    ├── services/               # Shared: platform services, systemd
    ├── api/                    # REST/gRPC
    └── utils/                  # Utilities
```

### CLI-to-Domain Mapping

| CLI Command | CLI Location | Implementation |
|-------------|--------------|----------------|
| `sega local` | `cli/commands/local.py` | `local/` |
| `sega forge` | `cli/commands/forge.py` | `forge/` (protection, packaging, signing, distribution) |
| `sega ship` | `cli/commands/ship.py` | `ship/` (deployers, strategies) |
| `sega probe` | `cli/commands/probe.py` | `probe/` (runners, mobile, chaining) |
| `sega doctor` | `cli/commands/doctor.py` | `doctor/` (health, repair, validation) |
| `sega infrastructure` | `cli/commands/infrastructure.py` | `infrastructure/` (vpn, cloud) |
| `sega secrets` | `cli/commands/secrets.py` | `secrets/` |
| `sega sysmon`/`sysnc` | `cli/commands/sysmon.py`, `sysnc.py` | `system/` |

### Benefits

- **CLI-aligned**: Package structure matches command groups
- **Discoverable**: `sega forge` implementation in `forge/`
- **Testable**: Each domain independently testable
- **Consistent**: Matches the standard engine layout

---

## Related Documentation

### SEGA Documentation
- [CLI Reference](cli-reference.md) - Command usage details
- [CLAUDE.md](../CLAUDE.md) - AI context and integration patterns
- [sega.yaml Specification](sega-yaml-spec.md) - Configuration format
- [Project Types](project-types.md) - Supported project types

### Orchestration Architecture (Authoritative)
- **[Orchestration Overview](/docs/architecture/orchestration/README.md)** - Scope and applicable projects
- **[Kubernetes Autoscaling Architecture](/docs/architecture/orchestration/KUBERNETES_AUTOSCALING_ARCHITECTURE.md)** - EKS + KEDA + GPU autoscaling
- **[Distributed Job Orchestration](/docs/architecture/orchestration/DISTRIBUTED_JOB_ORCHESTRATION.md)** - Job distribution patterns, queue management

**Note**: SEGA provisions the infrastructure (Terraform modules `eks/`, `keda/`). Projects contain the orchestration code in `common/simulation/orchestrator/`.

### Deployment Standards
- [SEGA Integration Standards](/docs/standards/deployment/SEGA_INTEGRATION_STANDARDS.md) - SEGA deployment patterns

---

*This document is the authoritative reference for SEGA's codebase structure. Update it when adding new features or reorganizing code.*
