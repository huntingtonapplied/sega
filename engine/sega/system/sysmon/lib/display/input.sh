#!/bin/bash
# ============================================================================
# SYSMON - Display Input Library
# ============================================================================
# Non-blocking keyboard input handling for live mode
# Source this file: source "${SYSMON_LIB_DIR}/display/input.sh"
# ============================================================================

# Prevent double-sourcing
[[ -n "${SYSMON_INPUT_LOADED:-}" ]] && return 0
SYSMON_INPUT_LOADED=1

# ============================================================================
# INPUT STATE
# ============================================================================

# Input action flags (set by handle_input)
INPUT_QUIT=false
INPUT_REFRESH=false
INPUT_TOGGLE_DETAIL=false
INPUT_TOGGLE_HELP=false
INPUT_FOCUS=""  # "", "1", "2", "local", "all"
INPUT_INTERVAL_CHANGE=0  # -1, 0, +1

# Page navigation state
INPUT_PAGE_CHANGE=0     # -1 (prev), 0 (none), +1 (next)
INPUT_PAGE_DIRECT=0     # Direct page number (1-6), 0 = no direct navigation
CURRENT_PAGE=1          # Current page (1-6)
PREVIOUS_PAGE=1         # Previous page for change detection
PAGE_CHANGED=false      # Flag to indicate page just changed (triggers screen clear)
MAX_PAGES=6             # Total number of pages

# Page definitions
# Page 1: Overview (default dashboard)
# Page 2: Storage Detail (venvs, node_modules, /data)
# Page 3: Docker Detail
# Page 4: Process/CPU Detail
# Page 5: Time Series Graphs
# Page 6: Services (non-Docker - Node.js frontends, Python backends)

# ============================================================================
# KEY READING
# ============================================================================

# Global variable to hold the last key read
LAST_KEY=""

# Read a single keypress (non-blocking)
# Sets LAST_KEY global variable instead of echoing (avoids subshell issues)
read_key() {
    LAST_KEY=""

    # Non-blocking read with 0.1s timeout
    IFS= read -rsn1 -t 0.1 LAST_KEY 2>/dev/null || true

    # Handle escape sequences (arrow keys, function keys, etc.)
    if [[ "$LAST_KEY" == $'\x1b' ]]; then
        # Read the [ or O character
        local char2=""
        IFS= read -rsn1 -t 0.1 char2 2>/dev/null || true
        LAST_KEY+="$char2"

        # If it's [ or O, read more characters
        if [[ "$char2" == "[" || "$char2" == "O" ]]; then
            local char3=""
            IFS= read -rsn1 -t 0.1 char3 2>/dev/null || true
            LAST_KEY+="$char3"

            # Handle longer sequences like \x1b[5~ (Page Up/Down)
            if [[ "$char3" =~ [0-9] ]]; then
                local char4=""
                IFS= read -rsn1 -t 0.1 char4 2>/dev/null || true
                LAST_KEY+="$char4"
            fi
        fi
    fi
}

# ============================================================================
# INPUT HANDLING
# ============================================================================

# Reset all input flags
reset_input_flags() {
    INPUT_QUIT=false
    INPUT_REFRESH=false
    INPUT_TOGGLE_DETAIL=false
    INPUT_TOGGLE_HELP=false
    INPUT_FOCUS=""
    INPUT_INTERVAL_CHANGE=0
    INPUT_PAGE_CHANGE=0
    INPUT_PAGE_DIRECT=0
}

# Handle keyboard input
# Returns: 0 to continue, 1 to quit
handle_input() {
    reset_input_flags

    read_key
    local key="$LAST_KEY"

    # No key pressed
    [[ -z "$key" ]] && return 0

    case "$key" in
        # Quit
        q|Q)
            INPUT_QUIT=true
            return 1
            ;;

        # Force refresh
        r|R)
            INPUT_REFRESH=true
            ;;

        # Increase interval
        +|=)
            INPUT_INTERVAL_CHANGE=1
            ;;

        # Decrease interval
        -|_)
            INPUT_INTERVAL_CHANGE=-1
            ;;

        # Direct page navigation via number keys
        1)
            INPUT_PAGE_DIRECT=1
            ;;
        2)
            INPUT_PAGE_DIRECT=2
            ;;
        3)
            INPUT_PAGE_DIRECT=3
            ;;
        4)
            INPUT_PAGE_DIRECT=4
            ;;
        5)
            INPUT_PAGE_DIRECT=5
            ;;
        6)
            INPUT_PAGE_DIRECT=6
            ;;

        # Focus on specific instance (use i prefix mentally, or via menu)
        l|L)
            INPUT_FOCUS="local"
            ;;
        a|A)
            INPUT_FOCUS="all"
            ;;

        # Toggle detailed view
        d|D)
            INPUT_TOGGLE_DETAIL=true
            ;;

        # Toggle help
        h|H|\?)
            INPUT_TOGGLE_HELP=true
            ;;

        # Page navigation - Next page
        n|N|$'\t')  # n, N, Tab
            INPUT_PAGE_CHANGE=1
            ;;

        # Page navigation - Previous page
        p|P)
            INPUT_PAGE_CHANGE=-1
            ;;

        # Arrow keys (escape sequences)
        $'\x1b[A')  # Up arrow - Next page (increase page number)
            INPUT_PAGE_CHANGE=1
            ;;
        $'\x1b[B')  # Down arrow - Previous page (decrease page number)
            INPUT_PAGE_CHANGE=-1
            ;;
        $'\x1b[C')  # Right arrow
            INPUT_INTERVAL_CHANGE=1
            ;;
        $'\x1b[D')  # Left arrow
            INPUT_INTERVAL_CHANGE=-1
            ;;

        # Page Up/Down keys
        $'\x1b[5~')  # Page Up
            INPUT_PAGE_CHANGE=-1
            ;;
        $'\x1b[6~')  # Page Down
            INPUT_PAGE_CHANGE=1
            ;;

        # Function keys for direct page access (F1-F5)
        $'\x1bOP'|$'\x1b[11~')  # F1 - Overview
            INPUT_PAGE_DIRECT=1
            ;;
        $'\x1bOQ'|$'\x1b[12~')  # F2 - Storage Detail
            INPUT_PAGE_DIRECT=2
            ;;
        $'\x1bOR'|$'\x1b[13~')  # F3 - Docker Detail
            INPUT_PAGE_DIRECT=3
            ;;
        $'\x1bOS'|$'\x1b[14~')  # F4 - Process/CPU
            INPUT_PAGE_DIRECT=4
            ;;
        $'\x1b[15~')  # F5 - Time Series
            INPUT_PAGE_DIRECT=5
            ;;
        $'\x1b[17~')  # F6 - Services
            INPUT_PAGE_DIRECT=6
            ;;

        # Space to refresh
        ' ')
            INPUT_REFRESH=true
            ;;

        # Escape to quit
        $'\x1b')
            INPUT_QUIT=true
            return 1
            ;;
    esac

    return 0
}

# ============================================================================
# PAGE NAVIGATION
# ============================================================================

# Get page name for display
get_page_name() {
    local page="${1:-$CURRENT_PAGE}"
    case "$page" in
        1) echo "Overview" ;;
        2) echo "Storage Detail" ;;
        3) echo "Docker Detail" ;;
        4) echo "Process/CPU" ;;
        5) echo "Time Series" ;;
        6) echo "Services" ;;
        *) echo "Unknown" ;;
    esac
}

# Handle page navigation and update CURRENT_PAGE
# Returns: 0 if page changed, 1 if no change
handle_page_navigation() {
    local old_page="$CURRENT_PAGE"
    PAGE_CHANGED=false

    # Handle direct page navigation
    if ((INPUT_PAGE_DIRECT > 0 && INPUT_PAGE_DIRECT <= MAX_PAGES)); then
        CURRENT_PAGE="$INPUT_PAGE_DIRECT"
    fi

    # Handle relative page navigation
    if ((INPUT_PAGE_CHANGE != 0)); then
        CURRENT_PAGE=$((CURRENT_PAGE + INPUT_PAGE_CHANGE))

        # Wrap around
        if ((CURRENT_PAGE < 1)); then
            CURRENT_PAGE="$MAX_PAGES"
        elif ((CURRENT_PAGE > MAX_PAGES)); then
            CURRENT_PAGE=1
        fi
    fi

    # Set PAGE_CHANGED flag if page actually changed
    if [[ "$old_page" != "$CURRENT_PAGE" ]]; then
        PAGE_CHANGED=true
        PREVIOUS_PAGE="$old_page"
        return 0
    fi
    return 1
}

# ============================================================================
# INPUT POLLING LOOP
# ============================================================================

# Poll for input with callback
# Usage: poll_input_loop $interval callback_func
# Calls callback_func every $interval seconds, or immediately on keypress
poll_input_loop() {
    local interval="$1"
    local callback="$2"

    local last_refresh=$(date +%s)
    local running=true

    while $running; do
        local now=$(date +%s)
        local elapsed=$((now - last_refresh))

        # Handle keyboard input
        if ! handle_input; then
            running=false
            break
        fi

        # Handle page navigation
        if handle_page_navigation; then
            # Page changed, force refresh
            INPUT_REFRESH=true
        fi

        # Check if refresh needed (time elapsed or forced)
        local should_refresh=false

        if [[ "$INPUT_REFRESH" == "true" ]]; then
            should_refresh=true
        elif ((elapsed >= interval)); then
            should_refresh=true
        fi

        # Handle interval changes
        if ((INPUT_INTERVAL_CHANGE != 0)); then
            interval=$((interval + INPUT_INTERVAL_CHANGE))
            ((interval < 1)) && interval=1
            ((interval > 60)) && interval=60
            # Export for callback to read
            export CURRENT_INTERVAL="$interval"
        fi

        # Call callback if refresh needed
        if $should_refresh; then
            last_refresh=$(date +%s)
            export CURRENT_INTERVAL="$interval"
            export TIME_TO_REFRESH="$interval"

            if ! "$callback"; then
                running=false
                break
            fi
        else
            # Export countdown for status line
            export TIME_TO_REFRESH=$((interval - elapsed))
        fi

        # Small sleep to prevent CPU spin
        sleep 0.05
    done
}

# ============================================================================
# HELP OVERLAY
# ============================================================================

# Show help overlay content
show_help_overlay() {
    local start_row="${1:-5}"
    local start_col="${2:-10}"

    local help_text=(
        "┌─────────────────────────────────────┐"
        "│        KEYBOARD SHORTCUTS           │"
        "├─────────────────────────────────────┤"
        "│  q, Esc     Quit dashboard          │"
        "│  r, Space   Refresh now             │"
        "│  ←, →       Change refresh rate     │"
        "├─────────────────────────────────────┤"
        "│           PAGE NAVIGATION           │"
        "│  1-6           Jump to page 1-6     │"
        "│  ↑, PgUp, p    Previous page        │"
        "│  ↓, PgDn, n    Next page            │"
        "│  F1-F6, Tab    Also work            │"
        "├─────────────────────────────────────┤"
        "│  1=Overview  2=Storage  3=Docker    │"
        "│  4=CPU       5=Graphs   6=Services  │"
        "├─────────────────────────────────────┤"
        "│  l          Focus Local instance    │"
        "│  a          Show All (default)      │"
        "├─────────────────────────────────────┤"
        "│  d          Toggle detailed view    │"
        "│  h, ?       Toggle this help        │"
        "├─────────────────────────────────────┤"
        "│  Press any key to close             │"
        "└─────────────────────────────────────┘"
    )

    local row="$start_row"
    for line in "${help_text[@]}"; do
        cursor_to "$row" "$start_col"
        echo -en "${CYAN}${line}${NC}"
        ((row++))
    done
}

# Wait for any key to dismiss help
wait_for_dismiss() {
    # Blocking read for any key
    IFS= read -rsn1 2>/dev/null
}

# ============================================================================
# PAGE INDICATOR
# ============================================================================

# Render page indicator bar
# Usage: render_page_indicator [width]
# Returns: string like "[1] Overview  2  3  4  5" or with highlight
render_page_indicator() {
    local width="${1:-80}"
    local indicator=""

    for ((i=1; i<=MAX_PAGES; i++)); do
        if ((i == CURRENT_PAGE)); then
            # Current page - highlighted with name
            local name=$(get_page_name "$i")
            indicator+="${BOLD}${CYAN}[$i] ${name}${NC}  "
        else
            # Other pages - just number
            indicator+="${DIM}$i${NC}  "
        fi
    done

    # Center the indicator
    local stripped=$(echo -e "$indicator" | sed 's/\x1b\[[0-9;]*m//g')
    local len=${#stripped}
    local padding=$(( (width - len) / 2 ))

    printf "%${padding}s%b" "" "$indicator"
}

# Get page indicator for status line
# Returns: compact page indicator like "Page 2/5 (Storage Detail)"
get_page_status() {
    local name=$(get_page_name "$CURRENT_PAGE")
    echo "Page ${CURRENT_PAGE}/${MAX_PAGES} (${name})"
}
