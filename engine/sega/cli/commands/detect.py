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
SEGA PROJECT DETECTION COMMAND
==============================================================================
File: src/sega/commands/detect.py
Project: SEGA (Scalable Engineering & Growth Automation)
Copyright: 2022-2025 FLEET
License: Apache-2.0

SEGA MODULE: Commands/ProjectDetection
COMPONENT: Auto-detection CLI Command
PURPOSE: Analyze repository structure to automatically detect project type and configuration
DEPENDENCIES: click, ProjectDetector
USAGE: sega detect [--path PATH] [--verbose]

This command provides intelligent project type detection by analyzing file patterns,
dependencies, and repository structure to determine the appropriate build pipeline.
==============================================================================
"""

import click
from ...project.project_detector import ProjectDetector


@click.command()
@click.option("--path", default=".", help="Project path to analyze")
@click.option(
    "--verbose", "-v", is_flag=True, help="Show detailed detection info"
)
def detect(path: str, verbose: bool):
    """Auto-detect project type from repository structure."""
    detector = ProjectDetector(path)
    project_type = detector.detect()

    if verbose:
        config = detector.get_build_config()
        click.echo(f"Project type: {project_type}")
        click.echo(f"Builder: {config['builder']}")
        click.echo(f"Tester: {config['tester']}")
        click.echo(f"Deployer: {config['deployer']}")
        click.echo(f"Monitor: {config['monitor']}")
    else:
        click.echo(project_type)
