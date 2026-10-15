#!/bin/bash
# ============================================================================
# SYSMON - Analyze Command
# ============================================================================
# Deep disk and system analysis
# ============================================================================

# Help text for this command
cmd_analyze_help() {
    cat << 'EOF'
sysmon analyze - Deep system analysis

Usage: sysmon analyze [options]

Options:
  --with-cpu          Include CPU, memory, and process metrics
  --output <file>     Save report to file (default: /tmp/sysmon_analysis_*.md)
  --instance <n>      Analyze specific instance (1 or 2)
  --help              Show this help

Analysis includes:
  - System disk overview with usage warnings
  - Top-level directory breakdown
  - Docker usage (images, containers, cache, volumes)
  - FLEET directory analysis (projects, node_modules, build artifacts)
  - Large file detection (>100MB)
  - Cleanup recommendations

With --with-cpu:
  - CPU and load average
  - Memory usage breakdown
  - Top processes by CPU
  - Docker container stats
  - Database storage by project

Examples:
  sysmon analyze                      # Full local analysis
  sysmon analyze --with-cpu           # Include CPU/memory
  sysmon analyze --output report.md   # Save to file
  sysmon analyze --instance 1         # Analyze Instance 1
EOF
}

# Generate analysis report
generate_analysis() {
    local with_cpu="$1"
    local output_file="$2"

    # Start report
    {
        echo "# SYSMON Analysis Report"
        echo ""
        echo "**Generated**: $(date '+%Y-%m-%d %H:%M:%S')"
        echo "**System**: $(hostname)"
        echo ""

        # System disk overview
        echo "## System Disk Overview"
        echo ""
        local disk_info
        disk_info=$(collect_disk_info)
        IFS='|' read -r total used avail pct <<< "$disk_info"

        echo "| Metric | Value |"
        echo "|--------|-------|"
        echo "| Total | $total |"
        echo "| Used | $used |"
        echo "| Available | $avail |"
        echo "| Usage | $pct |"
        echo ""

        # Status indicator
        local status
        status=$(get_status_text "${pct%\%}" "$DISK_WARNING_THRESHOLD" "$DISK_CRITICAL_THRESHOLD")
        echo "**Status**: $status"
        echo ""

        # Top directories
        echo "## Top Directories"
        echo ""
        echo "| Size | Directory |"
        echo "|------|-----------|"
        collect_top_directories "$HOME" 15 | while IFS='|' read -r size dir; do
            echo "| $size | $dir |"
        done
        echo ""

        # FLEET Directory Analysis
        if [[ -d "$FLEET_DIR" ]]; then
            echo "## FLEET Directory Analysis"
            echo ""

            local fleet_size
            fleet_size=$(collect_dir_size "$FLEET_DIR")
            echo "**Total FLEET Size**: $fleet_size"
            echo ""

            echo "### Top FLEET Subdirectories"
            echo ""
            echo "| Size | Directory |"
            echo "|------|-----------|"
            collect_top_directories "$FLEET_DIR" 20 | while IFS='|' read -r size dir; do
                local dirname
                dirname=$(basename "$dir")
                echo "| $size | $dirname |"
            done
            echo ""

            # node_modules analysis
            echo "### Node Modules"
            echo ""
            local nm_info
            nm_info=$(collect_node_modules_info "$FLEET_DIR")
            IFS='|' read -r nm_count nm_size <<< "$nm_info"
            echo "- **Count**: $nm_count directories"
            echo "- **Total Size**: $nm_size"
            echo ""

            # .next directories
            echo "### Build Artifacts (.next)"
            echo ""
            local next_info
            next_info=$(collect_next_dirs_info "$FLEET_DIR")
            IFS='|' read -r next_count next_size <<< "$next_info"
            echo "- **Count**: $next_count directories"
            echo "- **Total Size**: $next_size"
            echo ""

            # Shared venv
            echo "### Shared Virtual Environment"
            echo ""
            local venv_size
            venv_size=$(collect_venv_size)
            echo "- **Size**: $venv_size"
            echo ""

            # Preserves
            echo "### Preserves Directory"
            echo ""
            local preserves_size
            preserves_size=$(collect_preserves_size)
            echo "- **Size**: $preserves_size"
            echo ""
        fi

        # Docker analysis
        if is_docker_available; then
            echo "## Docker Usage"
            echo ""

            echo "### Docker Disk Usage"
            echo ""
            echo "| Type | Size | Reclaimable |"
            echo "|------|------|-------------|"
            collect_docker_disk | while IFS='|' read -r type size reclaim; do
                [[ "$type" == "NOT_AVAILABLE" ]] && continue
                echo "| $type | $size | $reclaim |"
            done
            echo ""

            # Dangling images
            local dangling
            dangling=$(collect_dangling_images)
            echo "**Dangling Images**: $dangling"

            # Stopped containers
            local stopped
            stopped=$(collect_stopped_containers)
            echo "**Stopped Containers**: $stopped"
            echo ""

            # Database volumes
            echo "### Database Volumes"
            echo ""
            local db_volumes
            db_volumes=$(collect_db_volumes_quick)

            if [[ "$db_volumes" == "NOT_AVAILABLE" ]]; then
                echo "_Docker not available_"
            elif [[ "$db_volumes" == "NO_VOLUMES" || -z "$db_volumes" ]]; then
                echo "_No database volumes found_"
            else
                echo "| Project | Type | Size |"
                echo "|---------|------|------|"
                echo "$db_volumes" | while IFS='|' read -r project vol_type size; do
                    echo "| $project | $vol_type | $size |"
                done
            fi
            echo ""
        else
            echo "## Docker Usage"
            echo ""
            echo "_Docker not available_"
            echo ""
        fi

        # Large files
        echo "## Large Files (>100MB)"
        echo ""
        local large_files
        large_files=$(collect_large_files "$HOME" "$LARGE_FILE_THRESHOLD")

        if [[ -z "$large_files" ]]; then
            echo "_No large files found_"
        else
            echo "| Size | File |"
            echo "|------|------|"
            echo "$large_files" | while IFS='|' read -r size file; do
                echo "| $size | $file |"
            done
        fi
        echo ""

        # CPU & Memory section (if requested)
        if [[ "$with_cpu" == "true" ]]; then
            echo "## CPU & Memory Usage"
            echo ""

            # Load average
            local load_avg
            load_avg=$(collect_load_average)
            echo "**Load Average**: $load_avg"

            # CPU usage
            local cpu_pct
            cpu_pct=$(collect_cpu_usage)
            local cpu_status
            cpu_status=$(get_status_text "${cpu_pct%.*}" "$CPU_WARNING_THRESHOLD" "$CPU_CRITICAL_THRESHOLD")
            echo "**CPU Usage**: ${cpu_pct}% ($cpu_status)"
            echo ""

            # Memory
            echo "### Memory"
            echo ""
            local mem_info
            mem_info=$(collect_memory_info)
            IFS='|' read -r mem_total mem_used mem_free mem_avail mem_pct <<< "$mem_info"
            echo "| Total | Used | Free | Available | Usage |"
            echo "|-------|------|------|-----------|-------|"
            echo "| $mem_total | $mem_used | $mem_free | $mem_avail | $mem_pct |"
            echo ""

            # Top processes
            echo "### Top Processes by CPU"
            echo ""
            echo "| User | CPU | Memory | Command |"
            echo "|------|-----|--------|---------|"
            collect_top_processes 10 | while IFS='|' read -r user cpu mem cmd; do
                echo "| $user | $cpu | $mem | $cmd |"
            done
            echo ""

            # Docker container stats
            if is_docker_available; then
                echo "### Docker Container Usage"
                echo ""
                local container_stats
                container_stats=$(collect_docker_containers)

                if [[ "$container_stats" == "NOT_AVAILABLE" ]]; then
                    echo "_Docker not available_"
                elif [[ "$container_stats" == "NO_CONTAINERS" ]]; then
                    echo "_No running containers_"
                else
                    echo "| Container | CPU | Memory | Mem % |"
                    echo "|-----------|-----|--------|-------|"
                    echo "$container_stats" | while IFS='|' read -r name cpu mem mem_pct; do
                        echo "| $name | $cpu | $mem | $mem_pct |"
                    done
                fi
                echo ""

                # Full database volume sizes (with sizing)
                echo "### Database Storage by Project"
                echo ""
                local db_full
                db_full=$(collect_db_volumes)

                if [[ "$db_full" == "NOT_AVAILABLE" ]]; then
                    echo "_Docker not available_"
                elif [[ "$db_full" == "NO_VOLUMES" || -z "$db_full" ]]; then
                    echo "_No database volumes found_"
                else
                    echo "| Project | Volume Type | Size |"
                    echo "|---------|-------------|------|"
                    echo "$db_full" | while IFS='|' read -r project vol_type size; do
                        echo "| $project | $vol_type | $size |"
                    done
                fi
                echo ""
            fi

            # Session counts
            echo "### Active Sessions"
            echo ""
            local claude_count tmux_count
            claude_count=$(collect_claude_count)
            tmux_count=$(collect_tmux_count)
            echo "- **Claude Sessions**: $claude_count"
            echo "- **Tmux Sessions**: $tmux_count"
            echo ""
        fi

        # Cleanup recommendations
        echo "## Cleanup Recommendations"
        echo ""

        local recommendations=0

        # Check disk usage
        local disk_num="${pct%\%}"
        if [[ "$disk_num" -ge "$DISK_CRITICAL_THRESHOLD" ]]; then
            echo "1. **CRITICAL**: Disk usage at ${pct}. Run cleanup immediately:"
            echo "   \`\`\`bash"
            echo "   sysmon cleanup builds"
            echo "   sysmon cleanup docker --aggressive"
            echo "   \`\`\`"
            recommendations=$((recommendations + 1))
        elif [[ "$disk_num" -ge "$DISK_WARNING_THRESHOLD" ]]; then
            echo "1. **WARNING**: Disk usage at ${pct}. Consider cleanup:"
            echo "   \`\`\`bash"
            echo "   sysmon cleanup builds"
            echo "   sysmon cleanup docker"
            echo "   \`\`\`"
            recommendations=$((recommendations + 1))
        fi

        # Check for dangling images
        if is_docker_available; then
            local dangling
            dangling=$(collect_dangling_images)
            if [[ "$dangling" -gt 0 ]]; then
                echo "$((recommendations + 1)). **Docker**: $dangling dangling images can be cleaned:"
                echo "   \`\`\`bash"
                echo "   sysmon cleanup docker"
                echo "   \`\`\`"
                recommendations=$((recommendations + 1))
            fi
        fi

        # Check node_modules size
        local nm_info
        nm_info=$(collect_node_modules_info "$FLEET_DIR" 2>/dev/null)
        if [[ -n "$nm_info" ]]; then
            IFS='|' read -r nm_count nm_size <<< "$nm_info"
            # Extract numeric size for comparison (rough)
            if [[ "$nm_size" =~ ^[0-9]+G ]]; then
                local nm_gb="${nm_size%G*}"
                if [[ "$nm_gb" -gt 10 ]]; then
                    echo "$((recommendations + 1)). **Node Modules**: ${nm_size} can be cleaned (will regenerate on npm install):"
                    echo "   \`\`\`bash"
                    echo "   sysmon cleanup builds --include-node-modules"
                    echo "   \`\`\`"
                    recommendations=$((recommendations + 1))
                fi
            fi
        fi

        # Check for Chrome temp data (macOS)
        local chrome_size=0
        while IFS= read -r dir; do
            if [[ -d "$dir" ]]; then
                local size
                size=$(du -sb "$dir" 2>/dev/null | awk '{print $1}')
                chrome_size=$((chrome_size + size))
            fi
        done < <(find /private/var/folders -maxdepth 5 -type d -name "com.google.Chrome*" 2>/dev/null)
        if [[ "$chrome_size" -gt 1073741824 ]]; then  # > 1GB
            local chrome_human
            chrome_human=$(echo "scale=1; $chrome_size / 1073741824" | bc)
            echo "$((recommendations + 1)). **Chrome Temp**: ${chrome_human}G of Chrome temp data can be cleaned:"
            echo "   \`\`\`bash"
            echo "   sysmon cleanup caches --chrome"
            echo "   \`\`\`"
            recommendations=$((recommendations + 1))
        fi

        # Check for SQL dumps in temp
        local sql_size=0
        while IFS= read -r file; do
            if [[ -f "$file" ]]; then
                local size
                size=$(stat -f%z "$file" 2>/dev/null || stat -c%s "$file" 2>/dev/null || echo "0")
                sql_size=$((sql_size + size))
            fi
        done < <(find /private/tmp /tmp "$HOME" -maxdepth 2 -name "*.sql" -type f -size +100M 2>/dev/null 2>&1)
        if [[ "$sql_size" -gt 104857600 ]]; then  # > 100MB
            local sql_human
            sql_human=$(echo "scale=1; $sql_size / 1073741824" | bc)
            echo "$((recommendations + 1)). **SQL Dumps**: ${sql_human}G of temp SQL dumps found:"
            echo "   \`\`\`bash"
            echo "   sysmon cleanup caches --tmp-sql"
            echo "   \`\`\`"
            recommendations=$((recommendations + 1))
        fi

        # Check for Python venvs in projects
        local venv_size=0
        while IFS= read -r dir; do
            if [[ -d "$dir" ]]; then
                local size
                size=$(du -sb "$dir" 2>/dev/null | awk '{print $1}')
                venv_size=$((venv_size + size))
            fi
        done < <(find "$FLEET_DIR" -maxdepth 3 -type d -name "venv" 2>/dev/null)
        if [[ "$venv_size" -gt 1073741824 ]]; then  # > 1GB
            local venv_human
            venv_human=$(echo "scale=1; $venv_size / 1073741824" | bc)
            echo "$((recommendations + 1)). **Project Venvs**: ${venv_human}G of venv directories can be cleaned:"
            echo "   \`\`\`bash"
            echo "   sysmon cleanup caches --venv"
            echo "   \`\`\`"
            recommendations=$((recommendations + 1))
        fi

        # Check Homebrew (macOS)
        if command -v brew &>/dev/null; then
            local brew_cellar_size=0
            if [[ -d "/opt/homebrew/Cellar" ]]; then
                brew_cellar_size=$(du -sb /opt/homebrew/Cellar 2>/dev/null | awk '{print $1}')
            fi
            if [[ "$brew_cellar_size" -gt 10737418240 ]]; then  # > 10GB
                echo "$((recommendations + 1)). **Homebrew**: Large Homebrew installation, consider cleanup:"
                echo "   \`\`\`bash"
                echo "   sysmon cleanup caches --homebrew"
                echo "   \`\`\`"
                recommendations=$((recommendations + 1))
            fi
        fi

        if [[ "$recommendations" -eq 0 ]]; then
            echo "_No immediate cleanup needed. System is healthy._"
        fi
        echo ""

        echo "---"
        echo "_Report generated by sysmon v${SYSMON_VERSION}_"

    } > "$output_file"

    echo "$output_file"
}

# Run remote analysis
run_remote_analysis() {
    local instance="$1"
    local with_cpu="$2"
    local output_file="$3"

    local instance_name
    local instance_ip
    instance_name=$(get_instance_name "$instance")
    instance_ip=$(get_instance_ip "$instance")

    log_info "Analyzing $instance_name ($instance_ip)..."

    if ! check_ssh_key; then
        log_error "SSH key not found"
        return 1
    fi

    local ssh_cmd
    ssh_cmd=$(get_ssh_cmd "$instance")

    # Build remote command
    local remote_cmd="bash ~/fleet/sega/engine/sega/system/sysmon/sysmon analyze"
    [[ "$with_cpu" == "true" ]] && remote_cmd+=" --with-cpu"

    # Run remotely and capture output
    eval "$ssh_cmd '$remote_cmd'" > "$output_file" 2>/dev/null

    if [[ $? -eq 0 ]]; then
        log_success "Analysis saved to: $output_file"
    else
        log_error "Remote analysis failed"
        return 1
    fi
}

# Main command function
cmd_analyze() {
    local with_cpu=false
    local output_file=""
    local instance=""

    # Parse arguments
    while [[ $# -gt 0 ]]; do
        case "$1" in
            --with-cpu)
                with_cpu=true
                shift
                ;;
            --output)
                output_file="$2"
                shift 2
                ;;
            --instance)
                instance="$2"
                shift 2
                ;;
            --help|-h)
                cmd_analyze_help
                return 0
                ;;
            *)
                log_error "Unknown option: $1"
                cmd_analyze_help
                return 1
                ;;
        esac
    done

    # Set default output file if not specified
    if [[ -z "$output_file" ]]; then
        output_file="/tmp/sysmon_analysis_$(date +%Y%m%d_%H%M%S).md"
    fi

    # Handle remote analysis
    if [[ -n "$instance" ]]; then
        run_remote_analysis "$instance" "$with_cpu" "$output_file"
        return $?
    fi

    # Local analysis
    log_info "Running system analysis..."
    [[ "$with_cpu" == "true" ]] && log_info "Including CPU/memory metrics (this may take a moment)..."

    start_spinner "Collecting data..."

    local result_file
    result_file=$(generate_analysis "$with_cpu" "$output_file")

    stop_spinner "ok"

    log_success "Analysis complete!"
    echo ""
    echo "Report saved to: $result_file"
    echo ""
    echo "View with: cat $result_file"
    echo "Or:        less $result_file"
}
