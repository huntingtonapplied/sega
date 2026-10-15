#!/bin/bash
# ============================================================================
# SYSMON - Nuke Command
# ============================================================================
# Aggressive full cleanup - stops all containers, clears caches, removes
# build artifacts, kills processes. The nuclear option.
# ============================================================================

# Help text for this command
cmd_nuke_help() {
    cat << 'EOF'
sysmon nuke - Aggressive full system cleanup

Usage: sysmon nuke [options]

Options:
  --instance <N>    Run on EC2 instance (1, 2, or 3)
  --all-instances   Run on all EC2 instances
  --include-volumes Include Docker volumes (DATA LOSS WARNING)
  --yes, -y         Skip confirmation prompts (DANGEROUS)
  --help            Show this help

This command performs aggressive cleanup:
  1. Kill language servers (pylsp, pyright, tsserver, etc.)
  2. Stop and remove ALL Docker containers
  3. Prune Docker images, networks, and build cache
  4. Remove build artifacts (.next, dist, __pycache__, .pytest_cache, .mypy_cache)
  5. Remove node_modules directories
  6. Clear system memory cache (drop_caches)

Optional with --include-volumes:
  7. Remove Docker volumes (WARNING: database data loss!)

Examples:
  sysmon nuke                      # Full cleanup, interactive
  sysmon nuke --yes                # Full cleanup, auto-confirm (DANGEROUS)
  sysmon nuke --instance 1         # Nuke Instance 1
  sysmon nuke --all-instances      # Nuke all EC2 instances
  sysmon nuke --include-volumes    # Include Docker volumes (data loss!)

WARNING: This is destructive! Docker containers will be stopped, all cached
data will be lost, and you'll need to rebuild/reinstall to continue working.
EOF
}

# Execute nuke on remote instance
run_remote_nuke() {
    local instance="$1"
    local include_volumes="$2"

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

    log_warning "Nuking Instance $instance ($ip)..."

    # Build the nuke command
    local remote_cmd="echo '=== NUKE: Instance $instance ===' && echo '' && "

    # Phase 1: Kill language servers
    remote_cmd+="echo '[1/6] Killing language servers...' && "
    remote_cmd+="pkill -f 'pylsp|pyright|typescript-language-server|tsserver|gopls|rust-analyzer|clangd' 2>/dev/null || true && "

    # Phase 2: Stop and remove all Docker containers
    remote_cmd+="echo '[2/6] Stopping all Docker containers...' && "
    remote_cmd+="docker stop \$(docker ps -aq) 2>/dev/null || true && "
    remote_cmd+="docker rm \$(docker ps -aq) 2>/dev/null || true && "

    # Phase 3: Docker prune
    remote_cmd+="echo '[3/6] Pruning Docker system...' && "
    remote_cmd+="docker system prune -af && "

    if [[ "$include_volumes" == "true" ]]; then
        remote_cmd+="docker volume prune -f && "
    fi

    # Phase 4: Remove build artifacts
    remote_cmd+="echo '[4/6] Removing build artifacts...' && "
    remote_cmd+="find ~/fleet -maxdepth 5 -type d \\( -name '.next' -o -name 'dist' -o -name '__pycache__' -o -name '.pytest_cache' -o -name '.mypy_cache' \\) ! -path '*/node_modules/*' -exec rm -rf {} + 2>/dev/null || true && "

    # Phase 5: Remove node_modules
    remote_cmd+="echo '[5/6] Removing node_modules...' && "
    remote_cmd+="find ~/fleet -maxdepth 4 -type d -name 'node_modules' -exec rm -rf {} + 2>/dev/null || true && "
    remote_cmd+="rm -rf ~/fleet/environments/*/node_modules ~/fleet/environments/*/*/node_modules 2>/dev/null || true && "

    # Phase 6: Clear memory cache
    remote_cmd+="echo '[6/6] Clearing memory cache...' && "
    remote_cmd+="sudo sh -c 'sync && echo 3 > /proc/sys/vm/drop_caches' 2>/dev/null || true && "

    # Show results
    remote_cmd+="echo '' && echo '=== Results ===' && "
    remote_cmd+="echo 'Memory:' && free -h | head -2 && "
    remote_cmd+="echo '' && echo 'Disk:' && df -h / | tail -1 && "
    remote_cmd+="echo '' && echo 'Docker:' && docker system df 2>/dev/null || echo 'Docker not running'"

    ssh -i "$ssh_key" -o StrictHostKeyChecking=no -o ConnectTimeout=60 \
        "ubuntu@$ip" "$remote_cmd"

    if [[ $? -eq 0 ]]; then
        log_success "Instance $instance nuked successfully"
    else
        log_warning "Instance $instance nuke completed with some warnings"
    fi
}

# Main command function
cmd_nuke() {
    local auto_yes=false
    local target_instance=""
    local all_instances=false
    local include_volumes=false

    # Parse arguments
    while [[ $# -gt 0 ]]; do
        case "$1" in
            --instance)
                target_instance="$2"
                shift 2
                ;;
            --all-instances)
                all_instances=true
                shift
                ;;
            --include-volumes)
                include_volumes=true
                shift
                ;;
            --yes|-y)
                auto_yes=true
                shift
                ;;
            --help|-h)
                cmd_nuke_help
                return 0
                ;;
            *)
                log_error "Unknown option: $1"
                cmd_nuke_help
                return 1
                ;;
        esac
    done

    # Handle remote execution
    if [[ "$all_instances" == "true" ]]; then
        print_header "🔥 NUKE: All Instances"
        echo ""
        log_warning "This will aggressively clean ALL EC2 instances!"
        log_warning "All containers will be stopped, caches cleared, builds removed."

        if [[ "$auto_yes" != "true" ]]; then
            if ! confirm "Proceed with nuking ALL instances?" "n"; then
                log_info "Nuke cancelled"
                return 0
            fi
        fi

        for i in 1 2 3; do
            echo ""
            run_remote_nuke "$i" "$include_volumes"
        done
        return 0
    fi

    if [[ -n "$target_instance" ]]; then
        print_header "🔥 NUKE: Instance $target_instance"
        echo ""
        log_warning "This will aggressively clean Instance $target_instance!"

        if [[ "$auto_yes" != "true" ]]; then
            if ! confirm "Proceed with nuking Instance $target_instance?" "n"; then
                log_info "Nuke cancelled"
                return 0
            fi
        fi

        run_remote_nuke "$target_instance" "$include_volumes"
        return 0
    fi

    # Local execution
    print_header "🔥 NUKE: Local System"

    echo ""
    log_warning "This will aggressively clean the local system!"
    log_warning "All containers will be stopped, caches cleared, builds removed."
    echo ""

    if [[ "$include_volumes" == "true" ]]; then
        log_error "WARNING: --include-volumes will DELETE Docker volumes!"
        log_error "This means DATABASE DATA WILL BE LOST!"
        echo ""
    fi

    if [[ "$auto_yes" != "true" ]]; then
        if ! confirm "Proceed with local nuke?" "n"; then
            log_info "Nuke cancelled"
            return 0
        fi
    fi

    # Initialize stats
    init_stats

    # Phase 1: Kill language servers
    print_section "Phase 1: Kill Language Servers"
    increment_stat "total"
    local killed_count
    killed_count=$(pgrep -f 'pylsp|pyright|typescript-language-server|tsserver|gopls|rust-analyzer|clangd' 2>/dev/null | wc -l)
    pkill -f 'pylsp|pyright|typescript-language-server|tsserver|gopls|rust-analyzer|clangd' 2>/dev/null || true
    if [[ "$killed_count" -gt 0 ]]; then
        log_success "Killed $killed_count language server process(es)"
    else
        log_info "No language servers running"
    fi
    increment_stat "success"

    # Phase 2: Stop and remove all Docker containers
    print_section "Phase 2: Stop All Docker Containers"
    increment_stat "total"
    if check_docker 2>/dev/null; then
        local container_count
        container_count=$(docker ps -aq 2>/dev/null | wc -l)
        if [[ "$container_count" -gt 0 ]]; then
            docker stop $(docker ps -aq) 2>/dev/null || true
            docker rm $(docker ps -aq) 2>/dev/null || true
            log_success "Stopped and removed $container_count container(s)"
        else
            log_info "No containers to remove"
        fi
        increment_stat "success"
    else
        log_warning "Docker not available"
        increment_stat "skipped"
    fi

    # Phase 3: Docker prune
    print_section "Phase 3: Prune Docker System"
    increment_stat "total"
    if check_docker 2>/dev/null; then
        docker system prune -af 2>/dev/null
        if [[ "$include_volumes" == "true" ]]; then
            docker volume prune -f 2>/dev/null
            log_success "Docker system and volumes pruned"
        else
            log_success "Docker system pruned (volumes preserved)"
        fi
        increment_stat "success"
    else
        increment_stat "skipped"
    fi

    # Phase 4: Remove build artifacts
    print_section "Phase 4: Remove Build Artifacts"
    increment_stat "total"
    local base_path="${FLEET_DIR:-$HOME/fleet}"
    if [[ -d "$base_path" ]]; then
        local artifact_count
        artifact_count=$(find "$base_path" -maxdepth 5 -type d \( -name '.next' -o -name 'dist' -o -name '__pycache__' -o -name '.pytest_cache' -o -name '.mypy_cache' \) ! -path '*/node_modules/*' 2>/dev/null | wc -l)
        find "$base_path" -maxdepth 5 -type d \( -name '.next' -o -name 'dist' -o -name '__pycache__' -o -name '.pytest_cache' -o -name '.mypy_cache' \) ! -path '*/node_modules/*' -exec rm -rf {} + 2>/dev/null || true
        log_success "Removed $artifact_count build artifact directories"
        increment_stat "success"
    else
        log_warning "FLEET directory not found: $base_path"
        increment_stat "skipped"
    fi

    # Phase 5: Remove node_modules
    print_section "Phase 5: Remove Node Modules"
    increment_stat "total"
    if [[ -d "$base_path" ]]; then
        local nm_count
        nm_count=$(find "$base_path" -maxdepth 4 -type d -name 'node_modules' 2>/dev/null | wc -l)
        find "$base_path" -maxdepth 4 -type d -name 'node_modules' -exec rm -rf {} + 2>/dev/null || true
        rm -rf "$base_path/environments/*/node_modules" "$base_path/environments/*/*/node_modules" 2>/dev/null || true
        log_success "Removed $nm_count node_modules directories"
        increment_stat "success"
    else
        increment_stat "skipped"
    fi

    # Phase 6: Clear memory cache
    print_section "Phase 6: Clear Memory Cache"
    increment_stat "total"
    sync
    if sudo sh -c 'echo 3 > /proc/sys/vm/drop_caches' 2>/dev/null; then
        log_success "Memory cache cleared"
        increment_stat "success"
    else
        log_warning "Could not clear memory cache (requires sudo)"
        increment_stat "skipped"
    fi

    # Show results
    echo ""
    print_header "Nuke Results"
    echo ""
    echo "Memory:"
    free -h | head -2
    echo ""
    echo "Disk:"
    df -h / | tail -1
    echo ""
    if check_docker 2>/dev/null; then
        echo "Docker:"
        docker system df
    fi

    print_stats "Nuke"
}
