#!/bin/bash
# ============================================================================
# SYSMON - Projects Command
# ============================================================================
# Display metrics organized by project across instances
# ============================================================================

# Help text for this command
cmd_projects_help() {
    cat << 'EOF'
sysmon projects - Project-based metrics dashboard

Usage: sysmon projects [options]

Options:
  --instance <n>    Show projects for specific instance (1 or 2)
  --project <name>  Show detailed metrics for a single project
  --quick           Skip database volume sizing (faster)
  --help            Show this help

Output includes:
  - Project summary table (all projects)
  - Per-project: containers, DB volume, disk usage, status

Examples:
  sysmon projects                    # All projects, both instances
  sysmon projects --instance 1       # Projects on Instance 1 only
  sysmon projects --project <name>    # Detailed view of one project
  sysmon projects --quick            # Skip DB sizing for speed
EOF
}

# Print project summary table header
print_project_table_header() {
    local instance="$1"
    local ip="$2"
    echo ""
    echo -e "${CYAN}${BOLD}━━━ Instance $instance Projects ($ip) ━━━${NC}"
    echo ""
    echo "| Project | Containers | DB Volume | Disk Usage | Status |"
    echo "|---------|------------|-----------|------------|--------|"
}

# Parse project metrics and print table row
print_project_row() {
    local project="$1"
    local metrics="$2"

    local dir_size containers db_info status

    dir_size=$(echo "$metrics" | grep "^DIR_SIZE:" | cut -d: -f2)
    containers=$(echo "$metrics" | grep "^CONTAINERS:" | cut -d: -f2)
    db_info=$(echo "$metrics" | grep "^DB_VOLUME:" | cut -d: -f2-)

    # Parse DB info
    local db_display
    if [[ "$db_info" == "none" ]]; then
        db_display="-"
    else
        IFS='|' read -r db_type db_size <<< "$db_info"
        db_display="${db_size} (${db_type})"
    fi

    # Determine status
    if [[ "$containers" -gt 0 ]]; then
        status="${GREEN}running${NC}"
    else
        status="${YELLOW}stopped${NC}"
    fi

    echo -e "| $project | $containers | $db_display | $dir_size | $status |"
}

# Print detailed view for a single project
print_project_detail() {
    local project="$1"
    local metrics="$2"
    local instance="$3"
    local ip="$4"

    echo ""
    echo -e "${CYAN}${BOLD}━━━ Project: $project (Instance $instance - $ip) ━━━${NC}"
    echo ""

    local dir_size containers db_info
    dir_size=$(echo "$metrics" | grep "^DIR_SIZE:" | cut -d: -f2)
    containers=$(echo "$metrics" | grep "^CONTAINERS:" | cut -d: -f2)
    db_info=$(echo "$metrics" | grep "^DB_VOLUME:" | cut -d: -f2-)

    echo "**Overview:**"
    echo "| Metric | Value |"
    echo "|--------|-------|"
    echo "| Disk Usage | $dir_size |"
    echo "| Running Containers | $containers |"

    # Parse DB info
    if [[ "$db_info" != "none" ]]; then
        IFS='|' read -r db_type db_size <<< "$db_info"
        echo "| Database | $db_type ($db_size) |"
    else
        echo "| Database | None |"
    fi
    echo ""

    # Container details
    local container_list
    container_list=$(echo "$metrics" | sed -n '/^CONTAINER_LIST:/,/^[A-Z_]*:/p' | grep -v "^CONTAINER_LIST:" | grep -v "^[A-Z_]*:" | grep -v "^---$")

    if [[ -n "$container_list" && "$containers" -gt 0 ]]; then
        echo "**Containers:**"
        echo "| Name | Status |"
        echo "|------|--------|"
        echo "$container_list" | while IFS='|' read -r name status; do
            [[ -z "$name" ]] && continue
            echo "| $name | $status |"
        done
        echo ""
    fi
}

# Collect and display projects for an instance
display_instance_projects() {
    local instance="$1"
    local quick_mode="$2"
    local target_project="$3"

    local ip
    ip=$(get_instance_ip "$instance")

    if [[ -z "$ip" ]]; then
        log_error "Invalid instance: $instance"
        return 1
    fi

    # Get project list
    local projects
    if [[ -n "$target_project" ]]; then
        projects="$target_project"
    else
        projects=$(get_instance_projects "$instance")
    fi

    if [[ -z "$projects" ]]; then
        log_error "No projects found for instance $instance"
        return 1
    fi

    # Collect metrics
    local metrics
    metrics=$(collect_remote_project_metrics "$instance" "$projects")

    if [[ -z "$metrics" ]]; then
        log_error "Failed to collect metrics from instance $instance"
        return 1
    fi

    # If single project, show detailed view
    if [[ -n "$target_project" ]]; then
        local project_metrics
        project_metrics=$(echo "$metrics" | sed -n "/^PROJECT:$target_project$/,/^---$/p")
        print_project_detail "$target_project" "$project_metrics" "$instance" "$ip"
        return 0
    fi

    # Otherwise show summary table
    print_project_table_header "$instance" "$ip"

    # Parse and display each project
    local current_project=""
    local current_metrics=""

    while IFS= read -r line; do
        if [[ "$line" =~ ^PROJECT:(.+)$ ]]; then
            # Print previous project if exists
            if [[ -n "$current_project" ]]; then
                print_project_row "$current_project" "$current_metrics"
            fi
            current_project="${BASH_REMATCH[1]}"
            current_metrics=""
        elif [[ "$line" == "---" ]]; then
            # End of project
            if [[ -n "$current_project" ]]; then
                print_project_row "$current_project" "$current_metrics"
                current_project=""
                current_metrics=""
            fi
        else
            current_metrics+="$line"$'\n'
        fi
    done <<< "$metrics"

    # Print last project if not ended with ---
    if [[ -n "$current_project" ]]; then
        print_project_row "$current_project" "$current_metrics"
    fi

    echo ""
}

# Find which instance a project belongs to
find_project_instance() {
    local project="$1"

    if echo "$INSTANCE1_PROJECTS" | grep -qw "$project"; then
        echo "1"
    elif echo "$INSTANCE2_PROJECTS" | grep -qw "$project"; then
        echo "2"
    else
        echo ""
    fi
}

# Main command function
cmd_projects() {
    local instance=""
    local project=""
    local quick_mode=false

    # Parse arguments
    while [[ $# -gt 0 ]]; do
        case "$1" in
            --instance|-i)
                instance="$2"
                shift 2
                ;;
            --project|-p)
                project="$2"
                shift 2
                ;;
            --quick)
                quick_mode=true
                shift
                ;;
            --help|-h)
                cmd_projects_help
                return 0
                ;;
            *)
                log_error "Unknown option: $1"
                cmd_projects_help
                return 1
                ;;
        esac
    done

    print_header "FLEET Project Metrics"
    echo "Generated: $(date '+%Y-%m-%d %H:%M:%S')"
    [[ "$quick_mode" == "true" ]] && echo "(Quick mode - DB volumes skipped)"

    # Check SSH key
    if ! check_ssh_key; then
        return 1
    fi

    # If specific project requested, find its instance
    if [[ -n "$project" ]]; then
        local proj_instance
        proj_instance=$(find_project_instance "$project")

        if [[ -z "$proj_instance" ]]; then
            log_error "Project '$project' not found in any instance"
            echo ""
            echo "Available projects:"
            echo "  Instance 1: $INSTANCE1_PROJECTS"
            echo "  Instance 2: $INSTANCE2_PROJECTS"
            return 1
        fi

        log_info "Collecting metrics for $project from Instance $proj_instance..."
        display_instance_projects "$proj_instance" "$quick_mode" "$project"
        return $?
    fi

    # If specific instance requested
    if [[ -n "$instance" ]]; then
        log_info "Collecting metrics from Instance $instance..."
        display_instance_projects "$instance" "$quick_mode" ""
        return $?
    fi

    # Otherwise show both instances
    log_info "Collecting metrics from both instances..."

    # Collect in parallel
    local tmp1="/tmp/sysmon_projects_i1_$$"
    local tmp2="/tmp/sysmon_projects_i2_$$"

    (
        display_instance_projects 1 "$quick_mode" "" > "$tmp1" 2>&1
    ) &
    local pid1=$!

    (
        display_instance_projects 2 "$quick_mode" "" > "$tmp2" 2>&1
    ) &
    local pid2=$!

    # Wait for completion
    wait $pid1
    local status1=$?
    wait $pid2
    local status2=$?

    # Display results
    if [[ -f "$tmp1" ]]; then
        cat "$tmp1"
        rm -f "$tmp1"
    fi

    if [[ -f "$tmp2" ]]; then
        cat "$tmp2"
        rm -f "$tmp2"
    fi

    # Print summary
    echo ""
    echo -e "${CYAN}${BOLD}━━━ PROJECT SUMMARY ━━━${NC}"
    echo ""
    echo "| Instance | Total Projects | Running | Stopped |"
    echo "|----------|----------------|---------|---------|"

    # Count from Instance 1
    local i1_total i1_running
    i1_total=$(echo "$INSTANCE1_PROJECTS" | wc -w)
    i1_running=$(ssh -i "$SYSMON_SSH_KEY" $SSH_OPTS ubuntu@"$INSTANCE1_IP" \
        'for p in '"$INSTANCE1_PROJECTS"'; do docker ps --format "{{.Names}}" 2>/dev/null | grep -qE "^${p}[-_]" && echo 1; done | wc -l' 2>/dev/null)
    i1_running="${i1_running:-0}"
    local i1_stopped=$((i1_total - i1_running))
    echo "| Instance 1 | $i1_total | $i1_running | $i1_stopped |"

    # Count from Instance 2
    local i2_total i2_running
    i2_total=$(echo "$INSTANCE2_PROJECTS" | wc -w)
    i2_running=$(ssh -i "$SYSMON_SSH_KEY" $SSH_OPTS ubuntu@"$INSTANCE2_IP" \
        'for p in '"$INSTANCE2_PROJECTS"'; do docker ps --format "{{.Names}}" 2>/dev/null | grep -qE "^${p}[-_]" && echo 1; done | wc -l' 2>/dev/null)
    i2_running="${i2_running:-0}"
    local i2_stopped=$((i2_total - i2_running))
    echo "| Instance 2 | $i2_total | $i2_running | $i2_stopped |"

    echo ""
    echo "---"
    echo "Run 'sysmon projects --project <name>' for detailed view"
}
