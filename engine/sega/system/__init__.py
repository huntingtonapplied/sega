"""
SEGA System Utilities Module

This module contains embedded system utilities for monitoring, synchronization,
and backup:

- sysmon: System monitoring for local and EC2 instances
- sysnc: Multi-system git synchronization for FLEET ecosystem
- preserve: Ecosystem backup and recovery tools

These utilities are integrated into SEGA as first-class CLI commands while
preserving the battle-tested bash implementations.
"""

from pathlib import Path

# Module paths for subprocess invocation
SYSTEM_DIR = Path(__file__).parent
SYSMON_DIR = SYSTEM_DIR / "sysmon"
SYSNC_DIR = SYSTEM_DIR / "sysnc"
PRESERVE_DIR = SYSTEM_DIR / "preserve"

__all__ = ["SYSTEM_DIR", "SYSMON_DIR", "SYSNC_DIR", "PRESERVE_DIR"]
