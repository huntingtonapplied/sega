"""
SEGA Signing Module

Platform-specific code signing tools:
- macOS: codesign + notarization
- Windows: Authenticode (signtool)
- Linux: GPG signing
"""

from .mac import MacSigner
from .windows import WindowsSigner
from .linux import LinuxSigner

__all__ = [
    "MacSigner",
    "WindowsSigner",
    "LinuxSigner",
]
