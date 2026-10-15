#!/bin/bash
# EC2 Quick Deploy Script - Using Git with recursion
# Run this on EC2 after setting up SSH key in GitLab

set -e

# Configuration
FLEET_ROOT="${1:-/opt/workspace}"
BRANCH="${2:-main}"

echo "EC2 Quick Deploy"
echo "===================="
echo "Target: $FLEET_ROOT"
echo "Branch: $BRANCH"
echo ""

# Clone main repo with recursion
echo "Cloning workspace with submodules..."
if [ -d "$FLEET_ROOT" ]; then
    echo "Directory exists. Pulling latest..."
    cd $FLEET_ROOT
    git pull origin $BRANCH
    git submodule update --init --recursive
else
    git clone --recursive --branch $BRANCH git@gitlab.com:example-org/workspace.git $FLEET_ROOT
    cd $FLEET_ROOT
fi

# If not using submodules, clone individual projects
if [ ! -d "$FLEET_ROOT/sega" ]; then
    echo "Cloning individual projects..."
    cd $FLEET_ROOT

    PROJECTS="sega atlas hermes orion"

    for project in $PROJECTS; do
        if [ ! -d "$project" ]; then
            echo "Cloning $project..."
            git clone git@gitlab.com:example-org/$project.git
        else
            echo "Updating $project..."
            cd $project
            git pull origin $BRANCH
            cd ..
        fi
    done
fi

# Install SEGA first
echo "Installing SEGA..."
cd $FLEET_ROOT/sega
python3 -m venv venv
./venv/bin/pip install --upgrade pip
./venv/bin/pip install -e .

# Create activation script
cat > $FLEET_ROOT/activate.sh << 'EOF'
#!/bin/bash
export FLEET_ROOT=/opt/workspace
export PATH=$FLEET_ROOT/sega/venv/bin:$PATH
export FLEET_USER=$USER
export FLEET_VENV=$FLEET_ROOT/environments/shared_venv
export FLEET_NODE_MODULES=$FLEET_ROOT/node_modules
alias sega='$FLEET_ROOT/sega/venv/bin/sega'
echo "Workspace environment activated"
EOF

chmod +x $FLEET_ROOT/activate.sh

echo ""
echo "Deployment complete!"
echo "===================="
echo "Next steps:"
echo "1. source $FLEET_ROOT/activate.sh"
echo "2. sega install detect"
echo "3. sega install target --target server-jellyfish"
echo "4. Deploy individual projects with: sega deploy --project <name>"
echo ""
echo "To update all projects later:"
echo "cd $FLEET_ROOT && git submodule foreach git pull origin main"
