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
SEGA: Enterprise Deployment Framework
=====================================================
File: src/sega/commands/__init__.py
Purpose: Package initialization for SEGA CLI commands module
Dependencies: None
Authors: FLEET Development Team
Copyright: 2022-2026 Huntington Applied
License: Apache-2.0
Last Modified: 2025-08-15
"""

"""SEGA CLI commands."""

from . import (
    # Core utilities
    logs,
    init,
    detect,
    infrastructure,
    workspace,
    project,
    monitor,
    api,
    grpc,
    fleet,
    local,
    program,
    flash,
    unified_server,
    nginx,
    frontend,
    ledger,
    # Consolidated command groups
    doctor,
    forge,
    ship,
    probe,
    # Additional commands
    install,
    secrets,
    social,
    sysmon,
    sysnc,
    validate,
    health,
    # Standalone commands (also available under forge)
    standalone,
    # Shared infrastructure commands
    prepare,
    # Desktop application build/package/sign/deploy
    desktop,
)

__all__ = [
    "logs",
    "init",
    "detect",
    "infrastructure",
    "workspace",
    "project",
    "monitor",
    "api",
    "grpc",
    "fleet",
    "local",
    "program",
    "flash",
    "unified_server",
    "nginx",
    "frontend",
    "ledger",
    "doctor",
    "forge",
    "ship",
    "probe",
    "install",
    "secrets",
    "social",
    "sysmon",
    "sysnc",
    "validate",
    "health",
    "standalone",
    "prepare",
    "desktop",
]
