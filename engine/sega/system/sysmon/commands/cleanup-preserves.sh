#!/bin/bash
# ============================================================================
# SYSMON - Cleanup Preserves Command
# ============================================================================
# Backup/preserve cleanup with retention policy
# ============================================================================

# Help text for this command
cmd_cleanup_preserves_help() {
    cat << 'EOF'
sysmon cleanup preserves - Backup and preserve cleanup

Usage: sysmon cleanup preserves [options]

Options:
  --keep <n>        Keep the N most recent preserves (default: 3)
  --path <dir>      Preserve directory path (default: ~/fleet-preserves)
  --all             Remove ALL preserves (use with caution)
  --yes, -y         Skip confirmation prompts
  --help            Show this help

Default behavior:
  Keeps the 3 most recent preserves and removes older ones.

Examples:
  sysmon cleanup preserves              # Keep 3 most recent
  sysmon cleanup preserves --keep 5     # Keep 5 most recent
  sysmon cleanup preserves --all        # Remove ALL preserves
  sysmon cleanup preserves --yes        # Auto-confirm

Preserve location: ~/fleet-preserves
Created by: sega/engine/sega/system/preserve/create-ecosystem-preserve.sh
EOF
}

# List preserves sorted by date (newest first)
list_preserves() {
    local preserve_dir="$1"

    if [[ ! -d "$preserve_dir" ]]; then
        return
    fi

    # List directories/files sorted by modification time (newest first)
    ls -t "$preserve_dir" 2>/dev/null
}

# Get preserve size
get_preserve_size() {
    local path="$1"
    if [[ -e "$path" ]]; then
        du -sb "$path" 2>/dev/null | awk '{print $1}'
    else
        echo "0"
    fi
}

# Show preserves summary
show_preserves_summary() {
    local preserve_dir="$1"

    if [[ ! -d "$preserve_dir" ]]; then
        echo "Preserve directory not found: $preserve_dir"
        return
    fi

    echo "Preserves in: $preserve_dir"
    echo ""

    local total_size=0
    local count=0

    while IFS= read -r item; do
        [[ -z "$item" ]] && continue
        local full_path="$preserve_dir/$item"
        local size size_human mod_date

        size=$(get_preserve_size "$full_path")
        size_human=$(human_size "$size")
        mod_date=$(stat -c '%y' "$full_path" 2>/dev/null | cut -d' ' -f1)

        total_size=$((total_size + size))
        count=$((count + 1))

        printf "  %2d. %-40s %10s  %s\n" "$count" "$item" "$size_human" "$mod_date"
    done <<< "$(list_preserves "$preserve_dir")"

    echo ""
    echo "Total: $count preserves ($(human_size "$total_size"))"
    echo ""
}

# Main command function
cmd_cleanup_preserves() {
    local preserve_dir="$HOME/fleet-preserves"
    local keep_count=3
    local remove_all=false
    local auto_yes=false

    # Parse arguments
    while [[ $# -gt 0 ]]; do
        case "$1" in
            --keep)
                keep_count="$2"
                if ! [[ "$keep_count" =~ ^[0-9]+$ ]]; then
                    log_error "Invalid keep count: $keep_count"
                    return 1
                fi
                shift 2
                ;;
            --path)
                preserve_dir="$2"
                shift 2
                ;;
            --all)
                remove_all=true
                shift
                ;;
            --yes|-y)
                auto_yes=true
                shift
                ;;
            --help|-h)
                cmd_cleanup_preserves_help
                return 0
                ;;
            *)
                log_error "Unknown option: $1"
                cmd_cleanup_preserves_help
                return 1
                ;;
        esac
    done

    print_header "Preserve Cleanup"

    # Check if preserve directory exists
    if [[ ! -d "$preserve_dir" ]]; then
        log_info "No preserve directory found: $preserve_dir"
        log_info "Nothing to clean up"
        return 0
    fi

    echo ""
    show_preserves_summary "$preserve_dir"

    # Get list of preserves
    local preserves
    preserves=$(list_preserves "$preserve_dir")

    if [[ -z "$preserves" ]]; then
        log_info "No preserves found"
        return 0
    fi

    local total_count
    total_count=$(echo "$preserves" | wc -l)

    # Initialize stats
    init_stats

    if [[ "$remove_all" == "true" ]]; then
        # Remove all preserves
        print_section "Remove All Preserves"
        increment_stat "total"

        local total_size=0
        while IFS= read -r item; do
            [[ -z "$item" ]] && continue
            local size
            size=$(get_preserve_size "$preserve_dir/$item")
            total_size=$((total_size + size))
        done <<< "$preserves"

        local size_human
        size_human=$(human_size "$total_size")

        log_warning "This will remove ALL $total_count preserves ($size_human)"

        if [[ "$auto_yes" != "true" ]]; then
            if ! confirm "Remove ALL preserves ($size_human)?" "n"; then
                log_info "Skipped preserve cleanup"
                increment_stat "skipped"
                print_stats "Preserve Cleanup"
                return 0
            fi
        fi

        if [[ "$SYSMON_DRY_RUN" == "true" ]]; then
            log_info "[DRY RUN] Would remove all preserves ($size_human)"
            return 0
        fi

        rm -rf "$preserve_dir"
        log_success "Removed all preserves ($size_human freed)"
        increment_stat "success"

    else
        # Keep N most recent, remove the rest
        print_section "Cleanup Old Preserves (keeping $keep_count most recent)"
        increment_stat "total"

        if [[ "$total_count" -le "$keep_count" ]]; then
            log_info "Only $total_count preserves found, keeping all (threshold: $keep_count)"
            return 0
        fi

        # Get preserves to remove (skip first N)
        local to_remove
        to_remove=$(echo "$preserves" | tail -n +$((keep_count + 1)))

        local remove_count remove_size=0
        remove_count=$(echo "$to_remove" | wc -l)

        while IFS= read -r item; do
            [[ -z "$item" ]] && continue
            local size
            size=$(get_preserve_size "$preserve_dir/$item")
            remove_size=$((remove_size + size))
        done <<< "$to_remove"

        local size_human
        size_human=$(human_size "$remove_size")

        log_info "Found $remove_count old preserves to remove ($size_human)"
        log_info "Keeping $keep_count most recent preserves"

        if [[ "$SYSMON_VERBOSE" == "true" ]]; then
            echo ""
            echo "Will remove:"
            while IFS= read -r item; do
                [[ -z "$item" ]] && continue
                echo "  - $item"
            done <<< "$to_remove"
            echo ""
        fi

        if [[ "$auto_yes" != "true" ]]; then
            if ! confirm "Remove $remove_count old preserves ($size_human)?"; then
                log_info "Skipped preserve cleanup"
                increment_stat "skipped"
                print_stats "Preserve Cleanup"
                return 0
            fi
        fi

        if [[ "$SYSMON_DRY_RUN" == "true" ]]; then
            log_info "[DRY RUN] Would remove $remove_count preserves ($size_human)"
            return 0
        fi

        # Remove old preserves
        local removed=0
        while IFS= read -r item; do
            [[ -z "$item" ]] && continue
            if rm -rf "$preserve_dir/$item" 2>/dev/null; then
                removed=$((removed + 1))
                log_debug "Removed: $item"
            fi
        done <<< "$to_remove"

        log_success "Removed $removed old preserves ($size_human freed)"
        increment_stat "success"
    fi

    print_stats "Preserve Cleanup"

    echo ""
    log_info "Run 'sysmon status' to verify disk usage after cleanup"
}
