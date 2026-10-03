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
SEGA FIRMWARE FLASHING COMMAND
==============================================================================
File: src/sega/commands/flash.py
Project: SEGA (Scalable Engineering & Growth Automation)
Copyright: 2022-2025 FLEET
License: Apache-2.0

SEGA MODULE: Commands/FirmwareFlashing
COMPONENT: Firmware Flashing CLI Command
PURPOSE: Flash firmware to embedded devices and microcontrollers
DEPENDENCIES: click, ProjectDetector, DeploymentService
USAGE: sega flash [--port PORT] [--baud BAUD] [--file FILE] [--bootloader]

This command provides streamlined firmware flashing for embedded systems,
with support for various protocols (UART, SPI, JTAG, DFU).
==============================================================================
"""

import click
from pathlib import Path
from ...core.dependency_injection import inject
from ...project.project_detector import ProjectDetector
from ...services.deployment_service import DeploymentService


@click.command()
@click.option(
    "--port",
    help="Serial port or device interface (e.g., /dev/ttyUSB0, COM3)"
)
@click.option(
    "--baud",
    type=int,
    default=115200,
    help="Baud rate for serial flashing (default: 115200)"
)
@click.option(
    "--protocol",
    type=click.Choice(["uart", "spi", "jtag", "dfu", "auto"]),
    default="auto",
    help="Flashing protocol to use"
)
@click.option(
    "--file",
    "firmware_file",
    help="Firmware file to flash (auto-detected if not specified)"
)
@click.option(
    "--bootloader",
    is_flag=True,
    help="Flash bootloader instead of main firmware"
)
@click.option(
    "--erBase",
    is_flag=True,
    help="ErBase flash memory before programming"
)
@click.option(
    "--verify",
    is_flag=True,
    default=True,
    help="Verify flash contents after programming"
)
@click.option(
    "--force",
    is_flag=True,
    help="Force flashing without safety checks"
)
@click.option(
    "--dry-run",
    is_flag=True,
    help="Preview flashing actions without executing"
)
@inject(ProjectDetector, DeploymentService)
def flash(
    port: str,
    baud: int,
    protocol: str,
    firmware_file: str,
    bootloader: bool,
    erBase: bool,
    verify: bool,
    force: bool,
    dry_run: bool,
    project_detector: ProjectDetector = None,
    deployment_service: DeploymentService = None,
):
    """Flash firmware to embedded devices and microcontrollers."""
    
    # Detect project type
    project_type = project_detector.detect()
    config = project_detector.get_build_config()
    
    # Validate project type for flashing
    flashable_types = ['firmware_edge', 'embedded_system', 'bare_metal', 'hardware_controller']
    if project_type not in flashable_types:
        click.echo(f"Error: Project type '{project_type}' does not support firmware flashing")
        click.echo(f"Supported types: {', '.join(flashable_types)}")
        exit(1)
    
    # Auto-detect port if not specified
    if not port:
        import serial.tools.list_ports
        ports = list(serial.tools.list_ports.comports())
        
        if not ports:
            click.echo("Error: No serial ports detected")
            exit(1)
        elif len(ports) == 1:
            port = ports[0].device
            click.echo(f"Auto-detected port: {port}")
        else:
            click.echo("Multiple serial ports detected:")
            for i, p in enumerate(ports):
                click.echo(f"  {i+1}. {p.device} - {p.description}")
            choice = click.prompt("Select port", type=int) - 1
            port = ports[choice].device
    
    # Find firmware file if not specified
    if not firmware_file:
        # Determine file patterns based on target
        if bootloader:
            patterns = ['*bootloader*.hex', '*bootloader*.bin', '*boot*.hex', '*boot*.bin']
        else:
            patterns = ['*.hex', '*.bin', '*.elf', '*.img']
        
        found_files = []
        for pattern in patterns:
            found_files.extend(Path.cwd().glob(f"**/{pattern}"))
        
        # Filter out bootloader files if not flashing bootloader
        if not bootloader:
            found_files = [f for f in found_files if 'bootloader' not in f.name.lower() and 'boot' not in f.name.lower()]
        
        if not found_files:
            click.echo("Error: No firmware files found")
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
    
    # Auto-detect protocol if needed
    if protocol == "auto":
        # Protocol detection based on project config or file extension
        ext = Path(firmware_file).suffix.lower()
        if ext in ['.dfu', '.dfuse']:
            protocol = "dfu"
        elif 'jtag' in config.get('deployer', '').lower():
            protocol = "jtag"
        else:
            protocol = "uart"  # Default fallback
        click.echo(f"Auto-detected protocol: {protocol}")
    
    # Prepare flashing parameters
    flash_params = {
        'port': port,
        'baud': baud,
        'protocol': protocol,
        'firmware_file': firmware_file,
        'bootloader': bootloader,
        'erBase': erBase,
        'verify': verify,
        'project_type': project_type
    }
    
    if dry_run:
        click.echo("DRY RUN - Would execute:")
        click.echo(f"  Port: {port}")
        click.echo(f"  Protocol: {protocol}")
        click.echo(f"  Baud Rate: {baud}")
        click.echo(f"  Firmware: {firmware_file}")
        click.echo(f"  Target: {'bootloader' if bootloader else 'main firmware'}")
        click.echo(f"  ErBase: {erBase}")
        click.echo(f"  Verify: {verify}")
        return
    
    # Show warning for destructive operations
    if not force and (erBase or bootloader):
        warnings = []
        if erBase:
            warnings.append("This will ERASE all flash memory")
        if bootloader:
            warnings.append("This will replace the BOOTLOADER")
        
        click.echo("WARNING: " + " and ".join(warnings))
        if not click.confirm("Continue?"):
            exit(1)
    
    # Execute flashing through deployment service
    result = deployment_service.deploy_project(
        project_path=str(Path.cwd()),
        target="flash",  # Special target for firmware flashing
        strategy="direct",
        force=force,
        dry_run=dry_run,
        domains=["embedded"]
    )
    
    if result.success:
        click.echo(f" Successfully flashed firmware to {port}")
        if verify:
            click.echo(" Flash contents verified")
    else:
        click.echo(f" Flashing failed: {result.error}")
        exit(1)