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
SEGA Production Setup Module
==============================================================================
File: src/sega/deployment/production_setup.py
Project: SEGA (Scalable Engineering & Growth Automation)
Copyright: 2022-2025 FLEET
License: Apache-2.0

SEGA MODULE: Deployment/ProductionSetup
COMPONENT: Production Infrastructure Generator
PURPOSE: Generate docker-compose, nginx, and deployment scripts for production
DEPENDENCIES: pathlib, yaml, logging

Consolidated from scripts/deploy/prod_docker_setup.sh
==============================================================================
"""

import logging
import os
from pathlib import Path
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)

# Default deploy root; override with SEGA_DEPLOY_ROOT.
DEFAULT_DEPLOY_ROOT = os.getenv("SEGA_DEPLOY_ROOT", "/opt/sega-production")


@dataclass
class ProductionConfig:
    """Configuration for production deployment setup."""
    deploy_root: str = field(default_factory=lambda: DEFAULT_DEPLOY_ROOT)
    registry: str = ""  # Must be set by user
    version: str = "latest"
    postgres_password: str = "CHANGE_THIS_STRONG_PASSWORD"
    redis_password: str = "CHANGE_THIS_STRONG_PASSWORD"
    projects: List[str] = field(default_factory=lambda: _default_production_projects())


def _default_production_projects() -> List[str]:
    """Default production project set, from `[ship] production_projects` config."""
    from sega.core.config import get_config
    return list(get_config().ship.production_projects)


class ProductionSetup:
    """Generate production deployment infrastructure."""

    def __init__(self, config: ProductionConfig):
        self.config = config
        self.deploy_path = Path(config.deploy_root)

    def generate_docker_compose(self) -> str:
        """Generate docker-compose.yml content."""
        services = {
            "postgres": {
                "image": "postgres:15-alpine",
                "environment": {
                    "POSTGRES_PASSWORD": "${POSTGRES_PASSWORD}",
                    "POSTGRES_USER": "fleet_user",
                    "POSTGRES_DB": "fleet_production",
                },
                "volumes": ["postgres_data:/var/lib/postgresql/data"],
                "ports": ["127.0.0.1:5432:5432"],
                "restart": "unless-stopped",
                "healthcheck": {
                    "test": ["CMD-SHELL", "pg_isready -U fleet_user"],
                    "interval": "10s",
                    "timeout": "5s",
                    "retries": 5,
                },
            },
            "redis": {
                "image": "redis:7-alpine",
                "command": "redis-server --requirepass ${REDIS_PASSWORD}",
                "volumes": ["redis_data:/data"],
                "ports": ["127.0.0.1:6379:6379"],
                "restart": "unless-stopped",
                "healthcheck": {
                    "test": ["CMD", "redis-cli", "ping"],
                    "interval": "10s",
                    "timeout": "5s",
                    "retries": 5,
                },
            },
        }

        # Add project services. Published ports are curated per-deployment data
        # sourced from the `[ship] production_ports` config map.
        from sega.core.config import get_config
        _cfg = get_config()
        project_ports = _cfg.ship.production_ports
        telemetry_project = _cfg.fleet.telemetry_project

        for project in self.config.projects:
            ports = project_ports.get(project, ["3001"])
            port_mappings = [f"127.0.0.1:{p}:{p}" for p in ports]

            services[project] = {
                "image": f"${{REGISTRY}}/fleet/{project}:${{VERSION}}",
                "environment": {
                    "DATABASE_URL": "postgresql://fleet_user:${POSTGRES_PASSWORD}@postgres:5432/fleet_production",
                    "REDIS_URL": "redis://:${REDIS_PASSWORD}@redis:6379/0",
                    "ENVIRONMENT": "production",
                },
                "depends_on": {
                    "postgres": {"condition": "service_healthy"},
                    "redis": {"condition": "service_healthy"},
                },
                "ports": port_mappings,
                "restart": "unless-stopped",
            }

            # Add telemetry-backend dependency for metrics-enabled services
            if (
                telemetry_project
                and project != telemetry_project
                and telemetry_project in self.config.projects
            ):
                services[project]["environment"]["SEGA_TELEMETRY_TCP_HOST"] = telemetry_project
                services[project]["environment"][f"{telemetry_project.upper()}_TCP_PORT"] = str(
                    _cfg.telemetry.tcp_protobuf_port
                )
                services[project]["depends_on"][telemetry_project] = {"condition": "service_healthy"}

        # Build YAML manually for control
        lines = ["version: '3.8'", "", "services:"]

        for name, svc in services.items():
            lines.append(f"  {name}:")
            for key, value in svc.items():
                if key == "environment" and isinstance(value, dict):
                    lines.append(f"    {key}:")
                    for env_key, env_val in value.items():
                        lines.append(f"      {env_key}: {env_val}")
                elif key == "depends_on" and isinstance(value, dict):
                    lines.append(f"    {key}:")
                    for dep_name, dep_cond in value.items():
                        lines.append(f"      {dep_name}:")
                        for cond_key, cond_val in dep_cond.items():
                            lines.append(f"        {cond_key}: {cond_val}")
                elif key == "healthcheck" and isinstance(value, dict):
                    lines.append(f"    {key}:")
                    for hc_key, hc_val in value.items():
                        if isinstance(hc_val, list):
                            lines.append(f"      {hc_key}: {hc_val}")
                        else:
                            lines.append(f"      {hc_key}: {hc_val}")
                elif isinstance(value, list):
                    lines.append(f"    {key}:")
                    for item in value:
                        lines.append(f"      - \"{item}\"")
                else:
                    lines.append(f"    {key}: {value}")
            lines.append("")

        lines.extend([
            "volumes:",
            "  postgres_data:",
            "  redis_data:",
            "",
            "networks:",
            "  default:",
            "    name: fleet_production",
        ])

        return "\n".join(lines)

    def generate_env_template(self) -> str:
        """Generate .env.production template."""
        return """# FLEET Production Environment Configuration
# EDIT THIS FILE WITH YOUR PRODUCTION VALUES

# Registry Configuration
REGISTRY=your-registry.com
VERSION=latest

# Database Passwords (CHANGE THESE!)
POSTGRES_PASSWORD=CHANGE_THIS_STRONG_PASSWORD
REDIS_PASSWORD=CHANGE_THIS_STRONG_PASSWORD

# Application Configuration
ENVIRONMENT=production
DEBUG=false
SECRET_KEY=CHANGE_THIS_GENERATED_SECRET

# Auth0 Configuration
AUTH0_DOMAIN=fleet-labs.auth0.com
AUTH0_CLIENT_ID=CHANGE_THIS_PRODUCTION_CLIENT_ID
AUTH0_CLIENT_SECRET=CHANGE_THIS_PRODUCTION_SECRET
AUTH0_AUDIENCE=https://api.fleet-dev.example.com

# External Services
MAILGUN_API_KEY=CHANGE_THIS_PRODUCTION_KEY
MAILGUN_DOMAIN=mg.example.ai
SENTRY_DSN=CHANGE_THIS_PRODUCTION_DSN
SENTRY_ENVIRONMENT=production

# Monitoring
METRICS_ENABLED=true
PROMETHEUS_ENABLED=true
GRAFANA_ENABLED=true
"""

    def generate_deploy_script(self) -> str:
        """Generate deploy.sh script."""
        from sega.core.config import get_config
        _cfg = get_config()
        migrate_services = " ".join(sorted(self.config.projects))
        telemetry_project = _cfg.fleet.telemetry_project
        telemetry_first = ""
        if telemetry_project and telemetry_project in self.config.projects:
            telemetry_first = (
                f"docker-compose up -d --no-deps {telemetry_project}\nsleep 5\n"
            )
        return f"""#!/bin/bash
# FLEET Production Deployment Script

set -e

echo "Starting deployment..."

# Load environment
source .env.production

# Pull latest images
echo "Pulling latest images..."
docker-compose pull

# Backup database
echo "Backing up database..."
docker-compose exec -T postgres pg_dumpall -U fleet_user > backup_$(date +%Y%m%d_%H%M%S).sql

# Deploy with rolling update
echo "Deploying services..."
docker-compose up -d --no-deps postgres redis
sleep 10

# Run migrations
echo "Running database migrations..."
for service in {migrate_services}; do
    if docker-compose ps $service > /dev/null 2>&1; then
        echo "Migrating $service..."
        docker-compose run --rm $service python manage.py migrate || true
    fi
done

# Start application services
{telemetry_first}docker-compose up -d

# Health check
echo "Running health checks..."
sleep 10
docker-compose ps

echo "Deployment complete!"
"""

    def generate_rollback_script(self) -> str:
        """Generate rollback.sh script."""
        return """#!/bin/bash
# FLEET Production Rollback Script

set -e

echo "Rolling back to previous version..."

# Load environment
source .env.production

# Set previous version
PREVIOUS_VERSION=${1:-previous}

# Update version in environment
sed -i "s/VERSION=.*/VERSION=$PREVIOUS_VERSION/" .env.production

# Pull previous images
docker-compose pull

# Deploy previous version
docker-compose up -d

echo "Rollback complete!"
"""

    def generate_monitor_script(self) -> str:
        """Generate monitor.sh script."""
        return """#!/bin/bash
# FLEET Production Monitoring Script

echo "=== FLEET Production Status ==="
echo ""

# Container status
echo "Container Status:"
docker-compose ps

echo ""
echo "Resource Usage:"
docker stats --no-stream

echo ""
echo "Health Endpoints:"
for port in 3001 3002 3005; do
    echo -n "Port $port: "
    curl -s http://localhost:$port/health | jq -r '.status' 2>/dev/null || echo "unavailable"
done

echo ""
echo "Recent Logs:"
docker-compose logs --tail=10
"""

    def generate_backup_script(self) -> str:
        """Generate backup.sh script."""
        return """#!/bin/bash
# FLEET Production Backup Script

BACKUP_DIR="/opt/backups"
DATE=$(date +%Y%m%d_%H%M%S)

# Create backup directory
sudo mkdir -p $BACKUP_DIR

# Backup databases
echo "Backing up databases..."
docker-compose exec -T postgres pg_dumpall -U fleet_user > $BACKUP_DIR/postgres_$DATE.sql

# Backup Redis
echo "Backing up Redis..."
docker-compose exec -T redis redis-cli --rdb /data/dump.rdb BGSAVE
sleep 5
docker cp $(docker-compose ps -q redis):/data/dump.rdb $BACKUP_DIR/redis_$DATE.rdb

# Backup environment
cp .env.production $BACKUP_DIR/env_$DATE

# Compress backups
tar -czf $BACKUP_DIR/fleet_backup_$DATE.tar.gz \\
    $BACKUP_DIR/postgres_$DATE.sql \\
    $BACKUP_DIR/redis_$DATE.rdb \\
    $BACKUP_DIR/env_$DATE

# Clean up old backups (keep last 7 days)
find $BACKUP_DIR -name "fleet_backup_*.tar.gz" -mtime +7 -delete

echo "Backup complete: $BACKUP_DIR/fleet_backup_$DATE.tar.gz"
"""

    def generate_nginx_config(self) -> str:
        """Generate nginx site configuration."""
        upstreams = []
        servers = []

        # Domains are read from central config (config.get_domain(name)); the
        # nginx-facing ports are curated legacy values that match no config
        # port formula, sourced from the `[ship] nginx_ports` config map.
        from sega.core.config import get_config
        _cfg = get_config()

        project_ports = _cfg.ship.nginx_ports

        for project in self.config.projects:
            domain = _cfg.get_domain(project)
            if domain and project in project_ports:
                port = project_ports.get(project, 3001)

                upstreams.append(f"""upstream {project}_backend {{
    server 127.0.0.1:{port};
}}""")

                servers.append(f"""server {{
    listen 443 ssl http2;
    server_name {domain} www.{domain};

    # SSL configuration (managed by Certbot)

    location / {{
        proxy_pass http://{project}_backend;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;

        proxy_connect_timeout 60s;
        proxy_send_timeout 60s;
        proxy_read_timeout 60s;
    }}
}}""")

        # Default server for health checks
        default_server = """# Default server
server {
    listen 80 default_server;
    server_name _;

    location /health {
        access_log off;
        return 200 "healthy\\n";
        add_header Content-Type text/plain;
    }

    location / {
        return 301 https://$host$request_uri;
    }
}"""

        return "\n\n".join([
            "# FLEET Production Nginx Configuration",
            "",
            "# Upstream definitions",
            "\n\n".join(upstreams),
            "",
            default_server,
            "",
            "# Application servers",
            "\n\n".join(servers),
        ])

    def setup(self, dry_run: bool = False) -> Dict[str, Any]:
        """Generate all production deployment files."""
        result = {
            "success": True,
            "files_created": [],
            "messages": [],
        }

        files_to_create = {
            "docker-compose.yml": self.generate_docker_compose(),
            ".env.production": self.generate_env_template(),
            "deploy.sh": self.generate_deploy_script(),
            "rollback.sh": self.generate_rollback_script(),
            "monitor.sh": self.generate_monitor_script(),
            "backup.sh": self.generate_backup_script(),
        }

        if dry_run:
            result["messages"].append(f"DRY RUN: Would create {len(files_to_create)} files in {self.deploy_path}")
            for filename in files_to_create:
                result["files_created"].append(str(self.deploy_path / filename))
            return result

        try:
            self.deploy_path.mkdir(parents=True, exist_ok=True)

            for filename, content in files_to_create.items():
                filepath = self.deploy_path / filename
                filepath.write_text(content)
                result["files_created"].append(str(filepath))

                # Make scripts executable
                if filename.endswith(".sh"):
                    filepath.chmod(0o755)

            # Generate nginx config separately (goes to /etc/nginx)
            nginx_config = self.generate_nginx_config()
            nginx_path = self.deploy_path / "nginx-sega-production.conf"
            nginx_path.write_text(nginx_config)
            result["files_created"].append(str(nginx_path))
            result["messages"].append(
                f"Nginx config generated. Copy to /etc/nginx/sites-available/ and enable."
            )

            result["messages"].append(f"Production setup complete in {self.deploy_path}")
            result["messages"].append("Next steps:")
            result["messages"].append("1. Edit .env.production with your values")
            result["messages"].append("2. Configure Docker registry access: docker login")
            result["messages"].append("3. Run ./deploy.sh")

        except Exception as e:
            result["success"] = False
            result["messages"].append(f"Error: {e}")

        return result


def setup_production(
    deploy_root: str = DEFAULT_DEPLOY_ROOT,
    projects: Optional[List[str]] = None,
    dry_run: bool = False
) -> Dict[str, Any]:
    """Convenience function for production setup."""
    config = ProductionConfig(
        deploy_root=deploy_root,
        projects=projects or _default_production_projects()
    )
    setup = ProductionSetup(config)
    return setup.setup(dry_run)
