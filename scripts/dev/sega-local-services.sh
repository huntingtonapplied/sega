#!/bin/bash
# Copyright 2022-2026 the SEGA authors
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

# ===============================================================
# SEGA SCRIPT - LOCAL SERVICES MANAGER
# ===============================================================
# File: scripts/sega-local-services.sh
# Purpose: Build, start, and manage local services and components
#
# Description: This script provides centralized control for local operations
# including building components, restarting systemd services, and starting software
# instances. It supports various command combinations for flexible local deployment.
#
# Usage: ./sega-local-services.sh [build] [restart_services] [start_components]
# Dependencies: project components, systemd, make, virtual environment
# Environment: workspace installation directory structure
#

set -euo pipefail

# Detect workspace installation directory (override with FLEET_ROOT)
if [ -n "${FLEET_ROOT:-}" ] && [ -d "$FLEET_ROOT" ]; then
    :  # explicit override
elif [ -d "$HOME/workspace" ]; then
    FLEET_ROOT="$HOME/workspace"
else
    echo "Error: workspace installation not found. Run 'sega install detect' first."
    exit 1
fi

# Source SEGA environment if available
if [ -f "$FLEET_ROOT/activate_sega.sh" ]; then
    source "$FLEET_ROOT/activate_sega.sh"
elif [ -f "$FLEET_ROOT/sega/.venv/bin/activate" ]; then
    source "$FLEET_ROOT/sega/.venv/bin/activate"
fi

# Define variables
LOG_DIR="$FLEET_ROOT/logs"
SERVICES_CONFIG_DIR="$FLEET_ROOT/config"

# Ensure logs directory exists
mkdir -p "$LOG_DIR"

# Colors for output
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
RED='\033[0;31m'
NC='\033[0m'

log() { echo -e "${BLUE}[$(date +'%H:%M:%S')]${NC} $1"; }
success() { echo -e "${GREEN}[SUCCESS]${NC} $1"; }
warning() { echo -e "${YELLOW}[WARNING]${NC} $1"; }
error() { echo -e "${RED}[ERROR]${NC} $1" >&2; }

# Display section header
section_header() {
    echo
    echo "=============================================="
    echo "  $1"
    echo "=============================================="
}

# Define functions
build_components() {
    section_header "Building Components"
    export PROTOCOL_BUFFERS_PYTHON_IMPLEMENTATION=python
    
    local build_log="$LOG_DIR/build_$(date +%Y%m%d_%H%M%S).log"
    
    # Build based on detected projects
    if [ -d "$FLEET_ROOT/nexus" ]; then
        log "Building Nexus component..."
        cd "$FLEET_ROOT/nexus" || { error "Failed to navigate to Nexus directory"; exit 1; }
        make install > "$build_log" 2>&1 &
        log "Nexus build started. Check logs at $build_log"
    fi
    
    # Add other component builds as needed
    if [ -d "$FLEET_ROOT/atlas" ]; then
        log "Building Atlas component..."
        cd "$FLEET_ROOT/atlas" || { error "Failed to navigate to Atlas directory"; exit 1; }
        if [ -f "Cargo.toml" ]; then
            cargo build --release >> "$build_log" 2>&1 &
            log "Atlas (Rust) build started"
        fi
    fi
    
    success "Component builds initiated. Check $build_log for progress."
}

restart_services() {
    section_header "Restarting Services"
    
    # Restart managed systemd services
    local services=()
    
    # Detect available services
    if systemctl list-unit-files | grep -q "nexus.service"; then
        services+=("nexus.service")
    fi
    
    if systemctl list-unit-files | grep -q "sega-*.service"; then
        services+=($(systemctl list-unit-files | grep "sega-" | awk '{print $1}'))
    fi
    
    if [ ${#services[@]} -eq 0 ]; then
        warning "No managed systemd services found. Use 'sega install validate' to check installation."
        return 0
    fi
    
    for service in "${services[@]}"; do
        log "Restarting $service..."
        if sudo systemctl restart "$service"; then
            success "Restarted $service"
        else
            error "Failed to restart $service"
        fi
    done
    
    success "Service restart completed."
}

start_components() {
    section_header "Starting Software Components"
    
    local component_log="$LOG_DIR/components_$(date +%Y%m%d_%H%M%S).log"
    
    # Start components based on system type detection
    if [ -f "$HOME/.sega/system_type" ]; then
        local system_type=$(cat "$HOME/.sega/system_type")
        log "Detected system type: $system_type"
        
        case "$system_type" in
            *engine*)
                log "Starting engine components..."
                start_engine_components "$component_log"
                ;;
            *platform*)
                log "Starting platform components..."
                start_platform_components "$component_log"
                ;;
            *server*)
                log "Starting server components..."
                start_server_components "$component_log"
                ;;
            *)
                log "Starting standard components..."
                start_standard_components "$component_log"
                ;;
        esac
    else
        warning "System type not detected. Starting standard components..."
        start_standard_components "$component_log"
    fi
    
    success "Component startup completed. Check $component_log for output."
}

start_engine_components() {
    local logfile="$1"
    
    # Start nexus if available
    local nexus_config="$SERVICES_CONFIG_DIR/nexus.toml"
    if [ -f "$nexus_config" ] && command -v nexus >/dev/null 2>&1; then
        log "Starting nexus engine..."
        nexus -c "$nexus_config" >> "$logfile" 2>&1 &
        success "Nexus engine started"
    fi
}

start_platform_components() {
    local logfile="$1"
    
    # Start platform-specific components
    log "Starting platform services..."
    
    # Use docker-compose if available
    if [ -f "$FLEET_ROOT/platform/docker-compose.yml" ]; then
        cd "$FLEET_ROOT/platform"
        docker compose up -d >> "$logfile" 2>&1
        success "Platform services started via Docker Compose"
    fi
}

start_server_components() {
    local logfile="$1"
    
    # Start server components including monitoring
    start_platform_components "$logfile"
    
    # Additional server-specific components
    log "Starting monitoring components..."
}

start_standard_components() {
    local logfile="$1"
    
    # Start basic components for development systems
    if command -v nexus >/dev/null 2>&1; then
        start_engine_components "$logfile"
    fi
}

show_status() {
    section_header "Services Status"
    
    # Show systemd services status
    log "Systemd Services:"
    systemctl --no-pager status nexus.service 2>/dev/null || echo "  nexus.service: not found"
    
    # Show docker services status
    if command -v docker >/dev/null 2>&1; then
        log "Docker Services:"
        docker ps --format "table {{.Names}}\t{{.Status}}" --filter "name=sega" 2>/dev/null || echo "  No sega docker services found"
    fi
    
    # Show running processes
    log "Managed Processes:"
    ps aux | grep -E "(nexus|sega)" | grep -v grep || echo "  No managed processes found"
}

show_help() {
    cat << EOF
SEGA Local Services Manager

Usage: $0 [COMMAND...]

Commands:
  build              Build project components
  restart_services   Restart systemd services
  start_components   Start software components
  status             Show services status
  help               Show this help message

Examples:
  $0 build                           # Build components
  $0 restart_services start_components  # Restart services and start components
  $0 status                          # Show current status
  $0 build restart_services start_components  # Full restart cycle

Note: This script detects your system type and adapts behavior accordingly.
Use 'sega install validate' to verify your installation.
EOF
}

# Main script logic
perform_build=0
perform_restart_services=0
perform_start_components=0
show_status_flag=0

# Parse arguments
if [ $# -eq 0 ]; then
    show_help
    exit 0
fi

for arg in "$@"; do
    case "$arg" in
        build)
            perform_build=1
            ;;
        restart_services)
            perform_restart_services=1
            ;;
        start_components)
            perform_start_components=1
            ;;
        status)
            show_status_flag=1
            ;;
        help|--help|-h)
            show_help
            exit 0
            ;;
        *)
            error "Unknown command: $arg"
            show_help
            exit 1
            ;;
    esac
done

# Execute based on input arguments
if [ "$perform_build" -eq 1 ]; then
    build_components
fi

if [ "$perform_restart_services" -eq 1 ]; then
    restart_services
fi

if [ "$perform_start_components" -eq 1 ]; then
    start_components
fi

if [ "$show_status_flag" -eq 1 ]; then
    show_status
fi

log "SEGA Local Services Manager completed."