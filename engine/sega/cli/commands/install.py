#!/usr/bin/env python3
# -*- coding: utf-8 -*-
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
SEGA INSTALL COMMAND
===============================================================================
File: src/sega/commands/install.py
Purpose: System installation and configuration command

Description: Provides system installation capabilities for different FLEET
system types using existing Ansible roles and project-agnostic configuration.
Integrates with SEGA's cross-domain deployment capabilities.

Dependencies:
- Internal: installation subsystem, project detection, deployment router
- External: click, ansible (optional)
===============================================================================
"""

import click
import sys
from typing import Optional
import json

from ...installation.installer import SystemInstaller
from ...installation.system_types import SystemTypeManager
from ...installation.validators import InstallationValidator


@click.group()
def install():
    """System installation and configuration commands."""
    pass


@install.command()
@click.option('--target', '-t', 
              help='Target system type to install')
@click.option('--dry-run', '-n', is_flag=True, 
              help='Show what would be installed without executing')
@click.option('--force', '-f', is_flag=True,
              help='Force installation even if system already configured')
@click.option('--config-file', '-c',
              help='Custom configuration file for installation')
@click.option('--ansible-inventory',
              help='Ansible inventory file for remote installation')
@click.option('--host',
              help='Target host for remote installation (requires ansible-inventory)')
def target(target: str, dry_run: bool, force: bool, 
           config_file: Optional[str], ansible_inventory: Optional[str], 
           host: Optional[str]):
    """Install system configuration for specified target type.
    
    Examples:
        sega install target --target development-jellyfish
        sega install target --target server-jellyfish --dry-run
        sega install target --target engine-jellyfish --host myserver.local
    """
    if not target:
        click.echo("Error: --target is required", err=True)
        click.echo("Use 'sega install list-targets' to see available options")
        sys.exit(1)
    
    try:
        # Get system installer
        installer = SystemInstaller()
        
        # Validate target type
        if not installer.is_valid_target(target):
            click.echo(f"Error: Invalid target type '{target}'", err=True)
            click.echo("Use 'sega install list-targets' to see available options")
            sys.exit(1)
        
        # Remote installation
        if host or ansible_inventory:
            if not ansible_inventory:
                click.echo("Error: --ansible-inventory required for remote installation", err=True)
                sys.exit(1)
            
            result = installer.install_remote(
                target=target,
                inventory=ansible_inventory,
                host=host,
                dry_run=dry_run,
                force=force,
                config_file=config_file
            )
        else:
            # Local installation
            result = installer.install_local(
                target=target,
                dry_run=dry_run,
                force=force,
                config_file=config_file
            )
        
        if result.success:
            click.echo(f"  Installation of {target} completed successfully")
            if result.next_steps:
                click.echo("\nNext Steps:")
                for step in result.next_steps:
                    click.echo(f"  • {step}")
        else:
            click.echo(f"  Installation failed: {result.error}", err=True)
            sys.exit(1)
            
    except Exception as e:
        click.echo(f"  Installation failed: {str(e)}", err=True)
        sys.exit(1)


@install.command('list-targets')
@click.option('--json-output', is_flag=True,
              help='Output in JSON format')
def list_targets(json_output: bool):
    """List available installation target types."""
    try:
        system_manager = SystemTypeManager()
        targets = system_manager.get_all_system_types()
        
        if json_output:
            target_data = []
            for target in targets:
                target_data.append({
                    'name': target.name,
                    'description': target.description,
                    'os_types': target.os_types,
                    'technology_stacks': target.technology_stacks,
                    'vpn_mode': target.vpn_mode
                })
            click.echo(json.dumps(target_data, indent=2))
        else:
            click.echo("Available Installation Targets:\n")
            
            # Group by category
            dev_targets = [t for t in targets if 'dev' in t.name]
            prod_targets = [t for t in targets if 'jellyfish' in t.name and 'dev' not in t.name]
            
            if dev_targets:
                click.echo("  Development Systems:")
                for target in dev_targets:
                    os_list = ", ".join(target.os_types)
                    click.echo(f"  • {target.name:<25} - {target.description} ({os_list})")
                click.echo()
            
            if prod_targets:
                click.echo("  Production Systems:")
                for target in prod_targets:
                    os_list = ", ".join(target.os_types)
                    vpn_info = f"VPN: {target.vpn_mode}"
                    click.echo(f"  • {target.name:<25} - {target.description} ({vpn_info})")
                
    except Exception as e:
        click.echo(f"  Failed to list targets: {str(e)}", err=True)
        sys.exit(1)


@install.command()
@click.option('--json-output', is_flag=True,
              help='Output in JSON format')
def detect(json_output: bool):
    """Auto-detect recommended system type for current environment."""
    try:
        detector = SystemInstaller()
        recommendation = detector.detect_recommended_target()
        
        if json_output:
            click.echo(json.dumps(recommendation, indent=2))
        else:
            click.echo("  System Detection Results:\n")
            
            # Current system info
            click.echo(f"OS: {recommendation['current_system']['os']}")
            click.echo(f"Architecture: {recommendation['current_system']['arch']}")
            if recommendation['current_system'].get('distribution'):
                click.echo(f"Distribution: {recommendation['current_system']['distribution']}")
            click.echo()
            
            # Detected projects
            if recommendation['detected_projects']:
                click.echo(" Detected FLEET Projects:")
                for project in recommendation['detected_projects']:
                    tech_stacks = ", ".join(project.get('technology_stacks', []))
                    click.echo(f"  • {project['name']} ({tech_stacks})")
                click.echo()
            
            # Recommendations
            click.echo("  Recommended System Types:")
            for rec in recommendation['recommendations']:
                confidence = " High" if rec['confidence'] > 0.8 else " Medium" if rec['confidence'] > 0.5 else " Low"
                click.echo(f"  • {rec['target']:<25} - {confidence} confidence")
                click.echo(f"    {rec['reason']}")
            click.echo()
            
            # Installation command
            if recommendation['recommendations']:
                primary_rec = recommendation['recommendations'][0]
                click.echo("  To install the recommended system type:")
                click.echo(f"   sega install target --target {primary_rec['target']}")
                
    except Exception as e:
        click.echo(f"  Detection failed: {str(e)}", err=True)
        sys.exit(1)


@install.command()
@click.option('--target', '-t',
              help='Target system type to validate')
@click.option('--json-output', is_flag=True,
              help='Output in JSON format')
def validate(target: Optional[str], json_output: bool):
    """Validate current system against target installation requirements."""
    try:
        validator = InstallationValidator()
        
        if target:
            # Validate specific target
            result = validator.validate_target_compatibility(target)
            
            if json_output:
                click.echo(json.dumps(result, indent=2))
            else:
                click.echo(f"  Validation Results for {target}:\n")
                
                if result['compatible']:
                    click.echo("  System is compatible with this target")
                else:
                    click.echo("  System is NOT compatible with this target")
                
                if result['issues']:
                    click.echo("\n   Issues Found:")
                    for issue in result['issues']:
                        severity_icon = "" if issue['severity'] == 'error' else ""
                        click.echo(f"  {severity_icon} {issue['message']}")
                
                if result['requirements']:
                    click.echo("\n  Requirements:")
                    for req in result['requirements']:
                        status_icon = " " if req['satisfied'] else " "
                        click.echo(f"  {status_icon} {req['description']}")
        else:
            # Validate current installation
            result = validator.validate_current_installation()
            
            if json_output:
                click.echo(json.dumps(result, indent=2))
            else:
                click.echo("  Current Installation Validation:\n")
                
                if result['sega_installed']:
                    click.echo("  SEGA is properly installed")
                else:
                    click.echo("  SEGA installation issues detected")
                
                if result['system_configured']:
                    click.echo(f"  System configured as: {result['detected_type']}")
                else:
                    click.echo("   No system configuration detected")
                
                if result['services_healthy']:
                    click.echo("  All services are healthy")
                else:
                    click.echo("   Some services have issues")
                    
    except Exception as e:
        click.echo(f"  Validation failed: {str(e)}", err=True)
        sys.exit(1)


@install.command('roles')
@click.option('--json-output', is_flag=True,
              help='Output in JSON format')
def list_roles(json_output: bool):
    """List available Ansible roles for system configuration."""
    from pathlib import Path

    try:
        # Find ansible roles directory
        sega_root = Path(__file__).parent.parent.parent.parent
        roles_dir = sega_root / "infrastructure" / "ansible" / "roles"

        if not roles_dir.exists():
            click.echo("Error: Ansible roles directory not found", err=True)
            sys.exit(1)

        # Collect role information
        roles = []
        for role_path in sorted(roles_dir.iterdir()):
            if role_path.is_dir() and not role_path.name.startswith('.'):
                role_info = {
                    'name': role_path.name,
                    'has_tasks': (role_path / 'tasks' / 'main.yml').exists(),
                    'has_defaults': (role_path / 'defaults' / 'main.yml').exists(),
                    'has_templates': (role_path / 'templates').exists(),
                }
                roles.append(role_info)

        if json_output:
            click.echo(json.dumps(roles, indent=2))
        else:
            click.echo("Available Ansible Roles:\n")
            click.echo(f"{'Role Name':<35} {'Tasks':<8} {'Defaults':<10} {'Templates'}")
            click.echo("-" * 70)

            for role in roles:
                tasks = "" if role['has_tasks'] else ""
                defaults = "" if role['has_defaults'] else ""
                templates = "" if role['has_templates'] else ""
                click.echo(f"{role['name']:<35} {tasks:<8} {defaults:<10} {templates}")

            click.echo(f"\nTotal: {len(roles)} roles")
            click.echo(f"\nRoles directory: {roles_dir}")

    except Exception as e:
        click.echo(f"Failed to list roles: {str(e)}", err=True)
        sys.exit(1)


@install.command('run-role')
@click.argument('role_name')
@click.option('--dry-run', '-n', is_flag=True,
              help='Show what would be executed without running')
@click.option('--host', '-h', default='localhost',
              help='Target host (default: localhost)')
@click.option('--extra-vars', '-e', multiple=True,
              help='Extra variables to pass to Ansible (key=value)')
def run_role(role_name: str, dry_run: bool, host: str, extra_vars: tuple):
    """Run a specific Ansible role directly.

    Examples:
        sega install run-role install_packages
        sega install run-role configure_monitoring --dry-run
        sega install run-role openvpn_client -e vpn_server=10.8.0.1
    """
    import subprocess
    import tempfile
    from pathlib import Path

    try:
        sega_root = Path(__file__).parent.parent.parent.parent
        roles_dir = sega_root / "infrastructure" / "ansible" / "roles"
        role_path = roles_dir / role_name

        if not role_path.exists():
            click.echo(f"Error: Role '{role_name}' not found", err=True)
            click.echo("Use 'sega install roles' to list available roles")
            sys.exit(1)

        click.echo(f"Running Ansible role: {role_name}")

        # Create temporary playbook
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)

            # Create inventory
            inventory_file = temp_path / 'inventory'
            if host == 'localhost':
                inventory_file.write_text('[local]\nlocalhost ansible_connection=local\n')
            else:
                inventory_file.write_text(f'[targets]\n{host}\n')

            # Create playbook
            playbook_file = temp_path / 'playbook.yml'
            playbook_content = f"""---
- name: Run {role_name}
  hosts: {'local' if host == 'localhost' else 'targets'}
  become: yes
  roles:
    - role: {role_name}
"""
            playbook_file.write_text(playbook_content)

            # Build ansible command
            cmd = [
                'ansible-playbook',
                '-i', str(inventory_file),
                str(playbook_file),
                '--roles-path', str(roles_dir),
            ]

            if dry_run:
                cmd.append('--check')

            for var in extra_vars:
                cmd.extend(['-e', var])

            if dry_run:
                click.echo(f"\nDRY RUN - Would execute:\n  {' '.join(cmd)}\n")

            result = subprocess.run(cmd, capture_output=not dry_run)

            if result.returncode == 0:
                click.echo(f"\n Role {role_name} completed successfully")
            else:
                click.echo(f"\n Role {role_name} failed", err=True)
                sys.exit(1)

    except FileNotFoundError:
        click.echo("Error: Ansible not installed. Install with: pip install ansible", err=True)
        sys.exit(1)
    except Exception as e:
        click.echo(f"Failed to run role: {str(e)}", err=True)
        sys.exit(1)


@install.command()
@click.option('--target', '-t',
              help='Target system type to show info for')
def info(target: str):
    """Show detailed information about a system type."""
    if not target:
        click.echo("Error: --target is required", err=True)
        sys.exit(1)
    
    try:
        system_manager = SystemTypeManager()
        system_type = system_manager.get_system_type(target)
        
        if not system_type:
            click.echo(f"Error: Unknown target type '{target}'", err=True)
            sys.exit(1)
        
        click.echo(f"  System Type: {system_type.name}\n")
        click.echo(f"Description: {system_type.description}")
        click.echo(f"Supported OS: {', '.join(system_type.os_types)}")
        click.echo(f"Technology Stacks: {', '.join(system_type.technology_stacks)}")
        click.echo(f"VPN Mode: {system_type.vpn_mode}")
        click.echo(f"Security Profile: {system_type.security_profile}")
        
        if system_type.package_requirements:
            click.echo("\n Package Requirements:")
            for os_type, packages in system_type.package_requirements.items():
                click.echo(f"  {os_type}: {', '.join(packages)}")
        
        if system_type.service_requirements:
            click.echo(f"\n  Services: {', '.join(system_type.service_requirements)}")
        
        if system_type.storage_requirements:
            click.echo("\n  Storage Requirements:")
            for mount, requirement in system_type.storage_requirements.items():
                click.echo(f"  {mount}: {requirement}")
        
        # Show installation steps preview
        click.echo("\n  Installation Preview:")
        click.echo(f"   sega install target --target {target} --dry-run")
        
    except Exception as e:
        click.echo(f"  Failed to get info: {str(e)}", err=True)
        sys.exit(1)


# Register with main CLI
def register_commands(cli):
    """Register install commands with main CLI."""
    cli.add_command(install)