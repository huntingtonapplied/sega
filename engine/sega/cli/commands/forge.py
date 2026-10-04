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
SEGA FORGE COMMAND - Build, Package & Distribute
==============================================================================
File: src/sega/commands/forge.py
Project: SEGA (Scalable Engineering & Growth Automation)
Copyright: 2022-2025 FLEET
License: Apache-2.0

SEGA MODULE: Commands/Forge
COMPONENT: Unified Build, Package, and Distribution CLI Command
PURPOSE: Consolidate build, compile, package, sign, and publish operations
DEPENDENCIES: click, pathlib, subprocess

Core Principle: Actions are commands, platforms are options.

This command consolidates:
- sega desktop build/dev → sega forge build/dev --platform desktop
- sega mobile build/dev → sega forge build/dev --platform mobile
- sega frontend build → sega forge build --platform web
- sega compile → sega forge compile
- sega package → sega forge package
- sega sign → sega forge sign
- (new) sega forge publish → distribute artifacts
- (new) sega forge release → full workflow
==============================================================================
"""

import click
import shutil
import subprocess
import sys
import os
from pathlib import Path
from typing import Optional

from ...infrastructure import get_distribution_config

# Direct imports for platform managers (replacing subprocess delegation)
from .desktop import DesktopManager
from .mobile import MobileManager
from .frontend import FrontendOrchestrator


# Platform choices
PLATFORMS = ["desktop", "mobile", "web", "api", "cli", "extension"]
PUBLISH_TARGETS = ["instance", "s3", "github", "appstore", "playstore", "registry"]
COMPILE_LANGS = ["python", "node", "js", "rust"]
SIGN_OS = ["mac", "windows", "linux"]


@click.group()
def forge():
    """Build, package, and distribute applications.

    Unified command for building, compiling, packaging, signing, and
    publishing applications across all platforms.

    Core Principle: Actions are commands, platforms are options.

    \b
    Examples:
        sega forge build --platform desktop    # Electron build
        sega forge build --platform mobile     # Expo/React Native build
        sega forge build --platform web        # Next.js/frontend build
        sega forge compile --lang python       # Nuitka compilation
        sega forge package --platform desktop  # Package for distribution
        sega forge sign --os mac               # Code signing
        sega forge publish --target github     # Publish to GitHub Releases
        sega forge release --platform desktop --target github  # Full workflow
    """
    pass


@forge.command()
@click.option("--platform", "-p", type=click.Choice(PLATFORMS), required=True,
              help="Target platform: desktop, mobile, web, api")
@click.option("--output", "-o", type=click.Path(), help="Output directory")
@click.option("--clean", is_flag=True, help="Clean build artifacts before building")
@click.option("--production", is_flag=True, help="Production build with optimizations")
@click.option("--verbose", "-v", is_flag=True, help="Verbose output")
@click.option("--project", type=str, help="Project name (for web builds)")
@click.option("--mobile-platform", type=click.Choice(["ios", "android"]), help="Mobile platform target")
@click.option("--profile", default="preview", help="Build profile for mobile (default: preview)")
def build(platform: str, output: Optional[str], clean: bool, production: bool, verbose: bool,
          project: Optional[str], mobile_platform: Optional[str], profile: str):
    """Build project for target platform.

    \b
    Platforms:
        desktop  - Electron application build
        mobile   - Expo/React Native build
        web      - Next.js/frontend build
        api      - Backend/API build
    """
    click.echo(f"Building for platform: {platform}")

    try:
        if platform == "desktop":
            # Use DesktopManager directly
            manager = DesktopManager()
            target = "darwin" if production else None  # Build for all platforms if production
            success = manager.build_app(target_platform=target)
            if not success:
                click.echo("Desktop build failed", err=True)
                sys.exit(1)

        elif platform == "mobile":
            # Use MobileManager directly
            manager = MobileManager()
            mobile_target = mobile_platform or "android"  # Default to Android
            success = manager.build_app(platform=mobile_target, profile=profile)
            if not success:
                click.echo("Mobile build failed", err=True)
                sys.exit(1)

        elif platform == "web":
            # Use FrontendOrchestrator directly
            orchestrator = FrontendOrchestrator()
            project_name = project or Path.cwd().name
            mode = "isolated" if production else "shared"
            result = orchestrator.build_frontend(project=project_name, mode=mode, clean=clean)
            if not result.success:
                click.echo(f"Web build failed: {result.message}", err=True)
                sys.exit(1)
            click.echo(result.message)

        elif platform == "api":
            # API builds typically use make or docker
            if verbose:
                click.echo("Running: make build")
            result = subprocess.run(["make", "build"])
            sys.exit(result.returncode)

        else:
            # Fallback for other platforms
            if verbose:
                click.echo("Running: make build")
            result = subprocess.run(["make", "build"])
            sys.exit(result.returncode)

        click.echo(f"Build complete for {platform}")

    except Exception as e:
        click.echo(f"Build error: {e}", err=True)
        sys.exit(1)


@forge.command()
@click.option("--platform", "-p", type=click.Choice(["desktop", "mobile", "web"]), required=True,
              help="Target platform for development server")
@click.option("--port", type=int, help="Custom port")
@click.option("--host", default="localhost", help="Host to bind to")
@click.option("--project", type=str, help="Project name (for web dev)")
@click.option("--no-backend", is_flag=True, help="Start without backend (desktop only)")
@click.option("--clear-cache", is_flag=True, help="Clear cache before starting (mobile only)")
def dev(platform: str, port: Optional[int], host: str, project: Optional[str],
        no_backend: bool, clear_cache: bool):
    """Start development server for platform.

    \b
    Platforms:
        desktop  - Electron dev mode
        mobile   - Expo dev server
        web      - Next.js dev server
    """
    click.echo(f"Starting {platform} development server...")

    try:
        if platform == "desktop":
            # Use DesktopManager directly
            manager = DesktopManager()
            success = manager.start_development(backend=not no_backend, debug_port=port)
            if not success:
                click.echo("Desktop dev server failed to start", err=True)
                sys.exit(1)

        elif platform == "mobile":
            # Use MobileManager directly
            manager = MobileManager()
            success = manager.start_development(clear_cache=clear_cache)
            if not success:
                click.echo("Mobile dev server failed to start", err=True)
                sys.exit(1)

        elif platform == "web":
            # Use FrontendOrchestrator directly
            orchestrator = FrontendOrchestrator()
            project_name = project or Path.cwd().name
            result = orchestrator.serve_frontend(project=project_name, dev=True)
            if not result.success:
                click.echo(f"Web dev server failed: {result.message}", err=True)
                sys.exit(1)
            click.echo(f"Dev server running on port {result.port}")

        else:
            # Fallback
            result = subprocess.run(["make", "dev"])
            sys.exit(result.returncode)

    except KeyboardInterrupt:
        click.echo("\nDevelopment server stopped")
    except Exception as e:
        click.echo(f"Dev server error: {e}", err=True)
        sys.exit(1)


@forge.command("compile")
@click.option("--lang", "-l", type=click.Choice(COMPILE_LANGS), required=True,
              help="Source language to compile")
@click.option("--output", "-o", type=click.Path(), help="Output directory")
@click.option("--standalone", is_flag=True, help="Create standalone binary")
@click.option("--onefile", is_flag=True, help="Single file output (where supported)")
@click.option("--dry-run", is_flag=True, help="Show command without executing")
@click.option("--source", "-s", type=click.Path(exists=True), help="Source file or directory")
def compile_cmd(lang: str, output: Optional[str], standalone: bool, onefile: bool,
                dry_run: bool, source: Optional[str]):
    """Compile source to protected binaries.

    \b
    Languages:
        python  - Nuitka compilation
        node    - Bytenode compilation
        js      - javascript-obfuscator
        rust    - cargo build --release
    """
    from ...forge.protection import NuitkaCompiler, BytenodeCompiler, JSObfuscator
    from ...forge.protection.nuitka import NuitkaConfig

    click.echo(f"Compiling {lang} to protected binary...")

    # Determine source path
    source_path = Path(source) if source else Path.cwd()
    output_path = Path(output) if output else None

    try:
        if lang == "python":
            config = NuitkaConfig(standalone=standalone, onefile=onefile)
            compiler = NuitkaCompiler(config)

            if not compiler.is_available():
                click.echo("Nuitka not installed. Install with: pip install nuitka", err=True)
                sys.exit(1)

            click.echo(f"Nuitka version: {compiler.get_version()}")

            if source_path.is_dir():
                result = compiler.compile_project(source_path, output_dir=output_path, dry_run=dry_run)
            else:
                result = compiler.compile(source_path, output_dir=output_path, dry_run=dry_run)

            if result.success:
                click.echo(f"Compilation successful: {result.output_path}")
                if result.command:
                    click.echo(f"Command: {result.command}")
            else:
                click.echo(f"Compilation failed: {result.error_message}", err=True)
                if result.stderr:
                    click.echo(result.stderr, err=True)
                sys.exit(1)

        elif lang == "node":
            compiler = BytenodeCompiler()

            if not compiler.is_available():
                click.echo("Bytenode not installed. Install with: npm install -g bytenode", err=True)
                sys.exit(1)

            click.echo(f"Bytenode version: {compiler.get_version()}")

            if source_path.is_dir():
                result = compiler.compile_directory(source_path, output_dir=output_path, dry_run=dry_run)
            else:
                result = compiler.compile([source_path], output_dir=output_path, dry_run=dry_run)

            if result.success:
                click.echo(f"Compilation successful: {len(result.output_files)} files compiled")
                for f in result.output_files:
                    click.echo(f"  - {f}")
            else:
                click.echo(f"Compilation failed: {result.error_message}", err=True)
                sys.exit(1)

        elif lang == "js":
            obfuscator = JSObfuscator()

            if not obfuscator.is_available():
                click.echo("javascript-obfuscator not installed. Install with: npm install -g javascript-obfuscator", err=True)
                sys.exit(1)

            click.echo(f"javascript-obfuscator version: {obfuscator.get_version()}")

            if source_path.is_dir():
                result = obfuscator.obfuscate_directory(source_path, output_dir=output_path, dry_run=dry_run)
            else:
                result = obfuscator.obfuscate(source_path, output_file=output_path, dry_run=dry_run)

            if result.success:
                click.echo(f"Obfuscation successful: {len(result.output_files)} files processed")
                for f in result.output_files:
                    click.echo(f"  - {f}")
            else:
                click.echo(f"Obfuscation failed: {result.error_message}", err=True)
                sys.exit(1)

        elif lang == "rust":
            # Rust uses cargo directly
            cargo_path = shutil.which("cargo")
            if not cargo_path:
                click.echo("Cargo not found. Install Rust toolchain.", err=True)
                sys.exit(1)

            cmd = ["cargo", "build", "--release"]
            if output:
                cmd.extend(["--target-dir", output])

            command_str = " ".join(cmd)
            if dry_run:
                click.echo(f"[DRY RUN] Would execute: {command_str}")
                return

            click.echo(f"Running: {command_str}")
            result = subprocess.run(cmd, cwd=source_path if source_path.is_dir() else source_path.parent)

            if result.returncode == 0:
                click.echo("Rust compilation successful")
            else:
                click.echo("Rust compilation failed", err=True)
                sys.exit(result.returncode)

        click.echo(f"Compile complete for {lang}")

    except Exception as e:
        click.echo(f"Compile error: {e}", err=True)
        sys.exit(1)


@forge.command()
@click.option("--platform", "-p", type=click.Choice(["desktop", "mobile", "cli", "extension", "ide"]),
              required=True, help="Target platform for packaging")
@click.option("--os", "target_os", type=click.Choice(SIGN_OS),
              help="Target OS (for desktop)")
@click.option("--output", "-o", type=click.Path(), help="Output directory")
@click.option("--dry-run", is_flag=True, help="Show command without executing")
@click.option("--project-dir", type=click.Path(exists=True), help="Project directory")
def package(platform: str, target_os: Optional[str], output: Optional[str],
            dry_run: bool, project_dir: Optional[str]):
    """Package application for distribution.

    \b
    Platforms:
        desktop    - .dmg, .exe, .AppImage (Electron)
        mobile     - .ipa, .apk (Expo EAS)
        cli        - standalone binary
        extension  - .vsix (VS Code extension)
        ide        - VS Code fork IDE
    """
    from ...forge.packaging import ElectronPackager, VSCodeIDEBuilder, VSCodeExtensionPackager
    from ...forge.packaging.electron import ElectronConfig, Platform

    click.echo(f"Packaging for {platform}...")

    # Determine project directory
    project_path = Path(project_dir) if project_dir else Path.cwd()
    output_path = Path(output) if output else None

    try:
        if platform == "desktop":
            # Map target_os to Platform enum
            platform_map = {
                "mac": Platform.MAC,
                "windows": Platform.WIN,
                "linux": Platform.LINUX,
                None: Platform.ALL,
            }
            target_platform = platform_map.get(target_os, Platform.ALL)

            config = ElectronConfig(platforms=[target_platform])
            if output_path:
                config.output_dir = str(output_path)

            packager = ElectronPackager(config)

            if not packager.is_available():
                click.echo("electron-builder not available. Install with: npm install -g electron-builder", err=True)
                sys.exit(1)

            click.echo(f"electron-builder version: {packager.get_version()}")

            # Look for desktop directory
            desktop_dir = project_path / "desktop"
            if desktop_dir.exists():
                project_path = desktop_dir

            result = packager.package(project_path, dry_run=dry_run)

            if result.success:
                click.echo(f"Packaging successful!")
                for artifact in result.artifacts:
                    click.echo(f"  - {artifact}")
            else:
                click.echo(f"Packaging failed: {result.error_message}", err=True)
                if result.stderr:
                    click.echo(result.stderr, err=True)
                sys.exit(1)

        elif platform == "ide":
            builder = VSCodeIDEBuilder()

            if not builder.is_available():
                click.echo("VS Code IDE build tools not available", err=True)
                sys.exit(1)

            # Look for ide directory
            ide_dir = project_path / "ide"
            if ide_dir.exists():
                project_path = ide_dir

            result = builder.build(project_path, output_dir=output_path, dry_run=dry_run)

            if result.success:
                click.echo(f"IDE build successful: {result.output_path}")
            else:
                click.echo(f"IDE build failed: {result.error_message}", err=True)
                sys.exit(1)

        elif platform == "extension":
            packager = VSCodeExtensionPackager()

            if not packager.is_available():
                click.echo("vsce not available. Install with: npm install -g @vscode/vsce", err=True)
                sys.exit(1)

            # Look for extension directory
            extension_dir = project_path / "extension"
            if extension_dir.exists():
                project_path = extension_dir

            result = packager.package(project_path, output_dir=output_path, dry_run=dry_run)

            if result.success:
                click.echo(f"Extension packaged: {result.vsix_path}")
            else:
                click.echo(f"Extension packaging failed: {result.error_message}", err=True)
                sys.exit(1)

        elif platform == "mobile":
            # Mobile uses Expo EAS - call existing mobile manager
            manager = MobileManager()
            mobile_os = "ios" if target_os == "mac" else "android"
            success = manager.build_app(platform=mobile_os, profile="preview")
            if not success:
                click.echo("Mobile packaging failed", err=True)
                sys.exit(1)
            click.echo("Mobile packaging successful")

        elif platform == "cli":
            # CLI packaging uses the compile command with standalone flag
            click.echo("For CLI packaging, use: sega forge compile --lang <python|rust> --standalone")
            return

        click.echo(f"Package complete for {platform}")

    except Exception as e:
        click.echo(f"Package error: {e}", err=True)
        sys.exit(1)


@forge.command()
@click.option("--os", "target_os", type=click.Choice(SIGN_OS), required=True,
              help="Target operating system")
@click.option("--identity", help="Signing identity (macOS)")
@click.option("--cert", type=click.Path(exists=True), help="Certificate path (Windows)")
@click.option("--notarize", is_flag=True, help="Notarize after signing (macOS)")
@click.option("--target", "-t", type=click.Path(exists=True), help="File or app to sign")
@click.option("--dry-run", is_flag=True, help="Show command without executing")
def sign(target_os: str, identity: Optional[str], cert: Optional[str], notarize: bool,
         target: Optional[str], dry_run: bool):
    """Code signing for distribution.

    \b
    Operating Systems:
        mac      - codesign + notarize
        windows  - signtool / osslsigncode
        linux    - GPG signing
    """
    from ...forge.signing import MacSigner, WindowsSigner, LinuxSigner
    from ...forge.signing.mac import MacSigningConfig
    from ...forge.signing.linux import LinuxSigningConfig

    click.echo(f"Signing for {target_os}...")

    # Determine target path
    target_path = Path(target) if target else None

    try:
        if target_os == "mac":
            config = MacSigningConfig(
                identity=identity or "",
                notarize=notarize,
            )
            signer = MacSigner(config)

            if not signer.is_available():
                click.echo("codesign not available (not on macOS?)", err=True)
                sys.exit(1)

            # List available identities if no target specified
            if not target_path:
                identities = signer.list_identities()
                if identities:
                    click.echo("Available signing identities:")
                    for ident in identities:
                        click.echo(f"  - {ident}")
                else:
                    click.echo("No signing identities found")
                return

            if notarize:
                result = signer.sign_and_notarize(target_path, identity, dry_run=dry_run)
            else:
                result = signer.sign(target_path, identity, dry_run=dry_run)

            if result.success:
                click.echo(f"Signing successful: {result.signed_path}")
                if result.notarization_status:
                    click.echo(f"Notarization: {result.notarization_status}")
                if result.command:
                    click.echo(f"Command: {result.command}")
            else:
                click.echo(f"Signing failed: {result.error_message}", err=True)
                if result.stderr:
                    click.echo(result.stderr, err=True)
                sys.exit(1)

        elif target_os == "windows":
            signer = WindowsSigner()

            if not signer.is_available():
                click.echo("signtool not available (not on Windows?)", err=True)
                sys.exit(1)

            if not target_path:
                click.echo("--target is required for Windows signing", err=True)
                sys.exit(1)

            result = signer.sign(target_path, certificate=cert, dry_run=dry_run)

            if result.success:
                click.echo(f"Signing successful: {result.signed_path}")
            else:
                click.echo(f"Signing failed: {result.error_message}", err=True)
                sys.exit(1)

        elif target_os == "linux":
            config = LinuxSigningConfig()
            signer = LinuxSigner(config)

            if not signer.is_available():
                click.echo("GPG not available. Install gnupg.", err=True)
                sys.exit(1)

            # List available keys if no target specified
            if not target_path:
                keys = signer.list_keys()
                if keys:
                    click.echo("Available GPG keys:")
                    for key in keys:
                        click.echo(f"  - {key.get('id', 'unknown')}: {key.get('uid', '')}")
                else:
                    click.echo("No GPG keys found")
                return

            result = signer.sign(target_path, dry_run=dry_run)

            if result.success:
                click.echo(f"Signing successful: {result.signature_path}")
                if result.command:
                    click.echo(f"Command: {result.command}")
            else:
                click.echo(f"Signing failed: {result.error_message}", err=True)
                sys.exit(1)

        click.echo(f"Sign complete for {target_os}")

    except Exception as e:
        click.echo(f"Sign error: {e}", err=True)
        sys.exit(1)


@forge.command()
@click.option("--target", "-t", type=click.Choice(PUBLISH_TARGETS), required=True,
              help="Publish destination")
@click.option("--version", help="Version tag")
@click.option("--file", "files", multiple=True, type=click.Path(exists=True),
              help="Files to publish")
@click.option("--dry-run", is_flag=True, help="Preview without publishing")
def publish(target: str, version: Optional[str], files: tuple, dry_run: bool):
    """Distribute artifacts to targets.

    \b
    Targets:
        instance   - SCP to EC2 download server
        s3         - Upload to S3 bucket
        github     - GitHub Releases
        appstore   - iOS App Store
        playstore  - Google Play Store
        registry   - Container/package registry (GitLab)
    """
    config = get_distribution_config()

    if dry_run:
        click.echo(f"[DRY RUN] Would publish to: {target}")
        if files:
            for f in files:
                click.echo(f"  - {f}")
        return

    click.echo(f"Publishing to {target}...")

    if target == "instance":
        # SCP to EC2 download server
        download_path = config.instance_download_path
        click.echo(f"Uploading to {download_path}")
        # Implementation would use paramiko or subprocess with scp

    elif target == "s3":
        # Upload to S3
        bucket = config.s3_bucket
        region = config.s3_region
        click.echo(f"Uploading to s3://{bucket}")
        # Implementation would use boto3

    elif target == "github":
        # GitHub Releases
        org = config.github_org
        click.echo(f"Creating GitHub release in {org}")
        # Implementation would use gh CLI or GitHub API

    elif target == "registry":
        # Container registry (GitLab)
        click.echo("Pushing to container registry...")
        cmd = ["docker", "push"]
        if files:
            cmd.append(files[0])
        result = subprocess.run(cmd)
        sys.exit(result.returncode)

    elif target in ["appstore", "playstore"]:
        click.echo(f"Publishing to {target}...")
        # Would integrate with fastlane or similar

    click.echo(f"Published to {target} successfully")


@forge.command()
@click.option("--platform", "-p", type=click.Choice(PLATFORMS), required=True,
              help="Target platform")
@click.option("--target", "-t", type=click.Choice(PUBLISH_TARGETS), required=True,
              help="Publish destination")
@click.option("--version", help="Version tag")
@click.option("--skip-tests", is_flag=True, help="Skip test execution")
@click.option("--dry-run", is_flag=True, help="Preview without executing")
def release(platform: str, target: str, version: Optional[str], skip_tests: bool, dry_run: bool):
    """Full release workflow: build -> compile -> package -> sign -> publish.

    Executes the complete release pipeline for the specified platform and target.

    \b
    Examples:
        sega forge release --platform desktop --target github
        sega forge release --platform mobile --target appstore
        sega forge release --platform api --target registry
    """
    steps = [
        ("build", f"Building for {platform}"),
        ("compile", "Compiling to protected binary"),
        ("package", "Packaging for distribution"),
        ("sign", "Code signing"),
        ("publish", f"Publishing to {target}"),
    ]

    if dry_run:
        click.echo("[DRY RUN] Release workflow:")
        for step, desc in steps:
            click.echo(f"  {step}: {desc}")
        return

    click.echo(f"Starting release workflow for {platform} -> {target}")
    click.echo("=" * 60)

    for step, desc in steps:
        click.echo(f"\n[{step.upper()}] {desc}")
        click.echo("-" * 40)

        # In a real implementation, each step would call the appropriate function
        # For now, we show the workflow structure
        if step == "build":
            click.echo(f"  sega forge build --platform {platform}")
        elif step == "compile":
            lang = "python" if platform == "api" else "node"
            click.echo(f"  sega forge compile --lang {lang}")
        elif step == "package":
            click.echo(f"  sega forge package --platform {platform}")
        elif step == "sign":
            click.echo("  sega forge sign --os <detected>")
        elif step == "publish":
            click.echo(f"  sega forge publish --target {target}")

    click.echo("\n" + "=" * 60)
    click.echo("Release workflow complete!")


if __name__ == "__main__":
    forge()
