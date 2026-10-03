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
SEGA API MODULE
==============================================================================
File: src/sega/api/__init__.py
Project: SEGA (Specialized Cross-Domain Deployment Platform)
Copyright: 2022-2025 FLEET
License: Apache-2.0
SEGA MODULE: API Interface
COMPONENT: HTTP API Server for Telemetry Integration
PURPOSE: Provide REST API endpoints for external systems to interact with SEGA
DEPENDENCIES: fastapi, uvicorn
USAGE: Telemetry dashboard integration and external CI/CD orchestration

This module provides HTTP API endpoints that complement the CLI interface,
enabling programmatic access to SEGA deployment capabilities.
==============================================================================
"""

from .server import app, start_server
from .models import (
    PipelineTriggerRequest,
    PipelineTriggerResponse,
    BuildStatusResponse,
    PipelineType,
    ApiError,
)

__all__ = [
    "app",
    "start_server",
    "PipelineTriggerRequest",
    "PipelineTriggerResponse",
    "BuildStatusResponse",
    "PipelineType",
    "ApiError",
]
