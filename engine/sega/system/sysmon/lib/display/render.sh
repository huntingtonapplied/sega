#!/bin/bash
# ============================================================================
# SYSMON - Display Render Library
# ============================================================================
# Screen rendering utilities using tput for cursor control
# Source this file: source "${SYSMON_LIB_DIR}/display/render.sh"
# ============================================================================

# Prevent double-sourcing
[[ -n "${SYSMON_RENDER_LOADED:-}" ]] && return 0
SYSMON_RENDER_LOADED=1

# ============================================================================
# SCREEN DIMENSIONS
# ============================================================================

# Get current terminal dimensions
get_screen_size() {
    SCREEN_ROWS=$(tput lines 2>/dev/null) || SCREEN_ROWS=24
    SCREEN_COLS=$(tput cols 2>/dev/null) || SCREEN_COLS=80
    SCREEN_WIDTH=$SCREEN_COLS
    SCREEN_HEIGHT=$SCREEN_ROWS
}

# ============================================================================
# LIVE MODE INITIALIZATION
# ============================================================================

# Global state for live mode
LIVE_MODE_ACTIVE=false

# Initialize live/animated mode
init_live_mode() {
    LIVE_MODE_ACTIVE=true

    # Save terminal settings and set raw mode for keystroke detection
    SAVED_STTY=$(stty -g 2>/dev/null) || SAVED_STTY=""
    stty -echo -icanon min 0 time 0 2>/dev/null || true

    # Enter alternate screen buffer (like vim, less)
    tput smcup 2>/dev/null || true

    # Hide cursor
    tput civis 2>/dev/null || true

    # Clear screen
    tput clear 2>/dev/null || true

    # Get initial screen size
    get_screen_size

    # Set up cleanup trap
    trap cleanup_live_mode EXIT INT TERM HUP

    # Handle terminal resize
    trap 'get_screen_size; SCREEN_RESIZED=true' WINCH
}

# Cleanup on exit - restore terminal state
cleanup_live_mode() {
    if [[ "$LIVE_MODE_ACTIVE" == "true" ]]; then
        LIVE_MODE_ACTIVE=false

        # Restore terminal settings
        [[ -n "${SAVED_STTY:-}" ]] && stty "$SAVED_STTY" 2>/dev/null || true

        # Show cursor
        tput cnorm 2>/dev/null || true

        # Exit alternate screen buffer
        tput rmcup 2>/dev/null || true

        # Reset terminal
        tput sgr0 2>/dev/null || true
    fi
}

# ============================================================================
# CURSOR CONTROL
# ============================================================================

# Move cursor to position (0-indexed)
cursor_to() {
    local row="${1:-0}"
    local col="${2:-0}"
    tput cup "$row" "$col" 2>/dev/null || true
}

# Move cursor to home position (top-left)
cursor_home() {
    tput cup 0 0 2>/dev/null || true
}

# Save cursor position
cursor_save() {
    tput sc 2>/dev/null || true
}

# Restore cursor position
cursor_restore() {
    tput rc 2>/dev/null || true
}

# Hide cursor
cursor_hide() {
    tput civis 2>/dev/null || true
}

# Show cursor
cursor_show() {
    tput cnorm 2>/dev/null || true
}

# ============================================================================
# SCREEN OPERATIONS
# ============================================================================

# Clear entire screen
screen_clear() {
    tput clear 2>/dev/null || true
}

# Clear from cursor to end of line
clear_to_eol() {
    tput el 2>/dev/null || true
}

# Clear from cursor to end of screen
clear_to_eos() {
    tput ed 2>/dev/null || true
}

# Clear line at specific row
clear_line() {
    local row="$1"
    cursor_to "$row" 0
    clear_to_eol
}

# Clear a region of the screen
clear_region() {
    local start_row="$1"
    local end_row="$2"
    local row

    for ((row=start_row; row<=end_row; row++)); do
        clear_line "$row"
    done
}

# ============================================================================
# BOX DRAWING
# ============================================================================

# Draw a box with optional title
# Usage: draw_box $row $col $width $height ["title"] ["color"]
draw_box() {
    local row="$1"
    local col="$2"
    local width="$3"
    local height="$4"
    local title="${5:-}"
    local color="${6:-$NC}"

    local i
    local inner_width=$((width - 2))

    # Top border
    cursor_to "$row" "$col"
    echo -en "${color}"
    echo -n "┌"

    if [[ -n "$title" ]]; then
        local title_len=${#title}
        local pad_left=$(( (inner_width - title_len - 2) / 2 ))
        local pad_right=$(( inner_width - title_len - 2 - pad_left ))

        printf '─%.0s' $(seq 1 $pad_left)
        echo -n " ${title} "
        printf '─%.0s' $(seq 1 $pad_right)
    else
        printf '─%.0s' $(seq 1 $inner_width)
    fi
    echo -n "┐"

    # Side borders
    for ((i=1; i<height-1; i++)); do
        cursor_to $((row + i)) "$col"
        echo -n "│"
        cursor_to $((row + i)) $((col + width - 1))
        echo -n "│"
    done

    # Bottom border
    cursor_to $((row + height - 1)) "$col"
    echo -n "└"
    printf '─%.0s' $(seq 1 $inner_width)
    echo -n "┘"

    echo -en "${NC}"
}

# Draw a horizontal line
# Usage: draw_hline $row $col $width ["char"] ["color"]
draw_hline() {
    local row="$1"
    local col="$2"
    local width="$3"
    local char="${4:-─}"
    local color="${5:-$NC}"

    cursor_to "$row" "$col"
    echo -en "${color}"
    printf "${char}%.0s" $(seq 1 $width)
    echo -en "${NC}"
}

# Draw a vertical line
# Usage: draw_vline $row $col $height ["char"] ["color"]
draw_vline() {
    local row="$1"
    local col="$2"
    local height="$3"
    local char="${4:-│}"
    local color="${5:-$NC}"

    local i
    echo -en "${color}"
    for ((i=0; i<height; i++)); do
        cursor_to $((row + i)) "$col"
        echo -n "$char"
    done
    echo -en "${NC}"
}

# ============================================================================
# TEXT OUTPUT
# ============================================================================

# Print text at position
# Usage: print_at $row $col "text" ["color"]
print_at() {
    local row="$1"
    local col="$2"
    local text="$3"
    local color="${4:-}"

    cursor_to "$row" "$col"
    if [[ -n "$color" ]]; then
        echo -en "${color}${text}${NC}"
    else
        echo -n "$text"
    fi
}

# Print text centered on row
# Usage: print_centered $row "text" ["color"]
print_centered() {
    local row="$1"
    local text="$2"
    local color="${3:-}"

    local text_len=${#text}
    local col=$(( (SCREEN_COLS - text_len) / 2 ))

    print_at "$row" "$col" "$text" "$color"
}

# Print text right-aligned
# Usage: print_right $row "text" ["color"] [$margin]
print_right() {
    local row="$1"
    local text="$2"
    local color="${3:-}"
    local margin="${4:-1}"

    local text_len=${#text}
    local col=$(( SCREEN_COLS - text_len - margin ))

    print_at "$row" "$col" "$text" "$color"
}

# Print padded text (fills to width)
# Usage: print_padded $row $col $width "text" ["color"]
print_padded() {
    local row="$1"
    local col="$2"
    local width="$3"
    local text="$4"
    local color="${5:-}"

    cursor_to "$row" "$col"
    if [[ -n "$color" ]]; then
        echo -en "${color}"
    fi
    printf "%-${width}s" "$text"
    if [[ -n "$color" ]]; then
        echo -en "${NC}"
    fi
}

# ============================================================================
# BUFFERED OUTPUT
# ============================================================================

# Output buffer for batch rendering
declare -a RENDER_BUFFER=()

# Add line to buffer
buffer_add() {
    RENDER_BUFFER+=("$1")
}

# Clear buffer
buffer_clear() {
    RENDER_BUFFER=()
}

# Flush buffer to screen starting at row
buffer_flush() {
    local start_row="${1:-0}"
    local row="$start_row"

    for line in "${RENDER_BUFFER[@]}"; do
        cursor_to "$row" 0
        echo -e "$line"
        ((row++))
    done

    buffer_clear
}

# ============================================================================
# ANIMATION HELPERS
# ============================================================================

# Spinner state
SPINNER_FRAME=0
SPINNER_CHARS='⠋⠙⠹⠸⠼⠴⠦⠧⠇⠏'

# Get next spinner frame
spinner_next() {
    local char="${SPINNER_CHARS:$SPINNER_FRAME:1}"
    SPINNER_FRAME=$(( (SPINNER_FRAME + 1) % ${#SPINNER_CHARS} ))
    echo -n "$char"
}

# Reset spinner
spinner_reset() {
    SPINNER_FRAME=0
}

# Pulse indicator state
PULSE_FRAME=0
PULSE_CHARS='○◔◑◕●◕◑◔'

# Get next pulse frame
pulse_next() {
    local char="${PULSE_CHARS:$PULSE_FRAME:1}"
    PULSE_FRAME=$(( (PULSE_FRAME + 1) % ${#PULSE_CHARS} ))
    echo -n "$char"
}

# Reset pulse
pulse_reset() {
    PULSE_FRAME=0
}
