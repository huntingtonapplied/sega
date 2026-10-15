# 01: Dev Infrastructure Setup

Setup development environment on a new instance or local machine.

## Instance Setup (EC2/Server)

```bash
# 1. Install SEGA
curl -sSL https://install.example.com/sega_install | bash
source ~/fleet/activate_sega.sh

# 2. Detect and configure system type
sega install detect
sega install target --target <detected-type>
sega install validate

# 3. Verify installation
sega doctor check
```

## Project Dev Setup

```bash
# 1. Start shared infrastructure
sega local up

# 2. Verify services
sega local status

# 3. Setup shared dependencies (optional, for non-docker dev)
cd ~/fleet/environments
./setup_shared_node_modules.sh
./setup_shared_venv.sh
```

## Project-Specific Setup

```bash
# 1. Navigate to project
cd ~/fleet/<project>

# 2. Install project dependencies
make install  # or: npm install / pip install -e .

# 3. Start project
make dev      # shared mode
# or
make up       # docker mode
```

## Verification

```bash
sega local status           # All services healthy
sega doctor check           # No issues
curl localhost:<port>/health  # Project responding
```
