#!/bin/bash
# ============================================================================
# SYSMON - Status Command
# ============================================================================
# Quick status check for local or remote instances
# ============================================================================

# Help text for this command
cmd_status_help() {
    cat << 'EOF'
sysmon status - Quick system status check

Usage: sysmon status [options]

Options:
  --instance <n>   Check specific instance (1, 2, or 3)
  --all            Check all instances (local + all EC2)
  --help           Show this help

Output includes:
  - Disk usage with color-coded percentage
  - Memory usage
  - Docker container count
  - Active Claude/tmux sessions
  - Load average

Examples:
  sysmon status                  # Local status
  sysmon status --instance 1     # Instance 1 only
  sysmon status --instance 2     # Instance 2 only
  sysmon status --instance 3     # Instance 3 only
  sysmon status --all            # All instances
EOF
}

# Print status line with color-coded value
print_status_line() {
    local label="$1"
    local value="$2"
    local warning="${3:-}"
    local critical="${4:-}"

    if [[ -n "$warning" && -n "$critical" ]]; then
        value=$(colored_percentage "$value" "$warning" "$critical")
    fi

    printf "  %-20s %s\n" "$label:" "$value"
}

# Get local status
get_local_status() {
    echo -e "${BOLD}Local System${NC}"
    echo ""

    # Disk
    local disk_info
    disk_info=$(collect_disk_info)
    IFS='|' read -r total used avail pct <<< "$disk_info"
    print_status_line "Disk Usage" "$pct ($used / $total)" "$DISK_WARNING_THRESHOLD" "$DISK_CRITICAL_THRESHOLD"

    # Memory
    local mem_info
    mem_info=$(collect_memory_info)
    IFS='|' read -r mem_total mem_used mem_free mem_avail mem_pct <<< "$mem_info"
    print_status_line "Memory" "$mem_pct ($mem_used / $mem_total)" "$MEM_WARNING_THRESHOLD" "$MEM_CRITICAL_THRESHOLD"

    # Load average
    local load
    load=$(collect_load_average)
    print_status_line "Load Average" "$load"

    # Docker containers
    if is_docker_available; then
        local container_count
        container_count=$(collect_container_count)
        print_status_line "Docker Containers" "$container_count running"
    else
        print_status_line "Docker" "Not available"
    fi

    # Claude sessions
    local claude_count
    claude_count=$(collect_claude_count)
    print_status_line "Claude Sessions" "$claude_count"

    # Tmux sessions
    local tmux_count
    tmux_count=$(collect_tmux_count)
    print_status_line "Tmux Sessions" "$tmux_count"

    # FLEET directory size
    local fleet_size
    fleet_size=$(collect_dir_size "$FLEET_DIR")
    print_status_line "FLEET Directory" "$fleet_size"
}

# Get remote status for an instance
get_remote_status() {
    local instance="$1"
    local instance_name
    local instance_ip

    instance_name=$(get_instance_name "$instance")
    instance_ip=$(get_instance_ip "$instance")

    echo -e "${BOLD}${instance_name}${NC} (${instance_ip})"
    echo ""

    # Check SSH key
    if ! check_ssh_key; then
        echo -e "  ${RED}SSH key not found${NC}"
        return 1
    fi

    # Test connectivity
    local ssh_cmd
    ssh_cmd=$(get_ssh_cmd "$instance")

    if ! eval "$ssh_cmd 'echo ok'" &>/dev/null; then
        echo -e "  ${RED}Connection failed${NC}"
        return 1
    fi

    # Collect remote metrics (quick mode)
    local metrics
    metrics=$(collect_remote_metrics "$instance" "true")

    if [[ -z "$metrics" ]]; then
        echo -e "  ${RED}Failed to collect metrics${NC}"
        return 1
    fi

    # Parse metrics
    local disk_info load_avg memory cpu_pct docker_running container_count claude_count tmux_count fleet_size

    disk_info=$(echo "$metrics" | grep -A1 "^DISK_INFO:" | tail -1)
    load_avg=$(echo "$metrics" | grep -A1 "^LOAD_AVG:" | tail -1)
    memory=$(echo "$metrics" | grep -A1 "^MEMORY:" | tail -1)
    cpu_pct=$(echo "$metrics" | grep -A1 "^CPU_PCT:" | tail -1)
    docker_running=$(echo "$metrics" | grep -A1 "^DOCKER_RUNNING:" | tail -1)
    container_count=$(echo "$metrics" | grep -A1 "^CONTAINER_COUNT:" | tail -1)
    claude_count=$(echo "$metrics" | grep -A1 "^CLAUDE_COUNT:" | tail -1)
    tmux_count=$(echo "$metrics" | grep -A1 "^TMUX_COUNT:" | tail -1)
    fleet_size=$(echo "$metrics" | grep -A1 "^FLEET_SIZE:" | tail -1)

    # Parse disk info
    IFS='|' read -r total used avail pct <<< "$disk_info"
    print_status_line "Disk Usage" "$pct ($used / $total)" "$DISK_WARNING_THRESHOLD" "$DISK_CRITICAL_THRESHOLD"

    # Parse memory
    IFS='|' read -r mem_total mem_used mem_free mem_avail mem_pct <<< "$memory"
    print_status_line "Memory" "$mem_pct ($mem_used / $mem_total)" "$MEM_WARNING_THRESHOLD" "$MEM_CRITICAL_THRESHOLD"

    # CPU
    print_status_line "CPU Usage" "${cpu_pct}%" "$CPU_WARNING_THRESHOLD" "$CPU_CRITICAL_THRESHOLD"

    # Load
    print_status_line "Load Average" "$load_avg"

    # Docker
    if [[ "$docker_running" == "true" ]]; then
        print_status_line "Docker Containers" "$container_count running"
    else
        print_status_line "Docker" "Not running"
    fi

    # Sessions
    print_status_line "Claude Sessions" "$claude_count"
    print_status_line "Tmux Sessions" "$tmux_count"
    print_status_line "FLEET Directory" "$fleet_size"
}

# Main command function
cmd_status() {
    local instance=""
    local all_instances=false

    # Parse arguments
    while [[ $# -gt 0 ]]; do
        case "$1" in
            --instance)
                instance="$2"
                shift 2
                ;;
            --all)
                all_instances=true
                shift
                ;;
            --help|-h)
                cmd_status_help
                return 0
                ;;
            *)
                log_error "Unknown option: $1"
                cmd_status_help
                return 1
                ;;
        esac
    done

    print_header "SYSMON Status"

    if [[ "$all_instances" == "true" ]]; then
        # Show all instances
        echo ""
        get_local_status
        
        # Get all configured instances dynamically
        local instances
        instances=$(get_all_instances)
        
        for inst in $instances; do
            echo ""
            echo "─────────────────────────────────"
            echo ""
            get_remote_status "$inst"
        done
    elif [[ -n "$instance" ]]; then
        # Show specific instance
        echo ""
        get_remote_status "$instance"
    else
        # Show local only
        echo ""
        get_local_status
    fi

    echo ""
}
