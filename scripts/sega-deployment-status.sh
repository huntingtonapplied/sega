#!/bin/bash
# SEGA Deployment Status - Quick wrapper until full CLI integration
# Usage: ./sega-deployment-status.sh [instance_id]

INSTANCE=${1:-1}

cd "${SEGA_ROOT:-/home/ubuntu/sega}"
python3 scripts/test-deployment-state.py "$INSTANCE"
