"""
SEGA Packaging Module

Platform-specific packaging tools:
- Electron: Desktop app packaging with electron-builder
- Expo: Mobile app packaging with EAS
- VS Code IDE: Full IDE fork builds
- VS Code Extension: Extension packaging with vsce
"""

from .electron import ElectronPackager
from .vscode_ide import VSCodeIDEBuilder
from .vscode_extension import VSCodeExtensionPackager

__all__ = [
    "ElectronPackager",
    "VSCodeIDEBuilder",
    "VSCodeExtensionPackager",
]
