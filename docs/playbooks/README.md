# SEGA Playbooks

Step-by-step operational procedures for common workflows.

| Playbook | Purpose |
|----------|---------|
| [01-dev-infrastructure](01-dev-infrastructure.md) | Instance setup and project dev environment |
| [02-sync-monitoring](02-sync-monitoring.md) | Multi-system sync and monitoring |
| [03-local-testing](03-local-testing.md) | Local testing (shared → docker) |
| [04-packaging](04-packaging.md) | Build and package products |
| [05-production-deploy](05-production-deploy.md) | Deploy production infrastructure |
| [06-product-launch](06-product-launch.md) | Launch consumer packages |
| [07-production-testing](07-production-testing.md) | Production validation |

## Related Documentation

| Document | Purpose |
|----------|---------|
| [TESTING_PROCEDURE.md](../reference/TESTING_PROCEDURE.md) | Full 8-level testing procedure with all commands |
| [SEGA_TESTING_FRAMEWORK.md](../development/SEGA_TESTING_FRAMEWORK.md) | Testing framework architecture |
| [cli-reference.md](../reference/cli-reference.md) | All CLI command options |

## Usage

Run playbooks in sequence for full workflows, or individually as needed.

**First-time setup**: 01 → 02 → 03
**Release cycle**: 03 → 04 → 05 → 06 → 07
