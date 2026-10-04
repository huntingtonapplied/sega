#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# Copyright 2025 SEGA

"""
SEGA INSTALLATION SUBSYSTEM
===============================================================================
Provides system installation and configuration capabilities for FLEET systems.
Integrates with existing SEGA deployment infrastructure and Ansible roles.
===============================================================================
"""

from .system_types import SystemType, SystemTypeManager
from .installer import SystemInstaller, InstallationResult
from .validators import InstallationValidator

__all__ = [
    'SystemType',
    'SystemTypeManager', 
    'SystemInstaller',
    'InstallationResult',
    'InstallationValidator'
]