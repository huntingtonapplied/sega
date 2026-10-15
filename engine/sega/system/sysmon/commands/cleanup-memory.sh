#!/bin/bash
# ============================================================================
# SYSMON - Cleanup Memory Command
# ============================================================================
# Clear system memory caches (page cache, dentries, inodes)
# ============================================================================

# Help text for this command
cmd_cleanup_memory_help() {
    cat << 'EOF'
sysmon cleanup memory - Clear system memory caches

Usage: sysmon cleanup memory [options]

Options:
  --pagecache       Clear page cache only (safest)
  --dentries        Clear dentries and inodes
  --all             Clear all caches (page cache + dentries + inodes)
  --instance <N>    Run on EC2 instance (1, 2, or 3)
  --all-instances   Run on all EC2 instances
  --yes, -y         Skip confirmation prompts
  --help            Show this help

Cache levels:
  1 = Page cache only (safest, most impact)
  2 = Dentries and inodes
  3 = All (page cache + dentries + inodes)

Examples:
  sysmon cleanup memory                    # Clear page cache (interactive)
  sysmon cleanup memory --all --yes        # Clear all caches, auto-confirm
  sysmon cleanup memory --instance 1       # Clear memory on Instance 1
  sysmon cleanup memory --all-instances    # Clear memory on all instances

Note: Clearing memory cache is safe - the kernel will rebuild caches as
needed. This frees up memory temporarily but may cause temporary slowdown
as caches are rebuilt. Requires sudo.

Warning: This is most effective when system is under memory pressure.
Clearing caches on an idle system has minimal benefit.
EOF
}

# Show current memory status
show_memory_status() {
    local prefix="${1:-}"

    echo "${prefix}Memory Status:"
    free -h | while read line; do
        echo "${prefix}  $line"
    done
    echo ""
}

# Clear page cache
clear_pagecache() {
    local auto_yes="$1"

    print_section "Page Cache"
    increment_stat "total"

    # Get current cache size
    local cached
    cached=$(free -h | awk '/^Mem:/ {print $6}')
    log_info "Current page cache: approximately $cached"

    if [[ "$auto_yes" != "true" ]]; then
        if ! confirm "Clear page cache?"; then
            log_info "Skipped page cache"
            increment_stat "skipped"
            return 0
        fi
    fi

    if [[ "$SYSMON_DRY_RUN" == "true" ]]; then
        log_info "[DRY RUN] Would clear page cache"
        return 0
    fi

    # Sync first to write dirty pages to disk
    sync

    # Clear page cache (level 1)
    if sudo sh -c 'echo 1 > /proc/sys/vm/drop_caches' 2>/dev/null; then
        log_success "Page cache cleared"
        increment_stat "success"
    else
        log_error "Failed to clear page cache (requires sudo)"
        increment_stat "failed"
    fi
}

# Clear dentries and inodes
clear_dentries() {
    local auto_yes="$1"

    print_section "Dentries and Inodes"
    increment_stat "total"

    log_info "Dentries and inodes cache filesystem metadata"

    if [[ "$auto_yes" != "true" ]]; then
        if ! confirm "Clear dentries and inodes cache?"; then
            log_info "Skipped dentries/inodes"
            increment_stat "skipped"
            return 0
        fi
    fi

    if [[ "$SYSMON_DRY_RUN" == "true" ]]; then
        log_info "[DRY RUN] Would clear dentries and inodes"
        return 0
    fi

    sync

    # Clear dentries and inodes (level 2)
    if sudo sh -c 'echo 2 > /proc/sys/vm/drop_caches' 2>/dev/null; then
        log_success "Dentries and inodes cache cleared"
        increment_stat "success"
    else
        log_error "Failed to clear dentries/inodes (requires sudo)"
        increment_stat "failed"
    fi
}

# Clear all caches
clear_all_caches() {
    local auto_yes="$1"

    print_section "All Memory Caches"
    increment_stat "total"

    log_info "This will clear page cache, dentries, and inodes"

    if [[ "$auto_yes" != "true" ]]; then
        if ! confirm "Clear all memory caches?"; then
            log_info "Skipped all caches"
            increment_stat "skipped"
            return 0
        fi
    fi

    if [[ "$SYSMON_DRY_RUN" == "true" ]]; then
        log_info "[DRY RUN] Would clear all memory caches"
        return 0
    fi

    sync

    # Clear all (level 3)
    if sudo sh -c 'echo 3 > /proc/sys/vm/drop_caches' 2>/dev/null; then
        log_success "All memory caches cleared"
        increment_stat "success"
    else
        log_error "Failed to clear memory caches (requires sudo)"
        increment_stat "failed"
    fi
}

# Execute cleanup on remote instance
run_remote_memory_cleanup() {
    local instance="$1"
    local level="${2:-3}"

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

    log_info "Clearing memory caches on Instance $instance ($ip)..."

    # Show before status
    ssh -i "$ssh_key" -o StrictHostKeyChecking=no -o ConnectTimeout=10 \
        "ubuntu@$ip" "echo 'Before:' && free -h | head -2" 2>/dev/null

    # Clear caches
    ssh -i "$ssh_key" -o StrictHostKeyChecking=no -o ConnectTimeout=10 \
        "ubuntu@$ip" "sudo sh -c 'sync && echo $level > /proc/sys/vm/drop_caches'" 2>/dev/null

    if [[ $? -eq 0 ]]; then
        # Show after status
        ssh -i "$ssh_key" -o StrictHostKeyChecking=no -o ConnectTimeout=10 \
            "ubuntu@$ip" "echo 'After:' && free -h | head -2" 2>/dev/null
        log_success "Instance $instance memory cache cleared"
    else
        log_error "Failed to clear memory on Instance $instance"
    fi
}

# Main command function
cmd_cleanup_memory() {
    local clear_level=1  # Default to page cache only
    local auto_yes=false
    local target_instance=""
    local all_instances=false

    # Parse arguments
    while [[ $# -gt 0 ]]; do
        case "$1" in
            --pagecache)
                clear_level=1
                shift
                ;;
            --dentries)
                clear_level=2
                shift
                ;;
            --all)
                clear_level=3
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
                cmd_cleanup_memory_help
                return 0
                ;;
            *)
                log_error "Unknown option: $1"
                cmd_cleanup_memory_help
                return 1
                ;;
        esac
    done

    # Handle remote execution
    if [[ "$all_instances" == "true" ]]; then
        print_header "Memory Cleanup (All Instances)"
        for i in 1 2 3; do
            run_remote_memory_cleanup "$i" "$clear_level"
            echo ""
        done
        return 0
    fi

    if [[ -n "$target_instance" ]]; then
        print_header "Memory Cleanup (Instance $target_instance)"
        run_remote_memory_cleanup "$target_instance" "$clear_level"
        return 0
    fi

    # Local execution
    print_header "Memory Cache Cleanup"

    echo ""
    show_memory_status "  "

    # Initialize stats
    init_stats

    case "$clear_level" in
        1)
            clear_pagecache "$auto_yes"
            ;;
        2)
            clear_dentries "$auto_yes"
            ;;
        3)
            clear_all_caches "$auto_yes"
            ;;
    esac

    echo ""
    log_info "After cleanup:"
    show_memory_status "  "

    print_stats "Memory Cleanup"
}
