#!/bin/bash
# Development Environment Activation Script
# Auto-generated - activates the consolidated workspace virtual environment

echo " Activating development environment..."

# Workspace root (override with FLEET_ROOT if your checkout lives elsewhere)
FLEET_ROOT="${FLEET_ROOT:-$HOME/workspace}"

# Navigate to workspace root and activate consolidated environment
cd "$FLEET_ROOT"
source environments/backend_venv/bin/activate

# Return to project directory
cd - > /dev/null

echo " Development environment active"
echo " Current project: $(basename $(pwd))"
echo " Python: $(which python)"
echo " Pip: $(which pip)"

# Show helpful commands
echo ""
echo " Available commands:"
echo "  python -m pytest          # Run tests"
echo "  python -m black .          # Format code"
echo "  python -m mypy .           # Type checking"
echo "  deactivate                 # Exit environment"
