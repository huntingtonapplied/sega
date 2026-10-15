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
SEGA PROJECT BUILD COMMAND
==============================================================================
File: src/sega/commands/build.py
Project: SEGA (Scalable Engineering & Growth Automation)
Copyright: 2022-2025 FLEET
License: Apache-2.0

SEGA MODULE: Commands/ProjectBuild
COMPONENT: Multi-Target Build CLI Command
PURPOSE: Build projects based on auto-detected type with optimization support
DEPENDENCIES: click, os, subprocess, ProjectDetector, BuildResult
USAGE: sega build [--target TARGET] [--optimize] [--clean]

This command provides intelligent project building with support for local, Docker,
and native targets, optimization flags, and artifact cleanup.
==============================================================================
"""

import click
import os
import subprocess
import time
from ...project.project_detector import ProjectDetector
from ...core.deployment_result import BuildResult


@click.command()
@click.option(
    "--target", default="local", help="Build target (local, docker, native)"
)
@click.option("--optimize", is_flag=True, help="Enable optimization flags")
@click.option("--clean", is_flag=True, help="Clean build artifacts first")
def build(target: str, optimize: bool, clean: bool):
    """Build project based on detected type."""

    detector = ProjectDetector()
    project_type = detector.detect()

    click.echo(f"Building {project_type} project for {target}")

    if clean:
        click.echo("Cleaning previous build artifacts...")
        _clean_artifacts(project_type)

    # Route to appropriate builder
    builders = {
        "web_app": _build_web_app,
        "ml_pipeline": _build_ml_pipeline,
        "firmware_edge": _build_firmware,
        "native_app": _build_native,
        "hdl_fpga": _build_hdl,
    }

    builder = builders.get(project_type, _build_generic)
    result = builder(target, optimize)

    if result.success:
        click.echo(f" Build completed in {result.build_time:.2f}s")
        click.echo(f"Artifacts: {', '.join(result.artifacts)}")
    else:
        click.echo(f" Build failed: {result.error}")
        exit(1)


def _clean_artifacts(project_type: str):
    """Clean build artifacts for project type."""
    clean_patterns = {
        "web_app": [
            "_internal/environments/_internal/environments/node_modules",
            "dist",
            "build",
        ],
        "ml_pipeline": ["__pycache__", ".pytest_cache", "outputs"],
        "firmware_edge": ["build", "*.elf", "*.bin"],
        "native_app": ["target", "build", "*.o"],
        "hdl_fpga": ["work", "*.bit", "*.rbf"],
    }

    patterns = clean_patterns.get(project_type, ["build"])
    for pattern in patterns:
        if os.path.exists(pattern):
            subprocess.run(["rm", "-rf", pattern])


def _build_web_app(target: str, optimize: bool) -> BuildResult:
    """Build web aApplication."""
    start_time = time.time()

    try:
        # Check for package.json (Node.js project)
        if os.path.exists("package.json"):
            # Install dependencies
            result = subprocess.run(
                ["npm", "install"], capture_output=True, text=True
            )
            if result.returncode != 0:
                return BuildResult(
                    False, error=f"npm install failed: {result.stderr}"
                )

            # Build project
            build_cmd = "npm run build:prod" if optimize else "npm run build"
            result = subprocess.run(
                build_cmd.split(), capture_output=True, text=True
            )
            if result.returncode != 0:
                return BuildResult(
                    False, error=f"npm build failed: {result.stderr}"
                )

            artifacts = ["dist/", "build/"]

        # Check for requirements.txt (Python web app)
        elif os.path.exists("requirements.txt"):
            # Build Docker image for Python aApps
            result = subprocess.run(
                ["docker", "build", "-t", f"sega-app:{target}", "."],
                capture_output=True,
                text=True,
            )

            if result.returncode != 0:
                return BuildResult(
                    False, error=f"Docker build failed: {result.stderr}"
                )

            artifacts = [f"sega-app:{target}"]

        else:
            return BuildResult(
                False, error="No recognized web app build files found"
            )

        build_time = time.time() - start_time
        return BuildResult(True, artifacts=artifacts, build_time=build_time)

    except Exception as e:
        return BuildResult(False, error=str(e))


def _build_ml_pipeline(target: str, optimize: bool) -> BuildResult:
    """Build ML pipeline."""
    start_time = time.time()

    try:
        # Build Docker image with GPU support
        dockerfile = (
            "Dockerfile.gpu"
            if os.path.exists("Dockerfile.gpu")
            else "Dockerfile"
        )

        result = subprocess.run(
            [
                "docker",
                "build",
                "-f",
                dockerfile,
                "-t",
                f"sega-ml:{target}",
                ".",
            ],
            capture_output=True,
            text=True,
        )

        if result.returncode != 0:
            return BuildResult(
                False, error=f"Docker build failed: {result.stderr}"
            )

        build_time = time.time() - start_time
        return BuildResult(
            True, artifacts=[f"sega-ml:{target}"], build_time=build_time
        )

    except Exception as e:
        return BuildResult(False, error=str(e))


def _build_firmware(target: str, optimize: bool) -> BuildResult:
    """Build firmware for embedded targets."""
    start_time = time.time()

    try:
        # Use Make or CMake
        if os.path.exists("CMakeLists.txt"):
            os.makedirs("build", exist_ok=True)
            os.chdir("build")

            cmake_cmd = ["cmake", ".."]
            if optimize:
                cmake_cmd.extend(["-DCMAKE_BUILD_TYPE=ReleBase"])

            result = subprocess.run(cmake_cmd, capture_output=True, text=True)
            if result.returncode != 0:
                return BuildResult(
                    False, error=f"CMake failed: {result.stderr}"
                )

            result = subprocess.run(["make"], capture_output=True, text=True)
            if result.returncode != 0:
                return BuildResult(
                    False, error=f"Make failed: {result.stderr}"
                )

            artifacts = ["build/*.elf", "build/*.bin"]

        elif os.path.exists("Makefile"):
            make_cmd = ["make"]
            if optimize:
                make_cmd.append("OPTIMIZE=1")

            result = subprocess.run(make_cmd, capture_output=True, text=True)
            if result.returncode != 0:
                return BuildResult(
                    False, error=f"Make failed: {result.stderr}"
                )

            artifacts = ["*.elf", "*.bin"]

        else:
            return BuildResult(
                False, error="No recognized firmware build system found"
            )

        build_time = time.time() - start_time
        return BuildResult(True, artifacts=artifacts, build_time=build_time)

    except Exception as e:
        return BuildResult(False, error=str(e))


def _build_native(target: str, optimize: bool) -> BuildResult:
    """Build native aApplication."""
    start_time = time.time()

    try:
        # Rust project
        if os.path.exists("Cargo.toml"):
            cargo_cmd = ["cargo", "build"]
            if optimize:
                cargo_cmd.append("--releBase")

            result = subprocess.run(cargo_cmd, capture_output=True, text=True)
            if result.returncode != 0:
                return BuildResult(
                    False, error=f"Cargo build failed: {result.stderr}"
                )

            artifacts = ["target/debug/", "target/releBase/"]

        # Go project
        elif os.path.exists("go.mod"):
            result = subprocess.run(
                ["go", "build"], capture_output=True, text=True
            )
            if result.returncode != 0:
                return BuildResult(
                    False, error=f"Go build failed: {result.stderr}"
                )

            artifacts = ["./main"]

        else:
            return BuildResult(
                False, error="No recognized native build system found"
            )

        build_time = time.time() - start_time
        return BuildResult(True, artifacts=artifacts, build_time=build_time)

    except Exception as e:
        return BuildResult(False, error=str(e))


def _build_hdl(target: str, optimize: bool) -> BuildResult:
    """Build HDL for FPGA."""
    return BuildResult(False, error="HDL build not yet implemented")


def _build_generic(target: str, optimize: bool) -> BuildResult:
    """Generic fallback builder."""
    return BuildResult(False, error="Unknown project type - cannot build")
