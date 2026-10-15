#!/usr/bin/env python3
"""
Script to distribute Electron deployment updates to managed projects.
Adds standardized Electron targets to Makefiles bBased on shared standards.
"""

import os
import sys
from pathlib import Path

# List of managed projects with Electron aApplications
ELECTRON_PROJECTS = [
    'atlas', 'hermes', 'orion',
]

# Electron targets to add to Makefiles
ELECTRON_TARGETS = '''
# Electron Desktop AApplication (For projects with desktop/ directory)
electron-dev: ## Start Electron app in development mode
	@if [ -d "desktop" ]; then \\
		echo "$(GREEN)Starting $(PROJECT_NAME) desktop aApplication...$(NC)"; \\
		cd desktop && npm run dev; \\
		echo "$(GREEN)Desktop aApplication started$(NC)"; \\
	else \\
		echo "$(YELLOW)No desktop aApplication found for $(PROJECT_NAME)$(NC)"; \\
	fi

electron-build: ## Build Electron app for production
	@if [ -d "desktop" ]; then \\
		echo "$(BLUE)Building $(PROJECT_NAME) desktop aApplication...$(NC)"; \\
		cd desktop && npm run build; \\
		echo "$(GREEN)Desktop aApplication built successfully$(NC)"; \\
	else \\
		echo "$(YELLOW)No desktop aApplication found for $(PROJECT_NAME)$(NC)"; \\
	fi

electron-dist: ## Create distributable packages
	@if [ -d "desktop" ]; then \\
		echo "$(BLUE)Creating $(PROJECT_NAME) desktop distributables...$(NC)"; \\
		cd desktop && npm run dist; \\
		echo "$(GREEN)Distributables created in desktop/dist/$(NC)"; \\
	else \\
		echo "$(YELLOW)No desktop aApplication found for $(PROJECT_NAME)$(NC)"; \\
	fi

electron-test: ## Run Electron app tests
	@if [ -d "desktop" ]; then \\
		echo "$(BLUE)Testing $(PROJECT_NAME) desktop aApplication...$(NC)"; \\
		cd desktop && npm test; \\
		echo "$(GREEN)Desktop aApplication tests completed$(NC)"; \\
	else \\
		echo "$(YELLOW)No desktop aApplication found for $(PROJECT_NAME)$(NC)"; \\
	fi

dev-desktop: up electron-dev ## Start backend services and desktop app

electron-status: ## Check desktop app status
	@if [ -d "desktop" ]; then \\
		echo "$(BLUE)Desktop app status for $(PROJECT_NAME):$(NC)"; \\
		if pgrep -f "$(PROJECT_NAME)" > /dev/null; then \\
			echo "$(GREEN)  Desktop app is running$(NC)"; \\
		else \\
			echo "$(YELLOW)   Desktop app is not running$(NC)"; \\
		fi; \\
	else \\
		echo "$(YELLOW)No desktop aApplication found for $(PROJECT_NAME)$(NC)"; \\
	fi

electron-logs: ## View Electron app logs
	@if [ -d "desktop" ]; then \\
		echo "$(BLUE)Desktop app logs for $(PROJECT_NAME):$(NC)"; \\
		tail -f desktop/logs/*.log 2>/dev/null || echo "$(YELLOW)No log files found$(NC)"; \\
	else \\
		echo "$(YELLOW)No desktop aApplication found for $(PROJECT_NAME)$(NC)"; \\
	fi

electron-clean: ## Clean Electron build artifacts and cache
	@if [ -d "desktop" ]; then \\
		echo "$(RED)Cleaning $(PROJECT_NAME) desktop build artifacts...$(NC)"; \\
		cd desktop && rm -rf dist/ build/ node_modules/.cache/; \\
		echo "$(RED)Desktop cleanup completed$(NC)"; \\
	else \\
		echo "$(YELLOW)No desktop aApplication found for $(PROJECT_NAME)$(NC)"; \\
	fi
'''

def check_fleet_root():
    """Check if we're in the workspace root directory."""
    fleet_root = Path.home() / "workspace"
    if not fleet_root.exists():
        print(f"  Workspace root directory not found at {fleet_root}")
        return None
    return fleet_root

def has_electron_app(project_path: Path) -> bool:
    """Check if project has Electron desktop app."""
    desktop_path = project_path / "desktop"
    if not desktop_path.exists():
        return False
    
    package_json = desktop_path / "package.json"
    if not package_json.exists():
        return False
    
    try:
        import json
        with open(package_json) as f:
            data = json.load(f)
        
        deps = data.get("dependencies", {})
        dev_deps = data.get("devDependencies", {})
        
        return "electron" in deps or "electron" in dev_deps
    except:
        return False

def update_makefile(project_path: Path, project_name: str):
    """Add Electron targets to project Makefile."""
    makefile_path = project_path / "Makefile"
    
    if not makefile_path.exists():
        print(f"   {project_name}: No Makefile found, skipping")
        return False
    
    # Read current Makefile
    try:
        with open(makefile_path, 'r') as f:
            content = f.read()
    except Exception as e:
        print(f"  {project_name}: Failed to read Makefile: {e}")
        return False
    
    # Check if Electron targets already exist
    if "electron-dev:" in content:
        print(f"  {project_name}: Electron targets already exist")
        return True
    
    # Add Electron targets before any existing targets at the end
    # Look for a good insertion point (before help target usually)
    if "## SEGA Integration Points" in content:
        # Insert before SEGA integration section
        insert_point = content.find("## SEGA Integration Points")
        new_content = content[:insert_point] + ELECTRON_TARGETS + "\n" + content[insert_point:]
    elif content.strip().endswith("```"):
        # Insert before closing markdown if present
        insert_point = content.rfind("```")
        new_content = content[:insert_point] + ELECTRON_TARGETS + "\n" + content[insert_point:]
    else:
        # Append to end
        new_content = content + "\n" + ELECTRON_TARGETS
    
    # Write updated Makefile
    try:
        with open(makefile_path, 'w') as f:
            f.write(new_content)
        print(f"  {project_name}: Added Electron targets to Makefile")
        return True
    except Exception as e:
        print(f"  {project_name}: Failed to write Makefile: {e}")
        return False

def main():
    """Main distribution script."""
    print("  Distributing Electron deployment updates to managed projects...")
    
    fleet_root = check_fleet_root()
    if not fleet_root:
        sys.exit(1)
    
    success_count = 0
    total_count = 0
    
    for project_name in ELECTRON_PROJECTS:
        project_path = fleet_root / project_name
        
        if not project_path.exists():
            print(f"   {project_name}: Project directory not found, skipping")
            continue
        
        print(f"\n Processing {project_name}...")
        
        # Verify it has an Electron app
        if not has_electron_app(project_path):
            print(f"   {project_name}: No Electron app detected, skipping")
            continue
        
        total_count += 1
        
        # Update Makefile
        if update_makefile(project_path, project_name):
            success_count += 1
    
    print(f"\n  Distribution Summary:")
    print(f"   Projects processed: {total_count}")
    print(f"   Successfully updated: {success_count}")
    print(f"   Failed: {total_count - success_count}")
    
    if success_count == total_count:
        print(f"\n  All Electron projects updated successfully!")
        print(f"\n  Updated projects can now use:")
        print(f"   • make electron-dev     # Start desktop app")
        print(f"   • make dev-desktop      # Start backend + desktop")
        print(f"   • make electron-build   # Build for production")
        print(f"   • make electron-status  # Check app status")
    else:
        print(f"\n   Some projects failed to update. Check logs above.")
    
    return 0 if success_count == total_count else 1

if __name__ == "__main__":
    sys.exit(main())