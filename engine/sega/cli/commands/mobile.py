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
SEGA MOBILE DEVELOPMENT COMMAND
==============================================================================
File: src/sega/commands/mobile.py
Project: SEGA (Scalable Engineering & Growth Automation)
Copyright: 2022-2025 SEGA Contributors
License: Apache-2.0

SEGA MODULE: Commands/MobileDevelopment
COMPONENT: Mobile Development CLI Command Group
PURPOSE: Manage mobile app development, testing, and deployment
DEPENDENCIES: click, subprocess, pathlib, ProjectDetector
USAGE: sega mobile [dev|build|test|deploy|preview|analyze]

This command group provides comprehensive mobile development management
for React Native/Expo projects across the FLEET ecosystem.
==============================================================================
"""

import click
import subprocess
import json
import os
from pathlib import Path
from typing import Optional, Dict
from tabulate import tabulate


class MobileManager:
    """Manages mobile development operations for FLEET projects."""
    
    def __init__(self, project_path: Optional[Path] = None):
        self.project_path = project_path or Path.cwd()
        self.expo_path = self.project_path / "expo"
        self.config = self._load_config()
        
    def _load_config(self) -> Dict:
        """Load mobile configuration from sega.yaml or package.json."""
        sega_config = self.project_path / "sega.yaml"
        if sega_config.exists():
            import yaml
            with open(sega_config) as f:
                config = yaml.safe_load(f)
                return config.get("mobile", {})
        
        # Fallback to package.json
        package_json = self.expo_path / "package.json"
        if package_json.exists():
            with open(package_json) as f:
                return json.load(f)
        
        return {}
    
    def _check_dependencies(self) -> bool:
        """Check if required dependencies are installed."""
        checks = {
            "Node.js": ["node", "--version"],
            "npm": ["npm", "--version"],
            "Expo CLI": ["npx", "expo", "--version"]
        }
        
        all_good = True
        for name, cmd in checks.items():
            try:
                result = subprocess.run(cmd, capture_output=True, text=True)
                if result.returncode == 0:
                    click.echo(f" {name}: {result.stdout.strip()}")
                else:
                    click.echo(f" {name}: Not found")
                    all_good = False
            except FileNotFoundError:
                click.echo(f" {name}: Not found")
                all_good = False
        
        return all_good
    
    def start_development(self, platform: Optional[str] = None, clear_cache: bool = False):
        """Start mobile development server."""
        if not self.expo_path.exists():
            click.echo(f"Error: No expo directory found at {self.expo_path}")
            return False
        
        os.chdir(self.expo_path)
        
        # Install dependencies if needed
        if not (self.expo_path / "node_modules").exists():
            click.echo("Installing dependencies...")
            subprocess.run(["npm", "install"], check=True)
        
        # Clear cache if requested
        if clear_cache:
            click.echo("Clearing cache...")
            subprocess.run(["npx", "expo", "start", "--clear"], check=True)
            return True
        
        # Start development server
        cmd = ["npx", "expo", "start"]
        if platform:
            cmd.extend([f"--{platform}"])
        
        click.echo("Starting Expo development server...")
        subprocess.run(cmd, check=True)
        return True
    
    def build_app(self, platform: str, profile: str = "preview", local: bool = False):
        """Build mobile aApplication."""
        if not self.expo_path.exists():
            click.echo(f"Error: No expo directory found at {self.expo_path}")
            return False
        
        os.chdir(self.expo_path)
        
        if local:
            # Local build
            click.echo(f"Building {platform} app locally...")
            if platform == "ios":
                cmd = ["npx", "expo", "run:ios", "--releBase"]
            elif platform == "android":
                cmd = ["npx", "expo", "run:android", "--variant", "releBase"]
            else:
                click.echo(f"Error: Unsupported platform for local build: {platform}")
                return False
        else:
            # EAS Build
            click.echo(f"Building {platform} app with EAS...")
            cmd = ["npx", "eas", "build", "--platform", platform, "--profile", profile]
        
        subprocess.run(cmd, check=True)
        return True
    
    def run_tests(self, coverage: bool = False, watch: bool = False):
        """Run mobile tests."""
        if not self.expo_path.exists():
            click.echo(f"Error: No expo directory found at {self.expo_path}")
            return False
        
        os.chdir(self.expo_path)
        
        cmd = ["npm", "test"]
        if coverage:
            cmd = ["npm", "run", "test:coverage"]
        elif watch:
            cmd = ["npm", "run", "test:watch"]
        
        click.echo("Running mobile tests...")
        subprocess.run(cmd, check=True)
        return True
    
    def deploy_app(self, platform: str, channel: str = "preview"):
        """Deploy mobile aApplication."""
        if not self.expo_path.exists():
            click.echo(f"Error: No expo directory found at {self.expo_path}")
            return False
        
        os.chdir(self.expo_path)
        
        if platform == "web":
            # Web deployment
            click.echo("Building web version...")
            subprocess.run(["npx", "expo", "export", "--platform", "web"], check=True)
            click.echo("Web build ready in dist/ directory")
        else:
            # EAS Update for OTA updates
            click.echo(f"Publishing update to {channel} channel...")
            cmd = ["npx", "eas", "update", "--channel", channel, "--message", "Update from SEGA"]
            subprocess.run(cmd, check=True)
        
        return True
    
    def analyze_bundle(self):
        """Analyze bundle size and dependencies."""
        if not self.expo_path.exists():
            click.echo(f"Error: No expo directory found at {self.expo_path}")
            return False
        
        os.chdir(self.expo_path)
        
        click.echo("Analyzing bundle...")
        subprocess.run(["npx", "expo", "export", "--dump-sourcemap"], check=True)
        
        # Additional analysis can be added here
        click.echo("Bundle analysis complete. Check the output for details.")
        return True
    
    def preview_on_device(self, platform: Optional[str] = None):
        """Preview app on physical device or simulator."""
        if not self.expo_path.exists():
            click.echo(f"Error: No expo directory found at {self.expo_path}")
            return False
        
        os.chdir(self.expo_path)
        
        if platform == "ios":
            click.echo("Opening iOS simulator...")
            subprocess.run(["npx", "expo", "run:ios"], check=True)
        elif platform == "android":
            click.echo("Opening Android emulator...")
            subprocess.run(["npx", "expo", "run:android"], check=True)
        else:
            click.echo("Starting Expo Go preview...")
            subprocess.run(["npx", "expo", "start", "--tunnel"], check=True)
        
        return True


@click.group()
@click.option('--project', '-p', type=click.Path(exists=True), help='Path to project directory')
@click.pass_context
def mobile(ctx, project):
    """Manage mobile aApplication development for FLEET projects.
    
    SEGA provides unified mobile development management for:
    - React Native/Expo development servers
    - iOS and Android builds
    - Mobile-specific testing
    - App store deployment
    - Bundle analysis and optimization
    
    Examples:
        sega mobile dev              # Start development server
        sega mobile build ios        # Build iOS app
        sega mobile test            # Run mobile tests
        sega mobile deploy android  # Deploy to Play Store
    """
    ctx.ensure_object(dict)
    ctx.obj['manager'] = MobileManager(Path(project) if project else None)


@mobile.command()
@click.option('--platform', '-p', type=click.Choice(['ios', 'android', 'web']), help='Target platform')
@click.option('--clear-cache', is_flag=True, help='Clear Metro bundler cache')
@click.pass_context
def dev(ctx, platform, clear_cache):
    """Start mobile development server.
    
    Examples:
        sega mobile dev                    # Start Expo server
        sega mobile dev --platform ios     # Start with iOS simulator
        sega mobile dev --clear-cache      # Clear cache and start
    """
    manager = ctx.obj['manager']
    
    click.echo("Checking mobile development dependencies...")
    if not manager._check_dependencies():
        click.echo("\nPlease install missing dependencies before continuing.")
        return
    
    if manager.start_development(platform, clear_cache):
        click.echo("Development server started successfully")
    else:
        click.echo("Failed to start development server")
        exit(1)


@mobile.command()
@click.argument('platform', type=click.Choice(['ios', 'android', 'web']))
@click.option('--profile', default='preview', help='Build profile to use')
@click.option('--local', is_flag=True, help='Build locally instead of using EAS')
@click.pass_context
def build(ctx, platform, profile, local):
    """Build mobile aApplication for distribution.
    
    Examples:
        sega mobile build ios              # Build iOS with EAS
        sega mobile build android --local  # Build Android locally
        sega mobile build web              # Build web version
    """
    manager = ctx.obj['manager']
    
    if manager.build_app(platform, profile, local):
        click.echo(f"Successfully built {platform} app")
    else:
        click.echo(f"Failed to build {platform} app")
        exit(1)


@mobile.group()
@click.pass_context
def test(ctx):
    """Mobile testing commands (JavaScript and native).
    
    Run JavaScript tests with Jest/Expo or native tests with platform tools.
    
    Examples:
        sega mobile test js                  # Run JavaScript tests
        sega mobile test native              # Run native tests
        sega mobile test devices             # List test devices
        sega mobile test check               # Check test environment
    """
    pass


@test.command('js')
@click.option('--coverage', is_flag=True, help='Generate coverage report')
@click.option('--watch', is_flag=True, help='Run tests in watch mode')
@click.pass_context
def test_js(ctx, coverage, watch):
    """Run JavaScript/React Native tests.
    
    Examples:
        sega mobile test js              # Run all JS tests
        sega mobile test js --coverage   # Run with coverage
        sega mobile test js --watch      # Run in watch mode
    """
    manager = ctx.obj['manager']
    
    if manager.run_tests(coverage, watch):
        click.echo("Tests completed successfully")
    else:
        click.echo("Tests failed")
        exit(1)


@mobile.command()
@click.argument('platform', type=click.Choice(['ios', 'android', 'web']))
@click.option('--channel', default='preview', help='Deployment channel')
@click.pass_context
def deploy(ctx, platform, channel):
    """Deploy mobile aApplication to stores or web.
    
    Examples:
        sega mobile deploy ios           # Deploy to TestFlight
        sega mobile deploy android       # Deploy to Play Store
        sega mobile deploy web          # Deploy web build
    """
    manager = ctx.obj['manager']
    
    if manager.deploy_app(platform, channel):
        click.echo(f"Successfully deployed to {platform}")
    else:
        click.echo(f"Failed to deploy to {platform}")
        exit(1)


@mobile.command()
@click.option('--platform', '-p', type=click.Choice(['ios', 'android']), help='Target platform')
@click.pass_context
def preview(ctx, platform):
    """Preview app on device or simulator.
    
    Examples:
        sega mobile preview              # Start Expo Go preview
        sega mobile preview --platform ios    # Preview on iOS simulator
        sega mobile preview -p android        # Preview on Android emulator
    """
    manager = ctx.obj['manager']
    
    if manager.preview_on_device(platform):
        click.echo("Preview started successfully")
    else:
        click.echo("Failed to start preview")
        exit(1)


@mobile.command()
@click.pass_context
def analyze(ctx):
    """Analyze bundle size and dependencies.
    
    Example:
        sega mobile analyze    # Generate bundle analysis
    """
    manager = ctx.obj['manager']
    
    if manager.analyze_bundle():
        click.echo("Analysis completed successfully")
    else:
        click.echo("Failed to analyze bundle")
        exit(1)


# Native testing commands
try:
    from sega.testing.mobile import (
        MobileTestOrchestrator,
        IOSNativeTestRunner,
        AndroidNativeTestRunner,
        DeviceManager
    )
    NATIVE_TESTING_AVAILABLE = True
except ImportError:
    NATIVE_TESTING_AVAILABLE = False


@test.command('native')
@click.option('--platform', '-p', type=click.Choice(['ios', 'android', 'both']), 
              default='both', help='Target platform')
@click.option('--suite', '-s', type=click.Choice(['unit', 'ui', 'performance', 'all']), 
              default='all', help='Test suite to run')
@click.option('--config', '-c', type=click.Path(exists=True), 
              help='Path to test configuration file')
@click.option('--device', '-d', multiple=True, help='Specific device(s) to test on')
@click.option('--parallel', is_flag=True, help='Run tests in parallel')
@click.option('--coverage', is_flag=True, help='Generate coverage reports')
@click.option('--report', type=click.Choice(['html', 'json', 'junit']), 
              default='html', help='Report format')
@click.option('--output', '-o', type=click.Path(), help='Output path for report')
@click.pass_context
def native(ctx, platform, suite, config, device, parallel, coverage, report, output):
    """Run native mobile tests using platform-specific tools.
    
    This command runs tests using:
    - iOS: xcodebuild and XCTest
    - Android: Gradle and JUnit/Espresso
    
    Examples:
        sega mobile test native                          # Run all tests
        sega mobile test native --platform ios --suite unit   # iOS unit tests
        sega mobile test native --device "iPhone 15 Pro"     # Test on specific device
        sega mobile test native --parallel --coverage        # Parallel with coverage
    """
    if not NATIVE_TESTING_AVAILABLE:
        click.echo("Error: Native testing infrastructure not available.")
        click.echo("Please ensure mobile testing modules are installed.")
        ctx.exit(1)
    
    # Determine config path
    if config:
        config_path = Path(config)
    else:
        # Look for default config files
        config_path = Path.cwd() / 'mobile_test_config.yaml'
        if not config_path.exists():
            config_path = Path.cwd() / 'mobile_test_config.json'
        
        if not config_path.exists():
            click.echo("Warning: No mobile test configuration found. Using defaults.")
            config_path = None
    
    # Create orchestrator
    try:
        orchestrator = MobileTestOrchestrator(config_path)
    except Exception as e:
        click.echo(f"Error: Failed to initialize test orchestrator: {e}", err=True)
        ctx.exit(1)
    
    # Update configuration for coverage if requested
    if coverage and orchestrator.config:
        if 'platforms' in orchestrator.config:
            if 'ios' in orchestrator.config['platforms']:
                orchestrator.config['platforms']['ios']['code_coverage'] = {'enabled': True}
            if 'android' in orchestrator.config['platforms']:
                orchestrator.config['platforms']['android']['coverage'] = {'enabled': True}
    
    click.echo("Running native mobile tests...")
    click.echo(f"Platform: {platform}")
    click.echo(f"Suite: {suite}")
    if device:
        click.echo(f"Devices: {', '.join(device)}")
    click.echo(f"Parallel: {parallel}")
    click.echo(f"Coverage: {coverage}")
    
    # Run tests
    try:
        if device:
            # Run on specific devices
            report_data = orchestrator.run_on_devices(
                test_suite=suite if suite != 'all' else None,
                devices=list(device)
            )
        else:
            # Run based on configuration
            report_data = orchestrator.run_tests(
                platform=platform if platform != 'both' else None,
                suite=suite if suite != 'all' else None,
                parallel=parallel
            )
        
        # Display results
        _display_test_results(report_data)
        
        # Generate report
        if not output:
            output = Path.cwd() / f'mobile_test_report.{report}'
        else:
            output = Path(output)
        
        if report == 'html':
            orchestrator.generate_html_report(report_data, output)
        elif report == 'junit':
            orchestrator.generate_junit_report(report_data, output)
        elif report == 'json':
            with open(output, 'w') as f:
                json.dump(report_data.to_dict(), f, indent=2)
        
        click.echo(f"\nReport saved to: {output}")
        
        # Cleanup
        orchestrator.cleanup()
        
        # Exit with appropriate code
        if report_data.summary['total_failed'] > 0:
            ctx.exit(1)
        
    except Exception as e:
        click.echo(f"Error: Test execution failed: {e}", err=True)
        orchestrator.cleanup()
        ctx.exit(1)


@test.command('devices')
@click.option('--platform', '-p', type=click.Choice(['ios', 'android', 'both']), 
              help='Filter by platform')
@click.option('--available', is_flag=True, help='Show only available devices')
@click.pass_context
def devices(ctx, platform, available):
    """List available test devices and simulators.
    
    Shows iOS simulators and Android emulators/devices that can be used for testing.
    
    Examples:
        sega mobile test devices                    # List all devices
        sega mobile test devices --platform ios     # iOS simulators only
        sega mobile test devices --available        # Only ready devices
    """
    if not NATIVE_TESTING_AVAILABLE:
        click.echo("Error: Native testing infrastructure not available.")
        ctx.exit(1)
    
    device_manager = DeviceManager()
    
    # Get devices
    all_devices = device_manager.list_all_devices(platform)
    
    if available:
        # Filter to available devices
        all_devices = [d for d in all_devices if d.state in ['available', 'booted', 'device']]
    
    if not all_devices:
        click.echo("No devices found.")
        return
    
    # Group by platform
    ios_devices = [d for d in all_devices if d.platform == 'ios']
    android_devices = [d for d in all_devices if d.platform == 'android']
    
    # Display iOS devices
    if ios_devices and platform in [None, 'ios', 'both']:
        click.echo("\niOS Simulators:")
        ios_data = []
        for device in ios_devices:
            ios_data.append([
                device.name,
                device.os_version,
                device.state,
                device.id[:8] + '...' if len(device.id) > 8 else device.id
            ])
        
        click.echo(tabulate(ios_data, headers=['Name', 'OS', 'State', 'ID'], tablefmt='simple'))
    
    # Display Android devices
    if android_devices and platform in [None, 'android', 'both']:
        click.echo("\nAndroid Devices:")
        android_data = []
        for device in android_devices:
            android_data.append([
                device.name,
                device.os_version,
                device.device_type,
                device.state,
                device.id
            ])
        
        click.echo(tabulate(android_data, headers=['Name', 'OS', 'Type', 'State', 'ID'], tablefmt='simple'))
    
    click.echo(f"\nTotal devices: {len(all_devices)}")


@test.command('check')
@click.pass_context
def check(ctx):
    """Check mobile testing environment and requirements.
    
    Verifies that all required tools and configurations are in place
    for native mobile testing.
    
    Example:
        sega mobile test check
    """
    if not NATIVE_TESTING_AVAILABLE:
        click.echo("Error: Native testing infrastructure not available.")
        ctx.exit(1)
    
    click.echo("Checking mobile testing environment...\n")
    
    # Check for config
    config_path = Path.cwd() / 'mobile_test_config.yaml'
    if not config_path.exists():
        config_path = Path.cwd() / 'mobile_test_config.json'
    
    config_exists = config_path.exists()
    click.echo(f"Configuration file: {'' if config_exists else ''} {config_path.name if config_exists else 'Not found'}")
    
    # Load config to check platforms
    ios_configured = False
    android_configured = False
    
    if config_exists:
        try:
            orchestrator = MobileTestOrchestrator(config_path)
            if 'platforms' in orchestrator.config:
                ios_configured = 'ios' in orchestrator.config['platforms']
                android_configured = 'android' in orchestrator.config['platforms']
        except:
            pass
    
    click.echo(f"iOS configured: {'' if ios_configured else ''}")
    click.echo(f"Android configured: {'' if android_configured else ''}")
    
    # Check iOS requirements
    if ios_configured:
        click.echo("\niOS Environment:")
        ios_runner = IOSNativeTestRunner(Path.cwd(), orchestrator.config['platforms']['ios'])
        ios_reqs = ios_runner.check_requirements()
        
        for req, value in ios_reqs.items():
            if isinstance(value, bool):
                click.echo(f"  {req}: {'' if value else ''}")
            else:
                click.echo(f"  {req}: {value}")
    
    # Check Android requirements
    if android_configured:
        click.echo("\nAndroid Environment:")
        android_runner = AndroidNativeTestRunner(Path.cwd(), orchestrator.config['platforms']['android'])
        android_reqs = android_runner.check_requirements()
        
        for req, value in android_reqs.items():
            if isinstance(value, bool):
                click.echo(f"  {req}: {'' if value else ''}")
            else:
                click.echo(f"  {req}: {value}")
    
    # Check devices
    click.echo("\nAvailable Devices:")
    device_manager = DeviceManager()
    all_devices = device_manager.list_all_devices()
    
    ios_count = len([d for d in all_devices if d.platform == 'ios'])
    android_emu_count = len([d for d in all_devices if d.platform == 'android' and d.device_type == 'emulator'])
    android_dev_count = len([d for d in all_devices if d.platform == 'android' and d.device_type == 'physical'])
    
    click.echo(f"  iOS simulators: {ios_count}")
    click.echo(f"  Android emulators: {android_emu_count}")
    click.echo(f"  Android devices: {android_dev_count}")
    
    # Overall status
    click.echo("\nOverall Status:")
    
    ios_ready = ios_configured and ios_reqs.get('xcode', False) and ios_count > 0
    android_ready = android_configured and android_reqs.get('gradle', False) and (android_emu_count > 0 or android_dev_count > 0)
    
    if ios_ready and android_ready:
        click.echo(" Ready for iOS and Android testing")
    elif ios_ready:
        click.echo(" Ready for iOS testing only")
    elif android_ready:
        click.echo(" Ready for Android testing only")
    else:
        click.echo(" Not ready for mobile testing. Please check requirements above.")


def _display_test_results(report):
    """Display test results in a formatted table"""
    click.echo("\nTest Results Summary")
    click.echo("=" * 60)
    
    # Overall summary
    summary_data = [
        ['Total Tests', report.summary['total_tests']],
        ['Passed', f"{report.summary['total_passed']} ({report.summary['pass_rate']:.1f}%)"],
        ['Failed', report.summary['total_failed']],
        ['Skipped', report.summary['total_skipped']],
        ['Duration', f"{report.total_duration:.2f}s"]
    ]
    
    click.echo(tabulate(summary_data, tablefmt='simple'))
    
    # Platform breakdown
    for platform, data in report.platforms.items():
        click.echo(f"\n{platform.upper()} Results:")
        
        suite_data = []
        for suite in data['suites']:
            row = [
                suite['suite'],
                suite['passed'],
                suite['failed'],
                suite['skipped'],
                f"{suite['duration']:.2f}s"
            ]
            
            # Add coverage if available
            if 'coverage' in suite:
                row.append(f"{suite['coverage']:.1f}%")
            
            suite_data.append(row)
        
        headers = ['Suite', 'Passed', 'Failed', 'Skipped', 'Duration']
        if any('coverage' in s for s in data['suites']):
            headers.append('Coverage')
        
        click.echo(tabulate(suite_data, headers=headers, tablefmt='simple'))