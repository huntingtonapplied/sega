"""
Test Chain Builder
==================
Build test chains from discovered API schemas.
Detects CRUD patterns and creates executable test sequences.
"""

import re
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Set

from ..openapi.models import DiscoveredAPI, HttpMethod, OpenAPIEndpoint
from .extractors import ValueExtractor, create_id_extractor
from .sample_generator import SampleDataGenerator


@dataclass
class TestStep:
    """A single step in a test chain."""

    name: str
    endpoint: str  # May contain {variables}
    method: str
    body: Optional[Dict[str, Any]] = None
    headers: Optional[Dict[str, str]] = None
    expected_status: List[int] = field(default_factory=lambda: [200, 201])
    extractors: List[ValueExtractor] = field(default_factory=list)
    requires_auth: bool = False
    description: Optional[str] = None


@dataclass
class TestChain:
    """A sequence of dependent test steps."""

    name: str
    description: str
    resource: str
    steps: List[TestStep]
    tags: List[str] = field(default_factory=list)

    @property
    def step_count(self) -> int:
        return len(self.steps)


class TestChainBuilder:
    """Builds test chains from discovered API schemas."""

    def __init__(self, api: DiscoveredAPI):
        self.api = api
        self.sample_generator = SampleDataGenerator(api)

    def build_all_chains(self) -> List[TestChain]:
        """
        Build all possible test chains from the API.

        Detects CRUD patterns and creates chains for each resource.
        """
        chains = []

        # Build health check chain
        health_chain = self._build_health_chain()
        if health_chain:
            chains.append(health_chain)

        # Build CRUD chains for each resource
        for resource in self.api.resources:
            crud_chain = self.build_crud_chain(resource)
            if crud_chain:
                chains.append(crud_chain)

        # Build read-only chains for resources without full CRUD
        for resource in self.api.resources:
            if not any(c.resource == resource for c in chains if c.name.endswith("_crud")):
                read_chain = self._build_read_chain(resource)
                if read_chain:
                    chains.append(read_chain)

        return chains

    def build_crud_chain(self, resource: str) -> Optional[TestChain]:
        """
        Build a CRUD test chain for a resource.

        Chain: POST (create) -> GET (read) -> PUT/PATCH (update) -> DELETE -> GET (verify deleted)
        """
        endpoints = self.api.get_endpoints_by_resource(resource)
        if not endpoints:
            return None

        # Find CRUD endpoints
        create_ep = self._find_endpoint(endpoints, HttpMethod.POST, has_id=False)
        read_ep = self._find_endpoint(endpoints, HttpMethod.GET, has_id=True)
        update_ep = self._find_endpoint(
            endpoints, HttpMethod.PUT, has_id=True
        ) or self._find_endpoint(endpoints, HttpMethod.PATCH, has_id=True)
        delete_ep = self._find_endpoint(endpoints, HttpMethod.DELETE, has_id=True)
        list_ep = self._find_endpoint(endpoints, HttpMethod.GET, has_id=False)

        # Need at least create + read or list to make a chain
        if not create_ep and not list_ep:
            return None

        steps = []
        id_var = f"{resource}_id"

        # Step 1: Create (if available)
        if create_ep:
            sample_body = self.sample_generator.generate_for_endpoint(create_ep)
            steps.append(
                TestStep(
                    name=f"create_{resource}",
                    endpoint=create_ep.path,
                    method="POST",
                    body=sample_body,
                    expected_status=[200, 201],
                    extractors=[
                        create_id_extractor(resource, "$.id"),
                        ValueExtractor(
                            source_path="$.data.id",
                            target_variable=id_var,
                            required=False,
                        ),
                    ],
                    requires_auth=create_ep.requires_auth,
                    description=f"Create a new {resource}",
                )
            )

        # Step 2: Read by ID (if available)
        if read_ep and create_ep:
            # Substitute ID parameter
            path = self._substitute_path_param(read_ep.path, id_var)
            steps.append(
                TestStep(
                    name=f"read_{resource}",
                    endpoint=path,
                    method="GET",
                    expected_status=[200],
                    requires_auth=read_ep.requires_auth,
                    description=f"Read {resource} by ID",
                )
            )

        # Step 3: Update (if available)
        if update_ep and create_ep:
            path = self._substitute_path_param(update_ep.path, id_var)
            sample_body = self.sample_generator.generate_for_endpoint(update_ep)
            steps.append(
                TestStep(
                    name=f"update_{resource}",
                    endpoint=path,
                    method=update_ep.method.value.upper(),
                    body=sample_body,
                    expected_status=[200],
                    requires_auth=update_ep.requires_auth,
                    description=f"Update {resource}",
                )
            )

        # Step 4: Delete (if available)
        if delete_ep and create_ep:
            path = self._substitute_path_param(delete_ep.path, id_var)
            steps.append(
                TestStep(
                    name=f"delete_{resource}",
                    endpoint=path,
                    method="DELETE",
                    expected_status=[200, 204],
                    requires_auth=delete_ep.requires_auth,
                    description=f"Delete {resource}",
                )
            )

            # Step 5: Verify deleted (GET should return 404)
            if read_ep:
                path = self._substitute_path_param(read_ep.path, id_var)
                steps.append(
                    TestStep(
                        name=f"verify_{resource}_deleted",
                        endpoint=path,
                        method="GET",
                        expected_status=[404],
                        requires_auth=read_ep.requires_auth,
                        description=f"Verify {resource} was deleted",
                    )
                )

        if len(steps) < 2:
            return None

        return TestChain(
            name=f"{resource}_crud",
            description=f"CRUD operations for {resource}",
            resource=resource,
            steps=steps,
            tags=["crud", resource],
        )

    def _build_health_chain(self) -> Optional[TestChain]:
        """Build a chain for health check endpoints."""
        health_endpoints = []

        for ep in self.api.endpoints:
            if ep.method == HttpMethod.GET and (
                "health" in ep.path.lower() or ep.path in ["/health", "/api/health"]
            ):
                health_endpoints.append(ep)

        if not health_endpoints:
            return None

        steps = []
        for ep in health_endpoints:
            steps.append(
                TestStep(
                    name=f"health_{ep.path.replace('/', '_').strip('_')}",
                    endpoint=ep.path,
                    method="GET",
                    expected_status=[200],
                    requires_auth=False,
                    description=f"Health check: {ep.path}",
                )
            )

        return TestChain(
            name="health_checks",
            description="Health check endpoints",
            resource="health",
            steps=steps,
            tags=["health"],
        )

    def _build_read_chain(self, resource: str) -> Optional[TestChain]:
        """Build a read-only chain for a resource (list endpoint)."""
        endpoints = self.api.get_endpoints_by_resource(resource)
        list_ep = self._find_endpoint(endpoints, HttpMethod.GET, has_id=False)

        if not list_ep:
            return None

        steps = [
            TestStep(
                name=f"list_{resource}",
                endpoint=list_ep.path,
                method="GET",
                expected_status=[200],
                requires_auth=list_ep.requires_auth,
                description=f"List all {resource}",
            )
        ]

        return TestChain(
            name=f"{resource}_read",
            description=f"Read operations for {resource}",
            resource=resource,
            steps=steps,
            tags=["read", resource],
        )

    def _find_endpoint(
        self,
        endpoints: List[OpenAPIEndpoint],
        method: HttpMethod,
        has_id: bool,
    ) -> Optional[OpenAPIEndpoint]:
        """Find an endpoint matching method and path pattern."""
        for ep in endpoints:
            if ep.method != method:
                continue

            # Check if path has ID parameter
            path_has_id = bool(re.search(r"\{[^}]+\}", ep.path))

            if path_has_id == has_id:
                return ep

        return None

    def _substitute_path_param(self, path: str, var_name: str) -> str:
        """
        Substitute path parameter with variable reference.

        "/users/{user_id}" with var_name="user_id" -> "/users/{user_id}"
        "/users/{id}" with var_name="user_id" -> "/users/{user_id}"
        """
        # Replace any {param} with {var_name}
        return re.sub(r"\{[^}]+\}", f"{{{var_name}}}", path)


def print_chains(chains: List[TestChain]) -> None:
    """Pretty print test chains."""
    print(f"\nDiscovered {len(chains)} test chains:\n")

    for chain in chains:
        print(f"  {chain.name}")
        print(f"    Description: {chain.description}")
        print(f"    Steps: {chain.step_count}")
        for i, step in enumerate(chain.steps, 1):
            auth = " [AUTH]" if step.requires_auth else ""
            print(f"      [{i}] {step.method} {step.endpoint}{auth}")
        print()
