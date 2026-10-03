#!/bin/bash
# ============================================================================
# SYSMON - Dashboard Command
# ============================================================================
# Multi-instance dashboard with 4-table view
# Supports both static and animated (live) modes
# ============================================================================

# Debug log file
SYSMON_DEBUG_LOG="${HOME}/.cache/sysmon/dashboard_debug.log"
SYSMON_DEBUG="${SYSMON_DEBUG:-false}"

# Debug logging function
debug_log() {
    if [[ "${SYSMON_DEBUG:-false}" == "true" ]]; then
        echo "[$(date '+%Y-%m-%d %H:%M:%S')] $*" >> "$SYSMON_DEBUG_LOG"
    fi
}

# Error handler
dashboard_error_handler() {
    local line=$1
    local cmd=$2
    local code=$3
    debug_log "ERROR at line $line: command '$cmd' exited with code $code"
    echo "Error at line $line: $cmd (exit $code)" >> "$SYSMON_DEBUG_LOG"
}

# Help text for this command
cmd_dashboard_help() {
    cat << 'EOF'
sysmon dashboard - Multi-instance dashboard

Usage: sysmon dashboard [options]

Options:
  --quick       Skip database volume sizing (faster)
  --animate     Enable live auto-updating dashboard
  --interval N  Refresh interval in seconds (default: 3, requires --animate)
  --debug       Enable debug logging to ~/.cache/sysmon/dashboard_debug.log
  --help        Show this help

Output includes:
  - Instance 1 metrics (disk, memory, CPU, Docker, sessions)
  - Instance 2 metrics
  - Local system metrics
  - Summary comparison table

Dashboard Pages (animated mode):
  Page 1: Overview      - Instance panels with disk/memory/CPU
  Page 2: Storage       - Detailed node_modules, venvs, build dirs, caches
  Page 3: Docker        - Container stats, database volumes
  Page 4: Process/CPU   - Detailed process list and CPU metrics
  Page 5: Time Series   - CPU/memory/disk history graphs
  Page 6: Services      - Non-Docker services (Node.js frontends, Python backends)

Animated Mode Controls:
  q, Esc           Quit dashboard
  r, Space         Refresh now
  ←, →             Change refresh interval
  ↑, PgUp, p       Previous page
  ↓, PgDn, n, Tab  Next page
  F1-F6, 1-6       Jump to specific page
  l                Focus Local instance
  a                Show all (default)
  d                Toggle detailed view
  h, ?             Show help overlay

Examples:
  sysmon dashboard                     # Static dashboard
  sysmon dashboard --quick             # Quick mode, skip DB sizing
  sysmon dashboard --animate           # Live auto-updating dashboard
  sysmon dashboard --animate --interval 5  # Custom refresh rate
EOF
}

# Print table header
print_table_header() {
    local title="$1"
    local instance_ip="$2"
    echo ""
    echo -e "${CYAN}${BOLD}━━━ $title ($instance_ip) ━━━${NC}"
    echo ""
}

# Print storage table for an instance
print_storage_table() {
    local metrics="$1"
    local quick_mode="$2"

    # Parse storage metrics
    local disk_info fleet_size venv_size preserves_size
    disk_info=$(echo "$metrics" | grep -A1 "^DISK_INFO:" | tail -1)
    fleet_size=$(echo "$metrics" | grep -A1 "^FLEET_SIZE:" | tail -1)
    venv_size=$(echo "$metrics" | grep -A1 "^VENV_SIZE:" | tail -1)
    preserves_size=$(echo "$metrics" | grep -A1 "^PRESERVES_SIZE:" | tail -1)

    # Parse disk fields
    IFS='|' read -r total used avail pct <<< "$disk_info"

    # Color-code disk usage
    local pct_num="${pct%\%}"
    local pct_display
    pct_display=$(colored_percentage "$pct" "$DISK_WARNING_THRESHOLD" "$DISK_CRITICAL_THRESHOLD")

    echo "| Category | Total | Used | Available | Usage |"
    echo "|----------|-------|------|-----------|-------|"
    echo "| Disk | $total | $used | $avail | $pct_display |"
    echo "| FLEET Directory | - | $fleet_size | - | - |"
    echo "| Shared venv | - | $venv_size | - | - |"
    echo "| Preserves | - | $preserves_size | - | - |"
    echo ""

    # Docker storage
    local docker_running
    docker_running=$(echo "$metrics" | grep -A1 "^DOCKER_RUNNING:" | tail -1)

    if [[ "$docker_running" == "true" ]]; then
        echo "**Docker Storage**:"
        # Try to get docker system df output if available
        if echo "$metrics" | grep -q "^DOCKER_DISK:"; then
            local docker_stats
            docker_stats=$(echo "$metrics" | awk '/^DOCKER_DISK:/{flag=1;next}/^[A-Z_]+:/{flag=0}flag')
            if [[ -n "$docker_stats" ]]; then
                echo "| Type | Size | Reclaimable |"
                echo "|------|------|-------------|"
                echo "$docker_stats" | while IFS='|' read -r type size reclaim; do
                    [[ -z "$type" ]] && continue
                    echo "| $type | $size | $reclaim |"
                done
            else
                echo "_No docker disk data available_"
            fi
        else
            echo "_Docker disk information not available in quick mode_"
        fi
        echo ""

        # Database volumes (only if DB_VOLUMES section exists in metrics)
        if [[ "$quick_mode" != "true" ]] && echo "$metrics" | grep -q "^DB_VOLUMES:"; then
            echo "**Database Volumes**:"
            local db_volumes
            # Extract only the lines between DB_VOLUMES: and the next marker, excluding both markers
            db_volumes=$(echo "$metrics" | awk '/^DB_VOLUMES:/{flag=1;next}/^[A-Z_]+:/{flag=0}flag')

            if [[ -n "$db_volumes" ]]; then
                echo "| Project | Type | Size |"
                echo "|---------|------|------|"
                echo "$db_volumes" | while IFS='|' read -r project vol_type size; do
                    [[ -z "$project" ]] && continue
                    echo "| $project | $vol_type | $size |"
                done
            else
                echo "_No database volumes found_"
            fi
            echo ""
        fi
    else
        echo "_Docker not running_"
        echo ""
    fi
}

# Print CPU/usage table for an instance
print_cpu_table() {
    local metrics="$1"

    # Parse CPU metrics
    local load_avg cpu_pct memory docker_running container_count claude_count tmux_count
    load_avg=$(echo "$metrics" | grep -A1 "^LOAD_AVG:" | tail -1)
    cpu_pct=$(echo "$metrics" | grep -A1 "^CPU_PCT:" | tail -1)
    memory=$(echo "$metrics" | grep -A1 "^MEMORY:" | tail -1)
    docker_running=$(echo "$metrics" | grep -A1 "^DOCKER_RUNNING:" | tail -1)
    container_count=$(echo "$metrics" | grep -A1 "^CONTAINER_COUNT:" | tail -1)
    claude_count=$(echo "$metrics" | grep -A1 "^CLAUDE_COUNT:" | tail -1)
    tmux_count=$(echo "$metrics" | grep -A1 "^TMUX_COUNT:" | tail -1)

    # Parse memory
    IFS='|' read -r mem_total mem_used mem_free mem_avail mem_pct <<< "$memory"

    # Color code values
    local cpu_display mem_display
    cpu_display=$(colored_percentage "${cpu_pct}%" "$CPU_WARNING_THRESHOLD" "$CPU_CRITICAL_THRESHOLD")
    mem_display=$(colored_percentage "$mem_pct" "$MEM_WARNING_THRESHOLD" "$MEM_CRITICAL_THRESHOLD")

    echo "| Metric | Value |"
    echo "|--------|-------|"
    echo "| Load Average | $load_avg |"
    echo "| CPU Usage | $cpu_display |"
    echo "| Memory | $mem_used / $mem_total ($mem_display) |"
    echo "| Claude Sessions | $claude_count |"
    echo "| Tmux Sessions | $tmux_count |"

    if [[ "$docker_running" == "true" ]]; then
        echo "| Docker Containers | $container_count |"
    else
        echo "| Docker | Not running |"
    fi
    echo ""

    # Top processes
    echo "**Top Processes**:"
    local top_procs
    top_procs=$(echo "$metrics" | awk '/^TOP_PROCESSES:/{flag=1;next}/^[A-Z_]+:/{flag=0}flag' | head -5)

    if [[ -n "$top_procs" ]]; then
        echo "| User | CPU | Mem | Command |"
        echo "|------|-----|-----|---------|"
        echo "$top_procs" | while IFS='|' read -r user cpu mem cmd; do
            [[ -z "$user" ]] && continue
            echo "| $user | $cpu | $mem | $cmd |"
        done
    fi
    echo ""

    # Docker container stats
    if [[ "$docker_running" == "true" && "$container_count" -gt 0 ]]; then
        echo "**Container Stats**:"
        local container_stats
        container_stats=$(echo "$metrics" | awk '/^DOCKER_STATS:/{flag=1;next}/^[A-Z_]+:/{flag=0}flag' | head -10)

        if [[ -n "$container_stats" ]]; then
            echo "| Container | CPU | Memory | Mem % |"
            echo "|-----------|-----|--------|-------|"
            echo "$container_stats" | while IFS='|' read -r name cpu mem mem_pct; do
                [[ -z "$name" ]] && continue
                echo "| $name | $cpu | $mem | $mem_pct |"
            done
        fi
        echo ""
    fi
}

# Print summary comparison table
print_summary_table() {
    local metrics1="$1"
    local metrics2="$2"
    local metrics3="$3"

    echo ""
    echo -e "${CYAN}${BOLD}━━━ SUMMARY COMPARISON ━━━${NC}"
    echo ""

    # Extract key metrics from all instances
    local disk1 disk2 disk3 cpu1 cpu2 cpu3 mem1 mem2 mem3 claude1 claude2 claude3 docker1 docker2 docker3

    disk1=$(echo "$metrics1" | grep -A1 "^DISK_INFO:" | tail -1 | cut -d'|' -f4)
    disk2=$(echo "$metrics2" | grep -A1 "^DISK_INFO:" | tail -1 | cut -d'|' -f4)
    disk3=$(echo "$metrics3" | grep -A1 "^DISK_INFO:" | tail -1 | cut -d'|' -f4)
    cpu1=$(echo "$metrics1" | grep -A1 "^CPU_PCT:" | tail -1)
    cpu2=$(echo "$metrics2" | grep -A1 "^CPU_PCT:" | tail -1)
    cpu3=$(echo "$metrics3" | grep -A1 "^CPU_PCT:" | tail -1)
    mem1=$(echo "$metrics1" | grep -A1 "^MEMORY:" | tail -1 | cut -d'|' -f5)
    mem2=$(echo "$metrics2" | grep -A1 "^MEMORY:" | tail -1 | cut -d'|' -f5)
    mem3=$(echo "$metrics3" | grep -A1 "^MEMORY:" | tail -1 | cut -d'|' -f5)
    claude1=$(echo "$metrics1" | grep -A1 "^CLAUDE_COUNT:" | tail -1)
    claude2=$(echo "$metrics2" | grep -A1 "^CLAUDE_COUNT:" | tail -1)
    claude3=$(echo "$metrics3" | grep -A1 "^CLAUDE_COUNT:" | tail -1)
    docker1=$(echo "$metrics1" | grep -A1 "^CONTAINER_COUNT:" | tail -1)
    docker2=$(echo "$metrics2" | grep -A1 "^CONTAINER_COUNT:" | tail -1)
    docker3=$(echo "$metrics3" | grep -A1 "^CONTAINER_COUNT:" | tail -1)

    # Color code
    local disk1_display disk2_display disk3_display cpu1_display cpu2_display cpu3_display mem1_display mem2_display mem3_display
    disk1_display=$(colored_percentage "$disk1" "$DISK_WARNING_THRESHOLD" "$DISK_CRITICAL_THRESHOLD")
    disk2_display=$(colored_percentage "$disk2" "$DISK_WARNING_THRESHOLD" "$DISK_CRITICAL_THRESHOLD")
    disk3_display=$(colored_percentage "$disk3" "$DISK_WARNING_THRESHOLD" "$DISK_CRITICAL_THRESHOLD")
    cpu1_display=$(colored_percentage "${cpu1}%" "$CPU_WARNING_THRESHOLD" "$CPU_CRITICAL_THRESHOLD")
    cpu2_display=$(colored_percentage "${cpu2}%" "$CPU_WARNING_THRESHOLD" "$CPU_CRITICAL_THRESHOLD")
    cpu3_display=$(colored_percentage "${cpu3}%" "$CPU_WARNING_THRESHOLD" "$CPU_CRITICAL_THRESHOLD")
    mem1_display=$(colored_percentage "$mem1" "$MEM_WARNING_THRESHOLD" "$MEM_CRITICAL_THRESHOLD")
    mem2_display=$(colored_percentage "$mem2" "$MEM_WARNING_THRESHOLD" "$MEM_CRITICAL_THRESHOLD")
    mem3_display=$(colored_percentage "$mem3" "$MEM_WARNING_THRESHOLD" "$MEM_CRITICAL_THRESHOLD")

    echo "| Metric | Instance 1 | Instance 2 | Instance 3 |"
    echo "|--------|------------|------------|------------|"
    echo "| Disk Usage | $disk1_display | $disk2_display | $disk3_display |"
    echo "| CPU Usage | $cpu1_display | $cpu2_display | $cpu3_display |"
    echo "| Memory Usage | $mem1_display | $mem2_display | $mem3_display |"
    echo "| Claude Sessions | $claude1 | $claude2 | $claude3 |"
    echo "| Docker Containers | $docker1 | $docker2 | $docker3 |"
    echo ""
}

# ============================================================================
# ANIMATED DASHBOARD MODE
# ============================================================================

# Global state for animated mode
declare -a CPU_HISTORY_I1=()
declare -a CPU_HISTORY_I2=()
declare -a CPU_HISTORY_I3=()
declare -a CPU_HISTORY_LOCAL=()
ANIMATE_DETAILED=false
ANIMATE_FOCUS="all"
ANIMATE_SHOW_HELP=false
ANIMATE_LAST_METRICS_I1=""
ANIMATE_LAST_METRICS_I2=""
ANIMATE_LAST_METRICS_I3=""
ANIMATE_LAST_METRICS_LOCAL=""
ANIMATE_STORAGE_DETAIL_I1=""
ANIMATE_STORAGE_DETAIL_I2=""
ANIMATE_STORAGE_DETAIL_I3=""
ANIMATE_SERVICES_I1=""
ANIMATE_SERVICES_I2=""
ANIMATE_SERVICES_I3=""

# Parse metrics to extract key values
parse_metric() {
    local metrics="$1"
    local key="$2"
    echo "$metrics" | grep -A1 "^${key}:" | tail -1
}

# Draw animated header
draw_animated_header() {
    local interval="$1"
    local timestamp=$(date '+%Y-%m-%d %H:%M:%S')

    cursor_to 0 0
    echo -en "${CYAN}${BOLD}"
    echo -n "┌────────────────────────────────────────────────────────────────────────────┐"
    cursor_to 1 0
    printf "│  ▓▓▓  SYSMON Live Dashboard         │  %-19s │  q=quit  │" "$timestamp"
    cursor_to 2 0
    echo -n "│  ▓▓▓  Refresh: ${interval}s                   │                       │  h=help  │"
    cursor_to 3 0
    echo -n "└────────────────────────────────────────────────────────────────────────────┘"
    echo -en "${NC}"
}

# Draw instance panel with progress bars
draw_instance_panel() {
    local row="$1"
    local name="$2"
    local ip="$3"
    local metrics="$4"
    local status="$5"
    local -n cpu_hist="$6"

    local panel_width=74
    local indicator

    case "$status" in
        ok) indicator="${GREEN}●${NC}" ;;
        loading) indicator="${CYAN}◐${NC}" ;;
        error) indicator="${RED}✗${NC}" ;;
        *) indicator="${DIM}○${NC}" ;;
    esac

    # Panel header
    cursor_to "$row" 2
    echo -en "${CYAN}┌─ ${name} (${ip}) ${indicator} "
    local header_used=$((${#name} + ${#ip} + 10))
    printf '─%.0s' $(seq 1 $((panel_width - header_used)))
    echo -en "┐${NC}"

    if [[ -z "$metrics" || "$status" == "error" ]]; then
        # Show error state
        cursor_to $((row + 1)) 2
        echo -en "${CYAN}│${NC}"
        cursor_to $((row + 1)) $((panel_width + 1))
        echo -en "${CYAN}│${NC}"

        cursor_to $((row + 2)) 2
        echo -en "${CYAN}│${NC}                   ${RED}CONNECTION FAILED${NC}                          "
        cursor_to $((row + 2)) $((panel_width + 1))
        echo -en "${CYAN}│${NC}"

        cursor_to $((row + 3)) 2
        echo -en "${CYAN}│${NC}"
        cursor_to $((row + 3)) $((panel_width + 1))
        echo -en "${CYAN}│${NC}"

        cursor_to $((row + 4)) 2
        echo -en "${CYAN}│${NC}"
        cursor_to $((row + 4)) $((panel_width + 1))
        echo -en "${CYAN}│${NC}"

        cursor_to $((row + 5)) 2
        echo -en "${CYAN}└"
        printf '─%.0s' $(seq 1 $((panel_width - 2)))
        echo -en "┘${NC}"
        return
    fi

    # Parse metrics
    local disk_info mem_info cpu_pct load_avg claude_count tmux_count container_count

    disk_info=$(parse_metric "$metrics" "DISK_INFO")
    mem_info=$(parse_metric "$metrics" "MEMORY")
    cpu_pct=$(parse_metric "$metrics" "CPU_PCT")
    load_avg=$(parse_metric "$metrics" "LOAD_AVG")
    claude_count=$(parse_metric "$metrics" "CLAUDE_COUNT")
    tmux_count=$(parse_metric "$metrics" "TMUX_COUNT")
    container_count=$(parse_metric "$metrics" "CONTAINER_COUNT")

    # Parse disk: total|used|avail|pct
    IFS='|' read -r disk_total disk_used disk_avail disk_pct <<< "$disk_info"

    # Parse memory: total|used|free|avail|pct
    IFS='|' read -r mem_total mem_used mem_free mem_avail mem_pct <<< "$mem_info"

    # Extract numeric percentages
    local disk_num="${disk_pct%\%}"
    local mem_num="${mem_pct%\%}"
    local cpu_num="${cpu_pct%\%}"

    # Update CPU history
    if [[ -n "$cpu_num" && "$cpu_num" =~ ^[0-9]+$ ]]; then
        cpu_hist+=("$cpu_num")
        # Keep only last 10 values
        if [[ ${#cpu_hist[@]} -gt 10 ]]; then
            cpu_hist=("${cpu_hist[@]:1}")
        fi
    fi

    # Row 1: Disk
    cursor_to $((row + 1)) 2
    echo -en "${CYAN}│${NC}  "
    printf "%-8s" "Disk"
    progress_bar "${disk_num:-0}" 100 32
    printf " (%s/%s)" "${disk_used:-?}" "${disk_total:-?}"
    # Pad to panel width
    cursor_to $((row + 1)) $((panel_width + 1))
    echo -en "${CYAN}│${NC}"

    # Row 2: Memory
    cursor_to $((row + 2)) 2
    echo -en "${CYAN}│${NC}  "
    printf "%-8s" "Memory"
    progress_bar "${mem_num:-0}" 100 32
    printf " (%s/%s)" "${mem_used:-?}" "${mem_total:-?}"
    cursor_to $((row + 2)) $((panel_width + 1))
    echo -en "${CYAN}│${NC}"

    # Row 3: CPU with sparkline
    cursor_to $((row + 3)) 2
    echo -en "${CYAN}│${NC}  "
    printf "%-8s" "CPU"
    progress_bar "${cpu_num:-0}" 100 32
    echo -n " "
    if [[ ${#cpu_hist[@]} -gt 0 ]]; then
        sparkline "${cpu_hist[@]}"
    fi
    cursor_to $((row + 3)) $((panel_width + 1))
    echo -en "${CYAN}│${NC}"

    # Row 4: Stats
    cursor_to $((row + 4)) 2
    echo -en "${CYAN}│${NC}  "
    printf "Claude: %-3s  Tmux: %-3s  Docker: %-2s containers" \
        "${claude_count:-0}" "${tmux_count:-0}" "${container_count:-0}"
    cursor_to $((row + 4)) $((panel_width + 1))
    echo -en "${CYAN}│${NC}"

    # Bottom border
    cursor_to $((row + 5)) 2
    echo -en "${CYAN}└"
    printf '─%.0s' $(seq 1 $((panel_width - 2)))
    echo -en "┘${NC}"
}

# Draw status line at bottom
draw_status_line() {
    local row="$1"
    local interval="$2"
    local time_to_refresh="$3"
    local last_refresh="$4"

    cursor_to "$row" 0
    clear_to_eol

    echo -en "${DIM}"
    printf "Last refresh: %ss ago │ Next: %ss │ Interval: %ss │ +/- to adjust │ r=refresh" \
        "$last_refresh" "$time_to_refresh" "$interval"
    echo -en "${NC}"
}

# Draw alerts section
draw_alerts() {
    local row="$1"

    cursor_to "$row" 0
    echo -en "${BOLD}─── Alerts ───────────────────────────────────────────────────────────────────${NC}"

    local alert_row=$((row + 1))
    local has_alerts=false

    # Check Instance 1 disk
    if [[ -n "$ANIMATE_LAST_METRICS_I1" ]]; then
        local disk_pct=$(parse_metric "$ANIMATE_LAST_METRICS_I1" "DISK_INFO" | cut -d'|' -f4)
        local disk_num="${disk_pct%\%}"
        if [[ "$disk_num" =~ ^[0-9]+$ ]] && [[ "$disk_num" -ge "$DISK_WARNING_THRESHOLD" ]]; then
            cursor_to "$alert_row" 0
            echo -en "${YELLOW}⚠${NC} Instance 1 disk usage at ${disk_num}% (threshold: ${DISK_WARNING_THRESHOLD}%)"
            clear_to_eol
            ((alert_row++))
            has_alerts=true
        fi
    fi

    # Check Instance 2 disk
    if [[ -n "$ANIMATE_LAST_METRICS_I2" ]]; then
        local disk_pct=$(parse_metric "$ANIMATE_LAST_METRICS_I2" "DISK_INFO" | cut -d'|' -f4)
        local disk_num="${disk_pct%\%}"
        if [[ "$disk_num" =~ ^[0-9]+$ ]] && [[ "$disk_num" -ge "$DISK_WARNING_THRESHOLD" ]]; then
            cursor_to "$alert_row" 0
            echo -en "${YELLOW}⚠${NC} Instance 2 disk usage at ${disk_num}% (threshold: ${DISK_WARNING_THRESHOLD}%)"
            clear_to_eol
            ((alert_row++))
            has_alerts=true
        fi
    fi

    # Check Instance 3 disk
    if [[ -n "$ANIMATE_LAST_METRICS_I3" ]]; then
        local disk_pct=$(parse_metric "$ANIMATE_LAST_METRICS_I3" "DISK_INFO" | cut -d'|' -f4)
        local disk_num="${disk_pct%\%}"
        if [[ "$disk_num" =~ ^[0-9]+$ ]] && [[ "$disk_num" -ge "$DISK_WARNING_THRESHOLD" ]]; then
            cursor_to "$alert_row" 0
            echo -en "${YELLOW}⚠${NC} Instance 3 disk usage at ${disk_num}% (threshold: ${DISK_WARNING_THRESHOLD}%)"
            clear_to_eol
            ((alert_row++))
            has_alerts=true
        fi
    fi

    if ! $has_alerts; then
        cursor_to "$alert_row" 0
        echo -en "${GREEN}✓${NC} All systems nominal"
        clear_to_eol
    fi
}

# Collect metrics for animated mode (parallel, non-blocking)
collect_animated_metrics() {
    local quick_mode="$1"
    local collect_timeout="${SYSMON_COLLECT_TIMEOUT:-6}"

    local tmp_i1="/tmp/sysmon_anim_i1_$$"
    local tmp_i2="/tmp/sysmon_anim_i2_$$"
    local tmp_i3="/tmp/sysmon_anim_i3_$$"
    local tmp_local="/tmp/sysmon_anim_local_$$"
    local tmp_storage_i1="/tmp/sysmon_anim_stor_i1_$$"
    local tmp_storage_i2="/tmp/sysmon_anim_stor_i2_$$"
    local tmp_storage_i3="/tmp/sysmon_anim_stor_i3_$$"

    # When on Docker page (page 3), we need full metrics including DOCKER_STATS
    local effective_quick_mode="$quick_mode"
    if [[ "$CURRENT_PAGE" == "3" ]]; then
        effective_quick_mode="false"
    fi

    # Start parallel collection - each in background with individual timeout
    (collect_remote_metrics 1 "$effective_quick_mode" > "$tmp_i1" 2>/dev/null) &
    local pid1=$!

    (collect_remote_metrics 2 "$effective_quick_mode" > "$tmp_i2" 2>/dev/null) &
    local pid2=$!

    (collect_remote_metrics 3 "$effective_quick_mode" > "$tmp_i3" 2>/dev/null) &
    local pid3=$!

    (collect_local_metrics "true" > "$tmp_local" 2>/dev/null) &
    local pid_local=$!

    # Collect storage detail if on Page 2 or if not yet loaded
    local pid_stor1="" pid_stor2="" pid_stor3=""
    if [[ "$CURRENT_PAGE" == "2" ]] || [[ -z "$ANIMATE_STORAGE_DETAIL_I1" ]]; then
        (collect_remote_storage_detail 1 > "$tmp_storage_i1" 2>/dev/null) &
        pid_stor1=$!
        (collect_remote_storage_detail 2 > "$tmp_storage_i2" 2>/dev/null) &
        pid_stor2=$!
        (collect_remote_storage_detail 3 > "$tmp_storage_i3" 2>/dev/null) &
        pid_stor3=$!
    fi

    # Collect services data if on Page 6 or if not yet loaded
    local tmp_services_i1="/tmp/sysmon_anim_svc_i1_$$"
    local tmp_services_i2="/tmp/sysmon_anim_svc_i2_$$"
    local tmp_services_i3="/tmp/sysmon_anim_svc_i3_$$"
    local pid_svc1="" pid_svc2="" pid_svc3=""
    if [[ "$CURRENT_PAGE" == "6" ]] || [[ -z "$ANIMATE_SERVICES_I1" ]]; then
        (collect_remote_native_services 1 > "$tmp_services_i1" 2>/dev/null) &
        pid_svc1=$!
        (collect_remote_native_services 2 > "$tmp_services_i2" 2>/dev/null) &
        pid_svc2=$!
        (collect_remote_native_services 3 > "$tmp_services_i3" 2>/dev/null) &
        pid_svc3=$!
    fi

    # Wait with timeout - don't block forever
    local wait_start=$(date +%s)
    local max_wait="$collect_timeout"

    while true; do
        # Check if any process still running (|| true to avoid set -e exit)
        local still_running=false
        kill -0 $pid1 2>/dev/null && still_running=true || true
        kill -0 $pid2 2>/dev/null && still_running=true || true
        kill -0 $pid3 2>/dev/null && still_running=true || true
        kill -0 $pid_local 2>/dev/null && still_running=true || true
        [[ -n "$pid_stor1" ]] && { kill -0 $pid_stor1 2>/dev/null && still_running=true || true; }
        [[ -n "$pid_stor2" ]] && { kill -0 $pid_stor2 2>/dev/null && still_running=true || true; }
        [[ -n "$pid_stor3" ]] && { kill -0 $pid_stor3 2>/dev/null && still_running=true || true; }
        [[ -n "$pid_svc1" ]] && { kill -0 $pid_svc1 2>/dev/null && still_running=true || true; }
        [[ -n "$pid_svc2" ]] && { kill -0 $pid_svc2 2>/dev/null && still_running=true || true; }
        [[ -n "$pid_svc3" ]] && { kill -0 $pid_svc3 2>/dev/null && still_running=true || true; }

        $still_running || break

        # Check timeout
        local elapsed=$(( $(date +%s) - wait_start ))
        if [[ $elapsed -ge $max_wait ]]; then
            # Kill any remaining processes
            kill $pid1 $pid2 $pid3 $pid_local 2>/dev/null || true
            [[ -n "$pid_stor1" ]] && kill $pid_stor1 2>/dev/null || true
            [[ -n "$pid_stor2" ]] && kill $pid_stor2 2>/dev/null || true
            [[ -n "$pid_stor3" ]] && kill $pid_stor3 2>/dev/null || true
            [[ -n "$pid_svc1" ]] && kill $pid_svc1 2>/dev/null || true
            [[ -n "$pid_svc2" ]] && kill $pid_svc2 2>/dev/null || true
            [[ -n "$pid_svc3" ]] && kill $pid_svc3 2>/dev/null || true
            break
        fi
        sleep 0.1
    done

    # Read results
    [[ -f "$tmp_i1" ]] && ANIMATE_LAST_METRICS_I1=$(cat "$tmp_i1") && rm -f "$tmp_i1"
    [[ -f "$tmp_i2" ]] && ANIMATE_LAST_METRICS_I2=$(cat "$tmp_i2") && rm -f "$tmp_i2"
    [[ -f "$tmp_i3" ]] && ANIMATE_LAST_METRICS_I3=$(cat "$tmp_i3") && rm -f "$tmp_i3"
    [[ -f "$tmp_local" ]] && ANIMATE_LAST_METRICS_LOCAL=$(cat "$tmp_local") && rm -f "$tmp_local"
    [[ -f "$tmp_storage_i1" ]] && ANIMATE_STORAGE_DETAIL_I1=$(cat "$tmp_storage_i1") && rm -f "$tmp_storage_i1"
    [[ -f "$tmp_storage_i2" ]] && ANIMATE_STORAGE_DETAIL_I2=$(cat "$tmp_storage_i2") && rm -f "$tmp_storage_i2"
    [[ -f "$tmp_storage_i3" ]] && ANIMATE_STORAGE_DETAIL_I3=$(cat "$tmp_storage_i3") && rm -f "$tmp_storage_i3"
    [[ -f "$tmp_services_i1" ]] && ANIMATE_SERVICES_I1=$(cat "$tmp_services_i1") && rm -f "$tmp_services_i1"
    [[ -f "$tmp_services_i2" ]] && ANIMATE_SERVICES_I2=$(cat "$tmp_services_i2") && rm -f "$tmp_services_i2"
    [[ -f "$tmp_services_i3" ]] && ANIMATE_SERVICES_I3=$(cat "$tmp_services_i3") && rm -f "$tmp_services_i3"

    # Record to history for time-series
    if type record_metrics &>/dev/null; then
        local cpu1 mem1 disk1 docker1 claude1
        local cpu2 mem2 disk2 docker2 claude2
        local cpu3 mem3 disk3 docker3 claude3

        cpu1=$(parse_metric "$ANIMATE_LAST_METRICS_I1" "CPU_PCT")
        mem1=$(parse_metric "$ANIMATE_LAST_METRICS_I1" "MEMORY" | cut -d'|' -f5 | tr -d '%')
        disk1=$(parse_metric "$ANIMATE_LAST_METRICS_I1" "DISK_INFO" | cut -d'|' -f4 | tr -d '%')
        docker1=$(parse_metric "$ANIMATE_LAST_METRICS_I1" "CONTAINER_COUNT")
        claude1=$(parse_metric "$ANIMATE_LAST_METRICS_I1" "CLAUDE_COUNT")

        cpu2=$(parse_metric "$ANIMATE_LAST_METRICS_I2" "CPU_PCT")
        mem2=$(parse_metric "$ANIMATE_LAST_METRICS_I2" "MEMORY" | cut -d'|' -f5 | tr -d '%')
        disk2=$(parse_metric "$ANIMATE_LAST_METRICS_I2" "DISK_INFO" | cut -d'|' -f4 | tr -d '%')
        docker2=$(parse_metric "$ANIMATE_LAST_METRICS_I2" "CONTAINER_COUNT")
        claude2=$(parse_metric "$ANIMATE_LAST_METRICS_I2" "CLAUDE_COUNT")

        cpu3=$(parse_metric "$ANIMATE_LAST_METRICS_I3" "CPU_PCT")
        mem3=$(parse_metric "$ANIMATE_LAST_METRICS_I3" "MEMORY" | cut -d'|' -f5 | tr -d '%')
        disk3=$(parse_metric "$ANIMATE_LAST_METRICS_I3" "DISK_INFO" | cut -d'|' -f4 | tr -d '%')
        docker3=$(parse_metric "$ANIMATE_LAST_METRICS_I3" "CONTAINER_COUNT")
        claude3=$(parse_metric "$ANIMATE_LAST_METRICS_I3" "CLAUDE_COUNT")

        record_metrics "instance1" "$cpu1" "$mem1" "$disk1" "$docker1" "$claude1" || true
        record_metrics "instance2" "$cpu2" "$mem2" "$disk2" "$docker2" "$claude2" || true
        record_metrics "instance3" "$cpu3" "$mem3" "$disk3" "$docker3" "$claude3" || true
    fi
    return 0
}

# Render the full animated dashboard
render_animated_dashboard() {
    local interval="$1"
    local time_to_refresh="$2"
    local last_refresh="$3"

    # Check if we're on a non-default page
    if [[ "$CURRENT_PAGE" != "1" ]] && type render_current_page &>/dev/null; then
        # Use the page dispatcher for pages 2-6
        if render_current_page \
            "$ANIMATE_LAST_METRICS_I1" \
            "$ANIMATE_LAST_METRICS_I2" \
            "$ANIMATE_LAST_METRICS_I3" \
            "$ANIMATE_LAST_METRICS_LOCAL" \
            "$ANIMATE_STORAGE_DETAIL_I1" \
            "$ANIMATE_STORAGE_DETAIL_I2" \
            "$ANIMATE_STORAGE_DETAIL_I3" \
            "$ANIMATE_SERVICES_I1" \
            "$ANIMATE_SERVICES_I2" \
            "$ANIMATE_SERVICES_I3"; then
            # Page was rendered, add status line
            draw_multipage_status_line 36 "$interval" "$time_to_refresh" "$last_refresh"
            return
        fi
    fi

    # Default: Page 1 Overview
    # Clear screen only when page changes to prevent flickering
    if [[ "$PAGE_CHANGED" == "true" ]]; then
        screen_clear
        sleep 0.05  # Brief pause for clean transition
    fi
    cursor_home

    # Header (rows 0-3)
    draw_animated_header "$interval"

    # Page indicator (row 4)
    if type render_page_indicator &>/dev/null; then
        cursor_to 4 0
        render_page_indicator 78
    fi

    # Instance 1 panel (rows 5-10)
    local status_i1="ok"
    [[ -z "$ANIMATE_LAST_METRICS_I1" ]] && status_i1="error"
    draw_instance_panel 5 "Instance 1" "$INSTANCE1_IP" "$ANIMATE_LAST_METRICS_I1" "$status_i1" CPU_HISTORY_I1

    # Instance 2 panel (rows 12-17)
    local status_i2="ok"
    [[ -z "$ANIMATE_LAST_METRICS_I2" ]] && status_i2="error"
    draw_instance_panel 12 "Instance 2" "$INSTANCE2_IP" "$ANIMATE_LAST_METRICS_I2" "$status_i2" CPU_HISTORY_I2

    # Instance 3 panel (rows 19-24)
    local status_i3="ok"
    [[ -z "$ANIMATE_LAST_METRICS_I3" ]] && status_i3="error"
    draw_instance_panel 19 "Instance 3" "$INSTANCE3_IP" "$ANIMATE_LAST_METRICS_I3" "$status_i3" CPU_HISTORY_I3

    # Local panel (rows 26-31)
    local status_local="ok"
    [[ -z "$ANIMATE_LAST_METRICS_LOCAL" ]] && status_local="error"
    draw_instance_panel 26 "Local System" "localhost" "$ANIMATE_LAST_METRICS_LOCAL" "$status_local" CPU_HISTORY_LOCAL

    # Alerts (row 33)
    draw_alerts 33

    # Status line (row 36)
    draw_multipage_status_line 36 "$interval" "$time_to_refresh" "$last_refresh"
}

# Draw status line with page info
draw_multipage_status_line() {
    local row="$1"
    local interval="$2"
    local time_to_refresh="$3"
    local last_refresh="$4"

    cursor_to "$row" 0
    clear_to_eol

    local page_info=""
    if type get_page_status &>/dev/null; then
        page_info=" │ $(get_page_status)"
    fi

    echo -en "${DIM}"
    printf "Last: %ss │ Next: %ss │ Interval: %ss%s │ ↑↓=page │ h=help" \
        "$last_refresh" "$time_to_refresh" "$interval" "$page_info"
    echo -en "${NC}"
}

# Display startup animation
show_startup_animation() {
    local width=${SCREEN_WIDTH:-80}
    local height=${SCREEN_HEIGHT:-24}
    local center_row=$((height / 2 - 6))

    screen_clear

    # SEGA ASCII art (smaller)
    local sega_logo=(
        "███████╗███████╗ ██████╗  █████╗ "
        "██╔════╝██╔════╝██╔════╝ ██╔══██╗"
        "███████╗█████╗  ██║  ███╗███████║"
        "╚════██║██╔══╝  ██║   ██║██╔══██║"
        "███████║███████╗╚██████╔╝██║  ██║"
        "╚══════╝╚══════╝ ╚═════╝ ╚═╝  ╚═╝"
    )

    # SYSMON ASCII art
    local sysmon_logo=(
        "███████╗██╗   ██╗███████╗███╗   ███╗ ██████╗ ███╗   ██╗"
        "██╔════╝╚██╗ ██╔╝██╔════╝████╗ ████║██╔═══██╗████╗  ██║"
        "███████╗ ╚████╔╝ ███████╗██╔████╔██║██║   ██║██╔██╗ ██║"
        "╚════██║  ╚██╔╝  ╚════██║██║╚██╔╝██║██║   ██║██║╚██╗██║"
        "███████║   ██║   ███████║██║ ╚═╝ ██║╚██████╔╝██║ ╚████║"
        "╚══════╝   ╚═╝   ╚══════╝╚═╝     ╚═╝ ╚═════╝ ╚═╝  ╚═══╝"
    )

    # Calculate center positions
    local sega_width=34
    local sysmon_width=56
    local sega_col=$(((width - sega_width) / 2))
    local sysmon_col=$(((width - sysmon_width) / 2))

    # Draw SEGA logo
    local row=$center_row
    for line in "${sega_logo[@]}"; do
        cursor_to $row $sega_col
        echo -en "${MAGENTA}${BOLD}${line}${NC}"
        ((row++))
    done

    ((row++))  # Gap between logos

    # Draw SYSMON logo
    for line in "${sysmon_logo[@]}"; do
        cursor_to $row $sysmon_col
        echo -en "${CYAN}${BOLD}${line}${NC}"
        ((row++))
    done

    # Subtitle
    ((row++))
    local subtitle="System Monitoring Dashboard"
    local subtitle_col=$(((width - ${#subtitle}) / 2))
    cursor_to $row $subtitle_col
    echo -en "${DIM}${subtitle}${NC}"
    ((row += 2))

    # Progress animation
    local stages=("Connecting to instances" "Loading metrics" "Initializing display" "Ready")
    local spinner=('⠋' '⠙' '⠹' '⠸' '⠼' '⠴' '⠦' '⠧' '⠇' '⠏')
    local progress_col=$(((width - 30) / 2))

    for i in "${!stages[@]}"; do
        cursor_to $row $progress_col
        echo -en "${CYAN}${spinner[$((i % ${#spinner[@]}))]}${NC} ${stages[$i]}...    "
        sleep 0.3
        cursor_to $row $progress_col
        echo -en "${GREEN}✓${NC} ${stages[$i]}        "
        ((row++))
    done

    sleep 0.2
}

# Main animated dashboard loop
run_animated_dashboard() {
    local interval="${1:-$SYSMON_REFRESH_INTERVAL}"
    local quick_mode="${2:-true}"

    debug_log "run_animated_dashboard started: interval=$interval quick=$quick_mode"

    # Initialize live mode
    debug_log "Calling init_live_mode"
    init_live_mode
    get_screen_size
    debug_log "Screen size: ${SCREEN_WIDTH}x${SCREEN_HEIGHT}"

    # Initialize history for time-series (Page 5)
    if type init_history &>/dev/null; then
        debug_log "Initializing history"
        init_history
    fi

    # Reset page to default
    CURRENT_PAGE=1

    local last_refresh_time=0
    local running=true

    # Show startup animation
    debug_log "Showing startup animation"
    show_startup_animation

    # Set PAGE_CHANGED for first render to ensure clean screen
    PAGE_CHANGED=true

    # Initial collection
    debug_log "Initial metrics collection"
    collect_animated_metrics "$quick_mode"
    last_refresh_time=$(date +%s)
    debug_log "Initial collection complete"

    debug_log "Entering main loop"
    local loop_count=0

    while $running; do
        loop_count=$((loop_count + 1))
        debug_log "Loop iteration $loop_count starting"
        local now=$(date +%s)
        local elapsed=$((now - last_refresh_time))
        local time_to_refresh=$((interval - elapsed))
        [[ $time_to_refresh -lt 0 ]] && time_to_refresh=0

        # Handle keyboard input
        debug_log "Calling handle_input"
        if ! handle_input; then
            debug_log "handle_input returned false (INPUT_QUIT=$INPUT_QUIT), exiting loop"
            running=false
            break
        fi
        debug_log "handle_input completed, LAST_KEY='$(printf '%s' "${LAST_KEY:-}" | xxd -p 2>/dev/null)'"

        # Log key presses
        [[ -n "${LAST_KEY:-}" ]] && debug_log "Key pressed: $(printf '%s' "$LAST_KEY" | xxd -p 2>/dev/null)"

        # Handle toggle flags
        if [[ "$INPUT_TOGGLE_HELP" == "true" ]]; then
            ANIMATE_SHOW_HELP=$((1 - ANIMATE_SHOW_HELP))
            if [[ "$ANIMATE_SHOW_HELP" == "1" ]]; then
                show_help_overlay 8 20
                wait_for_dismiss
                ANIMATE_SHOW_HELP=0
            fi
        fi

        if [[ "$INPUT_TOGGLE_DETAIL" == "true" ]]; then
            ANIMATE_DETAILED=$((1 - ANIMATE_DETAILED))
        fi

        if [[ -n "$INPUT_FOCUS" ]]; then
            ANIMATE_FOCUS="$INPUT_FOCUS"
        fi

        # Handle interval changes
        if [[ $INPUT_INTERVAL_CHANGE -ne 0 ]]; then
            interval=$((interval + INPUT_INTERVAL_CHANGE))
            [[ $interval -lt $SYSMON_MIN_INTERVAL ]] && interval=$SYSMON_MIN_INTERVAL
            [[ $interval -gt $SYSMON_MAX_INTERVAL ]] && interval=$SYSMON_MAX_INTERVAL
        fi

        # Handle page navigation
        if [[ $INPUT_PAGE_CHANGE -ne 0 ]] || [[ $INPUT_PAGE_DIRECT -gt 0 ]]; then
            local old_page=$CURRENT_PAGE
            if [[ $INPUT_PAGE_DIRECT -gt 0 ]]; then
                CURRENT_PAGE=$INPUT_PAGE_DIRECT
            else
                CURRENT_PAGE=$((CURRENT_PAGE + INPUT_PAGE_CHANGE))
                # Wrap around
                [[ $CURRENT_PAGE -lt 1 ]] && CURRENT_PAGE=$MAX_PAGES
                [[ $CURRENT_PAGE -gt $MAX_PAGES ]] && CURRENT_PAGE=1
            fi
            # Set PAGE_CHANGED flag if page actually changed
            if [[ "$old_page" != "$CURRENT_PAGE" ]]; then
                PAGE_CHANGED=true
                debug_log "Page changed: $old_page -> $CURRENT_PAGE (PAGE_CHANGED=true)"
            fi
        fi

        # Check if refresh needed
        local should_refresh=false
        if [[ "$INPUT_REFRESH" == "true" ]]; then
            should_refresh=true
        elif [[ $elapsed -ge $interval ]]; then
            should_refresh=true
        fi

        # Refresh data if needed
        if $should_refresh; then
            debug_log "Refreshing metrics (loop $loop_count)"
            collect_animated_metrics "$quick_mode"
            last_refresh_time=$(date +%s)
            elapsed=0
            time_to_refresh=$interval
        fi

        # Render dashboard
        debug_log "Rendering page $CURRENT_PAGE (loop $loop_count)"
        render_animated_dashboard "$interval" "$time_to_refresh" "$elapsed" || {
            debug_log "render_animated_dashboard failed with code $?"
        }

        # Reset PAGE_CHANGED after render
        PAGE_CHANGED=false

        # Small sleep to prevent CPU spin
        sleep 0.1
    done

    debug_log "Main loop exited after $loop_count iterations"
    # Cleanup handled by trap in init_live_mode
}

# Main command function
cmd_dashboard() {
    local quick_mode=false
    local animate_mode=false
    local interval="$SYSMON_REFRESH_INTERVAL"

    # Parse arguments
    while [[ $# -gt 0 ]]; do
        case "$1" in
            --quick)
                quick_mode=true
                shift
                ;;
            --animate)
                animate_mode=true
                shift
                ;;
            --interval)
                if [[ -n "$2" && "$2" =~ ^[0-9]+$ ]]; then
                    interval="$2"
                    shift 2
                else
                    log_error "--interval requires a numeric value"
                    return 1
                fi
                ;;
            --debug)
                SYSMON_DEBUG=true
                mkdir -p "$(dirname "$SYSMON_DEBUG_LOG")"
                echo "" > "$SYSMON_DEBUG_LOG"
                debug_log "=== Dashboard debug started ==="
                debug_log "Args: $*"
                trap 'dashboard_error_handler $LINENO "$BASH_COMMAND" $?' ERR
                shift
                ;;
            --help|-h)
                cmd_dashboard_help
                return 0
                ;;
            *)
                log_error "Unknown option: $1"
                cmd_dashboard_help
                return 1
                ;;
        esac
    done

    # Check if animated mode requested
    if [[ "$animate_mode" == "true" || "$SYSMON_ANIMATE" == "true" ]]; then
        # Verify TTY
        if [[ ! -t 1 ]]; then
            log_error "Animated mode requires an interactive terminal (TTY)"
            return 1
        fi

        # Run animated dashboard (quick mode forced for better refresh rate)
        run_animated_dashboard "$interval" "true"
        return $?
    fi

    # Static mode (original behavior)

    print_header "FLEET EC2 Dashboard"
    echo "Generated: $(date '+%Y-%m-%d %H:%M:%S')"
    [[ "$quick_mode" == "true" ]] && echo "(Quick mode - DB volumes skipped)"

    # Check SSH key
    if ! check_ssh_key; then
        return 1
    fi

    # Collect metrics from all instances in parallel
    log_info "Collecting metrics from all instances..."

    local metrics1="" metrics2="" metrics3=""
    local pid1 pid2 pid3
    local tmp1="/tmp/sysmon_dashboard_i1_$$"
    local tmp2="/tmp/sysmon_dashboard_i2_$$"
    local tmp3="/tmp/sysmon_dashboard_i3_$$"

    # Start parallel collection
    (
        collect_remote_metrics 1 "$quick_mode" > "$tmp1" 2>/dev/null
    ) &
    pid1=$!

    (
        collect_remote_metrics 2 "$quick_mode" > "$tmp2" 2>/dev/null
    ) &
    pid2=$!

    (
        collect_remote_metrics 3 "$quick_mode" > "$tmp3" 2>/dev/null
    ) &
    pid3=$!

    # Wait with spinner
    start_spinner "Collecting data from instances..."

    wait $pid1
    local status1=$?
    wait $pid2
    local status2=$?
    wait $pid3
    local status3=$?

    stop_spinner "ok"

    # Read results
    if [[ -f "$tmp1" ]]; then
        metrics1=$(cat "$tmp1")
        rm -f "$tmp1"
    fi

    if [[ -f "$tmp2" ]]; then
        metrics2=$(cat "$tmp2")
        rm -f "$tmp2"
    fi

    if [[ -f "$tmp3" ]]; then
        metrics3=$(cat "$tmp3")
        rm -f "$tmp3"
    fi

    # Display Instance 1
    if [[ -n "$metrics1" ]]; then
        print_table_header "Instance 1 - STORAGE" "$INSTANCE1_IP"
        print_storage_table "$metrics1" "$quick_mode"

        print_table_header "Instance 1 - CPU/USAGE" "$INSTANCE1_IP"
        print_cpu_table "$metrics1"
    else
        echo ""
        echo -e "${RED}Instance 1: Failed to collect metrics${NC}"
        echo ""
    fi

    # Display Instance 2
    if [[ -n "$metrics2" ]]; then
        print_table_header "Instance 2 - STORAGE" "$INSTANCE2_IP"
        print_storage_table "$metrics2" "$quick_mode"

        print_table_header "Instance 2 - CPU/USAGE" "$INSTANCE2_IP"
        print_cpu_table "$metrics2"
    else
        echo ""
        echo -e "${RED}Instance 2: Failed to collect metrics${NC}"
        echo ""
    fi

    # Display Instance 3
    if [[ -n "$metrics3" ]]; then
        print_table_header "Instance 3 - STORAGE" "$INSTANCE3_IP"
        print_storage_table "$metrics3" "$quick_mode"

        print_table_header "Instance 3 - CPU/USAGE" "$INSTANCE3_IP"
        print_cpu_table "$metrics3"
    else
        echo ""
        echo -e "${RED}Instance 3: Failed to collect metrics${NC}"
        echo ""
    fi

    # Summary comparison (if all succeeded)
    if [[ -n "$metrics1" && -n "$metrics2" && -n "$metrics3" ]]; then
        print_summary_table "$metrics1" "$metrics2" "$metrics3"
    fi

    echo "---"
    echo "Run 'sysmon analyze --instance <n>' for detailed analysis"
}
