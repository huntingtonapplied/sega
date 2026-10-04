#!/bin/bash
# ============================================================================
# SYSMON - Cleanup Builds Command
# ============================================================================
# Build artifact cleanup operations
# ============================================================================

# Help text for this command
cmd_cleanup_builds_help() {
    cat << 'EOF'
sysmon cleanup builds - Build artifact cleanup

Usage: sysmon cleanup builds [options]

Options:
  --include-node-modules  Also remove node_modules directories
  --include-rust          Also remove Rust target directories (can be 30GB+)
  --path <dir>            Base path to clean (default: ~/fleet)
  --instance <N>          Run on EC2 instance (1, 2, or 3)
  --all-instances         Run on all EC2 instances
  --yes, -y               Skip confirmation prompts
  --help                  Show this help

Cleanup targets (standard):
  1. .next directories (Next.js build output)
  2. build directories (generic build output)
  3. dist directories (distribution builds)
  4. __pycache__ directories (Python cache)
  5. .pytest_cache directories (pytest cache)
  6. .mypy_cache directories (mypy type checker cache)

Additional with --include-rust:
  7. Rust target directories (regenerate with cargo build)

Additional with --include-node-modules:
  8. node_modules directories (regenerate with npm install)

Examples:
  sysmon cleanup builds                        # Standard cleanup
  sysmon cleanup builds --yes                  # Auto-confirm
  sysmon cleanup builds --include-rust         # Include Rust targets (30GB+)
  sysmon cleanup builds --include-node-modules # Include node_modules
  sysmon cleanup builds --path /custom/path    # Custom base path
  sysmon cleanup builds --instance 1           # Clean builds on Instance 1
  sysmon cleanup builds --all-instances        # Clean builds on all instances
EOF
}

# Find and report directories of a type
find_dirs() {
    local base_path="$1"
    local dir_name="$2"
    local max_depth="${3:-10}"

    find "$base_path" -maxdepth "$max_depth" -type d -name "$dir_name" -prune 2>/dev/null
}

# Get total size of directories
get_dirs_size() {
    local base_path="$1"
    local dir_name="$2"

    local dirs
    dirs=$(find_dirs "$base_path" "$dir_name")

    if [[ -z "$dirs" ]]; then
        echo "0"
        return
    fi

    echo "$dirs" | xargs -I{} du -sb {} 2>/dev/null | awk '{sum += $1} END {print sum}'
}

# Cleanup specific directory type
cleanup_dir_type() {
    local base_path="$1"
    local dir_name="$2"
    local auto_yes="$3"
    local friendly_name="${4:-$dir_name}"

    local dirs
    dirs=$(find_dirs "$base_path" "$dir_name")

    if [[ -z "$dirs" ]]; then
        log_info "No $friendly_name directories found"
        return 0
    fi

    local count size size_human
    count=$(echo "$dirs" | wc -l)
    size=$(echo "$dirs" | xargs -I{} du -sb {} 2>/dev/null | awk '{sum += $1} END {print sum}')
    size_human=$(human_size "$size")

    log_info "Found $count $friendly_name directories ($size_human total)"

    # Show top directories
    if [[ "$SYSMON_VERBOSE" == "true" ]]; then
        echo "Largest directories:"
        echo "$dirs" | head -10 | while read -r dir; do
            local dir_size
            dir_size=$(du -sh "$dir" 2>/dev/null | cut -f1)
            echo "  $dir_size  $dir"
        done
    fi

    if [[ "$auto_yes" != "true" ]]; then
        if ! confirm "Remove $count $friendly_name directories ($size_human)?"; then
            log_info "Skipped $friendly_name"
            increment_stat "skipped"
            return 0
        fi
    fi

    if [[ "$SYSMON_DRY_RUN" == "true" ]]; then
        log_info "[DRY RUN] Would remove $count $friendly_name directories ($size_human)"
        return 0
    fi

    # Remove directories
    local removed=0
    local failed=0

    while IFS= read -r dir; do
        [[ -z "$dir" ]] && continue
        if rm -rf "$dir" 2>/dev/null; then
            removed=$((removed + 1))
            log_debug "Removed: $dir"
        else
            failed=$((failed + 1))
            log_debug "Failed to remove: $dir"
        fi
    done <<< "$dirs"

    if [[ "$failed" -eq 0 ]]; then
        log_success "Removed $removed $friendly_name directories ($size_human freed)"
        increment_stat "success"
    else
        log_warning "Removed $removed, failed $failed $friendly_name directories"
        increment_stat "failed"
    fi
}

# Get summary of what will be cleaned
show_cleanup_summary() {
    local base_path="$1"
    local include_node_modules="$2"
    local include_rust="$3"

    echo "Cleanup Summary for: $base_path"
    echo ""

    local total_size=0

    # .next
    local next_count next_size
    next_count=$(find_dirs "$base_path" ".next" | wc -l)
    next_size=$(get_dirs_size "$base_path" ".next")
    total_size=$((total_size + next_size))
    echo "  .next directories:      $next_count ($(human_size "$next_size"))"

    # build
    local build_count build_size
    build_count=$(find_dirs "$base_path" "build" 5 | wc -l)
    build_size=$(get_dirs_size "$base_path" "build")
    total_size=$((total_size + build_size))
    echo "  build directories:      $build_count ($(human_size "$build_size"))"

    # dist
    local dist_count dist_size
    dist_count=$(find_dirs "$base_path" "dist" 5 | wc -l)
    dist_size=$(get_dirs_size "$base_path" "dist")
    total_size=$((total_size + dist_size))
    echo "  dist directories:       $dist_count ($(human_size "$dist_size"))"

    # __pycache__
    local pycache_count pycache_size
    pycache_count=$(find_dirs "$base_path" "__pycache__" | wc -l)
    pycache_size=$(get_dirs_size "$base_path" "__pycache__")
    total_size=$((total_size + pycache_size))
    echo "  __pycache__ directories: $pycache_count ($(human_size "$pycache_size"))"

    # Rust target (if included)
    if [[ "$include_rust" == "true" ]]; then
        local rust_count rust_size
        rust_count=$(find "$base_path" -maxdepth 4 -type d -name "target" \
            -exec test -f "{}/CACHEDIR.TAG" -o -f "{}/.cargo-lock" \; -print 2>/dev/null | wc -l)
        # Also find target dirs that have debug/release subdirs (Rust signature)
        rust_count=$(find "$base_path" -maxdepth 4 -type d -name "target" 2>/dev/null | \
            while read -r dir; do
                [[ -d "$dir/debug" || -d "$dir/release" ]] && echo "$dir"
            done | wc -l)
        rust_size=$(find "$base_path" -maxdepth 4 -type d -name "target" 2>/dev/null | \
            while read -r dir; do
                [[ -d "$dir/debug" || -d "$dir/release" ]] && echo "$dir"
            done | xargs -I{} du -sb {} 2>/dev/null | awk '{sum += $1} END {print sum+0}')
        total_size=$((total_size + rust_size))
        echo "  Rust target dirs:       $rust_count ($(human_size "$rust_size"))"
    fi

    # node_modules (if included)
    if [[ "$include_node_modules" == "true" ]]; then
        local nm_count nm_size
        nm_count=$(find_dirs "$base_path" "node_modules" | wc -l)
        nm_size=$(get_dirs_size "$base_path" "node_modules")
        total_size=$((total_size + nm_size))
        echo "  node_modules:           $nm_count ($(human_size "$nm_size"))"
    fi

    echo ""
    echo "Total potential savings: $(human_size "$total_size")"
    echo ""
}

# Main command function
cmd_cleanup_builds() {
    local base_path="$FLEET_DIR"
    local include_node_modules=false
    local include_rust=false
    local auto_yes=false
    local target_instance=""
    local all_instances=false

    # Parse arguments
    while [[ $# -gt 0 ]]; do
        case "$1" in
            --include-node-modules)
                include_node_modules=true
                shift
                ;;
            --include-rust)
                include_rust=true
                shift
                ;;
            --path)
                base_path="$2"
                shift 2
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
                cmd_cleanup_builds_help
                return 0
                ;;
            *)
                log_error "Unknown option: $1"
                cmd_cleanup_builds_help
                return 1
                ;;
        esac
    done

    # Handle remote execution
    if [[ "$all_instances" == "true" ]]; then
        print_header "Build Cleanup (All Instances)"
        for i in 1 2 3; do
            run_remote_builds_cleanup "$i" "$include_node_modules" "$include_rust"
            echo ""
        done
        return 0
    fi

    if [[ -n "$target_instance" ]]; then
        print_header "Build Cleanup (Instance $target_instance)"
        run_remote_builds_cleanup "$target_instance" "$include_node_modules" "$include_rust"
        return 0
    fi

    # Local execution
    print_header "Build Artifact Cleanup"

    # Validate path
    if [[ ! -d "$base_path" ]]; then
        log_error "Directory not found: $base_path"
        return 1
    fi

    echo ""
    log_info "Scanning $base_path..."
    echo ""

    # Show summary
    show_cleanup_summary "$base_path" "$include_node_modules" "$include_rust"

    # Initialize stats
    init_stats

    # Phase 1: .next directories
    print_section "Phase 1: Next.js Build Output (.next)"
    increment_stat "total"
    cleanup_dir_type "$base_path" ".next" "$auto_yes" "Next.js build"

    # Phase 2: build directories (limit depth to avoid node_modules/build)
    print_section "Phase 2: Build Directories"
    increment_stat "total"
    # Use a more targeted approach for build dirs
    local build_dirs
    build_dirs=$(find "$base_path" -maxdepth 5 -type d -name "build" \
        ! -path "*/node_modules/*" \
        ! -path "*/.next/*" \
        -prune 2>/dev/null)

    if [[ -n "$build_dirs" ]]; then
        local build_count
        build_count=$(echo "$build_dirs" | wc -l)
        log_info "Found $build_count build directories"

        if [[ "$auto_yes" == "true" ]] || confirm "Remove build directories?"; then
            if [[ "$SYSMON_DRY_RUN" != "true" ]]; then
                echo "$build_dirs" | xargs rm -rf 2>/dev/null
                log_success "Removed build directories"
                increment_stat "success"
            else
                log_info "[DRY RUN] Would remove build directories"
            fi
        else
            increment_stat "skipped"
        fi
    else
        log_info "No build directories found"
    fi

    # Phase 3: dist directories
    print_section "Phase 3: Distribution Directories (dist)"
    increment_stat "total"
    local dist_dirs
    dist_dirs=$(find "$base_path" -maxdepth 5 -type d -name "dist" \
        ! -path "*/node_modules/*" \
        ! -path "*/.next/*" \
        -prune 2>/dev/null)

    if [[ -n "$dist_dirs" ]]; then
        local dist_count
        dist_count=$(echo "$dist_dirs" | wc -l)
        log_info "Found $dist_count dist directories"

        if [[ "$auto_yes" == "true" ]] || confirm "Remove dist directories?"; then
            if [[ "$SYSMON_DRY_RUN" != "true" ]]; then
                echo "$dist_dirs" | xargs rm -rf 2>/dev/null
                log_success "Removed dist directories"
                increment_stat "success"
            else
                log_info "[DRY RUN] Would remove dist directories"
            fi
        else
            increment_stat "skipped"
        fi
    else
        log_info "No dist directories found"
    fi

    # Phase 4: __pycache__
    print_section "Phase 4: Python Cache (__pycache__)"
    increment_stat "total"
    cleanup_dir_type "$base_path" "__pycache__" "$auto_yes" "Python cache"

    # Phase 5: .pytest_cache
    print_section "Phase 5: Pytest Cache (.pytest_cache)"
    increment_stat "total"
    cleanup_dir_type "$base_path" ".pytest_cache" "$auto_yes" "pytest cache"

    # Phase 6: .mypy_cache
    print_section "Phase 6: Mypy Cache (.mypy_cache)"
    increment_stat "total"
    cleanup_dir_type "$base_path" ".mypy_cache" "$auto_yes" "mypy cache"

    # Phase 7: Rust target directories (if requested)
    if [[ "$include_rust" == "true" ]]; then
        print_section "Phase 7: Rust Target Directories"
        increment_stat "total"

        # Find Rust target directories (identified by having debug/ or release/ subdirs)
        local rust_targets
        rust_targets=$(find "$base_path" -maxdepth 4 -type d -name "target" 2>/dev/null | \
            while read -r dir; do
                [[ -d "$dir/debug" || -d "$dir/release" ]] && echo "$dir"
            done)

        if [[ -n "$rust_targets" ]]; then
            local rust_count rust_size rust_size_human
            rust_count=$(echo "$rust_targets" | wc -l)
            rust_size=$(echo "$rust_targets" | xargs -I{} du -sb {} 2>/dev/null | awk '{sum += $1} END {print sum+0}')
            rust_size_human=$(human_size "$rust_size")

            log_info "Found $rust_count Rust target directories ($rust_size_human total)"
            log_warning "Removing Rust targets will require 'cargo build' to restore"

            # Show which projects have targets
            if [[ "$SYSMON_VERBOSE" == "true" ]]; then
                echo "Rust targets found in:"
                echo "$rust_targets" | while read -r dir; do
                    local dir_size
                    dir_size=$(du -sh "$dir" 2>/dev/null | cut -f1)
                    echo "  $dir_size  $dir"
                done
            fi

            if [[ "$auto_yes" == "true" ]] || confirm "Remove $rust_count Rust target directories ($rust_size_human)?"; then
                if [[ "$SYSMON_DRY_RUN" != "true" ]]; then
                    echo "$rust_targets" | xargs rm -rf 2>/dev/null
                    log_success "Removed Rust target directories ($rust_size_human freed)"
                    increment_stat "success"
                else
                    log_info "[DRY RUN] Would remove Rust target directories ($rust_size_human)"
                fi
            else
                increment_stat "skipped"
            fi
        else
            log_info "No Rust target directories found"
        fi
    fi

    # Phase 8: node_modules (if requested)
    if [[ "$include_node_modules" == "true" ]]; then
        print_section "Phase 8: Node Modules"
        increment_stat "total"

        log_warning "Removing node_modules will require 'npm install' to restore dependencies"
        cleanup_dir_type "$base_path" "node_modules" "$auto_yes" "node_modules"
    fi

    print_stats "Build Cleanup"

    echo ""
    log_info "Run 'sysmon analyze' to verify disk usage after cleanup"
}

# Execute build cleanup on remote instance
run_remote_builds_cleanup() {
    local instance="$1"
    local include_node_modules="$2"
    local include_rust="$3"

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

    log_info "Cleaning build artifacts on Instance $instance ($ip)..."

    # Build remote command - remove standard build artifacts
    local remote_cmd="echo '=== Build cleanup on Instance $instance ===' && "
    remote_cmd+="echo 'Removing .next, dist, __pycache__, .pytest_cache, .mypy_cache...' && "
    remote_cmd+="find ~/fleet -maxdepth 5 -type d \\( -name '.next' -o -name 'dist' -o -name '__pycache__' -o -name '.pytest_cache' -o -name '.mypy_cache' \\) ! -path '*/node_modules/*' -exec rm -rf {} + 2>/dev/null; "
    remote_cmd+="echo 'Standard build artifacts removed'"

    if [[ "$include_node_modules" == "true" ]]; then
        remote_cmd+=" && echo 'Removing node_modules...' && "
        remote_cmd+="find ~/fleet -maxdepth 4 -type d -name 'node_modules' -exec rm -rf {} + 2>/dev/null && "
        remote_cmd+="rm -rf ~/fleet/environments/*/node_modules ~/fleet/environments/*/*/node_modules 2>/dev/null; "
        remote_cmd+="echo 'node_modules removed'"
    fi

    if [[ "$include_rust" == "true" ]]; then
        remote_cmd+=" && echo 'Removing Rust target directories...' && "
        remote_cmd+="find ~/fleet -maxdepth 4 -type d -name 'target' -exec sh -c 'test -d \"\$1/debug\" -o -d \"\$1/release\" && rm -rf \"\$1\"' _ {} \\; 2>/dev/null; "
        remote_cmd+="echo 'Rust targets removed'"
    fi

    remote_cmd+=" && echo '' && df -h / | tail -1"

    ssh -i "$ssh_key" -o StrictHostKeyChecking=no -o ConnectTimeout=30 \
        "ubuntu@$ip" "$remote_cmd" 2>/dev/null

    if [[ $? -eq 0 ]]; then
        log_success "Instance $instance build cleanup complete"
    else
        log_warning "Instance $instance build cleanup may have partially failed"
    fi
}
