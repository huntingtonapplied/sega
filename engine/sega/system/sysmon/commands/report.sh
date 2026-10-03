#!/bin/bash
# ============================================================================
# SYSMON - Report Command
# ============================================================================
# Generate structured reports in markdown or JSON format
# ============================================================================

# Help text for this command
cmd_report_help() {
    cat << 'EOF'
sysmon report - Generate system report

Usage: sysmon report [options]

Options:
  --format <fmt>   Output format: markdown (default) or json
  --output <file>  Output file (default: stdout)
  --instance <n>   Report for specific instance (1 or 2)
  --all            Include all instances
  --help           Show this help

Report includes:
  - System identification
  - Disk usage summary
  - Docker status
  - Memory/CPU metrics
  - Active sessions

Examples:
  sysmon report                       # Markdown to stdout
  sysmon report --format json         # JSON to stdout
  sysmon report --output report.md    # Save to file
  sysmon report --all                 # All instances
EOF
}

# Generate JSON report
generate_json_report() {
    local include_remote="$1"

    # Collect local metrics
    local disk_info mem_info load_avg cpu_pct
    local container_count claude_count tmux_count
    local fleet_size venv_size

    disk_info=$(collect_disk_info)
    mem_info=$(collect_memory_info)
    load_avg=$(collect_load_average)
    cpu_pct=$(collect_cpu_usage)
    container_count=$(collect_container_count 2>/dev/null || echo "0")
    claude_count=$(collect_claude_count)
    tmux_count=$(collect_tmux_count)
    fleet_size=$(collect_dir_size "$FLEET_DIR")
    venv_size=$(collect_venv_size)

    # Parse disk
    IFS='|' read -r disk_total disk_used disk_avail disk_pct <<< "$disk_info"

    # Parse memory
    IFS='|' read -r mem_total mem_used mem_free mem_avail mem_pct <<< "$mem_info"

    # Build JSON
    cat << EOF
{
  "generated": "$(date -Iseconds)",
  "hostname": "$(hostname)",
  "version": "$SYSMON_VERSION",
  "local": {
    "disk": {
      "total": "$disk_total",
      "used": "$disk_used",
      "available": "$disk_avail",
      "percent": "$disk_pct"
    },
    "memory": {
      "total": "$mem_total",
      "used": "$mem_used",
      "free": "$mem_free",
      "available": "$mem_avail",
      "percent": "$mem_pct"
    },
    "cpu": {
      "usage": "$cpu_pct",
      "load_average": "$load_avg"
    },
    "docker": {
      "containers": $container_count,
      "available": $(is_docker_available && echo "true" || echo "false")
    },
    "sessions": {
      "claude": $claude_count,
      "tmux": $tmux_count
    },
    "fleet": {
      "size": "$fleet_size",
      "venv_size": "$venv_size"
    }
  }
EOF

    # Add remote instances if requested
    if [[ "$include_remote" == "true" ]]; then
        echo '  ,"instances": {'

        # Instance 1
        if check_ssh_key 2>/dev/null; then
            local metrics1
            metrics1=$(collect_remote_metrics 1 "true" 2>/dev/null)

            if [[ -n "$metrics1" ]]; then
                local i1_disk i1_cpu i1_mem i1_docker i1_claude
                i1_disk=$(echo "$metrics1" | grep -A1 "^DISK_INFO:" | tail -1 | cut -d'|' -f4)
                i1_cpu=$(echo "$metrics1" | grep -A1 "^CPU_PCT:" | tail -1)
                i1_mem=$(echo "$metrics1" | grep -A1 "^MEMORY:" | tail -1 | cut -d'|' -f5)
                i1_docker=$(echo "$metrics1" | grep -A1 "^CONTAINER_COUNT:" | tail -1)
                i1_claude=$(echo "$metrics1" | grep -A1 "^CLAUDE_COUNT:" | tail -1)

                cat << EOF
    "instance1": {
      "ip": "$INSTANCE1_IP",
      "name": "$INSTANCE1_NAME",
      "disk_percent": "$i1_disk",
      "cpu_percent": "$i1_cpu",
      "memory_percent": "$i1_mem",
      "docker_containers": $i1_docker,
      "claude_sessions": $i1_claude
    },
EOF
            fi

            # Instance 2
            local metrics2
            metrics2=$(collect_remote_metrics 2 "true" 2>/dev/null)

            if [[ -n "$metrics2" ]]; then
                local i2_disk i2_cpu i2_mem i2_docker i2_claude
                i2_disk=$(echo "$metrics2" | grep -A1 "^DISK_INFO:" | tail -1 | cut -d'|' -f4)
                i2_cpu=$(echo "$metrics2" | grep -A1 "^CPU_PCT:" | tail -1)
                i2_mem=$(echo "$metrics2" | grep -A1 "^MEMORY:" | tail -1 | cut -d'|' -f5)
                i2_docker=$(echo "$metrics2" | grep -A1 "^CONTAINER_COUNT:" | tail -1)
                i2_claude=$(echo "$metrics2" | grep -A1 "^CLAUDE_COUNT:" | tail -1)

                cat << EOF
    "instance2": {
      "ip": "$INSTANCE2_IP",
      "name": "$INSTANCE2_NAME",
      "disk_percent": "$i2_disk",
      "cpu_percent": "$i2_cpu",
      "memory_percent": "$i2_mem",
      "docker_containers": $i2_docker,
      "claude_sessions": $i2_claude
    }
EOF
            fi
        fi
        echo '  }'
    fi

    echo '}'
}

# Generate markdown report
generate_markdown_report() {
    local include_remote="$1"

    cat << EOF
# SYSMON Report

**Generated**: $(date '+%Y-%m-%d %H:%M:%S')
**Hostname**: $(hostname)
**Version**: $SYSMON_VERSION

## Local System

EOF

    # Disk
    local disk_info
    disk_info=$(collect_disk_info)
    IFS='|' read -r disk_total disk_used disk_avail disk_pct <<< "$disk_info"

    echo "### Disk Usage"
    echo ""
    echo "| Metric | Value |"
    echo "|--------|-------|"
    echo "| Total | $disk_total |"
    echo "| Used | $disk_used |"
    echo "| Available | $disk_avail |"
    echo "| Usage | $disk_pct |"
    echo ""

    # Memory
    local mem_info
    mem_info=$(collect_memory_info)
    IFS='|' read -r mem_total mem_used mem_free mem_avail mem_pct <<< "$mem_info"

    echo "### Memory"
    echo ""
    echo "| Metric | Value |"
    echo "|--------|-------|"
    echo "| Total | $mem_total |"
    echo "| Used | $mem_used |"
    echo "| Free | $mem_free |"
    echo "| Available | $mem_avail |"
    echo "| Usage | $mem_pct |"
    echo ""

    # CPU
    local load_avg cpu_pct
    load_avg=$(collect_load_average)
    cpu_pct=$(collect_cpu_usage)

    echo "### CPU"
    echo ""
    echo "- **Load Average**: $load_avg"
    echo "- **CPU Usage**: ${cpu_pct}%"
    echo ""

    # Docker
    echo "### Docker"
    echo ""
    if is_docker_available; then
        local container_count
        container_count=$(collect_container_count)
        echo "- **Status**: Running"
        echo "- **Containers**: $container_count"
    else
        echo "- **Status**: Not available"
    fi
    echo ""

    # Sessions
    local claude_count tmux_count
    claude_count=$(collect_claude_count)
    tmux_count=$(collect_tmux_count)

    echo "### Sessions"
    echo ""
    echo "- **Claude**: $claude_count"
    echo "- **Tmux**: $tmux_count"
    echo ""

    # FLEET
    local fleet_size venv_size
    fleet_size=$(collect_dir_size "$FLEET_DIR")
    venv_size=$(collect_venv_size)

    echo "### FLEET Ecosystem"
    echo ""
    echo "- **FLEET Directory**: $fleet_size"
    echo "- **Shared venv**: $venv_size"
    echo ""

    # Remote instances
    if [[ "$include_remote" == "true" ]]; then
        echo "---"
        echo ""
        echo "## Remote Instances"
        echo ""

        if check_ssh_key 2>/dev/null; then
            for instance in 1 2; do
                local metrics
                metrics=$(collect_remote_metrics "$instance" "true" 2>/dev/null)

                if [[ -n "$metrics" ]]; then
                    local inst_name inst_ip
                    inst_name=$(get_instance_name "$instance")
                    inst_ip=$(get_instance_ip "$instance")

                    echo "### $inst_name ($inst_ip)"
                    echo ""

                    local r_disk r_cpu r_mem r_docker r_claude
                    r_disk=$(echo "$metrics" | grep -A1 "^DISK_INFO:" | tail -1 | cut -d'|' -f4)
                    r_cpu=$(echo "$metrics" | grep -A1 "^CPU_PCT:" | tail -1)
                    r_mem=$(echo "$metrics" | grep -A1 "^MEMORY:" | tail -1 | cut -d'|' -f5)
                    r_docker=$(echo "$metrics" | grep -A1 "^CONTAINER_COUNT:" | tail -1)
                    r_claude=$(echo "$metrics" | grep -A1 "^CLAUDE_COUNT:" | tail -1)

                    echo "| Metric | Value |"
                    echo "|--------|-------|"
                    echo "| Disk Usage | $r_disk |"
                    echo "| CPU Usage | ${r_cpu}% |"
                    echo "| Memory Usage | $r_mem |"
                    echo "| Docker Containers | $r_docker |"
                    echo "| Claude Sessions | $r_claude |"
                    echo ""
                else
                    echo "### Instance $instance"
                    echo ""
                    echo "_Failed to collect metrics_"
                    echo ""
                fi
            done
        else
            echo "_SSH key not available for remote collection_"
            echo ""
        fi
    fi

    echo "---"
    echo "_Generated by sysmon v${SYSMON_VERSION}_"
}

# Main command function
cmd_report() {
    local format="markdown"
    local output_file=""
    local include_remote=false
    local specific_instance=""

    # Parse arguments
    while [[ $# -gt 0 ]]; do
        case "$1" in
            --format)
                format="$2"
                shift 2
                ;;
            --output)
                output_file="$2"
                shift 2
                ;;
            --instance)
                specific_instance="$2"
                shift 2
                ;;
            --all)
                include_remote=true
                shift
                ;;
            --help|-h)
                cmd_report_help
                return 0
                ;;
            *)
                log_error "Unknown option: $1"
                cmd_report_help
                return 1
                ;;
        esac
    done

    # Validate format
    if [[ "$format" != "markdown" && "$format" != "json" ]]; then
        log_error "Invalid format: $format. Use 'markdown' or 'json'"
        return 1
    fi

    # Generate report
    local report
    if [[ "$format" == "json" ]]; then
        report=$(generate_json_report "$include_remote")
    else
        report=$(generate_markdown_report "$include_remote")
    fi

    # Output
    if [[ -n "$output_file" ]]; then
        echo "$report" > "$output_file"
        log_success "Report saved to: $output_file"
    else
        echo "$report"
    fi
}
