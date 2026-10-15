#!/usr/bin/env python3
# Copyright 2025 SEGA
"""
SEGA Lazy Command Registry
==========================
Optimizes CLI startup time by loading commands on-demand.
"""

import importlib
import click
from typing import Dict, Any, Optional
from functools import lru_cache


class LazyCommandRegistry:
    """Registry for lazy-loading CLI commands to improve startup performance."""
    
    def __init__(self):
        self.command_modules = {
            'build': 'sega.commands.build',
            'deploy': 'sega.commands.deploy', 
            'status': 'sega.commands.status',
            'logs': 'sega.commands.logs',
            'init': 'sega.commands.init',
            'detect': 'sega.commands.detect',
            'doctor': 'sega.commands.doctor',
            'rollback': 'sega.commands.rollback',
            'scan': 'sega.commands.scan',
            'test': 'sega.commands.test',
            'optimize': 'sega.commands.optimize',
            'infrastructure': 'sega.commands.infrastructure',
            'workspace': 'sega.commands.workspace',
            'project': 'sega.commands.project',
            'monitor': 'sega.commands.monitor',
            'api': 'sega.commands.api',
            'grpc': 'sega.commands.grpc',
            'fleet': 'sega.commands.fleet',
            'local': 'sega.commands.local',
            'program': 'sega.commands.program',
            'flash': 'sega.commands.flash',
            'mobile': 'sega.commands.mobile',
            'desktop': 'sega.commands.desktop',
            'unified_server': 'sega.commands.unified_server',
            'install': 'sega.commands.install',
        }
        self._loaded_commands: Dict[str, Any] = {}
    
    @lru_cache(maxsize=32)
    def get_command(self, command_name: str) -> Optional[click.Command]:
        """Load and return a command by name, with LRU caching."""
        if command_name in self._loaded_commands:
            return self._loaded_commands[command_name]
            
        module_path = self.command_modules.get(command_name)
        if not module_path:
            return None
            
        try:
            module = importlib.import_module(module_path)
            command = getattr(module, command_name, None)
            if command and isinstance(command, click.Command):
                self._loaded_commands[command_name] = command
                return command
        except ImportError as e:
            click.echo(f"Warning: Failed to load command '{command_name}': {e}")
            
        return None
    
    def get_all_command_names(self) -> list[str]:
        """Get list of all available command names."""
        return list(self.command_modules.keys())
    
    def preload_common_commands(self) -> None:
        """Preload frequently used commands for better performance."""
        common_commands = ['test', 'local', 'status', 'deploy', 'logs']
        for cmd in common_commands:
            self.get_command(cmd)


# Create a global registry instance
command_registry = LazyCommandRegistry()


class LazyCommand(click.Command):
    """Wrapper for lazy-loaded commands."""
    
    def __init__(self, name: str, **attrs):
        self.command_name = name
        super().__init__(name, **attrs)
    
    def invoke(self, ctx):
        """Load the actual command and invoke it."""
        real_command = command_registry.get_command(self.command_name)
        if real_command:
            return real_command.invoke(ctx)
        else:
            raise click.ClickException(f"Command '{self.command_name}' could not be loaded")


def create_lazy_command(name: str, help_text: str = None) -> LazyCommand:
    """Create a lazy-loaded command wrapper."""
    return LazyCommand(
        name=name,
        help=help_text or f"Execute {name} command",
        callback=lambda: None  # Placeholder callback
    )