#!/bin/bash
# Sync Instance After Git History Cleanup
# Run this on Instance 1 and Instance 2 after force pushing cleaned history from Local
# This script performs a hard reset to match the cleaned remote history

set -e

echo "=========================================="
echo "Git History Cleanup - Instance Sync"
echo "=========================================="
echo ""

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
NC='\033[0m' # No Color

# Step 1: Hard reset main repo
echo -e "${CYAN}Step 1: Hard reset main repo${NC}"
cd ~/fleet
git fetch origin
git reset --hard origin/main
echo -e "${GREEN}✓ Main repo reset complete${NC}"
echo ""

# Step 2: Reset ALL submodules
echo -e "${CYAN}Step 2: Reset all submodules${NC}"
git submodule foreach 'git fetch origin && git reset --hard origin/main'
echo -e "${GREEN}✓ All submodules reset complete${NC}"
echo ""

# Step 3: Update submodule registrations
echo -e "${CYAN}Step 3: Update submodule registrations${NC}"
git submodule update --init --recursive
echo -e "${GREEN}✓ Submodule registrations updated${NC}"
echo ""

# Step 4: Clean any leftover files
echo -e "${CYAN}Step 4: Clean leftover files${NC}"
git clean -fd
git submodule foreach 'git clean -fd'
echo -e "${GREEN}✓ Cleanup complete${NC}"
echo ""

# Step 5: Verify sizes and status
echo -e "${CYAN}Step 5: Verify repository state${NC}"
echo ""
echo "Main repo .git size:"
du -sh .git
echo ""
echo "Total repo size:"
du -sh .
echo ""
echo "Git status:"
git status
echo ""

# Verify submodule count
SUBMODULE_COUNT=$(git submodule status | wc -l)
echo -e "Submodules initialized: ${GREEN}${SUBMODULE_COUNT}${NC}"
echo ""

echo -e "${GREEN}=========================================="
echo "Sync Complete!"
echo "==========================================${NC}"
echo ""
echo -e "${YELLOW}NOTE: All 4 systems (Local, I1, I2, I3) are now in sync.${NC}"
echo -e "${YELLOW}No bulk-stash-pull-pop-push needed - history is already aligned.${NC}"
echo ""
echo "To verify sync across systems, compare:"
echo "  git rev-parse HEAD"
echo "  git submodule status"
