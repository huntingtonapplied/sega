#!/usr/bin/env python3
"""
SEGA Shared Infrastructure Status Check
===============================================================================
Purpose: Verify shared infrastructure directory structure
"""

from pathlib import Path

environments_dir = Path.home() / "workspace" / "environments"

print("🔍 Checking SEGA shared infrastructure...")
print(f"📁 Environments directory: {environments_dir}")
print()

# Check shared directories
shared_dirs = {
    "frontend_shared": ["node_modules", "landing_deps", "product_deps"],
    "ide_shared": ["node_modules", "build_assets", "extensions"],
    "data": ["postgres", "timescale", "redis"],
    "configs": [],
}

for dir_name, subdirs in shared_dirs.items():
    dir_path = environments_dir / dir_name
    status = "✅" if dir_path.exists() else "❌"
    print(f"{status} {dir_name}/")

    if dir_path.exists():
        for subdir in subdirs:
            subdir_path = dir_path / subdir
            substatus = "✅" if subdir_path.exists() else "❌"
            print(f"  {substatus} {subdir}/")
    print()

# Check existing shared environments
existing_shared = ["backend_venv", "engine_venv", "node_modules"]
print("🔧 Existing shared environments:")
for env_name in existing_shared:
    env_path = environments_dir / env_name
    status = "✅" if env_path.exists() else "❌"
    print(f"{status} {env_name}")

print()
print("📋 Summary:")
total_dirs = len(shared_dirs) + len(existing_shared)
existing_count = sum(1 for d in list(shared_dirs.keys()) + existing_shared if (environments_dir / d).exists())
print(f"Directories: {existing_count}/{total_dirs} exist")

if existing_count == total_dirs:
    print("🎉 All shared infrastructure directories are ready!")
else:
    print("⚠️  Some directories are missing - run setup script")
