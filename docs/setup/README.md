# SEGA Setup

One-time installation and configuration procedures.

| Document | Purpose |
|----------|---------|
| [installation.md](installation.md) | SEGA core installation |
| [shared-node-modules.md](shared-node-modules.md) | Shared Node.js dependencies |
| [shared-python-venv.md](shared-python-venv.md) | Shared Python environment |

## Quick Start

```bash
# 1. Install SEGA
curl -sSL https://install.example.com/sega_install | bash
source ~/fleet/activate_sega.sh

# 2. Configure system
sega install detect
sega install target --target <type>
sega install validate

# 3. Verify
sega doctor check
```

See [installation.md](installation.md) for detailed instructions.
