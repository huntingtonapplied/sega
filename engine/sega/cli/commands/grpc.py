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
SEGA gRPC COMMAND
==============================================================================
File: src/sega/commands/grpc.py
Project: SEGA (Specialized Cross-Domain Deployment Platform)
Copyright: 2022-2025 FLEET
License: Apache-2.0
PURPOSE: CLI command to start gRPC streaming server
DEPENDENCIES: click, grpc server module
==============================================================================
"""

import click
import logging
import os

logger = logging.getLogger(__name__)


@click.group()
def grpc():
    """Manage gRPC streaming server for real-time metrics."""
    pass


@grpc.command()
@click.option(
    "--port",
    default=50051,
    type=int,
    help="gRPC server port (default: 50051)",
)
@click.option(
    "--host",
    default="0.0.0.0",
    help="gRPC server host (default: 0.0.0.0)",
)
@click.option(
    "--tls-cert",
    type=click.Path(exists=True),
    help="Path to TLS certificate file",
)
@click.option(
    "--tls-key",
    type=click.Path(exists=True),
    help="Path to TLS key file",
)
@click.option(
    "--log-level",
    type=click.Choice(["DEBUG", "INFO", "WARNING", "ERROR"]),
    default="INFO",
    help="Logging level",
)
def start(port, host, tls_cert, tls_key, log_level):
    """Start the gRPC streaming server for real-time metrics.
    
    This server provides real-time streaming of deployment metrics,
    resource usage, and health monitoring data to external systems
    like the Telemetry dashboard.
    
    Example:
        sega grpc start --port 50051
        sega grpc start --tls-cert cert.pem --tls-key key.pem
    """
    # Configure logging
    logging.basiconfig(
        level=getattr(logging, log_level),
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    try:
        from ...api.grpc_server import start_grpc_server
        
        # Set environment variables for TLS if provided
        if tls_cert and tls_key:
            os.environ["SEGA_GRPC_TLS_CERT"] = tls_cert
            os.environ["SEGA_GRPC_TLS_KEY"] = tls_key
            click.echo(f"Starting gRPC server with TLS on {host}:{port}")
        else:
            click.echo(f"Starting gRPC server without TLS on {host}:{port}")
            
        click.echo("gRPC metrics streaming server is starting...")
        click.echo(f"Streaming endpoint: {host}:{port}")
        click.echo("Press Ctrl+C to stop the server")
        
        # Start the server
        start_grpc_server(port=port)
        
    except ImportError as e:
        click.echo(f"Error: Missing gRPC dependencies - {e}", err=True)
        click.echo("Install with: pip install grpcio grpcio-tools", err=True)
        raise click.Abort()
    except KeyboardInterrupt:
        click.echo("\nShutting down gRPC server...")
    except Exception as e:
        logger.error(f"Failed to start gRPC server: {e}")
        raise click.ClickException(str(e))


@grpc.command()
def status():
    """Check gRPC server status."""
    import grpc
    
    # Try to connect to default port
    port = int(os.environ.get("SEGA_GRPC_PORT", 50051))
    channel_target = f"localhost:{port}"
    
    try:
        # Create a channel and try to connect
        channel = grpc.insecure_channel(channel_target)
        
        # Try to check channel connectivity
        try:
            grpc.channel_ready_future(channel).result(timeout=5)
            click.echo(f"[OK] gRPC server is running on port {port}")
            
            # Try to get service info if protobuf is available
            try:
                from ..proto import sega_metrics_pb2, sega_metrics_pb2_grpc
                
                stub = sega_metrics_pb2_grpc.MetricserviceStub(channel)
                # Make a simple request to verify service is responding
                request = sega_metrics_pb2.MetricsStreamRequest()
                response = stub.GetMetricSnapshot(request, timeout=2)
                
                click.echo("[OK] Metricservice is responding")
                click.echo(f"  Current metrics: {len(response.events)} events")
                
            except ImportError:
                click.echo("[WARNING] Protobuf files not generated (run protoc to enable full functionality)")
            except Exception as e:
                click.echo(f"[WARNING] Metricservice error: {e}")
                
        except grpc.FutureTimeoutError:
            click.echo(f"[ERROR] gRPC server is not running on port {port}")
            
    except Exception as e:
        click.echo(f"[ERROR] Error checking gRPC server: {e}", err=True)
        
    finally:
        if 'channel' in locals():
            channel.close()


@grpc.command()
def generate_proto():
    """Generate Python code from protobuf definitions."""
    import subprocess
    import sys
    from pathlib import Path
    
    # Find proto directory
    proto_dir = Path(__file__).parent.parent / "proto"
    
    if not proto_dir.exists():
        click.echo(f"Error: Proto directory not found at {proto_dir}", err=True)
        raise click.Abort()
        
    # Find sega_metrics.proto
    proto_file = proto_dir / "sega_metrics.proto"
    
    if not proto_file.exists():
        click.echo(f"Error: Proto file not found at {proto_file}", err=True)
        raise click.Abort()
        
    click.echo(f"Generating Python code from {proto_file}")
    
    try:
        # Run protoc to generate Python files
        cmd = [
            sys.executable, "-m", "grpc_tools.protoc",
            f"-I{proto_dir}",
            f"--python_out={proto_dir}",
            f"--grpc_python_out={proto_dir}",
            str(proto_file)
        ]
        
        result = subprocess.run(cmd, capture_output=True, text=True)
        
        if result.returncode == 0:
            click.echo("[OK] Successfully generated Python protobuf files:")
            click.echo(f"  - {proto_dir}/sega_metrics_pb2.py")
            click.echo(f"  - {proto_dir}/sega_metrics_pb2_grpc.py")
        else:
            click.echo("Error generating protobuf files:", err=True)
            click.echo(result.stderr, err=True)
            raise click.Abort()
            
    except subprocess.CalledProcessError as e:
        click.echo(f"Error running protoc: {e}", err=True)
        raise click.Abort()
    except Exception as e:
        click.echo(f"Error: {e}", err=True)
        click.echo("Make sure grpcio-tools is installed: pip install grpcio-tools", err=True)
        raise click.Abort()