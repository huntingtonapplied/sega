#!/bin/bash
# ============================================================================
# SYSMON - Cleanup Processes Command
# ============================================================================
# Kill development processes (language servers, watchers, etc.)
# ============================================================================

# Help text for this command
cmd_cleanup_processes_help() {
    cat << 'EOF'
sysmon cleanup processes - Kill development processes

Usage: sysmon cleanup processes [options]

Options:
  --langservers     Kill language server processes (pylsp, pyright, tsserver, gopls)
  --watchers        Kill file watchers (nodemon, chokidar, fswatch)
  --node            Kill all node processes (careful!)
  --all             Kill all of the above (default if no specific flag)
  --instance <N>    Run on EC2 instance (1, 2, or 3)
  --all-instances   Run on all EC2 instances
  --yes, -y         Skip confirmation prompts
  --help            Show this help

Process categories:
  Language Servers: pylsp, pyright, typescript-language-server, tsserver, gopls
  File Watchers:    nodemon, chokidar, fswatch, inotifywait
  Node Processes:   All node/npm processes (use carefully)

Examples:
  sysmon cleanup processes                      # Interactive, kill langservers
  sysmon cleanup processes --langservers        # Kill only language servers
  sysmon cleanup processes --all --yes          # Kill all, auto-confirm
  sysmon cleanup processes --instance 1         # Clean up Instance 1
  sysmon cleanup processes --all-instances      # Clean up all EC2 instances

Note: This is useful when language servers become unresponsive or consume
too much memory.
EOF
}

# Kill processes matching pattern
kill_process_pattern() {
    local pattern="$1"
    local description="$2"
    local auto_yes="$3"

    local pids
    pids=$(pgrep -f "$pattern" 2>/dev/null || true)

    if [[ -z "$pids" ]]; then
        log_info "No $description processes found"
        return 0
    fi

    local count
    count=$(echo "$pids" | wc -l)
    log_info "Found $count $description process(es)"

    # Show process details in verbose mode
    if [[ "$SYSMON_VERBOSE" == "true" ]]; then
        echo "Processes to kill:"
        ps -p $(echo "$pids" | tr '\n' ',') -o pid,ppid,user,%cpu,%mem,cmd --no-headers 2>/dev/null | head -10
    fi

    if [[ "$auto_yes" != "true" ]]; then
        if ! confirm "Kill $count $description process(es)?"; then
            log_info "Skipped $description"
            increment_stat "skipped"
            return 0
        fi
    fi

    if [[ "$SYSMON_DRY_RUN" == "true" ]]; then
        log_info "[DRY RUN] Would kill $count $description process(es)"
        return 0
    fi

    # Kill the processes
    local killed=0
    local failed=0

    for pid in $pids; do
        if kill "$pid" 2>/dev/null; then
            killed=$((killed + 1))
            log_debug "Killed PID $pid"
        else
            # Try with SIGKILL
            if kill -9 "$pid" 2>/dev/null; then
                killed=$((killed + 1))
                log_debug "Force killed PID $pid"
            else
                failed=$((failed + 1))
                log_debug "Failed to kill PID $pid"
            fi
        fi
    done

    if [[ "$failed" -eq 0 ]]; then
        log_success "Killed $killed $description process(es)"
        increment_stat "success"
    else
        log_warning "Killed $killed, failed $failed $description process(es)"
        increment_stat "failed"
    fi
}

# Kill language servers
cleanup_langservers() {
    local auto_yes="$1"

    print_section "Language Servers"
    increment_stat "total"

    # Combined pattern for all language servers
    local pattern='pylsp|pyright|typescript-language-server|tsserver|gopls|rust-analyzer|clangd|jdtls'
    kill_process_pattern "$pattern" "language server" "$auto_yes"
}

# Kill file watchers
cleanup_watchers() {
    local auto_yes="$1"

    print_section "File Watchers"
    increment_stat "total"

    local pattern='nodemon|chokidar|fswatch|inotifywait|watchman'
    kill_process_pattern "$pattern" "file watcher" "$auto_yes"
}

# Kill node processes
cleanup_node() {
    local auto_yes="$1"

    print_section "Node Processes"
    increment_stat "total"

    log_warning "This will kill ALL node processes"

    local pattern='node|npm'
    kill_process_pattern "$pattern" "node" "$auto_yes"
}

# Execute cleanup on remote instance
run_remote_cleanup() {
    local instance="$1"
    local args="$2"

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

    log_info "Cleaning processes on Instance $instance ($ip)..."

    # Build the remote command
    local remote_cmd="pkill -f 'pylsp|pyright|typescript-language-server|tsserver|gopls|rust-analyzer' 2>/dev/null; echo 'Language servers killed'"

    if [[ "$args" == *"--watchers"* || "$args" == *"--all"* ]]; then
        remote_cmd="$remote_cmd; pkill -f 'nodemon|chokidar|fswatch|inotifywait' 2>/dev/null; echo 'Watchers killed'"
    fi

    if [[ "$args" == *"--node"* ]]; then
        remote_cmd="$remote_cmd; pkill -f 'node|npm' 2>/dev/null; echo 'Node processes killed'"
    fi

    ssh -i "$ssh_key" -o StrictHostKeyChecking=no -o ConnectTimeout=10 \
        "ubuntu@$ip" "$remote_cmd" 2>/dev/null

    if [[ $? -eq 0 ]]; then
        log_success "Instance $instance cleanup complete"
    else
        log_warning "Instance $instance cleanup may have partially failed"
    fi
}

# Main command function
cmd_cleanup_processes() {
    local clean_langservers=false
    local clean_watchers=false
    local clean_node=false
    local clean_all=false
    local auto_yes=false
    local target_instance=""
    local all_instances=false

    # Parse arguments
    while [[ $# -gt 0 ]]; do
        case "$1" in
            --langservers)
                clean_langservers=true
                shift
                ;;
            --watchers)
                clean_watchers=true
                shift
                ;;
            --node)
                clean_node=true
                shift
                ;;
            --all)
                clean_all=true
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
                cmd_cleanup_processes_help
                return 0
                ;;
            *)
                log_error "Unknown option: $1"
                cmd_cleanup_processes_help
                return 1
                ;;
        esac
    done

    # Default to langservers if nothing specified
    if [[ "$clean_langservers" == "false" && "$clean_watchers" == "false" && "$clean_node" == "false" && "$clean_all" == "false" ]]; then
        clean_langservers=true
    fi

    if [[ "$clean_all" == "true" ]]; then
        clean_langservers=true
        clean_watchers=true
        # Note: --all does NOT include node by default (too destructive)
    fi

    # Handle remote execution
    if [[ "$all_instances" == "true" ]]; then
        print_header "Process Cleanup (All Instances)"
        local args=""
        [[ "$clean_langservers" == "true" ]] && args="$args --langservers"
        [[ "$clean_watchers" == "true" ]] && args="$args --watchers"
        [[ "$clean_node" == "true" ]] && args="$args --node"

        for i in 1 2 3; do
            run_remote_cleanup "$i" "$args"
        done
        return 0
    fi

    if [[ -n "$target_instance" ]]; then
        print_header "Process Cleanup (Instance $target_instance)"
        local args=""
        [[ "$clean_langservers" == "true" ]] && args="$args --langservers"
        [[ "$clean_watchers" == "true" ]] && args="$args --watchers"
        [[ "$clean_node" == "true" ]] && args="$args --node"

        run_remote_cleanup "$target_instance" "$args"
        return 0
    fi

    # Local execution
    print_header "Process Cleanup (Local)"

    # Initialize stats
    init_stats

    if [[ "$clean_langservers" == "true" ]]; then
        cleanup_langservers "$auto_yes"
    fi

    if [[ "$clean_watchers" == "true" ]]; then
        cleanup_watchers "$auto_yes"
    fi

    if [[ "$clean_node" == "true" ]]; then
        cleanup_node "$auto_yes"
    fi

    print_stats "Process Cleanup"
}
