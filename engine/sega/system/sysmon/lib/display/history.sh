#!/bin/bash
# ============================================================================
# SYSMON - History Storage Library
# ============================================================================
# Store and retrieve metrics history for time-series visualization
# Source this file: source "${SYSMON_LIB_DIR}/display/history.sh"
# ============================================================================

# Prevent double-sourcing
[[ -n "${SYSMON_HISTORY_LOADED:-}" ]] && return 0
SYSMON_HISTORY_LOADED=1

# ============================================================================
# CONFIGURATION
# ============================================================================

# History storage directory
HISTORY_DIR="${SYSMON_HISTORY_DIR:-${HOME}/.cache/sysmon}"

# Maximum data points to keep (24h at 30s intervals = 2880)
HISTORY_MAX_POINTS="${SYSMON_HISTORY_MAX:-2880}"

# History file names
HISTORY_FILE_I1="${HISTORY_DIR}/metrics_i1.csv"
HISTORY_FILE_I2="${HISTORY_DIR}/metrics_i2.csv"
HISTORY_FILE_LOCAL="${HISTORY_DIR}/metrics_local.csv"

# In-memory history arrays (for current session)
declare -a HISTORY_CPU_I1=()
declare -a HISTORY_MEM_I1=()
declare -a HISTORY_DISK_I1=()
declare -a HISTORY_DOCKER_I1=()
declare -a HISTORY_CLAUDE_I1=()
declare -a HISTORY_TS_I1=()

declare -a HISTORY_CPU_I2=()
declare -a HISTORY_MEM_I2=()
declare -a HISTORY_DISK_I2=()
declare -a HISTORY_DOCKER_I2=()
declare -a HISTORY_CLAUDE_I2=()
declare -a HISTORY_TS_I2=()

declare -a HISTORY_CPU_LOCAL=()
declare -a HISTORY_MEM_LOCAL=()
declare -a HISTORY_DISK_LOCAL=()
declare -a HISTORY_DOCKER_LOCAL=()
declare -a HISTORY_CLAUDE_LOCAL=()
declare -a HISTORY_TS_LOCAL=()

# ============================================================================
# INITIALIZATION
# ============================================================================

# Initialize history storage
init_history() {
    # Create history directory if it doesn't exist
    if [[ ! -d "$HISTORY_DIR" ]]; then
        mkdir -p "$HISTORY_DIR" 2>/dev/null || {
            log_warning "Could not create history directory: $HISTORY_DIR"
            return 1
        }
    fi

    # Create history files with headers if they don't exist
    for file in "$HISTORY_FILE_I1" "$HISTORY_FILE_I2" "$HISTORY_FILE_LOCAL"; do
        if [[ ! -f "$file" ]]; then
            echo "timestamp,cpu,mem,disk,docker,claude" > "$file"
        fi
    done

    # Load recent history into memory
    load_history_to_memory

    return 0
}

# ============================================================================
# FILE OPERATIONS
# ============================================================================

# Get history file for instance
get_history_file() {
    local instance="$1"
    case "$instance" in
        1|i1|instance1) echo "$HISTORY_FILE_I1" ;;
        2|i2|instance2) echo "$HISTORY_FILE_I2" ;;
        local|l)        echo "$HISTORY_FILE_LOCAL" ;;
        *) echo "" ;;
    esac
}

# Append metrics to history file
append_history_file() {
    local instance="$1"
    local cpu="$2"
    local mem="$3"
    local disk="$4"
    local docker="$5"
    local claude="$6"
    local ts="${7:-$(date +%s)}"

    local file=$(get_history_file "$instance")
    [[ -z "$file" ]] && return 1

    # Append to file
    echo "${ts},${cpu},${mem},${disk},${docker},${claude}" >> "$file"

    # Rotate if too large
    rotate_history_file "$instance"
}

# Rotate history file to keep only recent entries
rotate_history_file() {
    local instance="$1"
    local file=$(get_history_file "$instance")
    [[ -z "$file" || ! -f "$file" ]] && return 0

    local line_count=$(wc -l < "$file")

    if ((line_count > HISTORY_MAX_POINTS + 100)); then
        # Keep header + last HISTORY_MAX_POINTS lines
        local tmp_file="${file}.tmp"
        head -1 "$file" > "$tmp_file"
        tail -n "$HISTORY_MAX_POINTS" "$file" >> "$tmp_file"
        mv "$tmp_file" "$file"
    fi
}

# Read history from file for time range
read_history_file() {
    local instance="$1"
    local range="$2"  # 5m, 15m, 1h, 6h, 24h

    local file=$(get_history_file "$instance")
    [[ -z "$file" || ! -f "$file" ]] && return 1

    # Calculate since timestamp
    local since
    case "$range" in
        5m)  since=$(date -d "-5 minutes" +%s 2>/dev/null || date -v-5M +%s) ;;
        15m) since=$(date -d "-15 minutes" +%s 2>/dev/null || date -v-15M +%s) ;;
        1h)  since=$(date -d "-1 hour" +%s 2>/dev/null || date -v-1H +%s) ;;
        6h)  since=$(date -d "-6 hours" +%s 2>/dev/null || date -v-6H +%s) ;;
        24h) since=$(date -d "-24 hours" +%s 2>/dev/null || date -v-24H +%s) ;;
        *)   since=0 ;;
    esac

    # Filter by timestamp (skip header)
    tail -n +2 "$file" | awk -F',' -v since="$since" '$1 >= since'
}

# ============================================================================
# MEMORY OPERATIONS
# ============================================================================

# Load recent history from files into memory arrays
load_history_to_memory() {
    local max_points=60  # Keep last 60 points in memory (for sparklines)

    # Load Instance 1
    if [[ -f "$HISTORY_FILE_I1" ]]; then
        while IFS=',' read -r ts cpu mem disk docker claude; do
            [[ "$ts" == "timestamp" ]] && continue
            HISTORY_TS_I1+=("$ts")
            HISTORY_CPU_I1+=("$cpu")
            HISTORY_MEM_I1+=("$mem")
            HISTORY_DISK_I1+=("$disk")
            HISTORY_DOCKER_I1+=("$docker")
            HISTORY_CLAUDE_I1+=("$claude")
        done < <(tail -n "$max_points" "$HISTORY_FILE_I1")
    fi

    # Load Instance 2
    if [[ -f "$HISTORY_FILE_I2" ]]; then
        while IFS=',' read -r ts cpu mem disk docker claude; do
            [[ "$ts" == "timestamp" ]] && continue
            HISTORY_TS_I2+=("$ts")
            HISTORY_CPU_I2+=("$cpu")
            HISTORY_MEM_I2+=("$mem")
            HISTORY_DISK_I2+=("$disk")
            HISTORY_DOCKER_I2+=("$docker")
            HISTORY_CLAUDE_I2+=("$claude")
        done < <(tail -n "$max_points" "$HISTORY_FILE_I2")
    fi

    # Load Local
    if [[ -f "$HISTORY_FILE_LOCAL" ]]; then
        while IFS=',' read -r ts cpu mem disk docker claude; do
            [[ "$ts" == "timestamp" ]] && continue
            HISTORY_TS_LOCAL+=("$ts")
            HISTORY_CPU_LOCAL+=("$cpu")
            HISTORY_MEM_LOCAL+=("$mem")
            HISTORY_DISK_LOCAL+=("$disk")
            HISTORY_DOCKER_LOCAL+=("$docker")
            HISTORY_CLAUDE_LOCAL+=("$claude")
        done < <(tail -n "$max_points" "$HISTORY_FILE_LOCAL")
    fi
}

# Add metrics to in-memory history
append_history_memory() {
    local instance="$1"
    local cpu="$2"
    local mem="$3"
    local disk="$4"
    local docker="$5"
    local claude="$6"
    local ts="${7:-$(date +%s)}"

    local max_memory=60  # Keep last 60 points in memory

    case "$instance" in
        1|i1|instance1)
            HISTORY_TS_I1+=("$ts")
            HISTORY_CPU_I1+=("${cpu%%.*}")
            HISTORY_MEM_I1+=("${mem%%.*}")
            HISTORY_DISK_I1+=("${disk%%.*}")
            HISTORY_DOCKER_I1+=("$docker")
            HISTORY_CLAUDE_I1+=("$claude")
            # Trim if too long
            ((${#HISTORY_CPU_I1[@]} > max_memory)) && HISTORY_CPU_I1=("${HISTORY_CPU_I1[@]:1}")
            ((${#HISTORY_MEM_I1[@]} > max_memory)) && HISTORY_MEM_I1=("${HISTORY_MEM_I1[@]:1}")
            ((${#HISTORY_DISK_I1[@]} > max_memory)) && HISTORY_DISK_I1=("${HISTORY_DISK_I1[@]:1}")
            ((${#HISTORY_DOCKER_I1[@]} > max_memory)) && HISTORY_DOCKER_I1=("${HISTORY_DOCKER_I1[@]:1}")
            ((${#HISTORY_CLAUDE_I1[@]} > max_memory)) && HISTORY_CLAUDE_I1=("${HISTORY_CLAUDE_I1[@]:1}")
            ((${#HISTORY_TS_I1[@]} > max_memory)) && HISTORY_TS_I1=("${HISTORY_TS_I1[@]:1}")
            ;;
        2|i2|instance2)
            HISTORY_TS_I2+=("$ts")
            HISTORY_CPU_I2+=("${cpu%%.*}")
            HISTORY_MEM_I2+=("${mem%%.*}")
            HISTORY_DISK_I2+=("${disk%%.*}")
            HISTORY_DOCKER_I2+=("$docker")
            HISTORY_CLAUDE_I2+=("$claude")
            ((${#HISTORY_CPU_I2[@]} > max_memory)) && HISTORY_CPU_I2=("${HISTORY_CPU_I2[@]:1}")
            ((${#HISTORY_MEM_I2[@]} > max_memory)) && HISTORY_MEM_I2=("${HISTORY_MEM_I2[@]:1}")
            ((${#HISTORY_DISK_I2[@]} > max_memory)) && HISTORY_DISK_I2=("${HISTORY_DISK_I2[@]:1}")
            ((${#HISTORY_DOCKER_I2[@]} > max_memory)) && HISTORY_DOCKER_I2=("${HISTORY_DOCKER_I2[@]:1}")
            ((${#HISTORY_CLAUDE_I2[@]} > max_memory)) && HISTORY_CLAUDE_I2=("${HISTORY_CLAUDE_I2[@]:1}")
            ((${#HISTORY_TS_I2[@]} > max_memory)) && HISTORY_TS_I2=("${HISTORY_TS_I2[@]:1}")
            ;;
        local|l)
            HISTORY_TS_LOCAL+=("$ts")
            HISTORY_CPU_LOCAL+=("${cpu%%.*}")
            HISTORY_MEM_LOCAL+=("${mem%%.*}")
            HISTORY_DISK_LOCAL+=("${disk%%.*}")
            HISTORY_DOCKER_LOCAL+=("$docker")
            HISTORY_CLAUDE_LOCAL+=("$claude")
            ((${#HISTORY_CPU_LOCAL[@]} > max_memory)) && HISTORY_CPU_LOCAL=("${HISTORY_CPU_LOCAL[@]:1}")
            ((${#HISTORY_MEM_LOCAL[@]} > max_memory)) && HISTORY_MEM_LOCAL=("${HISTORY_MEM_LOCAL[@]:1}")
            ((${#HISTORY_DISK_LOCAL[@]} > max_memory)) && HISTORY_DISK_LOCAL=("${HISTORY_DISK_LOCAL[@]:1}")
            ((${#HISTORY_DOCKER_LOCAL[@]} > max_memory)) && HISTORY_DOCKER_LOCAL=("${HISTORY_DOCKER_LOCAL[@]:1}")
            ((${#HISTORY_CLAUDE_LOCAL[@]} > max_memory)) && HISTORY_CLAUDE_LOCAL=("${HISTORY_CLAUDE_LOCAL[@]:1}")
            ((${#HISTORY_TS_LOCAL[@]} > max_memory)) && HISTORY_TS_LOCAL=("${HISTORY_TS_LOCAL[@]:1}")
            ;;
    esac
}

# Record current metrics (both file and memory)
record_metrics() {
    local instance="$1"
    local cpu="$2"
    local mem="$3"
    local disk="$4"
    local docker="$5"
    local claude="$6"

    # Clean numeric values
    cpu="${cpu%%.*}"
    cpu="${cpu%\%}"
    mem="${mem%%.*}"
    mem="${mem%\%}"
    disk="${disk%%.*}"
    disk="${disk%\%}"

    local ts=$(date +%s)

    # Store to file (persistent)
    append_history_file "$instance" "$cpu" "$mem" "$disk" "$docker" "$claude" "$ts"

    # Store to memory (for quick access)
    append_history_memory "$instance" "$cpu" "$mem" "$disk" "$docker" "$claude" "$ts"
}

# ============================================================================
# QUERY FUNCTIONS
# ============================================================================

# Get CPU history array for instance
get_cpu_history() {
    local instance="$1"
    case "$instance" in
        1|i1|instance1) echo "${HISTORY_CPU_I1[@]}" ;;
        2|i2|instance2) echo "${HISTORY_CPU_I2[@]}" ;;
        local|l)        echo "${HISTORY_CPU_LOCAL[@]}" ;;
    esac
}

# Get memory history array for instance
get_mem_history() {
    local instance="$1"
    case "$instance" in
        1|i1|instance1) echo "${HISTORY_MEM_I1[@]}" ;;
        2|i2|instance2) echo "${HISTORY_MEM_I2[@]}" ;;
        local|l)        echo "${HISTORY_MEM_LOCAL[@]}" ;;
    esac
}

# Get disk history array for instance
get_disk_history() {
    local instance="$1"
    case "$instance" in
        1|i1|instance1) echo "${HISTORY_DISK_I1[@]}" ;;
        2|i2|instance2) echo "${HISTORY_DISK_I2[@]}" ;;
        local|l)        echo "${HISTORY_DISK_LOCAL[@]}" ;;
    esac
}

# Calculate statistics from array
calc_stats() {
    local -a values=("$@")
    local sum=0 min=999999 max=0 count=0

    for v in "${values[@]}"; do
        [[ -z "$v" || ! "$v" =~ ^[0-9]+$ ]] && continue
        ((sum += v))
        ((v < min)) && min=$v
        ((v > max)) && max=$v
        ((count++))
    done

    local avg=0
    ((count > 0)) && avg=$((sum / count))

    echo "$avg $min $max $count"
}

# ============================================================================
# UNIFIED METRIC ACCESS
# ============================================================================

# Get metric history for instance and metric type
# Usage: get_metric_history instance metric [count]
# Returns: space-separated values
get_metric_history() {
    local instance="$1"
    local metric="$2"
    local count="${3:-30}"

    local -a result=()

    case "$instance" in
        1|i1|instance1)
            case "$metric" in
                cpu)    result=("${HISTORY_CPU_I1[@]}") ;;
                mem)    result=("${HISTORY_MEM_I1[@]}") ;;
                disk)   result=("${HISTORY_DISK_I1[@]}") ;;
                docker) result=("${HISTORY_DOCKER_I1[@]}") ;;
                claude) result=("${HISTORY_CLAUDE_I1[@]}") ;;
            esac
            ;;
        2|i2|instance2)
            case "$metric" in
                cpu)    result=("${HISTORY_CPU_I2[@]}") ;;
                mem)    result=("${HISTORY_MEM_I2[@]}") ;;
                disk)   result=("${HISTORY_DISK_I2[@]}") ;;
                docker) result=("${HISTORY_DOCKER_I2[@]}") ;;
                claude) result=("${HISTORY_CLAUDE_I2[@]}") ;;
            esac
            ;;
        local|l)
            case "$metric" in
                cpu)    result=("${HISTORY_CPU_LOCAL[@]}") ;;
                mem)    result=("${HISTORY_MEM_LOCAL[@]}") ;;
                disk)   result=("${HISTORY_DISK_LOCAL[@]}") ;;
                docker) result=("${HISTORY_DOCKER_LOCAL[@]}") ;;
                claude) result=("${HISTORY_CLAUDE_LOCAL[@]}") ;;
            esac
            ;;
    esac

    # Return last 'count' values
    local len=${#result[@]}
    if ((len > count)); then
        result=("${result[@]:$((len - count))}")
    fi

    echo "${result[@]}"
}

# Check if history is available
has_history() {
    local instance="$1"

    case "$instance" in
        1|i1|instance1) [[ ${#HISTORY_CPU_I1[@]} -gt 0 ]] ;;
        2|i2|instance2) [[ ${#HISTORY_CPU_I2[@]} -gt 0 ]] ;;
        local|l)        [[ ${#HISTORY_CPU_LOCAL[@]} -gt 0 ]] ;;
        *) return 1 ;;
    esac
}
