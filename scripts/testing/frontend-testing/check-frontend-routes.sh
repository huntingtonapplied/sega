#!/bin/bash
# Frontend Route Analysis & Live Verification
# Extracts, validates, and optionally live-tests Next.js routes
#
# Supports:
#   - Single-app architecture (iteration1)
#   - Dual-app architecture (iteration2/uix_split): landing_app + product_app
#   - Main project paths ($FLEET_ROOT/$project/frontend)
#   - Staging paths ($FLEET_ROOT/design/integration_staging/projects/$project/iteration2)
#
# Usage:
#   Static Analysis:
#     ./check-frontend-routes.sh                           # Analyze all projects
#     ./check-frontend-routes.sh atlas                     # Analyze single project
#     ./check-frontend-routes.sh atlas http://localhost:3000  # With health check
#
#   Route Listing (no servers):
#     ./check-frontend-routes.sh --routes <path>                # List all routes
#     ./check-frontend-routes.sh --routes <path> --app landing  # Landing routes only
#     ./check-frontend-routes.sh --routes <path> --app product  # Product routes only
#
#   Serve Only (start servers, no testing):
#     ./check-frontend-routes.sh --serve <path>                 # Start both apps
#     ./check-frontend-routes.sh --serve <path> --app landing   # Landing only (port 3000)
#     ./check-frontend-routes.sh --serve <path> --app product   # Product only (port 3001)
#
#   Live Testing (start servers + test routes):
#     ./check-frontend-routes.sh --live <path>                  # Test both apps
#     ./check-frontend-routes.sh --live <path> --app landing    # Test landing only
#     ./check-frontend-routes.sh --live <path> --app product    # Test product only
#     ./check-frontend-routes.sh --live <path> --dry-run        # Preview what will be tested
#
#   Port Configuration:
#     --landing-port <port>   # Set landing app port (default: 3000)
#     --product-port <port>   # Set product app port (default: 3001)
#
# Examples:
#   ./check-frontend-routes.sh --routes ~/workspace/design/integration_staging/projects/atlas/iteration2
#   ./check-frontend-routes.sh --serve ~/workspace/design/integration_staging/projects/hermes/iteration2 --app landing
#   ./check-frontend-routes.sh --live ~/workspace/design/integration_staging/projects/orion/iteration2 --app product
#   ./check-frontend-routes.sh --serve <path> --landing-port 4000 --product-port 4001

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

# Default ports for live testing
LANDING_PORT=3000
PRODUCT_PORT=3001
SINGLE_APP_PORT=3010

# Parse arguments
MODE=""
DRY_RUN=false
PROJECT_PATH=""
APP_FILTER="both"  # landing, product, or both

while [[ $# -gt 0 ]]; do
    case $1 in
        --live)
            MODE="live"
            PROJECT_PATH="$2"
            shift 2
            ;;
        --serve)
            MODE="serve"
            PROJECT_PATH="$2"
            shift 2
            ;;
        --routes)
            MODE="routes"
            PROJECT_PATH="$2"
            shift 2
            ;;
        --app)
            APP_FILTER="$2"
            if [[ "$APP_FILTER" != "landing" && "$APP_FILTER" != "product" && "$APP_FILTER" != "both" ]]; then
                echo -e "${RED}Error: --app must be 'landing', 'product', or 'both'${NC}"
                exit 1
            fi
            shift 2
            ;;
        --landing-port)
            LANDING_PORT="$2"
            shift 2
            ;;
        --product-port)
            PRODUCT_PORT="$2"
            shift 2
            ;;
        --dry-run)
            DRY_RUN=true
            shift
            ;;
        -h|--help)
            head -50 "$0" | tail -45
            exit 0
            ;;
        *)
            if [ -z "$PROJECTS" ]; then
                PROJECTS="$1"
            else
                BASE_URL="$1"
            fi
            shift
            ;;
    esac
done

# Export variables for live module
export LANDING_PORT PRODUCT_PORT SINGLE_APP_PORT APP_FILTER

# If live, serve, or routes mode, run appropriate function and exit
if [ -n "$MODE" ]; then
    source "$(dirname "$0")/check-frontend-routes-live.sh"

    case "$MODE" in
        live)
            run_live_verification "$PROJECT_PATH" "$DRY_RUN" "$APP_FILTER"
            ;;
        serve)
            run_serve_only "$PROJECT_PATH" "$APP_FILTER"
            ;;
        routes)
            run_routes_only "$PROJECT_PATH" "$APP_FILTER"
            ;;
    esac
    exit $?
fi

# Workspace root containing project checkouts
FLEET_ROOT="${FLEET_ROOT:-$HOME/workspace}"

# Default projects list for analysis mode
if [ -z "$PROJECTS" ]; then
    PROJECTS="atlas hermes orion"
fi

# Optional: base URL for health checks
BASE_URL="${BASE_URL:-}"

echo "# Frontend Route Analysis Report"
echo "Date: $(date)"
echo "Purpose: List all frontend routes across managed projects"
echo ""

echo "| Project | Landing Routes | Product Routes | Total | Status |"
echo "|---------|----------------|----------------|-------|--------|"

for project in $PROJECTS; do
    frontend_path="$FLEET_ROOT/$project/frontend"

    if [ -d "$frontend_path" ]; then
        echo -n "| $project | "

        # Count landing_app routes (uix_split)
        if [ -d "$frontend_path/landing_app/src/app" ]; then
            landing_count=$(find "$frontend_path/landing_app/src/app" -name "page.tsx" 2>/dev/null | wc -l)
        else
            landing_count=0
        fi
        echo -n "$landing_count | "

        # Count product_app routes (uix_split)
        if [ -d "$frontend_path/product_app/src/app" ]; then
            product_count=$(find "$frontend_path/product_app/src/app" -name "page.tsx" 2>/dev/null | wc -l)
        # Fallback to single app structure
        elif [ -d "$frontend_path/src/app" ]; then
            product_count=$(find "$frontend_path/src/app" -name "page.tsx" 2>/dev/null | wc -l)
        else
            product_count=0
        fi
        echo -n "$product_count | "

        total=$((landing_count + product_count))
        echo -n "$total | "

        if [ $total -eq 0 ]; then
            echo "NO ROUTES |"
        elif [ $total -lt 10 ]; then
            echo "MINIMAL |"
        elif [ $total -lt 50 ]; then
            echo "STANDARD |"
        else
            echo "FULL |"
        fi
    else
        echo "| $project | - | - | - | NO FRONTEND |"
    fi
done

echo ""
echo "## Route Details"
echo ""

for project in $PROJECTS; do
    frontend_path="$FLEET_ROOT/$project/frontend"

    if [ -d "$frontend_path" ]; then
        echo "### $project"
        echo ""

        # Landing routes
        if [ -d "$frontend_path/landing_app/src/app" ]; then
            echo "**Landing App Routes:**"
            find "$frontend_path/landing_app/src/app" -name "page.tsx" 2>/dev/null | \
                sed "s|$frontend_path/landing_app/src/app||" | \
                sed 's|/page.tsx||' | \
                sed 's|([^)]*)\/||g' | \
                sed 's|\[\.\.\.([^]]*)\]|*|g' | \
                sed 's|\[\([^]]*\)\]|:\1|g' | \
                sed 's|^$|/|' | \
                sort | \
                while read route; do echo "- $route"; done
            echo ""
        fi

        # Product routes
        if [ -d "$frontend_path/product_app/src/app" ]; then
            echo "**Product App Routes:**"
            find "$frontend_path/product_app/src/app" -name "page.tsx" 2>/dev/null | \
                sed "s|$frontend_path/product_app/src/app||" | \
                sed 's|/page.tsx||' | \
                sed 's|([^)]*)\/||g' | \
                sed 's|\[\.\.\.([^]]*)\]|*|g' | \
                sed 's|\[\([^]]*\)\]|:\1|g' | \
                sed 's|^$|/|' | \
                sort | \
                while read route; do echo "- $route"; done
            echo ""
        elif [ -d "$frontend_path/src/app" ]; then
            echo "**App Routes (single app):**"
            find "$frontend_path/src/app" -name "page.tsx" 2>/dev/null | \
                sed "s|$frontend_path/src/app||" | \
                sed 's|/page.tsx||' | \
                sed 's|([^)]*)\/||g' | \
                sed 's|\[\.\.\.([^]]*)\]|*|g' | \
                sed 's|\[\([^]]*\)\]|:\1|g' | \
                sed 's|^$|/|' | \
                sort | \
                while read route; do echo "- $route"; done
            echo ""
        fi
    fi
done

# routeConfig validation - check sidebar routes match actual pages
echo "## routeConfig Validation"
echo ""
echo "Checking sidebar routes against actual pages..."
echo ""

for project in $PROJECTS; do
    frontend_path="$FLEET_ROOT/$project/frontend"
    route_config="$frontend_path/product_app/src/@crema/core/AppRoutes/routeConfig.tsx"

    # Also check staging location
    staging_path="$FLEET_ROOT/design/integration_staging/projects/$project/iteration2/frontend"
    staging_route_config="$staging_path/product_app/src/@crema/core/AppRoutes/routeConfig.tsx"

    # Use staging if it exists, otherwise main
    if [ -f "$staging_route_config" ]; then
        route_config="$staging_route_config"
        app_path="$staging_path/product_app/src/app"
    elif [ -f "$route_config" ]; then
        app_path="$frontend_path/product_app/src/app"
    else
        continue
    fi

    if [ -f "$route_config" ]; then
        echo "### $project"

        # Extract URLs from routeConfig
        config_urls=$(grep -oP "url:\s*['\"]\\K[^'\"]+(?=['\"])" "$route_config" 2>/dev/null | sort -u)

        orphan_count=0
        valid_count=0

        for url in $config_urls; do
            # Convert URL to possible page paths
            route_path="${url#/}"  # Remove leading slash

            # Check various possible locations
            found=false
            for check_path in \
                "$app_path/(protected)/$route_path/page.tsx" \
                "$app_path/(auth)/$route_path/page.tsx" \
                "$app_path/$route_path/page.tsx"; do
                if [ -f "$check_path" ]; then
                    found=true
                    break
                fi
            done

            # Check for dynamic route parents (e.g., /apps/mail/inbox -> /apps/mail/[folder])
            if [ "$found" = false ]; then
                parent_path=$(dirname "$route_path")
                if [ -d "$app_path/(protected)/$parent_path" ]; then
                    dynamic_check=$(find "$app_path/(protected)/$parent_path" -maxdepth 1 -type d -name '\[*\]' 2>/dev/null | head -1)
                    if [ -n "$dynamic_check" ] && [ -f "$dynamic_check/page.tsx" ]; then
                        found=true
                    fi
                fi
            fi

            if [ "$found" = true ]; then
                echo "- [OK] $url"
                valid_count=$((valid_count + 1))
            else
                echo "- [ORPHAN] $url - NO PAGE FOUND"
                orphan_count=$((orphan_count + 1))
            fi
        done

        echo ""
        if [ $orphan_count -gt 0 ]; then
            echo "**WARNING: $orphan_count orphaned routes in routeConfig!**"
            echo "Fix: Remove these routes from routeConfig.tsx"
        else
            echo "All $valid_count routes valid."
        fi
        echo ""
    fi
done

# Health check section (if BASE_URL provided)
if [ -n "$BASE_URL" ]; then
    echo "## Health Check Results"
    echo ""
    echo "Base URL: $BASE_URL"
    echo ""

    for project in $PROJECTS; do
        frontend_path="$FLEET_ROOT/$project/frontend"

        if [ -d "$frontend_path/product_app/src/app" ]; then
            echo "### $project"
            find "$frontend_path/product_app/src/app" -name "page.tsx" 2>/dev/null | \
                sed "s|$frontend_path/product_app/src/app||" | \
                sed 's|/page.tsx||' | \
                sed 's|([^)]*)\/||g' | \
                sed 's|^$|/|' | \
                sort -u | \
                while read route; do
                    # Skip dynamic routes
                    if echo "$route" | grep -q '\['; then
                        echo "- SKIP $route (dynamic)"
                    else
                        code=$(curl -s -o /dev/null -w "%{http_code}" --connect-timeout 2 "${BASE_URL}${route}" 2>/dev/null || echo "ERR")
                        echo "- $code $route"
                    fi
                done
            echo ""
        fi
    done
fi

echo "## Summary"
echo ""
echo "**Route Categories:**"
echo "- NO ROUTES: No page.tsx files found"
echo "- MINIMAL: 1-9 routes (utility apps)"
echo "- STANDARD: 10-49 routes (typical apps)"
echo "- FULL: 50+ routes (full template)"
