#!/usr/bin/env python3
"""
Merge all frontend dependencies from Instance 1 projects into shared package.json
Scans all projects and their landing_app/product_app/frontend directories
"""

import json
import sys
from pathlib import Path
from datetime import datetime

# Projects whose frontends feed the shared package.json, from the curated
# `[fleet] frontend_merge_projects` config list (this script may run standalone,
# so bootstrap the engine onto sys.path relative to this file).
sys.path.insert(0, str(Path(__file__).resolve().parents[3]))
try:
    from sega.core.config import get_config
    MERGE_PROJECTS = list(get_config().fleet.frontend_merge_projects)
except Exception:
    MERGE_PROJECTS = []

FLEET_ROOT = Path.home() / "fleet"
OUTPUT_FILE = Path.home() / "fleet" / "environments" / "package.json"
BACKUP_FILE = Path.home() / "fleet" / "environments" / f"package.json.backup.{datetime.now().strftime('%Y%m%d_%H%M%S')}"

def log(message):
    """Print with timestamp"""
    print(f"[{datetime.now().strftime('%H:%M:%S')}] {message}")

def find_package_json_files():
    """Find all package.json files in the configured project frontends"""
    package_files = []
    
    for project in MERGE_PROJECTS:
        project_dir = FLEET_ROOT / project
        if not project_dir.exists():
            log(f"⚠️  Project directory not found: {project}")
            continue
        
        # Check different frontend structures
        frontend_paths = [
            project_dir / "frontend" / "landing_app" / "package.json",
            project_dir / "frontend" / "product_app" / "package.json",
            project_dir / "frontend" / "package.json",  # Monolithic frontend layout
        ]
        
        for pkg_path in frontend_paths:
            if pkg_path.exists():
                package_files.append(pkg_path)
                log(f"✓ Found: {project}/{pkg_path.relative_to(project_dir)}")
    
    return package_files

def merge_dependencies(package_files):
    """Merge all dependencies and devDependencies"""
    merged_deps = {}
    merged_dev_deps = {}
    
    source_info = {}  # Track which project each dependency came from
    
    for pkg_file in package_files:
        try:
            with open(pkg_file, 'r') as f:
                pkg_data = json.load(f)
            
            project_name = pkg_file.parts[-4] if "frontend" in pkg_file.parts else "unknown"
            app_name = pkg_file.parts[-2] if "landing_app" in pkg_file.parts or "product_app" in pkg_file.parts else "frontend"
            source = f"{project_name}/{app_name}"
            
            # Merge dependencies
            if "dependencies" in pkg_data:
                for dep, version in pkg_data["dependencies"].items():
                    if dep not in merged_deps:
                        merged_deps[dep] = version
                        source_info[dep] = [source]
                    elif merged_deps[dep] != version:
                        # Version conflict - keep the higher version
                        log(f"  ⚠️  Version conflict for {dep}: {merged_deps[dep]} vs {version} (from {source})")
                        # Simple comparison: keep existing for now
                        source_info[dep].append(f"{source} (conflict)")
                    else:
                        source_info[dep].append(source)
            
            # Merge devDependencies
            if "devDependencies" in pkg_data:
                for dep, version in pkg_data["devDependencies"].items():
                    if dep not in merged_dev_deps:
                        merged_dev_deps[dep] = version
                    elif merged_dev_deps[dep] != version:
                        log(f"  ⚠️  Dev dependency version conflict for {dep}")
        
        except json.JSONDecodeError as e:
            log(f"❌ Error reading {pkg_file}: {e}")
            continue
    
    return merged_deps, merged_dev_deps, source_info

def create_merged_package_json(merged_deps, merged_dev_deps):
    """Create the merged package.json structure"""
    return {
        "name": "fleet-shared-environments",
        "version": "1.0.0",
        "private": True,
        "description": f"Shared node_modules for ALL Instance 1 frontend projects - Merged {datetime.now().strftime('%Y-%m-%d')}",
        "scripts": {
            "install:all": "npm install --legacy-peer-deps",
            "audit": "npm audit",
            "update": "npm update --legacy-peer-deps"
        },
        "dependencies": dict(sorted(merged_deps.items())),
        "devDependencies": dict(sorted(merged_dev_deps.items()))
    }

def main():
    """Main merge process"""
    log("="*60)
    log("FLEET Instance 1 - Frontend Dependency Merger")
    log("="*60)
    
    # Find all package.json files
    log("\nScanning Instance 1 projects for package.json files...")
    package_files = find_package_json_files()
    
    if not package_files:
        log("❌ No package.json files found!")
        sys.exit(1)
    
    log(f"\n✓ Found {len(package_files)} package.json files")
    
    # Merge dependencies
    log("\nMerging dependencies...")
    merged_deps, merged_dev_deps, source_info = merge_dependencies(package_files)
    
    log(f"\n✓ Merged {len(merged_deps)} dependencies")
    log(f"✓ Merged {len(merged_dev_deps)} devDependencies")
    log(f"✓ Total: {len(merged_deps) + len(merged_dev_deps)} packages")
    
    # Show some key dependencies
    log("\nKey dependencies found:")
    key_deps = ["next", "react", "react-dom", "@mui/material", "three", "echarts-for-react"]
    for dep in key_deps:
        if dep in merged_deps:
            log(f"  ✓ {dep}: {merged_deps[dep]}")
            log(f"    Sources: {', '.join(source_info.get(dep, ['unknown'])[:3])}")
    
    # Create merged package.json
    log("\nCreating merged package.json...")
    merged_package = create_merged_package_json(merged_deps, merged_dev_deps)
    
    # Backup existing if it exists
    if OUTPUT_FILE.exists():
        log(f"Backing up existing package.json to {BACKUP_FILE.name}")
        with open(OUTPUT_FILE, 'r') as f:
            existing = f.read()
        with open(BACKUP_FILE, 'w') as f:
            f.write(existing)
    
    # Write merged package.json
    with open(OUTPUT_FILE, 'w') as f:
        json.dump(merged_package, f, indent=2)
        f.write('\n')
    
    log(f"\n✅ Merged package.json written to: {OUTPUT_FILE}")
    log(f"✓ Total dependencies: {len(merged_deps)}")
    log(f"✓ Total devDependencies: {len(merged_dev_deps)}")
    log(f"✓ Grand total: {len(merged_deps) + len(merged_dev_deps)}")
    
    log("\nNext steps:")
    log("1. cd ~/fleet/environments")
    log("2. npm install --legacy-peer-deps")
    log("3. Verify: ls -la node_modules/.bin/next")
    log("="*60)
    
    return 0

if __name__ == "__main__":
    sys.exit(main())
