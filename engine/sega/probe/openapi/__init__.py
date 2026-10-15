"""
OpenAPI Discovery Module
========================
Fetch and parse OpenAPI schemas from running backend services.
"""

from .discoverer import DiscoveryConfig, DiscoveryResult, OpenAPIDiscoverer, print_discovery_results
from .models import (
    DiscoveredAPI,
    HttpMethod,
    OpenAPIEndpoint,
    OpenAPIParameter,
    OpenAPIRequestBody,
    OpenAPIResponse,
    OpenAPISchema,
)
from .schema_parser import OpenAPISchemaParser

__all__ = [
    # Discoverer
    "OpenAPIDiscoverer",
    "DiscoveryConfig",
    "DiscoveryResult",
    "print_discovery_results",
    # Parser
    "OpenAPISchemaParser",
    # Models
    "DiscoveredAPI",
    "OpenAPIEndpoint",
    "OpenAPIParameter",
    "OpenAPIRequestBody",
    "OpenAPIResponse",
    "OpenAPISchema",
    "HttpMethod",
]
