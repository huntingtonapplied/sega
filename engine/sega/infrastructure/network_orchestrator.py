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
SEGA NETWORK ORCHESTRATOR
=============================================================================
Orchestrates network-wide operations across VPN infrastructure.
"""

import asyncio
import logging
from typing import Dict, List, Optional, Any
from dataclasses import dataclass
import aiohttp

logger = logging.getLogger(__name__)


@dataclass
class NetworkNode:
    """Network node representation."""

    name: str
    ip: str
    type: str  # backend, engine, runner, edge
    services: List[str]
    status: str


class NetworkOrchestrator:
    """Orchestrates operations across the VPN network."""

    def __init__(self):
        self.nodes = {}
        self.service_registry = {}

    async def discover_network(
        self, subnet: str = "10.8.0.0/16"
    ) -> Dict[str, Any]:
        """Discover all nodes and services on the VPN network."""
        logger.info(f"Discovering network: {subnet}")

        # In production, use nmap or similar. For now, return the known
        # topology from the `[network.discovery]` config tables (operator
        # data; ships empty for new installs).
        from sega.core.config import get_config
        discovered = {
            category: [dict(node) for node in nodes]
            for category, nodes in get_config().network.discovery.items()
        }

        # Register discovered nodes
        for category, nodes in discovered.items():
            for node_info in nodes:
                node = NetworkNode(
                    name=f"{node_info['service']}-{node_info['ip']}",
                    ip=node_info["ip"],
                    type=category.rstrip("s"),  # Remove plural
                    services=[node_info["service"]],
                    status="discovered",
                )
                self.nodes[node.name] = node

        return {
            "status": "success",
            "discovered": discovered,
            "total_nodes": sum(len(nodes) for nodes in discovered.values()),
        }

    async def health_check_all(self) -> Dict[str, Any]:
        """Perform health checks on all registered nodes."""
        logger.info("Running network-wide health check")

        results = {}
        tasks = []

        for node in self.nodes.values():
            task = self._check_node_health(node)
            tasks.append(task)

        health_results = await asyncio.gather(*tasks, return_exceptions=True)

        for node, result in zip(self.nodes.values(), health_results):
            if isinstance(result, Exception):
                results[node.name] = {"status": "error", "error": str(result)}
            else:
                results[node.name] = result
                node.status = result["status"]

        healthy_count = sum(
            1 for r in results.values() if r["status"] == "healthy"
        )

        return {
            "total_nodes": len(self.nodes),
            "healthy": healthy_count,
            "unhealthy": len(self.nodes) - healthy_count,
            "results": results,
        }

    async def deploy_service(
        self, service_name: str, config: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Deploy a service across the network."""
        logger.info(f"Deploying service: {service_name}")

        # Find suitable nodes based on requirements
        suitable_nodes = self._find_suitable_nodes(
            config.get("requirements", {})
        )

        if not suitable_nodes:
            return {
                "status": "error",
                "error": "No suitable nodes found for deployment",
            }

        # Deploy to selected nodes
        deployment_tasks = []
        for node in suitable_nodes[: config.get("replicas", 1)]:
            task = self._deploy_to_node(node, service_name, config)
            deployment_tasks.append(task)

        results = await asyncio.gather(
            *deployment_tasks, return_exceptions=True
        )

        successful = [
            r
            for r in results
            if not isinstance(r, Exception) and r.get("status") == "success"
        ]

        # Update service registry
        self.service_registry[service_name] = {
            "nodes": [n.name for n in suitable_nodes[: len(successful)]],
            "config": config,
            "status": "deployed",
        }

        return {
            "status": "success" if successful else "failed",
            "service": service_name,
            "deployed_to": len(successful),
            "results": results,
        }

    async def route_traffic(
        self, source: str, destination: str, protocol: str = "http"
    ) -> Dict[str, Any]:
        """Configure traffic routing between services."""
        logger.info(f"Routing traffic from {source} to {destination}")

        # Find source and destination nodes
        src_nodes = [n for n in self.nodes.values() if source in n.services]
        dst_nodes = [
            n for n in self.nodes.values() if destination in n.services
        ]

        if not src_nodes or not dst_nodes:
            return {
                "status": "error",
                "error": "Source or destination service not found",
            }

        # Configure routing (simplified)
        routing_config = {
            "source": src_nodes[0].ip,
            "destination": dst_nodes[0].ip,
            "protocol": protocol,
            "port": self._get_service_port(destination),
        }

        # In production, configure actual network routing
        logger.info(f"Configured routing: {routing_config}")

        return {"status": "success", "routing": routing_config}

    async def execute_workflow(
        self, workflow: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Execute a distributed workflow across the network."""
        logger.info(f"Executing workflow: {workflow.get('name', 'unnamed')}")

        results = {}

        for step in workflow.get("steps", []):
            step_name = step["name"]

            if step["type"] == "parallel":
                # Execute parallel tasks
                tasks = []
                for task in step["tasks"]:
                    node = self._find_node_for_service(task["service"])
                    if node:
                        tasks.append(self._execute_task(node, task))

                step_results = await asyncio.gather(
                    *tasks, return_exceptions=True
                )
                results[step_name] = step_results

            elif step["type"] == "sequential":
                # Execute sequential tasks
                step_results = []
                for task in step["tasks"]:
                    node = self._find_node_for_service(task["service"])
                    if node:
                        result = await self._execute_task(node, task)
                        step_results.append(result)

                        # Check if should continue
                        if result.get("status") == "error" and not task.get(
                            "continue_on_error"
                        ):
                            break

                results[step_name] = step_results

        return {
            "workflow": workflow.get("name"),
            "status": "completed",
            "results": results,
        }

    async def balance_load(self, service: str) -> Dict[str, Any]:
        """Balance load across service instances."""
        if service not in self.service_registry:
            return {"status": "error", "error": f"Service {service} not found"}

        service_info = self.service_registry[service]
        nodes = [
            self.nodes[n] for n in service_info["nodes"] if n in self.nodes
        ]

        if len(nodes) < 2:
            return {
                "status": "no_action",
                "message": "Not enough nodes for load balancing",
            }

        # Get current load on each node
        await self._get_node_loads(nodes)

        # Simple round-robin for now
        # In production, use actual load metrics
        balanced_config = {
            "strategy": "round-robin",
            "nodes": [n.ip for n in nodes],
            "weights": [1] * len(nodes),
        }

        return {
            "status": "success",
            "service": service,
            "load_balancing": balanced_config,
        }

    async def _check_node_health(self, node: NetworkNode) -> Dict[str, Any]:
        """Check health of a single node."""
        health_endpoint = f"http://{node.ip}:8000/health"

        async with aiohttp.ClientSession() as session:
            try:
                async with session.get(
                    health_endpoint, timeout=aiohttp.ClientTimeout(total=5)
                ) as response:
                    if response.status == 200:
                        data = await response.json()
                        return {
                            "status": "healthy",
                            "services": node.services,
                            "metrics": data.get("metrics", {}),
                        }
                    else:
                        return {
                            "status": "unhealthy",
                            "http_status": response.status,
                        }
            except Exception as e:
                return {"status": "unreachable", "error": str(e)}

    def _find_suitable_nodes(
        self, requirements: Dict[str, Any]
    ) -> List[NetworkNode]:
        """Find nodes that meet deployment requirements."""
        suitable = []

        for node in self.nodes.values():
            if node.status != "healthy":
                continue

            # Check node type requirement
            if (
                requirements.get("node_type")
                and node.type != requirements["node_type"]
            ):
                continue

            # Check service requirements
            required_services = requirements.get("services", [])
            if not all(svc in node.services for svc in required_services):
                continue

            suitable.append(node)

        return suitable

    async def _deploy_to_node(
        self, node: NetworkNode, service: str, config: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Deploy service to a specific node."""
        deploy_endpoint = f"http://{node.ip}:8000/deploy"

        async with aiohttp.ClientSession() as session:
            try:
                async with session.post(
                    deploy_endpoint,
                    json={"service": service, "config": config},
                    timeout=aiohttp.ClientTimeout(total=30),
                ) as response:
                    return await response.json()
            except Exception as e:
                return {"status": "error", "error": str(e)}

    def _find_node_for_service(self, service: str) -> Optional[NetworkNode]:
        """Find a node running a specific service."""
        for node in self.nodes.values():
            if service in node.services and node.status == "healthy":
                return node
        return None

    async def _execute_task(
        self, node: NetworkNode, task: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Execute a task on a node."""
        endpoint = f"http://{node.ip}:{self._get_service_port(task['service'])}/execute"

        async with aiohttp.ClientSession() as session:
            try:
                async with session.post(
                    endpoint,
                    json=task.get("params", {}),
                    timeout=aiohttp.ClientTimeout(
                        total=task.get("timeout", 60)
                    ),
                ) as response:
                    return await response.json()
            except Exception as e:
                return {"status": "error", "error": str(e)}

    def _get_service_port(self, service: str) -> int:
        """Get default port for a service.

        Sourced from the `[network.service_ports]` config map, falling back to
        `[network] default_service_port` (operator data; ships empty).
        """
        from sega.core.config import get_config
        net = get_config().network
        return net.service_ports.get(service, net.default_service_port)

    async def _get_node_loads(
        self, nodes: List[NetworkNode]
    ) -> Dict[str, float]:
        """Get current load on nodes."""
        loads = {}

        for node in nodes:
            # In production, query actual metrics
            loads[node.name] = 0.5  # Placeholder

        return loads
