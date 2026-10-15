#!/bin/bash
# =============================================================================
# build-landing-apps.sh
# Builds all development landing apps using shared node_modules
#
# Usage:
#   ./scripts/build-landing-apps.sh                  # build all
#   ./scripts/build-landing-apps.sh atlas hermes    # build specific projects
#
# Requires: <workspace-root>/environments/landing_app/ with package.json + package-lock.json
# =============================================================================

set -eo pipefail

FLEET_ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
SHARED_DIR="$FLEET_ROOT/environments/landing_app"
COMPOSE_FILE="$(cd "$(dirname "$0")/.." && pwd)/config/docker-compose.landing-apps.yml"

# All development landing app projects
ALL_PROJECTS=(
  atlas
  hermes
  orion
)

# Use provided args or default to all
if [ $# -gt 0 ]; then
  PROJECTS=("$@")
else
  PROJECTS=("${ALL_PROJECTS[@]}")
fi

echo "=============================================="
echo "Landing App Build"
echo "Workspace root: $FLEET_ROOT"
echo "Shared deps: $SHARED_DIR"
echo "Projects:    ${PROJECTS[*]}"
echo "=============================================="

# -----------------------------------------------------------------------------
# Step 1: Install shared node_modules (skip if already installed)
# -----------------------------------------------------------------------------
echo ""
echo "[1/3] Checking shared node_modules..."

if [ ! -f "$SHARED_DIR/node_modules/.bin/next" ]; then
  echo "  Installing shared node_modules in $SHARED_DIR..."
  cd "$SHARED_DIR"
  npm ci --legacy-peer-deps
  echo "  Done."
else
  echo "  Shared node_modules already installed, skipping."
fi

# -----------------------------------------------------------------------------
# Step 2: Build each project using shared node_modules
# -----------------------------------------------------------------------------
echo ""
echo "[2/3] Building landing apps..."

FAILED=()

for proj in "${PROJECTS[@]}"; do
  LANDING_DIR="$FLEET_ROOT/$proj/frontend/landing_app"

  if [ ! -d "$LANDING_DIR" ]; then
    echo "  SKIP $proj - no frontend/landing_app directory"
    continue
  fi

  echo ""
  echo "  Building $proj..."

  # Symlink shared node_modules into project
  if [ -L "$LANDING_DIR/node_modules" ]; then
    rm "$LANDING_DIR/node_modules"
  elif [ -d "$LANDING_DIR/node_modules" ]; then
    echo "  WARNING: $proj has real node_modules dir, renaming to node_modules.bak"
    mv "$LANDING_DIR/node_modules" "$LANDING_DIR/node_modules.bak"
  fi

  ln -s "$SHARED_DIR/node_modules" "$LANDING_DIR/node_modules"

  # Build (run in subshell so set -e doesn't abort the outer script on failure)
  if (cd "$LANDING_DIR" && npm run build); then
    echo "  OK $proj"
  else
    echo "  FAILED $proj"
    FAILED+=("$proj")
  fi

  # Remove symlink after build (ignore errors - may already be gone)
  rm -f "$LANDING_DIR/node_modules"
done

# -----------------------------------------------------------------------------
# Step 3: Build Docker images and start containers (only successfully built)
# -----------------------------------------------------------------------------
echo ""
echo "[3/3] Building Docker images and starting containers..."

# Build service names from successfully built projects
SERVICES=()
for proj in "${PROJECTS[@]}"; do
  # Skip failed projects
  failed=0
  for f in "${FAILED[@]}"; do
    [ "$proj" = "$f" ] && failed=1 && break
  done
  [ "$failed" -eq 1 ] && continue
  # Convert project name to service name (my_project -> my-project-landing)
  svc=$(echo "$proj" | tr '_' '-')
  SERVICES+=("${svc}-landing")
done

if [ ${#SERVICES[@]} -eq 0 ]; then
  echo "No projects built successfully, skipping Docker step."
else
  docker compose -f "$COMPOSE_FILE" up --build -d "${SERVICES[@]}"
fi

echo ""
echo "=============================================="
if [ ${#FAILED[@]} -eq 0 ]; then
  echo "All builds complete."
else
  echo "WARNING: The following projects failed to build:"
  for f in "${FAILED[@]}"; do
    echo "  - $f"
  done
fi
echo ""
echo "Running containers:"
docker compose -f "$COMPOSE_FILE" ps
echo "=============================================="
