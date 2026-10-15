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
SEGA HTTP API SERVER
==============================================================================
File: src/sega/api/server.py  
Project: SEGA (Specialized Cross-Domain Deployment Platform)
Copyright: 2022-2025 FLEET
License: Apache-2.0
SEGA MODULE: HTTP API Server
COMPONENT: FastAPI aApplication for Telemetry integration
PURPOSE: Provide REST API endpoints for external systems
DEPENDENCIES: fastapi, uvicorn, core SEGA modules

This module implements the HTTP API server that enables Telemetry dashboard
and other external systems to trigger deployments and monitor build status.
==============================================================================
"""

import asyncio
import uuid
import time
import os
import logging
from datetime import datetime
from typing import Dict, List, Optional, Any
from pathlib import Path

from fastapi import FastAPI, HTTPException, Depends, Request, Security, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
import uvicorn

from .models import (
    PipelineTriggerRequest,
    PipelineTriggerResponse,
    BuildStatusResponse,
    BuildStatus,
    PipelineType,
    ProjectType,
    DeploymentStrategy,
    ApiError,
    HealthResponse,
)

# Import SEGA core components
from ..project.project_detector import ProjectDetector
from ..services.deployment_service import DeploymentService
from ..core.dependency_injection import DIContainer

# Logger configuration
logger = logging.getLogger("sega.api")

# Global build tracking
active_builds: Dict[str, Dict[str, Any]] = {}
build_history: Dict[str, Dict[str, Any]] = {}

# Security
security = HTTPBearer(auto_error=False)


# Hosts treated as local for the unconfigured-dev-key fallback below.
_LOCALHOST_HOSTS = {"127.0.0.1", "::1", "localhost"}


def _is_production_env() -> bool:
    """Case-insensitive production check (accepts 'production' and 'prod')."""
    return os.getenv("ENVIRONMENT", "").strip().lower() in ("production", "prod")


def verify_api_key(
    request: Request,
    credentials: Optional[HTTPAuthorizationCredentials] = Security(security),
):
    """Verify API key authentication."""
    expected_key = os.getenv("SEGA_API_KEY")

    # No API key configured. This previously returned True for EVERY caller — a
    # silent auth bypass on all protected endpoints (the comment claimed
    # "localhost only" but no host check was performed). Now: fail closed in
    # production; in dev, allow localhost only and log loudly.
    if not expected_key:
        if _is_production_env():
            logger.critical(
                "SEGA_API_KEY is not set in production — refusing to serve "
                "protected API endpoints. Set SEGA_API_KEY to enable the HTTP API."
            )
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="API authentication is not configured",
            )
        client_host = request.client.host if request.client else None
        if client_host not in _LOCALHOST_HOSTS:
            logger.critical(
                "SEGA_API_KEY is not set; rejecting non-localhost request from %s. "
                "Set SEGA_API_KEY to enable authenticated remote API access.",
                client_host,
            )
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="API key required",
                headers={"WWW-Authenticate": "Bearer"},
            )
        logger.warning(
            "SEGA_API_KEY is not set — allowing unauthenticated localhost request "
            "from %s (development mode only).",
            client_host,
        )
        return True

    if not credentials:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="API key required",
            headers={"WWW-Authenticate": "Bearer"},
        )

    if credentials.credentials != expected_key:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid API key",
            headers={"WWW-Authenticate": "Bearer"},
        )

    return credentials.credentials


# FastAPI aApplication
app = FastAPI(
    title="SEGA API",
    description="Cross-Domain Deployment Platform API",
    version="0.1.0",
    docs_url="/api/docs",
    redoc_url="/api/redoc",
)

# Add CORS middleware for Telemetry integration
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Configure appropriately for production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Track server start time for uptime calculation
server_start_time = time.time()


@app.exception_handler(Exception)
async def global_exception_handler(request, exc):
    """Global exception handler."""
    return JSONResponse(
        status_code=500,
        content=ApiError(
            error="internal_server_error",
            message=str(exc),
            request_id=str(uuid.uuid4()),
        ).dict(),
    )


@app.get("/health", response_model=HealthResponse)
async def health_check():
    """Health check endpoint."""
    uptime = int(time.time() - server_start_time)

    # Check dependencies
    dependencies = {}
    try:
        # Test AWS connectivity
        import boto3

        sts = boto3.client("sts")
        sts.get_caller_identity()
        dependencies["aws"] = "healthy"
    except Exception:
        dependencies["aws"] = "unhealthy"

    try:
        # Test Kubernetes connectivity
        from kubernetes import client, config

        config.load_incluster_config()
        v1 = client.CoreV1Api()
        v1.list_namespace()
        dependencies["kubernetes"] = "healthy"
    except Exception:
        dependencies["kubernetes"] = "unavailable"
        
    try:
        # Test gRPC streaming connectivity.
        # NOTE: channel.close() MUST run even when channel_ready_future times out —
        # otherwise every health poll leaks the channel's completion-queue thread
        # (observed: 1469 threads → ~99% CPU when the gRPC server isn't up).
        import grpc
        grpc_port = int(os.getenv("SEGA_GRPC_PORT", 50051))
        channel = grpc.insecure_channel(f"localhost:{grpc_port}")
        try:
            grpc.channel_ready_future(channel).result(timeout=1)
            dependencies["grpc_streaming"] = "healthy"
        finally:
            channel.close()
    except Exception:
        dependencies["grpc_streaming"] = "unavailable"

    return HealthResponse(
        status="healthy",
        version="0.1.0",
        uptime=uptime,
        dependencies=dependencies,
    )


@app.get("/v1/pipeline-types", response_model=List[PipelineType])
async def get_pipeline_types(api_key: str = Depends(verify_api_key)):
    """Get available pipeline types for deployment."""
    pipeline_types = [
        PipelineType(
            id="web_app",
            name="Web AApplication",
            project_type=ProjectType.WEB_APP,
            deployment_strategies=[
                DeploymentStrategy.ROLLING,
                DeploymentStrategy.BLUE_GREEN,
                DeploymentStrategy.MIXED,
            ],
            description="Deploy web aApplications to Kubernetes or ECS",
            requirements=["docker", "kubernetes_or_ecs"],
        ),
        PipelineType(
            id="ml_pipeline",
            name="ML Pipeline",
            project_type=ProjectType.ML_PIPELINE,
            deployment_strategies=[
                DeploymentStrategy.ROLLING,
                DeploymentStrategy.CANARY,
                DeploymentStrategy.MIXED,
            ],
            description="Deploy ML models to GPU clusters",
            requirements=["docker", "gpu_cluster", "model_registry"],
        ),
        PipelineType(
            id="firmware_edge",
            name="Firmware Deployment",
            project_type=ProjectType.FIRMWARE_EDGE,
            deployment_strategies=[DeploymentStrategy.ROLLING],
            description="Deploy firmware to edge devices via Ansible",
            requirements=["ansible", "vpn_access", "device_inventory"],
        ),
        PipelineType(
            id="hdl_fpga",
            name="FPGA Bitstream",
            project_type=ProjectType.HDL_FPGA,
            deployment_strategies=[DeploymentStrategy.BLUE_GREEN],
            description="Program FPGA devices with HDL bitstreams",
            requirements=[
                "fpga_tools",
                "hardware_access",
                "verification_tools",
            ],
        ),
        PipelineType(
            id="native_app",
            name="Native AApplication",
            project_type=ProjectType.NATIVE_APP,
            deployment_strategies=[DeploymentStrategy.ROLLING],
            description="Deploy native aApplications to bare metal via systemd",
            requirements=[
                "systemd",
                "bare_metal_access",
                "service_management",
            ],
        ),
    ]

    return pipeline_types


@app.post("/v1/pipelines/trigger", response_model=PipelineTriggerResponse)
async def trigger_pipeline(
    request: PipelineTriggerRequest, api_key: str = Depends(verify_api_key)
):
    """Trigger a deployment pipeline."""
    # Generate unique build ID
    build_id = str(uuid.uuid4())

    try:
        # Validate and resolve project path
        project_path = Path(request.project_path).resolve()
        if not project_path.exists():
            raise HTTPException(
                status_code=400,
                detail=f"Project path does not exist: {request.project_path}",
            )

        # Detect project type if not provided
        container = DIContainer.get_instance()
        detector = container.get(ProjectDetector)

        if request.project_type:
            project_type = request.project_type
        else:
            detected_type = detector.detect(str(project_path))
            project_type = (
                ProjectType(detected_type)
                if detected_type
                else ProjectType.UNKNOWN
            )

        # Create build record
        build_record = {
            "build_id": build_id,
            "status": BuildStatus.PENDING,
            "progress": 0,
            "message": "Build queued",
            "started_at": datetime.utcnow(),
            "completed_at": None,
            "duration": None,
            "project_type": project_type,
            "project_path": str(project_path),
            "target": request.target,
            "strategy": request.strategy,
            "image_tag": request.image_tag,
            "force": request.force,
            "dry_run": request.dry_run,
            "environment_variables": request.environment_variables,
            "notification_webhook": request.notification_webhook,
            "logs_url": f"/v1/builds/{build_id}/logs",
            "deployment_metadata": {},
            "error_details": None,
        }

        # Store build record
        active_builds[build_id] = build_record

        # Start deployment asynchronously
        asyncio.create_task(execute_deployment(build_id, build_record))

        return PipelineTriggerResponse(
            build_id=build_id,
            status="pending",
            message="Deployment pipeline triggered successfully",
            project_type=project_type,
            deployment_url=f"/v1/builds/{build_id}/status",
            estimated_duration=300,  # 5 minutes default estimate
        )

    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Failed to trigger pipeline: {str(e)}"
        )


@app.get("/v1/builds/{build_id}/status", response_model=BuildStatusResponse)
async def get_build_status(
    build_id: str, api_key: str = Depends(verify_api_key)
):
    """Get build status by ID."""
    # Check active builds first
    if build_id in active_builds:
        record = active_builds[build_id]
    elif build_id in build_history:
        record = build_history[build_id]
    else:
        raise HTTPException(
            status_code=404, detail=f"Build {build_id} not found"
        )

    # Calculate duration if completed
    duration = None
    if record["completed_at"] and record["started_at"]:
        duration = int(
            (record["completed_at"] - record["started_at"]).total_seconds()
        )

    return BuildStatusResponse(
        build_id=record["build_id"],
        status=record["status"],
        progress=record["progress"],
        message=record["message"],
        started_at=record["started_at"],
        completed_at=record["completed_at"],
        duration=duration,
        project_type=record["project_type"],
        target=record["target"],
        strategy=record["strategy"],
        logs_url=record["logs_url"],
        deployment_metadata=record["deployment_metadata"],
        error_details=record["error_details"],
    )


@app.get("/v1/builds/{build_id}/logs")
async def get_build_logs(
    build_id: str, api_key: str = Depends(verify_api_key)
):
    """Get build logs by ID."""
    if build_id not in active_builds and build_id not in build_history:
        raise HTTPException(
            status_code=404, detail=f"Build {build_id} not found"
        )

    # In a real implementation, logs would be stored in a proper logging system
    # For now, return a placeholder
    return {
        "build_id": build_id,
        "logs": [
            {
                "timestamp": datetime.utcnow().isoformat(),
                "level": "INFO",
                "message": "Deployment started",
            },
            {
                "timestamp": datetime.utcnow().isoformat(),
                "level": "INFO",
                "message": "Project detected and validated",
            },
            {
                "timestamp": datetime.utcnow().isoformat(),
                "level": "INFO",
                "message": "Deployment in progress...",
            },
        ],
    }


@app.post("/v1/deployments/cross-domain")
async def trigger_cross_domain_deployment(
    request: dict, api_key: str = Depends(verify_api_key)
):
    """Trigger a cross-domain deployment across multiple project types."""
    # Extract parameters
    domains = request.get("domains", [])
    target = request.get("target", "staging")
    strategy = request.get("strategy", "rolling")
    projects = request.get("projects", [])
    
    if not domains:
        raise HTTPException(
            status_code=400,
            detail="At least one domain must be specified"
        )
    
    if not projects:
        raise HTTPException(
            status_code=400,
            detail="At least one project must be specified"
        )
    
    # Create deployment records for each project
    deployment_results = []
    
    for project in projects:
        build_id = f"xd-{str(uuid.uuid4())[:8]}"
        
        # Create build record
        build_record = {
            "build_id": build_id,
            "project_path": project["path"],
            "project_type": project.get("type", "auto-detect"),
            "target": target,
            "strategy": strategy,
            "domains": domains,
            "status": BuildStatus.PENDING,
            "progress": 0,
            "message": "Cross-domain deployment queued",
            "created_at": datetime.utcnow(),
            "updated_at": datetime.utcnow(),
            "deployment_metadata": {},
            "error_details": None,
        }
        
        active_builds[build_id] = build_record
        
        # Schedule deployment with domain filtering
        asyncio.create_task(execute_cross_domain_deployment(build_id, build_record))
        
        deployment_results.append({
            "build_id": build_id,
            "project": project["path"],
            "status": "queued"
        })
    
    return {
        "deployment_id": f"xd-batch-{str(uuid.uuid4())[:8]}",
        "deployments": deployment_results,
        "domains": domains,
        "target": target,
        "strategy": strategy
    }


@app.get("/v1/hardware/status")
async def get_hardware_status(api_key: str = Depends(verify_api_key)):
    """Get status of connected hardware devices and programming interfaces."""
    hardware_status = {
        "timestamp": datetime.utcnow().isoformat(),
        "devices": {
            "fpga": {
                "connected": 0,
                "available": [],
                "busy": []
            },
            "embedded": {
                "connected": 0,
                "available": [],
                "busy": []
            },
            "microcontroller": {
                "connected": 0,
                "available": [],
                "busy": []
            }
        },
        "interfaces": {
            "jtag": {"status": "ready", "devices": []},
            "uart": {"status": "ready", "ports": []},
            "spi": {"status": "ready", "devices": []},
            "dfu": {"status": "ready", "devices": []}
        },
        "recent_deployments": []
    }
    
    # Check for connected devices
    try:
        import serial.tools.list_ports
        ports = list(serial.tools.list_ports.comports())
        hardware_status["interfaces"]["uart"]["ports"] = [
            {"port": p.device, "description": p.description}
            for p in ports
        ]
        hardware_status["devices"]["embedded"]["connected"] = len(ports)
        hardware_status["devices"]["embedded"]["available"] = [p.device for p in ports]
    except ImportError:
        pass
    
    # Check recent hardware deployments
    for build_id, record in {**active_builds, **build_history}.items():
        if record.get("project_type") in ["hdl_fpga", "firmware_edge", "bare_metal"]:
            hardware_status["recent_deployments"].append({
                "build_id": build_id,
                "type": record["project_type"],
                "status": record["status"],
                "timestamp": record["updated_at"].isoformat()
            })
    
    # Limit recent deployments to last 10
    hardware_status["recent_deployments"] = hardware_status["recent_deployments"][-10:]
    
    return hardware_status


async def execute_cross_domain_deployment(build_id: str, build_record: Dict[str, Any]):
    """Execute cross-domain deployment with domain filtering."""
    try:
        # Update status to running
        build_record["status"] = BuildStatus.RUNNING
        build_record["progress"] = 10
        build_record["message"] = "Cross-domain deployment started"
        
        # Get deployment service
        deployment_service = DIContainer.get(DeploymentService)
        
        # Execute deployment with domain filtering
        result = deployment_service.deploy_project(
            project_path=build_record["project_path"],
            target=build_record["target"],
            strategy=build_record["strategy"],
            domains=build_record["domains"]
        )
        
        # Update build record based on result
        if result.success:
            if result.metadata.get("skipped"):
                build_record["status"] = BuildStatus.SUCCESS
                build_record["message"] = f"Skipped: {result.metadata.get('reason', 'Domain filtering')}"
            else:
                build_record["status"] = BuildStatus.SUCCESS
                build_record["message"] = "Cross-domain deployment completed"
            build_record["progress"] = 100
            build_record["deployment_metadata"] = result.metadata or {}
        else:
            build_record["status"] = BuildStatus.FAILED
            build_record["message"] = "Cross-domain deployment failed"
            build_record["error_details"] = str(result.error)
            build_record["progress"] = 0
        
        # Move to history
        build_history[build_id] = build_record
        del active_builds[build_id]
        
    except Exception as e:
        build_record["status"] = BuildStatus.FAILED
        build_record["message"] = "Cross-domain deployment failed"
        build_record["error_details"] = str(e)
        build_record["progress"] = 0
        
        build_history[build_id] = build_record
        if build_id in active_builds:
            del active_builds[build_id]


async def execute_deployment(build_id: str, build_record: Dict[str, Any]):
    """Execute the actual deployment asynchronously."""
    try:
        # Update status to running
        build_record["status"] = BuildStatus.RUNNING
        build_record["progress"] = 10
        build_record["message"] = "Deployment started"
        
        # Send initial metric to gRPC stream
        await _send_deployment_metric(build_id, build_record)

        # Get deployment service
        container = DIContainer.get_instance()
        deployment_service = container.get(DeploymentService)

        # Update progress
        build_record["progress"] = 30
        build_record["message"] = "Preparing deployment"
        await _send_deployment_metric(build_id, build_record)

        # Execute deployment
        result = deployment_service.deploy_project(
            project_path=build_record["project_path"],
            target=build_record["target"],
            strategy=build_record["strategy"],
            image_tag=build_record["image_tag"],
            force=build_record["force"],
            dry_run=build_record["dry_run"],
        )

        # Update progress
        build_record["progress"] = 90
        build_record["message"] = "Finalizing deployment"
        await _send_deployment_metric(build_id, build_record)

        # Check deployment result
        if result.success:
            build_record["status"] = BuildStatus.SUCCESS
            build_record["progress"] = 100
            build_record["message"] = "Deployment completed successfully"
            build_record["deployment_metadata"] = result.metadata
        else:
            build_record["status"] = BuildStatus.FAILED
            build_record["progress"] = 100
            build_record["message"] = "Deployment failed"
            build_record["error_details"] = (
                str(result.error) if result.error else "Unknown error"
            )
            
        # Send final metric
        await _send_deployment_metric(build_id, build_record)

    except Exception as e:
        build_record["status"] = BuildStatus.FAILED
        build_record["progress"] = 100
        build_record["message"] = "Deployment failed with exception"
        build_record["error_details"] = str(e)
        
        # Send failure metric
        await _send_deployment_metric(build_id, build_record)

    finally:
        # Mark as completed
        build_record["completed_at"] = datetime.utcnow()

        # Move to history and remove from active builds
        build_history[build_id] = build_record.copy()
        if build_id in active_builds:
            del active_builds[build_id]

        # Send webhook notification if configured
        if build_record.get("notification_webhook"):
            try:
                # In a real implementation, send HTTP POST to webhook
                pass
            except Exception:
                # Don't fail deployment due to webhook issues
                pass


async def _send_deployment_metric(build_id: str, build_record: Dict[str, Any]):
    """Send deployment metric to gRPC streaming service."""
    try:
        import grpc
        
        # Check if protobuf is available
        try:
            from ..proto import sega_metrics_pb2, sega_metrics_pb2_grpc
        except ImportError:
            return  # Skip if protobuf not generated
            
        # Connect to gRPC server
        grpc_port = int(os.getenv("SEGA_GRPC_PORT", 50051))
        channel = grpc.insecure_channel(f"localhost:{grpc_port}")
        stub = sega_metrics_pb2_grpc.MetricserviceStub(channel)
        
        # Map build status to deployment status
        status_map = {
            BuildStatus.PENDING: sega_metrics_pb2.DEPLOYMENT_STATUS_PENDING,
            BuildStatus.RUNNING: sega_metrics_pb2.DEPLOYMENT_STATUS_RUNNING,
            BuildStatus.SUCCESS: sega_metrics_pb2.DEPLOYMENT_STATUS_SUCCESS,
            BuildStatus.FAILED: sega_metrics_pb2.DEPLOYMENT_STATUS_FAILED,
        }
        
        # Create deployment metric
        metric = sega_metrics_pb2.MetricEvent(
            event_id=f"{build_id}-{int(time.time())}",
            type=sega_metrics_pb2.METRIC_TYPE_DEPLOYMENT_PROGRESS,
            timestamp=sega_metrics_pb2.google.protobuf.timestamp_pb2.Timestamp(
                seconds=int(time.time())
            ),
            deployment=sega_metrics_pb2.DeploymentMetric(
                deployment_id=build_id,
                project_id=build_record.get("project_path", ""),
                status=status_map.get(build_record["status"], 0),
                progress_percentage=build_record["progress"],
                message=build_record["message"],
                timestamp=sega_metrics_pb2.google.protobuf.timestamp_pb2.Timestamp(
                    seconds=int(time.time())
                ),
                metadata={
                    "target": build_record.get("target", ""),
                    "strategy": build_record.get("strategy", ""),
                }
            ),
            source="sega-api-server",
            project_id=build_record.get("project_path", ""),
            tags={
                "build_id": build_id,
                "project_type": str(build_record.get("project_type", "")),
            }
        )
        
        # Push metric
        stub.PushMetric(metric, timeout=1)
        channel.close()
        
    except Exception as e:
        # Don't fail deployment due to metrics issues
        logger.debug(f"Failed to send deployment metric: {e}")


def start_server(
    host: str = "0.0.0.0", port: int = 8000, reload: bool = False
):
    """Start the SEGA API server."""
    uvicorn.run(
        "sega.api.server:app",
        host=host,
        port=port,
        reload=reload,
        log_level="info",
    )
