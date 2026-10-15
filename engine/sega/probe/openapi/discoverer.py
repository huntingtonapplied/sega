"""
OpenAPI Discoverer
==================
Fetches and parses OpenAPI schemas from running backend services.
"""

import asyncio
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

import httpx

from ...core.config import get_config
from .models import DiscoveredAPI
from .schema_parser import OpenAPISchemaParser


# Project set sourced from the curated `[fleet] api_test_projects` config list
# (discover_all() defaults to the operator-configured set); port VALUES come
# from central config (api port = 8000 + id).
# AUTHORITATIVE: /docs/standards/infrastructure/PORT_ALLOCATION_STANDARDS.md
_DISCOVERY_PROJECTS = list(get_config().fleet.api_test_projects)


def _build_discovery_ports() -> Dict[str, int]:
    """Build {project: api_port} from central config (api port = 8000 + id)."""
    cfg = get_config()
    ports: Dict[str, int] = {}
    for name in _DISCOVERY_PROJECTS:
        proj = cfg.get_project(name)
        if proj is None:
            continue
        ports[name] = proj.ports.api
    return ports


@dataclass
class DiscoveryConfig:
    """Configuration for OpenAPI discovery."""

    openapi_paths: List[str] = field(
        default_factory=lambda: [
            "/api/openapi.json",
            "/api/v1/openapi.json",
            "/openapi.json",
        ]
    )
    timeout: float = 30.0
    include_deprecated: bool = False
    auth_token: Optional[str] = None


@dataclass
class DiscoveryResult:
    """Result of discovering a single project's API."""

    project: str
    success: bool
    api: Optional[DiscoveredAPI] = None
    error: Optional[str] = None
    openapi_url: Optional[str] = None


class OpenAPIDiscoverer:
    """Discovers and parses OpenAPI schemas from running services."""

    # Default port mapping (api port), derived from central config.
    PROJECT_PORTS = _build_discovery_ports()

    def __init__(self, config: Optional[DiscoveryConfig] = None):
        self.config = config or DiscoveryConfig()
        self.parser = OpenAPISchemaParser()

    def get_base_url(self, project: str, host: str = "localhost") -> str:
        """Get base URL for a project."""
        port = self.PROJECT_PORTS.get(project, 8000)
        return f"http://{host}:{port}"

    async def discover(
        self,
        project: str,
        host: str = "localhost",
        base_url: Optional[str] = None,
    ) -> DiscoveryResult:
        """
        Discover OpenAPI schema from a running service.

        Tries multiple common OpenAPI paths until one succeeds.

        Args:
            project: Project name (e.g., "atlas")
            host: Host where service is running
            base_url: Override base URL (otherwise derived from project port)

        Returns:
            DiscoveryResult with parsed API or error
        """
        if base_url is None:
            base_url = self.get_base_url(project, host)

        for path in self.config.openapi_paths:
            url = f"{base_url}{path}"
            try:
                schema = await self._fetch_schema(url)
                if schema:
                    api = self.parser.parse(schema, project, base_url)

                    # Filter deprecated endpoints if configured
                    if not self.config.include_deprecated:
                        api.endpoints = [
                            ep for ep in api.endpoints if not ep.deprecated
                        ]

                    return DiscoveryResult(
                        project=project,
                        success=True,
                        api=api,
                        openapi_url=url,
                    )
            except Exception as e:
                continue

        return DiscoveryResult(
            project=project,
            success=False,
            error=f"Could not fetch OpenAPI schema from {base_url}",
        )

    async def discover_multiple(
        self,
        projects: List[str],
        host: str = "localhost",
    ) -> List[DiscoveryResult]:
        """
        Discover OpenAPI schemas from multiple projects in parallel.

        Args:
            projects: List of project names
            host: Host where services are running

        Returns:
            List of DiscoveryResults
        """
        tasks = [self.discover(project, host) for project in projects]
        return await asyncio.gather(*tasks)

    async def discover_all(
        self,
        host: str = "localhost",
    ) -> List[DiscoveryResult]:
        """Discover OpenAPI schemas from all known projects."""
        return await self.discover_multiple(list(self.PROJECT_PORTS.keys()), host)

    async def _fetch_schema(self, url: str) -> Optional[Dict[str, Any]]:
        """Fetch OpenAPI schema from URL."""
        headers = {"Accept": "application/json"}
        if self.config.auth_token:
            headers["Authorization"] = f"Bearer {self.config.auth_token}"

        async with httpx.AsyncClient(timeout=self.config.timeout) as client:
            response = await client.get(url, headers=headers)
            if response.status_code == 200:
                return response.json()
        return None


def print_discovery_results(results: List[DiscoveryResult]) -> None:
    """Pretty print discovery results."""
    print("\n" + "=" * 60)
    print("OPENAPI DISCOVERY RESULTS")
    print("=" * 60)

    successful = [r for r in results if r.success]
    failed = [r for r in results if not r.success]

    for result in successful:
        api = result.api
        print(f"\n{result.project.upper()} [DISCOVERED]")
        print(f"  URL: {result.openapi_url}")
        print(f"  Title: {api.title}")
        print(f"  Endpoints: {api.endpoint_count}")
        print(f"  Resources: {', '.join(api.resources[:5])}")
        if len(api.resources) > 5:
            print(f"             ... and {len(api.resources) - 5} more")

    if failed:
        print("\n" + "-" * 60)
        print("FAILED TO DISCOVER:")
        for result in failed:
            print(f"  {result.project}: {result.error}")

    print("\n" + "=" * 60)
    print(f"SUMMARY: {len(successful)}/{len(results)} projects discovered")
    print("=" * 60)
