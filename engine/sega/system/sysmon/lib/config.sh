#!/bin/bash
# ============================================================================
# SYSMON - Configuration
# ============================================================================
# Centralized configuration for instances, paths, and thresholds
# All values can be overridden via environment variables
# ============================================================================

# Prevent double-sourcing
[[ -n "${SYSMON_CONFIG_LOADED:-}" ]] && return 0
SYSMON_CONFIG_LOADED=1

# ============================================================================
# VERSION
# ============================================================================

SYSMON_VERSION="1.0.0"

# ============================================================================
# EC2 INSTANCE CONFIGURATION
# ============================================================================

# SSH Key path (override with SYSMON_SSH_KEY; injected from [instances] in
# config/sega.toml when invoked via the sega CLI)
SYSMON_SSH_KEY="${SYSMON_SSH_KEY:-}"

# Instance 1 Configuration (Group 1 + Group 4 temporary)
INSTANCE1_IP="${SYSMON_INSTANCE1_IP:-}"
INSTANCE1_NAME="Instance 1 (Group 1 + Group 4 temp)"
INSTANCE1_USER="${SYSMON_INSTANCE1_USER:-ubuntu}"

# Instance 2 Configuration (Group 2)
INSTANCE2_IP="${SYSMON_INSTANCE2_IP:-}"
INSTANCE2_NAME="Instance 2 (Group 2)"
INSTANCE2_USER="${SYSMON_INSTANCE2_USER:-ubuntu}"

# Instance 3 Configuration (Group 3)
INSTANCE3_IP="${SYSMON_INSTANCE3_IP:-}"
INSTANCE3_NAME="Instance 3 (Group 3)"
INSTANCE3_USER="${SYSMON_INSTANCE3_USER:-ubuntu}"

# Instance 4 Configuration (Group 4 - TBD)
INSTANCE4_IP="${SYSMON_INSTANCE4_IP:-}"
INSTANCE4_NAME="Instance 4 (Group 4 - TBD)"
INSTANCE4_USER="${SYSMON_INSTANCE4_USER:-ubuntu}"

# SSH Options
SSH_CONNECT_TIMEOUT="${SYSMON_SSH_TIMEOUT:-5}"
SSH_OPTS="-o ConnectTimeout=${SSH_CONNECT_TIMEOUT} -o StrictHostKeyChecking=no -o LogLevel=ERROR -o BatchMode=yes"

# Project groups per instance (space-separated; injected from [instances] in
# config/sega.toml when invoked via the sega CLI)
INSTANCE1_PROJECTS="${SYSMON_INSTANCE1_PROJECTS:-}"
INSTANCE2_PROJECTS="${SYSMON_INSTANCE2_PROJECTS:-}"
INSTANCE3_PROJECTS="${SYSMON_INSTANCE3_PROJECTS:-}"
INSTANCE4_PROJECTS="${SYSMON_INSTANCE4_PROJECTS:-}"

# ============================================================================
# PATH CONFIGURATION
# ============================================================================

# FLEET ecosystem paths
FLEET_DIR="${FLEET_DIR:-${HOME}/fleet}"
FLEET_DATA_DIR="${FLEET_DATA_DIR:-${FLEET_DIR}/data}"
FLEET_PRESERVE_DIR="${SYSMON_PRESERVE_DIR:-${HOME}/fleet-preserves}"
FLEET_ENVIRONMENTS_DIR="${FLEET_ENVIRONMENTS_DIR:-${FLEET_DIR}/environments}"

# Output paths
SYSMON_OUTPUT_DIR="${SYSMON_OUTPUT_DIR:-/tmp}"
SYSMON_LOG_FILE="${SYSMON_LOG_FILE:-${SYSMON_OUTPUT_DIR}/sysmon.log}"

# ============================================================================
# THRESHOLD CONFIGURATION
# ============================================================================

# Disk usage thresholds (percentage)
DISK_WARNING_THRESHOLD="${SYSMON_DISK_WARNING:-75}"
DISK_CRITICAL_THRESHOLD="${SYSMON_DISK_CRITICAL:-90}"

# CPU usage thresholds (percentage)
CPU_WARNING_THRESHOLD="${SYSMON_CPU_WARNING:-70}"
CPU_CRITICAL_THRESHOLD="${SYSMON_CPU_CRITICAL:-90}"

# Memory usage thresholds (percentage)
MEM_WARNING_THRESHOLD="${SYSMON_MEM_WARNING:-80}"
MEM_CRITICAL_THRESHOLD="${SYSMON_MEM_CRITICAL:-95}"

# Large file threshold (bytes) - default 100MB
LARGE_FILE_THRESHOLD="${SYSMON_LARGE_FILE:-104857600}"

# ============================================================================
# CLEANUP TARGETS
# ============================================================================

# Build artifacts to clean
BUILD_ARTIFACT_PATTERNS=(
    ".next"
    "build"
    "dist"
    "__pycache__"
)

# Optional cleanup targets (require explicit flag)
OPTIONAL_CLEANUP_PATTERNS=(
    "node_modules"
)

# Docker cleanup targets
DOCKER_CLEANUP_PHASES=(
    "dangling_images"
    "stopped_containers"
    "build_cache"
)

# ============================================================================
# DISPLAY CONFIGURATION
# ============================================================================

# Dashboard table limits
MAX_DOCKER_CONTAINERS="${SYSMON_MAX_CONTAINERS:-15}"
MAX_TOP_PROCESSES="${SYSMON_MAX_PROCESSES:-7}"
MAX_LARGE_FILES="${SYSMON_MAX_LARGE_FILES:-10}"
MAX_TOP_DIRECTORIES="${SYSMON_MAX_DIRECTORIES:-20}"

# ============================================================================
# ANIMATED MODE CONFIGURATION
# ============================================================================

# Enable animated output mode (override with --animate flag)
SYSMON_ANIMATE="${SYSMON_ANIMATE:-false}"

# Refresh interval for animated mode (seconds)
SYSMON_REFRESH_INTERVAL="${SYSMON_REFRESH_INTERVAL:-3}"

# Minimum and maximum refresh intervals
SYSMON_MIN_INTERVAL=1
SYSMON_MAX_INTERVAL=60

# Show detailed view by default in animated mode
SYSMON_DETAILED="${SYSMON_DETAILED:-false}"

# Focus mode: "all", "1", "2", "3", "4", "local"
SYSMON_FOCUS="${SYSMON_FOCUS:-all}"

# History length for sparklines (number of data points)
SYSMON_SPARKLINE_HISTORY=10

# ============================================================================
# HELPER FUNCTIONS
# ============================================================================

# Get SSH command for an instance
get_ssh_cmd() {
    local instance="$1"  # "1", "2", "3", or "4"
    local ip user

    case "$instance" in
        1|instance1)
            ip="$INSTANCE1_IP"
            user="$INSTANCE1_USER"
            ;;
        2|instance2)
            ip="$INSTANCE2_IP"
            user="$INSTANCE2_USER"
            ;;
        3|instance3)
            ip="$INSTANCE3_IP"
            user="$INSTANCE3_USER"
            ;;
        4|instance4)
            ip="$INSTANCE4_IP"
            user="$INSTANCE4_USER"
            ;;
        *)
            echo "Invalid instance: $instance" >&2
            return 1
            ;;
    esac

    # Check if IP is configured
    if [[ -z "$ip" ]]; then
        echo "Instance $instance IP not configured: set SYSMON_INSTANCE<N>_IP or configure [instances] in config/sega.toml (injected automatically via the sega CLI)" >&2
        return 1
    fi

    # Check if SSH key is configured
    if [[ -z "$SYSMON_SSH_KEY" ]]; then
        echo "SSH key not configured: set SYSMON_SSH_KEY or configure [instances] in config/sega.toml (injected automatically via the sega CLI)" >&2
        return 1
    fi

    echo "ssh -i \"$SYSMON_SSH_KEY\" $SSH_OPTS ${user}@${ip}"
}

# Get instance name by number
get_instance_name() {
    local instance="$1"
    case "$instance" in
        1|instance1) echo "$INSTANCE1_NAME" ;;
        2|instance2) echo "$INSTANCE2_NAME" ;;
        3|instance3) echo "$INSTANCE3_NAME" ;;
        4|instance4) echo "$INSTANCE4_NAME" ;;
        *) echo "Unknown" ;;
    esac
}

# Get instance IP by number
get_instance_ip() {
    local instance="$1"
    case "$instance" in
        1|instance1) echo "$INSTANCE1_IP" ;;
        2|instance2) echo "$INSTANCE2_IP" ;;
        3|instance3) echo "$INSTANCE3_IP" ;;
        4|instance4) echo "$INSTANCE4_IP" ;;
        *) echo "" ;;
    esac
}

# Get projects for an instance
get_instance_projects() {
    local instance="$1"
    case "$instance" in
        1|instance1) echo "$INSTANCE1_PROJECTS" ;;
        2|instance2) echo "$INSTANCE2_PROJECTS" ;;
        3|instance3) echo "$INSTANCE3_PROJECTS" ;;
        4|instance4) echo "$INSTANCE4_PROJECTS" ;;
        *) echo "" ;;
    esac
}

# Get all configured instances (returns space-separated list)
get_all_instances() {
    local instances=""
    # Only include instances whose IP is configured
    [[ -n "$INSTANCE1_IP" ]] && instances="$instances 1"
    [[ -n "$INSTANCE2_IP" ]] && instances="$instances 2"
    [[ -n "$INSTANCE3_IP" ]] && instances="$instances 3"
    [[ -n "$INSTANCE4_IP" ]] && instances="$instances 4"
    echo "${instances# }"
}

# Check if SSH key exists
check_ssh_key() {
    if [[ -z "$SYSMON_SSH_KEY" ]]; then
        log_error "SSH key not configured"
        log_info "Set SYSMON_SSH_KEY or configure [instances] in config/sega.toml (injected automatically via the sega CLI)"
        return 1
    fi
    if [[ ! -f "$SYSMON_SSH_KEY" ]]; then
        log_error "SSH key not found: $SYSMON_SSH_KEY"
        log_info "Set SYSMON_SSH_KEY environment variable or place key at default location"
        return 1
    fi
    return 0
}

# Get status color based on threshold
get_status_color() {
    local value="$1"
    local warning="$2"
    local critical="$3"

    # Extract numeric part
    local num="${value%\%}"
    num="${num%%.*}"

    if [[ "$num" -ge "$critical" ]]; then
        echo "critical"
    elif [[ "$num" -ge "$warning" ]]; then
        echo "warning"
    else
        echo "ok"
    fi
}

# Get status text
get_status_text() {
    local value="$1"
    local warning="$2"
    local critical="$3"
    local status

    status=$(get_status_color "$value" "$warning" "$critical")

    case "$status" in
        critical) echo "CRITICAL" ;;
        warning)  echo "WARNING" ;;
        ok)       echo "OK" ;;
    esac
}
