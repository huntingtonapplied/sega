#!/bin/bash
# ============================================================================
# SYSMON - Display Widgets Library
# ============================================================================
# Progress bars, gauges, sparklines, and other visual widgets
# Source this file: source "${SYSMON_LIB_DIR}/display/widgets.sh"
# ============================================================================

# Prevent double-sourcing
[[ -n "${SYSMON_WIDGETS_LOADED:-}" ]] && return 0
SYSMON_WIDGETS_LOADED=1

# ============================================================================
# PROGRESS BAR CHARACTERS
# ============================================================================

# Block style (default)
PROGRESS_FILLED='█'
PROGRESS_EMPTY='░'

# Alternative styles
PROGRESS_FILLED_THIN='━'
PROGRESS_EMPTY_THIN='─'

PROGRESS_FILLED_BLOCK='▓'
PROGRESS_EMPTY_BLOCK='░'

# ============================================================================
# PROGRESS BARS
# ============================================================================

# Draw a progress bar and return the string (no positioning)
# Usage: progress_bar $value $max $width
# Returns: [████████░░░░░░░░░░░░] 45%
progress_bar() {
    local value="$1"
    local max="$2"
    local width="${3:-30}"

    # Strip any non-numeric characters and handle decimals
    value="${value%\%}"
    value="${value%%.*}"
    value="${value//[^0-9]/}"
    [[ -z "$value" ]] && value=0

    max="${max%\%}"
    max="${max%%.*}"
    max="${max//[^0-9]/}"
    [[ -z "$max" || "$max" -eq 0 ]] && max=100

    # Calculate percentage
    local pct=0
    if [[ "$max" -gt 0 ]]; then
        pct=$((value * 100 / max))
    fi

    # Clamp to 0-100
    ((pct < 0)) && pct=0
    ((pct > 100)) && pct=100

    # Calculate filled/empty widths
    local bar_width=$((width - 2))  # Account for brackets
    local filled=$((pct * bar_width / 100))
    local empty=$((bar_width - filled))

    # Determine color based on percentage
    local color="$GREEN"
    if ((pct >= 90)); then
        color="$RED"
    elif ((pct >= 75)); then
        color="$YELLOW"
    elif ((pct >= 50)); then
        color="$CYAN"
    fi

    # Build bar string
    local bar="["
    bar+="${color}"
    for ((i=0; i<filled; i++)); do
        bar+="$PROGRESS_FILLED"
    done
    bar+="${NC}"
    for ((i=0; i<empty; i++)); do
        bar+="$PROGRESS_EMPTY"
    done
    bar+="]"

    echo -en "${bar} ${pct}%"
}

# Draw a progress bar at specific position
# Usage: draw_progress_bar $row $col $value $max $width
draw_progress_bar() {
    local row="$1"
    local col="$2"
    local value="$3"
    local max="$4"
    local width="${5:-30}"

    cursor_to "$row" "$col"
    progress_bar "$value" "$max" "$width"
}

# ============================================================================
# LABELED GAUGES
# ============================================================================

# Draw a labeled gauge (label + progress bar + details)
# Usage: labeled_gauge "Disk" $used $total $width ["suffix"]
# Returns: Disk    [████████████░░░░░░░░] 83% (80G/96G)
labeled_gauge() {
    local label="$1"
    local used="$2"
    local total="$3"
    local width="${4:-40}"
    local suffix="${5:-}"

    local label_width=8
    local bar_width=$((width - label_width - 20))  # Space for percentage and details

    # Label
    printf "%-${label_width}s" "$label"

    # Progress bar
    progress_bar "$used" "$total" "$bar_width"

    # Details
    if [[ -n "$suffix" ]]; then
        printf " (%s/%s)" "$used" "$total"
    fi
}

# Draw labeled gauge at position
# Usage: draw_labeled_gauge $row $col "Disk" $used $total $width ["suffix"]
draw_labeled_gauge() {
    local row="$1"
    local col="$2"
    shift 2

    cursor_to "$row" "$col"
    labeled_gauge "$@"
}

# ============================================================================
# SPARKLINES
# ============================================================================

# Sparkline characters (8 levels)
SPARKLINE_CHARS='▁▂▃▄▅▆▇█'

# Generate sparkline from values
# Usage: sparkline "${values[@]}"
# Returns: ▁▂▃▄▅▆▇█▆▄
sparkline() {
    local -a values=("$@")
    local count=${#values[@]}

    if [[ $count -eq 0 ]]; then
        return
    fi

    # Find min and max
    local min=${values[0]}
    local max=${values[0]}
    local v

    for v in "${values[@]}"; do
        ((v < min)) && min=$v
        ((v > max)) && max=$v
    done

    # Calculate range (avoid division by zero)
    local range=$((max - min))
    ((range == 0)) && range=1

    # Generate sparkline
    local result=""
    for v in "${values[@]}"; do
        local level=$(( (v - min) * 7 / range ))
        ((level < 0)) && level=0
        ((level > 7)) && level=7
        result+="${SPARKLINE_CHARS:$level:1}"
    done

    echo -n "$result"
}

# Draw sparkline at position
# Usage: draw_sparkline $row $col "${values[@]}"
draw_sparkline() {
    local row="$1"
    local col="$2"
    shift 2

    cursor_to "$row" "$col"
    sparkline "$@"
}

# ============================================================================
# STATUS INDICATORS
# ============================================================================

# Status indicator symbols
STATUS_HEALTHY='●'
STATUS_WARNING='⚠'
STATUS_ERROR='✗'
STATUS_PENDING='○'
STATUS_LOADING='◐'
STATUS_INFO='ℹ'
STATUS_CHECK='✓'

# Get colored status indicator
# Usage: status_indicator "healthy|warning|error|pending|loading|info|check"
status_indicator() {
    local status="$1"

    case "$status" in
        healthy|ok|good)
            echo -en "${GREEN}${STATUS_HEALTHY}${NC}"
            ;;
        warning|warn)
            echo -en "${YELLOW}${STATUS_WARNING}${NC}"
            ;;
        error|fail|critical)
            echo -en "${RED}${STATUS_ERROR}${NC}"
            ;;
        pending|waiting)
            echo -en "${DIM}${STATUS_PENDING}${NC}"
            ;;
        loading|checking)
            echo -en "${CYAN}${STATUS_LOADING}${NC}"
            ;;
        info)
            echo -en "${CYAN}${STATUS_INFO}${NC}"
            ;;
        check|done)
            echo -en "${GREEN}${STATUS_CHECK}${NC}"
            ;;
        *)
            echo -n "$status"
            ;;
    esac
}

# ============================================================================
# COMPACT METRICS
# ============================================================================

# Compact gauge (for tight spaces)
# Usage: compact_gauge "D" 83
# Returns: D:83%
compact_gauge() {
    local label="$1"
    local pct="$2"

    local color="$GREEN"
    if ((pct >= 90)); then
        color="$RED"
    elif ((pct >= 75)); then
        color="$YELLOW"
    fi

    echo -en "${label}:${color}${pct}%${NC}"
}

# Mini progress bar (5 chars wide)
# Usage: mini_bar 60
# Returns: [▓▓▓░░]
mini_bar() {
    local pct="$1"
    local filled=$((pct / 20))
    local empty=$((5 - filled))

    local color="$GREEN"
    if ((pct >= 90)); then
        color="$RED"
    elif ((pct >= 75)); then
        color="$YELLOW"
    fi

    echo -n "["
    echo -en "${color}"
    for ((i=0; i<filled; i++)); do echo -n "▓"; done
    echo -en "${NC}"
    for ((i=0; i<empty; i++)); do echo -n "░"; done
    echo -n "]"
}

# ============================================================================
# TABLES
# ============================================================================

# Draw table header
# Usage: table_header "Col1" "Col2" "Col3"
table_header() {
    local -a cols=("$@")

    echo -en "${BOLD}"
    echo -n "│"
    for col in "${cols[@]}"; do
        printf " %-12s │" "$col"
    done
    echo -e "${NC}"

    # Separator line
    echo -n "├"
    for col in "${cols[@]}"; do
        echo -n "──────────────┼"
    done
    echo ""
}

# Draw table row
# Usage: table_row "val1" "val2" "val3"
table_row() {
    local -a vals=("$@")

    echo -n "│"
    for val in "${vals[@]}"; do
        printf " %-12s │" "$val"
    done
    echo ""
}

# ============================================================================
# INSTANCE PANEL
# ============================================================================

# Draw instance status panel header
# Usage: instance_header "Instance 1" "203.0.113.10" "healthy"
instance_header() {
    local name="$1"
    local ip="$2"
    local status="$3"

    local indicator=$(status_indicator "$status")

    echo -en "${CYAN}${BOLD}─ ${name} (${ip}) ${indicator} "
    # Fill rest with dashes
    local used_len=$((${#name} + ${#ip} + 8))
    local remaining=$((SCREEN_COLS - used_len - 4))
    printf '─%.0s' $(seq 1 $remaining)
    echo -e "${NC}"
}

# ============================================================================
# ALERTS
# ============================================================================

# Format alert message
# Usage: alert_msg "warning" "Disk usage above 80%"
alert_msg() {
    local level="$1"
    local message="$2"

    local indicator=$(status_indicator "$level")
    echo -e "${indicator} ${message}"
}
