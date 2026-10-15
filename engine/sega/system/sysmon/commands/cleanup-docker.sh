#!/bin/bash
# ============================================================================
# SYSMON - Cleanup Docker Command
# ============================================================================
# Docker cleanup operations
# ============================================================================

# Help text for this command
cmd_cleanup_docker_help() {
    cat << 'EOF'
sysmon cleanup docker - Docker cleanup operations

Usage: sysmon cleanup docker [options]

Options:
  --all-containers  Stop and remove ALL containers (including running)
  --aggressive      Remove ALL unused images and volumes (not just dangling)
  --instance <N>    Run on EC2 instance (1, 2, or 3)
  --all-instances   Run on all EC2 instances
  --yes, -y         Skip confirmation prompts
  --help            Show this help

Cleanup phases (standard):
  1. Dangling images (tagged as <none>)
  2. Stopped containers (status=exited)
  3. Build cache

Additional with --all-containers:
  0. Stop and remove ALL running containers

Additional with --aggressive:
  4. All unused images
  5. Unused volumes

Examples:
  sysmon cleanup docker                        # Interactive cleanup
  sysmon cleanup docker --yes                  # Auto-confirm standard cleanup
  sysmon cleanup docker --aggressive           # Full cleanup including all unused
  sysmon cleanup docker --all-containers --yes # Stop all, then clean (nuke mode)
  sysmon cleanup docker --instance 1           # Clean up Docker on Instance 1
  sysmon cleanup docker --all-instances        # Clean up Docker on all instances
EOF
}

# Get Docker disk usage summary
get_docker_summary() {
    if ! is_docker_available; then
        echo "Docker not available"
        return 1
    fi

    echo "Docker Disk Usage:"
    docker system df 2>/dev/null | head -5
    echo ""
}

# Cleanup dangling images
cleanup_dangling_images() {
    local auto_yes="$1"

    local count
    count=$(docker images -f "dangling=true" -q 2>/dev/null | wc -l)

    if [[ "$count" -eq 0 ]]; then
        log_info "No dangling images to remove"
        return 0
    fi

    log_info "Found $count dangling images"

    if [[ "$auto_yes" != "true" ]]; then
        if ! confirm "Remove $count dangling images?"; then
            log_info "Skipped dangling images"
            increment_stat "skipped"
            return 0
        fi
    fi

    if [[ "$SYSMON_DRY_RUN" == "true" ]]; then
        log_info "[DRY RUN] Would remove $count dangling images"
        return 0
    fi

    docker image prune -f 2>/dev/null
    if [[ $? -eq 0 ]]; then
        log_success "Removed dangling images"
        increment_stat "success"
    else
        log_error "Failed to remove dangling images"
        increment_stat "failed"
    fi
}

# Cleanup stopped containers
cleanup_stopped_containers() {
    local auto_yes="$1"

    local count
    count=$(docker ps -a -f "status=exited" -q 2>/dev/null | wc -l)

    if [[ "$count" -eq 0 ]]; then
        log_info "No stopped containers to remove"
        return 0
    fi

    log_info "Found $count stopped containers"

    if [[ "$auto_yes" != "true" ]]; then
        if ! confirm "Remove $count stopped containers?"; then
            log_info "Skipped stopped containers"
            increment_stat "skipped"
            return 0
        fi
    fi

    if [[ "$SYSMON_DRY_RUN" == "true" ]]; then
        log_info "[DRY RUN] Would remove $count stopped containers"
        return 0
    fi

    docker container prune -f 2>/dev/null
    if [[ $? -eq 0 ]]; then
        log_success "Removed stopped containers"
        increment_stat "success"
    else
        log_error "Failed to remove stopped containers"
        increment_stat "failed"
    fi
}

# Cleanup build cache
cleanup_build_cache() {
    local auto_yes="$1"

    log_info "Build cache may contain cached layers"

    if [[ "$auto_yes" != "true" ]]; then
        if ! confirm "Remove build cache?"; then
            log_info "Skipped build cache"
            increment_stat "skipped"
            return 0
        fi
    fi

    if [[ "$SYSMON_DRY_RUN" == "true" ]]; then
        log_info "[DRY RUN] Would remove build cache"
        return 0
    fi

    docker builder prune -f 2>/dev/null
    if [[ $? -eq 0 ]]; then
        log_success "Removed build cache"
        increment_stat "success"
    else
        log_error "Failed to remove build cache"
        increment_stat "failed"
    fi
}

# Aggressive cleanup - all unused images
cleanup_unused_images() {
    local auto_yes="$1"

    log_warning "This will remove ALL unused images (not just dangling)"

    if [[ "$auto_yes" != "true" ]]; then
        if ! confirm "Remove all unused images?" "n"; then
            log_info "Skipped unused images"
            increment_stat "skipped"
            return 0
        fi
    fi

    if [[ "$SYSMON_DRY_RUN" == "true" ]]; then
        log_info "[DRY RUN] Would remove all unused images"
        return 0
    fi

    docker image prune -a -f 2>/dev/null
    if [[ $? -eq 0 ]]; then
        log_success "Removed unused images"
        increment_stat "success"
    else
        log_error "Failed to remove unused images"
        increment_stat "failed"
    fi
}

# Aggressive cleanup - unused volumes
cleanup_unused_volumes() {
    local auto_yes="$1"

    local count
    count=$(docker volume ls -f "dangling=true" -q 2>/dev/null | wc -l)

    if [[ "$count" -eq 0 ]]; then
        log_info "No unused volumes to remove"
        return 0
    fi

    log_warning "This will remove $count unused volumes (DATA LOSS WARNING)"

    if [[ "$auto_yes" != "true" ]]; then
        if ! confirm "Remove $count unused volumes? (This may cause data loss)" "n"; then
            log_info "Skipped unused volumes"
            increment_stat "skipped"
            return 0
        fi
    fi

    if [[ "$SYSMON_DRY_RUN" == "true" ]]; then
        log_info "[DRY RUN] Would remove $count unused volumes"
        return 0
    fi

    docker volume prune -f 2>/dev/null
    if [[ $? -eq 0 ]]; then
        log_success "Removed unused volumes"
        increment_stat "success"
    else
        log_error "Failed to remove unused volumes"
        increment_stat "failed"
    fi
}

# Stop and remove ALL containers (including running)
cleanup_all_containers() {
    local auto_yes="$1"

    local running_count stopped_count
    running_count=$(docker ps -q 2>/dev/null | wc -l)
    stopped_count=$(docker ps -a -f "status=exited" -q 2>/dev/null | wc -l)
    local total_count=$((running_count + stopped_count))

    if [[ "$total_count" -eq 0 ]]; then
        log_info "No containers to remove"
        return 0
    fi

    log_warning "This will stop and remove ALL $total_count containers ($running_count running, $stopped_count stopped)"

    if [[ "$auto_yes" != "true" ]]; then
        if ! confirm "Stop and remove ALL $total_count containers?" "n"; then
            log_info "Skipped all containers cleanup"
            increment_stat "skipped"
            return 0
        fi
    fi

    if [[ "$SYSMON_DRY_RUN" == "true" ]]; then
        log_info "[DRY RUN] Would stop and remove $total_count containers"
        return 0
    fi

    # Stop running containers
    if [[ "$running_count" -gt 0 ]]; then
        log_info "Stopping $running_count running containers..."
        docker stop $(docker ps -q) 2>/dev/null
    fi

    # Remove all containers
    docker rm $(docker ps -aq) 2>/dev/null
    if [[ $? -eq 0 ]]; then
        log_success "Removed all $total_count containers"
        increment_stat "success"
    else
        log_error "Failed to remove some containers"
        increment_stat "failed"
    fi
}

# Execute Docker cleanup on remote instance
run_remote_docker_cleanup() {
    local instance="$1"
    local all_containers="$2"
    local aggressive="$3"

    local ip
    case "$instance" in
        1) ip="${SYSMON_INSTANCE1_IP:-}" ;;
        2) ip="${SYSMON_INSTANCE2_IP:-}" ;;
        3) ip="${SYSMON_INSTANCE3_IP:-}" ;;
        *) log_error "Unknown instance: $instance"; return 1 ;;
    esac

    if [[ -z "$ip" ]]; then
        log_error "Instance $instance IP not configured: set SYSMON_INSTANCE${instance}_IP or configure [instances] in config/sega.toml"
        return 1
    fi

    local ssh_key="${SYSMON_SSH_KEY:-}"
    if [[ -z "$ssh_key" ]]; then
        log_error "SSH key not configured: set SYSMON_SSH_KEY or configure [instances] in config/sega.toml"
        return 1
    fi

    log_info "Cleaning Docker on Instance $instance ($ip)..."

    # Build remote command
    local remote_cmd="echo '=== Docker cleanup on Instance $instance ===' && "

    if [[ "$all_containers" == "true" ]]; then
        remote_cmd+="echo 'Stopping all containers...' && docker stop \$(docker ps -aq) 2>/dev/null; "
        remote_cmd+="echo 'Removing all containers...' && docker rm \$(docker ps -aq) 2>/dev/null; "
    fi

    remote_cmd+="echo 'Running docker system prune...' && docker system prune -f"

    if [[ "$aggressive" == "true" ]]; then
        remote_cmd+=" && docker image prune -a -f && docker volume prune -f"
    fi

    remote_cmd+=" && echo '' && echo 'Docker disk usage:' && docker system df"

    ssh -i "$ssh_key" -o StrictHostKeyChecking=no -o ConnectTimeout=10 \
        "ubuntu@$ip" "$remote_cmd" 2>/dev/null

    if [[ $? -eq 0 ]]; then
        log_success "Instance $instance Docker cleanup complete"
    else
        log_warning "Instance $instance Docker cleanup may have partially failed"
    fi
}

# Main command function
cmd_cleanup_docker() {
    local aggressive=false
    local all_containers=false
    local auto_yes=false
    local target_instance=""
    local all_instances=false

    # Parse arguments
    while [[ $# -gt 0 ]]; do
        case "$1" in
            --all-containers)
                all_containers=true
                shift
                ;;
            --aggressive)
                aggressive=true
                shift
                ;;
            --instance)
                target_instance="$2"
                shift 2
                ;;
            --all-instances)
                all_instances=true
                shift
                ;;
            --yes|-y)
                auto_yes=true
                shift
                ;;
            --help|-h)
                cmd_cleanup_docker_help
                return 0
                ;;
            *)
                log_error "Unknown option: $1"
                cmd_cleanup_docker_help
                return 1
                ;;
        esac
    done

    # Handle remote execution
    if [[ "$all_instances" == "true" ]]; then
        print_header "Docker Cleanup (All Instances)"
        for i in 1 2 3; do
            run_remote_docker_cleanup "$i" "$all_containers" "$aggressive"
            echo ""
        done
        return 0
    fi

    if [[ -n "$target_instance" ]]; then
        print_header "Docker Cleanup (Instance $target_instance)"
        run_remote_docker_cleanup "$target_instance" "$all_containers" "$aggressive"
        return 0
    fi

    # Local execution
    print_header "Docker Cleanup"

    # Check Docker availability
    if ! check_docker; then
        return 1
    fi

    # Show current usage
    echo ""
    echo "Before cleanup:"
    get_docker_summary

    # Initialize stats
    init_stats

    # Phase 0: All containers (if requested)
    if [[ "$all_containers" == "true" ]]; then
        print_section "Phase 0: Stop and Remove ALL Containers"
        increment_stat "total"
        cleanup_all_containers "$auto_yes"
    fi

    # Phase 1: Dangling images
    print_section "Phase 1: Dangling Images"
    increment_stat "total"
    cleanup_dangling_images "$auto_yes"

    # Phase 2: Stopped containers (skip if we already removed all)
    if [[ "$all_containers" != "true" ]]; then
        print_section "Phase 2: Stopped Containers"
        increment_stat "total"
        cleanup_stopped_containers "$auto_yes"
    fi

    # Phase 3: Build cache
    print_section "Phase 3: Build Cache"
    increment_stat "total"
    cleanup_build_cache "$auto_yes"

    # Aggressive phases
    if [[ "$aggressive" == "true" ]]; then
        print_section "Phase 4: All Unused Images (Aggressive)"
        increment_stat "total"
        cleanup_unused_images "$auto_yes"

        print_section "Phase 5: Unused Volumes (Aggressive)"
        increment_stat "total"
        cleanup_unused_volumes "$auto_yes"
    fi

    # Show results
    echo ""
    echo "After cleanup:"
    get_docker_summary

    print_stats "Docker Cleanup"
}
