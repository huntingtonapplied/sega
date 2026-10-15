"""
OpenAPI Schema Models
=====================
Data classes for representing parsed OpenAPI 3.x schemas.
"""

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional


class HttpMethod(Enum):
    """HTTP methods supported by OpenAPI."""
    GET = "get"
    POST = "post"
    PUT = "put"
    PATCH = "patch"
    DELETE = "delete"
    HEAD = "head"
    OPTIONS = "options"


@dataclass
class OpenAPIParameter:
    """Represents a path/query/header parameter."""
    name: str
    location: str  # "path", "query", "header", "cookie"
    required: bool
    schema_type: str
    description: Optional[str] = None
    example: Optional[Any] = None
    default: Optional[Any] = None
    enum: Optional[List[Any]] = None


@dataclass
class OpenAPIRequestBody:
    """Represents a request body schema."""
    content_type: str = "application/json"
    schema_ref: Optional[str] = None
    schema_inline: Optional[Dict[str, Any]] = None
    required: bool = True
    example: Optional[Any] = None


@dataclass
class OpenAPIResponse:
    """Represents a response definition."""
    status_code: int
    description: str
    schema_ref: Optional[str] = None
    schema_inline: Optional[Dict[str, Any]] = None


@dataclass
class OpenAPIEndpoint:
    """Represents a single API endpoint."""
    path: str
    method: HttpMethod
    operation_id: Optional[str] = None
    summary: Optional[str] = None
    description: Optional[str] = None
    tags: List[str] = field(default_factory=list)
    parameters: List[OpenAPIParameter] = field(default_factory=list)
    request_body: Optional[OpenAPIRequestBody] = None
    responses: Dict[int, OpenAPIResponse] = field(default_factory=dict)
    security: List[Dict[str, List[str]]] = field(default_factory=list)
    deprecated: bool = False

    @property
    def path_parameters(self) -> List[OpenAPIParameter]:
        """Get only path parameters."""
        return [p for p in self.parameters if p.location == "path"]

    @property
    def query_parameters(self) -> List[OpenAPIParameter]:
        """Get only query parameters."""
        return [p for p in self.parameters if p.location == "query"]

    @property
    def requires_auth(self) -> bool:
        """Check if endpoint requires authentication."""
        return len(self.security) > 0

    @property
    def resource_name(self) -> Optional[str]:
        """Extract resource name from path (e.g., /api/users -> users)."""
        parts = [p for p in self.path.split("/") if p and not p.startswith("{")]
        if parts:
            # Skip 'api', 'v1', etc.
            for part in reversed(parts):
                if part not in ("api", "v1", "v2"):
                    return part
        return None


@dataclass
class OpenAPISchema:
    """Represents a schema from components/schemas."""
    name: str
    schema_type: str  # "object", "array", "string", etc.
    properties: Dict[str, Any] = field(default_factory=dict)
    required_fields: List[str] = field(default_factory=list)
    example: Optional[Any] = None
    description: Optional[str] = None


@dataclass
class DiscoveredAPI:
    """Complete discovered API from OpenAPI schema."""
    project: str
    base_url: str
    openapi_version: str
    title: str
    version: str
    description: Optional[str] = None
    endpoints: List[OpenAPIEndpoint] = field(default_factory=list)
    schemas: Dict[str, OpenAPISchema] = field(default_factory=dict)
    security_schemes: Dict[str, Any] = field(default_factory=dict)

    @property
    def endpoint_count(self) -> int:
        """Total number of endpoints."""
        return len(self.endpoints)

    @property
    def resources(self) -> List[str]:
        """Unique resource names found in API."""
        names = set()
        for ep in self.endpoints:
            if ep.resource_name:
                names.add(ep.resource_name)
        return sorted(names)

    def get_endpoints_by_resource(self, resource: str) -> List[OpenAPIEndpoint]:
        """Get all endpoints for a specific resource."""
        return [ep for ep in self.endpoints if ep.resource_name == resource]

    def get_endpoints_by_method(self, method: HttpMethod) -> List[OpenAPIEndpoint]:
        """Get all endpoints with a specific HTTP method."""
        return [ep for ep in self.endpoints if ep.method == method]

    def get_endpoints_by_tag(self, tag: str) -> List[OpenAPIEndpoint]:
        """Get all endpoints with a specific tag."""
        return [ep for ep in self.endpoints if tag in ep.tags]
