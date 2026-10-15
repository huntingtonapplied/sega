#!/usr/bin/env python3
"""
Script to distribute SEGA testing integration updates to managed projects.
Updates Makefiles and project documentation with standardized SEGA test targets.
"""

import os
import sys
from pathlib import Path

# List of managed projects to update
FLEET_PROJECTS = [
    'atlas', 'hermes', 'orion',
]

# SEGA test targets to add to Makefiles
SEGA_TEST_TARGETS = '''
# Testing Infrastructure (SEGA-integrated)
test: ## Run all tests via SEGA
	@sega test --project $(PROJECT_NAME)

test-local: ## Run tests in local Docker environment
	@sega test local run --project $(PROJECT_NAME)

test-unit: ## Run unit tests only
	@sega test --project $(PROJECT_NAME) --suite unit

test-integration: ## Run integration tests
	@sega test --project $(PROJECT_NAME) --suite integration

test-coverage: ## Generate test coverage report
	@sega test --project $(PROJECT_NAME) --coverage

test-watch: ## Continuous testing mode
	@sega test --project $(PROJECT_NAME) --watch

# Test environment management
test-up: ## Start test infrastructure
	@sega test local up --project $(PROJECT_NAME)

test-down: ## Stop test infrastructure  
	@sega test local down --project $(PROJECT_NAME)

test-status: ## Show test environment status
	@sega test local status --project $(PROJECT_NAME)

# Legacy testing (fallback)
test-legacy: ## Legacy test execution (direct docker-compose)
	@if [ -f "docker-compose.test.yml" ]; then \\
		docker-compose -f docker-compose.test.yml up --abort-on-container-exit; \\
		docker-compose -f docker-compose.test.yml down; \\
	else \\
		echo "$(YELLOW)No docker-compose.test.yml found$(NC)"; \\
	fi
'''

def check_fleet_root():
    """Check if we're in the workspace root directory."""
    fleet_root = Path.home() / "workspace"
    if not fleet_root.exists():
        print(f"  Workspace root directory not found at {fleet_root}")
        return None
    return fleet_root

def has_testing_infrastructure(project_path: Path) -> dict:
    """Check what testing infrastructure a project has."""
    info = {
        'has_docker_test': (project_path / 'docker-compose.test.yml').exists(),
        'has_tests_dir': (project_path / 'tests').exists(),
        'has_makefile': (project_path / 'Makefile').exists(),
        'has_pytest_config': (project_path / 'pytest.ini').exists(),
        'has_jest_config': any(project_path.glob('jest*.js')) or any(project_path.glob('jest*.json')),
    }
    return info

def update_makefile(project_path: Path, project_name: str):
    """Add SEGA test targets to project Makefile."""
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
    
    # Check if SEGA test targets already exist
    if "sega test --project" in content:
        print(f"  {project_name}: SEGA test targets already exist")
        return True
    
    # Look for existing test targets to replace
    if "test:" in content and "docker-compose" in content:
        # Replace legacy test targets with SEGA integrated ones
        print(f"  {project_name}: Updating legacy test targets with SEGA integration")
        
        # Find and replace the test section
        lines = content.split('\n')
        new_lines = []
        in_test_section = False
        
        for line in lines:
            if line.startswith('test:') or line.startswith('test-'):
                if not in_test_section:
                    # Add SEGA test targets before the first test target
                    new_lines.append(SEGA_TEST_TARGETS.strip())
                    in_test_section = True
                # Skip existing test targets that will be replaced
                continue
            elif in_test_section and line.startswith(('\t', ' ')) and line.strip():
                # Skip test target implementation lines
                continue
            elif in_test_section and line.strip() == '':
                # Skip empty lines in test section
                continue
            elif in_test_section and not line.startswith(('\t', ' ')):
                # End of test section
                in_test_section = False
                new_lines.append(line)
            else:
                new_lines.append(line)
        
        new_content = '\n'.join(new_lines)
    else:
        # Add SEGA test targets at the end
        new_content = content + "\n" + SEGA_TEST_TARGETS
    
    # Write updated Makefile
    try:
        with open(makefile_path, 'w') as f:
            f.write(new_content)
        print(f"  {project_name}: Added SEGA test targets to Makefile")
        return True
    except Exception as e:
        print(f"  {project_name}: Failed to write Makefile: {e}")
        return False

def update_project_context(project_path: Path, project_name: str):
    """Update project context documentation if it exists."""
    context_files = ['context.yaml', 'CLAUDE.md', 'README.md']
    
    for context_file in context_files:
        file_path = project_path / context_file
        if file_path.exists():
            try:
                with open(file_path, 'r') as f:
                    content = f.read()
                
                # Add SEGA testing information if not already present
                if 'sega test' not in content.lower():
                    # Add a brief note about SEGA testing integration
                    sega_note = """
## Testing Integration

This project uses SEGA for unified testing orchestration:
- `make test` - Run all tests via SEGA
- `make test-unit` - Run unit tests only  
- `make test-local` - Run tests in Docker environment
- `sega test --project {}` - Direct SEGA testing

See `docs/standards/TESTING_STANDARDS.md` for complete testing guidelines.
""".format(project_name)
                    
                    new_content = content + sega_note
                    with open(file_path, 'w') as f:
                        f.write(new_content)
                    
                    print(f"  {project_name}: Updated {context_file} with SEGA testing info")
                    break
            except Exception as e:
                print(f"   {project_name}: Could not update {context_file}: {e}")

def main():
    """Main distribution script."""
    print(" Distributing SEGA testing integration to managed projects...")
    
    fleet_root = check_fleet_root()
    if not fleet_root:
        sys.exit(1)
    
    success_count = 0
    total_count = 0
    
    for project_name in FLEET_PROJECTS:
        project_path = fleet_root / project_name
        
        if not project_path.exists():
            print(f"   {project_name}: Project directory not found, skipping")
            continue
        
        print(f"\n  Processing {project_name}...")
        
        # Check testing infrastructure
        test_info = has_testing_infrastructure(project_path)
        
        print(f"   Testing infrastructure:")
        print(f"   • Docker test: {' ' if test_info['has_docker_test'] else ' '}")
        print(f"   • Tests directory: {' ' if test_info['has_tests_dir'] else ' '}")
        print(f"   • Makefile: {' ' if test_info['has_makefile'] else ' '}")
        
        total_count += 1
        
        # Update Makefile
        if update_makefile(project_path, project_name):
            # Update project context
            update_project_context(project_path, project_name)
            success_count += 1
    
    print(f"\n  Distribution Summary:")
    print(f"   Projects processed: {total_count}")
    print(f"   Successfully updated: {success_count}")
    print(f"   Failed: {total_count - success_count}")
    
    if success_count == total_count:
        print(f"\n  All projects updated successfully!")
        print(f"\n  Projects can now use:")
        print(f"   • make test              # SEGA-integrated testing")
        print(f"   • make test-local        # Docker environment testing")
        print(f"   • make test-coverage     # Coverage reporting")
        print(f"   • sega test --project <name>  # Direct SEGA commands")
    else:
        print(f"\n   Some projects failed to update. Check logs above.")
    
    return 0 if success_count == total_count else 1

if __name__ == "__main__":
    sys.exit(main())