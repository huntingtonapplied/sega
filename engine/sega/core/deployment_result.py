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
# SEGA MODULE - Deployment Result Types
# ===============================================================
# File: src/sega/core/deployment_result.py
# Purpose: Provides shared result types for deployment and build operations
#
# Description: Defines standardized result dataclasses used across the SEGA
# deployment system. Includes DeploymentResult and BuildResult for consistent
# return types and error handling across all deployment operations.
#
# Dependencies:
# - External: dataclasses, typing, datetime
# - Internal: None
#
# Used by: All deployers, build systems, deployment orchestrator
#

from dataclasses import dataclass
from typing import Optional, Dict, Any
from datetime import datetime


@dataclass
class DeploymentResult:
    """Standard result for all deployment operations."""

    success: bool
    error: Optional[str] = None
    message: Optional[str] = None
    deployment_id: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None
    timestamp: datetime = None
    start_time: Optional[float] = None

    def __post_init__(self):
        if self.timestamp is None:
            self.timestamp = datetime.now()


@dataclass
class BuildResult:
    """Result of build operations."""

    success: bool
    artifacts: list = None
    error: Optional[str] = None
    build_time: float = 0.0
    metadata: Optional[Dict[str, Any]] = None

    def __post_init__(self):
        if self.artifacts is None:
            self.artifacts = []
