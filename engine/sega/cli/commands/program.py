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
SEGA HARDWARE PROGRAMMING COMMAND
==============================================================================
File: src/sega/commands/program.py
Project: SEGA (Scalable Engineering & Growth Automation)
Copyright: 2022-2025 FLEET
License: Apache-2.0

SEGA MODULE: Commands/HardwareProgramming
COMPONENT: Hardware Programming CLI Command
PURPOSE: Program hardware devices (FPGA, embedded systems, microcontrollers)
DEPENDENCIES: click, ProjectDetector, DeploymentService
USAGE: sega program --device-type TYPE [--device DEVICE] [--file FILE]

This command provides unified hardware programming interface for FPGA bitstreams,
embedded firmware, and microcontroller code.
==============================================================================
"""

import click
from pathlib import Path
from ...core.dependency_injection import inject
from ...project.project_detector import ProjectDetector
from ...services.deployment_service import DeploymentService


@click.command()
@click.option(
    "--device-type",
    type=click.Choice(["fpga", "embedded", "microcontroller", "all"]),
    default="all",
    help="Type of device to program"
)
@click.option(
    "--device",
    help="Specific device identifier (e.g., /dev/ttyUSB0, JTAG:0)"
)
@click.option(
    "--file",
    "firmware_file",
    help="Firmware/bitstream file to program (auto-detected if not specified)"
)
@click.option(
    "--verify",
    is_flag=True,
    default=True,
    help="Verify programming after completion"
)
@click.option(
    "--force",
    is_flag=True,
    help="Force programming without safety checks"
)
@click.option(
    "--dry-run",
    is_flag=True,
    help="Preview programming actions without executing"
)
@inject(ProjectDetector, DeploymentService)
def program(
    device_type: str,
    device: str,
    firmware_file: str,
    verify: bool,
    force: bool,
    dry_run: bool,
    project_detector: ProjectDetector = None,
    deployment_service: DeploymentService = None,
):
    """Program hardware devices with firmware, bitstreams, or embedded code."""
    
    # Detect project type
    project_type = project_detector.detect()
    config = project_detector.get_build_config()
    
    # Map project types to device types
    device_type_mapping = {
        'hdl_fpga': 'fpga',
        'fpga_bitstream': 'fpga',
        'firmware_edge': 'embedded',
        'embedded_system': 'embedded',
        'bare_metal': 'microcontroller',
        'hardware_controller': 'microcontroller'
    }
    
    detected_device_type = device_type_mapping.get(project_type)
    
    # Handle device type selection
    if device_type == "all":
        if detected_device_type:
            device_type = detected_device_type
            click.echo(f"Auto-detected device type: {device_type}")
        else:
            click.echo("Error: Could not auto-detect device type. Please specify --device-type")
            exit(1)
    elif detected_device_type and detected_device_type != device_type:
        click.echo(f"Warning: Project type '{project_type}' typically uses '{detected_device_type}' devices")
        if not force:
            if not click.confirm("Continue with specified device type?"):
                exit(1)
    
    # Find firmware file if not specified
    if not firmware_file:
        # Look for common firmware file patterns
        patterns = {
            'fpga': ['*.bit', '*.rbf', '*.sof', '*.jed'],
            'embedded': ['*.hex', '*.bin', '*.elf', '*.img'],
            'microcontroller': ['*.hex', '*.bin', '*.elf']
        }
        
        found_files = []
        for pattern in patterns.get(device_type, []):
            found_files.extend(Path.cwd().glob(f"**/{pattern}"))
        
        if not found_files:
            click.echo(f"Error: No firmware files found for device type '{device_type}'")
            exit(1)
        elif len(found_files) == 1:
            firmware_file = str(found_files[0])
            click.echo(f"Using firmware file: {firmware_file}")
        else:
            click.echo("Multiple firmware files found:")
            for i, f in enumerate(found_files):
                click.echo(f"  {i+1}. {f}")
            choice = click.prompt("Select file", type=int) - 1
            firmware_file = str(found_files[choice])
    
    # Prepare programming parameters
    programming_params = {
        'device_type': device_type,
        'device': device,
        'firmware_file': firmware_file,
        'verify': verify,
        'force': force,
        'project_type': project_type
    }
    
    if dry_run:
        click.echo("DRY RUN - Would execute:")
        click.echo(f"  Device Type: {device_type}")
        click.echo(f"  Device: {device or 'auto-detect'}")
        click.echo(f"  Firmware: {firmware_file}")
        click.echo(f"  Verify: {verify}")
        return
    
    # Execute programming through deployment service
    # Using deployment service as it already handles hardware deployments
    result = deployment_service.deploy_project(
        project_path=str(Path.cwd()),
        target="device",  # Special target for direct device programming
        strategy="direct",
        force=force,
        dry_run=dry_run,
        domains=[device_type]
    )
    
    if result.success:
        click.echo(f" Successfully programmed {device_type} device")
        if verify:
            click.echo(" Programming verified")
    else:
        click.echo(f" Programming failed: {result.error}")
        exit(1)