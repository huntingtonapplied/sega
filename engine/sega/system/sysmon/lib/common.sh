#!/bin/bash
# ============================================================================
# SYSMON - Common Library
# ============================================================================
# Shared functions for colors, logging, utilities
# Source this file: source "$(dirname "$0")/lib/common.sh"
# ============================================================================

# Prevent double-sourcing
[[ -n "${SYSMON_COMMON_LOADED:-}" ]] && return 0
SYSMON_COMMON_LOADED=1

# ============================================================================
# TERMINAL DETECTION & COLORS
# ============================================================================

# Detect if stdout is a TTY for safe color handling
if [[ -t 1 ]]; then
    # Standard colors
    RED='\033[0;31m'
    GREEN='\033[0;32m'
    YELLOW='\033[1;33m'
    BLUE='\033[0;34m'
    MAGENTA='\033[0;35m'
    CYAN='\033[0;36m'
    WHITE='\033[0;37m'

    # Bright/light colors
    BRIGHT_RED='\033[91m'
    BRIGHT_GREEN='\033[92m'
    BRIGHT_YELLOW='\033[93m'
    BRIGHT_BLUE='\033[94m'
    BRIGHT_MAGENTA='\033[95m'
    BRIGHT_CYAN='\033[96m'

    # Text styles
    BOLD='\033[1m'
    DIM='\033[2m'
    ITALIC='\033[3m'
    UNDERLINE='\033[4m'
    BLINK='\033[5m'
    REVERSE='\033[7m'

    # Background colors (for alerts)
    BG_RED='\033[41m'
    BG_GREEN='\033[42m'
    BG_YELLOW='\033[43m'
    BG_BLUE='\033[44m'

    # Reset
    NC='\033[0m'  # No Color / Reset
else
    # Disable colors if not a TTY (pipes, redirects, etc.)
    RED='' GREEN='' YELLOW='' BLUE='' MAGENTA='' CYAN='' WHITE=''
    BRIGHT_RED='' BRIGHT_GREEN='' BRIGHT_YELLOW='' BRIGHT_BLUE=''
    BRIGHT_MAGENTA='' BRIGHT_CYAN=''
    BOLD='' DIM='' ITALIC='' UNDERLINE='' BLINK='' REVERSE=''
    BG_RED='' BG_GREEN='' BG_YELLOW='' BG_BLUE=''
    NC=''
fi

# ============================================================================
# LOGGING FUNCTIONS
# ============================================================================

# Log levels: DEBUG < INFO < SUCCESS < WARNING < ERROR
SYSMON_LOG_LEVEL="${SYSMON_LOG_LEVEL:-INFO}"
SYSMON_VERBOSE="${SYSMON_VERBOSE:-false}"
SYSMON_QUIET="${SYSMON_QUIET:-false}"

# Get timestamp for logging
_timestamp() {
    date '+%Y-%m-%d %H:%M:%S'
}

# Check if log level should be shown
_should_log() {
    local level="$1"
    case "$SYSMON_LOG_LEVEL" in
        DEBUG) return 0 ;;
        INFO)  [[ "$level" != "DEBUG" ]] && return 0 ;;
        *)     [[ "$level" =~ ^(SUCCESS|WARNING|ERROR)$ ]] && return 0 ;;
    esac
    return 1
}

# Core logging function
log() {
    [[ "$SYSMON_QUIET" == "true" ]] && return 0
    local message="$1"
    echo -e "${BLUE}[$(_timestamp)]${NC} $message"
}

log_info() {
    [[ "$SYSMON_QUIET" == "true" ]] && return 0
    _should_log "INFO" || return 0
    local message="$1"
    echo -e "${CYAN}[INFO]${NC} $message"
}

log_success() {
    [[ "$SYSMON_QUIET" == "true" ]] && return 0
    local message="$1"
    echo -e "${GREEN}[OK]${NC} $message"
}

log_warning() {
    local message="$1"
    echo -e "${YELLOW}[WARN]${NC} $message" >&2
}

log_error() {
    local message="$1"
    echo -e "${RED}[ERROR]${NC} $message" >&2
}

log_debug() {
    [[ "$SYSMON_VERBOSE" != "true" ]] && return 0
    local message="$1"
    echo -e "${MAGENTA}[DEBUG]${NC} $message"
}

# Print formatted header with borders
print_header() {
    local title="$1"
    local width="${2:-64}"
    local border=$(printf '━%.0s' $(seq 1 $width))
    echo ""
    echo -e "${CYAN}${BOLD}${border}${NC}"
    echo -e "${CYAN}${BOLD}  ${title}${NC}"
    echo -e "${CYAN}${BOLD}${border}${NC}"
}

# Print section header (smaller)
print_section() {
    local title="$1"
    echo ""
    echo -e "${BOLD}## ${title}${NC}"
    echo ""
}

# ============================================================================
# USER INTERACTION
# ============================================================================

# Global dry-run flag (can be set via environment)
SYSMON_DRY_RUN="${SYSMON_DRY_RUN:-false}"

# Confirm action with user (returns 0 for yes, 1 for no)
confirm() {
    local prompt="$1"
    local default="${2:-n}"

    # In dry-run mode, log and return success
    if [[ "$SYSMON_DRY_RUN" == "true" ]]; then
        log_info "[DRY RUN] Would ask: $prompt"
        return 0
    fi

    # In quiet mode, use default
    if [[ "$SYSMON_QUIET" == "true" ]]; then
        [[ "$default" =~ ^[Yy] ]] && return 0 || return 1
    fi

    local yn
    if [[ "$default" =~ ^[Yy] ]]; then
        read -p "$(echo -e "${YELLOW}${prompt} [Y/n]: ${NC}")" yn
        yn="${yn:-Y}"
    else
        read -p "$(echo -e "${YELLOW}${prompt} [y/N]: ${NC}")" yn
        yn="${yn:-N}"
    fi

    [[ "$yn" =~ ^[Yy] ]] && return 0 || return 1
}

# Execute command with dry-run support
run_cmd() {
    local cmd="$*"

    if [[ "$SYSMON_DRY_RUN" == "true" ]]; then
        log_info "[DRY RUN] Would execute: $cmd"
        return 0
    fi

    log_debug "Executing: $cmd"
    eval "$cmd"
}

# ============================================================================
# PROGRESS & STATISTICS
# ============================================================================

# Global statistics tracking.
#
# Uses discrete SYSMON_STAT_<key> variables + indirect expansion rather than an
# associative array. macOS ships bash 3.2, where `declare -A` errors out and
# (under `set -e`) aborts sourcing — which broke the capacity-gate. `printf -v`
# and `${!var}` indirection have been available since bash 3.1, so this works
# everywhere without requiring brew bash.

init_stats() {
    SYSMON_STAT_total=0
    SYSMON_STAT_success=0
    SYSMON_STAT_failed=0
    SYSMON_STAT_skipped=0
}

increment_stat() {
    local key="$1"
    local amount="${2:-1}"
    local var="SYSMON_STAT_${key}"
    printf -v "$var" '%d' "$(( ${!var:-0} + amount ))"
}

print_stats() {
    local operation="${1:-Operation}"
    echo ""
    echo -e "${BOLD}━━━ ${operation} Statistics ━━━${NC}"
    echo "  Total:   ${SYSMON_STAT_total:-0}"
    echo "  Success: ${GREEN}${SYSMON_STAT_success:-0}${NC}"
    echo "  Failed:  ${RED}${SYSMON_STAT_failed:-0}${NC}"
    echo "  Skipped: ${YELLOW}${SYSMON_STAT_skipped:-0}${NC}"
}

# Progress indicator (simple spinner)
_SPINNER_PID=""

start_spinner() {
    local message="$1"
    [[ "$SYSMON_QUIET" == "true" ]] && return 0
    [[ ! -t 1 ]] && return 0  # No spinner if not TTY

    (
        local chars='⠋⠙⠹⠸⠼⠴⠦⠧⠇⠏'
        while true; do
            for (( i=0; i<${#chars}; i++ )); do
                echo -en "\r${CYAN}${chars:$i:1}${NC} $message"
                sleep 0.1
            done
        done
    ) &
    _SPINNER_PID=$!
    disown
}

stop_spinner() {
    local status="$1"  # "ok" or "fail"
    [[ -z "$_SPINNER_PID" ]] && return 0

    kill "$_SPINNER_PID" 2>/dev/null
    wait "$_SPINNER_PID" 2>/dev/null
    _SPINNER_PID=""

    # Clear line and show result
    echo -en "\r\033[K"
    if [[ "$status" == "ok" ]]; then
        echo -e "${GREEN}✓${NC} Done"
    else
        echo -e "${RED}✗${NC} Failed"
    fi
}

# ============================================================================
# DEPENDENCY CHECKING
# ============================================================================

# Check if a command exists
check_command() {
    local cmd="$1"
    local install_hint="${2:-}"

    if ! command -v "$cmd" &> /dev/null; then
        log_error "$cmd not found"
        if [[ -n "$install_hint" ]]; then
            log_info "Install with: $install_hint"
        fi
        return 1
    fi
    return 0
}

# Check multiple dependencies
check_dependencies() {
    local -a deps=("$@")
    local missing=0

    for dep in "${deps[@]}"; do
        if ! check_command "$dep"; then
            missing=$((missing + 1))
        fi
    done

    if [[ $missing -gt 0 ]]; then
        log_error "Missing $missing required dependencies"
        return 1
    fi
    return 0
}

# Check if Docker is available and running
check_docker() {
    if ! check_command "docker"; then
        return 1
    fi

    if ! docker info &> /dev/null 2>&1; then
        log_error "Docker daemon is not running"
        log_info "Start Docker with: sudo systemctl start docker"
        return 1
    fi
    return 0
}

# ============================================================================
# UTILITY FUNCTIONS
# ============================================================================

# Get human-readable size
human_size() {
    local bytes="$1"
    if [[ -z "$bytes" || "$bytes" == "0" ]]; then
        echo "0B"
        return
    fi

    local units=("B" "KB" "MB" "GB" "TB")
    local unit=0
    local size=$bytes

    while (( $(echo "$size >= 1024" | bc -l) )) && (( unit < 4 )); do
        size=$(echo "scale=1; $size / 1024" | bc)
        unit=$((unit + 1))
    done

    echo "${size}${units[$unit]}"
}

# Get percentage with color coding
colored_percentage() {
    local value="$1"
    local warning="${2:-75}"
    local critical="${3:-90}"

    # Extract numeric value - handle formats like "83%", "83", "83% (80G/96G)"
    local num
    # First, strip everything after the first space or non-digit (except %)
    num="${value%% *}"
    # Then strip the % sign
    num="${num%\%}"
    # Strip decimal portion
    num="${num%%.*}"
    # Ensure it's numeric, default to 0 if not
    if ! [[ "$num" =~ ^[0-9]+$ ]]; then
        num=0
    fi

    if [[ "$num" -ge "$critical" ]]; then
        echo -e "${RED}${value}${NC}"
    elif [[ "$num" -ge "$warning" ]]; then
        echo -e "${YELLOW}${value}${NC}"
    else
        echo -e "${GREEN}${value}${NC}"
    fi
}

# Safe path quoting
quote_path() {
    local path="$1"
    printf '%q' "$path"
}

# Check if running on EC2 instance
detect_system() {
    local hostname_ip ip1 ip2
    hostname_ip=$(hostname -I 2>/dev/null | tr ' ' '\n' | head -1)
    ip1="${SYSMON_INSTANCE1_IP:-}"
    ip2="${SYSMON_INSTANCE2_IP:-}"

    if { [[ -n "$ip1" && "$hostname_ip" == *"$ip1"* ]]; } || [[ "$hostname_ip" == 172.31.* ]]; then
        if curl -s --connect-timeout 1 http://169.254.169.254/latest/meta-data/instance-id &>/dev/null; then
            # Check instance by some identifier
            echo "instance1"
        else
            echo "local"
        fi
    elif [[ -n "$ip2" && "$hostname_ip" == *"$ip2"* ]]; then
        echo "instance2"
    else
        echo "local"
    fi
}

# ============================================================================
# TABLE FORMATTING
# ============================================================================

# Print a markdown-style table row
table_row() {
    local -a cols=("$@")
    local row="|"
    for col in "${cols[@]}"; do
        row+=" $col |"
    done
    echo "$row"
}

# Print table separator
table_sep() {
    local num_cols="$1"
    local sep="|"
    for (( i=0; i<num_cols; i++ )); do
        sep+="-------|"
    done
    echo "$sep"
}
