"""
SEGA Package Command

Packages applications for distribution using:
- Electron Builder: Desktop apps (macOS, Windows, Linux)
- VS Code IDE: Custom VS Code builds
- VS Code Extension: .vsix packages
- Expo EAS: Mobile apps (iOS, Android)

Configuration is read from config/sega.toml.

Usage:
    sega package <project> --platform <desktop|mobile|ide|extension>
    sega package <project> --all
"""

import logging
import platform as plt
from pathlib import Path
from typing import Optional

import click

from ...core.config import get_config, SegaConfig
from ...forge.packaging import ElectronPackager, VSCodeIDEBuilder, VSCodeExtensionPackager
from ...forge.packaging.electron import ElectronConfig, Platform

logger = logging.getLogger(__name__)


def find_project_path(project: str) -> Optional[Path]:
    """Find project path from name or current directory."""
    if Path(project).exists():
        return Path(project).resolve()

    fleet_root = Path.home() / "fleet"
    if (fleet_root / project).exists():
        return fleet_root / project

    cwd = Path.cwd()
    if cwd.name == project:
        return cwd

    return None


def _detect_platforms(project_path: Path, config: SegaConfig) -> list[str]:
    """Auto-detect packaging platforms based on project structure and config."""
    platforms = []

    # Desktop (Electron)
    if config.packaging.desktop.enabled:
        desktop_indicators = [
            project_path / "electron.vite.config.ts",
            project_path / "electron.vite.config.js",
            project_path / "electron-builder.yml",
            project_path / "electron-builder.json",
            project_path / "frontend" / "electron.vite.config.ts",
        ]
        if any(p.exists() for p in desktop_indicators):
            platforms.append("desktop")

        # Also check package.json for electron
        pkg_json = project_path / "package.json"
        if pkg_json.exists() and "desktop" not in platforms:
            try:
                import json
                with open(pkg_json) as f:
                    pkg = json.load(f)
                    deps = {**pkg.get("dependencies", {}), **pkg.get("devDependencies", {})}
                    if "electron" in deps:
                        platforms.append("desktop")
            except Exception:
                pass

    # Mobile (Expo)
    if config.packaging.mobile.enabled:
        mobile_indicators = [
            project_path / "app.json",
            project_path / "expo.json",
            project_path / "mobile" / "app.json",
        ]
        for indicator in mobile_indicators:
            if indicator.exists():
                try:
                    import json
                    with open(indicator) as f:
                        data = json.load(f)
                        if "expo" in data:
                            platforms.append("mobile")
                            break
                except Exception:
                    pass

    # IDE (VS Code build)
    if config.packaging.ide.enabled:
        ide_indicators = [
            project_path / "product.json",
            project_path / "src" / "vs",
            project_path / "build" / "gulpfile.js",
        ]
        if any(p.exists() for p in ide_indicators):
            platforms.append("ide")

    # Extension (VS Code extension)
    if config.packaging.extension.enabled:
        extension_indicators = [
            project_path / ".vscodeignore",
            project_path / "vsc-extension-quickstart.md",
        ]
        if any(p.exists() for p in extension_indicators):
            platforms.append("extension")

        # Also check package.json for vscode extension
        pkg_json = project_path / "package.json"
        if pkg_json.exists() and "extension" not in platforms:
            try:
                import json
                with open(pkg_json) as f:
                    pkg = json.load(f)
                    if "publisher" in pkg and "engines" in pkg:
                        engines = pkg.get("engines", {})
                        if "vscode" in engines:
                            platforms.append("extension")
            except Exception:
                pass

    return platforms


def _package_desktop(
    project_path: Path,
    config: SegaConfig,
    output_dir: Path,
    targets: Optional[list[str]],
    dry_run: bool,
) -> dict:
    """Package desktop application with Electron using TOML config."""
    pkg_config = config.packaging.desktop

    # Build electron config from central TOML
    electron_config = ElectronConfig(
        output_dir=str(output_dir),
        template=pkg_config.template,
    )

    packager = ElectronPackager(electron_config)

    if not packager.is_available():
        return {
            "success": False,
            "error": "electron-builder not installed. Run: npm install -g electron-builder",
        }

    # Determine target platforms
    if targets:
        platform_map = {
            "mac": Platform.MAC,
            "macos": Platform.MAC,
            "darwin": Platform.MAC,
            "win": Platform.WINDOWS,
            "windows": Platform.WINDOWS,
            "linux": Platform.LINUX,
        }
        target_platforms = [platform_map.get(t.lower(), Platform.MAC) for t in targets]
    else:
        # Use platforms from config
        target_platforms = []
        for p in pkg_config.platforms:
            if p in ["mac", "macos"]:
                target_platforms.append(Platform.MAC)
            elif p in ["win", "windows"]:
                target_platforms.append(Platform.WINDOWS)
            elif p == "linux":
                target_platforms.append(Platform.LINUX)

        if not target_platforms:
            # Default to current platform
            system = plt.system().lower()
            if system == "darwin":
                target_platforms = [Platform.MAC]
            elif system == "windows":
                target_platforms = [Platform.WINDOWS]
            else:
                target_platforms = [Platform.LINUX]

    # Find frontend directory
    frontend_dirs = [project_path / "frontend", project_path]
    frontend_dir = next((fd for fd in frontend_dirs if (fd / "package.json").exists()), None)

    if frontend_dir is None:
        return {
            "success": False,
            "error": "No frontend directory with package.json found",
        }

    click.echo(f"Frontend dir: {frontend_dir}")
    click.echo(f"Targets: {[p.value for p in target_platforms]}")
    click.echo(f"Signing identity (mac): {pkg_config.signing.mac_identity}")

    # Package for each target
    outputs = []
    errors = []

    for target_platform in target_platforms:
        result = packager.package(
            frontend_dir,
            target_platform,
            output_dir,
            dry_run=dry_run,
        )

        if result.success:
            if result.output_files:
                outputs.extend(str(f) for f in result.output_files)
        else:
            errors.append(f"{target_platform.value}: {result.error_message}")

    if errors:
        return {
            "success": False,
            "error": "; ".join(errors),
            "output": outputs if outputs else None,
        }

    return {
        "success": True,
        "output": outputs,
    }


def _package_mobile(
    project_path: Path,
    config: SegaConfig,
    output_dir: Path,
    dry_run: bool,
) -> dict:
    """Package mobile application with Expo EAS using TOML config."""
    import shutil
    import subprocess

    pkg_config = config.packaging.mobile

    eas = shutil.which("eas")
    if not eas:
        return {
            "success": False,
            "error": "eas-cli not installed. Run: npm install -g eas-cli",
        }

    # Find mobile directory
    mobile_dirs = [project_path / "mobile", project_path]
    mobile_dir = next((md for md in mobile_dirs if (md / "app.json").exists()), None)

    if mobile_dir is None:
        return {
            "success": False,
            "error": "No mobile directory with app.json found",
        }

    # Determine platform from config
    platform = "all"
    if pkg_config.platforms:
        if len(pkg_config.platforms) == 1:
            platform = pkg_config.platforms[0]

    cmd = [eas, "build", "--profile=production", f"--platform={platform}", "--non-interactive"]
    command_str = " ".join(cmd)

    if dry_run:
        return {
            "success": True,
            "command": command_str,
            "output": f"[DRY RUN] Would execute in {mobile_dir}:\n{command_str}",
        }

    click.echo(f"Mobile dir: {mobile_dir}")
    click.echo(f"Running: {command_str}")

    result = subprocess.run(cmd, capture_output=True, text=True, cwd=mobile_dir)

    if result.returncode == 0:
        return {
            "success": True,
            "output": result.stdout,
            "command": command_str,
        }
    else:
        return {
            "success": False,
            "error": result.stderr or "EAS build failed",
            "command": command_str,
        }


def _package_ide(
    project_path: Path,
    config: SegaConfig,
    output_dir: Path,
    targets: Optional[list[str]],
    dry_run: bool,
) -> dict:
    """Package VS Code IDE build using TOML config."""
    from ...forge.packaging.vscode_ide import VSCodeBuildConfig

    pkg_config = config.packaging.ide

    ide_source = project_path
    template_path = Path.home() / "fleet" / "docs" / "templates" / "IDE" / "vscode"

    if not (ide_source / "src" / "vs").exists():
        if template_path.exists():
            ide_source = template_path
        else:
            return {
                "success": False,
                "error": "No VS Code source found. Need src/vs directory or template.",
            }

    build_config = VSCodeBuildConfig(
        output_dir=str(output_dir),
        build_system=pkg_config.build_system,
    )

    builder = VSCodeIDEBuilder(build_config, ide_source)

    if not builder.is_available():
        return {
            "success": False,
            "error": "gulp not installed. Run: npm install -g gulp-cli",
        }

    click.echo(f"IDE source: {ide_source}")

    # Install dependencies if needed
    if not dry_run and not (ide_source / "node_modules").exists():
        click.echo("Installing dependencies...")
        dep_result = builder.install_dependencies()
        if not dep_result.success:
            return {
                "success": False,
                "error": f"Failed to install dependencies: {dep_result.error_message}",
            }

    # Determine target platforms
    if targets:
        platform_targets = targets
    else:
        platform_targets = pkg_config.platforms if pkg_config.platforms else ["linux"]

    click.echo(f"Targets: {platform_targets}")

    outputs = []
    errors = []

    for target in platform_targets:
        target_map = {"mac": "darwin", "macos": "darwin", "win": "win32", "windows": "win32"}
        build_target = target_map.get(target.lower(), target.lower())

        result = builder.build(target=build_target, dry_run=dry_run)

        if result.success:
            if result.output_path:
                outputs.append(str(result.output_path))
        else:
            errors.append(f"{target}: {result.error_message}")

    if errors:
        return {
            "success": False,
            "error": "; ".join(errors),
            "output": outputs if outputs else None,
        }

    return {
        "success": True,
        "output": outputs,
    }


def _package_extension(
    project_path: Path,
    config: SegaConfig,
    output_dir: Path,
    dry_run: bool,
) -> dict:
    """Package VS Code extension using TOML config."""
    from ...forge.packaging.vscode_extension import VSCEConfig

    pkg_config = config.packaging.extension

    vsce_config = VSCEConfig(
        output_dir=str(output_dir),
        tool=pkg_config.tool,
    )

    packager = VSCodeExtensionPackager(vsce_config)

    if not packager.is_available():
        return {
            "success": False,
            "error": "vsce not installed. Run: npm install -g @vscode/vsce",
        }

    if not (project_path / "package.json").exists():
        return {
            "success": False,
            "error": "No package.json found",
        }

    click.echo(f"Extension dir: {project_path}")

    result = packager.package(project_path, output_dir, dry_run=dry_run)

    return {
        "success": result.success,
        "output": str(result.output_path) if result.output_path else None,
        "error": result.error_message,
        "command": result.command,
    }


@click.command()
@click.argument("project", default=".")
@click.option(
    "--platform", "-p",
    type=click.Choice(["desktop", "mobile", "ide", "extension", "cli", "all"]),
    default=None,
    help="Packaging platform",
)
@click.option("--all", "package_all", is_flag=True, help="Package for all applicable platforms")
@click.option("--target", "-t", multiple=True, help="Target OS (mac, win, linux)")
@click.option("--output", "-o", type=click.Path(), default=None, help="Output directory")
@click.option("--dry-run", is_flag=True, help="Show commands without executing")
@click.option("--verbose", "-v", is_flag=True, help="Verbose output")
def package(
    project: str,
    platform: Optional[str],
    package_all: bool,
    target: tuple,
    output: Optional[str],
    dry_run: bool,
    verbose: bool,
):
    """
    Package applications for distribution.

    Configuration is read from config/sega.toml.

    Examples:
        sega package vega --platform desktop
        sega package vega --platform desktop --target mac --target win
        sega package . --all
    """
    if verbose:
        logging.basicConfig(level=logging.DEBUG)

    # Load central TOML config
    config = get_config()

    # Find project
    project_path = find_project_path(project)
    if project_path is None:
        click.secho(f"Project not found: {project}", fg="red")
        raise SystemExit(1)

    click.echo(f"Project: {project_path}")
    click.echo(f"Config: {config.meta.config_path}")

    # Determine platforms
    if package_all or platform == "all":
        platforms = _detect_platforms(project_path, config)
        if not platforms:
            platforms = ["desktop"]  # Default
    elif platform:
        platforms = [platform]
    else:
        platforms = _detect_platforms(project_path, config)

    if not platforms:
        click.secho("No packaging platforms found", fg="yellow")
        return

    click.echo(f"Platforms: {', '.join(platforms)}")

    # Output directory
    output_dir = Path(output) if output else project_path / "dist" / "packages"
    if not dry_run:
        output_dir.mkdir(parents=True, exist_ok=True)

    # Parse targets
    os_targets = list(target) if target else None

    # Package each platform
    results = {}
    for p in platforms:
        click.echo(f"\n{'='*60}")
        click.echo(f"Packaging {p}...")
        click.echo("="*60)

        if p == "desktop":
            result = _package_desktop(project_path, config, output_dir, os_targets, dry_run)
        elif p == "mobile":
            result = _package_mobile(project_path, config, output_dir, dry_run)
        elif p == "ide":
            result = _package_ide(project_path, config, output_dir, os_targets, dry_run)
        elif p == "extension":
            result = _package_extension(project_path, config, output_dir, dry_run)
        else:
            click.secho(f"Unknown platform: {p}", fg="yellow")
            continue

        results[p] = result

        if result.get("success"):
            click.secho(f"  {p}: Success", fg="green")
            if result.get("output"):
                if isinstance(result["output"], list):
                    for out in result["output"]:
                        click.echo(f"  Output: {out}")
                else:
                    click.echo(f"  Output: {result['output']}")
        else:
            click.secho(f"  {p}: Failed", fg="red")
            if result.get("error"):
                click.echo(f"  Error: {result['error']}")

    # Summary
    click.echo(f"\n{'='*60}")
    click.echo("Packaging Summary")
    click.echo("="*60)
    success_count = sum(1 for r in results.values() if r.get("success"))
    click.echo(f"Completed: {success_count}/{len(results)} platforms")

    if success_count < len(results):
        raise SystemExit(1)
