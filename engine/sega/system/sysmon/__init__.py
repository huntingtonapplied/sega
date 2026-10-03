"""
SEGA Sysmon Module - System Monitoring

Provides system monitoring utilities for local and EC2 instances:
- Status checking (disk, memory, CPU, Docker)
- Deep analysis with cleanup recommendations
- Multi-instance dashboard
- Docker and build artifact cleanup
- Report generation (markdown/JSON)

The main dispatcher is a bash script that routes to command implementations
in the commands/ directory, using shared libraries from lib/.
"""

from pathlib import Path

SYSMON_DIR = Path(__file__).parent

# Main dispatcher
SYSMON_SCRIPT = SYSMON_DIR / "sysmon"

# Library paths
LIB_DIR = SYSMON_DIR / "lib"
COMMANDS_DIR = SYSMON_DIR / "commands"

__all__ = [
    "SYSMON_DIR",
    "SYSMON_SCRIPT",
    "LIB_DIR",
    "COMMANDS_DIR",
]
