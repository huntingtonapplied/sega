#!/bin/bash
# =============================================================================
# EC2 Instance Health Check Script
# =============================================================================
# Performs comprehensive health survey of FLEET projects on EC2 instances.
# Part of SEGA system utilities.
#
# Usage: ./ec2-health-check.sh [OPTIONS]
#   -i, --instance <1|2>   Instance number (default: 2)
#   -p, --project <name>   Check specific project only
#   -q, --quick            Quick check (skip port survey)
#   -j, --json             Output as JSON
#   -h, --help             Show this help
#
# Authoritative Sources:
#   - Ports: /docs/standards/infrastructure/PORT_ALLOCATION_STANDARDS.md
#   - Domains: /docs/architecture/infrastructure/dns/FLEET_DOMAIN_REGISTRY.md
#   - Procedure: /docs/guides/procedures/PROJECT_HEALTH_CHECK_PROCEDURE.md
#
# =============================================================================

set -e

# Configuration
# SSH key: set SSH_KEY, or configure [instances] in config/sega.toml.
SSH_KEY="${SSH_KEY:-}"
INSTANCE=2
PROJECT=""
QUICK=false
JSON_OUTPUT=false

# Phase toggles (all enabled by default)
SKIP_PORTS=false
SKIP_DOCKER=false
SKIP_NGINX=false
SKIP_HEALTH=false
SKIP_SSL=false

# Instance configurations
# Set SYSMON_INSTANCE<N>_IP / SYSMON_INSTANCE<N>_PROJECTS (space-separated),
# or configure [instances] in config/sega.toml (injected via the sega CLI).
declare -A INSTANCE_IPS=(
    [1]="${SYSMON_INSTANCE1_IP:-}"
    [2]="${SYSMON_INSTANCE2_IP:-}"
    [3]="${SYSMON_INSTANCE3_IP:-}"
)

declare -A INSTANCE_PROJECTS=(
    [1]="${SYSMON_INSTANCE1_PROJECTS:-}"
    [2]="${SYSMON_INSTANCE2_PROJECTS:-}"
    [3]="${SYSMON_INSTANCE3_PROJECTS:-}"
)

# Parse arguments
while [[ $# -gt 0 ]]; do
    case $1 in
        -i|--instance)
            INSTANCE="$2"
            shift 2
            ;;
        -p|--project)
            PROJECT="$2"
            shift 2
            ;;
        -q|--quick)
            QUICK=true
            shift
            ;;
        -j|--json)
            JSON_OUTPUT=true
            shift
            ;;
        --skip-ports)
            SKIP_PORTS=true
            shift
            ;;
        --skip-docker)
            SKIP_DOCKER=true
            shift
            ;;
        --skip-nginx)
            SKIP_NGINX=true
            shift
            ;;
        --skip-health)
            SKIP_HEALTH=true
            shift
            ;;
        --skip-ssl)
            SKIP_SSL=true
            shift
            ;;
        --only-ports)
            SKIP_DOCKER=true; SKIP_NGINX=true; SKIP_HEALTH=true; SKIP_SSL=true
            shift
            ;;
        --only-docker)
            SKIP_PORTS=true; SKIP_NGINX=true; SKIP_HEALTH=true; SKIP_SSL=true
            shift
            ;;
        --only-health)
            SKIP_PORTS=true; SKIP_DOCKER=true; SKIP_NGINX=true; SKIP_SSL=true
            shift
            ;;
        --only-ssl)
            SKIP_PORTS=true; SKIP_DOCKER=true; SKIP_NGINX=true; SKIP_HEALTH=true
            shift
            ;;
        -h|--help)
            echo "EC2 Instance Health Check"
            echo ""
            echo "Usage: $0 [OPTIONS]"
            echo ""
            echo "Options:"
            echo "  -i, --instance <1|2|3> Instance number (default: 2)"
            echo "  -p, --project <name>   Check specific project only"
            echo "  -q, --quick            Quick check (skip port survey)"
            echo "  -j, --json             Output as JSON"
            echo "  -h, --help             Show this help"
            echo ""
            echo "Phase Control:"
            echo "  --skip-ports           Skip port survey"
            echo "  --skip-docker          Skip Docker container check"
            echo "  --skip-nginx           Skip Nginx status check"
            echo "  --skip-health          Skip service health check"
            echo "  --skip-ssl             Skip SSL certificate check"
            echo ""
            echo "Single Phase:"
            echo "  --only-ports           Run only port survey"
            echo "  --only-docker          Run only Docker check"
            echo "  --only-health          Run only service health check"
            echo "  --only-ssl             Run only SSL certificate check"
            echo ""
            echo "Instance 1 (${INSTANCE_IPS[1]}): ${INSTANCE_PROJECTS[1]}"
            echo "Instance 2 (${INSTANCE_IPS[2]}): ${INSTANCE_PROJECTS[2]}"
            echo "Instance 3 (${INSTANCE_IPS[3]}): ${INSTANCE_PROJECTS[3]}"
            exit 0
            ;;
        *)
            echo "Unknown option: $1"
            exit 1
            ;;
    esac
done

# Validate instance
if [[ ! "${INSTANCE_IPS[$INSTANCE]+exists}" ]]; then
    echo "Error: Invalid instance number. Use 1, 2, or 3."
    exit 1
fi

IP="${INSTANCE_IPS[$INSTANCE]}"
PROJECTS="${INSTANCE_PROJECTS[$INSTANCE]}"

if [[ -z "$IP" ]]; then
    echo "Error: Instance $INSTANCE IP not configured."
    echo "Set SYSMON_INSTANCE${INSTANCE}_IP or configure [instances] in config/sega.toml."
    exit 1
fi

# Check SSH key exists
if [[ -z "$SSH_KEY" ]]; then
    echo "Error: SSH key not configured."
    echo "Set SSH_KEY or configure [instances] in config/sega.toml."
    exit 1
fi
if [[ ! -f "$SSH_KEY" ]]; then
    echo "Error: SSH key not found at $SSH_KEY"
    echo "Set SSH_KEY environment variable to override."
    exit 1
fi

# Helper function for SSH commands
ssh_cmd() {
    ssh -i "$SSH_KEY" -o ConnectTimeout=10 -o StrictHostKeyChecking=no "ubuntu@$IP" "$@" 2>/dev/null
}

# Header
if [[ "$JSON_OUTPUT" != true ]]; then
    echo "=========================================="
    echo "Health Check: Instance $INSTANCE ($IP)"
    echo "=========================================="
    echo "Timestamp: $(date -u +"%Y-%m-%dT%H:%M:%SZ")"
    echo "Projects: $PROJECTS"
fi

# Phase 1: Port Survey
if [[ "$SKIP_PORTS" != true && "$QUICK" != true ]]; then
    if [[ "$JSON_OUTPUT" != true ]]; then
        echo ""
        echo "--- Phase 1: Port Survey ---"
    fi
    ssh_cmd "ss -tlnp | grep LISTEN | sort -t: -k2 -n" || echo "Failed to get port survey"
fi

# Phase 2: Docker Container Status
if [[ "$SKIP_DOCKER" != true ]]; then
    if [[ "$JSON_OUTPUT" != true ]]; then
        echo ""
        echo "--- Phase 2: Docker Containers ---"
    fi
    DOCKER_STATUS=$(ssh_cmd "docker ps --format 'table {{.Names}}\t{{.Status}}\t{{.Ports}}' | sort" 2>/dev/null || echo "Failed to get Docker status")
    if [[ "$JSON_OUTPUT" != true ]]; then
        echo "$DOCKER_STATUS"
    fi
fi

# Phase 3: Nginx Status
if [[ "$SKIP_NGINX" != true ]]; then
    if [[ "$JSON_OUTPUT" != true ]]; then
        echo ""
        echo "--- Phase 3: Nginx Status ---"
    fi
    NGINX_STATUS=$(ssh_cmd "sudo nginx -t 2>&1" || echo "Nginx check failed")
    if [[ "$JSON_OUTPUT" != true ]]; then
        if echo "$NGINX_STATUS" | grep -q "syntax is ok"; then
            echo "Nginx: OK (config valid)"
        else
            echo "Nginx: ERROR"
            echo "$NGINX_STATUS"
        fi
    fi
fi

# Phase 4: Service Health Check (via SSH)
# Note: Direct `sega health --host <IP>` requires open ports (blocked by EC2 security groups)
# Instead, we run health checks via SSH to access localhost on the instance

if [[ "$SKIP_HEALTH" != true ]]; then
if [[ "$JSON_OUTPUT" != true ]]; then
    echo ""
    echo "--- Phase 4: Service Health (via SSH) ---"
fi

# Project port lookup.
# Ports follow the standard allocation formulas (api = 8000 + project_id,
# frontend = 3000 + project_id). Provide project ids via HEALTH_PROJECT_IDS
# as space-separated "project:id" pairs, e.g.:
#   HEALTH_PROJECT_IDS="atlas:0 hermes:1 orion:2"
# Unknown projects resolve to port 0 (skipped).
get_project_id() {
    local project="$1" pair
    for pair in ${HEALTH_PROJECT_IDS:-}; do
        if [[ "${pair%%:*}" == "$project" ]]; then
            echo "${pair##*:}"
            return
        fi
    done
    echo ""
}

get_api_port() {
    local id
    id=$(get_project_id "$1")
    if [[ -n "$id" ]]; then echo $((8000 + id)); else echo 0; fi
}

get_frontend_port() {
    local id
    id=$(get_project_id "$1")
    if [[ -n "$id" ]]; then echo $((3000 + id)); else echo 0; fi
}

HEALTHY_COUNT=0
UNHEALTHY_COUNT=0

for proj in $PROJECTS; do
    API_PORT=$(get_api_port "$proj")
    FE_PORT=$(get_frontend_port "$proj")

    if [[ $API_PORT -gt 0 ]]; then
        # Check backend API
        API_RESULT=$(ssh_cmd "curl -s -o /dev/null -w '%{http_code}' --max-time 5 http://127.0.0.1:$API_PORT/health" 2>/dev/null || echo "000")

        # Check frontend
        FE_RESULT=$(ssh_cmd "curl -s -o /dev/null -w '%{http_code}' --max-time 3 http://127.0.0.1:$FE_PORT" 2>/dev/null || echo "000")

        if [[ "$JSON_OUTPUT" != true ]]; then
            # Format output
            if [[ "$API_RESULT" == "200" ]]; then
                API_STATUS="[OK]"
                HEALTHY_COUNT=$((HEALTHY_COUNT + 1))
            else
                API_STATUS="[FAIL:$API_RESULT]"
                UNHEALTHY_COUNT=$((UNHEALTHY_COUNT + 1))
            fi

            if [[ "$FE_RESULT" == "200" || "$FE_RESULT" == "307" || "$FE_RESULT" == "308" ]]; then
                FE_STATUS="[OK]"
            elif [[ "$FE_RESULT" == "000" ]]; then
                FE_STATUS="[DOWN]"
            else
                FE_STATUS="[FAIL:$FE_RESULT]"
            fi

            printf "%-20s API:%-12s Frontend:%-12s\n" "$proj" "$API_STATUS" "$FE_STATUS"
        fi
    fi
done

if [[ "$JSON_OUTPUT" != true ]]; then
    echo ""
    echo "Summary: $HEALTHY_COUNT healthy APIs, $UNHEALTHY_COUNT unhealthy"
fi
fi  # End SKIP_HEALTH check

# Phase 5: SSL Certificate Status
if [[ "$SKIP_SSL" != true ]]; then
    if [[ "$JSON_OUTPUT" != true ]]; then
        echo ""
        echo "--- Phase 5: SSL Certificates ---"
    fi

    SSL_CERTS=$(ssh_cmd "sudo certbot certificates 2>/dev/null | grep -E 'Certificate Name:|Expiry Date:' | paste - -" 2>/dev/null || echo "")

    if [[ -n "$SSL_CERTS" && "$JSON_OUTPUT" != true ]]; then
        echo "$SSL_CERTS" | while read line; do
            CERT_NAME=$(echo "$line" | sed 's/.*Certificate Name: \([^ ]*\).*/\1/')
            EXPIRY=$(echo "$line" | sed 's/.*Expiry Date: \([^(]*\).*/\1/' | xargs)

            # Check if expiring soon (within 30 days)
            if [[ -n "$EXPIRY" ]]; then
                EXPIRY_EPOCH=$(date -d "$EXPIRY" +%s 2>/dev/null || echo "0")
                NOW_EPOCH=$(date +%s)
                DAYS_LEFT=$(( (EXPIRY_EPOCH - NOW_EPOCH) / 86400 ))

                if [[ $DAYS_LEFT -lt 0 ]]; then
                    STATUS="[EXPIRED]"
                elif [[ $DAYS_LEFT -lt 7 ]]; then
                    STATUS="[CRITICAL:${DAYS_LEFT}d]"
                elif [[ $DAYS_LEFT -lt 30 ]]; then
                    STATUS="[WARNING:${DAYS_LEFT}d]"
                else
                    STATUS="[OK:${DAYS_LEFT}d]"
                fi

                printf "%-30s %s\n" "$CERT_NAME" "$STATUS"
            fi
        done
    elif [[ "$JSON_OUTPUT" != true ]]; then
        echo "No certificates found or certbot not installed"
    fi
fi  # End SKIP_SSL check

# Summary
if [[ "$JSON_OUTPUT" != true ]]; then
    echo ""
    echo "=========================================="
    echo "Health check complete."
    echo "For detailed procedure: /docs/guides/procedures/PROJECT_HEALTH_CHECK_PROCEDURE.md"
fi
