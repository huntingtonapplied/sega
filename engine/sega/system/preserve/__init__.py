"""
SEGA Preserve Module

Ecosystem backup and recovery tools for the FLEET ecosystem.
Creates timestamped backups before sync operations.

Scripts:
    create-ecosystem-preserve.sh: Create comprehensive ecosystem backup

Usage:
    sega preserve                     # Create timestamped backup
    sega preserve --list              # List existing preserves
    sega preserve --cleanup [--keep N] # Remove old preserves
    sega preserve --size              # Show preserve directory size
"""

from pathlib import Path

# Module directory
PRESERVE_DIR = Path(__file__).parent

# Script paths
SCRIPTS = {
    "create_preserve": PRESERVE_DIR / "create-ecosystem-preserve.sh",
}


def get_script_path(script_name: str) -> Path:
    """Get the path to a preserve script."""
    if script_name not in SCRIPTS:
        raise ValueError(f"Unknown script: {script_name}. Available: {list(SCRIPTS.keys())}")
    return SCRIPTS[script_name]
