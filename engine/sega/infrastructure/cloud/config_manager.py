#!/usr/bin/env python
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

# ===============================================================
# SEGA MODULE - INFRASTRUCTURE CONFIG MANAGER
# ===============================================================
# File: src/sega/core/_internal/tooling/_internal/tooling/infrastructure/config_manager.py
# Purpose: Infrastructure configuration management
#
# Description: Manages persistence and retrieval of infrastructure configuration
# settings stored in YAML format. Handles loading, saving, and updating of
# sega-infrastructure.yaml configuration files with validation support.
#
# Dependencies:
# - External: yaml, click, pathlib
# - Internal: None (standalone configuration component)
#
# Used by: infrastructure_manager, setup_wizard, terraform_manager
#

"""Infrastructure configuration management."""

import yaml
import click
from pathlib import Path
from typing import Dict, Optional


class InfrastructureConfigManager:
    """Manages infrastructure configuration persistence."""

    def __init__(self, workspace_root: Optional[Path] = None):
        self.workspace_root = (
            Path(workspace_root) if workspace_root else Path.cwd()
        )
        self.config_dir = self.workspace_root / ".sega"
        self.config_dir.mkdir(exist_ok=True)
        self.config_file = self.workspace_root / "sega-infrastructure.yaml"
        self._config: Optional[Dict] = None

    @property
    def config(self) -> Dict:
        """Get current configuration, loading if needed."""
        if self._config is None:
            self._config = self.load()
        return self._config

    def load(self) -> Dict:
        """Load infrastructure configuration from sega-infrastructure.yaml."""
        if self.config_file.exists():
            with open(self.config_file) as f:
                self._config = yaml.safe_load(f)
                return self._config
        return {}

    def save(self, config: Dict) -> None:
        """Save infrastructure configuration to sega-infrastructure.yaml."""
        with open(self.config_file, "w") as f:
            yaml.dump(config, f, default_flow_style=False, indent=2)

        self._config = config
        click.echo(f"Infrastructure configuration saved to {self.config_file}")

    def update(self, updates: Dict) -> Dict:
        """Update configuration with new values."""
        current = self.config.copy()
        current.update(updates)
        self.save(current)
        return current

    def get(self, key: str, default=None):
        """Get configuration value by key."""
        return self.config.get(key, default)

    def set(self, key: str, value):
        """Set configuration value by key."""
        config = self.config.copy()
        config[key] = value
        self.save(config)
