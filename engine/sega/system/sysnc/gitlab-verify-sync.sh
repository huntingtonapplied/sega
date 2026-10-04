#!/bin/bash

###############################################################################
# FLEET GitLab Sync Verification Script
#
# Purpose: Verify that local machine and all EC2 instances have the same
#          git state for the main repository and all submodules.
#
# Usage: bash gitlab_verify_sync.sh
#
# Requirements:
# - Must be run from /home/testuser/fleet (or ~/fleet on local)
# - SSH keys for EC2 instances must be configured
# - Git must be installed on all instances
#
###############################################################################

# ANSI color codes
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
BOLD='\033[1m'
NC='\033[0m' # No Color

# Configuration
FLEET_ROOT="$HOME/fleet"
LOG_FILE="/tmp/verify_sync_$(date +%Y%m%d_%H%M%S).log"

# EC2 Instance Configuration
# Values come from the environment: set SYSMON_INSTANCE*_IP / SYSMON_SSH_KEY,
# or configure [instances] in config/sega.toml (injected by the sega CLI).
IP1="${SYSMON_INSTANCE1_IP:-${INSTANCE1_IP:-}}"
IP2="${SYSMON_INSTANCE2_IP:-${INSTANCE2_IP:-}}"
KEY="${SYSMON_SSH_KEY:-${SSH_KEY_PATH:-}}"
if [[ -z "$IP1" || -z "$IP2" || -z "$KEY" ]]; then
    echo "ERROR: instance configuration not set." >&2
    echo "Set SYSMON_INSTANCE1_IP, SYSMON_INSTANCE2_IP and SYSMON_SSH_KEY, or configure [instances] in config/sega.toml and run via the sega CLI." >&2
    exit 1
fi
declare -A EC2_INSTANCES
EC2_INSTANCES[prod-01]="${INSTANCE1_USER:-ubuntu}@${IP1}:${KEY}"
EC2_INSTANCES[prod-02]="${INSTANCE2_USER:-ubuntu}@${IP2}:${KEY}"
# Add more instances as they become active:
# EC2_INSTANCES[prod-03]="<user>@<instance-3-ip>:~/.ssh/<key>.pem"

###############################################################################
# Helper Functions
###############################################################################

print_header() {
    echo -e "\n${BLUE}${BOLD}=== $1 ===${NC}"
}

print_section() {
    echo -e "${CYAN}$1${NC}"
}

print_success() {
    echo -e "${GREEN}[✓] $1${NC}"
}

print_warning() {
    echo -e "${YELLOW}[!] $1${NC}"
}

print_error() {
    echo -e "${RED}[✗] $1${NC}"
}

log() {
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] $1" >> "$LOG_FILE"
}

###############################################################################
# Safety Check
###############################################################################

safety_check() {
    print_header "Safety Check"

    # Check if running from correct directory
    CURRENT_DIR=$(pwd)
    if [[ ! "$CURRENT_DIR" =~ "fleet"$ ]]; then
        print_error "Script must be run from $FLEET_ROOT"
        echo "Current directory: $CURRENT_DIR"
        exit 1
    fi

    print_success "Running from correct directory ($CURRENT_DIR)"
    log "Safety check passed: Running from $CURRENT_DIR"
}

###############################################################################
# Git Status Collection Functions
###############################################################################

get_git_status_local() {
    local repo_path="$1"
    cd "$repo_path" 2>/dev/null || return 1

    local branch=$(git branch --show-current 2>/dev/null || echo "DETACHED")
    local status=$(git status --porcelain 2>/dev/null | wc -l)
    local behind=$(git rev-list --count HEAD..@{u} 2>/dev/null || echo "?")
    local ahead=$(git rev-list --count @{u}..HEAD 2>/dev/null || echo "?")
    local commit=$(git rev-parse --short HEAD 2>/dev/null || echo "?")

    echo "${branch}|${commit}|${ahead}|${behind}|${status}"
}

get_git_status_remote() {
    local instance_name="$1"
    local ssh_config="$2"
    local repo_path="$3"

    # Parse SSH config
    local ssh_user_host=$(echo "$ssh_config" | cut -d':' -f1)
    local ssh_key=$(echo "$ssh_config" | cut -d':' -f2)

    # Get git status via SSH
    ssh -i "$ssh_key" -o ConnectTimeout=10 -o StrictHostKeyChecking=no "$ssh_user_host" \
        "cd $repo_path 2>/dev/null && \
         echo \$(git branch --show-current 2>/dev/null || echo 'DETACHED')'|'\
\$(git rev-parse --short HEAD 2>/dev/null || echo '?')'|'\
\$(git rev-list --count @{u}..HEAD 2>/dev/null || echo '?')'|'\
\$(git rev-list --count HEAD..@{u} 2>/dev/null || echo '?')'|'\
\$(git status --porcelain 2>/dev/null | wc -l)" 2>/dev/null
}

###############################################################################
# Main Verification Functions
###############################################################################

verify_main_repository() {
    print_header "Main Repository Verification"

    # Get local status
    print_section "Local Machine:"
    local local_status=$(get_git_status_local "$FLEET_ROOT")
    IFS='|' read -r branch commit ahead behind changes <<< "$local_status"

    echo "  Branch: $branch"
    echo "  Commit: $commit"
    echo "  Ahead: $ahead | Behind: $behind"
    echo "  Uncommitted changes: $changes"

    if [[ "$branch" == "main" ]] && [[ "$ahead" == "0" ]] && [[ "$behind" == "0" ]] && [[ "$changes" == "0" ]]; then
        print_success "Local main repository is clean and up to date"
    else
        print_warning "Local main repository has uncommitted changes or is out of sync"
    fi

    # Check EC2 instances
    for instance_name in "${!EC2_INSTANCES[@]}"; do
        print_section "\nEC2 Instance: $instance_name"

        local remote_status=$(get_git_status_remote "$instance_name" "${EC2_INSTANCES[$instance_name]}" "~/fleet")

        if [[ -z "$remote_status" ]]; then
            print_error "Could not connect to $instance_name or repository not found"
            continue
        fi

        IFS='|' read -r r_branch r_commit r_ahead r_behind r_changes <<< "$remote_status"

        echo "  Branch: $r_branch"
        echo "  Commit: $r_commit"
        echo "  Ahead: $r_ahead | Behind: $r_behind"
        echo "  Uncommitted changes: $r_changes"

        # Compare with local
        if [[ "$commit" == "$r_commit" ]] && [[ "$branch" == "$r_branch" ]]; then
            print_success "$instance_name matches local repository"
        else
            print_warning "$instance_name differs from local (local: $commit on $branch, remote: $r_commit on $r_branch)"
        fi
    done
}

verify_submodules() {
    print_header "Submodule Verification"

    # Get list of submodules
    cd "$FLEET_ROOT"
    local submodules=$(git submodule status | awk '{print $2}')

    for submodule in $submodules; do
        print_section "\nSubmodule: $submodule"

        # Get local status
        local local_status=$(get_git_status_local "$FLEET_ROOT/$submodule")
        IFS='|' read -r branch commit ahead behind changes <<< "$local_status"

        echo "  Local: $branch @ $commit (changes: $changes)"

        # Check each EC2 instance
        for instance_name in "${!EC2_INSTANCES[@]}"; do
            local remote_status=$(get_git_status_remote "$instance_name" "${EC2_INSTANCES[$instance_name]}" "~/fleet/$submodule")

            if [[ -z "$remote_status" ]]; then
                print_error "  $instance_name: Could not get status"
                continue
            fi

            IFS='|' read -r r_branch r_commit r_ahead r_behind r_changes <<< "$remote_status"

            if [[ "$commit" == "$r_commit" ]]; then
                echo "  $instance_name: ✓ $r_branch @ $r_commit"
            else
                print_warning "  $instance_name: ✗ $r_branch @ $r_commit (local: $commit)"
            fi
        done
    done
}

generate_summary_report() {
    print_header "Summary Report"

    local total_repos=$((1 + $(git -C "$FLEET_ROOT" submodule status | wc -l)))
    local synced=0
    local out_of_sync=0

    echo -e "\n${BOLD}Repository Status:${NC}"
    echo "  Total repositories checked: $total_repos (1 main + $(($total_repos - 1)) submodules)"
    echo "  Active EC2 instances: ${#EC2_INSTANCES[@]}"

    print_section "\nRecommendations:"
    echo "  • If repositories are out of sync, run: bash gitlab_bulk_pull.sh"
    echo "  • If EC2 instances differ from local, SSH to instance and run bulk pull"
    echo "  • For detailed logs, check: $LOG_FILE"
}

check_ec2_connectivity() {
    print_header "EC2 Instance Connectivity Check"

    for instance_name in "${!EC2_INSTANCES[@]}"; do
        print_section "Testing $instance_name..."

        local ssh_config="${EC2_INSTANCES[$instance_name]}"
        local ssh_user_host=$(echo "$ssh_config" | cut -d':' -f1)
        local ssh_key=$(echo "$ssh_config" | cut -d':' -f2)

        if ssh -i "$ssh_key" -o ConnectTimeout=5 -o StrictHostKeyChecking=no "$ssh_user_host" "echo 'Connected'" 2>/dev/null | grep -q "Connected"; then
            print_success "$instance_name is reachable"
        else
            print_error "$instance_name is NOT reachable (check SSH key and network)"
        fi
    done
}

###############################################################################
# Main Execution
###############################################################################

main() {
    print_header "FLEET GitLab Sync Verification"
    echo -e "${BLUE}Timestamp: $(date)${NC}"
    echo -e "${BLUE}Log File: $LOG_FILE${NC}"

    log "=== Verification Started ==="

    # Run safety checks
    safety_check

    # Check connectivity to EC2 instances
    check_ec2_connectivity

    # Verify main repository
    verify_main_repository

    # Verify all submodules
    verify_submodules

    # Generate summary report
    generate_summary_report

    print_header "Verification Complete"
    echo -e "${GREEN}${BOLD}All checks completed!${NC}\n"

    log "=== Verification Completed ==="
}

# Run main function
main "$@"
