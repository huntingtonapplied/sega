#!/bin/bash
# Development Node Quick Setup Script
# Usage: curl -sSL https://example.com/scripts/deploy/dev_node_setup.sh | bash

set -e

echo "======================================"
echo "Development Node Setup"
echo "======================================"
echo ""

# Configuration
FLEET_ROOT="${FLEET_ROOT:-$HOME/workspace}"
GIT_ORG="example-org"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

log_info() { echo -e "${GREEN}[INFO]${NC} $1"; }
log_warn() { echo -e "${YELLOW}[WARN]${NC} $1"; }
log_error() { echo -e "${RED}[ERROR]${NC} $1"; }

# Step 1: System Dependencies
log_info "Installing system dependencies..."
sudo apt update
sudo apt install -y git curl wget build-essential python3 python3-pip python3-venv make

# Step 2: Docker Installation
if ! command -v docker &> /dev/null; then
    log_info "Installing Docker..."
    curl -fsSL https://get.docker.com | sudo sh
    sudo usermod -aG docker $USER
    log_warn "Docker installed. You may need to logout/login for group changes to take effect."
else
    log_info "Docker already installed"
fi

# Step 3: Node.js Installation
if ! command -v node &> /dev/null; then
    log_info "Installing Node.js..."
    curl -fsSL https://deb.nodesource.com/setup_20.x | sudo -E bash -
    sudo apt install -y nodejs
else
    log_info "Node.js already installed"
fi

# Step 4: SSH Key Check
if [ ! -f ~/.ssh/id_ed25519 ] && [ ! -f ~/.ssh/id_rsa ]; then
    log_warn "No SSH key found. Generating new key..."
    ssh-keygen -t ed25519 -C "dev@example.com" -f ~/.ssh/id_ed25519 -N ""
    echo ""
    echo "===== IMPORTANT: Add this key to GitLab ====="
    cat ~/.ssh/id_ed25519.pub
    echo "=============================================="
    echo ""
    echo "Press Enter after adding the key to GitLab..."
    read
fi

# Step 5: Clone Workspace Repository
if [ ! -d "$FLEET_ROOT" ]; then
    log_info "Cloning workspace repository..."
    git clone --recurse-submodules git@gitlab.com:${GIT_ORG}/workspace.git "$FLEET_ROOT"
else
    log_info "Workspace repository already exists. Updating..."
    cd "$FLEET_ROOT"
    git pull
    git submodule update --init --recursive
fi

# Step 6: Install SEGA
log_info "Installing SEGA..."
cd "$FLEET_ROOT/sega"

if [ ! -d "venv" ]; then
    python3 -m venv venv
fi

source venv/bin/activate
pip install --upgrade pip
pip install -e .

# Step 7: Create Activation Script
log_info "Creating activation script..."
cat > "$FLEET_ROOT/activate.sh" << 'EOF'
#!/bin/bash
# Development Environment Activation

export FLEET_ROOT="$HOME/workspace"
export FLEET_USER="$USER"
export PATH="$FLEET_ROOT/sega/venv/bin:$PATH"

# Activate SEGA virtual environment
source "$FLEET_ROOT/sega/venv/bin/activate"

# Aliases
alias sega='python -m sega'
alias ws-status='sega local status'
alias ws-up='sega local up'
alias ws-down='sega local down'
alias ws-logs='sega local logs'

echo "Development Environment Activated"
echo "Commands available:"
echo "  sega         - SEGA CLI"
echo "  ws-status    - Check service status"
echo "  ws-up        - Start services"
echo "  ws-down      - Stop services"
echo "  ws-logs      - View logs"
EOF

chmod +x "$FLEET_ROOT/activate.sh"

# Step 8: Create Default Environment File
if [ ! -f "$FLEET_ROOT/.env.development" ]; then
    log_info "Creating default environment file..."
    cat > "$FLEET_ROOT/.env.development" << 'EOF'
# Development Environment Configuration
ENVIRONMENT=development
DEBUG=true
LOG_LEVEL=DEBUG

# Database
POSTGRES_HOST=localhost
POSTGRES_PORT=5432
POSTGRES_DB=app_development
POSTGRES_USER=app_user
POSTGRES_PASSWORD=development_password

# Redis
REDIS_HOST=localhost
REDIS_PORT=6379
REDIS_PASSWORD=development_password

# Metrics
METRICS_ENABLED=true
METRICS_TCP_HOST=localhost
METRICS_TCP_PORT=3308

# External Services (configure as needed)
AUTH0_DOMAIN=example.auth0.com
AUTH0_CLIENT_ID=development_client_id
AUTH0_CLIENT_SECRET=development_secret
EOF
fi

# Step 9: Start Core Services
log_info "Starting core services..."
cd "$FLEET_ROOT"
source activate.sh

# Start databases
sega local up

# Step 10: Quick Health Check
log_info "Running health check..."
docker ps

echo ""
echo "======================================"
echo -e "${GREEN}Setup Complete!${NC}"
echo "======================================"
echo ""
echo "Next steps:"
echo "1. source $FLEET_ROOT/activate.sh"
echo "2. cd $FLEET_ROOT/<project>"
echo "3. make dev-shared"
echo ""
echo "To configure Nginx for external access:"
echo "  sudo apt install nginx"
echo "  sega nginx generate --mode development"
echo ""
echo "For help: sega --help"
