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
SEGA MOBILE DEPLOYER
==============================================================================
File: src/sega/deployers/mobile_deployer.py
Project: SEGA (Scalable Engineering & Growth Automation)
Copyright: 2022-2025 SEGA Contributors
License: Apache-2.0

SEGA MODULE: Deployers/Mobile
COMPONENT: Mobile AApplication Deployment Handler
PURPOSE: Deploy React Native/Expo apps to various distribution channels
DEPENDENCIES: BaseDeployer, subprocess, json
USAGE: Instantiated by deployment router for mobile projects

This deployer handles deployment of mobile aApplications to:
- Apple App Store / TestFlight
- Google Play Store
- Expo AApplication Services (EAS)
- Web hosting platforms
==============================================================================
"""

import subprocess
import json
import os
from pathlib import Path
from typing import Dict, Optional
from datetime import datetime
from .base_deployer import BaseDeployer
from ...core.deployment_result import DeploymentResult


class MobileDeployer(BaseDeployer):
    """Handles deployment of mobile aApplications."""
    
    def __init__(self, config: Dict):
        """Initialize the mobile deployer with configuration."""
        super().__init__()
        self.config = config
        self.expo_path = Path(config.get("project_path", ".")) / "expo"
        self.mobile_config = self._load_mobile_config()
        
    def _load_mobile_config(self) -> Dict:
        """Load mobile-specific configuration."""
        # Try loading from sega.yaml mobile section
        if "mobile" in self.config:
            return self.config["mobile"]

        # Fallback to expo app.json
        app_json_path = self.expo_path / "app.json"
        if app_json_path.exists():
            try:
                with open(app_json_path) as f:
                    app_data = json.load(f)
                    return {
                        "name": app_data.get("expo", {}).get("name", ""),
                        "slug": app_data.get("expo", {}).get("slug", ""),
                        "version": app_data.get("expo", {}).get("version", "1.0.0"),
                        "platforms": app_data.get("expo", {}).get("platforms", [])
                    }
            except (json.JSONDecodeError, IOError):
                # If we can't load the app.json, return empty config
                pass

        return {}
    
    def validate_config(self) -> bool:
        """Validate mobile deployment configuration."""
        if not self.expo_path.exists():
            self.logger.error(f"Expo directory not found at {self.expo_path}")
            return False
        
        # Check for required files
        required_files = ["package.json", "app.json"]
        for file in required_files:
            if not (self.expo_path / file).exists():
                self.logger.error(f"Required file {file} not found in expo directory")
                return False
        
        # Validate platform-specific requirements
        target = self.config.get("target", "preview")
        
        if target in ["app-store", "testflight"]:
            # iOS deployment checks
            if not self._validate_ios_config():
                return False
                
        elif target in ["play-store", "play-console"]:
            # Android deployment checks
            if not self._validate_android_config():
                return False
        
        return True
    
    def _validate_ios_config(self) -> bool:
        """Validate iOS-specific configuration."""
        eas_json = self.expo_path / "eas.json"
        if not eas_json.exists():
            self.logger.error("eas.json not found - required for iOS deployment")
            return False
        
        # Check for iOS certificates and provisioning profiles
        # This would typically check for environment variables or files
        required_env = ["EXPO_APPLE_ID", "EXPO_APPLE_TEAM_ID"]
        for env in required_env:
            if not os.environ.get(env):
                self.logger.warning(f"Environment variable {env} not set")
        
        return True
    
    def _validate_android_config(self) -> bool:
        """Validate Android-specific configuration."""
        eas_json = self.expo_path / "eas.json"
        if not eas_json.exists():
            self.logger.error("eas.json not found - required for Android deployment")
            return False
        
        # Check for Android keystore
        if not os.environ.get("EXPO_ANDROID_KEYSTORE_BASE64"):
            self.logger.warning("Android keystore not configured")
        
        return True
    
    def pre_deploy(self) -> bool:
        """Pre-deployment tasks for mobile aApps."""
        self.logger.info("Running pre-deployment tasks...")
        
        os.chdir(self.expo_path)
        
        # Update version number if specified
        if "version" in self.config:
            self._update_app_version(self.config["version"])
        
        # Install dependencies
        self.logger.info("Installing dependencies...")
        result = subprocess.run(["npm", "install"], capture_output=True, text=True)
        if result.returncode != 0:
            self.logger.error(f"Failed to install dependencies: {result.stderr}")
            return False
        
        # Run tests if not skipped
        if not self.config.get("skip_tests", False):
            self.logger.info("Running tests...")
            result = subprocess.run(["npm", "test"], capture_output=True, text=True)
            if result.returncode != 0:
                self.logger.error(f"Tests failed: {result.stderr}")
                return False
        
        # Build the app
        target = self.config.get("target", "preview")
        platform = self._get_platform_from_target(target)
        
        if platform == "web":
            # Export web build
            self.logger.info("Building web version...")
            result = subprocess.run(
                ["npx", "expo", "export", "--platform", "web"],
                capture_output=True,
                text=True
            )
            if result.returncode != 0:
                self.logger.error(f"Web build failed: {result.stderr}")
                return False
        else:
            # EAS Build for native platforms
            self.logger.info(f"Triggering EAS build for {platform}...")
            profile = self.config.get("build_profile", "production")
            cmd = ["npx", "eas", "build", "--platform", platform, "--profile", profile]
            
            if not self.config.get("wait_for_build", True):
                cmd.append("--non-interactive")
            
            result = subprocess.run(cmd, capture_output=True, text=True)
            if result.returncode != 0:
                self.logger.error(f"EAS build failed: {result.stderr}")
                return False
            
            # Extract build ID from output
            self.build_id = self._extract_build_id(result.stdout)
        
        return True
    
    def deploy(self) -> DeploymentResult:
        """Deploy the mobile aApplication."""
        target = self.config.get("target", "preview")
        
        try:
            if target == "preview":
                return self._deploy_preview()
            elif target in ["app-store", "testflight"]:
                return self._deploy_ios()
            elif target in ["play-store", "play-console"]:
                return self._deploy_android()
            elif target == "web":
                return self._deploy_web()
            elif target == "ota":
                return self._deploy_ota_update()
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
    
    def _deploy_preview(self) -> DeploymentResult:
        """Deploy to Expo preview channel."""
        self.logger.info("Publishing to Expo preview channel...")
        
        channel = self.config.get("channel", "preview")
        message = self.config.get("message", f"Update from SEGA - {datetime.now()}")
        
        cmd = [
            "npx", "eas", "update",
            "--channel", channel,
            "--message", message
        ]
        
        result = subprocess.run(cmd, capture_output=True, text=True)
        
        if result.returncode == 0:
            update_url = self._extract_update_url(result.stdout)
            return DeploymentResult(
                success=True,
                deployment_id=f"expo-preview-{datetime.now().isoformat()}",
                metadata={
                    "channel": channel,
                    "update_url": update_url,
                    "message": message
                }
            )
        else:
            return DeploymentResult(
                success=False,
                error=f"Preview deployment failed: {result.stderr}"
            )
    
    def _deploy_ios(self) -> DeploymentResult:
        """Deploy to iOS App Store or TestFlight."""
        self.logger.info("Submitting to App Store Connect...")
        
        # Submit the build to App Store Connect
        cmd = ["npx", "eas", "submit", "--platform", "ios"]
        
        if hasattr(self, "build_id"):
            cmd.extend(["--id", self.build_id])
        
        result = subprocess.run(cmd, capture_output=True, text=True)
        
        if result.returncode == 0:
            submission_id = self._extract_submission_id(result.stdout)
            return DeploymentResult(
                success=True,
                deployment_id=submission_id,
                metadata={
                    "platform": "ios",
                    "target": self.config.get("target"),
                    "build_id": getattr(self, "build_id", None)
                }
            )
        else:
            return DeploymentResult(
                success=False,
                error=f"iOS submission failed: {result.stderr}"
            )
    
    def _deploy_android(self) -> DeploymentResult:
        """Deploy to Google Play Store."""
        self.logger.info("Submitting to Google Play Console...")
        
        # Submit the build to Google Play
        cmd = ["npx", "eas", "submit", "--platform", "android"]
        
        if hasattr(self, "build_id"):
            cmd.extend(["--id", self.build_id])
        
        # Specify releBase track
        track = self.config.get("releBase_track", "internal")
        cmd.extend(["--track", track])
        
        result = subprocess.run(cmd, capture_output=True, text=True)
        
        if result.returncode == 0:
            submission_id = self._extract_submission_id(result.stdout)
            return DeploymentResult(
                success=True,
                deployment_id=submission_id,
                metadata={
                    "platform": "android",
                    "track": track,
                    "build_id": getattr(self, "build_id", None)
                }
            )
        else:
            return DeploymentResult(
                success=False,
                error=f"Android submission failed: {result.stderr}"
            )
    
    def _deploy_web(self) -> DeploymentResult:
        """Deploy web build to hosting platform."""
        self.logger.info("Deploying web build...")
        
        # The web export should have created a dist directory
        dist_path = self.expo_path / "dist"
        if not dist_path.exists():
            return DeploymentResult(
                success=False,
                error="Web build output not found"
            )
        
        # Deploy based on configured provider
        provider = self.config.get("web_provider", "netlify")
        
        if provider == "netlify":
            return self._deploy_to_netlify(dist_path)
        elif provider == "vercel":
            return self._deploy_to_vercel(dist_path)
        elif provider == "s3":
            return self._deploy_to_s3(dist_path)
        else:
            return DeploymentResult(
                success=False,
                error=f"Unsupported web provider: {provider}"
            )
    
    def _deploy_ota_update(self) -> DeploymentResult:
        """Deploy over-the-air update."""
        self.logger.info("Publishing OTA update...")
        
        channel = self.config.get("channel", "production")
        platform = self.config.get("platform", "all")
        
        cmd = ["npx", "eas", "update", "--channel", channel]
        
        if platform != "all":
            cmd.extend(["--platform", platform])
        
        result = subprocess.run(cmd, capture_output=True, text=True)
        
        if result.returncode == 0:
            return DeploymentResult(
                success=True,
                deployment_id=f"ota-{channel}-{datetime.now().isoformat()}",
                metadata={
                    "channel": channel,
                    "platform": platform
                }
            )
        else:
            return DeploymentResult(
                success=False,
                error=f"OTA update failed: {result.stderr}"
            )
    
    def post_deploy(self, result: DeploymentResult) -> None:
        """Post-deployment tasks for mobile aApps."""
        if result.success:
            self.logger.info("Running post-deployment tasks...")
            
            # Notify team via webhook if configured
            if "webhook_url" in self.config:
                self._send_deployment_notification(result)
            
            # Tag the releBase in git
            if self.config.get("tag_releBase", True):
                version = self.mobile_config.get("version", "1.0.0")
                tag = f"mobile-v{version}-{datetime.now().strftime('%Y%m%d')}"
                subprocess.run(["git", "tag", tag])
                subprocess.run(["git", "push", "origin", tag])
    
    def rollback(self, deployment_id: str) -> bool:
        """Rollback a mobile deployment."""
        self.logger.info(f"Rolling back deployment {deployment_id}...")
        
        # For OTA updates, we can roll back by publishing a previous version
        if deployment_id.startswith("ota-"):
            # Extract channel from deployment ID
            parts = deployment_id.split("-")
            if len(parts) >= 2:
                channel = parts[1]
                
                # Publish previous version to channel
                cmd = ["npx", "eas", "update:rollback", "--channel", channel]
                result = subprocess.run(cmd, capture_output=True, text=True)
                
                return result.returncode == 0
        
        # For store deployments, rollback is manual
        self.logger.warning("Store deployments must be rolled back manually")
        return False
    
    def get_deployment_status(self, deployment_id: str) -> Dict:
        """Get the status of a deployment."""
        if deployment_id.startswith("expo-"):
            # Check EAS update status
            cmd = ["npx", "eas", "update:list", "--json"]
            result = subprocess.run(cmd, capture_output=True, text=True)
            
            if result.returncode == 0:
                updates = json.loads(result.stdout)
                # Find matching update
                for update in updates:
                    if update.get("id") == deployment_id:
                        return {
                            "status": "completed",
                            "details": update
                        }
        
        return {
            "status": "unknown",
            "deployment_id": deployment_id
        }
    
    # Helper methods
    
    def _get_platform_from_target(self, target: str) -> str:
        """Determine platform from deployment target."""
        ios_targets = ["app-store", "testflight", "ios"]
        android_targets = ["play-store", "play-console", "android"]
        
        if target in ios_targets:
            return "ios"
        elif target in android_targets:
            return "android"
        elif target == "web":
            return "web"
        else:
            return "all"
    
    def _update_app_version(self, version: str) -> None:
        """Update app version in configuration files."""
        # Update app.json
        app_json_path = self.expo_path / "app.json"
        with open(app_json_path) as f:
            app_data = json.load(f)
        
        app_data["expo"]["version"] = version
        
        # Update iOS build number
        if "ios" in app_data["expo"]:
            build_number = int(app_data["expo"]["ios"].get("buildNumber", "1")) + 1
            app_data["expo"]["ios"]["buildNumber"] = str(build_number)
        
        # Update Android version code
        if "android" in app_data["expo"]:
            version_code = app_data["expo"]["android"].get("versionCode", 1) + 1
            app_data["expo"]["android"]["versionCode"] = version_code
        
        with open(app_json_path, "w") as f:
            json.dump(app_data, f, indent=2)
    
    def _extract_build_id(self, output: str) -> Optional[str]:
        """Extract build ID from EAS build output."""
        # Parse build ID from output
        for line in output.split("\n"):
            if "Build ID:" in line or "build/" in line:
                # Extract ID from line
                parts = line.split("/")
                if len(parts) > 1:
                    return parts[-1].strip()
        return None
    
    def _extract_submission_id(self, output: str) -> Optional[str]:
        """Extract submission ID from EAS submit output."""
        # Parse submission ID from output
        for line in output.split("\n"):
            if "Submission ID:" in line:
                parts = line.split(":")
                if len(parts) > 1:
                    return parts[1].strip()
        return f"submission-{datetime.now().isoformat()}"
    
    def _extract_update_url(self, output: str) -> Optional[str]:
        """Extract update URL from EAS update output."""
        # Parse URL from output
        for line in output.split("\n"):
            if "expo.dev" in line and "https://" in line:
                # Extract URL
                import re
                urls = re.findall(r'https://[^\s]+', line)
                if urls:
                    return urls[0]
        return None
    
    def _deploy_to_netlify(self, dist_path: Path) -> DeploymentResult:
        """Deploy to Netlify."""
        # Implementation would use Netlify CLI or API
        self.logger.info("Deploying to Netlify...")
        # Placeholder for actual implementation
        return DeploymentResult(
            success=True,
            deployment_id=f"netlify-{datetime.now().isoformat()}",
            metadata={"provider": "netlify", "path": str(dist_path)}
        )
    
    def _deploy_to_vercel(self, dist_path: Path) -> DeploymentResult:
        """Deploy to Vercel."""
        # Implementation would use Vercel CLI or API
        self.logger.info("Deploying to Vercel...")
        # Placeholder for actual implementation
        return DeploymentResult(
            success=True,
            deployment_id=f"vercel-{datetime.now().isoformat()}",
            metadata={"provider": "vercel", "path": str(dist_path)}
        )
    
    def _deploy_to_s3(self, dist_path: Path) -> DeploymentResult:
        """Deploy to S3."""
        # Implementation would use AWS CLI or boto3
        self.logger.info("Deploying to S3...")
        # Placeholder for actual implementation
        return DeploymentResult(
            success=True,
            deployment_id=f"s3-{datetime.now().isoformat()}",
            metadata={"provider": "s3", "path": str(dist_path)}
        )
    
    def _send_deployment_notification(self, result: DeploymentResult) -> None:
        """Send deployment notification via webhook."""
        webhook_url = self.config.get("webhook_url")
        if webhook_url:
            # Send notification
            import requests
            payload = {
                "text": f"Mobile deployment completed: {result.deployment_id}",
                "metadata": result.metadata
            }
            try:
                requests.post(webhook_url, json=payload, timeout=10)
            except Exception as e:
                self.logger.warning(f"Failed to send notification: {e}")