"""
SEGA Compile Command

Compiles source code to protected binaries using:
- Nuitka: Python to standalone binary
- Bytenode: Node.js to V8 bytecode
- JavaScript Obfuscator: JS code obfuscation

Configuration is read from config/sega.toml.

Usage:
    sega compile <project> --target <python|node|js|rust>
    sega compile <project> --all
"""

import logging
import os
from pathlib import Path
from typing import Optional

import click

from ...core.config import get_config, SegaConfig
from ...forge.protection import NuitkaCompiler, BytenodeCompiler, JSObfuscator
from ...forge.protection.nuitka import NuitkaConfig
from ...forge.protection.bytenode import BytenodeConfig
from ...forge.protection.jsobfuscator import JSObfuscatorConfig

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


def _detect_targets(project_path: Path, config: SegaConfig) -> list[str]:
    """Auto-detect compilation targets based on project structure and config."""
    targets = []

    # Python
    python_indicators = [
        project_path / "pyproject.toml",
        project_path / "setup.py",
        project_path / "backend" / "main.py",
        project_path / "engine" / "main.py",
    ]
    if any(p.exists() for p in python_indicators) and config.protection.python.enabled:
        targets.append("python")

    # Node.js
    node_indicators = [
        project_path / "package.json",
        project_path / "frontend" / "package.json",
    ]
    if any(p.exists() for p in node_indicators) and config.protection.node.enabled:
        pkg_json = project_path / "package.json"
        if pkg_json.exists():
            try:
                import json
                with open(pkg_json) as f:
                    pkg = json.load(f)
                    deps = {**pkg.get("dependencies", {}), **pkg.get("devDependencies", {})}
                    if "electron" in deps or "react" in deps:
                        targets.append("node")
            except Exception:
                pass

    # JavaScript (function library)
    js_indicators = [
        project_path / "lib",
        project_path / "src" / "functions",
    ]
    if config.protection.js.enabled:
        if any(p.exists() and any(p.glob("*.js")) for p in js_indicators):
            targets.append("js")

    # Rust
    if (project_path / "Cargo.toml").exists() and config.protection.rust.enabled:
        targets.append("rust")

    return targets


def _compile_python(
    project_path: Path,
    config: SegaConfig,
    output_dir: Path,
    dry_run: bool,
) -> dict:
    """Compile Python with Nuitka using TOML config."""
    prot = config.protection.python

    # Build Nuitka config from central TOML
    nuitka_config = NuitkaConfig.from_options_string(prot.options)
    nuitka_config.output_dir = str(output_dir)

    compiler = NuitkaCompiler(nuitka_config)

    if not compiler.is_available():
        return {
            "success": False,
            "error": "Nuitka not installed. Run: pip install nuitka",
        }

    # Find entry point
    entry_points = [
        project_path / "backend" / "main.py",
        project_path / "engine" / "main.py",
        project_path / "src" / "main.py",
        project_path / "main.py",
        project_path / "__main__.py",
    ]

    entry_point = next((ep for ep in entry_points if ep.exists()), None)

    if entry_point is None:
        return {
            "success": False,
            "error": "No Python entry point found",
        }

    click.echo(f"Entry point: {entry_point}")

    # Set standalone environment variables for telemetry exclusion
    if config.distribution.exclusions.telemetry_reporter:
        for key, value in prot.standalone_env.items():
            os.environ[key] = value
        click.echo("Telemetry reporter: EXCLUDED (standalone build)")

    result = compiler.compile(entry_point, output_dir, dry_run=dry_run)

    return {
        "success": result.success,
        "output": str(result.output_path) if result.output_path else None,
        "error": result.error_message,
        "command": result.command,
    }


def _compile_node(
    project_path: Path,
    config: SegaConfig,
    output_dir: Path,
    dry_run: bool,
) -> dict:
    """Compile Node.js with Bytenode using TOML config."""
    prot = config.protection.node

    bytenode_config = BytenodeConfig.from_options_string(prot.options)
    bytenode_config.output_dir = str(output_dir)

    # Check for Electron
    pkg_json = project_path / "package.json"
    if pkg_json.exists():
        import json
        with open(pkg_json) as f:
            pkg = json.load(f)
            deps = {**pkg.get("dependencies", {}), **pkg.get("devDependencies", {})}
            if "electron" in deps:
                bytenode_config.electron = True

    compiler = BytenodeCompiler(bytenode_config)

    if not compiler.is_available():
        return {
            "success": False,
            "error": "Bytenode not installed. Run: npm install -g bytenode",
        }

    # Find frontend directory
    frontend_dirs = [
        project_path / "frontend" / "dist",
        project_path / "frontend" / "build",
        project_path / "dist",
        project_path / "build",
        project_path / "src" / "renderer",
    ]

    frontend_dir = next((fd for fd in frontend_dirs if fd.exists()), None)

    if frontend_dir is None:
        frontend_dir = project_path / "frontend" / "src"
        if not frontend_dir.exists():
            frontend_dir = project_path / "src"

    if not frontend_dir.exists():
        return {
            "success": False,
            "error": "No frontend directory found",
        }

    click.echo(f"Frontend dir: {frontend_dir}")

    # Set standalone defines for telemetry exclusion
    if config.distribution.exclusions.telemetry_reporter:
        click.echo("Telemetry reporter: EXCLUDED (standalone build)")

    result = compiler.compile_directory(
        frontend_dir,
        output_dir,
        exclude_patterns=["node_modules", "*.test.js", "*.spec.js", "*.d.ts"],
        dry_run=dry_run,
    )

    return {
        "success": result.success,
        "output": [str(f) for f in result.output_files] if result.output_files else None,
        "error": result.error_message,
        "command": result.command,
    }


def _compile_js(
    project_path: Path,
    config: SegaConfig,
    output_dir: Path,
    dry_run: bool,
) -> dict:
    """Compile JavaScript with obfuscator using TOML config."""
    prot = config.protection.js

    obf_config = JSObfuscatorConfig.from_options_string(prot.options)
    obf_config.output_dir = str(output_dir)

    obfuscator = JSObfuscator(obf_config)

    if not obfuscator.is_available():
        return {
            "success": False,
            "error": "javascript-obfuscator not installed. Run: npm install -g javascript-obfuscator",
        }

    js_dirs = [
        project_path / "lib",
        project_path / "src" / "functions",
        project_path / "src" / "lib",
        project_path / "functions",
    ]

    js_dir = next((jd for jd in js_dirs if jd.exists() and list(jd.glob("*.js"))), None)

    if js_dir is None:
        return {
            "success": False,
            "error": "No JavaScript source directory found",
        }

    click.echo(f"JS source dir: {js_dir}")

    result = obfuscator.obfuscate_directory(
        js_dir,
        output_dir,
        exclude_patterns=["node_modules", "*.test.js", "*.min.js"],
        dry_run=dry_run,
    )

    return {
        "success": result.success,
        "output": [str(f) for f in result.output_files] if result.output_files else None,
        "error": result.error_message,
        "command": result.command,
    }


def _compile_rust(
    project_path: Path,
    config: SegaConfig,
    output_dir: Path,
    dry_run: bool,
) -> dict:
    """Compile Rust with cargo using TOML config."""
    import shutil
    import subprocess

    cargo = shutil.which("cargo")
    if not cargo:
        return {
            "success": False,
            "error": "Cargo not installed",
        }

    prot = config.protection.rust

    # Build command with feature flags for standalone
    cmd = [cargo, "build", "--release"]

    if prot.exclude_default_features:
        cmd.append("--no-default-features")

    if prot.standalone_features:
        cmd.extend(["--features", ",".join(prot.standalone_features)])

    command_str = " ".join(cmd)

    if dry_run:
        return {
            "success": True,
            "command": command_str,
            "output": f"[DRY RUN] Would execute in {project_path}:\n{command_str}",
        }

    click.echo(f"Running: {command_str}")

    if config.distribution.exclusions.telemetry_reporter:
        click.echo("Telemetry reporter: EXCLUDED (standalone features)")

    result = subprocess.run(
        cmd,
        capture_output=True,
        text=True,
        cwd=project_path,
    )

    if result.returncode == 0:
        target_dir = project_path / "target" / "release"
        binaries = [b for b in target_dir.glob("*") if b.is_file() and not b.suffix]

        return {
            "success": True,
            "output": [str(b) for b in binaries],
            "command": command_str,
        }
    else:
        return {
            "success": False,
            "error": result.stderr or "Cargo build failed",
            "command": command_str,
        }


@click.command()
@click.argument("project", default=".")
@click.option(
    "--target", "-t",
    type=click.Choice(["python", "node", "js", "rust", "all"]),
    default=None,
    help="Compilation target",
)
@click.option("--all", "compile_all", is_flag=True, help="Compile all applicable targets")
@click.option("--output", "-o", type=click.Path(), default=None, help="Output directory")
@click.option("--dry-run", is_flag=True, help="Show commands without executing")
@click.option("--verbose", "-v", is_flag=True, help="Verbose output")
def compile(
    project: str,
    target: Optional[str],
    compile_all: bool,
    output: Optional[str],
    dry_run: bool,
    verbose: bool,
):
    """
    Compile source code to protected binaries.

    Configuration is read from config/sega.toml.

    Examples:
        sega compile atlas --target python
        sega compile vega --target node
        sega compile . --all
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

    # Determine targets
    if compile_all or target == "all":
        targets = _detect_targets(project_path, config)
        if not targets:
            targets = ["python"]  # Default
    elif target:
        targets = [target]
    else:
        targets = _detect_targets(project_path, config)

    if not targets:
        click.secho("No compilation targets found", fg="yellow")
        return

    click.echo(f"Targets: {', '.join(targets)}")
    click.echo(f"Mode: {config.distribution.default_mode}")

    # Output directory
    output_dir = Path(output) if output else project_path / "dist" / "compiled"
    if not dry_run:
        output_dir.mkdir(parents=True, exist_ok=True)

    # Compile each target
    results = {}
    for t in targets:
        click.echo(f"\n{'='*60}")
        click.echo(f"Compiling {t}...")
        click.echo("="*60)

        if t == "python":
            result = _compile_python(project_path, config, output_dir, dry_run)
        elif t == "node":
            result = _compile_node(project_path, config, output_dir, dry_run)
        elif t == "js":
            result = _compile_js(project_path, config, output_dir, dry_run)
        elif t == "rust":
            result = _compile_rust(project_path, config, output_dir, dry_run)
        else:
            click.secho(f"Unknown target: {t}", fg="yellow")
            continue

        results[t] = result

        if result.get("success"):
            click.secho(f"  {t}: Success", fg="green")
            if result.get("output"):
                click.echo(f"  Output: {result['output']}")
        else:
            click.secho(f"  {t}: Failed", fg="red")
            if result.get("error"):
                click.echo(f"  Error: {result['error']}")

    # Summary
    click.echo(f"\n{'='*60}")
    click.echo("Compilation Summary")
    click.echo("="*60)
    success_count = sum(1 for r in results.values() if r.get("success"))
    click.echo(f"Completed: {success_count}/{len(results)} targets")

    if success_count < len(results):
        raise SystemExit(1)
