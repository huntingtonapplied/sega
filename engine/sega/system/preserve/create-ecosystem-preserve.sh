#!/bin/bash
# Universal Ecosystem Preserve Creator
# Creates a timestamped archive of any directory/ecosystem
# Automatically detects and uses zip or tar.gz based on availability
# Excludes: node_modules, .git, venv, build artifacts, existing backups
#
# Usage:
#   ./create-ecosystem-preserve.sh [path]
#
# Arguments:
#   path    Optional. Directory to preserve. Defaults to ~/fleet
#
# Examples:
#   ./create-ecosystem-preserve.sh                    # Preserves ~/fleet
#   ./create-ecosystem-preserve.sh ~/devuser        # Preserves ~/devuser
#   ./create-ecosystem-preserve.sh /path/to/project   # Preserves any project

set -e

# Configuration
# Use provided path or default to FLEET
if [ -n "$1" ]; then
    SOURCE_ROOT="$(cd "$1" 2>/dev/null && pwd)" || {
        echo "Error: Cannot access directory: $1"
        exit 1
    }
else
    SOURCE_ROOT="${HOME}/fleet"
fi

# Derive preserve directory and naming from source
SOURCE_NAME=$(basename "$SOURCE_ROOT")
PRESERVE_DIR="${HOME}/${SOURCE_NAME}-preserves"
TIMESTAMP=$(date +"%Y%m%d-%H%M%S")

# Detect compression tool (zip preferred, tar.gz fallback)
# NOTE: zip commented out - uses too much memory and gets OOM killed
# if command -v zip >/dev/null 2>&1; then
#     COMPRESS_TOOL="zip"
#     PRESERVE_NAME="${SOURCE_NAME}-preserve-${TIMESTAMP}.zip"
#     PRESERVE_PATH="${PRESERVE_DIR}/${PRESERVE_NAME}"
# else
COMPRESS_TOOL="tar"
PRESERVE_NAME="${SOURCE_NAME}-preserve-${TIMESTAMP}.tar.gz"
PRESERVE_PATH="${PRESERVE_DIR}/${PRESERVE_NAME}"
# fi

# Exclusion patterns
EXCLUSIONS=(
    # Version control
    ".git"

    # Node/JavaScript
    "node_modules"
    ".npm"
    ".pnpm"
    ".yarn"
    "package-lock.json.backup*"
    "node_modules.backup*"

    # Python
    "venv"
    ".venv"
    "env"
    "__pycache__"
    ".pytest_cache"
    ".mypy_cache"
    ".ruff_cache"
    "fleet_venv"
    "backend_venv"
    "engine_venv"
    # Non-standard venv names present in fleet/environments (distribution_venv,
    # simtest_venv, cli_venv, test_venv, backend_venv_313, ...)
    "*_venv"
    "*_venv_*"
    "backend_venv_*"
    "*.pyc"

    # Coverage
    "htmlcov"
    "coverage"
    ".nyc_output"

    # Package backup files
    "package.json.backup*"
    "package-lock.json.backup*"

    # Build artifacts
    "build"
    "dist"
    "dist-electron"
    ".next"
    ".turbo"
    "out"
    "target"
    # Renamed rust target dirs (e.g. environments/target-telemetry-reporter)
    "target-*"
    "*.tsbuildinfo"
    ".nuxt"
    "squashfs-root"

    # IDE build artifacts
    "node_modules_ide"
    # VS Code / IDE-desktop build output (atlas/ide/.build) + scratch trees
    ".build"
    "*-ide-desktop-scratch"
    "*-scratch"

    # Agent worktrees — regenerable git-worktree checkouts (atlas/.claude/worktrees)
    "worktrees"

    # Mobile / Expo / native build artifacts (expo apps: ios/Pods, android/.gradle, .expo)
    ".expo"
    ".expo-shared"
    "Pods"
    ".gradle"
    ".cxx"
    "DerivedData"

    # Backup directories
    ".backups"
    ".corruption_backups"
    ".sentinel_backups"
    "backup_*"
    "*_backup_*"
    "*.backup"
    "*.backup_*"
    "*.boxbak"

    # Staging directories - commented out, too broad (excludes source code)
    # Build artifacts inside frontends are caught by node_modules/.next/build patterns
    # "integration_staging/*/frontend"
    # "integration_staging/*/*/frontend"

    # MongoDB data
    "data/journal"
    "data/diagnostic.data"
    "WiredTiger*"

    # Temporary files
    "tmp"
    ".tmp"
    "temp"
    ".cache"
    ".npm-cache"

    # IDE/Editor
    ".vscode"
    ".idea"

    # OS files
    ".DS_Store"
    "Thumbs.db"

    # Logs
    "logs"
    "*.log"
)

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Functions
log_info() {
    echo -e "${BLUE}ℹ${NC} $1"
}

log_success() {
    echo -e "${GREEN}✅${NC} $1"
}

log_warning() {
    echo -e "${YELLOW}⚠️${NC} $1"
}

log_error() {
    echo -e "${RED}❌${NC} $1"
}

# Create preserve directory if it doesn't exist
if [ ! -d "$PRESERVE_DIR" ]; then
    log_info "Creating preserve directory: $PRESERVE_DIR"
    mkdir -p "$PRESERVE_DIR"
fi

# Check if source directory exists
if [ ! -d "$SOURCE_ROOT" ]; then
    log_error "Source directory not found: $SOURCE_ROOT"
    exit 1
fi

# Display header
echo ""
echo "================================================"
echo "Ecosystem Preserve Creator"
echo "================================================"
log_info "Compression: $COMPRESS_TOOL"
log_info "Timestamp: $TIMESTAMP"
log_info "Source: $SOURCE_ROOT"
log_info "Destination: $PRESERVE_PATH"
echo ""

# Display what will be excluded
log_info "Excluding the following patterns:"
echo "  - Version control (.git)"
echo "  - Node modules (node_modules, .npm, .pnpm, .yarn)"
echo "  - Python virtual environments (venv, .venv, *_venv, __pycache__)"
echo "  - Build artifacts (build, dist, .next, target, target-*, .build, .turbo)"
echo "  - Agent worktrees + scratch trees (worktrees, *-scratch)"
echo "  - Mobile/Expo native builds (.expo, Pods, .gradle, .cxx, DerivedData)"
echo "  - Coverage reports (htmlcov, coverage, .nyc_output)"
echo "  - Backup directories (.backups, .corruption_backups, .sentinel_backups)"
echo "  - Package backup files (package.json.backup*, package-lock.json.backup*)"
echo "  - Staging frontend copies (integration_staging/*/frontend)"
echo "  - MongoDB data files (data/journal, WiredTiger*)"
echo "  - Temporary files and caches"
echo "  - IDE/Editor configs (.vscode, .idea)"
echo "  - OS files (.DS_Store, Thumbs.db)"
echo "  - Log files"
echo ""

# Create the preserve
log_info "Creating preserve archive (this may take a few minutes)..."

if [ "$COMPRESS_TOOL" = "zip" ]; then
    # Build exclusion arguments for zip
    EXCLUDE_ARGS=()
    for pattern in "${EXCLUSIONS[@]}"; do
        EXCLUDE_ARGS+=("-x" "*/${pattern}/*" "*/${pattern}")
    done

    cd "$(dirname "$SOURCE_ROOT")"
    if zip -r -q "$PRESERVE_PATH" "$(basename "$SOURCE_ROOT")" "${EXCLUDE_ARGS[@]}"; then
        SUCCESS=true
    else
        SUCCESS=false
    fi
else
    # Build exclusion arguments for tar
    EXCLUDE_ARGS=()
    for pattern in "${EXCLUSIONS[@]}"; do
        EXCLUDE_ARGS+=("--exclude=${pattern}")
    done

    if tar "${EXCLUDE_ARGS[@]}" -czf "$PRESERVE_PATH" -C "$(dirname "$SOURCE_ROOT")" "$(basename "$SOURCE_ROOT")"; then
        SUCCESS=true
    else
        SUCCESS=false
    fi
fi

# Report results
if [ "$SUCCESS" = true ]; then
    echo ""
    log_success "Preserve created successfully!"

    # Get preserve size
    PRESERVE_SIZE=$(du -h "$PRESERVE_PATH" | cut -f1)

    echo ""
    echo "================================================"
    echo "Preserve Details"
    echo "================================================"
    echo "Format:   $COMPRESS_TOOL"
    echo "Name:     $PRESERVE_NAME"
    echo "Location: $PRESERVE_PATH"
    echo "Size:     $PRESERVE_SIZE"
    echo ""

    # Count existing preserves
    PRESERVE_COUNT=$(ls -1 "$PRESERVE_DIR"/${SOURCE_NAME}-preserve-*.{zip,tar.gz} 2>/dev/null | wc -l)
    log_info "Total preserves in $PRESERVE_DIR: $PRESERVE_COUNT"

    # Warn if too many preserves
    if [ "$PRESERVE_COUNT" -gt 10 ]; then
        log_warning "You have $PRESERVE_COUNT preserves. Consider cleaning old preserves:"
        echo "    ls -t $PRESERVE_DIR/${SOURCE_NAME}-preserve-*.{zip,tar.gz} 2>/dev/null | tail -n +11 | xargs rm -f"
    fi

    echo ""
    log_success "Preserve complete!"

    # Return preserve path for scripting
    echo "$PRESERVE_PATH"
else
    log_error "Failed to create preserve"
    exit 1
fi
