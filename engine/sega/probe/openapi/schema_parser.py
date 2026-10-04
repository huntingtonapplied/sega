"""
OpenAPI Schema Parser
=====================
Parses OpenAPI 3.x JSON into structured models.
"""

from typing import Any, Dict, List, Optional

from .models import (
    DiscoveredAPI,
    HttpMethod,
    OpenAPIEndpoint,
    OpenAPIParameter,
    OpenAPIRequestBody,
    OpenAPIResponse,
    OpenAPISchema,
)


class OpenAPISchemaParser:
    """Parses OpenAPI 3.x schemas into structured models."""

    SUPPORTED_METHODS = ["get", "post", "put", "patch", "delete", "head", "options"]

    def parse(
        self,
        schema: Dict[str, Any],
        project: str,
        base_url: str,
    ) -> DiscoveredAPI:
        """
        Parse OpenAPI schema into DiscoveredAPI model.

        Args:
            schema: Raw OpenAPI JSON schema
            project: Project name (e.g., "atlas")
            base_url: Base URL of the API (e.g., "http://localhost:8009")

        Returns:
            DiscoveredAPI with parsed endpoints and schemas
        """
        info = schema.get("info", {})

        api = DiscoveredAPI(
            project=project,
            base_url=base_url,
            openapi_version=schema.get("openapi", "3.0.0"),
            title=info.get("title", project),
            version=info.get("version", "1.0.0"),
            description=info.get("description"),
        )

        # Parse component schemas
        api.schemas = self._parse_schemas(schema)

        # Parse security schemes
        api.security_schemes = self._parse_security_schemes(schema)

        # Parse endpoints
        api.endpoints = self._parse_endpoints(schema)

        return api

    def _parse_schemas(self, schema: Dict[str, Any]) -> Dict[str, OpenAPISchema]:
        """Parse components/schemas section."""
        schemas = {}
        components = schema.get("components", {})
        raw_schemas = components.get("schemas", {})

        for name, schema_def in raw_schemas.items():
            schemas[name] = OpenAPISchema(
                name=name,
                schema_type=schema_def.get("type", "object"),
                properties=schema_def.get("properties", {}),
                required_fields=schema_def.get("required", []),
                example=schema_def.get("example"),
                description=schema_def.get("description"),
            )

        return schemas

    def _parse_security_schemes(self, schema: Dict[str, Any]) -> Dict[str, Any]:
        """Parse components/securitySchemes section."""
        components = schema.get("components", {})
        return components.get("securitySchemes", {})

    def _parse_endpoints(self, schema: Dict[str, Any]) -> List[OpenAPIEndpoint]:
        """Parse paths section into endpoints."""
        endpoints = []
        paths = schema.get("paths", {})
        global_security = schema.get("security", [])

        for path, path_item in paths.items():
            # Handle path-level parameters
            path_params = self._parse_parameters(path_item.get("parameters", []))

            for method in self.SUPPORTED_METHODS:
                if method not in path_item:
                    continue

                operation = path_item[method]
                endpoint = self._parse_endpoint(
                    path=path,
                    method=method,
                    operation=operation,
                    path_params=path_params,
                    global_security=global_security,
                )
                endpoints.append(endpoint)

        return endpoints

    def _parse_endpoint(
        self,
        path: str,
        method: str,
        operation: Dict[str, Any],
        path_params: List[OpenAPIParameter],
        global_security: List[Dict[str, List[str]]],
    ) -> OpenAPIEndpoint:
        """Parse a single endpoint operation."""
        # Combine path-level and operation-level parameters
        op_params = self._parse_parameters(operation.get("parameters", []))
        all_params = path_params + op_params

        # Parse request body if present
        request_body = None
        if "requestBody" in operation:
            request_body = self._parse_request_body(operation["requestBody"])

        # Parse responses
        responses = self._parse_responses(operation.get("responses", {}))

        # Security: operation-level overrides global
        security = operation.get("security", global_security)

        return OpenAPIEndpoint(
            path=path,
            method=HttpMethod(method),
            operation_id=operation.get("operationId"),
            summary=operation.get("summary"),
            description=operation.get("description"),
            tags=operation.get("tags", []),
            parameters=all_params,
            request_body=request_body,
            responses=responses,
            security=security,
            deprecated=operation.get("deprecated", False),
        )

    def _parse_parameters(
        self, params: List[Dict[str, Any]]
    ) -> List[OpenAPIParameter]:
        """Parse parameter definitions."""
        parsed = []
        for param in params:
            schema = param.get("schema", {})
            parsed.append(
                OpenAPIParameter(
                    name=param.get("name", ""),
                    location=param.get("in", "query"),
                    required=param.get("required", False),
                    schema_type=schema.get("type", "string"),
                    description=param.get("description"),
                    example=param.get("example") or schema.get("example"),
                    default=schema.get("default"),
                    enum=schema.get("enum"),
                )
            )
        return parsed

    def _parse_request_body(
        self, request_body: Dict[str, Any]
    ) -> Optional[OpenAPIRequestBody]:
        """Parse request body definition."""
        content = request_body.get("content", {})

        # Prefer application/json
        if "application/json" in content:
            json_content = content["application/json"]
            schema = json_content.get("schema", {})

            return OpenAPIRequestBody(
                content_type="application/json",
                schema_ref=schema.get("$ref"),
                schema_inline=schema if "$ref" not in schema else None,
                required=request_body.get("required", True),
                example=json_content.get("example") or schema.get("example"),
            )

        # Fallback to first content type
        for content_type, content_def in content.items():
            schema = content_def.get("schema", {})
            return OpenAPIRequestBody(
                content_type=content_type,
                schema_ref=schema.get("$ref"),
                schema_inline=schema if "$ref" not in schema else None,
                required=request_body.get("required", True),
                example=content_def.get("example"),
            )

        return None

    def _parse_responses(
        self, responses: Dict[str, Any]
    ) -> Dict[int, OpenAPIResponse]:
        """Parse response definitions."""
        parsed = {}
        for status_code, response in responses.items():
            try:
                code = int(status_code)
            except ValueError:
                continue  # Skip 'default' or other non-numeric

            schema_ref = None
            schema_inline = None

            content = response.get("content", {})
            if "application/json" in content:
                schema = content["application/json"].get("schema", {})
                schema_ref = schema.get("$ref")
                schema_inline = schema if "$ref" not in schema else None

            parsed[code] = OpenAPIResponse(
                status_code=code,
                description=response.get("description", ""),
                schema_ref=schema_ref,
                schema_inline=schema_inline,
            )

        return parsed
