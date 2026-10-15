#!/usr/bin/env python3
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

"""
SEGA ENGINE COMPONENT DEPLOYER
=============================================================================
Deploys and manages compute engine components across the VPN network.
"""

import logging
import subprocess
from typing import Dict, List, Optional, Any
import aiohttp
from dataclasses import dataclass

logger = logging.getLogger(__name__)


@dataclass
class EngineNode:
    """Engine node configuration."""

    name: str
    type: str  # engine type key from the [engines.<name>] config tables
    host: str
    vpn_ip: str
    capabilities: List[str]
    resources: Dict[str, Any]


class EngineDeployer:
    """Manages engine component deployment across VPN nodes."""

    def __init__(self):
        self.engine_registry = {}
        self.deployment_configs = self._load_engine_configs()

    def deploy_engine(
        self, engine_type: str, target_host: str, **kwargs
    ) -> Dict[str, Any]:
        """
        Deploy an engine component to a VPN node.

        Args:
            engine_type: Type of engine (a configured [engines.<name>] key)
            target_host: VPN IP or hostname
            **kwargs: Engine-specific configuration

        Returns:
            Deployment result
        """
        logger.info(f"Deploying {engine_type} engine to {target_host}")

        if engine_type not in self.deployment_configs:
            return {
                "status": "error",
                "error": f"Unknown engine type: {engine_type}",
            }

        config = self.deployment_configs[engine_type]

        # Generate deployment script
        script = self._generate_deployment_script(engine_type, config, kwargs)

        # Deploy via SSH
        try:
            result = subprocess.run(
                ["ssh", f"root@{target_host}", "bash -s"],
                input=script.encode(),
                capture_output=True,
                text=True,
            )

            if result.returncode == 0:
                # Register engine node
                node = EngineNode(
                    name=f"{engine_type}-{target_host}",
                    type=engine_type,
                    host=target_host,
                    vpn_ip=kwargs.get("vpn_ip", target_host),
                    capabilities=config.get("capabilities", []),
                    resources=kwargs.get("resources", {}),
                )
                self.engine_registry[node.name] = node

                logger.info(f"{engine_type} engine deployed successfully")
                return {
                    "status": "success",
                    "engine": engine_type,
                    "host": target_host,
                    "endpoints": self._get_engine_endpoints(
                        engine_type, target_host
                    ),
                }
            else:
                logger.error(f"Engine deployment failed: {result.stderr}")
                return {"status": "failed", "error": result.stderr}

        except Exception as e:
            logger.error(f"Engine deployment error: {e}")
            return {"status": "error", "error": str(e)}

    def scale_engine(self, engine_type: str, replicas: int) -> Dict[str, Any]:
        """Scale an engine component horizontally."""
        logger.info(f"Scaling {engine_type} engine to {replicas} replicas")

        current_nodes = [
            n for n in self.engine_registry.values() if n.type == engine_type
        ]
        current_count = len(current_nodes)

        if replicas > current_count:
            # Scale up
            needed = replicas - current_count
            available_hosts = self._get_available_hosts(engine_type)

            if len(available_hosts) < needed:
                return {
                    "status": "partial",
                    "message": f"Only {len(available_hosts)} hosts available for scaling",
                }

            results = []
            for i in range(needed):
                result = self.deploy_engine(engine_type, available_hosts[i])
                results.append(result)

            return {
                "status": "success",
                "scaled_to": replicas,
                "deployments": results,
            }

        elif replicas < current_count:
            # Scale down
            to_remove = current_count - replicas
            removed = []

            for i in range(to_remove):
                node = current_nodes[i]
                if self.undeploy_engine(node.name):
                    removed.append(node.name)

            return {
                "status": "success",
                "scaled_to": replicas,
                "removed": removed,
            }

        return {"status": "no_change", "current_replicas": current_count}

    def undeploy_engine(self, node_name: str) -> bool:
        """Remove an engine deployment."""
        if node_name not in self.engine_registry:
            return False

        node = self.engine_registry[node_name]
        logger.info(f"Undeploying engine {node_name} from {node.host}")

        try:
            # Stop engine services
            subprocess.run(
                ["ssh", f"root@{node.host}", "systemctl stop fleet-engine-*"],
                check=True,
            )

            # Remove from registry
            del self.engine_registry[node_name]
            return True

        except Exception as e:
            logger.error(f"Failed to undeploy engine: {e}")
            return False

    def get_engine_status(
        self, engine_type: Optional[str] = None
    ) -> Dict[str, Any]:
        """Get status of deployed engines."""
        status = {"engines": {}}

        for node in self.engine_registry.values():
            if engine_type and node.type != engine_type:
                continue

            # Check health endpoint
            health = self._check_engine_health(node)

            if node.type not in status["engines"]:
                status["engines"][node.type] = []

            status["engines"][node.type].append(
                {
                    "name": node.name,
                    "host": node.host,
                    "vpn_ip": node.vpn_ip,
                    "health": health,
                    "capabilities": node.capabilities,
                    "resources": node.resources,
                }
            )

        return status

    async def orchestrate_workflow(
        self, workflow: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Orchestrate a multi-engine workflow."""
        logger.info(
            f"Orchestrating workflow: {workflow.get('name', 'unnamed')}"
        )

        results = {}

        # Execute workflow steps
        for step in workflow.get("steps", []):
            engine_type = step.get("engine")
            operation = step.get("operation")
            params = step.get("params", {})

            # Find available engine node
            nodes = [
                n
                for n in self.engine_registry.values()
                if n.type == engine_type
            ]
            if not nodes:
                results[step["name"]] = {
                    "status": "error",
                    "error": f"No {engine_type} engine available",
                }
                continue

            # Execute operation on engine
            node = nodes[0]  # Simple round-robin in production
            result = await self._execute_engine_operation(
                node, operation, params
            )
            results[step["name"]] = result

            # Check if step failed
            if result.get("status") == "error" and not step.get(
                "continue_on_error"
            ):
                break

        return {
            "workflow": workflow.get("name"),
            "status": "completed"
            if all(r.get("status") == "success" for r in results.values())
            else "partial",
            "results": results,
        }

    def _load_engine_configs(self) -> Dict[str, Dict[str, Any]]:
        """Load engine deployment configurations.

        Sourced from the `[engines.<name>]` config tables (image, ports,
        capabilities, resources, env, endpoint templates, host pools). This is
        operator-curated deployment data; ships empty for new installs.
        """
        from sega.core.config import get_config
        return {name: dict(entry) for name, entry in get_config().engines.items()}

    def _generate_deployment_script(
        self, engine_type: str, config: Dict[str, Any], kwargs: Dict[str, Any]
    ) -> str:
        """Generate engine deployment script."""
        env_vars = config.get("env", {}).copy()
        env_vars.update(kwargs.get("env", {}))

        env_exports = "\n".join(
            [f'export {k}="{v}"' for k, v in env_vars.items()]
        )
        ports = " ".join([f"-p {p}:{p}" for p in config["ports"]])

        return f"""#!/bin/bash
set -euo pipefail

# Pull latest engine image
docker pull {config['image']}

# Stop existing engine if running
docker stop fleet-engine-{engine_type} || true
docker rm fleet-engine-{engine_type} || true

# Set environment
{env_exports}

# Run engine container
docker run -d \
  --name fleet-engine-{engine_type} \
  --restart unless-stopped \
  --network host \
  {ports} \
  --env-file <(env | grep -E "^(ORION|ATLAS|ORION|FPGA|FLEET)_") \
  {config['image']}

# Create systemd service
cat > /etc/systemd/system/fleet-engine-{engine_type}.service <<EOF
[Unit]
Description=FLEET {engine_type.title()} Engine
After=docker.service
Requires=docker.service

[Service]
Type=simple
Restart=always
ExecStart=/usr/bin/docker start -a fleet-engine-{engine_type}
ExecStop=/usr/bin/docker stop fleet-engine-{engine_type}

[Install]
WantedBy=multi-user.target
EOF

systemctl daemon-reload
systemctl enable fleet-engine-{engine_type}.service

echo "Engine {engine_type} deployed successfully"
"""

    def _get_engine_endpoints(
        self, engine_type: str, host: str
    ) -> Dict[str, str]:
        """Get engine service endpoints.

        Endpoint URL templates come from the engine's `endpoints` config map
        (e.g. ``api = "http://{host}:8100"``) and are formatted with the host.
        """
        templates = self.deployment_configs.get(engine_type, {}).get("endpoints", {})
        return {label: tmpl.format(host=host) for label, tmpl in templates.items()}

    def _get_available_hosts(self, engine_type: str) -> List[str]:
        """Get available hosts for engine deployment.

        In production, query the infrastructure service; for now, return the
        engine's configured `hosts` pool (VPN IPs) from config.
        """
        return list(self.deployment_configs.get(engine_type, {}).get("hosts", []))

    def _check_engine_health(self, node: EngineNode) -> str:
        """Check engine health status."""
        endpoints = self._get_engine_endpoints(node.type, node.host)
        health_url = endpoints.get("api", "") + "/health"

        try:
            response = subprocess.run(
                [
                    "curl",
                    "-s",
                    "-o",
                    "/dev/null",
                    "-w",
                    "%{http_code}",
                    health_url,
                ],
                capture_output=True,
                text=True,
                timeout=5,
            )
            return "healthy" if response.stdout == "200" else "unhealthy"
        except (subprocess.SubprocessError, subprocess.TimeoutExpired):
            return "unknown"

    async def _execute_engine_operation(
        self, node: EngineNode, operation: str, params: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Execute operation on engine node."""
        endpoints = self._get_engine_endpoints(node.type, node.host)
        api_url = endpoints.get("api", "")

        async with aiohttp.ClientSession() as session:
            try:
                async with session.post(
                    f"{api_url}/execute",
                    json={"operation": operation, "params": params},
                    timeout=aiohttp.ClientTimeout(total=300),
                ) as response:
                    return await response.json()
            except Exception as e:
                return {"status": "error", "error": str(e)}
