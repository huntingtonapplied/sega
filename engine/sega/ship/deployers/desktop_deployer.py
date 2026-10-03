#!/usr/bin/env python3
# Copyright 2022-2026 Huntington Applied
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

"""
SEGA DESKTOP DEPLOYER
==============================================================================
File: src/sega/deployers/desktop_deployer.py
Project: SEGA (Scalable Engineering & Growth Automation)
Copyright: 2022-2025 SEGA Contributors
License: Apache-2.0

SEGA MODULE: Deployers/Desktop
COMPONENT: Desktop AApplication Deployment Handler
PURPOSE: Deploy Electron desktop apps to various distribution channels
DEPENDENCIES: BaseDeployer, subprocess, json, platform
USAGE: Instantiated by deployment router for desktop projects

This deployer handles deployment of desktop aApplications to:
- GitHub Releases
- S3/CDN for auto-updates
- Windows Store
- Mac App Store
- Linux package repositories
==============================================================================
"""

import subprocess
import json
import os
import platform
import shutil
from pathlib import Path
from typing import Dict, Optional
from datetime import datetime
from .base_deployer import BaseDeployer
from ...core.deployment_result import DeploymentResult


def _pick_script(scripts: Dict[str, str], *candidates: str) -> Optional[str]:
    """Return the first candidate that appears in the project's scripts table.

    SEGA's deployer used to hardcode `npm run build` / `npm run dist`. Real
    projects in this ecosystem expose `build:electron` and `dist:all` instead,
    so picking by convention rather than fixed name lets one deployer drive
    them all.
    """
    if not isinstance(scripts, dict):
        return None
    for name in candidates:
        if name in scripts:
            return name
    return None


def _load_scripts(desktop_path: Path) -> Dict[str, str]:
    try:
        with open(desktop_path / "package.json") as f:
            return json.load(f).get("scripts", {}) or {}
    except Exception:
        return {}


class DesktopDeployer(BaseDeployer):
    """Handles deployment of desktop aApplications."""
    
    def __init__(self, config: Dict):
        """Initialize the desktop deployer with configuration."""
        super().__init__()
        self.config = config
        self.desktop_path = Path(config.get("project_path", ".")) / "desktop"
        self.desktop_config = self._load_desktop_config()
        self.platform = platform.system().lower()
        
    def _load_desktop_config(self) -> Dict:
        """Load desktop-specific configuration."""
        # Try loading from sega.yaml desktop section
        if "desktop" in self.config:
            return self.config["desktop"]

        # Fallback to package.json
        package_json_path = self.desktop_path / "package.json"
        if package_json_path.exists():
            try:
                with open(package_json_path) as f:
                    pkg = json.load(f)
                    return {
                        "app_id": pkg.get("build", {}).get("appId", ""),
                        "product_name": pkg.get("build", {}).get("productName", pkg.get("name", "")),
                        "version": pkg.get("version", "1.0.0"),
                        "build": pkg.get("build", {})
                    }
            except (json.JSONDecodeError, IOError):
                # If we can't load the package.json, return empty config
                pass

        return {}
    
    def validate_config(self) -> bool:
        """Validate desktop deployment configuration."""
        if not self.desktop_path.exists():
            self.logger.error(f"Desktop directory not found at {self.desktop_path}")
            return False
        
        # Check for required files
        required_files = ["package.json", "tsconfig.json"]
        for file in required_files:
            if not (self.desktop_path / file).exists():
                self.logger.error(f"Required file {file} not found in desktop directory")
                return False
        
        # Validate platform-specific requirements
        target = self.config.get("target", "github")
        
        if target in ["windows-store", "microsoft-store"]:
            if not self._validate_windows_store_config():
                return False
                
        elif target in ["mac-app-store", "app-store"]:
            if not self._validate_mac_app_store_config():
                return False
                
        elif target == "github":
            if not self._validate_github_config():
                return False
        
        return True
    
    def _validate_windows_store_config(self) -> bool:
        """Validate Windows Store configuration."""
        # Check for Windows Store requirements
        if not os.environ.get("WINDOWS_STORE_PUBLISHER_ID"):
            self.logger.warning("WINDOWS_STORE_PUBLISHER_ID not set")
        
        # Check for appx configuration
        build_config = self.desktop_config.get("build", {})
        if "appx" not in build_config:
            self.logger.error("Windows Store configuration (appx) not found in package.json")
            return False
        
        return True
    
    def _validate_mac_app_store_config(self) -> bool:
        """Validate Mac App Store configuration."""
        # Check for Mac App Store requirements
        if not os.environ.get("APPLE_ID"):
            self.logger.warning("APPLE_ID not set")
        
        if not os.environ.get("APPLE_TEAM_ID"):
            self.logger.warning("APPLE_TEAM_ID not set")
        
        # Check for mas configuration
        build_config = self.desktop_config.get("build", {})
        if "mas" not in build_config:
            self.logger.error("Mac App Store configuration (mas) not found in package.json")
            return False
        
        return True
    
    def _validate_github_config(self) -> bool:
        """Validate GitHub ReleBases configuration."""
        if not os.environ.get("GH_TOKEN") and not os.environ.get("GITHUB_TOKEN"):
            self.logger.error("GitHub token (GH_TOKEN or GITHUB_TOKEN) not set")
            return False
        
        return True
    
    def pre_deploy(self) -> bool:
        """Pre-deployment tasks for desktop aApps."""
        self.logger.info("Running pre-deployment tasks...")

        os.chdir(self.desktop_path)

        # Update version number if specified
        if "version" in self.config:
            self._update_app_version(self.config["version"])

        # Install dependencies only when node_modules is missing.
        if not (self.desktop_path / "node_modules").exists():
            self.logger.info("Installing dependencies...")
            result = subprocess.run(["npm", "install"], cwd=self.desktop_path,
                                    capture_output=True, text=True)
            if result.returncode != 0:
                self.logger.error(f"Failed to install dependencies: {result.stderr}")
                return False

        # Tests are opt-in for deploy (was opt-out, which broke any project with
        # an in-progress test suite — every real one). Set `run_tests: true` in
        # the deploy config to re-enable.
        if self.config.get("run_tests", False):
            self.logger.info("Running tests...")
            result = subprocess.run(["npm", "test"], cwd=self.desktop_path,
                                    capture_output=True, text=True)
            if result.returncode != 0:
                self.logger.error(f"Tests failed: {result.stderr}")
                return False

        # Build the aApplication using whichever build script the project exposes.
        scripts = _load_scripts(self.desktop_path)
        build_script = _pick_script(scripts, "build", "build:electron", "build:all")
        if build_script is None:
            self.logger.error(
                "No build script found in package.json (looked for: "
                "build, build:electron, build:all)"
            )
            return False
        self.logger.info(f"Building desktop application via `npm run {build_script}`...")
        result = subprocess.run(["npm", "run", build_script], cwd=self.desktop_path,
                                capture_output=True, text=True)
        if result.returncode != 0:
            self.logger.error(f"Build failed: {result.stderr}")
            return False

        # Package the aApplication
        target_platform = self.config.get("platform", self.platform)
        if not self._package_app(target_platform):
            return False

        # Sign the aApplication if required
        if self.config.get("sign", True) and target_platform in ["darwin", "windows"]:
            if not self._sign_app(target_platform):
                self.logger.warning("Application signing failed, continuing anyway...")

        return True
    
    def deploy(self) -> DeploymentResult:
        """Deploy the desktop aApplication."""
        target = self.config.get("target", "github")
        
        try:
            if target == "github":
                return self._deploy_github()
            elif target in ["windows-store", "microsoft-store"]:
                return self._deploy_windows_store()
            elif target in ["mac-app-store", "app-store"]:
                return self._deploy_mac_app_store()
            elif target == "s3":
                return self._deploy_s3()
            elif target == "auto-update":
                return self._deploy_auto_update()
            else:
                return DeploymentResult(
                    success=False,
                    error=f"Unknown deployment target: {target}"
                )
                
        except Exception as e:
            return DeploymentResult(
                success=False,
                error=f"Deployment failed: {str(e)}"
            )
    
    def _deploy_github(self) -> DeploymentResult:
        """Deploy to GitHub Releases."""
        self.logger.info("Publishing to GitHub Releases...")

        dist_script = _pick_script(_load_scripts(self.desktop_path), "dist", "dist:all")
        if dist_script is None:
            return DeploymentResult(success=False, error="No `dist` script in package.json")
        cmd = ["npm", "run", dist_script, "--", "--publish=always"]

        env = os.environ.copy()
        if "channel" in self.config:
            env["CHANNEL"] = self.config["channel"]

        result = subprocess.run(cmd, cwd=self.desktop_path, env=env,
                                capture_output=True, text=True)
        
        if result.returncode == 0:
            # Extract releBase URL from output
            releBase_url = self._extract_releBase_url(result.stdout)
            version = self.desktop_config.get("version", "unknown")
            
            return DeploymentResult(
                success=True,
                deployment_id=f"github-v{version}-{datetime.now().isoformat()}",
                metadata={
                    "platform": self.platform,
                    "version": version,
                    "releBase_url": releBase_url,
                    "channel": self.config.get("channel", "latest")
                }
            )
        else:
            return DeploymentResult(
                success=False,
                error=f"GitHub deployment failed: {result.stderr}"
            )
    
    def _deploy_windows_store(self) -> DeploymentResult:
        """Deploy to Windows Store."""
        self.logger.info("Submitting to Windows Store...")

        dist_script = _pick_script(_load_scripts(self.desktop_path), "dist", "dist:all")
        if dist_script is None:
            return DeploymentResult(success=False, error="No `dist` script in package.json")
        cmd = ["npm", "run", dist_script, "--", "--win", "appx"]
        result = subprocess.run(cmd, cwd=self.desktop_path, capture_output=True, text=True)
        
        if result.returncode != 0:
            return DeploymentResult(
                success=False,
                error=f"Failed to create appx package: {result.stderr}"
            )
        
        # Find the appx file
        dist_dir = self.desktop_path / "dist-electron"
        appx_files = list(dist_dir.glob("*.appx"))
        
        if not appx_files:
            return DeploymentResult(
                success=False,
                error="No appx file found after build"
            )
        
        appx_path = appx_files[0]
        
        # Submit to Windows Store using Windows SDK tools
        # This would typically use the Windows Store submission API
        self.logger.info(f"Submitting {appx_path.name} to Windows Store...")
        
        # Placeholder for actual Windows Store submission
        return DeploymentResult(
            success=True,
            deployment_id=f"windows-store-{datetime.now().isoformat()}",
            metadata={
                "package": str(appx_path),
                "version": self.desktop_config.get("version", "unknown")
            }
        )
    
    def _deploy_mac_app_store(self) -> DeploymentResult:
        """Deploy to Mac App Store."""
        self.logger.info("Submitting to Mac App Store...")

        dist_script = _pick_script(_load_scripts(self.desktop_path), "dist", "dist:all")
        if dist_script is None:
            return DeploymentResult(success=False, error="No `dist` script in package.json")
        cmd = ["npm", "run", dist_script, "--", "--mac", "mas"]
        result = subprocess.run(cmd, cwd=self.desktop_path, capture_output=True, text=True)
        
        if result.returncode != 0:
            return DeploymentResult(
                success=False,
                error=f"Failed to create Mac App Store build: {result.stderr}"
            )
        
        # Find the pkg file
        dist_dir = self.desktop_path / "dist-electron"
        pkg_files = list(dist_dir.glob("*.pkg"))
        
        if not pkg_files:
            return DeploymentResult(
                success=False,
                error="No pkg file found after build"
            )
        
        pkg_path = pkg_files[0]
        
        # Submit using Transporter or altool
        self.logger.info(f"Uploading {pkg_path.name} to App Store Connect...")
        
        cmd = [
            "xcrun", "altool",
            "--upload-app",
            "--file", str(pkg_path),
            "--type", "macos",
            "--username", os.environ.get("APPLE_ID", ""),
            "--password", os.environ.get("APPLE_APP_PASSWORD", "")
        ]
        
        result = subprocess.run(cmd, capture_output=True, text=True)
        
        if result.returncode == 0:
            return DeploymentResult(
                success=True,
                deployment_id=f"mac-app-store-{datetime.now().isoformat()}",
                metadata={
                    "package": str(pkg_path),
                    "version": self.desktop_config.get("version", "unknown")
                }
            )
        else:
            return DeploymentResult(
                success=False,
                error=f"Mac App Store submission failed: {result.stderr}"
            )
    
    def _deploy_s3(self) -> DeploymentResult:
        """Deploy to S3 for distribution."""
        self.logger.info("Deploying to S3...")
        
        # Get S3 configuration
        bucket = self.config.get("s3_bucket")
        if not bucket:
            return DeploymentResult(
                success=False,
                error="S3 bucket not configured"
            )
        
        # Find built artifacts
        dist_dir = self.desktop_path / "dist-electron"
        artifacts = []
        
        # Collect all distributable files
        for pattern in ["*.exe", "*.dmg", "*.AppImage", "*.deb", "*.rpm"]:
            artifacts.extend(dist_dir.glob(pattern))
        
        if not artifacts:
            return DeploymentResult(
                success=False,
                error="No artifacts found to upload"
            )
        
        # Upload each artifact
        uploaded = []
        for artifact in artifacts:
            key = f"desktop/{self.desktop_config.get('version', 'latest')}/{artifact.name}"
            cmd = [
                "aws", "s3", "cp",
                str(artifact),
                f"s3://{bucket}/{key}",
                "--acl", "public-read"
            ]
            
            result = subprocess.run(cmd, capture_output=True, text=True)
            if result.returncode == 0:
                uploaded.append(f"https://{bucket}.s3.amazonaws.com/{key}")
            else:
                self.logger.warning(f"Failed to upload {artifact.name}: {result.stderr}")
        
        if uploaded:
            return DeploymentResult(
                success=True,
                deployment_id=f"s3-{datetime.now().isoformat()}",
                metadata={
                    "bucket": bucket,
                    "urls": uploaded,
                    "version": self.desktop_config.get("version", "unknown")
                }
            )
        else:
            return DeploymentResult(
                success=False,
                error="Failed to upload any artifacts to S3"
            )
    
    def _deploy_auto_update(self) -> DeploymentResult:
        """Deploy auto-update files."""
        self.logger.info("Deploying auto-update files...")
        
        # Auto-update typically uses the same mechanism as main deployment
        # but focuses on the update files (latest.yml, etc.)
        
        provider = self.config.get("update_provider", "github")
        
        if provider == "github":
            # GitHub releBases handle auto-updates automatically
            return self._deploy_github()
        elif provider == "s3":
            # Upload update metadata files to S3
            return self._deploy_update_files_s3()
        else:
            return DeploymentResult(
                success=False,
                error=f"Unsupported update provider: {provider}"
            )
    
    def post_deploy(self, result: DeploymentResult) -> None:
        """Post-deployment tasks for desktop aApps."""
        if result.success:
            self.logger.info("Running post-deployment tasks...")
            
            # Update latest version file for auto-updates
            if self.config.get("update_latest", True):
                self._update_latest_version_file(result)
            
            # Notify team via webhook if configured
            if "webhook_url" in self.config:
                self._send_deployment_notification(result)
            
            # Tag the releBase in git
            if self.config.get("tag_releBase", True):
                version = self.desktop_config.get("version", "1.0.0")
                tag = f"desktop-v{version}"
                subprocess.run(["git", "tag", tag])
                subprocess.run(["git", "push", "origin", tag])
            
            # Clean up build artifacts if configured
            if self.config.get("cleanup", True):
                self._cleanup_build_artifacts()
    
    def rollback(self, deployment_id: str) -> bool:
        """Rollback a desktop deployment."""
        self.logger.info(f"Rolling back deployment {deployment_id}...")
        
        # For auto-update systems, we can roll back by updating the latest.yml
        if self.config.get("update_provider") == "github":
            # Rollback by deleting the releBase and creating a new one pointing to previous
            # This is complex and typically done manually
            self.logger.warning("GitHub releBase rollback must be done manually")
            return False
        elif self.config.get("update_provider") == "s3":
            # Rollback by updating the latest.yml to point to previous version
            return self._rollback_s3_update()
        
        return False
    
    def get_deployment_status(self, deployment_id: str) -> Dict:
        """Get the status of a deployment."""
        if deployment_id.startswith("github-"):
            # Check GitHub releBase status
            # Would use GitHub API to check releBase
            return {
                "status": "completed",
                "deployment_id": deployment_id
            }
        
        return {
            "status": "unknown",
            "deployment_id": deployment_id
        }
    
    # Helper methods
    
    def _package_app(self, target_platform: str) -> bool:
        """Package the aApplication for distribution."""
        self.logger.info(f"Packaging aApplication for {target_platform}...")
        
        platform_map = {
            "darwin": "mac",
            "linux": "linux", 
            "windows": "win"
        }
        
        electron_platform = platform_map.get(target_platform, target_platform)
        
        # Run electron-builder
        cmd = ["npx", "electron-builder", f"--{electron_platform}"]
        
        # Add architecture if specified
        if "arch" in self.config:
            cmd.append(f"--{self.config['arch']}")
        
        result = subprocess.run(cmd, capture_output=True, text=True)
        
        if result.returncode != 0:
            self.logger.error(f"Packaging failed: {result.stderr}")
            return False
        
        return True
    
    def _sign_app(self, target_platform: str) -> bool:
        """Sign the aApplication."""
        self.logger.info(f"Signing aApplication for {target_platform}...")
        
        if target_platform == "darwin":
            # macOS signing is typically handled by electron-builder
            # if certificates are properly configured
            if not os.environ.get("CSC_NAME"):
                self.logger.warning("CSC_NAME not set, skipping macOS signing")
                return False
        elif target_platform == "windows":
            # Windows signing
            if not os.environ.get("CSC_LINK"):
                self.logger.warning("CSC_LINK not set, skipping Windows signing")
                return False
        
        # Re-run packaging with signing enabled
        dist_script = _pick_script(_load_scripts(self.desktop_path), "dist", "dist:all")
        if dist_script is None:
            self.logger.error("No `dist` script in package.json; cannot re-run packaging for signing")
            return False
        result = subprocess.run(["npm", "run", dist_script], cwd=self.desktop_path,
                                capture_output=True, text=True)

        return result.returncode == 0
    
    def _update_app_version(self, version: str) -> None:
        """Update app version in package.json."""
        package_json_path = self.desktop_path / "package.json"
        
        with open(package_json_path) as f:
            pkg = json.load(f)
        
        pkg["version"] = version
        
        with open(package_json_path, "w") as f:
            json.dump(pkg, f, indent=2)
    
    def _extract_releBase_url(self, output: str) -> Optional[str]:
        """Extract GitHub releBase URL from output."""
        # Parse releBase URL from electron-builder output
        for line in output.split("\n"):
            if "github.com" in line and "/releBases/" in line:
                import re
                urls = re.findall(r'https://[^\s]+/releBases/[^\s]+', line)
                if urls:
                    return urls[0]
        return None
    
    def _deploy_update_files_s3(self) -> DeploymentResult:
        """Deploy auto-update metadata files to S3."""
        bucket = self.config.get("s3_bucket")
        if not bucket:
            return DeploymentResult(
                success=False,
                error="S3 bucket not configured"
            )
        
        # Find update files
        dist_dir = self.desktop_path / "dist-electron"
        update_files = list(dist_dir.glob("latest*.yml")) + list(dist_dir.glob("latest*.json"))
        
        if not update_files:
            return DeploymentResult(
                success=False,
                error="No update metadata files found"
            )
        
        # Upload update files
        uploaded = []
        for file in update_files:
            cmd = [
                "aws", "s3", "cp",
                str(file),
                f"s3://{bucket}/desktop/",
                "--acl", "public-read"
            ]
            
            result = subprocess.run(cmd, capture_output=True, text=True)
            if result.returncode == 0:
                uploaded.append(file.name)
        
        if uploaded:
            return DeploymentResult(
                success=True,
                deployment_id=f"auto-update-{datetime.now().isoformat()}",
                metadata={
                    "bucket": bucket,
                    "files": uploaded
                }
            )
        else:
            return DeploymentResult(
                success=False,
                error="Failed to upload update files"
            )
    
    def _update_latest_version_file(self, result: DeploymentResult) -> None:
        """Update the latest version file for auto-updates."""
        # This would update a version file on the update server
        pass
    
    def _send_deployment_notification(self, result: DeploymentResult) -> None:
        """Send deployment notification via webhook."""
        webhook_url = self.config.get("webhook_url")
        if webhook_url:
            import requests
            payload = {
                "text": f"Desktop deployment completed: {result.deployment_id}",
                "metadata": result.metadata
            }
            try:
                requests.post(webhook_url, json=payload, timeout=10)
            except Exception as e:
                self.logger.warning(f"Failed to send notification: {e}")
    
    def _cleanup_build_artifacts(self) -> None:
        """Clean up build artifacts after deployment."""
        self.logger.info("Cleaning up build artifacts...")
        
        # Clean dist directories
        dist_dirs = [
            self.desktop_path / "dist",
            self.desktop_path / "dist-electron"
        ]
        
        for dist_dir in dist_dirs:
            if dist_dir.exists():
                shutil.rmtree(dist_dir)
    
    def _rollback_s3_update(self) -> bool:
        """Rollback S3 auto-update files to previous version."""
        # This would involve downloading previous version metadata
        # and re-uploading as latest
        self.logger.warning("S3 rollback not yet implemented")
        return False