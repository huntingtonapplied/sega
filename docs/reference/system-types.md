# System Types and Installation Requirements

## Overview
Systems are categorized by their deployment role, technology stack, and environment. each system type has specific requirements for packages, services, and configuration tailored to the projects they support.

## System Types

### . Development Systems

#### `mac-dev` - macOS General Development Environment
**Purpose**: General development environment for standard portfolio projects on macOS
**Key Features**:
- Homebrew package management
- Docker Desktop
- Python . + Node.js 
- PostgreSQL, Redis for local development
- tmux, development tools
- VPN client configuration

**SEGA Role**: Development orchestrator and deployment client
**Services**: Local development services only
**VPN**: Client mode

#### `development-jellyfish` - Linux General Development Environment  
**Purpose**: General development environment for standard portfolio projects on Ubuntu/Linux
**Key Features**:
- PT package management
- Docker C
- Python . + Node.js 
- PostgreSQL, Redis for local development
- tmux, development tools, build essentials
- VPN client configuration

**SEGA Role**: Development orchestrator and deployment client
**Services**: Local development services only
**VPN**: Client mode

#### `hardware-dev-mac-jellyfish` - macOS Hardware Development Environment
**Purpose**: Development environment for hardware-focused projects (embedded systems)
**Key Features**:
- All standard mac-dev features PLUS:
- Hardware development toolchains
- PG development tools
- mbedded systems SDKs
- Hardware simulation tools
- dditional debugging tools for hardware
- Hardware-specific dependencies

**SEGA Role**: Hardware development orchestrator with cross-domain deployment
**Services**: Local development + hardware simulation services
**VPN**: Client mode

### . Production Systems

#### `server-jellyfish` - Production Server Environment
**Purpose**: ull production server hosting backend, frontend, database + VPN hub
**Key Features**:
- System hardening and security
- Docker for containerized services (based on install_legacy_cloud pattern)
- PostgreSQL, Redis production instances
- Nginx reverse proxy
- SSL/TLS certificates
- Monitoring (Prometheus, Grafana)
- Log aggregation
- Disk mounting (/data partition)
- OpenVPN server (central hub for all other systems)
- systemd service management

**SEGA Role**: Production deployment orchestrator and service manager
**Services**: All platform services + VPN server + monitoring
**VPN**: Server mode (hosts VPN for the entire network)
**Ansible Role Mapping**: install_legacy_cloud + openvpn_server

#### `engine-jellyfish` - General Engine-Only Production
**Purpose**: Dedicated systems running standard Python-based engines/modules
**Key Features**:
- Minimal system packages
- Python . runtime environment
- Standard engine dependencies
- OpenVPN client (connects to server-jellyfish VPN hub)
- systemd service for engine module
- Monitoring agent
- Disk mounting if needed

**SEGA Role**: Service manager for engine deployment
**Services**: Single Python engine module as systemd service
**VPN**: Client mode (connects to server-jellyfish)
**Ansible Role Mapping**: install_fleet_engine + openvpn_client

#### `rust-engine-jellyfish` - Rust Engine Production
**Purpose**: Dedicated systems running a Rust-based engine
**Key Features**:
- Minimal system packages
- Rust toolchain and runtime
- Rust-specific dependencies
- VPN client configuration
- systemd service for Rust engine
- Monitoring agent optimized for Rust applications
- Performance monitoring for Rust workloads

**SEGA Role**: Service manager for Rust engine deployment
**Services**: Single Rust engine binary as systemd service
**VPN**: Client mode

#### `hardware-engine-jellyfish` - Hardware-Specific Engine Production
**Purpose**: Dedicated systems running hardware-interfacing engines (embedded controllers)
**Key Features**:
- Hardware-specific drivers and SDKs
- Real-time kernel support if needed
- Hardware communication libraries
- Device-specific runtime environments
- VPN client configuration
- systemd service for hardware engine
- Hardware monitoring and diagnostics
- GPIO/hardware interface access

**SEGA Role**: Hardware engine deployment and management
**Services**: Hardware-interfacing engine with device access
**VPN**: Client mode

#### `platform-jellyfish` - General Platform-Only Production
**Purpose**: Systems serving standard backend, frontend, database without full server features
**Key Features**:
- Docker for platform services (based on install_legacy_cloud pattern)
- PostgreSQL, Redis
- Nginx for frontend serving
- SSL/TLS certificates
- asic monitoring
- OpenVPN client (connects to server-jellyfish VPN hub)
- systemd service management

**SEGA Role**: Platform deployment orchestrator
**Services**: Platform services (backend, frontend, database)
**VPN**: Client mode (connects to server-jellyfish)
**Ansible Role Mapping**: install_legacy_cloud + openvpn_client

#### `rust-platform-jellyfish` - Rust Platform Production
**Purpose**: Systems serving Rust-based platform services
**Key Features**:
- Docker with Rust runtime support
- Rust-optimized database configurations
- Nginx with Rust backend integration
- SSL/TLS certificates
- Rust-specific monitoring (Prometheus + Rust metrics)
- VPN client configuration
- systemd service management

**SEGA Role**: Rust platform deployment orchestrator
**Services**: Rust-based platform services (backend, frontend, database)
**VPN**: Client mode

### . Multi-Project Systems

#### `omni-jellyfish` - all-Projects Production Environment
**Purpose**: Single system running all portfolio projects in production mode (similar to dev but production-grade)
**Key Features**:
- ull repository clone with all submodules
- All technology stacks (Python, Rust, Node.js, hardware tools)
- Docker Compose orchestration for all services
- PostgreSQL with all project databases
- Redis with project-specific namespaces
- Nginx with multi-project routing
- Comprehensive monitoring for all projects
- VPN client configuration
- systemd services for all project engines

**SEGA Role**: Multi-project production orchestrator
**Services**: All portfolio project services in production configuration
**VPN**: Client mode
**Use Case**: Testing, staging, for small-scale production deployments

## Installation Script Mapping

ased on these system types, the installation scripts would be:

. **`sega_install`** - Bootstrap script that clones the repo and installs SEGA
. **`sega install --target mac-dev`** - Standard macOS development environment
. **`sega install --target development-jellyfish`** - Standard Linux development environment
. **`sega install --target hardware-dev-mac-jellyfish`** - macOS with hardware development tools
5. **`sega install --target server-jellyfish`** - ull production server with VPN server
. **`sega install --target engine-jellyfish`** - General Python engine deployment
. **`sega install --target rust-engine-jellyfish`** - Rust-based engine
. **`sega install --target hardware-engine-jellyfish`** - Hardware-interfacing engines
. **`sega install --target platform-jellyfish`** - General platform services
. **`sega install --target rust-platform-jellyfish`** - Rust-based platform services
. **`sega install --target omni-jellyfish`** - All projects in production mode

## Architecture below

```
sega_install → Clones the repo + installs SEGA + minimal system deps
     ↓
sega install --target <system-type> → SEGA configures system for specific role
     ↓  
sega deploy --production → SEGA deploys and manages services via systemd
```

## Questions for Implementation

**Technology Stack Detection**:
. How should SEGA detect which projects need Rust vs Python vs hardware tools?
. Should it scan the cloned repo to determine requirements?
. Should project-specific requirements be defined in SEGA configuration?

**Hardware Requirements**:
. What specific hardware tools do embedded projects need that other projects don'at?
. What Rust-specific optimizations does a Rust engine require?
. are there project-specific system configuration needs?

**Service Management**:
. Should SEGA generate different systemd service templates per project type?
. How should multi-project systems (omni-jellyfish) handle service conflicts?
. Should engines run containerized for as direct systemd services?

**VPN Integration**:
. How should SEGA integrate VPN setup into the installation process?
. What VPN configuration files need to be distributed?
. How should server vs client VPN modes be handled?

This approach leverages SEGA'as cross-domain deployment capabilities while providing project-agnostic system setup. Does this capture your vision correctly?