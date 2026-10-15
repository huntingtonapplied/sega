#!/bin/bash
# ============================================================================
# SYSMON - Dashboard Page Renderers
# ============================================================================
# Page-specific rendering functions for multi-page dashboard
# Source this file: source "${SYSMON_LIB_DIR}/display/pages.sh"
# ============================================================================

# Prevent double-sourcing
[[ -n "${SYSMON_PAGES_LOADED:-}" ]] && return 0
SYSMON_PAGES_LOADED=1

# ============================================================================
# PAGE 1: OVERVIEW (Default Dashboard)
# ============================================================================
# This is the existing dashboard view - handled by dashboard.sh directly

# ============================================================================
# PAGE 2: STORAGE DETAIL
# ============================================================================

# Cache for storage detail data
declare -A STORAGE_CACHE_I1
declare -A STORAGE_CACHE_I2
declare -A STORAGE_CACHE_LOCAL

# Render storage section header
render_storage_section() {
    local title="$1"
    local row="$2"
    local width="${3:-76}"

    cursor_to "$row" 2
    echo -en "${CYAN}${BOLD}─── ${title} "
    local title_len=$((${#title} + 5))
    printf '─%.0s' $(seq 1 $((width - title_len)))
    echo -en "${NC}"
}

# Render node_modules table
render_node_modules_table() {
    local row="$1"
    local data="$2"
    local max_rows="${3:-8}"

    render_storage_section "Node Modules" "$row" >/dev/tty
    ((row++))

    cursor_to "$row" 2 >/dev/tty
    printf "${DIM}%-15s %-35s %10s${NC}" "Project" "Path" "Size" >/dev/tty
    ((row++))

    local count=0
    while IFS='|' read -r project path size; do
        [[ -z "$project" || "$project" == "NOT_AVAILABLE" ]] && continue
        ((count >= max_rows)) && break

        cursor_to "$row" 2 >/dev/tty
        printf "%-15s %-35s %10s" "${project:0:15}" "${path:0:35}" "$size" >/dev/tty
        ((row++))
        ((count++))
    done <<< "$data"

    if [[ $count -eq 0 ]]; then
        cursor_to "$row" 2 >/dev/tty
        echo -en "${DIM}No node_modules found${NC}" >/dev/tty
        ((row++))
    fi

    echo "$row"
}

# Render venv table
render_venv_table() {
    local row="$1"
    local data="$2"
    local max_rows="${3:-5}"

    render_storage_section "Python Virtual Environments" "$row" >/dev/tty
    ((row++))

    cursor_to "$row" 2 >/dev/tty
    printf "${DIM}%-20s %-40s %10s${NC}" "Name" "Path" "Size" >/dev/tty
    ((row++))

    local count=0
    while IFS='|' read -r name path size; do
        [[ -z "$name" || "$name" == "NOT_AVAILABLE" ]] && continue
        ((count >= max_rows)) && break

        cursor_to "$row" 2 >/dev/tty
        printf "%-20s %-40s %10s" "${name:0:20}" "${path:0:40}" "$size" >/dev/tty
        ((row++))
        ((count++))
    done <<< "$data"

    if [[ $count -eq 0 ]]; then
        cursor_to "$row" 2 >/dev/tty
        echo -en "${DIM}No virtual environments found${NC}" >/dev/tty
        ((row++))
    fi

    echo "$row"
}

# Render build directories table
render_build_dirs_table() {
    local row="$1"
    local data="$2"
    local max_rows="${3:-6}"

    render_storage_section "Build Directories" "$row" >/dev/tty
    ((row++))

    cursor_to "$row" 2 >/dev/tty
    printf "${DIM}%-8s %-15s %-35s %10s${NC}" "Type" "Project" "Path" "Size" >/dev/tty
    ((row++))

    local count=0
    while IFS='|' read -r type project path size; do
        [[ -z "$type" || "$type" == "NOT_AVAILABLE" ]] && continue
        ((count >= max_rows)) && break

        cursor_to "$row" 2 >/dev/tty
        printf "%-8s %-15s %-35s %10s" "$type" "${project:0:15}" "${path:0:35}" "$size" >/dev/tty
        ((row++))
        ((count++))
    done <<< "$data"

    if [[ $count -eq 0 ]]; then
        cursor_to "$row" 2 >/dev/tty
        echo -en "${DIM}No build directories found${NC}" >/dev/tty
        ((row++))
    fi

    echo "$row"
}

# Render cache directories table
render_cache_table() {
    local row="$1"
    local data="$2"

    render_storage_section "Cache Directories" "$row" >/dev/tty
    ((row++))

    cursor_to "$row" 2 >/dev/tty
    printf "${DIM}%-15s %-45s %10s${NC}" "Name" "Path" "Size" >/dev/tty
    ((row++))

    local count=0
    while IFS='|' read -r name path size; do
        [[ -z "$name" ]] && continue

        cursor_to "$row" 2 >/dev/tty
        printf "%-15s %-45s %10s" "$name" "${path:0:45}" "$size" >/dev/tty
        ((row++))
        ((count++))
    done <<< "$data"

    if [[ $count -eq 0 ]]; then
        cursor_to "$row" 2 >/dev/tty
        echo -en "${DIM}No cache directories found${NC}" >/dev/tty
        ((row++))
    fi

    echo "$row"
}

# Parse storage detail sections from collected data
parse_storage_section() {
    local data="$1"
    local section="$2"

    echo "$data" | sed -n "/^${section}:/,/^[A-Z_]*:/p" | grep -v "^${section}:" | grep -v "^[A-Z_]*:$" | grep -v "^===" | head -20
}

# Render full storage detail page
render_storage_detail_page() {
    local instance_data="$1"
    local instance_name="$2"
    local start_row="${3:-5}"

    local row="$start_row"

    # Page header
    cursor_to "$row" 2 >/dev/tty
    echo -en "${CYAN}${BOLD}━━━ Storage Detail: ${instance_name} ━━━${NC}" >/dev/tty
    ((row += 2))

    # Node modules section
    local node_data=$(parse_storage_section "$instance_data" "NODE_MODULES")
    row=$(render_node_modules_table "$row" "$node_data" 6)
    ((row++))

    # Venv section
    local venv_data=$(parse_storage_section "$instance_data" "VENVS")
    row=$(render_venv_table "$row" "$venv_data" 4)
    ((row++))

    # Build dirs section
    local build_data=$(parse_storage_section "$instance_data" "BUILD_DIRS")
    row=$(render_build_dirs_table "$row" "$build_data" 5)
    ((row++))

    # Cache section
    local cache_data=$(parse_storage_section "$instance_data" "CACHE_DIRS")
    row=$(render_cache_table "$row" "$cache_data")

    echo "$row"
}

# ============================================================================
# PAGE 3: DOCKER DETAIL
# ============================================================================

# Render docker containers table with more detail
render_docker_containers_detail() {
    local row="$1"
    local data="$2"
    local max_rows="${3:-12}"

    render_storage_section "Running Containers" "$row" >/dev/tty
    ((row++))

    cursor_to "$row" 2 >/dev/tty
    printf "${DIM}%-25s %8s %15s %8s${NC}" "Container" "CPU" "Memory" "Mem %" >/dev/tty
    ((row++))

    local count=0
    while IFS='|' read -r name cpu mem mem_pct; do
        [[ -z "$name" ]] && continue
        ((count >= max_rows)) && break

        # Color code high usage
        local cpu_color="${NC}"
        local mem_color="${NC}"
        local cpu_num="${cpu%\%}"
        local mem_num="${mem_pct%\%}"

        [[ "$cpu_num" =~ ^[0-9]+$ ]] && ((cpu_num > 50)) && cpu_color="${YELLOW}"
        [[ "$cpu_num" =~ ^[0-9]+$ ]] && ((cpu_num > 80)) && cpu_color="${RED}"
        [[ "$mem_num" =~ ^[0-9]+$ ]] && ((mem_num > 50)) && mem_color="${YELLOW}"
        [[ "$mem_num" =~ ^[0-9]+$ ]] && ((mem_num > 80)) && mem_color="${RED}"

        cursor_to "$row" 2 >/dev/tty
        echo -en "$(printf "%-25s" "${name:0:25}")" >/dev/tty
        echo -en "${cpu_color}$(printf "%8s" "$cpu")${NC}" >/dev/tty
        echo -en "$(printf "%15s" "$mem")" >/dev/tty
        echo -en "${mem_color}$(printf "%8s" "$mem_pct")${NC}" >/dev/tty
        ((row++))
        ((count++))
    done <<< "$data"

    if [[ $count -eq 0 ]]; then
        cursor_to "$row" 2 >/dev/tty
        echo -en "${DIM}No running containers${NC}" >/dev/tty
        ((row++))
    fi

    echo "$row"
}

# Render docker volumes table
render_docker_volumes_detail() {
    local row="$1"
    local data="$2"
    local max_rows="${3:-10}"

    render_storage_section "Database Volumes" "$row" >/dev/tty
    ((row++))

    cursor_to "$row" 2 >/dev/tty
    printf "${DIM}%-15s %-15s %10s${NC}" "Project" "Type" "Size" >/dev/tty
    ((row++))

    local count=0
    while IFS='|' read -r project vol_type size; do
        [[ -z "$project" || "$project" == "NOT_AVAILABLE" || "$project" == "NO_VOLUMES" ]] && continue
        ((count >= max_rows)) && break

        cursor_to "$row" 2 >/dev/tty
        printf "%-15s %-15s %10s" "$project" "$vol_type" "$size" >/dev/tty
        ((row++))
        ((count++))
    done <<< "$data"

    if [[ $count -eq 0 ]]; then
        cursor_to "$row" 2 >/dev/tty
        echo -en "${DIM}No database volumes found${NC}" >/dev/tty
        ((row++))
    fi

    echo "$row"
}

# Render docker detail page
render_docker_detail_page() {
    local metrics="$1"
    local instance_name="$2"
    local start_row="${3:-5}"

    local row="$start_row"

    # Page header
    cursor_to "$row" 2 >/dev/tty
    echo -en "${CYAN}${BOLD}━━━ Docker Detail: ${instance_name} ━━━${NC}" >/dev/tty
    ((row += 2))

    # Docker system df
    local docker_running=$(parse_metric "$metrics" "DOCKER_RUNNING")

    if [[ "$docker_running" != "true" ]]; then
        cursor_to "$row" 2 >/dev/tty
        echo -en "${YELLOW}Docker is not running on this instance${NC}" >/dev/tty
        echo "$row"
        return
    fi

    # Container stats
    local container_stats=$(echo "$metrics" | sed -n '/^DOCKER_STATS:/,/^[A-Z_]*:/p' | grep -v "^DOCKER_STATS:" | grep -v "^[A-Z_]*:$" | head -15)
    row=$(render_docker_containers_detail "$row" "$container_stats" 10)
    ((row++))

    # Database volumes
    local db_volumes=$(echo "$metrics" | sed -n '/^DB_VOLUMES:/,/^[A-Z_]*:/p' | grep -v "^DB_VOLUMES:" | grep -v "^[A-Z_]*:$")
    row=$(render_docker_volumes_detail "$row" "$db_volumes" 8)

    echo "$row"
}

# ============================================================================
# PAGE 4: PROCESS/CPU DETAIL
# ============================================================================

# Render process table with more detail
render_process_table_detail() {
    local row="$1"
    local data="$2"
    local max_rows="${3:-15}"

    render_storage_section "Top Processes by CPU" "$row" >/dev/tty
    ((row++))

    cursor_to "$row" 2 >/dev/tty
    printf "${DIM}%-12s %8s %8s %-40s${NC}" "User" "CPU" "Memory" "Command" >/dev/tty
    ((row++))

    local count=0
    while IFS='|' read -r user cpu mem cmd; do
        [[ -z "$user" ]] && continue
        ((count >= max_rows)) && break

        # Color code high usage
        local cpu_color="${NC}"
        local cpu_num="${cpu%\%}"
        [[ "$cpu_num" =~ ^[0-9]+$ ]] && ((cpu_num > 25)) && cpu_color="${YELLOW}"
        [[ "$cpu_num" =~ ^[0-9]+$ ]] && ((cpu_num > 50)) && cpu_color="${RED}"

        cursor_to "$row" 2 >/dev/tty
        echo -en "$(printf "%-12s" "$user")" >/dev/tty
        echo -en "${cpu_color}$(printf "%8s" "$cpu")${NC}" >/dev/tty
        echo -en "$(printf "%8s" "$mem")" >/dev/tty
        echo -en " $(printf "%-40s" "${cmd:0:40}")" >/dev/tty
        ((row++))
        ((count++))
    done <<< "$data"

    echo "$row"
}

# Render CPU/memory detail page
render_cpu_detail_page() {
    local metrics="$1"
    local instance_name="$2"
    local start_row="${3:-5}"

    local row="$start_row"

    # Page header
    cursor_to "$row" 2 >/dev/tty
    echo -en "${CYAN}${BOLD}━━━ Process/CPU Detail: ${instance_name} ━━━${NC}" >/dev/tty
    ((row += 2))

    # System stats
    local cpu_pct=$(parse_metric "$metrics" "CPU_PCT")
    local load_avg=$(parse_metric "$metrics" "LOAD_AVG")
    local mem_info=$(parse_metric "$metrics" "MEMORY")

    IFS='|' read -r mem_total mem_used mem_free mem_avail mem_pct <<< "$mem_info"

    cursor_to "$row" 2 >/dev/tty
    echo -en "CPU Usage: " >/dev/tty
    local cpu_num="${cpu_pct%\%}"
    progress_bar "${cpu_num:-0}" 100 40 >/dev/tty
    echo -en " ${cpu_pct:-0}%" >/dev/tty
    ((row++))

    cursor_to "$row" 2 >/dev/tty
    echo -en "Memory:    " >/dev/tty
    local mem_num="${mem_pct%\%}"
    progress_bar "${mem_num:-0}" 100 40 >/dev/tty
    echo -en " ${mem_used:-?}/${mem_total:-?} (${mem_pct:-?})" >/dev/tty
    ((row++))

    cursor_to "$row" 2 >/dev/tty
    echo -en "Load Avg:  ${load_avg:-N/A}" >/dev/tty
    ((row += 2))

    # Process table
    local top_procs=$(echo "$metrics" | sed -n '/^TOP_PROCESSES:/,/^[A-Z_]*:/p' | grep -v "^TOP_PROCESSES:" | grep -v "^[A-Z_]*:$" | head -15)
    row=$(render_process_table_detail "$row" "$top_procs" 12)

    echo "$row"
}

# ============================================================================
# PAGE 5: TIME SERIES GRAPHS
# ============================================================================

# Render a simple ASCII line graph
# Usage: render_ascii_graph "val1 val2 val3..." width height min max
render_ascii_graph() {
    local values_str="$1"
    local width="${2:-60}"
    local height="${3:-8}"
    local min_val="${4:-0}"
    local max_val="${5:-100}"

    # Convert string to array
    local -a values=($values_str)
    local count=${#values[@]}

    if ((count == 0)); then
        for ((h=0; h<height; h++)); do
            echo -en "${DIM}"
            printf "     │"
            printf '%*s' "$width" '' | tr ' ' '·'
            echo -en "${NC}"
            echo ""
        done
        return
    fi

    # Calculate range
    local range=$((max_val - min_val))
    ((range <= 0)) && range=100

    # Render each row from top to bottom
    for ((row=height; row>=1; row--)); do
        local threshold=$(( min_val + row * range / height ))

        # Y-axis label
        if ((row == height)); then
            printf "%4d%%│" "$max_val"
        elif ((row == 1)); then
            printf "%4d%%│" "$min_val"
        else
            printf "     │"
        fi

        # Render graph line
        local step=1
        ((count > width)) && step=$((count / width))

        local col=0
        local i=0
        while ((col < width && i < count)); do
            local v="${values[$i]}"
            [[ -z "$v" || ! "$v" =~ ^[0-9]+$ ]] && v=0

            if ((v >= threshold)); then
                echo -en "${GREEN}█${NC}"
            elif ((v >= threshold - range/height/2)); then
                echo -en "${YELLOW}▄${NC}"
            else
                echo -n " "
            fi
            ((i += step))
            ((col++))
        done

        # Pad remaining
        while ((col < width)); do
            echo -n " "
            ((col++))
        done

        echo ""
    done

    # X-axis
    printf "     └"
    printf '─%.0s' $(seq 1 $width)
    echo ""
}

# Render time series page
render_time_series_page() {
    local start_row="${1:-5}"

    local row="$start_row"

    # Page header
    cursor_to "$row" 2
    echo -en "${CYAN}${BOLD}━━━ Time Series Graphs ━━━${NC}"
    ((row += 2))

    # Check if history is available
    if ! type get_metric_history &>/dev/null; then
        cursor_to "$row" 2
        echo -en "${YELLOW}Time series history not available${NC}"
        cursor_to $((row + 1)) 2
        echo -en "${DIM}History module not loaded${NC}"
        echo "$row"
        return
    fi

    # Get history data
    local cpu_hist_i1=$(get_metric_history "instance1" "cpu" 30)
    local cpu_hist_i2=$(get_metric_history "instance2" "cpu" 30)
    local cpu_hist_i3=$(get_metric_history "instance3" "cpu" 30)
    local mem_hist_i1=$(get_metric_history "instance1" "mem" 30)
    local mem_hist_i2=$(get_metric_history "instance2" "mem" 30)
    local mem_hist_i3=$(get_metric_history "instance3" "mem" 30)
    local disk_hist_i1=$(get_metric_history "instance1" "disk" 30)
    local disk_hist_i2=$(get_metric_history "instance2" "disk" 30)
    local disk_hist_i3=$(get_metric_history "instance3" "disk" 30)

    # Instance 1 CPU graph
    cursor_to "$row" 2
    echo -en "${BOLD}Instance 1 - CPU Usage (last 30 samples)${NC}"
    ((row++))

    if [[ -n "$cpu_hist_i1" && "$cpu_hist_i1" != " " ]]; then
        for ((h=0; h<7; h++)); do
            cursor_to "$((row + h))" 2
        done
        cursor_to "$row" 2
        render_ascii_graph "$cpu_hist_i1" 60 6 0 100
        ((row += 8))
    else
        cursor_to "$row" 2
        echo -en "${DIM}Collecting data... (history will appear after a few refreshes)${NC}"
        ((row += 2))
    fi

    ((row++))  # Space between graphs

    # Instance 2 CPU graph
    cursor_to "$row" 2
    echo -en "${BOLD}Instance 2 - CPU Usage (last 30 samples)${NC}"
    ((row++))

    if [[ -n "$cpu_hist_i2" && "$cpu_hist_i2" != " " ]]; then
        for ((h=0; h<7; h++)); do
            cursor_to "$((row + h))" 2
        done
        cursor_to "$row" 2
        render_ascii_graph "$cpu_hist_i2" 60 6 0 100
        ((row += 8))
    else
        cursor_to "$row" 2
        echo -en "${DIM}Collecting data... (history will appear after a few refreshes)${NC}"
        ((row += 2))
    fi

    ((row++))  # Space between graphs

    # Instance 3 CPU graph
    cursor_to "$row" 2
    echo -en "${BOLD}Instance 3 - CPU Usage (last 30 samples)${NC}"
    ((row++))

    if [[ -n "$cpu_hist_i3" && "$cpu_hist_i3" != " " ]]; then
        for ((h=0; h<7; h++)); do
            cursor_to "$((row + h))" 2
        done
        cursor_to "$row" 2
        render_ascii_graph "$cpu_hist_i3" 60 6 0 100
        ((row += 8))
    else
        cursor_to "$row" 2
        echo -en "${DIM}Collecting data... (history will appear after a few refreshes)${NC}"
        ((row += 2))
    fi

    ((row += 2))  # Space before sparklines section

    # Sparkline comparison section
    cursor_to "$row" 2
    echo -en "${BOLD}Trend Sparklines${NC}"
    ((row += 2))  # Extra space after header

    cursor_to "$row" 2
    echo -en "CPU I1:  "
    if [[ -n "$cpu_hist_i1" && "$cpu_hist_i1" != " " ]]; then
        sparkline $cpu_hist_i1
    else
        echo -en "${DIM}--${NC}"
    fi
    ((row += 2))  # Space between rows

    cursor_to "$row" 2
    echo -en "CPU I2:  "
    if [[ -n "$cpu_hist_i2" && "$cpu_hist_i2" != " " ]]; then
        sparkline $cpu_hist_i2
    else
        echo -en "${DIM}--${NC}"
    fi
    ((row += 2))  # Space between rows

    cursor_to "$row" 2
    echo -en "CPU I3:  "
    if [[ -n "$cpu_hist_i3" && "$cpu_hist_i3" != " " ]]; then
        sparkline $cpu_hist_i3
    else
        echo -en "${DIM}--${NC}"
    fi
    ((row += 2))  # Space between rows

    cursor_to "$row" 2
    echo -en "Mem I1:  "
    if [[ -n "$mem_hist_i1" && "$mem_hist_i1" != " " ]]; then
        sparkline $mem_hist_i1
    else
        echo -en "${DIM}--${NC}"
    fi
    ((row += 2))  # Space between rows

    cursor_to "$row" 2
    echo -en "Mem I2:  "
    if [[ -n "$mem_hist_i2" && "$mem_hist_i2" != " " ]]; then
        sparkline $mem_hist_i2
    else
        echo -en "${DIM}--${NC}"
    fi
    ((row += 2))  # Space between rows

    cursor_to "$row" 2
    echo -en "Mem I3:  "
    if [[ -n "$mem_hist_i3" && "$mem_hist_i3" != " " ]]; then
        sparkline $mem_hist_i3
    else
        echo -en "${DIM}--${NC}"
    fi
    ((row += 2))  # Space between rows

    cursor_to "$row" 2
    echo -en "Disk I1: "
    if [[ -n "$disk_hist_i1" && "$disk_hist_i1" != " " ]]; then
        sparkline $disk_hist_i1
    else
        echo -en "${DIM}--${NC}"
    fi
    ((row += 2))  # Space between rows

    cursor_to "$row" 2
    echo -en "Disk I2: "
    if [[ -n "$disk_hist_i2" && "$disk_hist_i2" != " " ]]; then
        sparkline $disk_hist_i2
    else
        echo -en "${DIM}--${NC}"
    fi
    ((row += 2))  # Space between rows

    cursor_to "$row" 2
    echo -en "Disk I3: "
    if [[ -n "$disk_hist_i3" && "$disk_hist_i3" != " " ]]; then
        sparkline $disk_hist_i3
    else
        echo -en "${DIM}--${NC}"
    fi

    echo "$row"
}

# ============================================================================
# PAGE 6: NATIVE SERVICES
# ============================================================================

# Cache for services data
SERVICES_CACHE_I1=""
SERVICES_CACHE_I2=""

# Render Node.js services table
render_node_services_table() {
    local row="$1"
    local data="$2"
    local max_rows="${3:-10}"

    render_storage_section "Node.js (Frontends)" "$row" >/dev/tty
    ((row++))

    cursor_to "$row" 2 >/dev/tty
    printf "${DIM}%-15s %8s %-20s %10s${NC}" "Project" "Port" "Process" "Status" >/dev/tty
    ((row++))

    local count=0
    while IFS='|' read -r project port process status; do
        [[ -z "$project" || "$project" == "NOT_AVAILABLE" ]] && continue
        ((count >= max_rows)) && break

        # Status indicator
        local status_icon="${GREEN}●${NC}"
        [[ "$status" != "running" ]] && status_icon="${RED}○${NC}"

        cursor_to "$row" 2 >/dev/tty
        printf "%-15s %8s %-20s " "${project:0:15}" "$port" "${process:0:20}" >/dev/tty
        echo -en "$status_icon Running" >/dev/tty
        ((row++))
        ((count++))
    done <<< "$data"

    if [[ $count -eq 0 ]]; then
        cursor_to "$row" 2 >/dev/tty
        echo -en "${DIM}No Node.js services running${NC}" >/dev/tty
        ((row++))
    fi

    echo "$row"
}

# Render Python/uvicorn services table
render_python_services_table() {
    local row="$1"
    local data="$2"
    local max_rows="${3:-10}"

    render_storage_section "Python/uvicorn (Backends)" "$row" >/dev/tty
    ((row++))

    cursor_to "$row" 2 >/dev/tty
    printf "${DIM}%-15s %8s %10s %10s${NC}" "Project" "Port" "Workers" "Status" >/dev/tty
    ((row++))

    local count=0
    while IFS='|' read -r project port workers status; do
        [[ -z "$project" || "$project" == "NOT_AVAILABLE" ]] && continue
        ((count >= max_rows)) && break

        # Status indicator
        local status_icon="${GREEN}●${NC}"
        [[ "$status" != "running" ]] && status_icon="${RED}○${NC}"

        cursor_to "$row" 2 >/dev/tty
        printf "%-15s %8s %10s " "${project:0:15}" "$port" "$workers" >/dev/tty
        echo -en "$status_icon Running" >/dev/tty
        ((row++))
        ((count++))
    done <<< "$data"

    if [[ $count -eq 0 ]]; then
        cursor_to "$row" 2 >/dev/tty
        echo -en "${DIM}No Python/uvicorn services running${NC}" >/dev/tty
        ((row++))
    fi

    echo "$row"
}

# Parse services section from collected data
parse_services_section() {
    local data="$1"
    local section="$2"

    echo "$data" | sed -n "/^${section}:/,/^[A-Z_]*:/p" | grep -v "^${section}:" | grep -v "^[A-Z_]*:$" | grep -v "^===" | head -20
}

# Render services detail page for an instance
render_services_instance() {
    local services_data="$1"
    local instance_name="$2"
    local start_row="$3"

    local row="$start_row"

    # Instance header
    cursor_to "$row" 2 >/dev/tty
    echo -en "${CYAN}${BOLD}━━━ ${instance_name} ━━━${NC}" >/dev/tty
    ((row += 2))

    # Node.js services
    local node_data=$(parse_services_section "$services_data" "NODE_SERVICES")
    row=$(render_node_services_table "$row" "$node_data" 6)
    ((row++))

    # Python services
    local python_data=$(parse_services_section "$services_data" "PYTHON_SERVICES")
    row=$(render_python_services_table "$row" "$python_data" 8)

    echo "$row"
}

# Render full services page
render_services_page() {
    local services_i1="$1"
    local services_i2="$2"
    local services_i3="$3"
    local start_row="${4:-5}"

    local row="$start_row"

    # Check if we have any data
    if [[ -z "$services_i1" && -z "$services_i2" && -z "$services_i3" ]]; then
        cursor_to "$row" 2 >/dev/tty
        echo -en "${YELLOW}Collecting services data...${NC}" >/dev/tty
        return
    fi

    # Render Instance 1
    if [[ "$ANIMATE_FOCUS" == "1" || "$ANIMATE_FOCUS" == "" || "$ANIMATE_FOCUS" == "all" ]] && [[ -n "$services_i1" ]]; then
        row=$(render_services_instance "$services_i1" "Instance 1" "$row")
        ((row += 2))
    fi

    # Render Instance 2
    if [[ "$ANIMATE_FOCUS" == "2" || "$ANIMATE_FOCUS" == "all" ]] && [[ -n "$services_i2" ]]; then
        row=$(render_services_instance "$services_i2" "Instance 2" "$row")
        ((row += 2))
    fi

    # Render Instance 3
    if [[ "$ANIMATE_FOCUS" == "3" || "$ANIMATE_FOCUS" == "all" ]] && [[ -n "$services_i3" ]]; then
        row=$(render_services_instance "$services_i3" "Instance 3" "$row")
    fi
}

# ============================================================================
# PAGE DISPATCHER
# ============================================================================

# Render the appropriate page based on CURRENT_PAGE
render_current_page() {
    local metrics_i1="$1"
    local metrics_i2="$2"
    local metrics_i3="$3"
    local metrics_local="$4"
    local storage_detail_i1="$5"
    local storage_detail_i2="$6"
    local storage_detail_i3="$7"
    local services_i1="${8:-$SERVICES_CACHE_I1}"
    local services_i2="${9:-$SERVICES_CACHE_I2}"
    local services_i3="${10:-$SERVICES_CACHE_I3}"

    case "$CURRENT_PAGE" in
        1)
            # Overview page - handled by existing dashboard render
            return 1  # Signal to use default renderer
            ;;
        2)
            # Storage Detail page
            if [[ "$PAGE_CHANGED" == "true" ]]; then
                screen_clear
                sleep 0.05  # Brief pause for clean transition
            fi
            cursor_home

            # Header
            echo -en "${CYAN}${BOLD}┌────────────────────────────────────────────────────────────────────────────┐${NC}"
            cursor_to 1 0
            echo -en "${CYAN}│  SYSMON - Storage Detail                                   $(get_page_status) │${NC}"
            cursor_to 2 0
            echo -en "${CYAN}└────────────────────────────────────────────────────────────────────────────┘${NC}"

            # Render page indicator
            cursor_to 3 0
            render_page_indicator 78

            # Render storage detail for focused instance or all
            local row=5
            if [[ "$ANIMATE_FOCUS" == "1" || "$ANIMATE_FOCUS" == "" || "$ANIMATE_FOCUS" == "all" ]]; then
                if [[ -n "$storage_detail_i1" ]]; then
                    row=$(render_storage_detail_page "$storage_detail_i1" "Instance 1" "$row")
                fi
            fi

            if [[ "$ANIMATE_FOCUS" == "2" || "$ANIMATE_FOCUS" == "all" ]]; then
                if [[ -n "$storage_detail_i2" ]]; then
                    row=$(render_storage_detail_page "$storage_detail_i2" "Instance 2" "$((row + 2))")
                fi
            fi

            if [[ "$ANIMATE_FOCUS" == "3" || "$ANIMATE_FOCUS" == "all" ]]; then
                if [[ -n "$storage_detail_i3" ]]; then
                    row=$(render_storage_detail_page "$storage_detail_i3" "Instance 3" "$((row + 2))")
                fi
            fi
            ;;
        3)
            # Docker Detail page
            if [[ "$PAGE_CHANGED" == "true" ]]; then
                screen_clear
                sleep 0.05  # Brief pause for clean transition
            fi
            cursor_home

            echo -en "${CYAN}${BOLD}┌────────────────────────────────────────────────────────────────────────────┐${NC}"
            cursor_to 1 0
            echo -en "${CYAN}│  SYSMON - Docker Detail                                    $(get_page_status) │${NC}"
            cursor_to 2 0
            echo -en "${CYAN}└────────────────────────────────────────────────────────────────────────────┘${NC}"

            cursor_to 3 0
            render_page_indicator 78

            local row=5
            if [[ "$ANIMATE_FOCUS" == "1" || "$ANIMATE_FOCUS" == "" || "$ANIMATE_FOCUS" == "all" ]]; then
                row=$(render_docker_detail_page "$metrics_i1" "Instance 1" "$row")
            fi

            if [[ "$ANIMATE_FOCUS" == "2" || "$ANIMATE_FOCUS" == "all" ]]; then
                row=$(render_docker_detail_page "$metrics_i2" "Instance 2" "$((row + 2))")
            fi

            if [[ "$ANIMATE_FOCUS" == "3" || "$ANIMATE_FOCUS" == "all" ]]; then
                row=$(render_docker_detail_page "$metrics_i3" "Instance 3" "$((row + 2))")
            fi
            ;;
        4)
            # Process/CPU Detail page
            if [[ "$PAGE_CHANGED" == "true" ]]; then
                screen_clear
                sleep 0.05  # Brief pause for clean transition
            fi
            cursor_home

            echo -en "${CYAN}${BOLD}┌────────────────────────────────────────────────────────────────────────────┐${NC}"
            cursor_to 1 0
            echo -en "${CYAN}│  SYSMON - Process/CPU Detail                               $(get_page_status) │${NC}"
            cursor_to 2 0
            echo -en "${CYAN}└────────────────────────────────────────────────────────────────────────────┘${NC}"

            cursor_to 3 0
            render_page_indicator 78

            local row=5
            if [[ "$ANIMATE_FOCUS" == "1" || "$ANIMATE_FOCUS" == "" || "$ANIMATE_FOCUS" == "all" ]]; then
                row=$(render_cpu_detail_page "$metrics_i1" "Instance 1" "$row")
            fi

            if [[ "$ANIMATE_FOCUS" == "2" || "$ANIMATE_FOCUS" == "all" ]]; then
                row=$(render_cpu_detail_page "$metrics_i2" "Instance 2" "$((row + 2))")
            fi

            if [[ "$ANIMATE_FOCUS" == "3" || "$ANIMATE_FOCUS" == "all" ]]; then
                row=$(render_cpu_detail_page "$metrics_i3" "Instance 3" "$((row + 2))")
            fi
            ;;
        5)
            # Time Series page
            if [[ "$PAGE_CHANGED" == "true" ]]; then
                screen_clear
                sleep 0.05  # Brief pause for clean transition
            fi
            cursor_home

            echo -en "${CYAN}${BOLD}┌────────────────────────────────────────────────────────────────────────────┐${NC}"
            cursor_to 1 0
            echo -en "${CYAN}│  SYSMON - Time Series Graphs                               $(get_page_status) │${NC}"
            cursor_to 2 0
            echo -en "${CYAN}└────────────────────────────────────────────────────────────────────────────┘${NC}"

            cursor_to 3 0
            render_page_indicator 78

            render_time_series_page 5
            ;;
        6)
            # Services page (non-Docker services)
            if [[ "$PAGE_CHANGED" == "true" ]]; then
                screen_clear
                sleep 0.05  # Brief pause for clean transition
            fi
            cursor_home

            echo -en "${CYAN}${BOLD}┌────────────────────────────────────────────────────────────────────────────┐${NC}"
            cursor_to 1 0
            echo -en "${CYAN}│  SYSMON - Services (Non-Docker)                            $(get_page_status) │${NC}"
            cursor_to 2 0
            echo -en "${CYAN}└────────────────────────────────────────────────────────────────────────────┘${NC}"

            cursor_to 3 0
            render_page_indicator 78

            render_services_page "$services_i1" "$services_i2" "$services_i3" 5
            ;;
    esac

    return 0
}
