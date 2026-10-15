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
SEGA DESKTOP DEVELOPMENT COMMAND
==============================================================================
File: src/sega/commands/desktop.py
Project: SEGA (Scalable Engineering & Growth Automation)
Copyright: 2022-2025 SEGA Contributors
License: Apache-2.0

SEGA MODULE: Commands/DesktopDevelopment
COMPONENT: Desktop AApplication CLI Command Group
PURPOSE: Manage Electron desktop app development, testing, and deployment
DEPENDENCIES: click, subprocess, pathlib, json
USAGE: sega desktop [dev|build|test|deploy|package|sign]

This command group provides comprehensive desktop aApplication management
for Electron projects across the FLEET ecosystem.
==============================================================================
"""

import click
import subprocess
import json
import os
import platform
from pathlib import Path
from typing import Optional, Dict, List
import logging

logger = logging.getLogger(__name__)

# Default Node.js major-version range for Electron native modules.
# Overridable per-project via sega.yaml: `desktop.node_version: {min, max}`.
DEFAULT_MIN_NODE_VERSION = 18
DEFAULT_MAX_NODE_VERSION = 22

# Build profiles. Each profile encodes the shape of one style of Electron
# desktop project: required files, accepted entry-point locations, and the
# preferred npm-script candidate lists. Selecting a profile (via `--mode`,
# sega.yaml `desktop.mode`, or auto-detection) controls everything downstream:
# validation, build, package, sign, deploy.
#
# Add a new profile here if a project ships a layout that neither covers.
BUILD_PROFILES: Dict[str, Dict] = {
    'electron': {
        'description': 'Plain tsc Electron app — sources in electron/, no bundler',
        'required_files': [
            'package.json',
            'tsconfig.json',
            'tsconfig.main.json',
            'tsconfig.preload.json',
        ],
        'main_candidates': [
            'electron/main/main.ts',
            'app/main/main.ts',
        ],
        'preload_candidates': [
            'electron/preload/preload.ts',
            'app/preload/preload.ts',
        ],
        'build_scripts': ['build:electron', 'build', 'build:all'],
        'dist_scripts': ['dist', 'dist:all'],
        'dev_scripts': ['dev', 'dev:all', 'start'],
        'dev_renderer_scripts': ['dev:renderer', 'dev:frontend', 'dev'],
        'test_scripts': ['test'],
        'test_integration_scripts': ['test:integration', 'integration'],
        'test_e2e_scripts': ['test:e2e', 'e2e'],
    },
    'vite': {
        'description': 'Vite-bundled Electron app — sources in src/, vite.config.ts',
        'required_files': [
            'package.json',
            'tsconfig.json',
            'tsconfig.main.json',
            'tsconfig.preload.json',
            'vite.config.ts',
        ],
        'main_candidates': [
            'src/main/main.ts',
        ],
        'preload_candidates': [
            'src/preload/preload.ts',
        ],
        'build_scripts': ['build'],
        'dist_scripts': ['dist'],
        'dev_scripts': ['dev'],
        'dev_renderer_scripts': ['dev:renderer', 'dev'],
        'test_scripts': ['test'],
        'test_integration_scripts': ['test:integration'],
        'test_e2e_scripts': ['test:e2e'],
    },
}

VALID_MODES = ('auto', *BUILD_PROFILES.keys())
DEFAULT_MODE = 'auto'


class DesktopManager:
    """Manages desktop aApplication operations for FLEET projects."""

    def __init__(self, project_path: Optional[Path] = None, mode: str = DEFAULT_MODE):
        self.project_path = project_path or Path.cwd()
        self.desktop_path = self.project_path / "desktop"
        self.config = self._load_config()
        self.platform = platform.system().lower()
        # Mode precedence: explicit CLI arg > sega.yaml `desktop.mode` > 'auto'.
        # 'auto' is resolved lazily so detection runs against the actual files.
        requested = mode if mode != DEFAULT_MODE else self.config.get('mode', DEFAULT_MODE)
        if requested not in VALID_MODES:
            raise click.BadParameter(
                f"Unknown desktop build mode '{requested}'. "
                f"Valid modes: {', '.join(VALID_MODES)}"
            )
        self._requested_mode = requested
        self._resolved_mode: Optional[str] = None

    @property
    def mode(self) -> str:
        """The effective build mode after auto-detection (cached)."""
        if self._resolved_mode is None:
            self._resolved_mode = self._resolve_mode()
        return self._resolved_mode

    def _resolve_mode(self) -> str:
        """Pick a concrete profile when mode is 'auto'.

        The authoritative signal is tsconfig.main.json's `include` — that's
        what tsc itself uses to find main-process sources. Some projects
        carry both a leftover `src/` tree and the real `electron/` tree
        (orion does); a pure file-existence check picks the wrong one.

        Rules (first match wins):
          1. tsconfig.main.json `include` references `electron/` (not `src/`)  → electron
          2. tsconfig.main.json `include` references `src/` AND a vite.config
             is present                                                       → vite
          3. vite.config.* AND src/main/main.ts both present                  → vite
          4. otherwise                                                        → electron
        """
        if self._requested_mode != 'auto':
            return self._requested_mode

        def _has_vite_config() -> bool:
            return any(
                (self.desktop_path / f'vite.config.{ext}').exists()
                for ext in ('ts', 'js', 'mjs', 'cjs', 'mts', 'cts')
            )

        tsc_main = self.desktop_path / 'tsconfig.main.json'
        if tsc_main.exists():
            try:
                raw = tsc_main.read_text(errors='replace')
            except Exception:
                raw = ''
            # Use a substring check rather than JSON parse: tsconfigs are often
            # JSONC (with comments / trailing commas) and json.load will reject
            # them. Substring scanning the `include` region is robust enough.
            has_electron = 'electron/' in raw
            has_src = '"src/' in raw or "'src/" in raw
            if has_electron and not has_src:
                return 'electron'
            if has_src and _has_vite_config():
                return 'vite'
            if has_electron:
                return 'electron'

        if _has_vite_config() and (self.desktop_path / 'src' / 'main' / 'main.ts').exists():
            return 'vite'
        return 'electron'

    def _profile(self) -> Dict:
        """Return the active build profile dict."""
        return BUILD_PROFILES[self.mode]
        
    def _load_config(self) -> Dict:
        """Load desktop configuration from sega.yaml or package.json."""
        sega_config = self.project_path / "sega.yaml"
        if sega_config.exists():
            import yaml
            with open(sega_config) as f:
                config = yaml.safe_load(f)
                return config.get("desktop", {})
        
        # Fallback to package.json
        package_json = self.desktop_path / "package.json"
        if package_json.exists():
            with open(package_json) as f:
                pkg = json.load(f)
                return {
                    "app_id": pkg.get("build", {}).get("appId", ""),
                    "product_name": pkg.get("build", {}).get("productName", pkg.get("name", "")),
                    "electron_version": self._get_electron_version(pkg)
                }
        
        return {}
    
    def _get_electron_version(self, package_json: Dict) -> str:
        """Extract Electron version from package.json."""
        deps = package_json.get("devDependencies", {})
        electron_version = deps.get("electron", "")
        return electron_version.lstrip("^~")

    def _package_scripts(self) -> Dict[str, str]:
        """Return the scripts table from desktop/package.json, or {} on error."""
        try:
            with open(self.desktop_path / "package.json") as f:
                return json.load(f).get("scripts", {}) or {}
        except Exception:
            return {}

    def _pick_script(self, *candidates: str) -> Optional[str]:
        """Return the first candidate script name that exists in package.json.

        SEGA shouldn't assume every desktop project exposes the same script
        names. Hermes uses `build:electron` + `dist:all`; the template uses
        plain `build` + `dist`. This picker lets one command pipeline drive
        both without per-project branching.
        """
        scripts = self._package_scripts()
        for name in candidates:
            if name in scripts:
                return name
        return None

    def _run_npm_script(self, *candidates: str, env: Optional[Dict] = None,
                       extra_args: Optional[List[str]] = None) -> bool:
        """Run the first matching npm script. Returns False if none exist.

        Raises CalledProcessError on script failure (preserves existing
        check=True behavior) so callers can surface the real build error.
        """
        script = self._pick_script(*candidates)
        if script is None:
            logger.error(
                f"None of the expected npm scripts exist in package.json: "
                f"{', '.join(candidates)}"
            )
            return False
        cmd = ["npm", "run", script]
        if extra_args:
            cmd += ["--", *extra_args]
        click.echo(f"  $ {' '.join(cmd)}")
        subprocess.run(cmd, cwd=self.desktop_path, env=env, check=True)
        return True

    def _run_profile_script(self, profile_key: str, *, env: Optional[Dict] = None,
                            extra_args: Optional[List[str]] = None) -> bool:
        """Run the first script the active profile defines for `profile_key`.

        `profile_key` is one of 'build_scripts', 'dist_scripts', 'dev_scripts',
        etc. The profile's ordered candidate list is consulted; the first one
        present in package.json wins. Falls back to `False` with a clear error
        if none of the candidates exist (so callers can abort cleanly).
        """
        profile = self._profile()
        candidates = profile.get(profile_key) or []
        if not candidates:
            logger.error(f"Profile '{self.mode}' defines no scripts for {profile_key}")
            return False
        return self._run_npm_script(*candidates, env=env, extra_args=extra_args)

    def _ensure_dependencies_installed(self) -> bool:
        """Run `npm install` when node_modules is missing OR stale.

        `node_modules` is treated as stale when `package.json` was modified
        more recently than npm's install marker (`node_modules/.package-lock.json`
        — written by npm at the end of every install). This catches the common
        case where a dep was added to `package.json` after an earlier install,
        which would otherwise silently fall through and produce mysterious
        'Cannot find module' errors from tsc.
        """
        # Abort early if the lock file is corrupted — saves a multi-minute
        # `npm install` failure that produces an opaque 404 error.
        if not self.check_lock_integrity():
            return False

        nm = self.desktop_path / "node_modules"
        pkg = self.desktop_path / "package.json"
        if not nm.exists():
            reason = "node_modules is missing"
        else:
            install_marker = nm / ".package-lock.json"
            try:
                if not install_marker.exists() or pkg.stat().st_mtime > install_marker.stat().st_mtime:
                    reason = "package.json is newer than the last install"
                else:
                    return True
            except OSError:
                reason = "could not stat node_modules install marker"
        click.echo(f"Installing desktop dependencies (npm install) — {reason}...")
        try:
            subprocess.run(["npm", "install"], cwd=self.desktop_path, check=True)
            return True
        except subprocess.CalledProcessError as e:
            logger.error(f"npm install failed: {e}")
            return False
    
    def _check_dependencies(self) -> bool:
        """Check if required dependencies are installed."""
        checks = {
            "Node.js": ["node", "--version"],
            "npm": ["npm", "--version"],
            "Python": ["python3", "--version"]
        }
        
        # Platform-specific checks
        if self.platform == "darwin":
            checks["Xcode"] = ["xcodebuild", "-version"]
        elif self.platform == "windows":
            checks["Visual Studio"] = ["msbuild", "/version"]
        
        all_good = True
        for name, cmd in checks.items():
            try:
                result = subprocess.run(cmd, capture_output=True, text=True)
                if result.returncode == 0:
                    version = result.stdout.strip().split('\n')[0]
                    click.echo(f" {name}: {version}")
                else:
                    click.echo(f" {name}: Not found")
                    all_good = False
            except FileNotFoundError:
                click.echo(f" {name}: Not found")
                all_good = False
        
        return all_good
    
    def check_node_compatibility(self) -> bool:
        """Ensure the Node.js major version is within the supported range.

        Default range is v18.x – v22.x, which covers every Node release line
        FLEET desktop projects have shipped on. Override per project via
        sega.yaml: `desktop.node_version: {min: 18, max: 22}`.
        """
        node_cfg = self.config.get('node_version') or {}
        min_v = int(node_cfg.get('min', DEFAULT_MIN_NODE_VERSION))
        max_v = int(node_cfg.get('max', DEFAULT_MAX_NODE_VERSION))

        try:
            result = subprocess.run(['node', '-v'], capture_output=True, text=True, check=True)
            version_str = result.stdout.strip().lstrip('v')
            major = int(version_str.split('.')[0])

            if major < min_v or major > max_v:
                logger.error(
                    f"Node.js v{version_str} is outside the supported range "
                    f"(v{min_v}.x - v{max_v}.x) for Electron native modules."
                )
                if self.platform == 'darwin':
                    logger.info(
                        f"Install with: brew install node@{min_v} && brew link --overwrite node@{min_v}"
                    )
                elif self.platform == 'linux':
                    logger.info(f"Install with: nvm install {min_v} && nvm use {min_v}")
                else:
                    logger.info(f"Download Node.js v{min_v}.x LTS from https://nodejs.org/")
                return False

            logger.info(f"Node.js v{version_str} is compatible")
            return True

        except subprocess.CalledProcessError:
            logger.error("Failed to check Node.js version. Is Node.js installed?")
            return False
        except Exception as e:
            logger.error(f"Error checking Node.js version: {e}")
            return False

    def _resolve_required_files(self) -> list:
        """Return the concrete list of required files for this project.

        Precedence:
          1. sega.yaml `desktop.required_files` (explicit, verbatim)
          2. Active build profile's `required_files` + first-matching main/preload
             entry from the profile's candidate lists
        """
        override = self.config.get('required_files')
        if override:
            return list(override)

        profile = self._profile()
        required = list(profile['required_files'])

        for candidate in profile['main_candidates']:
            if (self.desktop_path / candidate).exists():
                required.append(candidate)
                break
        else:
            required.append(profile['main_candidates'][0])  # flagged as missing

        for candidate in profile['preload_candidates']:
            if (self.desktop_path / candidate).exists():
                required.append(candidate)
                break
        else:
            required.append(profile['preload_candidates'][0])

        return required

    def validate_desktop_structure(self) -> tuple[bool, list]:
        """Ensure all required files exist before building.

        Layout (src/ vs electron/) is auto-detected. Projects with a custom
        structure can pin the list via sega.yaml `desktop.required_files`.
        """
        required = self._resolve_required_files()
        missing_files = [
            rel for rel in required if not (self.desktop_path / rel).exists()
        ]

        if missing_files:
            logger.error(f"Missing required files in {self.desktop_path}:")
            for file in missing_files:
                logger.error(f"  - {file}")

            if 'tsconfig.json' in missing_files:
                logger.info(
                    "Missing TypeScript configurations. "
                    "See docs/standards/DESKTOP_TEMPLATE_FIXES_REQUIRED.md for templates"
                )
            profile = self._profile()
            entry_paths = profile['main_candidates'] + profile['preload_candidates']
            if any(rel in missing_files for rel in entry_paths):
                logger.info(
                    f"Build mode is '{self.mode}' — {profile['description']}. "
                    f"Accepted main paths: {', '.join(profile['main_candidates'])}; "
                    f"accepted preload paths: {', '.join(profile['preload_candidates'])}. "
                    f"Switch mode via `--mode <name>` or sega.yaml `desktop.mode`, "
                    f"or override the file list via sega.yaml `desktop.required_files`."
                )

            return False, missing_files

        logger.info("Desktop project structure validated successfully")
        return True, []
    
    def check_native_dependencies(self) -> bool:
        """Check for native dependencies that might cause build issues."""
        package_json_path = self.desktop_path / 'package.json'

        try:
            with open(package_json_path, 'r') as f:
                package_data = json.load(f)

            # Native dependencies that require platform toolchains or
            # electron-specific rebuild steps. These aren't errors — they're
            # heads-up info if a packaging step later fails.
            problematic_packages = {
                'better-sqlite3': 'native module — needs electron-rebuild for Electron ABI',
                'node-sass': 'deprecated; prefer dart-sass (`sass`)',
                'node-gyp': 'needs a C toolchain (Xcode/MSVC/build-essential)',
                'bcrypt': 'native; bcryptjs is a drop-in pure-JS alternative',
                'canvas': 'native; requires Cairo/Pango/libjpeg/etc.',
                'sharp': 'native; platform-specific prebuilds via libvips',
            }
            
            all_deps = {
                **package_data.get('dependencies', {}),
                **package_data.get('devDependencies', {})
            }
            
            found_issues = []
            for pkg, issue in problematic_packages.items():
                if pkg in all_deps:
                    found_issues.append(f"{pkg}: {issue}")
            
            if found_issues:
                logger.warning("Found potentially problematic native dependencies:")
                for issue in found_issues:
                    logger.warning(f"  - {issue}")
                return False
            
            return True
            
        except Exception as e:
            logger.error(f"Failed to check native dependencies: {e}")
            return True  # Don't block if we can't check
    
    def verify_main_entry_after_build(self) -> bool:
        """After tsc emits, verify `package.json main` resolves to a real file.

        Hermes's `main` was `dist/main.js` but tsc emits to
        `dist/electron/main/main.js`. Without this check, the build burns
        ~3 minutes through electron-builder's downloads + native-rebuilds
        before failing with "Application entry file ... does not exist."
        Catching it here means failing in milliseconds with a specific fix.

        Only runs after `dist/` exists (post-build); pre-build, the entry
        is expected to be missing.

        Returns True if main resolves, False otherwise.
        """
        pkg_path = self.desktop_path / "package.json"
        dist_dir = self.desktop_path / "dist"
        if not dist_dir.exists():
            # Hasn't been built yet — nothing to verify.
            return True

        try:
            with open(pkg_path) as f:
                pkg = json.load(f)
        except Exception as e:
            logger.warning(f"Could not parse package.json for entry verification: {e}")
            return True  # Don't block on parse errors

        main_rel = pkg.get('main')
        if not isinstance(main_rel, str):
            return True  # No main field — electron-builder will use its own default

        main_path = self.desktop_path / main_rel
        if main_path.exists():
            return True

        # Find the entry tsc actually emitted (any *main.js under dist/).
        candidates = sorted(
            p.relative_to(self.desktop_path)
            for p in dist_dir.rglob("main.js")
        )
        if candidates:
            candidate_lines = '\n'.join(f"    \"main\": \"{p}\"" for p in candidates)
            logger.error(
                f"package.json `main` is \"{main_rel}\" but that file does not "
                f"exist after tsc. tsc actually emitted these `main.js` files:\n"
                f"{candidate_lines}\n"
                f"Fix: update package.json `main` to one of the paths above so "
                f"electron-builder can find the entry point."
            )
        else:
            logger.error(
                f"package.json `main` is \"{main_rel}\" but tsc produced no "
                f"`main.js` under {dist_dir}. Check tsconfig.main.json's "
                f"`include` and `outDir`."
            )
        return False

    def verify_bundled_runtime_deps(self) -> bool:
        """Catch the 'compiled fine, crashes at launch' class of bug.

        tsc walks up ancestor `node_modules/` directories during module
        resolution. So a desktop project that imports `jsonwebtoken` can
        compile cleanly *because* a sibling project (e.g., the parent
        repo's backend) has it installed at `../../node_modules/jsonwebtoken/`.
        electron-builder only packages `desktop/node_modules/` into the
        `.asar`, though, so at runtime the import throws
        "Cannot find module 'jsonwebtoken'" the moment the user launches
        the app.

        This check scans every `require(...)` call in the compiled `dist/`
        tree and verifies the target is either a Node builtin or present
        in `desktop/node_modules/`. Catches the class of bug before the
        binary ships.

        Returns True if every required module is bundleable, False otherwise.
        """
        import re
        dist_dir = self.desktop_path / "dist"
        nm = self.desktop_path / "node_modules"
        if not dist_dir.exists():
            return True  # Nothing compiled yet; nothing to verify.

        # Node ≥ 16 builtin module list. Names like `node:fs` are normalized.
        node_builtins = {
            'assert', 'async_hooks', 'buffer', 'child_process', 'cluster', 'console',
            'constants', 'crypto', 'dgram', 'diagnostics_channel', 'dns', 'domain',
            'events', 'fs', 'http', 'http2', 'https', 'inspector', 'module', 'net',
            'os', 'path', 'perf_hooks', 'process', 'punycode', 'querystring',
            'readline', 'repl', 'stream', 'string_decoder', 'sys', 'timers', 'tls',
            'trace_events', 'tty', 'url', 'util', 'v8', 'vm', 'wasi', 'worker_threads',
            'zlib',
            # Electron-specific modules resolved by the runtime, not from node_modules
            'electron', 'electron/main', 'electron/renderer', 'electron/common',
        }

        # Match require('<name>') / require("<name>") where <name> is a bare
        # package specifier (not relative, not absolute). Also catch ES-style
        # `from '<name>'` in case some compiled file preserves them. Skip
        # transitive deps inside node_modules — only verify things the
        # project's own code emits.
        req_pattern = re.compile(
            r'''(?:require\(\s*|from\s+)['"]([^'"./][^'"]*)['"]'''
        )
        # JSDoc `@example` blocks survive tsc compilation verbatim and often
        # contain demonstration imports/requires. Strip block and line comments
        # before scanning so we only see real code-path requires.
        block_comment = re.compile(r'/\*.*?\*/', re.DOTALL)
        line_comment = re.compile(r'(?<!:)//.*$', re.MULTILINE)

        missing: Dict[str, set] = {}
        for js_file in dist_dir.rglob("*.js"):
            try:
                content = js_file.read_text(errors='replace')
            except OSError:
                continue
            content = block_comment.sub('', content)
            content = line_comment.sub('', content)
            for match in req_pattern.finditer(content):
                raw = match.group(1)
                # Normalize `node:fs` → `fs`
                if raw.startswith('node:'):
                    raw = raw[5:]
                # Scoped package: `@scope/name/sub` → `@scope/name`
                if raw.startswith('@'):
                    parts = raw.split('/', 2)
                    pkg = '/'.join(parts[:2]) if len(parts) >= 2 else raw
                else:
                    pkg = raw.split('/', 1)[0]
                # Builtin check — match either full raw spec (e.g., `fs/promises`)
                # or the package root (e.g., `fs`). Both forms are legal in
                # source; only the root is checkable against node_builtins.
                if raw in node_builtins or pkg in node_builtins:
                    continue
                if (nm / pkg).exists():
                    continue
                rel = js_file.relative_to(self.desktop_path)
                missing.setdefault(pkg, set()).add(str(rel))

        if missing:
            logger.error(
                "Compiled code requires modules that are NOT in this project's "
                "desktop/node_modules/. At runtime, electron-builder's `.asar` "
                "won't include them and the app will crash with 'Cannot find "
                "module'. This usually means the dep was resolved at compile time "
                "via an ancestor node_modules/ (e.g., the parent repo's), but "
                "isn't declared in your package.json."
            )
            for pkg, files in sorted(missing.items()):
                sample = sorted(files)[:3]
                more = f" (+{len(files)-3} more)" if len(files) > 3 else ""
                logger.error(f"  - '{pkg}' required by: {', '.join(sample)}{more}")
            logger.error(
                "Fix: add the missing modules to package.json `dependencies` "
                "and re-run `sega desktop build`."
            )
            return False
        return True

    def check_lock_integrity(self) -> bool:
        """Detect corruption in package-lock.json before npm install runs.

        npm package names are all-lowercase by spec. A lock file containing
        package keys with uppercase letters is the signature of a bad
        find-and-replace (we hit a `string → sString` mangling propagated
        across six projects in the FLEET ecosystem). Catching this here turns
        a multi-minute `npm install` failure into a one-second abort with
        a specific fix.

        Returns True if the lock looks clean (or doesn't exist), False if
        corruption was detected and the user should remove the lock.
        """
        lock_path = self.desktop_path / "package-lock.json"
        if not lock_path.exists():
            return True
        try:
            raw = lock_path.read_text(errors='replace')
        except OSError as e:
            logger.warning(f"Could not read {lock_path}: {e}")
            return True  # Don't block on read errors

        import re
        # Package keys under "packages": look for lowercase-then-uppercase
        # inside a "node_modules/<name>" or "name": "<name>" position.
        suspicious = re.findall(
            r'"node_modules/([^"]*[a-z][A-Z][^"]*)"',
            raw,
        )
        # Also catch the literal sString prefix everywhere (defense in depth).
        if 'sString' in raw:
            suspicious.append('sString (literal corruption from prior ecosystem sync)')

        if suspicious:
            sample = ', '.join(sorted(set(suspicious))[:5])
            logger.error(
                f"package-lock.json appears corrupted at {lock_path}. "
                f"Suspicious entries: {sample}"
                f"{' (and more)' if len(suspicious) > 5 else ''}. "
                f"Recommended fix: `rm '{lock_path}'` and re-run; "
                f"npm will regenerate the lock from the (clean) package.json."
            )
            return False
        return True

    def check_package_json_paths(self) -> bool:
        """Report (do NOT mutate) suspicious paths in the project's package.json.

        SEGA used to rewrite `main` and substitute developer home directories
        in scripts; both were destructive — the `main` rewrite guessed a path
        (`dist/main/main.js`) that matches no real tsc emit layout in this
        ecosystem, and the home-dir substitution broke scripts on the very
        machine where the path was correct. Now we just surface issues and
        leave the fix to the project owner.

        Returns True if no issues were found, False if any were reported.
        """
        package_json_path = self.desktop_path / 'package.json'
        issues = []

        try:
            with open(package_json_path, 'r') as f:
                package_data = json.load(f)
        except Exception as e:
            logger.error(f"Failed to read package.json: {e}")
            return False

        # Absolute developer paths that shouldn't ship in committed scripts:
        # known CI/dev homes plus this developer's own workspace root.
        suspicious_substrings = [
            '/home/testuser/fleet',
            str(Path.home() / 'fleet'),
            'C:\\Users\\testuser\\fleet',
        ]
        for script_name, script_value in (package_data.get('scripts') or {}).items():
            if not isinstance(script_value, str):
                continue
            for needle in suspicious_substrings:
                if needle in script_value:
                    issues.append(
                        f"script '{script_name}' contains hardcoded path '{needle}' — "
                        f"replace with $HOME/$USERPROFILE or an env var"
                    )

        # `main` should resolve to a file once tsc has run. We only flag this
        # post-build (when `dist/` exists) to avoid noise before the first
        # compile. Pre-build it's expected that the entry doesn't exist yet.
        current_main = package_data.get('main')
        dist_dir = self.desktop_path / 'dist'
        if isinstance(current_main, str) and dist_dir.exists():
            emitted = self.desktop_path / current_main
            if not emitted.exists():
                issues.append(
                    f"package.json `main` is '{current_main}' but that file is missing "
                    f"after build; check tsconfig.main.json `outDir`/`include` and "
                    f"update `main` to match the path tsc actually emits"
                )

        for msg in issues:
            logger.warning(msg)

        return not issues
    
    def start_development(self, backend: bool = True, debug_port: Optional[int] = None):
        """Start desktop development environment."""
        if not self.desktop_path.exists():
            click.echo(f"Error: No desktop directory found at {self.desktop_path}")
            return False

        os.chdir(self.desktop_path)

        if not self._ensure_dependencies_installed():
            return False

        env = os.environ.copy()
        if debug_port:
            env["ELECTRON_INSPECT"] = str(debug_port)

        if backend:
            click.echo(f"Starting desktop app with backend (mode={self.mode})...")
            ok = self._run_profile_script('dev_scripts', env=env)
        else:
            click.echo(f"Starting desktop app (frontend only, mode={self.mode})...")
            ok = self._run_profile_script('dev_renderer_scripts', env=env)

        return ok
    
    def build_app(self, target_platform: Optional[str] = None, arch: str = "x64"):
        """Build desktop aApplication."""
        if not self.desktop_path.exists():
            click.echo(f"Error: No desktop directory found at {self.desktop_path}")
            return False
        
        os.chdir(self.desktop_path)
        
        # Pre-build validation
        click.echo("Running pre-build validation...")
        
        # Check Node.js compatibility
        if not self.check_node_compatibility():
            click.echo("Build aborted due to Node.js compatibility issues")
            return False
        
        # Validate project structure
        is_valid, missing_files = self.validate_desktop_structure()
        if not is_valid:
            click.echo("Build aborted due to missing required files")
            return False
        
        # Check for native dependency issues
        if not self.check_native_dependencies():
            click.echo("Warning: Build may fail due to native dependency issues")
        
        # Surface package.json issues without mutating the project.
        if not self.check_package_json_paths():
            click.echo("Warning: package.json has issues (see log above); continuing build")
        
        # Determine target platform
        if not target_platform:
            target_platform = self.platform
        
        platform_map = {
            "darwin": "mac",
            "linux": "linux",
            "windows": "win"
        }
        
        electron_platform = platform_map.get(target_platform, target_platform)

        click.echo(f"Building for {electron_platform} ({arch}) — mode={self.mode}")

        # Make sure deps are present before any npm script runs.
        if not self._ensure_dependencies_installed():
            return False

        # Compile TypeScript using whichever build script the active profile
        # prefers and the project actually defines.
        try:
            if not self._run_profile_script('build_scripts'):
                return False
        except subprocess.CalledProcessError as e:
            click.echo(f"Build failed at `{' '.join(e.cmd)}` (exit {e.returncode}). "
                       f"See npm/tsc output above for the underlying error.")
            return False

        # Fail-fast: verify package.json `main` resolves to a tsc-emitted file
        # before electron-builder spends minutes downloading Electron + running
        # native-module rebuilds, only to fail on a missing entry point.
        if not self.verify_main_entry_after_build():
            click.echo(
                "Build aborted: package.json `main` doesn't point at any tsc "
                "emit. Fix the `main` field (see candidates listed above) and "
                "re-run `sega desktop build`."
            )
            return False

        # Fail-fast: every `require()` in compiled code must resolve from
        # desktop/node_modules/, not from an ancestor's node_modules. Otherwise
        # the .asar will be missing the module and the app will crash at launch.
        if not self.verify_bundled_runtime_deps():
            click.echo(
                "Build aborted: compiled code imports modules that aren't "
                "declared in package.json (see log above). Add the listed "
                "modules to dependencies and re-run."
            )
            return False

        # Package with electron-builder. Cross-platform builds bypass project
        # scripts so the platform flags are guaranteed correct.
        try:
            if target_platform != self.platform:
                cmd = ["npx", "electron-builder", f"--{electron_platform}", f"--{arch}"]
                click.echo(f"  $ {' '.join(cmd)}")
                subprocess.run(cmd, cwd=self.desktop_path, check=True)
            else:
                if not self._run_profile_script('dist_scripts'):
                    return False
        except subprocess.CalledProcessError as e:
            click.echo(f"Packaging failed at `{' '.join(e.cmd)}` (exit {e.returncode}). "
                       f"See electron-builder output above for the underlying error.")
            return False

        output_dir = self.desktop_path / "dist-electron"
        click.echo(f"\nBuild complete! Output in: {output_dir}")
        return True
    
    def run_tests(self, integration: bool = False, e2e: bool = False):
        """Run desktop aApplication tests."""
        if not self.desktop_path.exists():
            click.echo(f"Error: No desktop directory found at {self.desktop_path}")
            return False
        
        os.chdir(self.desktop_path)
        
        if e2e:
            click.echo(f"Running E2E tests (mode={self.mode})...")
            return self._run_profile_script('test_e2e_scripts')
        elif integration:
            click.echo(f"Running integration tests (mode={self.mode})...")
            return self._run_profile_script('test_integration_scripts')
        else:
            click.echo(f"Running unit tests (mode={self.mode})...")
            return self._run_profile_script('test_scripts')
    
    def package_app(self, formats: List[str], sign: bool = False):
        """Create distribution packages."""
        if not self.desktop_path.exists():
            click.echo(f"Error: No desktop directory found at {self.desktop_path}")
            return False

        os.chdir(self.desktop_path)

        if not self._ensure_dependencies_installed():
            return False

        # electron-builder uses --mac / --win / --linux, not the raw uname value.
        platform_flag_map = {"darwin": "mac", "linux": "linux", "windows": "win"}
        builder_platform = platform_flag_map.get(self.platform, self.platform)

        platform_formats = {
            "darwin": ["dmg", "zip", "pkg"],
            "linux": ["AppImage", "deb", "rpm", "snap"],
            "windows": ["nsis", "msi", "portable"],
        }
        available_formats = platform_formats.get(self.platform, [])

        if not formats:
            formats = [available_formats[0]]

        for fmt in formats:
            if fmt not in available_formats:
                click.echo(f"Warning: Format '{fmt}' not available for {self.platform}")
                continue

            click.echo(f"Creating {fmt} package...")
            # `package` is for local artifacts; never publish. Publication is
            # an explicit choice via `sega desktop deploy`. The `sign` flag is
            # threaded through electron-builder via env (CSC_NAME / CSC_LINK).
            cmd = ["npx", "electron-builder", f"--{builder_platform}", f"--{fmt}", "--publish=never"]
            subprocess.run(cmd, cwd=self.desktop_path, check=True)

        return True
    
    def sign_app(self, certificate: Optional[str] = None):
        """Sign desktop aApplication for distribution."""
        if not self.desktop_path.exists():
            click.echo(f"Error: No desktop directory found at {self.desktop_path}")
            return False

        os.chdir(self.desktop_path)

        if not self._ensure_dependencies_installed():
            return False

        env = os.environ.copy()

        if self.platform == "darwin":
            if certificate:
                env["CSC_NAME"] = certificate
            click.echo(f"Signing macOS app (mode={self.mode})...")
            if not self._run_profile_script('dist_scripts', env=env):
                return False
            click.echo("Notarizing app with Apple...")
            # Additional notarization steps would go here
        elif self.platform == "windows":
            if certificate:
                env["CSC_LINK"] = certificate
            click.echo(f"Signing Windows app (mode={self.mode})...")
            if not self._run_profile_script('dist_scripts', env=env):
                return False
        else:
            click.echo("Code signing not required for Linux")

        return True
    
    def deploy_app(self, channel: str = "stable", provider: str = "github"):
        """Deploy desktop aApplication updates."""
        if not self.desktop_path.exists():
            click.echo(f"Error: No desktop directory found at {self.desktop_path}")
            return False
        
        os.chdir(self.desktop_path)
        
        if provider == "github":
            click.echo(f"Publishing to GitHub releases (mode={self.mode})...")
            env = os.environ.copy()
            env["CHANNEL"] = channel
            if not self._ensure_dependencies_installed():
                return False
            if not self._run_profile_script(
                'dist_scripts', env=env, extra_args=["--publish=always"]
            ):
                return False

        elif provider == "s3":
            click.echo("Publishing to S3...")
            # S3 deployment logic here
            
        elif provider == "custom":
            click.echo("Publishing to custom update server...")
            # Custom deployment logic here
        
        click.echo(f"Deployment complete! Channel: {channel}")
        return True


@click.group()
@click.option('--project', '-p', type=click.Path(exists=True),
              help='Path to project directory (defaults to current directory)')
@click.option('--mode', type=click.Choice(list(VALID_MODES)), default=DEFAULT_MODE,
              show_default=True,
              help=(
                  "Build profile. 'auto' detects from the project (vite.config.ts + "
                  "src/main/main.ts → vite, else electron). 'electron' = plain tsc "
                  "in electron/. 'vite' = bundled via vite.config.ts in src/."
              ))
@click.pass_context
def desktop(ctx, project, mode):
    """Manage desktop application development for FLEET projects.

    SEGA provides unified desktop development management for:
    - Electron application development
    - Cross-platform builds (Windows, macOS, Linux)
    - Desktop-specific testing
    - Code signing and notarization
    - Auto-update deployment

    Build mode precedence: --mode flag > sega.yaml `desktop.mode` > auto-detect.

    Examples:
        sega desktop dev                          # Start development
        sega desktop build                        # Build for current platform
        sega desktop --mode electron build        # Force the electron/ layout
        sega desktop --mode vite build            # Force the Vite src/ layout
        sega desktop modes                        # List available build modes
        sega desktop package dmg                  # Create DMG installer
        sega desktop deploy                       # Deploy updates
    """
    ctx.ensure_object(dict)
    ctx.obj['manager'] = DesktopManager(
        Path(project) if project else None,
        mode=mode,
    )


@desktop.command()
@click.option('--no-backend', is_flag=True, help='Start without Python backend')
@click.option('--debug-port', type=int, help='Chrome DevTools debug port')
@click.pass_context
def dev(ctx, no_backend, debug_port):
    """Start desktop development environment.
    
    Examples:
        sega desktop dev                      # Start with backend
        sega desktop dev --no-backend         # Frontend only
        sega desktop dev --debug-port 9222    # Enable debugging
    """
    manager = ctx.obj['manager']
    
    click.echo("Checking desktop development dependencies...")
    if not manager._check_dependencies():
        click.echo("\nPlease install missing dependencies before continuing.")
        return
    
    if manager.start_development(not no_backend, debug_port):
        click.echo("Development environment started successfully")
    else:
        click.echo("Failed to start development environment")
        exit(1)


@desktop.command()
@click.option('--platform', '-p', type=click.Choice(['windows', 'mac', 'linux']), help='Target platform')
@click.option('--arch', type=click.Choice(['x64', 'arm64', 'ia32']), default='x64', help='Target architecture')
@click.pass_context
def build(ctx, platform, arch):
    """Build desktop aApplication.
    
    Examples:
        sega desktop build                    # Build for current platform
        sega desktop build --platform mac     # Build for macOS
        sega desktop build --arch arm64       # Build for ARM64
    """
    manager = ctx.obj['manager']
    
    # Map friendly names to system names
    platform_map = {
        'windows': 'windows',
        'mac': 'darwin',
        'linux': 'linux'
    }
    
    target_platform = platform_map.get(platform) if platform else None
    
    if manager.build_app(target_platform, arch):
        click.echo("Build completed successfully")
    else:
        click.echo("Build failed")
        exit(1)


@desktop.command()
@click.option('--integration', is_flag=True, help='Run integration tests')
@click.option('--e2e', is_flag=True, help='Run end-to-end tests')
@click.pass_context
def test(ctx, integration, e2e):
    """Run desktop aApplication tests.
    
    Examples:
        sega desktop test                # Run unit tests
        sega desktop test --integration  # Run integration tests
        sega desktop test --e2e         # Run E2E tests
    """
    manager = ctx.obj['manager']
    
    if manager.run_tests(integration, e2e):
        click.echo("Tests completed successfully")
    else:
        click.echo("Tests failed")
        exit(1)


@desktop.command()
@click.argument('formats', nargs=-1)
@click.option('--sign', is_flag=True, help='Sign the package')
@click.pass_context
def package(ctx, formats, sign):
    """Create distribution packages.
    
    Examples:
        sega desktop package              # Default package
        sega desktop package dmg zip      # Multiple formats
        sega desktop package msi --sign   # Signed installer
    """
    manager = ctx.obj['manager']
    
    if manager.package_app(list(formats), sign):
        click.echo("Packaging completed successfully")
    else:
        click.echo("Packaging failed")
        exit(1)


@desktop.command()
@click.option('--certificate', '-c', help='Certificate name or path')
@click.pass_context
def sign(ctx, certificate):
    """Sign desktop aApplication for distribution.
    
    Examples:
        sega desktop sign                           # Use default cert
        sega desktop sign -c "Developer ID"        # Specific cert
    """
    manager = ctx.obj['manager']
    
    if manager.sign_app(certificate):
        click.echo("AApplication signed successfully")
    else:
        click.echo("Signing failed")
        exit(1)


@desktop.command()
@click.option('--channel', default='stable', help='ReleBase channel')
@click.option('--provider', type=click.Choice(['github', 's3', 'custom']), default='github', help='Update provider')
@click.pass_context
def deploy(ctx, channel, provider):
    """Deploy desktop aApplication updates.
    
    Examples:
        sega desktop deploy                      # Deploy to stable
        sega desktop deploy --channel beta       # Deploy to beta
        sega desktop deploy --provider s3        # Deploy to S3
    """
    manager = ctx.obj['manager']
    
    if manager.deploy_app(channel, provider):
        click.echo("Deployment completed successfully")
    else:
        click.echo("Deployment failed")
        exit(1)


@desktop.command()
@click.pass_context
def validate(ctx):
    """Validate desktop project structure and dependencies.
    
    Checks for:
    - Required TypeScript configuration files
    - Correct Node.js version
    - Problematic native dependencies
    - Hardcoded paths in package.json
    
    Example:
        sega desktop validate
    """
    manager = ctx.obj['manager']

    click.echo(f"Validating desktop project at {manager.desktop_path}")
    click.echo(f"Build mode: {manager.mode}  ({manager._profile()['description']})")

    all_valid = True

    # Check Node.js
    if not manager.check_node_compatibility():
        all_valid = False
    
    # Check structure
    is_valid, missing = manager.validate_desktop_structure()
    if not is_valid:
        all_valid = False
    
    # Check dependencies
    if not manager.check_native_dependencies():
        click.echo("Warning: Potential dependency issues found")
    
    # Surface package.json issues (read-only — no automatic mutation).
    if not manager.check_package_json_paths():
        click.echo("Warning: package.json has issues (see log above)")
    
    if all_valid:
        click.echo(" Desktop project validation passed")
    else:
        click.echo(" Desktop project validation failed")
        exit(1)


@desktop.command()
@click.pass_context
def modes(ctx):
    """List available build modes and show which one is active for this project.

    Example:
        sega desktop modes
        sega desktop --mode vite modes
    """
    manager = ctx.obj['manager']
    active = manager.mode
    click.echo(f"Active mode: {active}  (project: {manager.project_path})")
    click.echo("")
    click.echo("Available modes:")
    for name, profile in BUILD_PROFILES.items():
        marker = " *" if name == active else "  "
        click.echo(f"{marker} {name:<10} {profile['description']}")
        click.echo(f"     main:    {', '.join(profile['main_candidates'])}")
        click.echo(f"     preload: {', '.join(profile['preload_candidates'])}")
        click.echo(f"     build:   {', '.join(profile['build_scripts'])}")
        click.echo(f"     dist:    {', '.join(profile['dist_scripts'])}")
        click.echo("")
    click.echo("Mode precedence: --mode flag > sega.yaml `desktop.mode` > auto-detect")


@desktop.command()
@click.option('--deps', is_flag=True, help='Also remove node_modules/')
@click.option('--lock', is_flag=True, help='Also remove package-lock.json')
@click.option('-y', '--yes', is_flag=True, help='Skip the confirmation prompt')
@click.pass_context
def clean(ctx, deps, lock, yes):
    """Remove build outputs (and optionally deps + lock) for a fresh rebuild.

    Always removes: dist/, dist-electron/
    With --deps:    also removes node_modules/  (forces full re-install)
    With --lock:    also removes package-lock.json  (forces lock regeneration —
                    useful when the lock is suspected corrupted)

    Examples:
        sega desktop clean                 # Just build outputs
        sega desktop clean --deps          # Outputs + node_modules
        sega desktop clean --deps --lock   # Full reset
        sega desktop clean --lock -y       # Remove corrupted lock, no prompt
    """
    manager = ctx.obj['manager']
    targets = []
    for rel in ('dist', 'dist-electron'):
        p = manager.desktop_path / rel
        if p.exists():
            targets.append(p)
    if deps:
        p = manager.desktop_path / 'node_modules'
        if p.exists():
            targets.append(p)
    if lock:
        p = manager.desktop_path / 'package-lock.json'
        if p.exists():
            targets.append(p)

    if not targets:
        click.echo("Nothing to clean — all targets already absent.")
        return

    click.echo(f"Will remove the following from {manager.desktop_path}:")
    for p in targets:
        kind = "dir " if p.is_dir() else "file"
        click.echo(f"  {kind}  {p.relative_to(manager.desktop_path)}")

    if not yes:
        if not click.confirm("Proceed?", default=False):
            click.echo("Cancelled.")
            return

    import shutil
    for p in targets:
        if p.is_dir():
            shutil.rmtree(p)
        else:
            p.unlink()
        click.echo(f"  removed {p.relative_to(manager.desktop_path)}")
    click.echo("Clean complete.")