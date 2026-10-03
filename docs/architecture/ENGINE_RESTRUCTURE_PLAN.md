# SEGA Engine Restructure Plan

**Status**: Implemented | **Date**: 2025-12-15
**Author**: Architecture Review
**Reference**: Standard Python engine pattern (reference implementation)

---

## Overview

This document outlines the restructure of SEGA from a flat `src/sega/` layout to a domain-based `engine/sega/` architecture that:
- Separates CLI commands from implementation
- Organizes implementation by CLI command groups
- Follows a standard Python engine pattern

---

## Current Structure

```
sega/
├── src/sega/                    # All code in flat structure
│   ├── __init__.py
│   ├── __main__.py              # CLI entry point + all setup
│   ├── commands/                # 50+ CLI commands (mixed concerns)
│   ├── deployers/               # Scattered from ship commands
│   ├── deployment/              # Mixed local + ship concerns
│   ├── testing/                 # Probe implementation
│   ├── protection/              # Forge implementation
│   ├── packaging/               # Forge implementation
│   ├── signing/                 # Forge implementation
│   ├── distribution/            # Forge implementation
│   ├── validation/              # Doctor implementation
│   ├── security/                # Doctor implementation
│   ├── infrastructure/          # Infrastructure implementation
│   ├── cloud/                   # Infrastructure implementation
│   ├── detectors/               # Project detection
│   ├── core/                    # Shared utilities
│   ├── services/                # Shared services
│   ├── system/                  # sysmon, sysnc scripts
│   ├── api/                     # REST/gRPC
│   └── utils/                   # Utilities
├── pyproject.toml
└── tests/
```

**Issues with Current Structure**:
- Commands mixed with implementation logic
- No clear domain boundaries
- Difficult to find implementation for a command group
- Doesn't follow the standard engine layout

---

## Target Structure

Organized by CLI command groups with separated CLI layer:

```
sega/
├── engine/
│   ├── pyproject.toml
│   └── sega/
│       ├── __init__.py
│       ├── __main__.py          # Slim entry point → cli.main
│       │
│       ├── cli/                 # CLI Layer (SEPARATE)
│       │   ├── __init__.py
│       │   ├── main.py          # Click group, logging, DI setup
│       │   └── commands/        # All CLI command modules
│       │       ├── __init__.py
│       │       ├── local.py
│       │       ├── forge.py
│       │       ├── ship.py
│       │       ├── probe.py
│       │       ├── doctor.py
│       │       ├── infrastructure.py
│       │       ├── secrets.py
│       │       ├── sysmon.py
│       │       ├── sysnc.py
│       │       └── ... (standalone commands)
│       │
│       ├── local/               # sega local implementation
│       │   ├── __init__.py
│       │   ├── manager.py       # LocalDeploymentManager
│       │   ├── shared_infra.py  # SharedInfrastructureManager
│       │   └── nginx.py         # NginxManager
│       │
│       ├── forge/               # sega forge implementation
│       │   ├── __init__.py
│       │   ├── protection/      # Nuitka, Bytenode, JS-Obfuscator
│       │   ├── packaging/       # Electron, Expo, VS Code
│       │   ├── signing/         # macOS, Windows, Linux
│       │   └── distribution/    # S3, registries
│       │
│       ├── ship/                # sega ship implementation
│       │   ├── __init__.py
│       │   ├── service.py       # DeploymentService
│       │   ├── registry.py      # RegistryDeployer
│       │   ├── production.py    # ProductionSetup
│       │   ├── deployers/       # Platform deployers
│       │   │   ├── base.py
│       │   │   ├── docker.py
│       │   │   ├── k8s.py
│       │   │   ├── ansible.py
│       │   │   ├── ecs.py
│       │   │   └── router.py
│       │   └── strategies/      # Rolling, blue-green, canary
│       │
│       ├── probe/               # sega probe implementation
│       │   ├── __init__.py
│       │   ├── orchestrator.py  # TestOrchestrator
│       │   ├── runners/
│       │   │   ├── unit.py
│       │   │   ├── integration.py
│       │   │   ├── browser.py
│       │   │   ├── api.py
│       │   │   └── engine.py
│       │   ├── mobile/          # iOS/Android testing
│       │   └── chaining/        # Test data chaining
│       │
│       ├── doctor/              # sega doctor implementation
│       │   ├── __init__.py
│       │   ├── health.py
│       │   ├── repair.py
│       │   ├── security.py
│       │   └── validation/
│       │
│       ├── infrastructure/      # sega infrastructure implementation
│       │   ├── __init__.py
│       │   ├── ec2_config.py
│       │   ├── vpn_manager.py
│       │   ├── engine_deployer.py
│       │   ├── runner_manager.py
│       │   ├── network_orchestrator.py
│       │   └── cloud/           # AWS/Terraform
│       │
│       ├── secrets/             # sega secrets implementation
│       │   ├── __init__.py
│       │   ├── gitlab.py
│       │   └── social.py
│       │
│       ├── system/              # sega sysmon + sysnc
│       │   ├── __init__.py
│       │   ├── sysmon/          # Bash scripts
│       │   └── sysnc/           # Bash scripts
│       │
│       ├── project/             # Project detection & management
│       │   ├── __init__.py
│       │   ├── detector.py
│       │   ├── ledger.py
│       │   └── workspace.py
│       │
│       ├── core/                # Shared cross-cutting
│       │   ├── __init__.py
│       │   ├── di.py
│       │   ├── config.py
│       │   └── logging.py
│       │
│       ├── services/            # Shared services
│       │   ├── __init__.py
│       │   └── fleet_service.py
│       │
│       ├── api/                 # REST/gRPC
│       │   └── __init__.py
│       │
│       └── utils/               # Shared utilities
│           └── __init__.py
│
├── tests/                       # Unchanged location
├── docs/
├── infrastructure/              # Ansible, Terraform, K8s
├── scripts/
└── config/
```

---

## CLI Command Group to Domain Mapping

| CLI Command | Domain Package | Purpose |
|-------------|----------------|---------|
| `sega local` | `local/` | Local development lifecycle (up, down, status, logs) |
| `sega forge` | `forge/` | Build, compile, package, sign, publish, release |
| `sega ship` | `ship/` | Deploy, rollback, status, promote, validate |
| `sega probe` | `probe/` | Test orchestration (run, unit, e2e, browser, api) |
| `sega doctor` | `doctor/` | Diagnostics (check, diagnose, repair, optimize, scan) |
| `sega infrastructure` | `infrastructure/` | VPN, engine, runner, network provisioning |
| `sega secrets` | `secrets/` | GitLab CI/CD secrets management |
| `sega sysmon` | `system/` | System monitoring |
| `sega sysnc` | `system/` | Multi-system git synchronization |

**Shared Packages** (used across multiple domains):
- `project/` - Project detection, ledger, workspace
- `core/` - Dependency injection, config, logging
- `services/` - Platform services, systemd service
- `api/` - REST/gRPC endpoints
- `utils/` - Common utilities

---

## Module Migration Map

### local/ Domain
| Current | New |
|---------|-----|
| `deployment/local_deployment_manager.py` | `local/manager.py` |
| `deployment/enhanced_local_deployment_manager.py` | `local/enhanced_manager.py` |
| `deployment/shared_infrastructure.py` | `local/shared_infra.py` |
| `commands/nginx.py` (NginxManager) | `local/nginx.py` |

### forge/ Domain
| Current | New |
|---------|-----|
| `protection/*` | `forge/protection/` |
| `packaging/*` | `forge/packaging/` |
| `signing/*` | `forge/signing/` |
| `distribution/*` | `forge/distribution/` |

### ship/ Domain
| Current | New |
|---------|-----|
| `services/deployment_service.py` | `ship/service.py` |
| `deployment/registry_deployer.py` | `ship/registry.py` |
| `deployment/production_setup.py` | `ship/production.py` |
| `deployers/*` | `ship/deployers/` |

### probe/ Domain
| Current | New |
|---------|-----|
| `testing/*` | `probe/` |

### doctor/ Domain
| Current | New |
|---------|-----|
| `validation/*` | `doctor/validation/` |
| `security/*` | `doctor/security.py` |

### infrastructure/ Domain
| Current | New |
|---------|-----|
| `infrastructure/*` | `infrastructure/` |
| `cloud/*` | `infrastructure/cloud/` |

### secrets/ Domain
| Current | New |
|---------|-----|
| `commands/secrets.py` logic | `secrets/gitlab.py` |
| `commands/social.py` logic | `secrets/social.py` |

### system/ Domain
| Current | New |
|---------|-----|
| `system/sysmon/*` | `system/sysmon/` |
| `system/sysnc/*` | `system/sysnc/` |

### Shared Packages
| Current | New |
|---------|-----|
| `detectors/*` | `project/` |
| `core/*` | `core/` |
| `services/*` | `services/` |
| `api/*` | `api/` |
| `utils/*` | `utils/` |

---

## Import Pattern

Commands import from their corresponding domain package:

```python
# cli/commands/local.py
from ...local.manager import LocalDeploymentManager
from ...local.shared_infra import SharedInfrastructureManager

# cli/commands/ship.py
from ...ship.service import DeploymentService
from ...ship.deployers.router import DeploymentRouter
from ...project.detector import ProjectDetector

# cli/commands/probe.py
from ...probe.orchestrator import TestOrchestrator
from ...probe.runners.browser import BrowserTestRunner
```

---

## pyproject.toml Changes

```toml
[build-system]
requires = ["flit_core >=3.2,<4"]
build-backend = "flit_core.buildapi"

[project]
name = "sega"
# ... rest unchanged

[project.scripts]
sega = "sega.cli.main:cli"

[tool.flit.sdist]
include = [
    "sega/system/sysmon/**/*",
    "sega/system/sysnc/**/*",
]

[tool.flit.module]
name = "sega"
```

---

## Implementation Steps

1. **Create directory structure** - Create all domain directories
2. **Move CLI layer** - Move commands to `cli/commands/`, create `cli/main.py`
3. **Move domains** - Move implementation to domain packages in order:
   - `system/` (simplest, bash scripts)
   - `infrastructure/` (minimal dependencies)
   - `project/` (shared, needed by others)
   - `core/` (shared, needed by others)
   - `local/`
   - `forge/`
   - `ship/`
   - `probe/`
   - `doctor/`
   - `secrets/`
   - `services/`, `api/`, `utils/`
4. **Update imports** - Fix all import statements
5. **Update pyproject.toml** - Point to new entry point
6. **Verify** - Run `sega --version` and `sega doctor check`
7. **Remove old structure** - Delete `src/sega/` after verification

---

## Benefits

1. **CLI-aligned** - Package structure matches documented command groups
2. **Discoverable** - `sega forge` implementation lives in `forge/`
3. **Separated concerns** - CLI layer separate from business logic
4. **Testable** - Each domain independently testable
5. **Consistent** - Matches the standard engine layout
6. **Maintainable** - Clear ownership and boundaries

---

## Rollback Plan

If issues arise:
1. The old `src/sega/` structure remains until final verification
2. `pyproject.toml` can be reverted to point back to `src/sega`
3. Git history preserves all changes for easy revert

---

## Related Documentation

- [Feature Map](../reference/FEATURE_MAP.md) - CLI command documentation
- [CLI Reference](../reference/cli-reference.md) - Command usage
- Reference engine implementation - standard layout example
- [Engine Standards](../../../../docs/standards/development/ENGINE_DOCUMENTATION_FRAMEWORK.md)
