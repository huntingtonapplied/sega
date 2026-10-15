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
SEGA API COMMAND
==============================================================================
File: src/sega/commands/api.py
Project: SEGA (Specialized Cross-Domain Deployment Platform)  
Copyright: 2022-2025 FLEET
License: Apache-2.0
SEGA MODULE: API Server Command
COMPONENT: CLI command to start HTTP API server
PURPOSE: Enable starting the HTTP API server from CLI
DEPENDENCIES: click, api server module

This module provides the CLI command to start the SEGA HTTP API server
for Telemetry integration and external system access.
==============================================================================
"""

import click
import os
import sys

from ...api.server import start_server
from ...core.dependency_injection import setup_default_dependencies


@click.command()
@click.option(
    "--host", default="0.0.0.0", help="Host to bind the API server to"
)
@click.option("--port", default=8000, help="Port to bind the API server to")
@click.option(
    "--reload", is_flag=True, help="Enable auto-reload for development"
)
@click.option(
    "--api-key",
    envvar="SEGA_API_KEY",
    help="API key for authentication (can also be set via SEGA_API_KEY env var)",
)
def api(host: str, port: int, reload: bool, api_key: str):
    """Start the SEGA HTTP API server for Telemetry integration.

    This command starts the FastAPI-based HTTP server that provides REST API
    endpoints for external systems like Telemetry dashboard to trigger deployments
    and monitor build status.

    Examples:
        sega api                          # Start on default host:port (0.0.0.0:8000)
        sega api --host localhost --port 8080   # Custom host and port
        sega api --reload                 # Development mode with auto-reload
        sega api --api-key secret123      # With API key authentication

    Environment Variables:
        SEGA_API_KEY: API key for authentication (optional)

    The API provides endpoints:
        GET  /health                      # Health check
        GET  /v1/pipeline-types           # Available pipeline types
        POST /v1/pipelines/trigger        # Trigger deployment
        GET  /v1/builds/{id}/status       # Get build status
        GET  /v1/builds/{id}/logs         # Get build logs
        GET  /api/docs                    # Interactive API documentation
    """

    # Setup dependency injection
    setup_default_dependencies()

    # Set API key in environment if provided
    if api_key:
        os.environ["SEGA_API_KEY"] = api_key
        click.echo(" API key authentication enabled")
    else:
        click.echo(
            " No API key set - API will accept all requests from localhost"
        )
        click.echo(
            "  Set SEGA_API_KEY environment variable for production use"
        )

    # Display startup information
    click.echo(f" Starting SEGA API server on {host}:{port}")
    click.echo(
        f" API documentation available at: http://{host}:{port}/api/docs"
    )
    click.echo(f" Health check endpoint: http://{host}:{port}/health")

    if reload:
        click.echo(" Auto-reload enabled for development")

    try:
        # Start the server
        start_server(host=host, port=port, reload=reload)
    except KeyboardInterrupt:
        click.echo("\n SEGA API server stopped")
        sys.exit(0)
    except Exception as e:
        click.echo(f" Failed to start API server: {e}")
        sys.exit(1)
