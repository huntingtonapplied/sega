#!/bin/bash
# Live Frontend Route Verification Module
# Sourced by check-frontend-routes.sh when --live, --serve, or --routes flag is used
#
# This module provides:
#   - run_live_verification: Start servers and test routes
#   - run_serve_only: Start servers without testing (keeps running)
#   - run_routes_only: List routes without starting servers

# Inherit colors from parent script
RED="${RED:-\033[0;31m}"
GREEN="${GREEN:-\033[0;32m}"
YELLOW="${YELLOW:-\033[1;33m}"
BLUE="${BLUE:-\033[0;34m}"
NC="${NC:-\033[0m}"

# Inherit ports from parent script
LANDING_PORT="${LANDING_PORT:-3000}"
PRODUCT_PORT="${PRODUCT_PORT:-3001}"
SINGLE_APP_PORT="${SINGLE_APP_PORT:-3010}"

# Detect frontend architecture
detect_architecture() {
    local project_path="$1"

    # Check for dual-app structure
    if [ -d "$project_path/frontend/landing_app" ] && [ -d "$project_path/frontend/product_app" ]; then
        echo "dual-app"
    elif [ -d "$project_path/landing_app" ] && [ -d "$project_path/product_app" ]; then
        echo "dual-app-direct"
    # Check for single-app structure
    elif [ -d "$project_path/frontend/src/app" ]; then
        echo "single-app"
    elif [ -d "$project_path/src/app" ]; then
        echo "single-app-direct"
    else
        echo "unknown"
    fi
}

# Get routes from Next.js app directory
get_nextjs_routes() {
    local app_dir="$1"

    if [ ! -d "$app_dir" ]; then
        return
    fi

    find "$app_dir" -name "page.tsx" -type f 2>/dev/null | while read -r page_file; do
        # Convert file path to route
        local route=$(dirname "$page_file" | sed "s|$app_dir||" | sed 's|/page$||')

        # Strip route groups like (protected), (auth)
        route=$(echo "$route" | sed 's|([^)]*)\/||g' | sed 's|([^)]*)$||')

        # Skip API routes
        if echo "$route" | grep -q '/api/'; then
            continue
        fi

        # Skip dynamic routes for live testing
        if echo "$route" | grep -q '\['; then
            continue
        fi

        # Handle root route
        if [ -z "$route" ]; then
            route="/"
        fi

        echo "$route"
    done | sort -u
}

# Test a single route
test_route() {
    local port="$1"
    local route="$2"
    local dry_run="$3"

    local url="http://localhost:${port}${route}"
    local route_name=$(echo "$route" | sed 's|^/||' | sed 's|/|_|g')
    [ -z "$route_name" ] && route_name="root"
    local tmp_file="/tmp/page_${route_name}_${port}.html"

    if [ "$dry_run" = true ]; then
        echo -e "  ${YELLOW}[DRY-RUN]${NC} Would test: $url"
        return 0
    fi

    # Fetch content and capture both status code and content
    local response=$(curl -s -o "$tmp_file" -w "%{http_code}" --connect-timeout 5 "$url" 2>/dev/null || echo "000")
    local line_count=0
    local byte_count=0

    if [ -f "$tmp_file" ]; then
        line_count=$(wc -l < "$tmp_file" 2>/dev/null || echo "0")
        byte_count=$(wc -c < "$tmp_file" 2>/dev/null || echo "0")
    fi

    case "$response" in
        200)
            if [ "$line_count" -eq 0 ] || [ "$byte_count" -lt 100 ]; then
                echo -e "  ${YELLOW}⚠️${NC}  $route (200 but ${line_count} lines, ${byte_count} bytes - EMPTY/MINIMAL)"
                return 1
            else
                echo -e "  ${GREEN}✅${NC} $route (200, ${line_count} lines, ${byte_count} bytes)"
                return 0
            fi
            ;;
        301|302|307|308)
            echo -e "  ${YELLOW}↪️${NC}  $route ($response redirect, ${line_count} lines)"
            return 0
            ;;
        000)
            echo -e "  ${RED}❌${NC} $route (connection failed)"
            return 1
            ;;
        *)
            echo -e "  ${RED}❌${NC} $route ($response, ${line_count} lines)"
            return 1
            ;;
    esac
}

# Start Next.js dev server
start_server() {
    local app_dir="$1"
    local port="$2"
    local app_name="$3"
    local dry_run="$4"

    echo -e "${BLUE}Starting $app_name on port $port...${NC}"

    if [ "$dry_run" = true ]; then
        echo -e "${YELLOW}[DRY-RUN] Would start: cd $app_dir && npx next dev -p $port${NC}"
        return 0
    fi

    # Kill any existing process on this port
    pkill -f "next dev -p $port" 2>/dev/null || true
    sleep 1

    cd "$app_dir"
    timeout 120 npx next dev -p "$port" > "/tmp/next_${app_name}_${port}.log" 2>&1 &
    local pid=$!
    echo "$pid" >> /tmp/frontend_route_test_pids

    # Wait for server to be ready
    local max_wait=30
    local waited=0
    while [ $waited -lt $max_wait ]; do
        if curl -s -o /dev/null -w "%{http_code}" "http://localhost:$port" 2>/dev/null | grep -qE "200|307|308"; then
            echo -e "${GREEN}Server ready on port $port${NC}"
            return 0
        fi
        sleep 1
        waited=$((waited + 1))
    done

    echo -e "${YELLOW}Server may still be starting on port $port${NC}"
    return 0
}

# Start server and keep running (for --serve mode)
start_server_foreground() {
    local app_dir="$1"
    local port="$2"
    local app_name="$3"

    echo -e "${BLUE}Starting $app_name on port $port (foreground)...${NC}"
    echo -e "${YELLOW}Press Ctrl+C to stop${NC}"
    echo ""

    cd "$app_dir"
    npx next dev -p "$port"
}

# Cleanup servers
cleanup_servers() {
    echo ""
    echo -e "${BLUE}Cleaning up servers...${NC}"

    if [ -f /tmp/frontend_route_test_pids ]; then
        while read -r pid; do
            kill "$pid" 2>/dev/null || true
        done < /tmp/frontend_route_test_pids
        rm -f /tmp/frontend_route_test_pids
    fi

    # Kill any stray next dev processes we might have started
    pkill -f "next dev -p $LANDING_PORT" 2>/dev/null || true
    pkill -f "next dev -p $PRODUCT_PORT" 2>/dev/null || true
    pkill -f "next dev -p $SINGLE_APP_PORT" 2>/dev/null || true
}

# Get app directories based on architecture
get_app_dirs() {
    local project_path="$1"
    local arch="$2"

    case "$arch" in
        dual-app)
            echo "$project_path/frontend/landing_app" "$project_path/frontend/product_app"
            ;;
        dual-app-direct)
            echo "$project_path/landing_app" "$project_path/product_app"
            ;;
        single-app)
            echo "$project_path/frontend" ""
            ;;
        single-app-direct)
            echo "$project_path" ""
            ;;
    esac
}

# ============================================================================
# run_routes_only: List routes without starting servers
# ============================================================================
run_routes_only() {
    local project_path="$1"
    local app_filter="${2:-both}"

    if [ -z "$project_path" ]; then
        echo -e "${RED}Error: Project path required for --routes mode${NC}"
        return 1
    fi

    project_path=$(realpath "$project_path" 2>/dev/null || echo "$project_path")

    if [ ! -d "$project_path" ]; then
        echo -e "${RED}Error: Directory not found: $project_path${NC}"
        return 1
    fi

    local project_name=$(basename "$(dirname "$project_path")")
    local arch=$(detect_architecture "$project_path")

    echo "======================================================================"
    echo -e "${BLUE}Frontend Route Listing${NC}"
    echo "======================================================================"
    echo "Project: $project_name"
    echo "Path: $project_path"
    echo -e "Architecture: ${BLUE}$arch${NC}"
    echo -e "Filter: ${BLUE}$app_filter${NC}"
    echo ""

    local landing_dir product_dir
    read landing_dir product_dir <<< $(get_app_dirs "$project_path" "$arch")

    local total_routes=0

    # Landing App Routes
    if [[ "$app_filter" == "both" || "$app_filter" == "landing" ]]; then
        if [ -n "$landing_dir" ] && [ -d "$landing_dir" ]; then
            echo -e "${BLUE}=== Landing App Routes (Port $LANDING_PORT) ===${NC}"
            local landing_routes=$(get_nextjs_routes "$landing_dir/src/app")
            if [ -n "$landing_routes" ]; then
                while IFS= read -r route; do
                    [ -z "$route" ] && continue
                    echo "  $route"
                    total_routes=$((total_routes + 1))
                done <<< "$landing_routes"
            else
                echo -e "  ${YELLOW}No routes found${NC}"
            fi
            echo ""
        fi
    fi

    # Product App Routes
    if [[ "$app_filter" == "both" || "$app_filter" == "product" ]]; then
        if [ -n "$product_dir" ] && [ -d "$product_dir" ]; then
            echo -e "${BLUE}=== Product App Routes (Port $PRODUCT_PORT) ===${NC}"
            local product_routes=$(get_nextjs_routes "$product_dir/src/app")
            if [ -n "$product_routes" ]; then
                while IFS= read -r route; do
                    [ -z "$route" ] && continue
                    echo "  $route"
                    total_routes=$((total_routes + 1))
                done <<< "$product_routes"
            else
                echo -e "  ${YELLOW}No routes found${NC}"
            fi
            echo ""
        elif [ "$arch" = "single-app" ] || [ "$arch" = "single-app-direct" ]; then
            echo -e "${BLUE}=== App Routes (Port $SINGLE_APP_PORT) ===${NC}"
            local app_routes=$(get_nextjs_routes "$landing_dir/src/app")
            if [ -n "$app_routes" ]; then
                while IFS= read -r route; do
                    [ -z "$route" ] && continue
                    echo "  $route"
                    total_routes=$((total_routes + 1))
                done <<< "$app_routes"
            else
                echo -e "  ${YELLOW}No routes found${NC}"
            fi
            echo ""
        fi
    fi

    echo "======================================================================"
    echo -e "Total Routes: ${GREEN}$total_routes${NC}"
    echo "======================================================================"
}

# ============================================================================
# run_serve_only: Start servers without testing (keeps running until Ctrl+C)
# ============================================================================
run_serve_only() {
    local project_path="$1"
    local app_filter="${2:-both}"

    if [ -z "$project_path" ]; then
        echo -e "${RED}Error: Project path required for --serve mode${NC}"
        return 1
    fi

    project_path=$(realpath "$project_path" 2>/dev/null || echo "$project_path")

    if [ ! -d "$project_path" ]; then
        echo -e "${RED}Error: Directory not found: $project_path${NC}"
        return 1
    fi

    local project_name=$(basename "$(dirname "$project_path")")
    local arch=$(detect_architecture "$project_path")

    echo "======================================================================"
    echo -e "${BLUE}Frontend Server Mode${NC}"
    echo "======================================================================"
    echo "Project: $project_name"
    echo "Path: $project_path"
    echo -e "Architecture: ${BLUE}$arch${NC}"
    echo -e "Filter: ${BLUE}$app_filter${NC}"
    echo ""

    local landing_dir product_dir
    read landing_dir product_dir <<< $(get_app_dirs "$project_path" "$arch")

    # Setup cleanup trap
    trap cleanup_servers EXIT

    # Initialize PID file
    rm -f /tmp/frontend_route_test_pids
    touch /tmp/frontend_route_test_pids

    case "$arch" in
        dual-app|dual-app-direct)
            if [[ "$app_filter" == "both" ]]; then
                # Start both in background, then wait
                if [ -d "$landing_dir" ]; then
                    start_server "$landing_dir" "$LANDING_PORT" "landing_app" false
                fi
                if [ -d "$product_dir" ]; then
                    start_server "$product_dir" "$PRODUCT_PORT" "product_app" false
                fi
                echo ""
                echo -e "${GREEN}Both servers running. Press Ctrl+C to stop.${NC}"
                echo -e "  Landing: http://localhost:$LANDING_PORT"
                echo -e "  Product: http://localhost:$PRODUCT_PORT"
                echo ""
                # Wait indefinitely
                while true; do sleep 3600; done
            elif [[ "$app_filter" == "landing" ]]; then
                if [ -d "$landing_dir" ]; then
                    start_server_foreground "$landing_dir" "$LANDING_PORT" "landing_app"
                else
                    echo -e "${RED}Landing app not found${NC}"
                    return 1
                fi
            elif [[ "$app_filter" == "product" ]]; then
                if [ -d "$product_dir" ]; then
                    start_server_foreground "$product_dir" "$PRODUCT_PORT" "product_app"
                else
                    echo -e "${RED}Product app not found${NC}"
                    return 1
                fi
            fi
            ;;

        single-app|single-app-direct)
            start_server_foreground "$landing_dir" "$SINGLE_APP_PORT" "frontend"
            ;;

        *)
            echo -e "${RED}Unknown architecture - cannot detect frontend structure${NC}"
            return 1
            ;;
    esac
}

# ============================================================================
# run_live_verification: Start servers and test routes
# ============================================================================
run_live_verification() {
    local project_path="$1"
    local dry_run="$2"
    local app_filter="${3:-both}"

    if [ -z "$project_path" ]; then
        echo -e "${RED}Error: Project path required for --live mode${NC}"
        echo "Usage: check-frontend-routes.sh --live <project_path> [--app landing|product|both] [--dry-run]"
        return 1
    fi

    project_path=$(realpath "$project_path" 2>/dev/null || echo "$project_path")

    if [ ! -d "$project_path" ]; then
        echo -e "${RED}Error: Directory not found: $project_path${NC}"
        return 1
    fi

    # Setup cleanup trap
    trap cleanup_servers EXIT

    # Initialize PID file
    rm -f /tmp/frontend_route_test_pids
    touch /tmp/frontend_route_test_pids

    local project_name=$(basename "$(dirname "$project_path")")
    local iteration=$(basename "$project_path")

    echo "======================================================================"
    echo -e "${BLUE}Frontend Route Live Verification${NC}"
    echo "======================================================================"
    echo "Project: $project_name"
    echo "Path: $project_path"
    echo ""

    local arch=$(detect_architecture "$project_path")
    echo -e "Architecture: ${BLUE}$arch${NC}"
    echo -e "Filter: ${BLUE}$app_filter${NC}"
    echo ""

    local total_routes=0
    local passed_routes=0
    local failed_routes=0

    case "$arch" in
        dual-app)
            echo "======================================================================"
            echo -e "${BLUE}Testing Dual-App Architecture${NC}"
            echo "======================================================================"

            # Landing App
            if [[ "$app_filter" == "both" || "$app_filter" == "landing" ]]; then
                local landing_dir="$project_path/frontend/landing_app"
                if [ -d "$landing_dir" ]; then
                    echo ""
                    echo -e "${BLUE}=== Landing App (Port $LANDING_PORT) ===${NC}"

                    start_server "$landing_dir" "$LANDING_PORT" "landing_app" "$dry_run"
                    [ "$dry_run" != true ] && sleep 3

                    local landing_routes=$(get_nextjs_routes "$landing_dir/src/app")

                    if [ -n "$landing_routes" ]; then
                        echo "Testing routes:"
                        while IFS= read -r route; do
                            [ -z "$route" ] && continue
                            total_routes=$((total_routes + 1))
                            if test_route "$LANDING_PORT" "$route" "$dry_run"; then
                                passed_routes=$((passed_routes + 1))
                            else
                                failed_routes=$((failed_routes + 1))
                            fi
                        done <<< "$landing_routes"
                    else
                        echo -e "${YELLOW}No routes found in landing_app${NC}"
                    fi
                fi
            fi

            # Product App
            if [[ "$app_filter" == "both" || "$app_filter" == "product" ]]; then
                local product_dir="$project_path/frontend/product_app"
                if [ -d "$product_dir" ]; then
                    echo ""
                    echo -e "${BLUE}=== Product App (Port $PRODUCT_PORT) ===${NC}"

                    start_server "$product_dir" "$PRODUCT_PORT" "product_app" "$dry_run"
                    [ "$dry_run" != true ] && sleep 3

                    local product_routes=$(get_nextjs_routes "$product_dir/src/app")

                    if [ -n "$product_routes" ]; then
                        echo "Testing routes:"
                        while IFS= read -r route; do
                            [ -z "$route" ] && continue
                            total_routes=$((total_routes + 1))
                            if test_route "$PRODUCT_PORT" "$route" "$dry_run"; then
                                passed_routes=$((passed_routes + 1))
                            else
                                failed_routes=$((failed_routes + 1))
                            fi
                        done <<< "$product_routes"
                    else
                        echo -e "${YELLOW}No routes found in product_app${NC}"
                    fi
                fi
            fi
            ;;

        dual-app-direct)
            # Same as dual-app but without /frontend prefix
            echo "======================================================================"
            echo -e "${BLUE}Testing Dual-App Architecture (Direct)${NC}"
            echo "======================================================================"

            if [[ "$app_filter" == "both" || "$app_filter" == "landing" ]]; then
                local landing_dir="$project_path/landing_app"
                if [ -d "$landing_dir" ]; then
                    echo ""
                    echo -e "${BLUE}=== Landing App (Port $LANDING_PORT) ===${NC}"

                    start_server "$landing_dir" "$LANDING_PORT" "landing_app" "$dry_run"
                    [ "$dry_run" != true ] && sleep 3

                    local landing_routes=$(get_nextjs_routes "$landing_dir/src/app")

                    if [ -n "$landing_routes" ]; then
                        echo "Testing routes:"
                        while IFS= read -r route; do
                            [ -z "$route" ] && continue
                            total_routes=$((total_routes + 1))
                            if test_route "$LANDING_PORT" "$route" "$dry_run"; then
                                passed_routes=$((passed_routes + 1))
                            else
                                failed_routes=$((failed_routes + 1))
                            fi
                        done <<< "$landing_routes"
                    fi
                fi
            fi

            if [[ "$app_filter" == "both" || "$app_filter" == "product" ]]; then
                local product_dir="$project_path/product_app"
                if [ -d "$product_dir" ]; then
                    echo ""
                    echo -e "${BLUE}=== Product App (Port $PRODUCT_PORT) ===${NC}"

                    start_server "$product_dir" "$PRODUCT_PORT" "product_app" "$dry_run"
                    [ "$dry_run" != true ] && sleep 3

                    local product_routes=$(get_nextjs_routes "$product_dir/src/app")

                    if [ -n "$product_routes" ]; then
                        echo "Testing routes:"
                        while IFS= read -r route; do
                            [ -z "$route" ] && continue
                            total_routes=$((total_routes + 1))
                            if test_route "$PRODUCT_PORT" "$route" "$dry_run"; then
                                passed_routes=$((passed_routes + 1))
                            else
                                failed_routes=$((failed_routes + 1))
                            fi
                        done <<< "$product_routes"
                    fi
                fi
            fi
            ;;

        single-app|single-app-direct)
            echo "======================================================================"
            echo -e "${BLUE}Testing Single-App Architecture${NC}"
            echo "======================================================================"

            local frontend_dir
            local app_dir

            if [ "$arch" = "single-app" ]; then
                frontend_dir="$project_path/frontend"
                app_dir="$frontend_dir/src/app"
            else
                frontend_dir="$project_path"
                app_dir="$project_path/src/app"
            fi

            start_server "$frontend_dir" "$SINGLE_APP_PORT" "frontend" "$dry_run"
            [ "$dry_run" != true ] && sleep 5

            local routes=$(get_nextjs_routes "$app_dir")

            if [ -n "$routes" ]; then
                echo "Testing routes:"
                while IFS= read -r route; do
                    [ -z "$route" ] && continue
                    total_routes=$((total_routes + 1))
                    if test_route "$SINGLE_APP_PORT" "$route" "$dry_run"; then
                        passed_routes=$((passed_routes + 1))
                    else
                        failed_routes=$((failed_routes + 1))
                    fi
                done <<< "$routes"
            else
                echo -e "${YELLOW}No routes found${NC}"
            fi
            ;;

        *)
            echo -e "${RED}Unknown architecture - cannot detect frontend structure${NC}"
            echo "Expected one of:"
            echo "  - <path>/frontend/landing_app + product_app (dual-app)"
            echo "  - <path>/landing_app + product_app (dual-app-direct)"
            echo "  - <path>/frontend/src/app (single-app)"
            echo "  - <path>/src/app (single-app-direct)"
            return 1
            ;;
    esac

    # Summary
    echo ""
    echo "======================================================================"
    echo -e "${BLUE}SUMMARY${NC}"
    echo "======================================================================"
    echo "Total Routes Tested: $total_routes"
    echo -e "Passed: ${GREEN}$passed_routes${NC}"
    echo -e "Failed: ${RED}$failed_routes${NC}"

    if [ $failed_routes -eq 0 ] && [ $total_routes -gt 0 ]; then
        echo ""
        echo -e "${GREEN}✅ All routes verified successfully${NC}"
        return 0
    elif [ $failed_routes -gt 0 ]; then
        echo ""
        echo -e "${RED}❌ Some routes failed verification${NC}"
        return 1
    else
        echo ""
        echo -e "${YELLOW}⚠️  No routes tested${NC}"
        return 0
    fi
}
