#!/usr/bin/env python3
"""
SEGA Standalone Commands - compile, sign, package

These are standalone versions of the forge subcommands for users who prefer
direct access (e.g., `sega compile` instead of `sega forge compile`).

Both entry points use the same underlying modules.
"""

import click
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Optional


# Re-export forge subcommands as standalone commands
# This allows both `sega compile` and `sega forge compile` to work

@click.command("compile")
@click.option("--lang", "-l", type=click.Choice(["python", "node", "js", "rust"]), required=True,
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

    \b
    Examples:
        sega compile --lang python --source ./backend
        sega compile --lang rust --dry-run
        sega compile --lang node --source ./frontend/dist
    """
    from ...forge.protection import NuitkaCompiler, BytenodeCompiler, JSObfuscator
    from ...forge.protection.nuitka import NuitkaConfig

    click.echo(f"Compiling {lang} to protected binary...")

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


@click.command("sign")
@click.option("--os", "target_os", type=click.Choice(["mac", "windows", "linux"]), required=True,
              help="Target operating system")
@click.option("--identity", help="Signing identity (macOS)")
@click.option("--cert", type=click.Path(exists=True), help="Certificate path (Windows)")
@click.option("--notarize", is_flag=True, help="Notarize after signing (macOS)")
@click.option("--target", "-t", type=click.Path(exists=True), help="File or app to sign")
@click.option("--dry-run", is_flag=True, help="Show command without executing")
def sign_cmd(target_os: str, identity: Optional[str], cert: Optional[str], notarize: bool,
             target: Optional[str], dry_run: bool):
    """Code signing for distribution.

    \b
    Operating Systems:
        mac      - codesign + notarize
        windows  - signtool / osslsigncode
        linux    - GPG signing

    \b
    Examples:
        sega sign --os linux --target ./dist/app.AppImage
        sega sign --os mac --target ./dist/App.app --identity "Developer ID"
        sega sign --os linux  # List available GPG keys
    """
    from ...forge.signing import MacSigner, WindowsSigner, LinuxSigner
    from ...forge.signing.mac import MacSigningConfig
    from ...forge.signing.linux import LinuxSigningConfig

    click.echo(f"Signing for {target_os}...")

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
            else:
                click.echo(f"Signing failed: {result.error_message}", err=True)
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
            else:
                click.echo(f"Signing failed: {result.error_message}", err=True)
                sys.exit(1)

        click.echo(f"Sign complete for {target_os}")

    except Exception as e:
        click.echo(f"Sign error: {e}", err=True)
        sys.exit(1)


@click.command("package")
@click.option("--platform", "-p", type=click.Choice(["desktop", "mobile", "cli", "extension", "ide"]),
              required=True, help="Target platform for packaging")
@click.option("--os", "target_os", type=click.Choice(["mac", "windows", "linux"]),
              help="Target OS (for desktop)")
@click.option("--output", "-o", type=click.Path(), help="Output directory")
@click.option("--dry-run", is_flag=True, help="Show command without executing")
@click.option("--project-dir", type=click.Path(exists=True), help="Project directory")
def package_cmd(platform: str, target_os: Optional[str], output: Optional[str],
                dry_run: bool, project_dir: Optional[str]):
    """Package application for distribution.

    \b
    Platforms:
        desktop    - .dmg, .exe, .AppImage (Electron)
        mobile     - .ipa, .apk (Expo EAS)
        cli        - standalone binary
        extension  - .vsix (VS Code extension)
        ide        - VS Code fork IDE

    \b
    Examples:
        sega package --platform desktop --os linux
        sega package --platform extension --project-dir ./extension
        sega package --platform mobile --os mac  # iOS build
    """
    from ...forge.packaging import ElectronPackager, VSCodeIDEBuilder, VSCodeExtensionPackager
    from ...forge.packaging.electron import ElectronConfig, Platform
    from ..commands.mobile import MobileManager

    click.echo(f"Packaging for {platform}...")

    project_path = Path(project_dir) if project_dir else Path.cwd()
    output_path = Path(output) if output else None

    try:
        if platform == "desktop":
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

            desktop_dir = project_path / "desktop"
            if desktop_dir.exists():
                project_path = desktop_dir

            result = packager.package(project_path, dry_run=dry_run)

            if result.success:
                click.echo("Packaging successful!")
                for artifact in result.artifacts:
                    click.echo(f"  - {artifact}")
            else:
                click.echo(f"Packaging failed: {result.error_message}", err=True)
                sys.exit(1)

        elif platform == "ide":
            builder = VSCodeIDEBuilder()

            if not builder.is_available():
                click.echo("VS Code IDE build tools not available", err=True)
                sys.exit(1)

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
            manager = MobileManager()
            mobile_os = "ios" if target_os == "mac" else "android"
            success = manager.build_app(platform=mobile_os, profile="preview")
            if not success:
                click.echo("Mobile packaging failed", err=True)
                sys.exit(1)
            click.echo("Mobile packaging successful")

        elif platform == "cli":
            click.echo("For CLI packaging, use: sega compile --lang <python|rust> --standalone")
            return

        click.echo(f"Package complete for {platform}")

    except Exception as e:
        click.echo(f"Package error: {e}", err=True)
        sys.exit(1)
