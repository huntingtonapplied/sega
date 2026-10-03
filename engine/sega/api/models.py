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
SEGA API MODELS
==============================================================================
File: src/sega/api/models.py
Project: SEGA (Specialized Cross-Domain Deployment Platform)
Copyright: 2022-2025 FLEET
License: Apache-2.0
SEGA MODULE: API Data Models
COMPONENT: Pydantic models for API request/response validation
PURPOSE: Define structured data models for HTTP API interactions
DEPENDENCIES: pydantic (via fastapi)

This module defines the data models used by the SEGA HTTP API for
Telemetry integration and external system communication.
==============================================================================
"""

from pydantic import BaseModel, Field
from typing import Dict, List, Optional, Any
from enum import Enum
from datetime import datetime


class DeploymentStrategy(str, Enum):
    """Available deployment strategies."""

    ROLLING = "rolling"
    BLUE_GREEN = "blue_green"
    CANARY = "canary"
    MIXED = "mixed"


class ProjectType(str, Enum):
    """Supported project types for cross-domain deployment."""

    WEB_APP = "web_app"
    ML_PIPELINE = "ml_pipeline"
    FIRMWARE_EDGE = "firmware_edge"
    HDL_FPGA = "hdl_fpga"
    NATIVE_APP = "native_app"
    UNKNOWN = "unknown"


class PipelineType(BaseModel):
    """Available pipeline type definition."""

    id: str = Field(..., description="Unique pipeline type identifier")
    name: str = Field(..., description="Human-readable pipeline name")
    project_type: ProjectType = Field(
        ..., description="Associated project type"
    )
    deployment_strategies: List[DeploymentStrategy] = Field(
        ..., description="Supported deployment strategies"
    )
    description: str = Field(..., description="Pipeline description")
    requirements: List[str] = Field(
        default_factory=list, description="Pipeline requirements"
    )


class PipelineTriggerRequest(BaseModel):
    """Request model for triggering a pipeline deployment."""

    project_path: str = Field(..., description="Path to project to deploy")
    target: str = Field(
        ..., description="Deployment target (staging, production)"
    )
    strategy: DeploymentStrategy = Field(
        default=DeploymentStrategy.ROLLING,
        description="Deployment strategy to use",
    )
    image_tag: str = Field(default="latest", description="Image tag to deploy")
    force: bool = Field(default=False, description="Force deployment flag")
    dry_run: bool = Field(default=False, description="Dry run flag")
    project_type: Optional[ProjectType] = Field(
        default=None, description="Override project type detection"
    )
    environment_variables: Dict[str, str] = Field(
        default_factory=dict, description="Additional environment variables"
    )
    notification_webhook: Optional[str] = Field(
        default=None, description="Webhook URL for deployment notifications"
    )


class PipelineTriggerResponse(BaseModel):
    """Response model for pipeline trigger requests."""

    build_id: str = Field(..., description="Unique build identifier")
    status: str = Field(..., description="Initial build status")
    message: str = Field(..., description="Response message")
    project_type: ProjectType = Field(..., description="Detected project type")
    deployment_url: Optional[str] = Field(
        default=None, description="URL to track deployment progress"
    )
    estimated_duration: Optional[int] = Field(
        default=None, description="Estimated deployment duration in seconds"
    )


class BuildStatus(str, Enum):
    """Build status values."""

    PENDING = "pending"
    RUNNING = "running"
    SUCCESS = "success"
    FAILED = "failed"
    CANCELLED = "cancelled"


class BuildStatusResponse(BaseModel):
    """Response model for build status queries."""

    build_id: str = Field(..., description="Build identifier")
    status: BuildStatus = Field(..., description="Current build status")
    progress: int = Field(..., description="Build progress percentage (0-100)")
    message: str = Field(..., description="Status message")
    started_at: Optional[datetime] = Field(
        default=None, description="Build start timestamp"
    )
    completed_at: Optional[datetime] = Field(
        default=None, description="Build completion timestamp"
    )
    duration: Optional[int] = Field(
        default=None, description="Build duration in seconds"
    )
    project_type: ProjectType = Field(..., description="Project type")
    target: str = Field(..., description="Deployment target")
    strategy: DeploymentStrategy = Field(
        ..., description="Deployment strategy"
    )
    logs_url: Optional[str] = Field(
        default=None, description="URL to access build logs"
    )
    deployment_metadata: Dict[str, Any] = Field(
        default_factory=dict, description="Additional deployment metadata"
    )
    error_details: Optional[str] = Field(
        default=None, description="Error details if build failed"
    )


class ApiError(BaseModel):
    """Standard API error response."""

    error: str = Field(..., description="Error type")
    message: str = Field(..., description="Error message")
    details: Optional[Dict[str, Any]] = Field(
        default=None, description="Additional error details"
    )
    request_id: Optional[str] = Field(
        default=None, description="Request identifier for tracing"
    )


class HealthResponse(BaseModel):
    """Health check response."""

    status: str = Field(..., description="Service status")
    version: str = Field(..., description="SEGA version")
    uptime: int = Field(..., description="Service uptime in seconds")
    dependencies: Dict[str, str] = Field(
        ..., description="Dependency status (aws, k8s, etc.)"
    )
