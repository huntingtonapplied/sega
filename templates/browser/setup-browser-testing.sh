#!/bin/bash
# Setup browser testing for a project
# Usage: ./setup-browser-testing.sh [project-name]

set -e

PROJECT_NAME="${1:-$(basename $(pwd))}"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(pwd)"

echo "Setting up browser testing for project: $PROJECT_NAME"

# Create browser test directory structure
mkdir -p tests/browser/{e2e,visual,accessibility}
mkdir -p tests/browser/results

# Copy configuration templates
echo "Copying configuration templates..."
cp "$SCRIPT_DIR/config.json" tests/browser/
cp "$SCRIPT_DIR/static-validation.config.ts" tests/browser/
cp "$SCRIPT_DIR/dynamic-validation.config.ts" tests/browser/
cp "$SCRIPT_DIR/integration-validation.config.ts" tests/browser/

# Copy test templates
echo "Copying test templates..."
cp "$SCRIPT_DIR/static-validation.spec.js" tests/browser/e2e/
cp "$SCRIPT_DIR/dynamic-validation.spec.js" tests/browser/e2e/
cp "$SCRIPT_DIR/integration-validation.spec.js" tests/browser/e2e/

# Update config with project-specific settings
echo "Updating configuration for $PROJECT_NAME..."

# Get project port from your organization's port allocation standards
case "$PROJECT_NAME" in
    "atlas") PORT="3101" ;;
    "hermes") PORT="3102" ;;
    "orion") PORT="3103" ;;
    *) PORT="3001" ;;
esac

# Update config.json with project-specific port
sed -i.bak "s/localhost:3001/localhost:$PORT/g" tests/browser/config.json
rm tests/browser/config.json.bak

# Install Playwright if not already installed
if ! command -v npx playwright --version &> /dev/null; then
    echo "Installing Playwright..."
    npm install -D @playwright/test
    npx playwright install
fi

# Create example test
cat > tests/browser/e2e/example.spec.js << EOF
const { test, expect } = require('@playwright/test');

test.describe('$PROJECT_NAME Example Tests', () => {
  test('homepage loads', async ({ page }) => {
    await page.goto('/');
    await expect(page).toHaveTitle(/.*$/);
    await expect(page.locator('body')).toBeVisible();
  });
});
EOF

# Add package.json scripts if package.json exists
if [ -f "package.json" ]; then
    echo "Adding browser test scripts to package.json..."
    
    # Check if scripts section exists
    if ! grep -q '"scripts"' package.json; then
        # Add scripts section
        sed -i.bak 's/{/{\n  "scripts": {},/' package.json
    fi
    
    # Add browser test scripts
    node -e "
    const fs = require('fs');
    const pkg = JSON.parse(fs.readFileSync('package.json', 'utf8'));
    
    pkg.scripts = pkg.scripts || {};
    pkg.scripts['test:browser'] = 'sega test browser --project $PROJECT_NAME';
    pkg.scripts['test:browser:headed'] = 'sega test browser --project $PROJECT_NAME --headed';
    pkg.scripts['test:validation'] = 'sega test browser --project $PROJECT_NAME --type validation';
    pkg.scripts['test:browser:debug'] = 'sega test browser --project $PROJECT_NAME --debug';
    
    fs.writeFileSync('package.json', JSON.stringify(pkg, null, 2));
    "
    
    rm -f package.json.bak
fi

# Create .gitignore entries for test artifacts
echo "Adding test artifacts to .gitignore..."
{
    echo ""
    echo "# Browser test artifacts"
    echo "tests/browser/results/"
    echo "test-results/"
    echo "playwright-report/"
} >> .gitignore

echo ""
echo " Browser testing setup complete for $PROJECT_NAME!"
echo ""
echo "Next steps:"
echo "1. Customize tests/browser/config.json for your project"
echo "2. Update test selectors in the config file"
echo "3. Run tests with: sega test browser --project $PROJECT_NAME"
echo "4. Run validation tests with: sega test browser --project $PROJECT_NAME --type validation"
echo ""
echo "Available test commands:"
echo "  npm run test:browser          # Run all browser tests"
echo "  npm run test:browser:headed   # Run with visible browser"
echo "  npm run test:validation       # Run 3-tier validation"
echo "  npm run test:browser:debug    # Run in debug mode"
echo ""