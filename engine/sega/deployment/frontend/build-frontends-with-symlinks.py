#!/usr/bin/env python3
"""
Symlinked Frontend Builder for Instance 1
Uses shared node_modules from ~/fleet/environments/node_modules/
Each app symlinks to shared dependencies
"""

import json
import subprocess
import sys
import time
from pathlib import Path
from datetime import datetime

CONFIG_FILE = Path.home() / "fleet" / "sega" / "config" / "instance1-frontend-builds.json"
LOG_FILE = Path("/tmp") / "instance1-builds.log"
SHARED_NODE_MODULES = Path.home() / "fleet" / "environments" / "node_modules"

def log(message):
    """Log to both console and file"""
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    log_line = f"[{timestamp}] {message}"
    print(log_line)
    with open(LOG_FILE, "a") as f:
        f.write(log_line + "\n")

def run_command(cmd, cwd=None, timeout=900):
    """Run shell command and return success status"""
    try:
        result = subprocess.run(
            cmd,
            shell=True,
            cwd=cwd,
            capture_output=True,
            text=True,
            timeout=timeout
        )
        return result.returncode == 0, result.stdout, result.stderr
    except subprocess.TimeoutExpired:
        return False, "", f"Command timed out after {timeout}s"
    except Exception as e:
        return False, "", str(e)

def check_disk_space():
    """Check available disk space"""
    success, stdout, _ = run_command("df -h /home/ubuntu | tail -1")
    if success:
        parts = stdout.split()
        if len(parts) >= 5:
            log(f"Disk usage: {parts[4]} used, {parts[3]} available")
            return parts[3]
    return "unknown"

def build_app(project_name, app_config):
    """Build a single frontend app using shared node_modules symlink"""
    app_name = app_config["name"]
    app_path = app_config["path"]
    port = app_config["port"]
    
    log(f"\n{'='*60}")
    log(f"Building: {project_name}/{app_name}")
    log(f"Port: {port}")
    log(f"Domain: {app_config['domain']}")
    log(f"{'='*60}")
    
    app_dir = Path.home() / "fleet" / project_name / app_path
    
    if not app_dir.exists():
        log(f"❌ ERROR: Directory not found: {app_dir}")
        return False
    
    # Step 1: Create symlink to shared node_modules
    log("Step 1/3: Setting up shared node_modules symlink...")
    node_modules_link = app_dir / "node_modules"
    
    # Remove existing node_modules (file, directory, or symlink)
    if node_modules_link.exists() or node_modules_link.is_symlink():
        if node_modules_link.is_symlink():
            log(f"  Removing existing symlink...")
            node_modules_link.unlink()
        else:
            log(f"  Removing existing node_modules directory...")
            success, _, err = run_command(f"rm -rf {node_modules_link}")
            if not success:
                log(f"❌ Failed to remove node_modules: {err}")
                return False
    
    # Create symlink
    success, _, err = run_command(f"ln -s {SHARED_NODE_MODULES} {node_modules_link}")
    if not success:
        log(f"❌ Failed to create symlink: {err}")
        return False
    
    # Verify symlink and next binary
    if not (node_modules_link / ".bin" / "next").exists():
        log(f"❌ ERROR: next binary not found in symlinked node_modules")
        return False
    
    log("  ✓ Symlink created and verified")
    
    # Step 2: Verify next.config
    log("Step 2/3: Verifying next.config...")
    next_config_files = list(app_dir.glob("next.config.*"))
    if not next_config_files:
        log(f"❌ No next.config file found in {app_dir}")
        return False
    
    next_config = next_config_files[0]
    with open(next_config, "r") as f:
        config_content = f.read()
        if "output: 'standalone'" in config_content or "output: isDesktopBuild ? 'export' : 'standalone'" in config_content:
            log("  ✓ Config has output: 'standalone'")
        else:
            log(f"  ⚠️  WARNING: Config may not have standalone output")
    
    # Step 3: Run build
    log("Step 3/3: Running npm run build...")
    log("  (This may take 2-5 minutes...)")
    
    start_time = time.time()
    success, stdout, stderr = run_command("npm run build", cwd=app_dir, timeout=900)
    build_time = time.time() - start_time
    
    if not success:
        log(f"❌ BUILD FAILED ({build_time:.1f}s)")
        log(f"STDERR:\n{stderr[-2000:]}")
        if stdout:
            log(f"STDOUT (last 2000 chars):\n{stdout[-2000:]}")
        return False
    
    log(f"✅ BUILD SUCCESS ({build_time:.1f}s)")
    
    # Verify standalone output
    standalone_server = app_dir / ".next" / "standalone" / "server.js"
    if standalone_server.exists():
        log(f"  ✓ Standalone server.js found")
        # Get build size
        success, stdout, _ = run_command(f"du -sh {app_dir / '.next'}")
        if success:
            size = stdout.split()[0]
            log(f"  ✓ Build size: {size}")
    else:
        log(f"  ⚠️  WARNING: standalone/server.js not found")
    
    return True

def main():
    """Main build orchestrator"""
    log("\n" + "="*60)
    log("Instance 1 Symlinked Frontend Builder")
    log("="*60)
    
    # Verify shared node_modules exists
    if not SHARED_NODE_MODULES.exists():
        log(f"❌ ERROR: Shared node_modules not found at {SHARED_NODE_MODULES}")
        log("   Run: cd ~/fleet/environments && npm install --legacy-peer-deps")
        sys.exit(1)
    
    if not (SHARED_NODE_MODULES / ".bin" / "next").exists():
        log(f"❌ ERROR: next binary not found in shared node_modules")
        log("   Shared node_modules may not be properly installed")
        sys.exit(1)
    
    log(f"✓ Shared node_modules verified at {SHARED_NODE_MODULES}")
    
    # Check disk space
    check_disk_space()
    
    # Load config
    if not CONFIG_FILE.exists():
        log(f"❌ Config file not found: {CONFIG_FILE}")
        sys.exit(1)
    
    with open(CONFIG_FILE, "r") as f:
        config = json.load(f)
    
    log(f"Loaded config: {config['instance']} ({config['ip']})")
    log(f"Total apps to build: {config['summary']['total_apps_to_build']}")
    
    # Build queue
    build_queue = []
    for project in config["projects"]:
        for app in project["apps"]:
            if app["build"]:
                build_queue.append({
                    "project": project["name"],
                    "app": app
                })
    
    log(f"\nBuild queue: {len(build_queue)} apps")
    for i, item in enumerate(build_queue, 1):
        log(f"  {i}. {item['project']}/{item['app']['name']}")
    
    # Build sequentially
    results = {
        "success": [],
        "failed": []
    }
    
    for i, item in enumerate(build_queue, 1):
        log(f"\n\n{'#'*60}")
        log(f"# Build {i}/{len(build_queue)}")
        log(f"{'#'*60}")
        
        success = build_app(item["project"], item["app"])
        
        if success:
            results["success"].append(f"{item['project']}/{item['app']['name']}")
        else:
            results["failed"].append(f"{item['project']}/{item['app']['name']}")
        
        # Check disk space after each build
        check_disk_space()
        
        # Pause between builds to let server breathe
        if i < len(build_queue):
            log("\nPausing 15 seconds before next build...")
            time.sleep(15)
    
    # Summary
    log("\n\n" + "="*60)
    log("BUILD SUMMARY")
    log("="*60)
    log(f"✅ Successful: {len(results['success'])}/{len(build_queue)}")
    for app in results["success"]:
        log(f"  ✓ {app}")
    
    if results["failed"]:
        log(f"\n❌ Failed: {len(results['failed'])}/{len(build_queue)}")
        for app in results["failed"]:
            log(f"  ✗ {app}")
    
    log(f"\nFull log: {LOG_FILE}")
    check_disk_space()
    log("="*60)
    
    return 0 if not results["failed"] else 1

if __name__ == "__main__":
    sys.exit(main())
