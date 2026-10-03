#!/bin/bash
# ============================================================================
# SYSMON - Data Collectors
# ============================================================================
# Functions to collect disk, CPU, Docker, and other system metrics
# ============================================================================

# Prevent double-sourcing
[[ -n "${SYSMON_COLLECTORS_LOADED:-}" ]] && return 0
SYSMON_COLLECTORS_LOADED=1

# ============================================================================
# DISK INFORMATION
# ============================================================================

# Collect disk usage for root filesystem
# Returns: total|used|available|percentage
collect_disk_info() {
    local df_output
    df_output=$(df -h / 2>/dev/null | tail -1)

    if [[ -z "$df_output" ]]; then
        echo "N/A|N/A|N/A|N/A"
        return 1
    fi

    # Parse df output: Filesystem Size Used Avail Use% Mounted
    local total used avail pct
    read -r _ total used avail pct _ <<< "$df_output"

    echo "${total}|${used}|${avail}|${pct}"
}

# Collect directory size
# Args: directory_path
# Returns: size in human-readable format
collect_dir_size() {
    local dir="$1"
    if [[ -d "$dir" ]]; then
        du -sh "$dir" 2>/dev/null | cut -f1
    else
        echo "N/A"
    fi
}

# Collect top N largest directories under a path
# Args: path, count (default 10)
# Returns: size|path (one per line)
collect_top_directories() {
    local base_path="$1"
    local count="${2:-10}"

    if [[ ! -d "$base_path" ]]; then
        return 1
    fi

    du -h --max-depth=1 "$base_path" 2>/dev/null | \
        sort -hr | \
        head -n "$count" | \
        awk '{print $1"|"$2}'
}

# Collect large files (>threshold)
# Args: path, threshold_bytes (default 100MB)
# Returns: size|path (one per line)
collect_large_files() {
    local base_path="$1"
    local threshold="${2:-104857600}"  # 100MB default

    if [[ ! -d "$base_path" ]]; then
        return 1
    fi

    find "$base_path" -type f -size +"$((threshold / 1024))k" 2>/dev/null | \
        head -n "${MAX_LARGE_FILES:-10}" | \
        while read -r file; do
            local size
            size=$(du -h "$file" 2>/dev/null | cut -f1)
            echo "${size}|${file}"
        done
}

# ============================================================================
# CPU & MEMORY INFORMATION
# ============================================================================

# Collect CPU usage percentage
# Returns: percentage (e.g., "45.2")
collect_cpu_usage() {
    # Method 1: top
    local cpu
    cpu=$(top -bn1 2>/dev/null | grep "Cpu(s)" | awk '{print $2}' | cut -d'%' -f1)

    if [[ -z "$cpu" ]]; then
        # Method 2: /proc/stat
        local cpu1 cpu2 idle1 idle2
        read -r _ cpu1 _ _ idle1 _ < /proc/stat
        sleep 0.5
        read -r _ cpu2 _ _ idle2 _ < /proc/stat
        local diff_cpu=$((cpu2 - cpu1))
        local diff_idle=$((idle2 - idle1))
        local diff_total=$((diff_cpu + diff_idle))
        if [[ $diff_total -gt 0 ]]; then
            cpu=$(echo "scale=1; $diff_cpu * 100 / $diff_total" | bc)
        else
            cpu="0"
        fi
    fi

    echo "${cpu:-0}"
}

# Collect load average
# Returns: 1min, 5min, 15min
collect_load_average() {
    uptime 2>/dev/null | grep -oP 'load average: \K.*' | tr -d ' ' || echo "N/A"
}

# Collect memory info
# Returns: total|used|free|available|percentage
collect_memory_info() {
    local mem_output
    mem_output=$(free -h 2>/dev/null | grep "^Mem:")

    if [[ -z "$mem_output" ]]; then
        echo "N/A|N/A|N/A|N/A|N/A"
        return 1
    fi

    # Parse: Mem: total used free shared buff/cache available
    local total used free available
    read -r _ total used free _ _ available <<< "$mem_output"

    # Calculate percentage
    local total_kb used_kb pct
    total_kb=$(free 2>/dev/null | grep "^Mem:" | awk '{print $2}')
    used_kb=$(free 2>/dev/null | grep "^Mem:" | awk '{print $3}')
    if [[ -n "$total_kb" && "$total_kb" -gt 0 ]]; then
        pct=$(echo "scale=1; $used_kb * 100 / $total_kb" | bc)
    else
        pct="N/A"
    fi

    echo "${total}|${used}|${free}|${available}|${pct}%"
}

# ============================================================================
# DOCKER INFORMATION
# ============================================================================

# Check if Docker is available
is_docker_available() {
    command -v docker &>/dev/null && docker info &>/dev/null 2>&1
}

# Collect Docker disk usage
# Returns: type|size|reclaimable (multiple lines)
collect_docker_disk() {
    if ! is_docker_available; then
        echo "NOT_AVAILABLE"
        return 1
    fi

    docker system df --format '{{.Type}}|{{.Size}}|{{.Reclaimable}}' 2>/dev/null
}

# Collect Docker container stats
# Returns: name|cpu|memory|mem_percent (multiple lines)
collect_docker_containers() {
    if ! is_docker_available; then
        echo "NOT_AVAILABLE"
        return 1
    fi

    local container_count
    container_count=$(docker ps -q 2>/dev/null | wc -l)

    if [[ "$container_count" -eq 0 ]]; then
        echo "NO_CONTAINERS"
        return 0
    fi

    docker stats --no-stream --format '{{.Name}}|{{.CPUPerc}}|{{.MemUsage}}|{{.MemPerc}}' 2>/dev/null | \
        head -n "${MAX_DOCKER_CONTAINERS:-15}"
}

# Collect running container count
collect_container_count() {
    if ! is_docker_available; then
        echo "0"
        return 1
    fi

    docker ps -q 2>/dev/null | wc -l
}

# Collect dangling image count
collect_dangling_images() {
    if ! is_docker_available; then
        echo "0"
        return 1
    fi

    docker images -f "dangling=true" -q 2>/dev/null | wc -l
}

# Collect stopped container count
collect_stopped_containers() {
    if ! is_docker_available; then
        echo "0"
        return 1
    fi

    docker ps -a -f "status=exited" -q 2>/dev/null | wc -l
}

# ============================================================================
# DATABASE VOLUMES
# ============================================================================

# Collect database volume sizes by project
# Returns: project|type|size (multiple lines)
collect_db_volumes() {
    if ! is_docker_available; then
        echo "NOT_AVAILABLE"
        return 1
    fi

    local volumes
    volumes=$(docker volume ls -q 2>/dev/null | grep -E "(postgres|timescale|database|db)" | sort)

    if [[ -z "$volumes" ]]; then
        echo "NO_VOLUMES"
        return 0
    fi

    echo "$volumes" | while read -r vol; do
        [[ -z "$vol" ]] && continue

        # Extract project name (first part before - or _)
        local project
        project=$(echo "$vol" | sed -E 's/^([a-z]+)[-_].*/\1/')

        # Determine volume type
        local vol_type
        if echo "$vol" | grep -qi "timescale"; then
            vol_type="TimescaleDB"
        elif echo "$vol" | grep -qi "postgres"; then
            vol_type="PostgreSQL"
        elif echo "$vol" | grep -qi "database"; then
            vol_type="Database"
        else
            vol_type="DB"
        fi

        # Get size (this can be slow)
        local size
        size=$(docker run --rm -v "${vol}:/data" alpine du -sh /data 2>/dev/null | cut -f1)
        size="${size:-N/A}"

        echo "${project}|${vol_type}|${size}"
    done
}

# Quick DB volume list (without sizes)
collect_db_volumes_quick() {
    if ! is_docker_available; then
        echo "NOT_AVAILABLE"
        return 1
    fi

    docker volume ls -q 2>/dev/null | grep -E "(postgres|timescale|database|db)" | sort | while read -r vol; do
        local project vol_type
        project=$(echo "$vol" | sed -E 's/^([a-z]+)[-_].*/\1/')

        if echo "$vol" | grep -qi "timescale"; then
            vol_type="TimescaleDB"
        elif echo "$vol" | grep -qi "postgres"; then
            vol_type="PostgreSQL"
        else
            vol_type="DB"
        fi

        echo "${project}|${vol_type}|--"
    done
}

# ============================================================================
# PROJECT-BASED METRICS
# ============================================================================

# Get all projects for an instance
# Args: instance_number (1 or 2)
# Returns: space-separated list of project names
get_instance_projects() {
    local instance="$1"
    case "$instance" in
        1|instance1) echo "$INSTANCE1_PROJECTS" ;;
        2|instance2) echo "$INSTANCE2_PROJECTS" ;;
        *) echo "" ;;
    esac
}

# Collect metrics for a single project
# Args: project_name
# Returns: structured data for the project
collect_project_metrics() {
    local project="$1"
    local fleet_dir="${FLEET_DIR:-$HOME/fleet}"

    # Project directory size
    local dir_size="N/A"
    if [[ -d "$fleet_dir/$project" ]]; then
        dir_size=$(du -sh "$fleet_dir/$project" 2>/dev/null | cut -f1)
    fi
    echo "DIR_SIZE:$dir_size"

    # Docker containers for this project
    if is_docker_available; then
        local containers
        containers=$(docker ps --format '{{.Names}}' 2>/dev/null | grep -E "^${project}[-_]" | wc -l)
        echo "CONTAINERS:$containers"

        # Container details
        echo "CONTAINER_LIST:"
        docker ps --format '{{.Names}}|{{.Status}}|{{.Ports}}' 2>/dev/null | grep -E "^${project}[-_]" | head -5

        # Database volume
        local db_vol
        db_vol=$(docker volume ls -q 2>/dev/null | grep -E "^${project}[-_].*(postgres|timescale|database|db)" | head -1)
        if [[ -n "$db_vol" ]]; then
            local db_size
            db_size=$(docker run --rm -v "${db_vol}:/data" alpine du -sh /data 2>/dev/null | cut -f1)
            local db_type="DB"
            if echo "$db_vol" | grep -qi "timescale"; then
                db_type="TimescaleDB"
            elif echo "$db_vol" | grep -qi "postgres"; then
                db_type="PostgreSQL"
            fi
            echo "DB_VOLUME:${db_type}|${db_size:-N/A}"
        else
            echo "DB_VOLUME:none"
        fi
    else
        echo "CONTAINERS:0"
        echo "CONTAINER_LIST:"
        echo "DB_VOLUME:none"
    fi

    # Check for running processes
    local procs
    procs=$(pgrep -c -f "$project" 2>/dev/null || echo "0")
    echo "PROCESSES:$procs"
}

# Collect all project metrics for an instance (remote)
# Args: instance_number, project_list (optional, defaults to instance projects)
# Returns: structured data for all projects
collect_remote_project_metrics() {
    local instance="$1"
    local projects="${2:-$(get_instance_projects "$instance")}"

    local ssh_cmd
    ssh_cmd=$(get_ssh_cmd "$instance")

    if [[ -z "$ssh_cmd" ]]; then
        return 1
    fi

    # Build remote script for project collection
    # Note: Using heredoc with quoted delimiter to prevent local expansion
    local remote_script
    remote_script=$(cat << 'REMOTE_EOF'
FLEET_DIR="$HOME/fleet"

for project in __PROJECTS__; do
    echo "PROJECT:$project"

    # Directory size
    if [ -d "$FLEET_DIR/$project" ]; then
        dir_size=$(du -sh "$FLEET_DIR/$project" 2>/dev/null | cut -f1)
    else
        dir_size="N/A"
    fi
    echo "DIR_SIZE:$dir_size"

    # Docker containers
    if command -v docker &>/dev/null && docker info &>/dev/null 2>&1; then
        containers=$(docker ps --format '{{.Names}}' 2>/dev/null | grep -E "^${project}[-_]" | wc -l)
        echo "CONTAINERS:$containers"

        # Container details
        echo "CONTAINER_LIST:"
        docker ps --format '{{.Names}}|{{.Status}}' 2>/dev/null | grep -E "^${project}[-_]" | head -5

        # Database volume
        db_vol=$(docker volume ls -q 2>/dev/null | grep -E "^${project}[-_].*(postgres|timescale|database|db)" | head -1)
        if [ -n "$db_vol" ]; then
            db_size=$(docker run --rm -v "${db_vol}:/data" alpine du -sh /data 2>/dev/null | cut -f1)
            db_type="DB"
            if echo "$db_vol" | grep -qi "timescale"; then
                db_type="TimescaleDB"
            elif echo "$db_vol" | grep -qi "postgres"; then
                db_type="PostgreSQL"
            fi
            echo "DB_VOLUME:${db_type}|${db_size:-N/A}"
        else
            echo "DB_VOLUME:none"
        fi
    else
        echo "CONTAINERS:0"
        echo "CONTAINER_LIST:"
        echo "DB_VOLUME:none"
    fi

    echo "---"
done
REMOTE_EOF
)
    # Replace placeholder with actual projects
    remote_script="${remote_script/__PROJECTS__/$projects}"

    # Execute via SSH (need eval because ssh_cmd contains quoted paths)
    eval "$ssh_cmd" '"$remote_script"' 2>/dev/null
}

# ============================================================================
# PROCESS INFORMATION
# ============================================================================

# Collect top processes by CPU
# Returns: user|cpu|mem|command (multiple lines)
collect_top_processes() {
    local count="${1:-${MAX_TOP_PROCESSES:-7}}"

    ps aux --sort=-%cpu 2>/dev/null | \
        head -n $((count + 1)) | \
        tail -n "$count" | \
        awk '{printf "%s|%.1f%%|%.1f%%|%s\n", $1, $3, $4, $11}'
}

# Count Claude processes
collect_claude_count() {
    pgrep -c claude 2>/dev/null || echo "0"
}

# Count tmux sessions
collect_tmux_count() {
    tmux list-sessions 2>/dev/null | wc -l || echo "0"
}

# ============================================================================
# FLEET SPECIFIC COLLECTORS
# ============================================================================

# Collect node_modules directories count and size
collect_node_modules_info() {
    local base_path="${1:-$FLEET_DIR}"

    if [[ ! -d "$base_path" ]]; then
        echo "0|N/A"
        return 1
    fi

    local count size
    count=$(find "$base_path" -type d -name "node_modules" -prune 2>/dev/null | wc -l)
    size=$(find "$base_path" -type d -name "node_modules" -prune -exec du -csh {} + 2>/dev/null | tail -1 | cut -f1)

    echo "${count}|${size:-N/A}"
}

# Collect .next directories count and size
collect_next_dirs_info() {
    local base_path="${1:-$FLEET_DIR}"

    if [[ ! -d "$base_path" ]]; then
        echo "0|N/A"
        return 1
    fi

    local count size
    count=$(find "$base_path" -maxdepth 3 -type d -name ".next" 2>/dev/null | wc -l)
    size=$(find "$base_path" -maxdepth 3 -type d -name ".next" -exec du -csh {} + 2>/dev/null | tail -1 | cut -f1)

    echo "${count}|${size:-N/A}"
}

# Collect shared venv size
collect_venv_size() {
    local venv_path="${FLEET_ENVIRONMENTS_DIR:-${FLEET_DIR}/environments}"
    collect_dir_size "$venv_path"
}

# Collect preserves directory size
collect_preserves_size() {
    collect_dir_size "$FLEET_PRESERVE_DIR"
}

# ============================================================================
# REMOTE COLLECTION
# ============================================================================

# Execute command on remote instance
# Args: instance_number, command
# Returns: command output
remote_exec() {
    local instance="$1"
    shift
    local cmd="$*"

    local ssh_cmd
    ssh_cmd=$(get_ssh_cmd "$instance")

    if [[ -z "$ssh_cmd" ]]; then
        log_error "Failed to get SSH command for instance $instance"
        return 1
    fi

    eval "$ssh_cmd '$cmd'" 2>/dev/null
}

# Collect all metrics from local system
# Args: quick_mode (true/false) - skip slow du commands if true
# Returns: structured data string (same format as collect_remote_metrics)
collect_local_metrics() {
    local quick_mode="${1:-false}"

    echo "DISK_INFO:"
    df -h / 2>/dev/null | tail -1 | awk '{print $2"|"$3"|"$4"|"$5}'

    echo "LOAD_AVG:"
    uptime 2>/dev/null | grep -oP 'load average: \K.*' | tr -d ' ' || echo "N/A"

    echo "MEMORY:"
    local total used pct
    total=$(free | grep "^Mem:" | awk '{print $2}')
    used=$(free | grep "^Mem:" | awk '{print $3}')
    if [[ "$total" -gt 0 ]] 2>/dev/null; then
        pct=$(echo "scale=1; $used * 100 / $total" | bc)
    else
        pct="N/A"
    fi
    free -h | grep "^Mem:" | awk -v p="$pct" '{print $2"|"$3"|"$4"|"$7"|"p"%"}'

    echo "CPU_PCT:"
    top -bn1 2>/dev/null | grep "Cpu(s)" | awk '{print $2}' | cut -d'%' -f1 || echo "0"

    echo "DOCKER_RUNNING:"
    if command -v docker &>/dev/null && docker info &>/dev/null 2>&1; then
        echo "true"
    else
        echo "false"
    fi

    echo "CONTAINER_COUNT:"
    docker ps -q 2>/dev/null | wc -l || echo "0"

    echo "DOCKER_STATS:"
    if [[ "$quick_mode" != "true" ]] && docker info &>/dev/null 2>&1; then
        docker stats --no-stream --format '{{.Name}}|{{.CPUPerc}}|{{.MemUsage}}|{{.MemPerc}}' 2>/dev/null | head -15
    fi

    echo "CLAUDE_COUNT:"
    pgrep -c claude 2>/dev/null || echo "0"

    echo "TMUX_COUNT:"
    tmux list-sessions 2>/dev/null | wc -l || echo "0"

    # Slow directory sizing - skip in quick mode
    if [[ "$quick_mode" != "true" ]]; then
        echo "FLEET_SIZE:"
        du -sh ~/fleet 2>/dev/null | cut -f1 || echo "N/A"

        echo "VENV_SIZE:"
        du -sh ~/fleet/environments 2>/dev/null | cut -f1 || echo "N/A"

        echo "PRESERVES_SIZE:"
        du -sh ~/fleet-preserves 2>/dev/null | cut -f1 || echo "N/A"
    else
        echo "FLEET_SIZE:"
        echo "--"
        echo "VENV_SIZE:"
        echo "--"
        echo "PRESERVES_SIZE:"
        echo "--"
    fi

    echo "TOP_PROCESSES:"
    ps aux --sort=-%cpu 2>/dev/null | head -6 | tail -5 | awk '{printf "%s|%.1f%%|%.1f%%|%s\n", $1, $3, $4, $11}'
}

# Collect all metrics from remote instance
# Args: instance_number, quick_mode (true/false)
# Returns: structured data string
collect_remote_metrics() {
    local instance="$1"
    local quick_mode="${2:-false}"

    local ssh_cmd
    ssh_cmd=$(get_ssh_cmd "$instance")

    if [[ -z "$ssh_cmd" ]]; then
        return 1
    fi

    # Build remote collection script - fast version for quick_mode
    local remote_script
    if [[ "$quick_mode" == "true" ]]; then
        remote_script='
        echo "DISK_INFO:"
        df -h / 2>/dev/null | tail -1 | awk "{print \$2\"|\"\$3\"|\"\$4\"|\"\$5}"

        echo "LOAD_AVG:"
        uptime 2>/dev/null | grep -oP "load average: \K.*" | tr -d " " || echo "N/A"

        echo "MEMORY:"
        total=$(free | grep "^Mem:" | awk "{print \$2}")
        used=$(free | grep "^Mem:" | awk "{print \$3}")
        if [ "$total" -gt 0 ] 2>/dev/null; then
            pct=$(echo "scale=1; $used * 100 / $total" | bc)
        else
            pct="N/A"
        fi
        free -h | grep "^Mem:" | awk -v p="$pct" "{print \$2\"|\"\$3\"|\"\$4\"|\"\$7\"|\"p\"%\"}"

        echo "CPU_PCT:"
        top -bn1 2>/dev/null | grep "Cpu(s)" | awk "{print \$2}" | cut -d"%" -f1 || echo "0"

        echo "DOCKER_RUNNING:"
        if command -v docker &>/dev/null && docker info &>/dev/null 2>&1; then
            echo "true"
        else
            echo "false"
        fi

        echo "CONTAINER_COUNT:"
        docker ps -q 2>/dev/null | wc -l || echo "0"

        echo "DOCKER_STATS:"

        echo "CLAUDE_COUNT:"
        pgrep -c claude 2>/dev/null || echo "0"

        echo "TMUX_COUNT:"
        tmux list-sessions 2>/dev/null | wc -l || echo "0"

        echo "FLEET_SIZE:"
        echo "--"
        echo "VENV_SIZE:"
        echo "--"
        echo "PRESERVES_SIZE:"
        echo "--"

        echo "TOP_PROCESSES:"
        ps aux --sort=-%cpu 2>/dev/null | head -6 | tail -5 | awk "{printf \"%s|%.1f%%|%.1f%%|%s\\n\", \$1, \$3, \$4, \$11}"
        '
    else
        remote_script='
        echo "DISK_INFO:"
        df -h / 2>/dev/null | tail -1 | awk "{print \$2\"|\"\$3\"|\"\$4\"|\"\$5}"

        echo "LOAD_AVG:"
        uptime 2>/dev/null | grep -oP "load average: \K.*" | tr -d " " || echo "N/A"

        echo "MEMORY:"
        total=$(free | grep "^Mem:" | awk "{print \$2}")
        used=$(free | grep "^Mem:" | awk "{print \$3}")
        if [ "$total" -gt 0 ] 2>/dev/null; then
            pct=$(echo "scale=1; $used * 100 / $total" | bc)
        else
            pct="N/A"
        fi
        free -h | grep "^Mem:" | awk -v p="$pct" "{print \$2\"|\"\$3\"|\"\$4\"|\"\$7\"|\"p\"%\"}"

        echo "CPU_PCT:"
        top -bn1 2>/dev/null | grep "Cpu(s)" | awk "{print \$2}" | cut -d"%" -f1 || echo "0"

        echo "DOCKER_RUNNING:"
        if command -v docker &>/dev/null && docker info &>/dev/null 2>&1; then
            echo "true"
        else
            echo "false"
        fi

        echo "CONTAINER_COUNT:"
        docker ps -q 2>/dev/null | wc -l || echo "0"

        echo "DOCKER_STATS:"
        if docker info &>/dev/null 2>&1; then
            docker stats --no-stream --format "{{.Name}}|{{.CPUPerc}}|{{.MemUsage}}|{{.MemPerc}}" 2>/dev/null | head -15
        fi

        echo "CLAUDE_COUNT:"
        pgrep -c claude 2>/dev/null || echo "0"

        echo "TMUX_COUNT:"
        tmux list-sessions 2>/dev/null | wc -l || echo "0"

        echo "FLEET_SIZE:"
        du -sh ~/fleet 2>/dev/null | cut -f1 || echo "N/A"

        echo "VENV_SIZE:"
        du -sh ~/fleet/environments 2>/dev/null | cut -f1 || echo "N/A"

        echo "PRESERVES_SIZE:"
        du -sh ~/fleet-preserves 2>/dev/null | cut -f1 || echo "N/A"

        echo "TOP_PROCESSES:"
        ps aux --sort=-%cpu 2>/dev/null | head -6 | tail -5 | awk "{printf \"%s|%.1f%%|%.1f%%|%s\\n\", \$1, \$3, \$4, \$11}"
        '
    fi

    # Add DB volume collection if not quick mode
    if [[ "$quick_mode" != "true" ]]; then
        remote_script+='
        echo "DB_VOLUMES:"
        if docker info &>/dev/null 2>&1; then
            for vol in $(docker volume ls -q 2>/dev/null | grep -E "(postgres|timescale|database|db)" | sort); do
                project=$(echo "$vol" | sed -E "s/^([a-z]+)[-_].*/\1/")
                if echo "$vol" | grep -qi "timescale"; then
                    vol_type="TimescaleDB"
                elif echo "$vol" | grep -qi "postgres"; then
                    vol_type="PostgreSQL"
                else
                    vol_type="DB"
                fi
                size=$(docker run --rm -v "$vol":/data alpine du -sh /data 2>/dev/null | cut -f1)
                echo "${project}|${vol_type}|${size:-N/A}"
            done
        fi
        '
    fi

    eval "$ssh_cmd '$remote_script'" 2>/dev/null
}

# ============================================================================
# STORAGE DETAIL COLLECTORS (Page 2)
# ============================================================================

# Collect detailed node_modules by project
# Returns: project|path|size (multiple lines)
collect_node_modules_detail() {
    local base_path="${1:-$FLEET_DIR}"

    if [[ ! -d "$base_path" ]]; then
        echo "NOT_AVAILABLE"
        return 1
    fi

    find "$base_path" -type d -name "node_modules" -prune 2>/dev/null | while read -r dir; do
        # Extract project from path
        local project
        project=$(echo "$dir" | sed -E "s|$base_path/([^/]+)/.*|\1|")

        # Get relative path from project
        local rel_path
        rel_path=$(echo "$dir" | sed -E "s|$base_path/[^/]+/||")

        # Get size
        local size
        size=$(du -sh "$dir" 2>/dev/null | cut -f1)

        echo "${project}|${rel_path}|${size:-N/A}"
    done | sort -t'|' -k3 -hr | head -20
}

# Collect detailed venv/environments info
# Returns: name|path|size (multiple lines)
collect_venv_detail() {
    local base_path="${FLEET_ENVIRONMENTS_DIR:-${FLEET_DIR}/environments}"

    if [[ ! -d "$base_path" ]]; then
        echo "NOT_AVAILABLE"
        return 1
    fi

    # List directories in environments
    for dir in "$base_path"/*/; do
        [[ ! -d "$dir" ]] && continue

        local name
        name=$(basename "$dir")

        local size
        size=$(du -sh "$dir" 2>/dev/null | cut -f1)

        echo "${name}|${dir}|${size:-N/A}"
    done | sort -t'|' -k3 -hr
}

# Collect build directories (.next, dist, build, target)
# Returns: type|project|path|size (multiple lines)
collect_build_dirs_detail() {
    local base_path="${1:-$FLEET_DIR}"

    if [[ ! -d "$base_path" ]]; then
        echo "NOT_AVAILABLE"
        return 1
    fi

    local results=""

    # .next directories (Next.js)
    while IFS= read -r dir; do
        [[ -z "$dir" ]] && continue
        local project
        project=$(echo "$dir" | sed -E "s|$base_path/([^/]+)/.*|\1|")
        local size
        size=$(du -sh "$dir" 2>/dev/null | cut -f1)
        results+=".next|${project}|${dir}|${size:-N/A}\n"
    done < <(find "$base_path" -maxdepth 4 -type d -name ".next" 2>/dev/null)

    # dist directories
    while IFS= read -r dir; do
        [[ -z "$dir" ]] && continue
        local project
        project=$(echo "$dir" | sed -E "s|$base_path/([^/]+)/.*|\1|")
        local size
        size=$(du -sh "$dir" 2>/dev/null | cut -f1)
        results+="dist|${project}|${dir}|${size:-N/A}\n"
    done < <(find "$base_path" -maxdepth 4 -type d -name "dist" 2>/dev/null)

    # target directories (Rust)
    while IFS= read -r dir; do
        [[ -z "$dir" ]] && continue
        local project
        project=$(echo "$dir" | sed -E "s|$base_path/([^/]+)/.*|\1|")
        local size
        size=$(du -sh "$dir" 2>/dev/null | cut -f1)
        results+="target|${project}|${dir}|${size:-N/A}\n"
    done < <(find "$base_path" -maxdepth 4 -type d -name "target" 2>/dev/null)

    # Sort by size (column 4) and output
    echo -e "$results" | sort -t'|' -k4 -hr | head -15
}

# Collect /data directory usage
# Returns: path|size (multiple lines)
collect_data_dirs() {
    local data_paths=(
        "/data"
        "${HOME}/data"
        "${FLEET_DIR}/data"
    )

    for path in "${data_paths[@]}"; do
        if [[ -d "$path" ]]; then
            local total_size
            total_size=$(du -sh "$path" 2>/dev/null | cut -f1)
            echo "TOTAL|${path}|${total_size:-N/A}"

            # Top subdirectories
            du -h --max-depth=1 "$path" 2>/dev/null | \
                sort -hr | \
                head -10 | \
                while read -r size subdir; do
                    [[ "$subdir" == "$path" ]] && continue
                    echo "SUB|${subdir}|${size}"
                done
        fi
    done
}

# Collect cache directories
# Returns: type|path|size (multiple lines)
collect_cache_dirs() {
    local cache_paths=(
        "${HOME}/.cache"
        "${HOME}/.npm"
        "${HOME}/.cargo"
        "${HOME}/.rustup"
        "${HOME}/.local/share/pnpm"
    )

    for path in "${cache_paths[@]}"; do
        if [[ -d "$path" ]]; then
            local size
            size=$(du -sh "$path" 2>/dev/null | cut -f1)
            local name
            name=$(basename "$path")
            echo "${name}|${path}|${size:-N/A}"
        fi
    done
}

# Collect log files sizes
# Returns: path|size (multiple lines, sorted by size)
collect_log_files() {
    local log_paths=(
        "/var/log"
        "${HOME}/.local/state"
        "${FLEET_DIR}/*/logs"
    )

    local results=""

    for pattern in "${log_paths[@]}"; do
        # Handle glob patterns
        for path in $pattern; do
            if [[ -d "$path" ]]; then
                local size
                size=$(du -sh "$path" 2>/dev/null | cut -f1)
                results+="${path}|${size:-N/A}\n"
            fi
        done
    done

    echo -e "$results" | sort -t'|' -k2 -hr | head -10
}

# Collect full storage summary for Page 2
# Returns: structured data with all storage categories
collect_storage_detail() {
    local base_path="${1:-$FLEET_DIR}"

    echo "=== STORAGE DETAIL ==="

    echo "NODE_MODULES:"
    collect_node_modules_detail "$base_path"

    echo "VENVS:"
    collect_venv_detail

    echo "BUILD_DIRS:"
    collect_build_dirs_detail "$base_path"

    echo "DATA_DIRS:"
    collect_data_dirs

    echo "CACHE_DIRS:"
    collect_cache_dirs

    echo "LOG_DIRS:"
    collect_log_files

    echo "=== END STORAGE DETAIL ==="
}

# ============================================================================
# NATIVE SERVICES COLLECTORS (Page 6)
# ============================================================================
# Detect non-Docker services: Node.js frontends, Python/uvicorn backends

# Collect running Node.js services (frontends)
# Returns: project|port|process|status (multiple lines)
collect_node_services() {
    # Find node/next/vite processes with listening ports
    ps aux 2>/dev/null | grep -E 'node|next|vite' | grep -v grep | while read -r line; do
        local user pid cpu mem vsz rss tty stat start time cmd
        read -r user pid cpu mem vsz rss tty stat start time cmd <<< "$line"

        # Try to identify project from command or cwd
        local project="unknown"
        local port=""
        local process_name=""

        # Extract port from common patterns
        if [[ "$cmd" =~ -p[[:space:]]*([0-9]+) ]]; then
            port="${BASH_REMATCH[1]}"
        elif [[ "$cmd" =~ port[[:space:]]*([0-9]+) ]]; then
            port="${BASH_REMATCH[1]}"
        fi

        # Try to get port from lsof/ss if not found in command
        if [[ -z "$port" ]]; then
            port=$(ss -tlnp 2>/dev/null | grep "pid=${pid}," | head -1 | awk '{print $4}' | sed 's/.*://')
        fi

        # Extract process type
        if echo "$cmd" | grep -q "next-server"; then
            process_name="next-server"
        elif echo "$cmd" | grep -q "vite"; then
            process_name="vite"
        elif echo "$cmd" | grep -q "npm"; then
            process_name="npm"
        else
            process_name="node"
        fi

        # Try to identify project from cwd
        local cwd_path=""
        cwd_path=$(readlink -f "/proc/${pid}/cwd" 2>/dev/null)
        if [[ -n "$cwd_path" && "$cwd_path" =~ fleet/([^/]+) ]]; then
            project="${BASH_REMATCH[1]}"
        fi

        [[ -n "$port" ]] && echo "${project}|${port}|${process_name}|running"
    done | sort -t'|' -k1,1 -u
}

# Collect running Python/uvicorn services (backends/engines)
# Returns: project|port|workers|status (multiple lines)
collect_python_services() {
    # Find uvicorn processes
    ps aux 2>/dev/null | grep -E 'uvicorn|python.*main' | grep -v grep | while read -r line; do
        local user pid cpu mem vsz rss tty stat start time cmd
        read -r user pid cpu mem vsz rss tty stat start time cmd <<< "$line"

        local project="unknown"
        local port=""
        local workers=""

        # Extract port from uvicorn command
        if [[ "$cmd" =~ --port[[:space:]]*([0-9]+) ]]; then
            port="${BASH_REMATCH[1]}"
        elif [[ "$cmd" =~ :([0-9]+) ]]; then
            port="${BASH_REMATCH[1]}"
        fi

        # Extract workers
        if [[ "$cmd" =~ --workers[[:space:]]*([0-9]+) ]]; then
            workers="${BASH_REMATCH[1]}"
        else
            workers="1"
        fi

        # Try to get port from ss if not found
        if [[ -z "$port" ]]; then
            port=$(ss -tlnp 2>/dev/null | grep "pid=${pid}," | head -1 | awk '{print $4}' | sed 's/.*://')
        fi

        # Try to identify project from cwd or command
        local cwd_path=""
        cwd_path=$(readlink -f "/proc/${pid}/cwd" 2>/dev/null)
        if [[ -n "$cwd_path" && "$cwd_path" =~ fleet/([^/]+) ]]; then
            project="${BASH_REMATCH[1]}"
        fi

        # Skip parent uvicorn processes (they don't have ports)
        [[ -n "$port" ]] && echo "${project}|${port}|${workers}|running"
    done | sort -t'|' -k2,2 -u
}

# Collect all native services for an instance
# Returns: structured data for Page 6
collect_native_services() {
    echo "=== NATIVE SERVICES ==="

    echo "NODE_SERVICES:"
    collect_node_services

    echo "PYTHON_SERVICES:"
    collect_python_services

    echo "=== END NATIVE SERVICES ==="
}

# Remote native services collection
collect_remote_native_services() {
    local instance="$1"

    local ssh_cmd
    ssh_cmd=$(get_ssh_cmd "$instance")

    if [[ -z "$ssh_cmd" ]]; then
        return 1
    fi

    local remote_script='
echo "=== NATIVE SERVICES ==="

echo "NODE_SERVICES:"
# Find node/next/vite processes with project detection
ps aux 2>/dev/null | grep -E "node|next|vite" | grep -v grep | while read -r line; do
    pid=$(echo "$line" | awk "{print \$2}")
    cmd=$(echo "$line" | awk "{for(i=11;i<=NF;i++) printf \"%s \", \$i}")

    project="unknown"
    port=""
    process_name="node"

    # Extract port
    port=$(echo "$cmd" | grep -oP "(-p|--port|port=)\s*\K[0-9]+" | head -1)
    if [ -z "$port" ]; then
        port=$(ss -tlnp 2>/dev/null | grep "pid=${pid}," | head -1 | awk "{print \$4}" | sed "s/.*://")
    fi

    # Extract process type
    if echo "$cmd" | grep -q "next-server"; then
        process_name="next-server"
    elif echo "$cmd" | grep -q "vite"; then
        process_name="vite"
    elif echo "$cmd" | grep -q "npm"; then
        process_name="npm"
    fi

    # Get project from cwd
    cwd=$(readlink -f "/proc/${pid}/cwd" 2>/dev/null)
    if [ -n "$cwd" ]; then
        project=$(echo "$cwd" | sed -n "s|.*/fleet/\([^/]*\).*|\1|p")
        [ -z "$project" ] && project="unknown"
    fi

    [ -n "$port" ] && echo "${project}|${port}|${process_name}|running"
done | sort -t"|" -k1,1 -u

echo "PYTHON_SERVICES:"
# Find uvicorn/python backend processes
ps aux 2>/dev/null | grep -E "uvicorn|python.*main" | grep -v grep | while read -r line; do
    pid=$(echo "$line" | awk "{print \$2}")
    cmd=$(echo "$line" | awk "{for(i=11;i<=NF;i++) printf \"%s \", \$i}")

    project="unknown"
    port=""
    workers="1"

    # Extract port
    port=$(echo "$cmd" | grep -oP "(--port\s*|:)\K[0-9]+" | head -1)
    if [ -z "$port" ]; then
        port=$(ss -tlnp 2>/dev/null | grep "pid=${pid}," | head -1 | awk "{print \$4}" | sed "s/.*://")
    fi

    # Extract workers
    workers=$(echo "$cmd" | grep -oP "--workers\s*\K[0-9]+" || echo "1")

    # Get project from cwd
    cwd=$(readlink -f "/proc/${pid}/cwd" 2>/dev/null)
    if [ -n "$cwd" ]; then
        project=$(echo "$cwd" | sed -n "s|.*/fleet/\([^/]*\).*|\1|p")
        [ -z "$project" ] && project="unknown"
    fi

    [ -n "$port" ] && echo "${project}|${port}|${workers}|running"
done | sort -t"|" -k2,2 -u

echo "=== END NATIVE SERVICES ==="
'

    eval "$ssh_cmd '$remote_script'" 2>/dev/null
}

# Remote storage detail collection
collect_remote_storage_detail() {
    local instance="$1"

    local ssh_cmd
    ssh_cmd=$(get_ssh_cmd "$instance")

    if [[ -z "$ssh_cmd" ]]; then
        return 1
    fi

    local remote_script='
FLEET_DIR="$HOME/fleet"

echo "=== STORAGE DETAIL ==="

echo "NODE_MODULES:"
find "$FLEET_DIR" -type d -name "node_modules" -prune 2>/dev/null | while read -r dir; do
    project=$(echo "$dir" | sed -E "s|$FLEET_DIR/([^/]+)/.*|\1|")
    rel_path=$(echo "$dir" | sed -E "s|$FLEET_DIR/[^/]+/||")
    size=$(du -sh "$dir" 2>/dev/null | cut -f1)
    echo "${project}|${rel_path}|${size:-N/A}"
done | sort -t"|" -k3 -hr | head -20

echo "VENVS:"
venv_path="$FLEET_DIR/environments"
if [ -d "$venv_path" ]; then
    for dir in "$venv_path"/*/; do
        [ -d "$dir" ] || continue
        name=$(basename "$dir")
        size=$(du -sh "$dir" 2>/dev/null | cut -f1)
        echo "${name}|${dir}|${size:-N/A}"
    done | sort -t"|" -k3 -hr
else
    echo "NOT_AVAILABLE"
fi

echo "BUILD_DIRS:"
find "$FLEET_DIR" -maxdepth 4 -type d \( -name ".next" -o -name "dist" -o -name "target" \) 2>/dev/null | while read -r dir; do
    type=$(basename "$dir")
    project=$(echo "$dir" | sed -E "s|$FLEET_DIR/([^/]+)/.*|\1|")
    size=$(du -sh "$dir" 2>/dev/null | cut -f1)
    echo "${type}|${project}|${dir}|${size:-N/A}"
done | sort -t"|" -k4 -hr | head -15

echo "DATA_DIRS:"
for path in /data "$HOME/data" "$FLEET_DIR/data"; do
    if [ -d "$path" ]; then
        total=$(du -sh "$path" 2>/dev/null | cut -f1)
        echo "TOTAL|${path}|${total:-N/A}"
        du -h --max-depth=1 "$path" 2>/dev/null | sort -hr | head -10 | while read -r size subdir; do
            [ "$subdir" = "$path" ] && continue
            echo "SUB|${subdir}|${size}"
        done
    fi
done

echo "CACHE_DIRS:"
for path in "$HOME/.cache" "$HOME/.npm" "$HOME/.cargo" "$HOME/.rustup"; do
    if [ -d "$path" ]; then
        name=$(basename "$path")
        size=$(du -sh "$path" 2>/dev/null | cut -f1)
        echo "${name}|${path}|${size:-N/A}"
    fi
done

echo "=== END STORAGE DETAIL ==="
'

    eval "$ssh_cmd '$remote_script'" 2>/dev/null
}
