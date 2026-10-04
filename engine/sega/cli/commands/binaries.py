#!/usr/bin/env python3
"""
SEGA BINARIES COMMAND - Build and Distribute All Build Assets
==============================================================================
File: engine/sega/cli/commands/binaries.py
Purpose: Build and distribute desktop, IDE, and binary assets
Asset Types: Desktop (Electron), IDE (VS Code fork), Binary (CLI tools)
==============================================================================
"""

import subprocess
import os
import re
import shutil
import sys
import tempfile
import hashlib
import json
import platform as _platform
from pathlib import Path
from typing import Optional, List, Dict

import click

from ...infrastructure import INSTANCE1, get_instance, get_ssh_key_path, get_ssh_options
from ...core.config import get_config
from ...utils.paths import get_fleet_root


def _config_desktop_projects() -> List[str]:
    """Projects the SEGA config marks as `has_desktop`, ordered by project id.

    Used to cross-check (not replace) the curated DESKTOP_PROJECTS list — the config
    catalog is the SSOT for the has_desktop flag, but it currently marks fewer projects
    than the curated build set, so DESKTOP_PROJECTS stays authoritative for what builds
    (see the note on DESKTOP_PROJECTS). Returns [] if config can't load.
    """
    try:
        projs = get_config().projects.values()
        return [p.name for p in sorted(projs, key=lambda p: p.id) if p.has_desktop]
    except Exception:
        return []

# =============================================================================
# Asset Type Constants
# =============================================================================

ASSET_TYPES = ["desktop", "ide", "binary", "all"]
PLATFORMS = ["mac", "windows", "linux", "all"]

# Build registries are now CONFIG DATA, not hardcoded here. The curated build sets
# (desktop / IDE / binary / CLI / engine membership + per-project build metadata) live
# in the `[build]` section of config/sega.toml and are read via get_config().build.*.
# They are NOT derivable from the config `has_desktop` flag (it is incomplete — config
# marks only one project has_desktop — and some entries, e.g. atlas/atlas, are not
# [projects] keys at all), which is why they are stored as standalone `[build]` config.
# Per-project workspace paths remain rooted through get_fleet_root() (honours SEGA_FLEET_ROOT).
#
# The module-level names below are rebuilt from config into the SAME SHAPES the rest of
# this file consumes (plain lists / dicts, with the historical dict keys — including the
# `lang` key derived from the config `tool` field), so downstream callers are unchanged.

# Desktop Projects (Electron applications) — curated build set from config.
DESKTOP_PROJECTS: List[str] = list(get_config().build.desktop)

# IDE Projects (VS Code fork) — from config.
IDE_PROJECTS: List[str] = list(get_config().build.ide)

# Binary Projects (CLI tools): project -> build language ("rust"/"python") — from config.
BINARY_PROJECTS: Dict[str, str] = dict(get_config().build.binary)


def _detect_os_arch_for_cli() -> tuple[str, str]:
    """Detect OS/arch strings for CLI binary naming."""
    sysname = _platform.system().lower()
    if sysname == "darwin":
        os_name = "darwin"
    elif sysname == "linux":
        os_name = "linux"
    else:
        raise click.ClickException(f"Unsupported build OS: {sysname} (expected darwin or linux)")

    machine = _platform.machine().lower()
    if machine in {"x86_64", "amd64"}:
        arch = "x86_64"  # canonical token presented in every download URL (install.sh/fetch.sh/frontend); never amd64
    elif machine in {"arm64", "aarch64"}:
        arch = "arm64"
    else:
        raise click.ClickException(f"Unsupported build architecture: {machine} (expected amd64 or arm64)")

    return os_name, arch


def _preflight_nuitka_build() -> None:
    """Fail fast (before spinning a venv + compiling) if the host lacks a Nuitka build prereq.

    Nuitka `--standalone`/`--module` on Linux needs `patchelf` to rewrite RPATHs — without it
    EVERY Python build FATALs deep in the run (gcc/clang being present is NOT enough). macOS
    uses install_name_tool and doesn't need it. Surface it up-front with the apt fix rather than
    letting it fail per-project mid-build. See SHARED_LESSONS "Linux Nuitka build host needs patchelf".
    """
    if _platform.system().lower() == "linux" and not shutil.which("patchelf"):
        raise click.ClickException(
            "Nuitka standalone builds on Linux require 'patchelf' (not installed). "
            "Fix: sudo apt-get install -y patchelf ccache")


# CLI project configuration (projects with dedicated CLI entry points).
# Config-derived (config/sega.toml `[build.cli.*]`); cli_dir is relative to ~/fleet/{project}/.
# Rebuilt into the historical dict shape the rest of this file consumes. The build type is
# stored as `tool` in config; here it is surfaced as the `lang` key ONLY for non-Python
# (e.g. Rust/cargo) builds, matching the original literals (callers do .get("lang","python")).
def _build_cli_projects() -> Dict[str, dict]:
    out: Dict[str, dict] = {}
    for name, e in get_config().build.cli.items():
        entry = {
            "cli_dir": e.cli_dir,
            "package_name": e.package_name,
            "binary_name": e.binary_name,
            "install_script": e.install_script,
            "source_dir": e.source_dir,
        }
        if e.tool != "python":
            entry["lang"] = e.tool
        out[name] = entry
    return out


CLI_PROJECTS: Dict[str, dict] = _build_cli_projects()


def _read_toml_version(pyproject_path: Path) -> str:
    if not pyproject_path.exists():
        raise click.ClickException(f"pyproject.toml not found: {pyproject_path}")

    if sys.version_info >= (3, 11):
        import tomllib as toml_parser  # type: ignore
    else:
        try:
            import tomli as toml_parser  # type: ignore
        except ImportError as e:
            raise click.ClickException("tomli is required on Python <3.11") from e

    with open(pyproject_path, "rb") as f:
        data = toml_parser.load(f)

    project = data.get("project") or {}
    version = project.get("version")
    if version:
        return str(version)

    # flit/PEP 621 DYNAMIC version: `[project] dynamic = ["version"]` — the version isn't in
    # pyproject; it lives in the package's `__init__.py` as `__version__`. Every FLEET engine
    # (atlas/hermes/hermes/atlas/hermes) is flit-dynamic, so resolve it there.
    if "version" in (project.get("dynamic") or []):
        pkg = project.get("name", "").replace("-", "_")
        # flit tool config can name a different module; honor it if present.
        pkg = (((data.get("tool") or {}).get("flit") or {}).get("module") or {}).get("name") or pkg
        base = pyproject_path.parent
        for init in ([base / pkg / "__init__.py", base / f"{pkg}.py"] if pkg else []):
            if init.exists():
                m = re.search(r"""__version__\s*=\s*['"]([^'"]+)['"]""", init.read_text())
                if m:
                    return m.group(1)
        raise click.ClickException(
            f"[project].version is dynamic in {pyproject_path} but no __version__ found "
            f"in {pkg}/__init__.py — pass --version explicitly")
    raise click.ClickException(f"Could not read [project].version from {pyproject_path}")


def _read_cargo_version(cargo_path: Path) -> str:
    """Read [package].version from a Rust Cargo.toml."""
    if not cargo_path.exists():
        raise click.ClickException(f"Cargo.toml not found: {cargo_path}")

    if sys.version_info >= (3, 11):
        import tomllib as toml_parser  # type: ignore
    else:
        try:
            import tomli as toml_parser  # type: ignore
        except ImportError as e:
            raise click.ClickException("tomli is required on Python <3.11") from e

    with open(cargo_path, "rb") as f:
        data = toml_parser.load(f)

    version = (data.get("package") or {}).get("version")
    if not version:
        raise click.ClickException(f"Could not read [package].version from {cargo_path}")
    return str(version)


def _cargo_build_binary(source_dir: Path, cargo_bin_name: str, dest_binary: Path,
                        features: Optional[str] = None) -> None:
    """Build a Rust release binary with cargo and stage it at dest_binary.

    Builds natively for the host arch (no --target cross-compile). cargo_bin_name
    is the Cargo [[bin]] name; the artifact lands at target/release/<name> and is
    copied to dest_binary (dist/<binary>-<os>-<arch>) for the shared publish path.
    features (optional): comma-separated Cargo features — required when the [[bin]] is
    gated behind `required-features` (e.g. orion-engine needs `marl`, else cargo silently
    builds nothing and the artifact is missing).
    """
    # Prefer the rustup toolchain (`~/.cargo/bin/cargo`) over a distro `/usr/bin/cargo`, which is
    # often old (Ubuntu ships 1.75) and FATALs on a modern `Cargo.lock` v4
    # (`lock file version 4 requires -Znext-lockfile-bump`). Preferring rustup makes the build
    # immune to PATH ordering. See SHARED_LESSONS "Rust CLIs need the rustup cargo on PATH".
    rustup_cargo = Path.home() / ".cargo" / "bin" / "cargo"
    cargo = str(rustup_cargo) if rustup_cargo.exists() else shutil.which("cargo")
    if not cargo:
        raise click.ClickException("cargo not found (install the Rust toolchain via rustup)")

    cmd = [cargo, "build", "--release", "--bin", cargo_bin_name]
    if features:
        cmd += ["--features", features]

    # The engines' build scripts (prost-build) need `protoc`. On the mac minis it's installed at
    # /opt/homebrew/bin but NOT on the non-interactive shell PATH sega runs under, so the build
    # script FATALs "Could not find protoc". Resolve it and pass PROTOC through so the build works
    # headless (verified 2026-07-22: orion/orion `cargo check` fails without it, passes with it).
    env = os.environ.copy()
    if not env.get("PROTOC"):
        protoc = shutil.which("protoc") or next(
            (p for p in ("/opt/homebrew/bin/protoc", "/usr/local/bin/protoc", "/usr/bin/protoc")
             if Path(p).exists()), None)
        if protoc:
            env["PROTOC"] = protoc
    subprocess.run(
        cmd,
        cwd=str(source_dir),
        check=True,
        env=env,
    )

    # Resolve where cargo actually placed the artifact. A crate- or repo-level
    # .cargo/config.toml (or CARGO_TARGET_DIR) can redirect target-dir away from
    # source_dir/target — the FLEET fleet shares a cli_target dir (TARGET_DIR_STANDARD.md),
    # so target/release/<bin> under the source does NOT exist. Search candidates in order.
    candidates: List[Path] = []
    env_target = os.environ.get("CARGO_TARGET_DIR")
    if env_target:
        candidates.append(Path(env_target).expanduser())
    for base in [source_dir, *source_dir.parents]:
        cfg = base / ".cargo" / "config.toml"
        if cfg.exists():
            m = re.search(r'(?m)^\s*target-dir\s*=\s*"([^"]+)"', cfg.read_text())
            if m:
                td = Path(m.group(1))
                candidates.append(td if td.is_absolute() else (base / td).resolve())
            break
    candidates.append(source_dir / "target")

    built = next((c / "release" / cargo_bin_name for c in candidates
                  if (c / "release" / cargo_bin_name).exists()), None)
    if built is None:
        searched = ", ".join(str(c / "release" / cargo_bin_name) for c in candidates)
        raise click.ClickException(f"cargo build succeeded but binary not found. Searched: {searched}")

    dest_binary.parent.mkdir(parents=True, exist_ok=True)
    subprocess.run(["cp", str(built), str(dest_binary)], check=True)
    subprocess.run(["chmod", "755", str(dest_binary)], check=True)

# =============================================================================
# CLI Command Group
# =============================================================================


@click.group()
def binaries():
    """Build and distribute all build assets (desktop, IDE, binary)."""
    pass


@binaries.command()
@click.option("--type", "-t", type=click.Choice(ASSET_TYPES), default="desktop", help="Asset type to build")
@click.option("--project", "-p", help="Specific project (default: all)")
@click.option("--platform", type=click.Choice(PLATFORMS), default="all", help="Target platform")
@click.option("--local", is_flag=True, help="Build locally instead of on instance")
@click.option("--skip-frontend", is_flag=True, help="Skip frontend build (desktop only)")
@click.option("--skip-backend", is_flag=True, help="Skip backend build (desktop only)")
def build(type, project, platform, local, skip_frontend, skip_backend):
    """Build assets for specified type and platform.

    Examples:
        sega binaries build --type desktop -p atlas --platform mac
        sega binaries build --type ide -p atlas --platform all
        sega binaries build --type binary -p orion --platform linux
        sega binaries build --type all  # Build all asset types
    """
    click.echo(f"Building {type} assets...")
    click.echo(f"Platform: {platform}")
    click.echo("")

    if type == "desktop" or type == "all":
        _build_desktop(project, platform, local, skip_frontend, skip_backend)

    if type == "ide" or type == "all":
        _build_ide(project, platform, local)

    if type == "binary" or type == "all":
        _build_binary(project, platform, local)


@binaries.command()
@click.option("--type", "-t", type=click.Choice(ASSET_TYPES), default="desktop", help="Asset type to distribute")
@click.option("--project", "-p", help="Specific project (default: all)")
@click.option("--platform", type=click.Choice(PLATFORMS), default="all", help="Platform to distribute")
@click.option("--instance", "-i", type=int, default=1, help="Instance number")
@click.option("--dry-run", is_flag=True, help="Show what would be copied")
def distribute(type, project, platform, instance, dry_run):
    """Distribute built assets to downloads infrastructure.

    Examples:
        sega binaries distribute --type desktop -p atlas
        sega binaries distribute --type ide -p atlas --platform mac
        sega binaries distribute --type binary -p orion
        sega binaries distribute --type all  # Distribute all built assets
    """
    if instance != 1:
        click.echo("Error: Downloads currently only on Instance 1")
        return

    click.echo(f"Distributing {type} assets to Instance {instance}...")
    click.echo("")

    if type == "desktop" or type == "all":
        _distribute_desktop(project, platform, instance, dry_run)

    if type == "ide" or type == "all":
        _distribute_ide(project, platform, instance, dry_run)

    if type == "binary" or type == "all":
        _distribute_binary(project, platform, instance, dry_run)


@binaries.command()
@click.option("--type", "-t", type=click.Choice(ASSET_TYPES), default="desktop", help="Asset type to verify")
@click.option("--project", "-p", help="Specific project")
@click.option("--instance", "-i", type=int, default=1, help="Instance number")
def verify(type, project, instance):
    """Verify built assets exist in downloads infrastructure.

    Examples:
        sega binaries verify --type desktop -p atlas
        sega binaries verify --type ide
        sega binaries verify --type all  # Verify all asset types
    """
    click.echo(f"Verifying {type} assets on Instance {instance}...\n")

    if type == "desktop" or type == "all":
        _verify_desktop(project, instance)

    if type == "ide" or type == "all":
        _verify_ide(project, instance)

    if type == "binary" or type == "all":
        _verify_binary(project, instance)


@binaries.command()
@click.option("--type", "-t", type=click.Choice(ASSET_TYPES), default="desktop", help="Asset type to release")
@click.option("--project", "-p", help="Specific project")
@click.option("--platform", type=click.Choice(PLATFORMS), default="all", help="Target platform")
def release(type, project, platform):
    """Build and distribute in one command.

    Equivalent to: build + distribute

    Examples:
        sega binaries release --type desktop -p atlas
        sega binaries release --type ide -p atlas --platform mac
        sega binaries release --type all  # Build and distribute everything
    """
    click.echo(f"Building and distributing {type} assets...")
    click.echo(f"Projects: {project or 'all'}")
    click.echo("")

    # Build
    if type == "desktop" or type == "all":
        _build_desktop(project, platform, False, False, False)

    if type == "ide" or type == "all":
        _build_ide(project, platform, False)

    if type == "binary" or type == "all":
        _build_binary(project, platform, False)

    # Distribute
    if type == "desktop" or type == "all":
        _distribute_desktop(project, platform, 1, False)

    if type == "ide" or type == "all":
        _distribute_ide(project, platform, 1, False)

    if type == "binary" or type == "all":
        _distribute_binary(project, platform, 1, False)

    click.echo("\n✓ Build and distribution complete")


@binaries.command("publish-cli")
@click.option("--project", "-p", "projects", type=click.Choice(list(CLI_PROJECTS.keys())),
              multiple=True, help="CLI project(s) — repeatable (-p a -p b). Omit with --all.")
@click.option("--all", "all_projects", is_flag=True,
              help="Publish every CLI whose source is present on this host.")
@click.option("--local", is_flag=True, help="Publish to local machine (no SSH)")
@click.option("--local-root", default=None, help="Local web root (default: auto-detect Homebrew nginx root)")
@click.option("--instance", "-i", type=int, default=None, help="Target EC2 instance number")
@click.option("--version", default=None, help="Override version (single project only)")
@click.option(
    "--source",
    default=None,
    type=click.Path(file_okay=False, dir_okay=True, exists=True, path_type=Path),
    help="Source dir with pyproject.toml (single project only; default: auto-detect)",
)
@click.option("--dry-run", is_flag=True, help="Show what would be done")
@click.option("--purge", is_flag=True, help="Purge the Cloudflare edge cache for the published URLs "
              "(needs CLOUDFLARE_API_TOKEN/CF_API_TOKEN with Zone:Cache Purge). Use when republishing "
              "a same-version artifact whose immutable cache would otherwise stay stale.")
def publish_cli(projects, all_projects, local, local_root, instance, version, source, dry_run, purge):
    """Build and publish standalone CLI binary(ies) to /var/www/downloads.

    Builds for the current host OS/arch (no cross-compilation). Binary: {project}-{os}-{arch}.
    Handles MULTIPLE projects: repeat -p, or --all (every CLI whose source is on this host).
    """
    if local and instance is not None:
        raise click.ClickException("Use either --local or --instance, not both")
    if not local and instance is None:
        raise click.ClickException("Specify exactly one of: --local or --instance")

    instance_config = None
    if instance is not None:
        instance_config = get_instance(str(instance))
        if not instance_config or not instance_config.ip:
            raise click.ClickException(f"Unknown/invalid instance: {instance}")

    selected = _resolve_projects(projects, all_projects, CLI_PROJECTS, "source_dir")
    if (version or source) and len(selected) != 1:
        raise click.ClickException(
            "--version/--source apply to a single project; omit them for --all/multiple")

    _run_fleet(selected, lambda p: _publish_cli_one(
        p, local, local_root, instance_config, version, source, dry_run, purge), "publish-cli")


def _source_provenance(source_dir: Path) -> dict:
    """Best-effort git provenance for a CLI source tree, stamped into the published
    manifest so a drift probe can later tell whether the shipped binary is stale
    vs current source (lab/client_testing/binary_drift_probe.sh).

    The key field is `cli_tree` — the git tree-object hash of the CLI source dir
    itself (`git rev-parse HEAD:<clidir>`). It changes iff the CLI's *tracked
    content* changes, so it is an exact, timestamp-independent "needs rebuild?"
    signal: a commit that only touches other parts of the repo leaves cli_tree
    unchanged, and a whitespace-free content change always changes it. `dirty`
    flags uncommitted changes in the CLI dir (build not reproducible from a commit).
    """
    def _git(*args):
        try:
            return subprocess.run(
                ["git", "-C", str(source_dir), *args],
                capture_output=True, text=True, check=True,
            ).stdout.strip()
        except Exception:
            return ""

    commit = _git("rev-parse", "HEAD")
    toplevel = _git("rev-parse", "--show-toplevel")
    cli_tree = ""
    if toplevel:
        try:
            rel = source_dir.resolve().relative_to(Path(toplevel).resolve())
            cli_tree = _git("rev-parse", f"HEAD:{rel.as_posix()}") if rel.parts else _git("rev-parse", "HEAD^{tree}")
        except Exception:
            cli_tree = ""
    dirty = bool(_git("status", "--porcelain", "--", str(source_dir)))
    return {"git_commit": commit, "cli_tree": cli_tree, "dirty": dirty}


def _publish_cli_one(project, local, local_root, instance_config, version, source, dry_run, purge):
    """Build + publish ONE CLI binary — the per-project worker for `publish-cli`."""

    # Get project configuration
    proj_config = CLI_PROJECTS[project]
    cli_dir = proj_config["cli_dir"]
    package_name = proj_config["package_name"]
    binary_name_prefix = proj_config["binary_name"]
    install_script_name = proj_config.get("install_script", "")
    lang = proj_config.get("lang", "python")  # "python" (Nuitka) or "rust" (cargo)

    # Resolve source directory
    source_dir = (source or (get_fleet_root() / cli_dir)).expanduser().resolve()
    install_script = source_dir / install_script_name if install_script_name else None

    # Language-specific entry point + version source
    if lang == "rust":
        cargo_path = source_dir / "Cargo.toml"
        if not cargo_path.exists():
            raise click.ClickException(f"Cargo.toml not found: {cargo_path}")
        resolved_version = version or _read_cargo_version(cargo_path)
    else:
        pyproject_path = source_dir / "pyproject.toml"
        entry_point = source_dir / package_name / "main.py"
        if not entry_point.exists():
            raise click.ClickException(f"Entry point not found: {entry_point}")
        resolved_version = version or _read_toml_version(pyproject_path)

    if install_script_name and not (install_script and install_script.exists()):
        click.echo(f"Warning: Install script not found: {install_script}")
        install_script = None
    os_name, arch = _detect_os_arch_for_cli()
    binary_name = f"{binary_name_prefix}-{os_name}-{arch}"
    dist_dir = source_dir / "dist"
    local_binary = dist_dir / binary_name

    click.echo("Publishing CLI:")
    click.echo(f"  project:  {project}")
    click.echo(f"  version:  {resolved_version}")
    click.echo(f"  platform: {os_name}/{arch}")
    click.echo(f"  source:   {source_dir}")
    click.echo(f"  output:   {local_binary}")
    if local:
        # Homebrew nginx default document root: /opt/homebrew/var/www
        default_local_root = None
        if Path("/opt/homebrew/var/www").exists():
            default_local_root = "/opt/homebrew/var/www"
        elif Path("/usr/local/var/www").exists():
            default_local_root = "/usr/local/var/www"
        else:
            default_local_root = str(Path.cwd())

        effective_local_root = local_root or default_local_root
        click.echo(f"  target:   local:{effective_local_root}")
    else:
        click.echo(f"  target:   {instance_config.ssh_host}")

    remote_root = f"/var/www/downloads/{project}" if not local else f"{(local_root or default_local_root).rstrip('/')}/downloads/{project}"
    remote_cli_root = f"{remote_root}/cli"
    remote_release_dir = f"{remote_cli_root}/releases/{resolved_version}"
    remote_binary_path = f"{remote_release_dir}/{binary_name}"
    remote_install_path = f"{remote_cli_root}/install.sh"
    # Moving 'latest' pointer (mirror of newest stable) — see VERSIONING_STANDARDS.md
    remote_latest_dir = f"{remote_cli_root}/releases/latest"

    if dry_run:
        click.echo("\n[DRY RUN] Build:")
        if lang == "rust":
            click.echo(f"  - cargo build --release ({source_dir}) -> {local_binary}")
        else:
            click.echo(f"  - Build {entry_point} -> {local_binary}")
        click.echo("[DRY RUN] Deploy:")
        if install_script:
            click.echo(f"  - {install_script} -> {remote_install_path}")
        click.echo(f"  - {local_binary} -> {remote_binary_path}")
        click.echo(f"  - {local_binary} -> {remote_latest_dir}/{binary_name} (latest mirror)")
        click.echo(f"  - SHA256SUMS -> {remote_release_dir}/ and {remote_latest_dir}/")
        return

    dist_dir.mkdir(parents=True, exist_ok=True)

    if lang == "rust":
        # Build the native release binary with cargo, then stage it as dist/{binary_name}.
        _cargo_build_binary(source_dir, binary_name_prefix, local_binary)
    else:
        _preflight_nuitka_build()  # fail fast on Linux-without-patchelf, before the venv/compile
        # Build in an isolated venv so deps + nuitka are available.
        with tempfile.TemporaryDirectory(prefix="sega-cli-build-") as tmp:
            venv_dir = Path(tmp) / "venv"
            subprocess.run([sys.executable, "-m", "venv", str(venv_dir)], check=True)

            vpy = venv_dir / "bin" / "python"
            if not vpy.exists():
                raise click.ClickException(f"venv python not found at {vpy} (unsupported platform?)")

            def _pip(args: list[str]):
                subprocess.run([str(vpy), "-m", "pip", *args], check=True)

            _pip(["install", "-U", "pip"])
            # setuptools is required in the build venv: with --disable-plugin=
            # anti-bloat, Nuitka's implicit-imports evaluates `version("setuptools")
            # >= (71,)` and FATALs if setuptools is absent (Python 3.12+ venvs no
            # longer seed it — hit on node-5/py3.13 2026-08-17). Harmless on 3.11.
            _pip(["install", "-U", "setuptools"])
            # Use onefile extra to avoid runtime prompts/warnings (e.g. zstandard).
            _pip(["install", "Nuitka[onefile]==2.5.9"])  # pin: newer Nuitka (4.1.3/2.7.x) FATALs on the vtk implicit-import guard; non-monotonic — see SHARED_LESSONS "Nuitka --module/onefile"
            _pip(["install", "Nuitka[onefile]==2.5.9"])
            _pip(["install", "-e", str(source_dir)])

            env = os.environ.copy()
            env["PATH"] = f"{venv_dir / 'bin'}:{env.get('PATH', '')}"

            # Only force-include rich's unicode data if the project actually pulled rich
            # in. Nuitka FATALs on --include-package for a package it can't locate, so a
            # click-only CLI (e.g. atlas) would otherwise fail the whole build.
            nuitka_args = [
                str(vpy), "-m", "nuitka",
                "--standalone", "--onefile", "--follow-imports",
                "--assume-yes-for-downloads",
                # Disable the anti-bloat plugin. It rewrites parts of the
                # certifi -> importlib.resources import chain into a bare
                # `raise ImportError()` (empty message), which crashes EVERY
                # CLI's first network call (httpcore._ssl -> import certifi ->
                # certifi/core.py). Root cause of C8-1, verified with a minimal
                # Nuitka repro on node-1 2026-08-17: with anti-bloat the compiled
                # binary fails `import certifi`; with it disabled, `import certifi`
                # + a real httpx GET both succeed. Costs ~+3.7MB/binary (6.4->10MB),
                # trivial for a CLI — correctness over size.
                "--disable-plugin=anti-bloat",
            ]
            if subprocess.run([str(vpy), "-c", "import rich._unicode_data"], capture_output=True).returncode == 0:
                nuitka_args.append("--include-package=rich._unicode_data")
            # NOTE (2026-08-16): CLIs that import `requests` crash under Nuitka onefile
            # with a bare ImportError at certifi/core.py (certifi's importlib.resources
            # loader). Adding --include-package-data=certifi / --include-package=
            # importlib.resources here was tried and produced a BYTE-IDENTICAL binary
            # (Nuitka already includes them) — it does NOT fix the crash, so it was
            # reverted rather than enshrined as a false fix. The working pattern is to
            # use `httpx` (as atlas/atlas do), which builds and runs cleanly; atlas
            # was migrated off requests. Revisit here only with a verified Nuitka fix.
            nuitka_args += [
                f"--output-dir={dist_dir}",
                f"--output-filename={binary_name}",
                str(entry_point),
            ]
            subprocess.run(
                nuitka_args,
                cwd=str(source_dir),
                env=env,
                check=True,
            )

    if not local_binary.exists():
        raise click.ClickException(f"Build succeeded but output binary not found: {local_binary}")

    # Integrity: write SHA256SUMS next to the binary (format: "<sha256>  <filename>").
    # Same content serves both the versioned dir and the 'latest' mirror (filename is stable).
    sha256 = hashlib.sha256(local_binary.read_bytes()).hexdigest()
    sums_path = dist_dir / "SHA256SUMS"
    sums_path.write_text(f"{sha256}  {binary_name}\n")
    click.echo(f"  sha256:   {sha256}")

    # Build-provenance manifest — records what SOURCE produced this binary so a
    # drift probe can later decide whether the published artifact is stale vs the
    # current source (lab/client_testing/binary_drift_probe.sh). Written next to
    # the binary in both the versioned dir and the latest/ mirror. The source
    # fields are platform-independent, so a same-source build for another platform
    # overwrites it harmlessly.
    from datetime import datetime, timezone
    prov = _source_provenance(source_dir)
    manifest = {
        "project": project,
        "version": resolved_version,
        "platform": f"{os_name}/{arch}",
        "binary": binary_name,
        "sha256": sha256,
        "lang": lang,
        "built_at": datetime.now(timezone.utc).isoformat(),
        **prov,
    }
    manifest_path = dist_dir / "manifest.json"
    manifest_path.write_text(json.dumps(manifest, indent=2) + "\n")
    click.echo(
        f"  source:   commit={(prov['git_commit'] or '?')[:12]} "
        f"cli_tree={(prov['cli_tree'] or '?')[:12]}{' DIRTY' if prov['dirty'] else ''}"
    )

    if local:
        for d in (remote_release_dir, remote_latest_dir):
            Path(d).mkdir(parents=True, exist_ok=True)
            subprocess.run(["cp", str(local_binary), f"{d}/{binary_name}"], check=True)
            subprocess.run(["cp", str(sums_path), f"{d}/SHA256SUMS"], check=True)
            subprocess.run(["cp", str(manifest_path), f"{d}/manifest.json"], check=True)
            subprocess.run(["chmod", "755", f"{d}/{binary_name}"], check=True)
        if install_script and install_script.exists():
            subprocess.run(["cp", str(install_script), remote_install_path], check=True)
            subprocess.run(["chmod", "755", remote_install_path], check=True)
    else:
        # Deploy to instance
        ssh_key = get_ssh_key_path()
        ssh_opts = get_ssh_options()

        tmp_bin = f"/tmp/{binary_name}"
        tmp_sums = f"/tmp/{project}-SHA256SUMS"
        tmp_manifest = f"/tmp/{project}-manifest.json"
        tmp_install = f"/tmp/{project}-install.sh"

        def _scp(local_path: str, remote_tmp: str):
            subprocess.run(
                ["scp", *ssh_opts, "-i", str(ssh_key), local_path, f"{instance_config.ssh_host}:{remote_tmp}"],
                check=True,
            )

        _scp(str(local_binary), tmp_bin)
        _scp(str(sums_path), tmp_sums)
        _scp(str(manifest_path), tmp_manifest)
        if install_script and install_script.exists():
            _scp(str(install_script), tmp_install)

        # Versioned dir is the source of truth; latest/ is a mirror of it.
        deploy_cmds = (
            f"sudo mkdir -p '{remote_release_dir}' '{remote_latest_dir}' '{remote_cli_root}' && "
            f"sudo mv '{tmp_bin}' '{remote_binary_path}' && sudo chmod 755 '{remote_binary_path}' && "
            f"sudo mv '{tmp_sums}' '{remote_release_dir}/SHA256SUMS' && "
            f"sudo mv '{tmp_manifest}' '{remote_release_dir}/manifest.json' && "
            f"sudo cp '{remote_binary_path}' '{remote_latest_dir}/{binary_name}' && "
            f"sudo cp '{remote_release_dir}/SHA256SUMS' '{remote_latest_dir}/SHA256SUMS' && "
            f"sudo cp '{remote_release_dir}/manifest.json' '{remote_latest_dir}/manifest.json'"
        )

        if install_script and install_script.exists():
            deploy_cmds += (
                f" && sudo mv '{tmp_install}' '{remote_install_path}' && sudo chmod 755 '{remote_install_path}'"
            )

        deploy_cmds += (
            f" && sudo chown -R www-data:www-data '{remote_root}' && sudo chmod -R 755 '{remote_root}'"
        )

        subprocess.run(
            ["ssh", *ssh_opts, "-i", str(ssh_key), instance_config.ssh_host, deploy_cmds],
            check=True,
        )

    click.echo("\n✓ Published")
    if install_script and install_script.exists():
        click.echo(f"  install:  {remote_install_path}")
    click.echo(f"  binary:   {remote_binary_path}")
    click.echo(f"  latest:   {remote_latest_dir}/{binary_name}")
    click.echo(f"  checksum: {remote_release_dir}/SHA256SUMS")

    if purge:
        try:
            from .downloads import PROJECT_DOMAINS
            dom = PROJECT_DOMAINS.get(project)
        except Exception:
            dom = None
        if not dom:
            click.echo("  ⚠ --purge: no download domain mapped for project; skipping")
        else:
            base = f"https://downloads.{dom}/cli"
            _purge_cloudflare_cache(dom, [
                f"{base}/releases/{resolved_version}/{binary_name}",
                f"{base}/releases/latest/{binary_name}",
                f"{base}/releases/{resolved_version}/SHA256SUMS",
                f"{base}/releases/latest/SHA256SUMS",
                f"{base}/install.sh",
            ])


# =============================================================================
# Engine Asset Functions (obfuscated, importable engine packages)
# =============================================================================

# Engines shipped as DOWNLOADABLE, OBFUSCATED packages (the crown-jewel physics — NOT
# the web app). Python engines compile to an importable `<pkg>.so` via Nuitka --module
# (machine code; no `.py` source delivered) wrapped in a pip wheel that still `import`s
# normally. Rust engines ship as a stripped release binary (already native machine code;
# no source obfuscator needed — strip symbols via the Cargo release profile).
# Canonical: common/docs/ENGINE_PACKAGING_AND_PROTECTION_STANDARD.md.
# Config-derived (config/sega.toml `[build.engine.*]`). Rebuilt into the historical
# dict shape: python entries carry `package`; rust entries carry `binary_name` (Cargo
# [[bin]]; version read from Cargo.toml) and optional `features`. The build type is
# stored as `tool` in config and surfaced here as the `lang` key (callers do
# .get("lang", "python")); heterogeneous per-lang keys are passed through as-is.
def _build_engine_projects() -> Dict[str, dict]:
    out: Dict[str, dict] = {}
    for name, e in get_config().build.engine.items():
        entry = {k: v for k, v in e.items() if k != "tool"}
        entry["lang"] = e.get("tool", "python")
        out[name] = entry
    return out


ENGINE_PROJECTS: Dict[str, dict] = _build_engine_projects()


def _read_toml_deps(pyproject_path: Path) -> list[str]:
    """Read [project].dependencies so the compiled wheel can declare them as
    Requires-Dist. Nuitka --module keeps third-party deps EXTERNAL (we compile only our
    own source, not numpy/torch/etc.), so the wheel must pull them at install time."""
    try:
        import tomllib
        data = tomllib.loads(pyproject_path.read_text())
        return list(data.get("project", {}).get("dependencies", []) or [])
    except Exception:
        return []


# Wheel assembly runs INSIDE the build venv (via its interpreter) so the wheel's
# python/abi/platform tag matches the interpreter that built the .so. A wheel is just a
# zip with a dist-info dir, so no build backend is needed — but `packaging` must be
# importable in the venv (installed alongside Nuitka).
_WHEEL_BUILDER_SRC = r'''
import base64, csv, hashlib, io, json, sys, zipfile
from pathlib import Path
from packaging.tags import sys_tags

so_path, dist, version, dest, req_json = sys.argv[1:6]
reqs = json.loads(req_json)
so_path = Path(so_path); dest = Path(dest)
so_name = so_path.name  # e.g. atlas.cpython-313-darwin.so (importable top-level module)

tag = next(iter(sys_tags()))
tagstr = f"{tag.interpreter}-{tag.abi}-{tag.platform}"
norm = dist.replace("-", "_")
distinfo = f"{norm}-{version}.dist-info"
wheel_name = f"{norm}-{version}-{tagstr}.whl"

def rec(path, data):
    h = base64.urlsafe_b64encode(hashlib.sha256(data).digest()).rstrip(b"=").decode()
    return (path, f"sha256={h}", str(len(data)))

metadata = f"Metadata-Version: 2.1\nName: {dist}\nVersion: {version}\n"
metadata += "Summary: FLEET compiled engine (obfuscated; source not distributed)\n"
for r in reqs:
    metadata += f"Requires-Dist: {r}\n"
metadata = metadata.encode()
wheelmeta = (f"Wheel-Version: 1.0\nGenerator: sega-publish-engine\n"
             f"Root-Is-Purelib: false\nTag: {tagstr}\n").encode()
so_data = so_path.read_bytes()

records = [rec(so_name, so_data), rec(f"{distinfo}/METADATA", metadata),
           rec(f"{distinfo}/WHEEL", wheelmeta)]
buf = io.StringIO()
w = csv.writer(buf, lineterminator="\n"); w.writerows(records)
w.writerow([f"{distinfo}/RECORD", "", ""])
record_data = buf.getvalue().encode()

dest.mkdir(parents=True, exist_ok=True)
out = dest / wheel_name
with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as z:
    z.writestr(so_name, so_data)
    z.writestr(f"{distinfo}/METADATA", metadata)
    z.writestr(f"{distinfo}/WHEEL", wheelmeta)
    z.writestr(f"{distinfo}/RECORD", record_data)
print(str(out))
'''


# Assembles the PATCH-PORTABLE dual-band wheel: <pkg>/_abi/<pkg>_{hi,lo}.so (the two
# opaque Nuitka builds) + <pkg>/__init__.py (the version-selecting loader shim). Runs
# under the build interpreter so packaging.tags yields the correct cp313 linux tag.
_DUALBAND_WHEEL_BUILDER_SRC = r'''
import base64, csv, hashlib, io, json, sys, zipfile
from pathlib import Path
from packaging.tags import sys_tags

pkg, dist, version, dest, hi_so, lo_so, shim, req_json = sys.argv[1:9]
reqs = json.loads(req_json)
dest = Path(dest)

tag = next(iter(sys_tags()))
tagstr = f"{tag.interpreter}-{tag.abi}-{tag.platform}"
norm = dist.replace("-", "_")
distinfo = f"{norm}-{version}.dist-info"
wheel_name = f"{norm}-{version}-{tagstr}.whl"

def rec(path, data):
    h = base64.urlsafe_b64encode(hashlib.sha256(data).digest()).rstrip(b"=").decode()
    return (path, f"sha256={h}", str(len(data)))

metadata = f"Metadata-Version: 2.1\nName: {dist}\nVersion: {version}\n"
metadata += "Summary: FLEET compiled engine (obfuscated; source not distributed)\n"
for r in reqs:
    metadata += f"Requires-Dist: {r}\n"
metadata = metadata.encode()
wheelmeta = (f"Wheel-Version: 1.0\nGenerator: sega-publish-engine-dualband\n"
             f"Root-Is-Purelib: false\nTag: {tagstr}\n").encode()

hi_data = Path(hi_so).read_bytes()
lo_data = Path(lo_so).read_bytes()
shim_data = Path(shim).read_bytes()

members = [
    (f"{pkg}/__init__.py", shim_data),
    (f"{pkg}/_abi/{pkg}_hi.so", hi_data),
    (f"{pkg}/_abi/{pkg}_lo.so", lo_data),
    (f"{distinfo}/METADATA", metadata),
    (f"{distinfo}/WHEEL", wheelmeta),
]
records = [rec(p, d) for p, d in members]
buf = io.StringIO()
w = csv.writer(buf, lineterminator="\n"); w.writerows(records)
w.writerow([f"{distinfo}/RECORD", "", ""])
record_data = buf.getvalue().encode()

dest.mkdir(parents=True, exist_ok=True)
out = dest / wheel_name
with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as z:
    for p, d in members:
        z.writestr(p, d)
    z.writestr(f"{distinfo}/RECORD", record_data)
print(str(out))
'''


# -- Patch-portability across CPython 3.13.x (the E2+E3 orion SIGSEGV fix) --------
#
# Nuitka `--module` compiles against CPython INTERNAL structs (`_PyRuntime`, thread/
# interpreter state) and bakes their FIELD OFFSETS into the machine code. Those offsets
# shifted at **CPython 3.13.12**, so a single `.so` built on one side of that boundary
# SIGSEGVs in `PyInit_<pkg>` (before any Python runs) when imported on the other side —
# despite the shared `cp313` wheel tag (Nuitka does not use the stable/limited ABI).
# Proven on node-5 2026-09-11: a .so built on 3.13.14 imports clean on 3.13.12/14/15 but
# crashes (exit 139) on 3.13.0–3.13.11, and vice-versa. Newer Nuitka (2.7.16) does NOT
# fix it (same split) and re-triggers the vtk guard bug — so the .so itself cannot be
# made patch-portable.
#
# Durable fix: ship BOTH bands in one wheel (two opaque Nuitka .so, no source leak) plus
# a tiny pure-python loader `__init__.py` that selects the matching band at import time by
# `sys.version_info`. One wheel, one `pip install`, one `import <pkg>`, works across the
# whole 3.13.x range. Enforcement is unaffected: the loaded module is still the compiled
# .so (its `__compiled__`/`.so` self-signals hold), the shim carries zero engine logic.
#
# ONLY applies to Linux CPython 3.13 builds (where the boundary bites and both interpreter
# bands are reachable). To enable, point SEGA_ENGINE_ABI_LO_PYTHON at a CPython whose patch
# is <= 3.13.11 (e.g. `uv python install 3.13.11`); the host interpreter (this build) must
# be the >= 3.13.12 band. When the env is unset the build falls back to the historical
# single-band wheel (unchanged behavior for every other engine/host).
ABI_SPLIT_313 = (3, 13, 12)  # first patch on the "hi" side of the internal-ABI boundary

_DUALBAND_SHIM_SRC = '''\
"""{pkg} engine loader — patch-portable across CPython 3.13.x.

The engine ships as two opaque Nuitka --module builds, one per CPython 3.13 ABI band.
Nuitka bakes CPython internal-struct field offsets into machine code; those offsets
shifted at CPython {split_str}, so a single .so SIGSEGVs on the other band. This loader
selects the matching band at import time. No engine source ships (both bands are .so).
"""
import sys as _sys, os as _os, importlib.util as _u, importlib.machinery as _m
_here = _os.path.dirname(__file__)
_band = "hi" if _sys.version_info[:3] >= {split_tuple!r} else "lo"
_so = _os.path.join(_here, "_abi", "{pkg}_%s.so" % _band)
if not _os.path.exists(_so):
    raise ImportError("{pkg}: missing ABI band artifact: %s" % _so)
_loader = _m.ExtensionFileLoader("{pkg}", _so)
_spec = _u.spec_from_loader("{pkg}", _loader, origin=_so)
_mod = _u.module_from_spec(_spec)
# Bind THIS module name to the compiled module BEFORE exec so PyInit_ binds correctly.
_sys.modules["{pkg}"] = _mod
_loader.exec_module(_mod)
'''


def _nuitka_module_so(vpy: Path, engine_dir: Path, pkg: str, out_dir: Path) -> Path:
    """Run one Nuitka `--module` build of <engine_dir>/<pkg> using interpreter `vpy`,
    returning the produced `<pkg>*.so`. The interpreter's CPython patch fixes the .so's
    ABI band."""
    def _pip(args: list[str]):
        subprocess.run([str(vpy), "-m", "pip", *args], check=True)

    _pip(["install", "-U", "pip"])
    # Pin Nuitka to the 2.5–2.6 band. Both 4.1.3 (latest) and 2.7.x FATAL on the
    # implicit-imports vtk guard (`version("vtk") >= (9,)` → `None >= tuple`) when vtk
    # isn't installed; 2.4.x fails differently. The bug is NON-MONOTONIC by version, so
    # do NOT "just use latest". 2.5.9 verified across engines. See
    # common/docs/ENGINE_PACKAGING_AND_PROTECTION_STANDARD.md.
    _pip(["install", "Nuitka==2.5.9", "packaging", "wheel"])
    # Install the engine (editable) WITHOUT its deps. Nuitka --module does static
    # analysis (it doesn't execute the package), so third-party deps (numpy/scipy/torch)
    # need NOT be present — they stay external in the .so and are declared as Requires-Dist
    # for the customer's install. --no-deps also avoids fragile source-builds in the fresh
    # venv (e.g. hermes's scipy → "OpenBLAS not found") and skips re-pulling torch every build.
    _pip(["install", "-e", str(engine_dir), "--no-deps"])

    out_dir.mkdir(parents=True, exist_ok=True)
    subprocess.run(
        [str(vpy), "-m", "nuitka", "--module",
         f"--include-package={pkg}",
         "--assume-yes-for-downloads",
         f"--output-dir={out_dir}",
         str(engine_dir / pkg)],
        cwd=str(engine_dir), check=True,
    )
    so_files = list(out_dir.glob(f"{pkg}*.so"))
    if not so_files:
        raise click.ClickException(
            f"Nuitka --module produced no {pkg}*.so in {out_dir} "
            f"(found: {[p.name for p in out_dir.iterdir()]})")
    return so_files[0]


def _dualband_lo_python() -> Optional[Path]:
    """The <=3.13.11 interpreter for the 'lo' ABI band, if dual-band is applicable.

    Returns None (→ single-band build) unless: this is a Linux CPython 3.13 host on the
    'hi' band (>= 3.13.12) AND SEGA_ENGINE_ABI_LO_PYTHON points at a runnable <=3.13.11
    CPython. Keeps the fix opt-in and scoped to the affected ABI class only."""
    if sys.platform != "linux" or sys.version_info[:2] != (3, 13):
        return None
    if sys.version_info[:3] < ABI_SPLIT_313:
        return None  # host is itself the 'lo' band; would need a 'hi' helper instead
    lo = os.environ.get("SEGA_ENGINE_ABI_LO_PYTHON")
    if not lo:
        return None
    lo_path = Path(lo).expanduser()
    if not lo_path.exists():
        raise click.ClickException(f"SEGA_ENGINE_ABI_LO_PYTHON does not exist: {lo_path}")
    try:
        out = subprocess.run([str(lo_path), "-c",
                              "import sys;print('.'.join(map(str,sys.version_info[:3])))"],
                             check=True, capture_output=True, text=True).stdout.strip()
        lo_ver = tuple(int(x) for x in out.split("."))
    except Exception as e:
        raise click.ClickException(f"SEGA_ENGINE_ABI_LO_PYTHON not runnable ({lo_path}): {e}")
    if lo_ver[:2] != (3, 13) or lo_ver >= ABI_SPLIT_313:
        raise click.ClickException(
            f"SEGA_ENGINE_ABI_LO_PYTHON must be CPython <= 3.13.11 (the 'lo' band); got {out}")
    return lo_path


def _build_engine_wheel(engine_dir: Path, pkg: str, dist_name: str, version: str,
                        dist_dir: Path) -> Path:
    """Compile <engine_dir>/<pkg> to an importable, obfuscated `<pkg>.so` via Nuitka
    --module and wrap it in a pip wheel. Returns the wheel path. No `.py` is shipped.

    On Linux CPython 3.13 with SEGA_ENGINE_ABI_LO_PYTHON set, builds a PATCH-PORTABLE
    dual-band wheel (see the ABI_SPLIT_313 note above); otherwise the historical
    single-band wheel."""
    _preflight_nuitka_build()  # fail fast on Linux-without-patchelf, before the venv/compile
    pkg_source = engine_dir / pkg
    if not (pkg_source / "__init__.py").exists():
        raise click.ClickException(f"Engine package not found: {pkg_source}/__init__.py")
    reqs = _read_toml_deps(engine_dir / "pyproject.toml")

    lo_python = _dualband_lo_python()

    with tempfile.TemporaryDirectory(prefix="sega-engine-build-") as tmp:
        venv_dir = Path(tmp) / "venv"
        subprocess.run([sys.executable, "-m", "venv", str(venv_dir)], check=True)
        vpy = venv_dir / "bin" / "python"
        if not vpy.exists():
            raise click.ClickException(f"venv python not found at {vpy}")

        # 'hi' band (this build interpreter, >= 3.13.12 when dual-band; else whatever host).
        hi_so = _nuitka_module_so(vpy, engine_dir, pkg, Path(tmp) / "nuitka-hi")

        if lo_python is None:
            # Historical single-band wheel — unchanged behavior.
            wheel_script = Path(tmp) / "mkwheel.py"
            wheel_script.write_text(_WHEEL_BUILDER_SRC)
            import json as _json
            result = subprocess.run(
                [str(vpy), str(wheel_script), str(hi_so), dist_name, version,
                 str(dist_dir), _json.dumps(reqs)],
                check=True, capture_output=True, text=True,
            )
            wheel_path = Path(result.stdout.strip().splitlines()[-1])
            if not wheel_path.exists():
                raise click.ClickException(f"Wheel assembly reported {wheel_path} but it is missing")
            return wheel_path

        # Dual-band: build the 'lo' (<=3.13.11) .so in its own venv, then assemble a wheel
        # with both .so + the version-selecting loader shim.
        click.echo(f"  dual-band: building 'lo' band (<= 3.13.11) via {lo_python}")
        lo_venv = Path(tmp) / "venv-lo"
        subprocess.run([str(lo_python), "-m", "venv", str(lo_venv)], check=True)
        lo_vpy = lo_venv / "bin" / "python"
        lo_so = _nuitka_module_so(lo_vpy, engine_dir, pkg, Path(tmp) / "nuitka-lo")

        wheel_script = Path(tmp) / "mkwheel_dualband.py"
        wheel_script.write_text(_DUALBAND_WHEEL_BUILDER_SRC)
        shim_src = _DUALBAND_SHIM_SRC.format(
            pkg=pkg, split_tuple=ABI_SPLIT_313,
            split_str=".".join(map(str, ABI_SPLIT_313)))
        shim_path = Path(tmp) / "shim__init__.py"
        shim_path.write_text(shim_src)
        import json as _json
        result = subprocess.run(
            [str(vpy), str(wheel_script), pkg, dist_name, version, str(dist_dir),
             str(hi_so), str(lo_so), str(shim_path), _json.dumps(reqs)],
            check=True, capture_output=True, text=True,
        )
        wheel_path = Path(result.stdout.strip().splitlines()[-1])
        if not wheel_path.exists():
            raise click.ClickException(f"Dual-band wheel assembly reported {wheel_path} but it is missing")
        return wheel_path


def _resolve_projects(projects: tuple, all_projects: bool, registry: Dict, dir_key: str) -> List[str]:
    """Resolve the -p/--all selection into a concrete project list.

    --all is HOST-AWARE: it selects every registry project whose SOURCE dir is actually
    present on this machine (a mini only holds a subset of the fleet), so `--all` builds
    exactly what can be built here. -p is repeatable (deduped, order preserved).
    """
    if all_projects and projects:
        raise click.ClickException("Use --all or -p, not both")
    if all_projects:
        present = [p for p, cfg in registry.items()
                   if (get_fleet_root() / cfg[dir_key]).expanduser().exists()]
        if not present:
            raise click.ClickException("--all: no project sources found on this host")
        return present
    if projects:
        return list(dict.fromkeys(projects))
    raise click.ClickException("Specify -p <project> (repeatable) or --all")


def _run_fleet(selected: List[str], build_one, label: str) -> None:
    """Run build_one(project) for each selected project. Isolates per-project failures
    (one bad project doesn't abort the rest), prints a summary for multi-project runs,
    and exits nonzero if any project failed."""
    multi = len(selected) > 1
    results: List[tuple] = []
    for i, p in enumerate(selected, 1):
        if multi:
            click.echo(f"\n{'=' * 8} {label}: {p} ({i}/{len(selected)}) {'=' * 8}")
        try:
            build_one(p)
            results.append((p, None))
        except Exception as e:  # isolate: keep going so one failure doesn't sink the batch
            click.echo(f"  ✗ {p} FAILED: {e}", err=True)
            results.append((p, str(e)))
    if multi:
        ok = sum(1 for _, e in results if e is None)
        click.echo(f"\n=== {label} summary: {ok}/{len(results)} succeeded ===")
        for p, e in results:
            click.echo(f"  {'✓' if e is None else '✗'} {p}" + (f" — {e}" if e else ""))
    if any(e is not None for _, e in results):
        raise SystemExit(1)


@binaries.command("publish-engine")
@click.option("--project", "-p", "projects", type=click.Choice(list(ENGINE_PROJECTS.keys())),
              multiple=True, help="Engine project(s) — repeatable (-p a -p b). Omit with --all.")
@click.option("--all", "all_projects", is_flag=True,
              help="Publish every engine whose source is present on this host.")
@click.option("--local", is_flag=True, help="Publish to local machine (no SSH)")
@click.option("--local-root", default=None, help="Local web root (default: auto-detect nginx root)")
@click.option("--instance", "-i", type=int, default=None, help="Target EC2 instance number")
@click.option("--version", default=None, help="Override version (single project only)")
@click.option("--dry-run", is_flag=True, help="Show what would be done")
@click.option("--purge", is_flag=True, help="Purge Cloudflare edge cache for the published URLs")
def publish_engine(projects, all_projects, local, local_root, instance, version, dry_run, purge):
    """Build and publish OBFUSCATED, downloadable engine package(s).

    Python engines -> Nuitka --module -> importable `<pkg>.so` in a pip wheel (NO `.py`
    delivered). Rust engines -> stripped `cargo --release` binary. Published to
    downloads.<domain>/engine/releases/<version>/. Handles MULTIPLE projects: repeat -p,
    or --all (every engine whose source is on this host).
    """
    if local and instance is not None:
        raise click.ClickException("Use either --local or --instance, not both")
    if not local and instance is None:
        raise click.ClickException("Specify exactly one of: --local or --instance")

    instance_config = None
    if instance is not None:
        instance_config = get_instance(str(instance))
        if not instance_config or not instance_config.ip:
            raise click.ClickException(f"Unknown/invalid instance: {instance}")

    selected = _resolve_projects(projects, all_projects, ENGINE_PROJECTS, "engine_dir")
    if version and len(selected) != 1:
        raise click.ClickException(
            "--version applies to a single project; omit it for --all/multiple (each reads its manifest)")

    _run_fleet(selected, lambda p: _publish_engine_one(
        p, local, local_root, instance_config, version, dry_run, purge), "publish-engine")


def _publish_engine_one(project, local, local_root, instance_config, version, dry_run, purge):
    """Build + publish ONE engine — the per-project worker for `publish-engine`."""
    proj = ENGINE_PROJECTS[project]
    lang = proj.get("lang", "python")
    engine_dir = (get_fleet_root() / proj["engine_dir"]).expanduser().resolve()
    if not engine_dir.exists():
        raise click.ClickException(f"Engine dir not found: {engine_dir}")
    os_name, arch = _detect_os_arch_for_cli()

    if lang == "rust":
        cargo_path = engine_dir / "Cargo.toml"
        if not cargo_path.exists():
            raise click.ClickException(f"Cargo.toml not found: {cargo_path}")
        resolved_version = version or _read_cargo_version(cargo_path)
        artifact_name = f"{proj['binary_name']}-{os_name}-{arch}"
    else:
        pyproject_path = engine_dir / "pyproject.toml"
        if not pyproject_path.exists():
            raise click.ClickException(f"pyproject.toml not found: {pyproject_path}")
        resolved_version = version or _read_toml_version(pyproject_path)
        artifact_name = None  # wheel name (with interpreter tag) is known post-build

    default_local_root = None
    if local:
        if Path("/opt/homebrew/var/www").exists():
            default_local_root = "/opt/homebrew/var/www"
        elif Path("/usr/local/var/www").exists():
            default_local_root = "/usr/local/var/www"
        else:
            default_local_root = str(Path.cwd())
    effective_local_root = local_root or default_local_root

    remote_root = (f"/var/www/downloads/{project}" if not local
                   else f"{effective_local_root.rstrip('/')}/downloads/{project}")
    remote_engine_root = f"{remote_root}/engine"
    remote_release_dir = f"{remote_engine_root}/releases/{resolved_version}"
    remote_latest_dir = f"{remote_engine_root}/releases/latest"

    click.echo("Publishing ENGINE (obfuscated):")
    click.echo(f"  project:  {project}")
    click.echo(f"  version:  {resolved_version}")
    click.echo(f"  platform: {os_name}/{arch}")
    click.echo(f"  lang:     {lang}")
    click.echo(f"  source:   {engine_dir}")
    click.echo(f"  target:   {'local:' + effective_local_root if local else instance_config.ssh_host}")

    if dry_run:
        click.echo("\n[DRY RUN] Build:")
        if lang == "rust":
            click.echo(f"  - cargo build --release (strip via profile) -> {artifact_name}")
        else:
            click.echo(f"  - nuitka --module {proj['package']} -> {proj['package']}.so -> pip wheel")
        click.echo(f"[DRY RUN] Deploy -> {remote_release_dir}/ (+ latest mirror) + SHA256SUMS")
        return

    dist_dir = engine_dir / "dist"
    dist_dir.mkdir(parents=True, exist_ok=True)

    if lang == "rust":
        local_artifact = dist_dir / artifact_name
        # _cargo_build_binary builds --release; strip is applied via the crate's
        # [profile.release] strip = true (at the WORKSPACE ROOT — member profiles are ignored).
        # The DISTRIBUTION engine build ALWAYS enables the `licensed` feature so the compiled
        # license/access gate enforces (compile-time build provenance, not a runtime bypass;
        # internal `cargo build` omits it → gate no-ops). Merged with any project required-
        # features (e.g. orion-engine needs `marl`).
        _dist_features = ",".join(f for f in [proj.get("features"), "licensed"] if f)
        _cargo_build_binary(engine_dir, proj["binary_name"], local_artifact, _dist_features)
    else:
        local_artifact = _build_engine_wheel(
            engine_dir, proj["package"], project, resolved_version, dist_dir)
        artifact_name = local_artifact.name

    if not local_artifact.exists():
        raise click.ClickException(f"Build succeeded but artifact missing: {local_artifact}")

    sha256 = hashlib.sha256(local_artifact.read_bytes()).hexdigest()
    sums_path = dist_dir / "SHA256SUMS"
    sums_path.write_text(f"{sha256}  {artifact_name}\n")
    click.echo(f"  artifact: {artifact_name}")
    click.echo(f"  sha256:   {sha256}")

    # Drift manifest (mirrors publish-cli): provenance + src_trees so
    # surface_health_probe can flag a published engine that fell behind source
    # (the atlas wheel sat ~684 commits stale with no signal, 2026-09-02).
    prov = _source_provenance(engine_dir)
    eng_manifest = {
        "project": project, "version": resolved_version,
        "platform": f"{os_name}/{arch}", "artifact": artifact_name,
        "sha256": sha256, "lang": lang,
        "built_at": datetime.now(timezone.utc).isoformat(),
        **prov, "src_trees": {"engine": prov.get("cli_tree", "")},
    }
    eng_manifest_path = dist_dir / "manifest.json"
    eng_manifest_path.write_text(json.dumps(eng_manifest, indent=2) + "\n")
    click.echo(f"  source:   commit={(prov['git_commit'] or '?')[:12]} "
               f"engine_tree={(prov['cli_tree'] or '?')[:12]}{' DIRTY' if prov['dirty'] else ''}")

    def _merge_sums(dest_dir: str) -> None:
        """Write SHA256SUMS preserving OTHER artifacts' lines (a darwin publish must
        not strand the linux wheel line — the E1 single-platform clobber class)."""
        dest = Path(dest_dir) / "SHA256SUMS"
        lines = {artifact_name: f"{sha256}  {artifact_name}"}
        if dest.exists():
            for ln in dest.read_text().splitlines():
                parts = ln.split(None, 1)
                if len(parts) == 2 and parts[1].strip() != artifact_name:
                    lines[parts[1].strip()] = ln
        dest.write_text("\n".join(lines.values()) + "\n")

    if local:
        for d in (remote_release_dir, remote_latest_dir):
            Path(d).mkdir(parents=True, exist_ok=True)
            subprocess.run(["cp", str(local_artifact), f"{d}/{artifact_name}"], check=True)
            _merge_sums(d)
            subprocess.run(["cp", str(eng_manifest_path), f"{d}/manifest.json"], check=True)
    else:
        ssh_key = get_ssh_key_path()
        ssh_opts = get_ssh_options()
        tmp_art = f"/tmp/{artifact_name}"
        tmp_sums = f"/tmp/{project}-engine-SHA256SUMS"

        def _scp(local_path: str, remote_tmp: str):
            subprocess.run(["scp", *ssh_opts, "-i", str(ssh_key), local_path,
                            f"{instance_config.ssh_host}:{remote_tmp}"], check=True)

        _scp(str(local_artifact), tmp_art)
        _scp(str(sums_path), tmp_sums)
        deploy_cmds = (
            f"sudo mkdir -p '{remote_release_dir}' '{remote_latest_dir}' && "
            f"sudo mv '{tmp_art}' '{remote_release_dir}/{artifact_name}' && "
            f"sudo mv '{tmp_sums}' '{remote_release_dir}/SHA256SUMS' && "
            f"sudo cp '{remote_release_dir}/{artifact_name}' '{remote_latest_dir}/{artifact_name}' && "
            f"sudo cp '{remote_release_dir}/SHA256SUMS' '{remote_latest_dir}/SHA256SUMS' && "
            f"sudo chown -R www-data:www-data '{remote_root}' && sudo chmod -R 755 '{remote_root}'"
        )
        subprocess.run(["ssh", *ssh_opts, "-i", str(ssh_key), instance_config.ssh_host,
                        deploy_cmds], check=True)

    click.echo("\n✓ Published (obfuscated engine)")
    click.echo(f"  artifact: {remote_release_dir}/{artifact_name}")
    click.echo(f"  latest:   {remote_latest_dir}/{artifact_name}")
    click.echo(f"  checksum: {remote_release_dir}/SHA256SUMS")

    if purge:
        try:
            from .downloads import PROJECT_DOMAINS
            dom = PROJECT_DOMAINS.get(project)
        except Exception:
            dom = None
        if not dom:
            click.echo("  ⚠ --purge: no download domain mapped for project; skipping")
        else:
            base = f"https://downloads.{dom}/engine"
            _purge_cloudflare_cache(dom, [
                f"{base}/releases/{resolved_version}/{artifact_name}",
                f"{base}/releases/latest/{artifact_name}",
                f"{base}/releases/{resolved_version}/SHA256SUMS",
                f"{base}/releases/latest/SHA256SUMS",
            ])


def _present_projects(registry: Dict, dir_key: str) -> List[str]:
    """Projects in the registry whose source dir exists on this host (no raise; may be empty)."""
    return [p for p, cfg in registry.items()
            if (get_fleet_root() / cfg[dir_key]).expanduser().exists()]


@binaries.command("publish-all")
@click.option("--local", is_flag=True, help="Publish to local machine (no SSH)")
@click.option("--local-root", default=None, help="Local web root (default: auto-detect nginx root)")
@click.option("--instance", "-i", type=int, default=None, help="Target EC2 instance number")
@click.option("--dry-run", is_flag=True, help="Show what would be done")
@click.option("--purge", is_flag=True, help="Purge Cloudflare edge cache for the published URLs")
@click.option("--engines-only", is_flag=True, help="Only engines (skip CLIs)")
@click.option("--clis-only", is_flag=True, help="Only CLIs (skip engines)")
def publish_all(local, local_root, instance, dry_run, purge, engines_only, clis_only):
    """Build + publish EVERY engine and CLI whose source is present on THIS host — one command.

    Host-aware: a mini holds only a subset of the fleet, so this builds exactly what's checked
    out here. Per-project failures are isolated; a summary prints at the end. Each artifact reads
    its own version from its manifest. For a single project or overrides, use publish-engine /
    publish-cli directly.
    """
    if local and instance is not None:
        raise click.ClickException("Use either --local or --instance, not both")
    if not local and instance is None:
        raise click.ClickException("Specify exactly one of: --local or --instance")
    if engines_only and clis_only:
        raise click.ClickException("Use --engines-only or --clis-only, not both")

    instance_config = None
    if instance is not None:
        instance_config = get_instance(str(instance))
        if not instance_config or not instance_config.ip:
            raise click.ClickException(f"Unknown/invalid instance: {instance}")

    engines = [] if clis_only else _present_projects(ENGINE_PROJECTS, "engine_dir")
    clis = [] if engines_only else _present_projects(CLI_PROJECTS, "source_dir")
    if not engines and not clis:
        raise click.ClickException("No engine or CLI sources found on this host")

    # Map display label -> (kind, project) so one _run_fleet handles both surfaces with isolation.
    combined = {f"engine:{p}": ("engine", p) for p in engines}
    combined.update({f"cli:{p}": ("cli", p) for p in clis})
    click.echo(f"publish-all on this host: {len(engines)} engine(s) + {len(clis)} CLI(s)")

    def build_one(label):
        kind, p = combined[label]
        if kind == "engine":
            _publish_engine_one(p, local, local_root, instance_config, None, dry_run, purge)
        else:
            _publish_cli_one(p, local, local_root, instance_config, None, None, dry_run, purge)

    _run_fleet(list(combined.keys()), build_one, "publish-all")


# =============================================================================
# Desktop Asset Functions (Electron)
# =============================================================================


def _build_desktop(project: Optional[str], platform: str, local: bool, skip_frontend: bool, skip_backend: bool):
    """Build desktop Electron applications."""
    projects = [project] if project else DESKTOP_PROJECTS

    click.echo(f"Building desktop binaries for: {', '.join(projects)}")

    # Informational config cross-check (never alters the build set): surface drift between
    # the curated DESKTOP_PROJECTS and the config `has_desktop` flag so the two can be
    # reconciled over time. DESKTOP_PROJECTS remains authoritative for what builds.
    if not project:
        cfg_desktop = set(_config_desktop_projects())
        if cfg_desktop:
            missing_flag = [p for p in projects if p not in cfg_desktop]
            if missing_flag:
                click.echo(
                    "  ⓘ config has_desktop does not flag: "
                    f"{', '.join(missing_flag)} (building anyway per curated list)")

    if local:
        _build_desktop_local(projects, platform, skip_frontend, skip_backend)
    else:
        _build_desktop_on_instance(projects, platform, skip_frontend, skip_backend)


def _clean_pyinstaller_cache() -> None:
    """Remove PyInstaller's regenerable bincache before a desktop build.

    PyInstaller caches processed dylibs in ~/Library/Application Support/pyinstaller
    (macOS) / ~/.cache/pyinstaller (Linux). A stale/corrupt cached dylib (classically
    Pillow's liblzma.5.dylib on arm64) makes build:backend fail with
    "SystemError: Failed to process binary …", which then ships a desktop app WITHOUT
    its bundled backend → the app launches to a splash and quits on backend timeout.
    Clearing the cache (it is fully regenerated on the next build) is the reliable fix,
    and doing it here protects EVERY desktop project's build, not just the one that hit it.
    """
    for cache in (Path.home() / "Library/Application Support/pyinstaller",
                  Path.home() / ".cache/pyinstaller"):
        if cache.exists():
            shutil.rmtree(cache, ignore_errors=True)
            click.echo(f"  cleared pyinstaller cache: {cache}")


def _purge_cloudflare_cache(domain: str, urls: List[str]) -> None:
    """Best-effort Cloudflare edge-cache purge for the given URLs (stdlib only).

    Reads CLOUDFLARE_API_TOKEN / CF_API_TOKEN from the environment; the token needs
    Zone:Cache Purge. Never raises — a missing token or missing permission is reported
    and skipped so it can't fail a publish.
    """
    import json as _json
    import urllib.request as _u
    import urllib.error as _ue

    token = os.environ.get("CLOUDFLARE_API_TOKEN") or os.environ.get("CF_API_TOKEN")
    if not token:
        # Fallback: the committed FLEET keys doc (present on all fleet hosts under ~/fleet/keys).
        keys_doc = get_fleet_root() / "keys" / "CLOUDFLARE_TOKENS.md"
        if keys_doc.exists():
            m = re.search(r"cfat_[A-Za-z0-9]+", keys_doc.read_text())
            token = m.group(0) if m else None
    if not token:
        click.echo("  ⚠ purge: no CF token (env CLOUDFLARE_API_TOKEN/CF_API_TOKEN or keys/CLOUDFLARE_TOKENS.md); skipping")
        return
    api = "https://api.cloudflare.com/client/v4"
    zone = ".".join(domain.split(".")[-2:])  # registrable domain

    def _req(method: str, path: str, body=None):
        req = _u.Request(
            f"{api}/{path}", method=method,
            headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
            data=_json.dumps(body).encode() if body else None,
        )
        try:
            with _u.urlopen(req, timeout=30) as r:
                return _json.loads(r.read())
        except _ue.HTTPError as e:
            try:
                return _json.loads(e.read())
            except Exception:
                return {"success": False, "errors": [str(e)]}

    try:
        z = _req("GET", f"zones?name={zone}")
        res = z.get("result") or []
        if not res:
            click.echo(f"  ⚠ purge: no zone access for {zone}")
            return
        out = _req("POST", f"zones/{res[0]['id']}/purge_cache", {"files": urls})
        if out.get("success"):
            click.echo(f"  ✓ purged {len(urls)} URL(s) from Cloudflare cache")
        else:
            click.echo(f"  ⚠ purge failed (token needs Zone:Cache Purge?): {out.get('errors')}")
    except Exception as e:  # never let a purge fail the publish
        click.echo(f"  ⚠ purge error: {e}")


def _build_desktop_local(projects: List[str], platform: str, skip_frontend: bool, skip_backend: bool):
    """Build desktop binaries locally."""
    fleet_root = get_fleet_root()
    _clean_pyinstaller_cache()  # guard against the stale-dylib backend-bundle failure (fleet-wide)

    for proj in projects:
        project_path = fleet_root / proj / "desktop"

        if not project_path.exists():
            click.echo(f"  ⚠ {proj}: No desktop directory")
            continue

        click.echo(f"\nBuilding {proj}...")

        # Determine electron-builder platform flag
        platform_flag = {"mac": "-m", "windows": "-w", "linux": "-l", "all": "-mwl"}.get(platform, "-mwl")

        try:
            # Run build
            if not skip_frontend and not skip_backend:
                subprocess.run(["npm", "run", "build:all"], cwd=project_path, check=True)

            # Package with electron-builder
            subprocess.run(["npm", "run", "dist", "--", platform_flag], cwd=project_path, check=True)

            click.echo(f"  ✓ {proj} built successfully")

        except subprocess.CalledProcessError as e:
            click.echo(f"  ✗ {proj} build failed: {e}")


def _build_desktop_on_instance(projects: List[str], platform: str, skip_frontend: bool, skip_backend: bool):
    """Build desktop binaries on Instance 1."""
    click.echo("Building on Instance 1...")

    instance_config = INSTANCE1
    ssh_key = get_ssh_key_path()
    ssh_opts = get_ssh_options()

    platform_flag = {"mac": "-m", "windows": "-w", "linux": "-l", "all": "-mwl"}.get(platform, "-mwl")

    for proj in projects:
        click.echo(f"\nBuilding {proj}...")

        # Build command
        if not skip_frontend and not skip_backend:
            build_cmd = f"cd ~/fleet/{proj}/desktop && npm run build:all && npm run dist -- {platform_flag}"
        else:
            build_cmd = f"cd ~/fleet/{proj}/desktop && npm run dist -- {platform_flag}"

        ssh_command = ["ssh", *ssh_opts, "-i", str(ssh_key), f"{instance_config.user}@{instance_config.ip}", build_cmd]

        result = subprocess.run(ssh_command)

        if result.returncode == 0:
            click.echo(f"  ✓ {proj} built successfully")
        else:
            click.echo(f"  ✗ {proj} build failed")


def _distribute_desktop(project: Optional[str], platform: str, instance: int, dry_run: bool):
    """Distribute desktop binaries to downloads infrastructure."""
    projects = [project] if project else DESKTOP_PROJECTS

    click.echo(f"Distributing desktop binaries for: {', '.join(projects)}")

    for proj in projects:
        _distribute_desktop_project(proj, platform, instance, dry_run)


# os -> (canonical os token, [electron-builder extensions])
_DESKTOP_PLATFORMS = {
    "mac": ("darwin", ["dmg"]),
    "windows": ("windows", ["exe"]),
    "linux": ("linux", ["AppImage", "deb"]),
}


def _canonical_desktop_name(filename: str, slug: str, version: str, os_token: str) -> str:
    """Map an electron-builder output filename to the canonical asset name
    `{slug}-{version}-{os}-{arch}.{ext}` per ASSET_NAMING_STANDARDS.

    electron-builder emits non-canonical tokens (e.g. `Hermes-1.0.0-arm64.dmg`,
    `Document Scanner-1.0.0.dmg`, `app_1.0.0_amd64.deb`). We keep the extension and
    infer the arch from the source name; OS comes from the target platform. Arch
    defaults to x86_64 when the name carries no arch hint.
    """
    ext = filename.rsplit(".", 1)[-1]
    low = filename.lower()
    if "arm64" in low or "aarch64" in low:
        arch = "arm64"
    elif "universal" in low:
        arch = "universal"
    elif "x64" in low or "amd64" in low or "x86_64" in low:
        arch = "x86_64"
    else:
        arch = "x86_64"
    return f"{slug}-{version}-{os_token}-{arch}.{ext}"


def _distribute_desktop_project(project: str, platform: str, instance: int, dry_run: bool):
    """Distribute desktop binaries for a single project.

    Normalizes electron-builder output to canonical names and publishes to
    `/var/www/downloads/{project}/desktop/releases/{version}/` with a SHA256SUMS file.
    No -desktop- infix; OS/arch tokens normalized (mac->darwin, x64->x86_64).
    See docs/standards/deployment/ASSET_NAMING_STANDARDS.md + DISTRIBUTION_STRATEGY.md.
    """
    import re

    instance_config = INSTANCE1
    ssh_key = get_ssh_key_path()
    ssh_opts = get_ssh_options()
    slug = project.replace("_", "-")

    def _ssh(cmd: str, **kw):
        return subprocess.run(
            ["ssh", *ssh_opts, "-i", str(ssh_key), f"{instance_config.user}@{instance_config.ip}", cmd],
            **kw,
        )

    platforms_to_copy = ["mac", "windows", "linux"] if platform == "all" else [platform]

    # Resolve version + the list of built artifacts from the instance.
    ver_res = _ssh(
        f"grep -m1 '\"version\"' ~/fleet/{project}/desktop/package.json", capture_output=True, text=True
    )
    m = re.search(r'"version"\s*:\s*"([^"]+)"', ver_res.stdout or "")
    if not m:
        click.echo(f"  ⚠ {project}: could not read version from desktop/package.json")
        return
    version = m.group(1)
    dest_dir = f"/var/www/downloads/{project}/desktop/releases/{version}"

    ls_res = _ssh(f"ls -1 ~/fleet/{project}/desktop/dist-electron/ 2>/dev/null", capture_output=True, text=True)
    built = [f for f in (ls_res.stdout or "").splitlines() if f.strip()]

    wanted_exts = {e for p in platforms_to_copy for e in _DESKTOP_PLATFORMS[p][1]}
    os_for_ext = {e: _DESKTOP_PLATFORMS[p][0] for p in platforms_to_copy for e in _DESKTOP_PLATFORMS[p][1]}

    plan = []  # (src_filename, canonical_name)
    for f in built:
        ext = f.rsplit(".", 1)[-1] if "." in f else ""
        if ext not in wanted_exts:
            continue
        plan.append((f, _canonical_desktop_name(f, slug, version, os_for_ext[ext])))

    if not plan:
        click.echo(f"  ⚠ {project}: no desktop artifacts found in dist-electron for {platforms_to_copy}")
        return

    if dry_run:
        click.echo(f"  Would publish to {dest_dir}/ :")
        for src, dst in plan:
            click.echo(f"    {src}  ->  {dst}")
        click.echo(f"    + SHA256SUMS")
        return

    _ssh(f"sudo mkdir -p '{dest_dir}'")
    for src, dst in plan:
        # Source names can contain spaces; quote with $HOME (tilde won't expand in quotes).
        _ssh(f'sudo cp "$HOME/fleet/{project}/desktop/dist-electron/{src}" "{dest_dir}/{dst}"')

    # Generate SHA256SUMS in the release dir (sha256sum on Linux instance).
    _ssh(f"cd '{dest_dir}' && sudo sh -c 'sha256sum * > SHA256SUMS' 2>/dev/null || true")
    _ssh(
        f"sudo chown -R www-data:www-data /var/www/downloads/{project}/ && "
        f"sudo chmod -R 755 /var/www/downloads/{project}/",
        capture_output=True,
    )
    click.echo(f"  ✓ {project}: {len(plan)} artifact(s) -> {dest_dir}/")


def _verify_desktop(project: Optional[str], instance: int):
    """Verify desktop binaries exist in downloads infrastructure."""
    projects = [project] if project else DESKTOP_PROJECTS

    instance_config = INSTANCE1
    ssh_key = get_ssh_key_path()
    ssh_opts = get_ssh_options()

    click.echo("Desktop Applications:")
    for proj in projects:
        # Check for desktop installer artifacts under desktop/releases/*/
        check_cmd = f"ls -lh /var/www/downloads/{proj}/desktop/releases/*/*.{{dmg,exe,AppImage,deb}} 2>/dev/null | wc -l"

        ssh_command = ["ssh", *ssh_opts, "-i", str(ssh_key), f"{instance_config.user}@{instance_config.ip}", check_cmd]

        result = subprocess.run(ssh_command, capture_output=True, text=True)
        count = result.stdout.strip()

        if count and int(count) > 0:
            click.echo(f"  {proj}: ✓ {count} binaries found")
        else:
            click.echo(f"  {proj}: ⚠ No binaries found")


# =============================================================================
# IDE Asset Functions (VS Code Fork)
# =============================================================================


def _build_ide(project: Optional[str], platform: str, local: bool):
    """Build VS Code fork IDE applications."""
    projects = [project] if project else IDE_PROJECTS

    click.echo(f"Building IDE for: {', '.join(projects)}")

    # TODO: Implement IDE build
    # - gulp vscode-darwin-x64
    # - gulp vscode-win32-x64-archive
    # - gulp vscode-linux-x64
    # - vsce package (for extensions)
    click.echo("  ⚠ IDE builds not yet implemented")


def _distribute_ide(project: Optional[str], platform: str, instance: int, dry_run: bool):
    """Distribute IDE builds and extensions."""
    projects = [project] if project else IDE_PROJECTS

    click.echo(f"Distributing IDE for: {', '.join(projects)}")

    # TODO: Implement IDE distribution
    # - Copy to /var/www/downloads/{project}-ide/{os}/
    # - Copy .vsix to /var/www/downloads/{project}-ide/extensions/
    click.echo("  ⚠ IDE distribution not yet implemented")


def _verify_ide(project: Optional[str], instance: int):
    """Verify IDE builds exist in downloads infrastructure."""
    projects = [project] if project else IDE_PROJECTS

    click.echo("IDE Applications:")
    for proj in projects:
        click.echo(f"  {proj}-ide: ⚠ Not yet implemented")


# =============================================================================
# Binary Asset Functions (CLI Tools)
# =============================================================================


def _build_binary(project: Optional[str], platform: str, local: bool):
    """Build standalone CLI binaries."""
    projects = [project] if project else list(BINARY_PROJECTS.keys())

    click.echo(f"Building CLI binaries for: {', '.join(projects)}")

    for proj in projects:
        lang = BINARY_PROJECTS[proj]

        if lang == "rust":
            _build_rust_binary(proj, platform, local)
        elif lang == "python":
            _build_python_binary(proj, platform, local)


def _build_rust_binary(project: str, platform: str, local: bool):
    """Build a Rust CLI binary using cargo (native host arch).

    Cross-compilation (--target) is not wired here; build on a host matching the
    target OS/arch. For full build+publish (SHA256SUMS + versioned/latest deploy
    + install.sh), use `sega binaries publish-cli -p <project>`.
    """
    click.echo(f"  Building {project} (Rust)...")

    if project not in CLI_PROJECTS:
        click.echo(f"    ⚠ No CLI configuration for {project}")
        return

    proj_config = CLI_PROJECTS[project]
    cargo_bin_name = proj_config["package_name"]
    binary_name_prefix = proj_config["binary_name"]

    source_dir = (get_fleet_root() / proj_config["cli_dir"]).expanduser().resolve()
    if not (source_dir / "Cargo.toml").exists():
        click.echo(f"    ✗ Cargo.toml not found: {source_dir / 'Cargo.toml'}")
        return

    os_name, arch = _detect_os_arch_for_cli()
    binary_name = f"{binary_name_prefix}-{os_name}-{arch}"
    local_binary = source_dir / "dist" / binary_name

    click.echo(f"    Source: {source_dir}")
    click.echo(f"    Output: {local_binary}")

    try:
        _cargo_build_binary(source_dir, cargo_bin_name, local_binary)
        click.echo(f"    ✓ Build successful: {local_binary}")
    except (subprocess.CalledProcessError, click.ClickException) as e:
        click.echo(f"    ✗ Build failed: {e}")


def _build_python_binary(project: str, platform: str, local: bool):
    """Build Python binary using Nuitka."""
    click.echo(f"  Building {project} (Python/Nuitka)...")

    if project not in CLI_PROJECTS:
        click.echo(f"    ⚠ No CLI configuration for {project}")
        return

    proj_config = CLI_PROJECTS[project]
    cli_dir = proj_config["cli_dir"]
    package_name = proj_config["package_name"]
    binary_name_prefix = proj_config["binary_name"]

    source_dir = (get_fleet_root() / cli_dir).expanduser().resolve()
    entry_point = source_dir / package_name / "main.py"

    if not entry_point.exists():
        click.echo(f"    ✗ Entry point not found: {entry_point}")
        return

    if not local:
        click.echo(f"    ⚠ Remote builds not yet implemented, use --local")
        return

    os_name, arch = _detect_os_arch_for_cli()
    binary_name = f"{binary_name_prefix}-{os_name}-{arch}"
    dist_dir = source_dir / "dist"
    local_binary = dist_dir / binary_name

    click.echo(f"    Source: {source_dir}")
    click.echo(f"    Output: {local_binary}")

    # Build in an isolated venv so deps + nuitka are available.
    dist_dir.mkdir(parents=True, exist_ok=True)

    with tempfile.TemporaryDirectory(prefix=f"sega-{project}-build-") as tmp:
        venv_dir = Path(tmp) / "venv"
        subprocess.run([sys.executable, "-m", "venv", str(venv_dir)], check=True)

        vpy = venv_dir / "bin" / "python"
        if not vpy.exists():
            click.echo(f"    ✗ venv python not found at {vpy} (unsupported platform?)")
            return

        def _pip(args: list[str]):
            subprocess.run([str(vpy), "-m", "pip", *args], check=True)

        try:
            _pip(["install", "-U", "pip"])
            # setuptools required in the build venv when anti-bloat is disabled
            # (Nuitka implicit-imports evaluates version("setuptools"); Python 3.12+
            # venvs no longer seed it). See the note in _publish_cli_one.
            _pip(["install", "-U", "setuptools"])
            _pip(["install", "Nuitka[onefile]==2.5.9"])  # pin: newer Nuitka (4.1.3/2.7.x) FATALs on the vtk implicit-import guard; non-monotonic — see SHARED_LESSONS "Nuitka --module/onefile"
            _pip(["install", "Nuitka[onefile]==2.5.9"])
            _pip(["install", "-e", str(source_dir)])

            env = os.environ.copy()
            env["PATH"] = f"{venv_dir / 'bin'}:{env.get('PATH', '')}"

            # Only force-include rich's unicode data if the project actually pulled rich
            # in. Nuitka FATALs on --include-package for a package it can't locate, so a
            # click-only CLI (e.g. atlas) would otherwise fail the whole build.
            nuitka_args = [
                str(vpy), "-m", "nuitka",
                "--standalone", "--onefile", "--follow-imports",
                "--assume-yes-for-downloads",
                # Disable the anti-bloat plugin. It rewrites parts of the
                # certifi -> importlib.resources import chain into a bare
                # `raise ImportError()` (empty message), which crashes EVERY
                # CLI's first network call (httpcore._ssl -> import certifi ->
                # certifi/core.py). Root cause of C8-1, verified with a minimal
                # Nuitka repro on node-1 2026-08-17: with anti-bloat the compiled
                # binary fails `import certifi`; with it disabled, `import certifi`
                # + a real httpx GET both succeed. Costs ~+3.7MB/binary (6.4->10MB),
                # trivial for a CLI — correctness over size.
                "--disable-plugin=anti-bloat",
            ]
            if subprocess.run([str(vpy), "-c", "import rich._unicode_data"], capture_output=True).returncode == 0:
                nuitka_args.append("--include-package=rich._unicode_data")
            # NOTE (2026-08-16): CLIs that import `requests` crash under Nuitka onefile
            # with a bare ImportError at certifi/core.py (certifi's importlib.resources
            # loader). Adding --include-package-data=certifi / --include-package=
            # importlib.resources here was tried and produced a BYTE-IDENTICAL binary
            # (Nuitka already includes them) — it does NOT fix the crash, so it was
            # reverted rather than enshrined as a false fix. The working pattern is to
            # use `httpx` (as atlas/atlas do), which builds and runs cleanly; atlas
            # was migrated off requests. Revisit here only with a verified Nuitka fix.
            nuitka_args += [
                f"--output-dir={dist_dir}",
                f"--output-filename={binary_name}",
                str(entry_point),
            ]
            subprocess.run(
                nuitka_args,
                cwd=str(source_dir),
                env=env,
                check=True,
            )

            if local_binary.exists():
                click.echo(f"    ✓ Build successful: {local_binary}")
            else:
                click.echo(f"    ✗ Build succeeded but output not found: {local_binary}")
        except subprocess.CalledProcessError as e:
            click.echo(f"    ✗ Build failed: {e}")


def _distribute_binary(project: Optional[str], platform: str, instance: int, dry_run: bool):
    """Distribute CLI binaries to downloads infrastructure.

    The canonical build+distribute path for CLI binaries (both Python/Nuitka and
    Rust/cargo) is `sega binaries publish-cli`, which handles SHA256SUMS, the
    versioned + 'latest' release layout, install.sh, and permissions in one step.
    This older split distribute step is intentionally not duplicated.
    """
    projects = [project] if project else list(BINARY_PROJECTS.keys())

    click.echo(f"Distributing CLI binaries for: {', '.join(projects)}")
    for proj in projects:
        click.echo(
            f"  → use: sega binaries publish-cli -p {proj} "
            f"--local   (or --instance {instance})"
        )


def _verify_binary(project: Optional[str], instance: int):
    """Verify CLI binaries exist in downloads infrastructure."""
    projects = [project] if project else list(BINARY_PROJECTS.keys())

    click.echo("CLI Binaries:")
    for proj in projects:
        click.echo(f"  {proj}: ⚠ Not yet implemented")


# =============================================================================
# Engine catalog + frontend — the models-analog. Regenerate the landing-app
# engine/download copy (incl. the API-key -> session-lease ACCESS MODEL) from
# the engine's published/derived release, instead of hand-editing React.
# Mirrors `sega models catalog` / `sega models frontend`. See
# common/docs/process/ENGINE_PACKAGE_BUILD_NOTES.md ("Structural fix") +
# UNIFIED_ENGINE_ACCESS_MODEL_ROLLOUT.md.
# =============================================================================

def _engine_access_manifest(project: str, lang: str) -> dict:
    """The access story is uniform across gated engines: an online-minted API key
    bootstraps a subscription-bound RS256 session lease the COMPILED artifact verifies
    offline and renews. Python engines auto-acquire from the key; Rust engines verify a
    provided lease token (or a perpetual key). Enforcement lives only in the shipped
    .so/binary (source/CI no-op)."""
    return {
        "requiresApiKey": True,
        "requiresSubscription": True,
        "offlineLease": True,
        "nodeLocked": True,
        "leaseModel": "session-lease-rs256",
        "acquisition": "auto" if lang == "python" else "token",
        "enforcedIn": "compiled-artifact",
    }


def _engine_access_copy(install_cmd: str) -> list:
    """The four copy points every engine download page must state (build-notes:
    'access-model copy each project needs NOW')."""
    return [
        {"step": "Install",
         "title": "Install the package",
         "body": f"{install_cmd} — the compiled engine; featurization, orchestration, and the "
                 "access gate are baked in."},
        {"step": "Authenticate",
         "title": "Mint an API key",
         "body": "Account -> Developer tab -> create an API key. Pasting it once bootstraps a "
                 "subscription-bound session lease; the key itself is only the bootstrap."},
        {"step": "Run",
         "title": "An active subscription is required to run",
         "body": "On every run the compiled engine verifies a subscription-bound RS256 session "
                 "lease. Without an active subscription it acquires no lease and exits."},
        {"step": "Offline",
         "title": "Verified offline, hardware node-locked",
         "body": "The lease is verified offline against a public key embedded in the binary and is "
                 "node-locked to the machine; it renews on reconnect, so short offline use works "
                 "while a copied binary or a lapsed subscription stops a bounded time later."},
    ]


def _engine_release_info(project: str) -> dict:
    """Version + download URLs + install command for one engine, derived from SOURCE
    (no network) — the same version logic `publish-engine` uses."""
    from .downloads import PROJECT_DOMAINS
    proj = ENGINE_PROJECTS[project]
    lang = proj.get("lang", "python")
    engine_dir = (get_fleet_root() / proj["engine_dir"]).expanduser()
    if lang == "rust":
        version = _read_cargo_version(engine_dir / "Cargo.toml")
        package = proj["binary_name"]
        os_name, arch = _detect_os_arch_for_cli()
        artifact = f"{package}-{os_name}-{arch}"
        pip_install = None
    else:
        version = _read_toml_version(engine_dir / "pyproject.toml")
        package = proj["package"]
        artifact = None  # wheel name carries an interpreter tag known only post-build
        pip_install = f"pip install {package}"
    dom = PROJECT_DOMAINS.get(project)
    base = f"https://downloads.{dom}/engine/releases" if dom else None
    # Optional companion thin-client CLI (ungated HTTP client), if the project ships one.
    cli_install = f"pip install {project}-cli" if project in CLI_PROJECTS else None
    return {
        "project": project,
        "lang": lang,
        "package": package,
        "version": version,
        "domain": dom,
        "pipInstall": pip_install,
        "cliInstall": cli_install,
        "artifact": artifact,
        "releaseUrl": f"{base}/{version}/" if base else None,
        "latestUrl": f"{base}/latest/" if base else None,
        "checksumsUrl": f"{base}/{version}/SHA256SUMS" if base else None,
    }


def _render_engine_access_ts(info: dict, access: dict, copy: list) -> str:
    info_body = json.dumps(info, indent=2)
    access_body = json.dumps(access, indent=2)
    copy_body = json.dumps(copy, indent=2)
    return (
        "/**\n"
        " * Engine access + download data — GENERATED by `sega binaries frontend`.\n"
        " * Do not edit by hand; regenerate from the engine's published release.\n"
        " * Reflects the API-key -> session-lease access model (an active subscription is\n"
        " * required to RUN the engine); see UNIFIED_ENGINE_ACCESS_MODEL_ROLLOUT.md.\n"
        " */\n\n"
        "export interface EngineAccessManifest {\n"
        "  requiresApiKey: boolean;\n"
        "  requiresSubscription: boolean;\n"
        "  offlineLease: boolean;\n"
        "  nodeLocked: boolean;\n"
        "  leaseModel: string;\n"
        "  acquisition: string;\n"
        "  enforcedIn: string;\n"
        "}\n\n"
        "export interface EngineAccessStep { step: string; title: string; body: string }\n\n"
        "export interface EngineRelease {\n"
        "  project: string;\n"
        "  lang: string;\n"
        "  package: string;\n"
        "  version: string;\n"
        "  domain: string | null;\n"
        "  pipInstall: string | null;\n"
        "  cliInstall: string | null;\n"
        "  artifact: string | null;\n"
        "  releaseUrl: string | null;\n"
        "  latestUrl: string | null;\n"
        "  checksumsUrl: string | null;\n"
        "}\n\n"
        f"export const engineRelease: EngineRelease = {info_body};\n\n"
        f"export const engineAccess: EngineAccessManifest = {access_body};\n\n"
        f"export const engineAccessSteps: EngineAccessStep[] = {copy_body};\n"
    )


@binaries.command("catalog")
@click.option("-o", "--out", "out_path", type=click.Path(path_type=Path),
              default=get_fleet_root() / (get_config().fleet.engine_catalog_path
                                        or "shared/engine-catalog.json"),
              show_default=True, help="Where to write the merged engine catalog JSON.")
def engine_catalog(out_path):
    """Merge every gated engine's release + access manifest into one catalog
    (the engine analog of `sega models catalog`)."""
    entries = []
    for project in ENGINE_PROJECTS:
        try:
            info = _engine_release_info(project)
        except Exception as e:
            click.echo(f"  skip {project}: {e}")
            continue
        info["access"] = _engine_access_manifest(project, info["lang"])
        entries.append(info)
    doc = {
        "generated_by": "sega binaries catalog",
        "count": len(entries),
        "projects": sorted(e["project"] for e in entries),
        "engines": entries,
    }
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(doc, indent=2) + "\n")
    click.echo(f"✓ engine catalog: {len(entries)} engine(s) → {out_path}")


@binaries.command("frontend")
@click.option("--project", "-p", "project", required=True,
              type=click.Choice(list(ENGINE_PROJECTS.keys())),
              help="Engine project whose landing-app access copy to regenerate.")
@click.option("-o", "--out", "out_path", type=click.Path(path_type=Path), default=None,
              help="Override output path (default: <project>/frontend/landing_app/src/"
                   "components/Pages/Developers/CLI/engineAccess.ts).")
def engine_frontend(project, out_path):
    """Generate the landing-app engineAccess.ts (install + version + the API-key ->
    session-lease access copy) — the engine analog of `sega models frontend`."""
    info = _engine_release_info(project)
    access = _engine_access_manifest(project, info["lang"])
    install_cmd = info["pipInstall"] or (
        f"download {info['package']} from {info['latestUrl'] or 'the downloads page'}")
    copy = _engine_access_copy(install_cmd)
    ts = _render_engine_access_ts(info, access, copy)
    landing = get_fleet_root() / project / "frontend" / "landing_app"
    if out_path is None and not landing.exists():
        raise click.ClickException(f"landing app not found: {landing} (pass -o to override)")
    dest = out_path or (landing / "src" / "components" / "Pages" / "Developers" / "CLI"
                        / "engineAccess.ts")
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text(ts)
    click.echo(f"✓ {project}: engineAccess.ts (v{info['version']}, {info['lang']}) → {dest}")
