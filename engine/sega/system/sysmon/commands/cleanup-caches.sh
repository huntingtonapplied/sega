#!/bin/bash
# ============================================================================
# SYSMON - Cleanup Caches Command
# ============================================================================
# System cache cleanup operations (npm, cargo, claude, etc.)
# ============================================================================

# Help text for this command
cmd_cleanup_caches_help() {
    cat << 'EOF'
sysmon cleanup caches - System cache cleanup

Usage: sysmon cleanup caches [options]

Options:
  --npm             Clean npm cache (~/.npm and /root/.npm)
  --cargo           Clean cargo registry cache (~/.cargo/registry)
  --claude          Clean Claude Code cache (~/.claude)
  --homebrew        Clean Homebrew cache (brew cleanup --prune=all)
  --chrome          Clean Chrome temp/cache data
  --system          Clean system temp files (/private/tmp, /var/folders)
  --venv            Clean Python virtual environments in projects
  --tmp-sql         Clean temporary SQL dump files
  --all             Clean all caches (default if no specific flag)
  --yes, -y         Skip confirmation prompts
  --help            Show this help

Cache locations:
  npm:      ~/.npm, /root/.npm (requires sudo)
  cargo:    ~/.cargo/registry, ~/.cargo/git
  claude:   ~/.claude
  homebrew: /opt/homebrew cache, old versions
  chrome:   /private/var/folders/.../com.google.Chrome*
  system:   /private/tmp, /private/var/folders caches
  venv:     */venv directories in projects
  tmp-sql:  /private/tmp/*.sql, /tmp/*.sql

Examples:
  sysmon cleanup caches              # Clean all caches (interactive)
  sysmon cleanup caches --npm        # Clean only npm cache
  sysmon cleanup caches --homebrew   # Clean Homebrew old versions
  sysmon cleanup caches --chrome     # Clean Chrome temp data
  sysmon cleanup caches --system     # Clean system temp files
  sysmon cleanup caches --all --yes  # Clean all caches, auto-confirm

Note: Cleaning caches is safe - they will be rebuilt automatically when needed.
EOF
}

# Get cache directory size
get_cache_size() {
    local path="$1"
    if [[ -d "$path" ]]; then
        du -sb "$path" 2>/dev/null | awk '{print $1}'
    else
        echo "0"
    fi
}

# Clean npm cache
cleanup_npm_cache() {
    local auto_yes="$1"

    print_section "NPM Cache"
    increment_stat "total"

    local user_npm="$HOME/.npm"
    local root_npm="/root/.npm"
    local total_size=0
    local locations=()

    if [[ -d "$user_npm" ]]; then
        local size
        size=$(get_cache_size "$user_npm")
        total_size=$((total_size + size))
        locations+=("$user_npm")
    fi

    # Check root npm (may need sudo)
    if sudo test -d "$root_npm" 2>/dev/null; then
        local size
        size=$(sudo du -sb "$root_npm" 2>/dev/null | awk '{print $1}')
        total_size=$((total_size + size))
        locations+=("$root_npm")
    fi

    if [[ ${#locations[@]} -eq 0 ]]; then
        log_info "No npm cache found"
        return 0
    fi

    local size_human
    size_human=$(human_size "$total_size")
    log_info "Found npm cache: $size_human"

    for loc in "${locations[@]}"; do
        log_debug "  $loc"
    done

    if [[ "$auto_yes" != "true" ]]; then
        if ! confirm "Remove npm cache ($size_human)?"; then
            log_info "Skipped npm cache"
            increment_stat "skipped"
            return 0
        fi
    fi

    if [[ "$SYSMON_DRY_RUN" == "true" ]]; then
        log_info "[DRY RUN] Would remove npm cache ($size_human)"
        return 0
    fi

    # Remove user npm cache
    if [[ -d "$user_npm" ]]; then
        rm -rf "$user_npm" 2>/dev/null
    fi

    # Remove root npm cache (with sudo)
    if sudo test -d "$root_npm" 2>/dev/null; then
        sudo rm -rf "$root_npm" 2>/dev/null
    fi

    log_success "Removed npm cache ($size_human freed)"
    increment_stat "success"
}

# Clean cargo cache
cleanup_cargo_cache() {
    local auto_yes="$1"

    print_section "Cargo Cache"
    increment_stat "total"

    local cargo_registry="$HOME/.cargo/registry"
    local cargo_git="$HOME/.cargo/git"
    local total_size=0
    local locations=()

    if [[ -d "$cargo_registry" ]]; then
        local size
        size=$(get_cache_size "$cargo_registry")
        total_size=$((total_size + size))
        locations+=("$cargo_registry")
    fi

    if [[ -d "$cargo_git" ]]; then
        local size
        size=$(get_cache_size "$cargo_git")
        total_size=$((total_size + size))
        locations+=("$cargo_git")
    fi

    if [[ ${#locations[@]} -eq 0 ]]; then
        log_info "No cargo cache found"
        return 0
    fi

    local size_human
    size_human=$(human_size "$total_size")
    log_info "Found cargo cache: $size_human"
    log_info "Note: This preserves ~/.cargo/bin (installed tools)"

    for loc in "${locations[@]}"; do
        log_debug "  $loc"
    done

    if [[ "$auto_yes" != "true" ]]; then
        if ! confirm "Remove cargo cache ($size_human)?"; then
            log_info "Skipped cargo cache"
            increment_stat "skipped"
            return 0
        fi
    fi

    if [[ "$SYSMON_DRY_RUN" == "true" ]]; then
        log_info "[DRY RUN] Would remove cargo cache ($size_human)"
        return 0
    fi

    for loc in "${locations[@]}"; do
        rm -rf "$loc" 2>/dev/null
    done

    log_success "Removed cargo cache ($size_human freed)"
    increment_stat "success"
}

# Clean Claude Code cache
cleanup_claude_cache() {
    local auto_yes="$1"

    print_section "Claude Code Cache"
    increment_stat "total"

    local claude_dir="$HOME/.claude"

    if [[ ! -d "$claude_dir" ]]; then
        log_info "No Claude cache found"
        return 0
    fi

    local size size_human
    size=$(get_cache_size "$claude_dir")
    size_human=$(human_size "$size")

    log_info "Found Claude cache: $size_human"
    log_warning "This will clear Claude Code session data and preferences"

    if [[ "$auto_yes" != "true" ]]; then
        if ! confirm "Remove Claude cache ($size_human)?" "n"; then
            log_info "Skipped Claude cache"
            increment_stat "skipped"
            return 0
        fi
    fi

    if [[ "$SYSMON_DRY_RUN" == "true" ]]; then
        log_info "[DRY RUN] Would remove Claude cache ($size_human)"
        return 0
    fi

    rm -rf "$claude_dir" 2>/dev/null

    log_success "Removed Claude cache ($size_human freed)"
    increment_stat "success"
}

# Clean Homebrew cache and old versions
cleanup_homebrew_cache() {
    local auto_yes="$1"

    print_section "Homebrew Cache"
    increment_stat "total"

    if ! command -v brew &>/dev/null; then
        log_info "Homebrew not installed"
        return 0
    fi

    log_info "Checking Homebrew for cleanup opportunities..."
    
    # Get estimated cleanup size
    local cleanup_info
    cleanup_info=$(brew cleanup --dry-run 2>/dev/null | tail -5)
    
    if [[ -z "$cleanup_info" ]]; then
        log_info "No Homebrew cache to clean"
        return 0
    fi

    log_info "Homebrew cleanup will remove old versions and cache"

    if [[ "$auto_yes" != "true" ]]; then
        if ! confirm "Run brew cleanup --prune=all?"; then
            log_info "Skipped Homebrew cleanup"
            increment_stat "skipped"
            return 0
        fi
    fi

    if [[ "$SYSMON_DRY_RUN" == "true" ]]; then
        log_info "[DRY RUN] Would run: brew cleanup --prune=all"
        return 0
    fi

    brew cleanup --prune=all 2>&1 | tail -5
    log_success "Homebrew cleanup complete"
    increment_stat "success"
}

# Clean Chrome temp and cache data
cleanup_chrome_cache() {
    local auto_yes="$1"

    print_section "Chrome Temp/Cache Data"
    increment_stat "total"

    local total_size=0
    local locations=()

    # macOS Chrome temp locations
    local chrome_code_sign="/private/var/folders/*/*/X/com.google.Chrome.code_sign_clone"
    local chrome_helper="/private/var/folders/*/*/C/com.google.Chrome.helper"
    
    # Find and calculate sizes
    while IFS= read -r dir; do
        if [[ -d "$dir" ]]; then
            local size
            size=$(get_cache_size "$dir")
            total_size=$((total_size + size))
            locations+=("$dir")
        fi
    done < <(find /private/var/folders -maxdepth 5 -type d -name "com.google.Chrome*" 2>/dev/null)

    if [[ ${#locations[@]} -eq 0 ]]; then
        log_info "No Chrome temp data found"
        return 0
    fi

    local size_human
    size_human=$(human_size "$total_size")
    log_info "Found Chrome temp data: $size_human in ${#locations[@]} locations"

    if [[ "$auto_yes" != "true" ]]; then
        if ! confirm "Remove Chrome temp data ($size_human)?"; then
            log_info "Skipped Chrome cache"
            increment_stat "skipped"
            return 0
        fi
    fi

    if [[ "$SYSMON_DRY_RUN" == "true" ]]; then
        log_info "[DRY RUN] Would remove Chrome temp data ($size_human)"
        return 0
    fi

    for loc in "${locations[@]}"; do
        rm -rf "$loc" 2>/dev/null
    done

    log_success "Removed Chrome temp data ($size_human freed)"
    increment_stat "success"
}

# Clean system temp files
cleanup_system_temp() {
    local auto_yes="$1"

    print_section "System Temp Files"
    increment_stat "total"

    local total_size=0
    local locations=()

    # /private/tmp files (excluding active ones)
    if [[ -d "/private/tmp" ]]; then
        # Find large files in /tmp older than 1 day
        while IFS= read -r file; do
            if [[ -f "$file" ]]; then
                local size
                size=$(stat -f%z "$file" 2>/dev/null || echo "0")
                total_size=$((total_size + size))
                locations+=("$file")
            fi
        done < <(find /private/tmp -type f -size +10M -mtime +1 2>/dev/null)
    fi

    # Check for SQL dumps specifically
    while IFS= read -r file; do
        if [[ -f "$file" ]]; then
            local size
            size=$(stat -f%z "$file" 2>/dev/null || echo "0")
            total_size=$((total_size + size))
            # Only add if not already in list
            if [[ ! " ${locations[*]} " =~ " ${file} " ]]; then
                locations+=("$file")
            fi
        fi
    done < <(find /private/tmp /tmp -name "*.sql" -type f 2>/dev/null)

    if [[ ${#locations[@]} -eq 0 ]]; then
        log_info "No significant temp files found"
        return 0
    fi

    local size_human
    size_human=$(human_size "$total_size")
    log_info "Found ${#locations[@]} temp files: $size_human"

    # Show top files
    for loc in "${locations[@]:0:5}"; do
        local file_size
        file_size=$(du -sh "$loc" 2>/dev/null | cut -f1)
        log_debug "  $file_size  $(basename "$loc")"
    done

    if [[ "$auto_yes" != "true" ]]; then
        if ! confirm "Remove temp files ($size_human)?"; then
            log_info "Skipped temp files"
            increment_stat "skipped"
            return 0
        fi
    fi

    if [[ "$SYSMON_DRY_RUN" == "true" ]]; then
        log_info "[DRY RUN] Would remove temp files ($size_human)"
        return 0
    fi

    for loc in "${locations[@]}"; do
        rm -f "$loc" 2>/dev/null
    done

    log_success "Removed temp files ($size_human freed)"
    increment_stat "success"
}

# Clean Python virtual environments in project directories
cleanup_venv_cache() {
    local auto_yes="$1"

    print_section "Python Virtual Environments"
    increment_stat "total"

    local fleet_dir="${FLEET_DIR:-$HOME/fleet}"
    local total_size=0
    local locations=()

    # Find venv directories in projects
    while IFS= read -r dir; do
        if [[ -d "$dir" ]]; then
            local size
            size=$(get_cache_size "$dir")
            total_size=$((total_size + size))
            locations+=("$dir")
        fi
    done < <(find "$fleet_dir" -maxdepth 3 -type d -name "venv" 2>/dev/null)

    if [[ ${#locations[@]} -eq 0 ]]; then
        log_info "No venv directories found"
        return 0
    fi

    local size_human
    size_human=$(human_size "$total_size")
    log_info "Found ${#locations[@]} venv directories: $size_human"
    log_warning "These can be regenerated with 'pip install -r requirements.txt'"

    # Show locations
    for loc in "${locations[@]:0:5}"; do
        local venv_size
        venv_size=$(du -sh "$loc" 2>/dev/null | cut -f1)
        local project
        project=$(echo "$loc" | sed -E "s|$fleet_dir/([^/]+)/.*|\1|")
        log_debug "  $venv_size  $project/venv"
    done

    if [[ "$auto_yes" != "true" ]]; then
        if ! confirm "Remove venv directories ($size_human)?" "n"; then
            log_info "Skipped venv directories"
            increment_stat "skipped"
            return 0
        fi
    fi

    if [[ "$SYSMON_DRY_RUN" == "true" ]]; then
        log_info "[DRY RUN] Would remove venv directories ($size_human)"
        return 0
    fi

    for loc in "${locations[@]}"; do
        rm -rf "$loc" 2>/dev/null
    done

    log_success "Removed venv directories ($size_human freed)"
    increment_stat "success"
}

# Clean temporary SQL dump files
cleanup_sql_dumps() {
    local auto_yes="$1"

    print_section "Temporary SQL Dumps"
    increment_stat "total"

    local total_size=0
    local locations=()

    # Find SQL dumps in common temp locations
    while IFS= read -r file; do
        if [[ -f "$file" ]]; then
            local size
            size=$(stat -f%z "$file" 2>/dev/null || echo "0")
            total_size=$((total_size + size))
            locations+=("$file")
        fi
    done < <(find /private/tmp /tmp "$HOME" -maxdepth 2 -name "*.sql" -type f -size +1M 2>/dev/null)

    if [[ ${#locations[@]} -eq 0 ]]; then
        log_info "No SQL dump files found"
        return 0
    fi

    local size_human
    size_human=$(human_size "$total_size")
    log_info "Found ${#locations[@]} SQL dump files: $size_human"

    for loc in "${locations[@]}"; do
        local file_size
        file_size=$(du -sh "$loc" 2>/dev/null | cut -f1)
        log_debug "  $file_size  $(basename "$loc")"
    done

    if [[ "$auto_yes" != "true" ]]; then
        if ! confirm "Remove SQL dump files ($size_human)?"; then
            log_info "Skipped SQL dumps"
            increment_stat "skipped"
            return 0
        fi
    fi

    if [[ "$SYSMON_DRY_RUN" == "true" ]]; then
        log_info "[DRY RUN] Would remove SQL dumps ($size_human)"
        return 0
    fi

    for loc in "${locations[@]}"; do
        rm -f "$loc" 2>/dev/null
    done

    log_success "Removed SQL dump files ($size_human freed)"
    increment_stat "success"
}

# Show cache summary
show_cache_summary() {
    echo "Cache Summary:"
    echo ""

    local total=0

    # NPM
    local npm_size=0
    [[ -d "$HOME/.npm" ]] && npm_size=$(get_cache_size "$HOME/.npm")
    if sudo test -d "/root/.npm" 2>/dev/null; then
        local root_size
        root_size=$(sudo du -sb "/root/.npm" 2>/dev/null | awk '{print $1}')
        npm_size=$((npm_size + root_size))
    fi
    total=$((total + npm_size))
    echo "  npm cache:       $(human_size "$npm_size")"

    # Cargo
    local cargo_size=0
    [[ -d "$HOME/.cargo/registry" ]] && cargo_size=$((cargo_size + $(get_cache_size "$HOME/.cargo/registry")))
    [[ -d "$HOME/.cargo/git" ]] && cargo_size=$((cargo_size + $(get_cache_size "$HOME/.cargo/git")))
    total=$((total + cargo_size))
    echo "  cargo cache:     $(human_size "$cargo_size")"

    # Claude
    local claude_size=0
    [[ -d "$HOME/.claude" ]] && claude_size=$(get_cache_size "$HOME/.claude")
    total=$((total + claude_size))
    echo "  claude cache:    $(human_size "$claude_size")"

    # Chrome temp (macOS)
    local chrome_size=0
    while IFS= read -r dir; do
        if [[ -d "$dir" ]]; then
            local size
            size=$(get_cache_size "$dir")
            chrome_size=$((chrome_size + size))
        fi
    done < <(find /private/var/folders -maxdepth 5 -type d -name "com.google.Chrome*" 2>/dev/null)
    total=$((total + chrome_size))
    echo "  chrome temp:     $(human_size "$chrome_size")"

    # System temp (large files in /tmp)
    local tmp_size=0
    while IFS= read -r file; do
        if [[ -f "$file" ]]; then
            local size
            size=$(stat -f%z "$file" 2>/dev/null || echo "0")
            tmp_size=$((tmp_size + size))
        fi
    done < <(find /private/tmp /tmp -type f -size +10M 2>/dev/null 2>&1)
    total=$((total + tmp_size))
    echo "  system temp:     $(human_size "$tmp_size")"

    # Python venvs in projects
    local venv_size=0
    local fleet_dir="${FLEET_DIR:-$HOME/fleet}"
    while IFS= read -r dir; do
        if [[ -d "$dir" ]]; then
            local size
            size=$(get_cache_size "$dir")
            venv_size=$((venv_size + size))
        fi
    done < <(find "$fleet_dir" -maxdepth 3 -type d -name "venv" 2>/dev/null)
    total=$((total + venv_size))
    echo "  project venvs:   $(human_size "$venv_size")"

    # SQL dumps
    local sql_size=0
    while IFS= read -r file; do
        if [[ -f "$file" ]]; then
            local size
            size=$(stat -f%z "$file" 2>/dev/null || echo "0")
            sql_size=$((sql_size + size))
        fi
    done < <(find /private/tmp /tmp "$HOME" -maxdepth 2 -name "*.sql" -type f -size +1M 2>/dev/null 2>&1)
    total=$((total + sql_size))
    echo "  sql dumps:       $(human_size "$sql_size")"

    echo ""
    echo "Total: $(human_size "$total")"
    echo ""
}

# Main command function
cmd_cleanup_caches() {
    local clean_npm=false
    local clean_cargo=false
    local clean_claude=false
    local clean_homebrew=false
    local clean_chrome=false
    local clean_system=false
    local clean_venv=false
    local clean_sql=false
    local clean_all=false
    local auto_yes=false

    # Parse arguments
    while [[ $# -gt 0 ]]; do
        case "$1" in
            --npm)
                clean_npm=true
                shift
                ;;
            --cargo)
                clean_cargo=true
                shift
                ;;
            --claude)
                clean_claude=true
                shift
                ;;
            --homebrew)
                clean_homebrew=true
                shift
                ;;
            --chrome)
                clean_chrome=true
                shift
                ;;
            --system)
                clean_system=true
                shift
                ;;
            --venv)
                clean_venv=true
                shift
                ;;
            --tmp-sql)
                clean_sql=true
                shift
                ;;
            --all)
                clean_all=true
                shift
                ;;
            --yes|-y)
                auto_yes=true
                shift
                ;;
            --help|-h)
                cmd_cleanup_caches_help
                return 0
                ;;
            *)
                log_error "Unknown option: $1"
                cmd_cleanup_caches_help
                return 1
                ;;
        esac
    done

    # Default to all if no specific cache selected
    if [[ "$clean_npm" == "false" && "$clean_cargo" == "false" && "$clean_claude" == "false" && \
          "$clean_homebrew" == "false" && "$clean_chrome" == "false" && "$clean_system" == "false" && \
          "$clean_venv" == "false" && "$clean_sql" == "false" ]]; then
        clean_all=true
    fi

    if [[ "$clean_all" == "true" ]]; then
        clean_npm=true
        clean_cargo=true
        clean_claude=true
        clean_homebrew=true
        clean_chrome=true
        clean_system=true
        clean_venv=true
        clean_sql=true
    fi

    print_header "System Cache Cleanup"

    echo ""
    show_cache_summary

    # Initialize stats
    init_stats

    # Clean selected caches
    if [[ "$clean_npm" == "true" ]]; then
        cleanup_npm_cache "$auto_yes"
    fi

    if [[ "$clean_cargo" == "true" ]]; then
        cleanup_cargo_cache "$auto_yes"
    fi

    if [[ "$clean_claude" == "true" ]]; then
        cleanup_claude_cache "$auto_yes"
    fi

    if [[ "$clean_homebrew" == "true" ]]; then
        cleanup_homebrew_cache "$auto_yes"
    fi

    if [[ "$clean_chrome" == "true" ]]; then
        cleanup_chrome_cache "$auto_yes"
    fi

    if [[ "$clean_system" == "true" ]]; then
        cleanup_system_temp "$auto_yes"
    fi

    if [[ "$clean_sql" == "true" ]]; then
        cleanup_sql_dumps "$auto_yes"
    fi

    if [[ "$clean_venv" == "true" ]]; then
        cleanup_venv_cache "$auto_yes"
    fi

    print_stats "Cache Cleanup"

    echo ""
    log_info "Run 'sysmon status' to verify disk usage after cleanup"
}
