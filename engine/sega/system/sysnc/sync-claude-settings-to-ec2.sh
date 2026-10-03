#!/bin/bash
# ============================================================================
# Sync Claude Settings to EC2 Instances
# ============================================================================
# PURPOSE:
#   Synchronize all .claude/settings.local.json files from local to EC2
#   instances 1, 2, and 3
#
# USAGE:
#   ./sync-claude-settings-to-ec2.sh [instance]
#   instance: 1 = fleet-prod-01, 2 = fleet-prod-02, 3 = fleet-prod-03, all = all instances
# ============================================================================

set -euo pipefail

# Colors
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
PURPLE='\033[0;35m'
CYAN='\033[0;36m'
WHITE='\033[1;37m'
NC='\033[0m'

# Parse arguments
INSTANCE="${1:-all}"

# EC2 configuration
# Values come from the environment: set SYSMON_INSTANCE*_IP / SYSMON_SSH_KEY,
# or configure [instances] in config/sega.toml (injected by the sega CLI).
SSH_KEY="${SYSMON_SSH_KEY:-${SSH_KEY_PATH:-}}"
IP1="${SYSMON_INSTANCE1_IP:-${INSTANCE1_IP:-}}"
IP2="${SYSMON_INSTANCE2_IP:-${INSTANCE2_IP:-}}"
IP3="${SYSMON_INSTANCE3_IP:-${INSTANCE3_IP:-}}"
if [ -z "$SSH_KEY" ] || [ -z "$IP1" ] || [ -z "$IP2" ] || [ -z "$IP3" ]; then
    echo "ERROR: instance configuration not set." >&2
    echo "Set SYSMON_INSTANCE1_IP/SYSMON_INSTANCE2_IP/SYSMON_INSTANCE3_IP and SYSMON_SSH_KEY, or configure [instances] in config/sega.toml and run via the sega CLI." >&2
    exit 1
fi
INSTANCE1_HOST="${INSTANCE1_USER:-ubuntu}@${IP1}"
INSTANCE2_HOST="${INSTANCE2_USER:-ubuntu}@${IP2}"
INSTANCE3_HOST="${INSTANCE3_USER:-ubuntu}@${IP3}"

echo -e "${PURPLE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo -e "${WHITE}  CLAUDE SETTINGS SYNC TO EC2${NC}"
echo -e "${PURPLE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo

# Verify SSH key exists
if [ ! -f "$SSH_KEY" ]; then
    echo -e "${RED}❌ SSH key not found: $SSH_KEY${NC}"
    exit 1
fi
chmod 600 "$SSH_KEY"

# Function to sync to an instance
sync_to_instance() {
    local instance_num="$1"
    local host="$2"
    local instance_name="fleet-prod-0${instance_num}"

    echo -e "${CYAN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
    echo -e "${WHITE}  Syncing to Instance $instance_num: $instance_name ($host)${NC}"
    echo -e "${CYAN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
    echo

    # Test SSH connection
    echo -e "${BLUE}Testing SSH connection...${NC}"
    if ! ssh -i "$SSH_KEY" -o ConnectTimeout=5 -o BatchMode=yes "$host" "echo 'SSH OK'" >/dev/null 2>&1; then
        echo -e "${RED}❌ SSH connection failed to $host${NC}"
        return 1
    fi
    echo -e "${GREEN}✓ SSH connection successful${NC}"
    echo

    # Sync docs directory (healer, surgeon, operations, secretary, design, social workers)
    echo -e "${YELLOW}Syncing docs/ directory settings...${NC}"
    rsync -avz --progress \
        -e "ssh -i $SSH_KEY" \
        --include='**/.claude/settings.local.json' \
        --include='**/.claude/' \
        --include='*/' \
        --exclude='*' \
        /home/testuser/fleet/docs/ \
        "$host:~/fleet/docs/"
    echo -e "${GREEN}✓ docs/ synced${NC}"
    echo

    # Sync project directories (space-separated list; set SYSNC_ALL_PROJECTS,
    # e.g. "atlas hermes orion", or configure [instances].projects in
    # config/sega.toml and run via the sega CLI)
    echo -e "${YELLOW}Syncing project settings...${NC}"
    if [ -z "${SYSNC_ALL_PROJECTS:-}" ]; then
        echo -e "${YELLOW}  WARNING: SYSNC_ALL_PROJECTS not set; skipping project settings sync${NC}"
    fi
    for project in ${SYSNC_ALL_PROJECTS:-}; do
        if [ -d "/home/testuser/fleet/$project/.claude" ]; then
            echo -e "${BLUE}  Syncing $project...${NC}"
            rsync -avz \
                -e "ssh -i $SSH_KEY" \
                --include='.claude/settings.local.json' \
                --include='.claude/' \
                --exclude='*' \
                "/home/testuser/fleet/$project/" \
                "$host:~/fleet/$project/" 2>&1 | grep -v "sending incremental" || true
            echo -e "${GREEN}  ✓ $project${NC}"
        fi
    done
    echo

    # Sync other key directories
    for dir in dispatcher tracker; do
        if [ -d "/home/testuser/fleet/$dir/.claude" ]; then
            echo -e "${BLUE}Syncing $dir...${NC}"
            rsync -avz --progress \
                -e "ssh -i $SSH_KEY" \
                --include='**/.claude/settings.local.json' \
                --include='**/.claude/' \
                --include='*/' \
                --exclude='*' \
                "/home/testuser/fleet/$dir/" \
                "$host:~/fleet/$dir/"
            echo -e "${GREEN}✓ $dir synced${NC}"
        fi
    done

    echo
    echo -e "${GREEN}✅ Instance $instance_num sync complete!${NC}"
    echo
}

# Sync based on argument
case "$INSTANCE" in
    1)
        sync_to_instance 1 "$INSTANCE1_HOST"
        ;;
    2)
        sync_to_instance 2 "$INSTANCE2_HOST"
        ;;
    all)
        sync_to_instance 1 "$INSTANCE1_HOST"
        echo
        sync_to_instance 2 "$INSTANCE2_HOST"
        echo
        sync_to_instance 3 "$INSTANCE3_HOST"
        ;;
    *)
        echo -e "${RED}Invalid instance: $INSTANCE${NC}"
        echo "Usage: $0 [1|2|3|all]"
        exit 1
        ;;
esac

echo
echo -e "${PURPLE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo -e "${GREEN}  ✅ SYNC COMPLETE${NC}"
echo -e "${PURPLE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo
echo -e "${CYAN}All Claude settings files synced to EC2 instances!${NC}"
echo
