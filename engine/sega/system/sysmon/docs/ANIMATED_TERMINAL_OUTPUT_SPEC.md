# SYSMON Animated Terminal Output Specification

## Overview

This document specifies the live auto-updating dashboard feature for **SYSMON**, the FLEET system monitoring utility. The implementation enables real-time monitoring with automatic refresh, similar to `htop` or `watch`.

**Target Project:** SYSMON (Bash)
**Document Purpose:** Implementation reference for live dashboard mode

---

## Table of Contents

1. [Output Modes](#1-output-modes)
2. [ASCII Brand Identity](#2-ascii-brand-identity)
3. [Live Dashboard Architecture](#3-live-dashboard-architecture)
4. [Dashboard Visualizations](#4-dashboard-visualizations)
5. [Progress Indicators](#5-progress-indicators)
6. [Technical Implementation](#6-technical-implementation)
7. [Animation Reference](#7-animation-reference)
8. [File Structure](#8-file-structure)
9. [Implementation Phases](#9-implementation-phases)

---

## 1. Output Modes

### 1.1 Mode Definitions

| Mode | Behavior | Terminal Requirement | Use Case |
|------|----------|---------------------|----------|
| `stream` | One-time output, exits after display (current) | Any | Scripts, piping, CI/CD |
| `live` | Auto-refreshing dashboard with in-place updates | TTY with ANSI support | Interactive monitoring |
| `watch` | Refresh at interval, scroll output | Any TTY | Simple continuous monitoring |
| `quiet` | Minimal output, final result only | Any | Automation, cron jobs |

### 1.2 CLI Interface

```bash
# Live dashboard mode (new)
sysmon dashboard --live                    # Live updating dashboard
sysmon dashboard --live --interval 5       # Custom refresh (default: 3s)
sysmon dashboard --live --quick            # Skip slow metrics in live mode

# Watch mode (simpler alternative)
sysmon dashboard --watch                   # Uses system 'watch' command
sysmon dashboard --watch --interval 10     # Custom interval

# Status with live mode
sysmon status --live                       # Live local status
sysmon status --live --all                 # Live all-instance status

# Projects with live mode
sysmon projects --live                     # Live project metrics

# Current behavior (default)
sysmon dashboard                           # One-time output
sysmon dashboard --quick                   # Quick one-time output
sysmon dashboard -q                        # Quiet mode
```

### 1.3 Environment Variable Override

```bash
# Set default mode
export SYSMON_OUTPUT_MODE=live
export SYSMON_REFRESH_INTERVAL=5

# Or use config file
# ~/.config/sysmon/config
# OUTPUT_MODE=live
# REFRESH_INTERVAL=5
```

### 1.4 Auto-Detection Logic

```
if --live flag provided:
    use live mode (requires TTY)
else if --watch flag provided:
    use watch mode
else if $SYSMON_OUTPUT_MODE set:
    use specified mode
else:
    use "stream" (one-time output)

if live mode requested but not TTY:
    fallback to watch mode with warning
```

---

## 2. ASCII Brand Identity

### 2.1 SYSMON Brand

**Theme:** System monitoring, metrics, infrastructure health
**Color Palette:**
- Cyan (#00FFFF) - primary, headers
- Green (#00FF00) - healthy/good
- Yellow (#FFFF00) - warning
- Red (#FF0000) - critical
- Blue (#0000FF) - informational

### 2.2 Large Banner (Startup)

```
    ╭────────────────────────────────────────────────────────────╮
    │                                                            │
    │     ███████╗██╗   ██╗███████╗███╗   ███╗ ██████╗ ███╗   ██╗│
    │     ██╔════╝╚██╗ ██╔╝██╔════╝████╗ ████║██╔═══██╗████╗  ██║│
    │     ███████╗ ╚████╔╝ ███████╗██╔████╔██║██║   ██║██╔██╗ ██║│
    │     ╚════██║  ╚██╔╝  ╚════██║██║╚██╔╝██║██║   ██║██║╚██╗██║│
    │     ███████║   ██║   ███████║██║ ╚═╝ ██║╚██████╔╝██║ ╚████║│
    │     ╚══════╝   ╚═╝   ╚══════╝╚═╝     ╚═╝ ╚═════╝ ╚═╝  ╚═══╝│
    │                                                            │
    │              FLEET System Monitor  v1.0.0                    │
    │         Disk • CPU • Docker • Multi-Instance               │
    │                                                            │
    ╰────────────────────────────────────────────────────────────╯
```

### 2.3 Compact Banner (Dashboard Header)

```
┌────────────────────────────────────────────────────────────────┐
│  ▓▓▓  SYSMON  │  FLEET System Monitor  │  Live Dashboard         │
│  ▓▓▓          │  Refresh: 3s         │  Press 'q' to quit      │
└────────────────────────────────────────────────────────────────┘
```

### 2.4 Minimal Mark (Inline)

```
[SYSMON]  or  ▓ SYSMON  or  ◉ SYSMON
```

### 2.5 Status Indicators

```
Instance Status:
  ● Online     (green, pulsing in live mode)
  ◐ Checking   (cyan, animated)
  ○ Offline    (gray)
  ⚠ Warning    (yellow)
  ✗ Error      (red)
```

---

## 3. Live Dashboard Architecture

### 3.1 Screen Layout

```
┌─────────────────────────────────────────────────────────────────────────┐
│  ▓▓▓  SYSMON Live Dashboard          │  2025-12-14 13:45:23  │  q=quit  │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                         │
│  ┌─ Instance 1 (203.0.113.10) ● ────────────────────────────────────┐  │
│  │                                                                   │  │
│  │  Disk    [██████████████████░░░░░░░░░░░░░░░░░░░░] 83% (80G/96G)  │  │
│  │  Memory  [██████████████░░░░░░░░░░░░░░░░░░░░░░░░] 42% (3.4G/8G)  │  │
│  │  CPU     [████░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░] 12% ▁▂▃▂▁▂▃▄▃  │  │
│  │                                                                   │  │
│  │  Claude: 8   Tmux: 12   Docker: 4 containers                     │  │
│  │                                                                   │  │
│  └───────────────────────────────────────────────────────────────────┘  │
│                                                                         │
│  ┌─ Instance 2 (203.0.113.20) ● ───────────────────────────────────┐  │
│  │                                                                   │  │
│  │  Disk    [████████████████████████░░░░░░░░░░░░░░] 65% (62G/96G)  │  │
│  │  Memory  [██████████████████░░░░░░░░░░░░░░░░░░░░] 51% (4.1G/8G)  │  │
│  │  CPU     [██████░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░] 18% ▂▃▄▅▄▃▂▁▂  │  │
│  │                                                                   │  │
│  │  Claude: 5   Tmux: 8    Docker: 6 containers                     │  │
│  │                                                                   │  │
│  └───────────────────────────────────────────────────────────────────┘  │
│                                                                         │
│  ┌─ Local System ● ─────────────────────────────────────────────────┐  │
│  │                                                                   │  │
│  │  Disk    [████████████░░░░░░░░░░░░░░░░░░░░░░░░░░] 31% (264G/926G)│  │
│  │  Memory  [██████████████████░░░░░░░░░░░░░░░░░░░░] 47% (14G/30G)  │  │
│  │  CPU     [████████░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░] 24% ▃▄▅▆▅▄▃▂▃  │  │
│  │                                                                   │  │
│  │  Claude: 39  Tmux: 46   Docker: 1 container                      │  │
│  │                                                                   │  │
│  └───────────────────────────────────────────────────────────────────┘  │
│                                                                         │
│  ─── Alerts ───────────────────────────────────────────────────────── │
│  ⚠ Instance 1 disk usage above 80% threshold                          │
│                                                                         │
│  Last refresh: 2s ago  │  Next: 1s  │  ↑↓ scroll  │  r=refresh now    │
└─────────────────────────────────────────────────────────────────────────┘
```

### 3.2 Keyboard Controls

| Key | Action |
|-----|--------|
| `q` | Quit dashboard |
| `r` | Force immediate refresh |
| `+` / `-` | Increase/decrease refresh interval |
| `1` / `2` / `3` | Focus on Instance 1 / 2 / Local |
| `a` | Show all instances (default) |
| `d` | Toggle detailed view |
| `h` | Toggle help overlay |
| `↑` / `↓` | Scroll (if content exceeds screen) |

### 3.3 Refresh Cycle

```
┌─────────────────────────────────────────────────────────────┐
│  Refresh Cycle (3 seconds default)                          │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  t=0.0s   Start refresh                                     │
│           ├─ Spawn parallel SSH connections                │
│           │   Instance 1 ──┐                               │
│           │   Instance 2 ──┼── Collect metrics             │
│           │   Local ───────┘                               │
│                                                             │
│  t=1.5s   Metrics received (typical)                        │
│           ├─ Parse results                                  │
│           ├─ Calculate deltas (CPU sparkline)              │
│           └─ Update display buffer                          │
│                                                             │
│  t=1.6s   Render to screen                                  │
│           ├─ Clear screen (optional) or cursor home        │
│           ├─ Draw updated content                          │
│           └─ Update status line                            │
│                                                             │
│  t=3.0s   Next refresh cycle                                │
│                                                             │
└─────────────────────────────────────────────────────────────┘
```

---

## 4. Dashboard Visualizations

### 4.1 Resource Gauges

#### Horizontal Bar (Primary)
```
Disk    [██████████████████░░░░░░░░░░░░░░░░░░░░] 83% (80G/96G)
        └─ filled ─────────┘└─ empty ──────────┘
```

#### Color Thresholds
```
0-50%:   Green   [████████████████████░░░░░░░░░░░░░░░░░░░░]
50-75%:  Cyan    [████████████████████████████░░░░░░░░░░░░]
75-90%:  Yellow  [████████████████████████████████████░░░░]
90-100%: Red     [████████████████████████████████████████]
```

#### Compact Gauges (When Space Limited)
```
D:83% M:42% C:12%     or     D[▓▓▓▓░] M[▓▓░░░] C[▓░░░░]
```

### 4.2 CPU Sparkline History

Shows last 10 readings as a mini graph:
```
CPU     [████░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░] 12% ▁▂▃▂▁▂▃▄▃▂
                                                    └─ history ─┘
```

Sparkline characters (8 levels):
```
▁ (1/8)  ▂ (2/8)  ▃ (3/8)  ▄ (4/8)  ▅ (5/8)  ▆ (6/8)  ▇ (7/8)  █ (8/8)
```

### 4.3 Instance Status Panel

#### Healthy Instance
```
┌─ Instance 1 (203.0.113.10) ● ────────────────────────────────────┐
│                                                                   │
│  Disk    [██████████████████░░░░░░░░░░░░░░░░░░░░] 83% (80G/96G)  │
│  Memory  [██████████████░░░░░░░░░░░░░░░░░░░░░░░░] 42% (3.4G/8G)  │
│  CPU     [████░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░] 12% ▁▂▃▂▁▂▃▄▃  │
│                                                                   │
│  Claude: 8   Tmux: 12   Docker: 4 containers                     │
│                                                                   │
└───────────────────────────────────────────────────────────────────┘
```

#### Unreachable Instance
```
┌─ Instance 2 (203.0.113.20) ✗ ───────────────────────────────────┐
│                                                                   │
│                    ┌─────────────────────┐                       │
│                    │  CONNECTION FAILED  │                       │
│                    │                     │                       │
│                    │  SSH timeout after  │                       │
│                    │  10 seconds         │                       │
│                    │                     │                       │
│                    │  Last seen: 5m ago  │                       │
│                    └─────────────────────┘                       │
│                                                                   │
└───────────────────────────────────────────────────────────────────┘
```

#### Loading State (During Refresh)
```
┌─ Instance 1 (203.0.113.10) ◐ ────────────────────────────────────┐
│                                                                   │
│  Disk    [████████████████████████████████████░░] 83% (80G/96G)  │
│  Memory  [████████████████████░░░░░░░░░░░░░░░░░░] 42%  ← stale   │
│  CPU     ⠋ Collecting metrics...                                  │
│                                                                   │
└───────────────────────────────────────────────────────────────────┘
```

### 4.4 Detailed View (Toggle with 'd')

```
┌─ Instance 1 DETAILED (203.0.113.10) ● ───────────────────────────┐
│                                                                   │
│  ─── Storage ───────────────────────────────────────────────────  │
│  Disk    [██████████████████░░░░░░░░░░░░░░░░░░░░] 83% (80G/96G)  │
│                                                                   │
│  Breakdown:                                                       │
│    FLEET Directory     22G  ████████████████                       │
│    Shared venv        5.6G ████████                              │
│    Preserves          3.5G █████                                 │
│    Other             48.9G ██████████████████████████████        │
│                                                                   │
│  ─── Compute ───────────────────────────────────────────────────  │
│  Memory  [██████████████░░░░░░░░░░░░░░░░░░░░░░░░] 42% (3.4G/8G)  │
│  CPU     [████░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░] 12% ▁▂▃▂▁▂▃▄▃  │
│  Load Avg: 0.45, 0.52, 0.48                                      │
│                                                                   │
│  ─── Docker ────────────────────────────────────────────────────  │
│  Containers: 4 running                                           │
│    atlas-db        CPU: 2.1%   Mem: 512MB                   │
│    orion-redis          CPU: 0.3%   Mem: 128MB                   │
│    hermes-postgres  CPU: 1.8%   Mem: 256MB                   │
│    altair-mongo       CPU: 0.5%   Mem: 384MB                   │
│                                                                   │
│  ─── Sessions ──────────────────────────────────────────────────  │
│  Claude: 8 sessions   Tmux: 12 sessions                         │
│                                                                   │
└───────────────────────────────────────────────────────────────────┘
```

### 4.5 Alert Panel

```
─── Alerts ─────────────────────────────────────────────────────────
⚠ Instance 1 disk usage at 83% (threshold: 80%)
⚠ Instance 2 memory usage at 89% (threshold: 85%)
✗ Instance 2 SSH connection intermittent (2 failures in last 5min)
```

Alert severity colors:
- `✗` Red: Critical (>90% usage, connection failures)
- `⚠` Yellow: Warning (>75% usage, slow responses)
- `ℹ` Cyan: Info (notable but not problematic)

---

## 5. Progress Indicators

### 5.1 Collection Progress

During initial data collection:
```
┌────────────────────────────────────────────────────────────────┐
│  ▓▓▓  SYSMON  │  Initializing Live Dashboard                   │
├────────────────────────────────────────────────────────────────┤
│                                                                 │
│  Collecting initial metrics...                                  │
│                                                                 │
│  ├─ ✓ Local system          complete                           │
│  ├─ ⠙ Instance 1            connecting...                      │
│  └─ ○ Instance 2            waiting                            │
│                                                                 │
│  [████████████░░░░░░░░░░░░░░░░░░░░░░░░░░░░] 33% (1/3)          │
│                                                                 │
└────────────────────────────────────────────────────────────────┘
```

### 5.2 Refresh Indicator

Status line shows refresh state:
```
Refreshing ⠋  │  Last: 2s ago  │  Next: 1s
Refreshing ⠙  │  Last: 2s ago  │  Next: 1s
Refreshing ⠹  │  Last: 2s ago  │  Next: 1s
...
Ready ●       │  Last: 0s ago  │  Next: 3s
```

### 5.3 Spinner Patterns

```
Braille dots (smooth):  ⠋ ⠙ ⠹ ⠸ ⠼ ⠴ ⠦ ⠧ ⠇ ⠏
Simple:                 | / - \
Circle:                 ◐ ◓ ◑ ◒
Pulse:                  ○ ◔ ◑ ◕ ● ◕ ◑ ◔
```

---

## 6. Technical Implementation

### 6.1 Bash Implementation Strategy

#### Terminal Control
```bash
# Cursor control
tput clear          # Clear screen
tput cup 0 0        # Move cursor to top-left
tput civis          # Hide cursor
tput cnorm          # Show cursor (on exit)
tput sc             # Save cursor position
tput rc             # Restore cursor position

# Screen dimensions
COLS=$(tput cols)
ROWS=$(tput lines)

# Alternate screen buffer (like vim, less)
tput smcup          # Enter alternate buffer
tput rmcup          # Exit alternate buffer
```

#### Color Codes (Extended)
```bash
# Already in common.sh, add:
BRIGHT_GREEN='\033[92m'
BRIGHT_RED='\033[91m'
BRIGHT_YELLOW='\033[93m'
BRIGHT_CYAN='\033[96m'
BG_RED='\033[41m'
BG_GREEN='\033[42m'
BG_YELLOW='\033[43m'
```

### 6.2 New Module Structure

```
utilities/sysmon/
├── sysmon                      # Main entry (MODIFY: add --live flag)
├── lib/
│   ├── common.sh               # (MODIFY: add tput utilities)
│   ├── config.sh               # (MODIFY: add REFRESH_INTERVAL)
│   ├── collectors.sh           # (existing)
│   └── display/                # NEW DIRECTORY
│       ├── render.sh           # Screen rendering functions
│       ├── widgets.sh          # Progress bars, gauges, sparklines
│       ├── layout.sh           # Screen layout management
│       └── input.sh            # Keyboard input handling
├── commands/
│   ├── dashboard.sh            # (MODIFY: add live mode)
│   ├── status.sh               # (MODIFY: add live mode)
│   ├── live.sh                 # NEW: Live dashboard command
│   └── ...
└── docs/
    └── ANIMATED_TERMINAL_OUTPUT_SPEC.md  # This file
```

### 6.3 Core Functions

#### lib/display/render.sh
```bash
#!/bin/bash
# Screen rendering utilities

# Initialize live mode
init_live_mode() {
    # Enter alternate screen buffer
    tput smcup
    # Hide cursor
    tput civis
    # Clear screen
    tput clear
    # Set up cleanup trap
    trap cleanup_live_mode EXIT INT TERM
}

# Cleanup on exit
cleanup_live_mode() {
    # Show cursor
    tput cnorm
    # Exit alternate buffer
    tput rmcup
}

# Move cursor to position
move_cursor() {
    local row=$1 col=$2
    tput cup "$row" "$col"
}

# Clear line at position
clear_line() {
    local row=$1
    move_cursor "$row" 0
    tput el  # Clear to end of line
}

# Draw box
draw_box() {
    local row=$1 col=$2 width=$3 height=$4 title="$5"
    local i

    # Top border
    move_cursor "$row" "$col"
    echo -n "┌─"
    [[ -n "$title" ]] && echo -n " $title "
    for ((i=${#title}+4; i<width-1; i++)); do echo -n "─"; done
    echo -n "┐"

    # Sides
    for ((i=1; i<height-1; i++)); do
        move_cursor $((row+i)) "$col"
        echo -n "│"
        move_cursor $((row+i)) $((col+width-1))
        echo -n "│"
    done

    # Bottom border
    move_cursor $((row+height-1)) "$col"
    echo -n "└"
    for ((i=1; i<width-1; i++)); do echo -n "─"; done
    echo -n "┘"
}
```

#### lib/display/widgets.sh
```bash
#!/bin/bash
# Widget rendering utilities

# Draw progress bar
# Usage: draw_progress_bar $value $max $width $row $col
draw_progress_bar() {
    local value=$1 max=$2 width=$3 row=$4 col=$5
    local pct=$((value * 100 / max))
    local filled=$((pct * (width - 2) / 100))
    local empty=$((width - 2 - filled))

    # Color based on percentage
    local color
    if ((pct >= 90)); then color="$RED"
    elif ((pct >= 75)); then color="$YELLOW"
    elif ((pct >= 50)); then color="$CYAN"
    else color="$GREEN"
    fi

    move_cursor "$row" "$col"
    echo -n "["
    echo -en "$color"
    printf '█%.0s' $(seq 1 $filled)
    echo -en "$NC"
    printf '░%.0s' $(seq 1 $empty)
    echo -n "] ${pct}%"
}

# Draw sparkline from array of values
# Usage: draw_sparkline "${values[@]}"
draw_sparkline() {
    local -a values=("$@")
    local chars='▁▂▃▄▅▆▇█'
    local max=0 min=999999
    local v

    # Find range
    for v in "${values[@]}"; do
        ((v > max)) && max=$v
        ((v < min)) && min=$v
    done

    local range=$((max - min))
    ((range == 0)) && range=1

    # Draw sparkline
    for v in "${values[@]}"; do
        local level=$(( (v - min) * 7 / range ))
        echo -n "${chars:$level:1}"
    done
}

# Draw gauge with label
# Usage: draw_gauge "Disk" 83 96 40 5 2
draw_labeled_gauge() {
    local label=$1 used=$2 total=$3 width=$4 row=$5 col=$6
    local pct=$((used * 100 / total))

    move_cursor "$row" "$col"
    printf "%-8s" "$label"
    draw_progress_bar "$used" "$total" "$((width - 20))" "$row" "$((col + 8))"
    printf " (%dG/%dG)" "$used" "$total"
}
```

#### lib/display/input.sh
```bash
#!/bin/bash
# Non-blocking keyboard input handling

# Read single keypress (non-blocking)
read_key() {
    local key
    IFS= read -rsn1 -t 0.1 key 2>/dev/null
    echo "$key"
}

# Main input handler
handle_input() {
    local key=$(read_key)

    case "$key" in
        q|Q) return 1 ;;                    # Quit
        r|R) FORCE_REFRESH=true ;;          # Force refresh
        +)   ((REFRESH_INTERVAL++)) ;;      # Increase interval
        -)   ((REFRESH_INTERVAL > 1)) && ((REFRESH_INTERVAL--)) ;;
        1)   FOCUS_INSTANCE=1 ;;
        2)   FOCUS_INSTANCE=2 ;;
        3)   FOCUS_INSTANCE=local ;;
        a|A) FOCUS_INSTANCE=all ;;
        d|D) DETAILED_VIEW=$((1 - DETAILED_VIEW)) ;;
        h|H) SHOW_HELP=$((1 - SHOW_HELP)) ;;
    esac
    return 0
}
```

### 6.4 Main Live Loop

```bash
# commands/live.sh or integrated into dashboard.sh

run_live_dashboard() {
    local interval="${1:-3}"

    # Initialize
    init_live_mode
    init_metrics_history

    local last_refresh=0
    local running=true

    while $running; do
        local now=$(date +%s)

        # Handle keyboard input
        if ! handle_input; then
            running=false
            break
        fi

        # Check if refresh needed
        if [[ "$FORCE_REFRESH" == "true" ]] || \
           ((now - last_refresh >= interval)); then

            FORCE_REFRESH=false
            last_refresh=$now

            # Collect metrics (parallel)
            collect_all_metrics_async

            # Wait for results
            wait_for_metrics

            # Update history for sparklines
            update_metrics_history

            # Render screen
            render_dashboard
        fi

        # Update status line (countdown)
        update_status_line $((interval - (now - last_refresh)))

        # Small sleep to prevent CPU spin
        sleep 0.1
    done

    cleanup_live_mode
}
```

### 6.5 Parallel Metric Collection

```bash
# lib/collectors.sh additions

collect_all_metrics_async() {
    # Create temp files for results
    local tmp_local="/tmp/sysmon_live_local_$$"
    local tmp_i1="/tmp/sysmon_live_i1_$$"
    local tmp_i2="/tmp/sysmon_live_i2_$$"

    # Start parallel collection
    collect_local_metrics > "$tmp_local" 2>/dev/null &
    local pid_local=$!

    collect_remote_metrics 1 "true" > "$tmp_i1" 2>/dev/null &
    local pid_i1=$!

    collect_remote_metrics 2 "true" > "$tmp_i2" 2>/dev/null &
    local pid_i2=$!

    # Store PIDs for wait
    METRIC_PIDS=($pid_local $pid_i1 $pid_i2)
    METRIC_FILES=("$tmp_local" "$tmp_i1" "$tmp_i2")
}

wait_for_metrics() {
    local timeout=10
    local i

    for i in "${!METRIC_PIDS[@]}"; do
        if ! wait_with_timeout "${METRIC_PIDS[$i]}" "$timeout"; then
            # Mark as failed
            echo "FAILED" > "${METRIC_FILES[$i]}"
        fi
    done

    # Read results
    METRICS_LOCAL=$(cat "${METRIC_FILES[0]}" 2>/dev/null)
    METRICS_I1=$(cat "${METRIC_FILES[1]}" 2>/dev/null)
    METRICS_I2=$(cat "${METRIC_FILES[2]}" 2>/dev/null)

    # Cleanup
    rm -f "${METRIC_FILES[@]}"
}
```

---

## 7. Animation Reference

### 7.1 Spinner Patterns

| Name | Frames | Use Case |
|------|--------|----------|
| Braille | `⠋⠙⠹⠸⠼⠴⠦⠧⠇⠏` | Loading, collecting |
| Pulse | `○◔◑◕●◕◑◔` | Status checking |
| Simple | `\|/-` | Fallback |
| Circle | `◐◓◑◒` | Connection status |

### 7.2 Status Symbols

| Symbol | Meaning | Color |
|--------|---------|-------|
| `●` | Healthy/Active | Green |
| `○` | Inactive/Pending | Gray |
| `◐` | In Progress | Cyan |
| `✓` | Complete/Success | Green |
| `✗` | Error/Failed | Red |
| `⚠` | Warning | Yellow |
| `ℹ` | Info | Cyan |

### 7.3 Progress Bar Styles

```
Block:       [████████████░░░░░░░░]
Thin:        [━━━━━━━━━━━━────────]
Gradient:    [██████▓▓▓▓░░░░░░░░░░]
ASCII:       [============--------]
```

### 7.4 Sparkline Characters

```
Height levels (8): ▁ ▂ ▃ ▄ ▅ ▆ ▇ █

Example readings: 10, 25, 40, 35, 20, 15, 30, 45, 50, 35
Sparkline:        ▁▂▄▃▂▁▃▅▆▃
```

### 7.5 Box Drawing

```
Light:    ┌ ─ ┐ │ └ ┘ ├ ┤ ┬ ┴ ┼
Heavy:    ┏ ━ ┓ ┃ ┗ ┛ ┣ ┫ ┳ ┻ ╋
Double:   ╔ ═ ╗ ║ ╚ ╝ ╠ ╣ ╦ ╩ ╬
Rounded:  ╭ ─ ╮ │ ╰ ╯
```

---

## 8. File Structure

### 8.1 Files to Create

```
utilities/sysmon/
├── lib/
│   └── display/                # NEW DIRECTORY
│       ├── render.sh           # Screen control, box drawing
│       ├── widgets.sh          # Progress bars, gauges, sparklines
│       ├── layout.sh           # Dashboard layout management
│       └── input.sh            # Non-blocking keyboard input
└── docs/
    └── ANIMATED_TERMINAL_OUTPUT_SPEC.md  # This file
```

### 8.2 Files to Modify

```
utilities/sysmon/
├── sysmon                      # ADD: --live, --watch flags
├── lib/
│   ├── common.sh               # ADD: tput utilities, extended colors
│   └── config.sh               # ADD: REFRESH_INTERVAL default
└── commands/
    ├── dashboard.sh            # ADD: --live mode integration
    └── status.sh               # ADD: --live mode support
```

---

## 9. Implementation Phases

### Phase 1: Foundation

**Goal:** Add terminal control utilities without changing behavior

- [ ] Create `lib/display/` directory structure
- [ ] Implement `render.sh` with basic tput utilities
- [ ] Implement `widgets.sh` with progress bar function
- [ ] Add `--live` flag parsing (inactive)
- [ ] Add `SYSMON_REFRESH_INTERVAL` config option

**Deliverable:** New files exist, no behavior change

### Phase 2: Widget Library

**Goal:** Complete widget library

- [ ] Implement sparkline drawing
- [ ] Implement labeled gauge widget
- [ ] Implement box drawing functions
- [ ] Implement status indicators
- [ ] Test widgets in isolation

**Deliverable:** All widgets work standalone

### Phase 3: Input Handling

**Goal:** Non-blocking keyboard input

- [ ] Implement `input.sh` with key reading
- [ ] Implement key handler dispatch
- [ ] Test keyboard controls
- [ ] Handle terminal resize (SIGWINCH)

**Deliverable:** Responsive keyboard handling

### Phase 4: Live Dashboard

**Goal:** Working live mode

- [ ] Implement main refresh loop
- [ ] Integrate parallel metric collection
- [ ] Implement full dashboard layout
- [ ] Add metrics history for sparklines
- [ ] Test on different terminal sizes

**Deliverable:** `sysmon dashboard --live` works

### Phase 5: Polish

**Goal:** Production-ready

- [ ] Add help overlay (h key)
- [ ] Add detailed view toggle (d key)
- [ ] Optimize refresh performance
- [ ] Add graceful degradation for non-TTY
- [ ] Update documentation and help text
- [ ] Add `--watch` mode as fallback

**Deliverable:** Feature-complete live dashboard

---

## References

### Internal
- ORION/Atlas Animation Spec: `~/fleet/docs/architecture/terminal-animation/ANIMATED_TERMINAL_OUTPUT_SPEC.md`
- SYSMON main: `~/fleet/utilities/sysmon/sysmon`
- SYSMON dashboard: `~/fleet/utilities/sysmon/commands/dashboard.sh`
- SYSMON common lib: `~/fleet/utilities/sysmon/lib/common.sh`

### External
- Bash tput reference: https://tldp.org/HOWTO/Bash-Prompt-HOWTO/x405.html
- ANSI escape codes: https://en.wikipedia.org/wiki/ANSI_escape_code
- Sparkline inspiration: https://github.com/holman/spark

---

*Document Version: 1.0*
*Created: 2025-12-14*
*Project: SYSMON*
