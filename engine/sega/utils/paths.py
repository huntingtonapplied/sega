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
SEGA Path Utilities
===================
Provides generalized path resolution across different environments.
"""

import os
from pathlib import Path


def get_fleet_root() -> Path:
    """
    Get the FLEET root directory, supporting multiple environments.

    Tries in order:
    1. SEGA_FLEET_ROOT / FLEET_ROOT environment variable
    2. Detect from current script location (assumes under /fleet/)
    3. Fall back to ~/fleet (home directory relative)

    Returns:
        Path: The FLEET root directory
    """
    # Check environment variables first (SEGA_FLEET_ROOT preferred, FLEET_ROOT legacy)
    for env_var in ('SEGA_FLEET_ROOT', 'FLEET_ROOT'):
        if env_var in os.environ:
            return Path(os.environ[env_var]).expanduser()

    # Try to detect from current location
    cwd = Path.cwd()
    for parent in [cwd] + list(cwd.parents):
        if parent.name == 'fleet':
            return parent

    # Fall back to ~/fleet (works on any system)
    return Path('~/fleet').expanduser()


def get_sega_root() -> Path:
    """
    Get the SEGA project root directory.

    Returns:
        Path: The SEGA project root directory
    """
    return get_fleet_root() / 'sega'


def get_project_root(project_name: str) -> Path:
    """
    Get the root directory for a specific FLEET project.

    Args:
        project_name: Name of the project

    Returns:
        Path: The project root directory
    """
    return get_fleet_root() / project_name
