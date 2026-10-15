"""
Sample Data Generator
=====================
Generate sample request bodies from OpenAPI schemas.
"""

import random
import string
import uuid
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

from ..openapi.models import DiscoveredAPI, OpenAPIEndpoint, OpenAPISchema


class SampleDataGenerator:
    """Generates sample data from OpenAPI schemas for testing."""

    def __init__(self, api: Optional[DiscoveredAPI] = None):
        self.api = api
        self.schemas = api.schemas if api else {}

    def generate_for_endpoint(
        self,
        endpoint: OpenAPIEndpoint,
    ) -> Optional[Dict[str, Any]]:
        """
        Generate sample request body for an endpoint.

        Uses schema examples if available, otherwise generates from types.
        """
        if not endpoint.request_body:
            return None

        # Try to use provided example first
        if endpoint.request_body.example:
            return endpoint.request_body.example

        # Resolve schema reference
        schema_ref = endpoint.request_body.schema_ref
        if schema_ref:
            schema_name = self._extract_schema_name(schema_ref)
            if schema_name in self.schemas:
                return self.generate_from_schema(self.schemas[schema_name])

        # Use inline schema
        if endpoint.request_body.schema_inline:
            return self._generate_from_raw_schema(endpoint.request_body.schema_inline)

        return {}

    def generate_from_schema(self, schema: OpenAPISchema) -> Dict[str, Any]:
        """Generate sample data from a parsed OpenAPISchema."""
        if schema.example:
            return schema.example

        return self._generate_from_properties(
            schema.properties,
            schema.required_fields,
        )

    def _generate_from_raw_schema(
        self,
        schema: Dict[str, Any],
    ) -> Any:
        """Generate sample data from raw schema dict."""
        schema_type = schema.get("type", "object")

        # Use example if provided
        if "example" in schema:
            return schema["example"]

        if schema_type == "object":
            return self._generate_from_properties(
                schema.get("properties", {}),
                schema.get("required", []),
            )
        elif schema_type == "array":
            items = schema.get("items", {})
            return [self._generate_from_raw_schema(items)]
        else:
            return self._generate_value(schema)

    def _generate_from_properties(
        self,
        properties: Dict[str, Any],
        required: List[str],
    ) -> Dict[str, Any]:
        """Generate object from properties definition."""
        result = {}

        for prop_name, prop_schema in properties.items():
            # Always include required fields, optionally include others
            if prop_name in required or random.random() > 0.3:
                result[prop_name] = self._generate_value(prop_schema, prop_name)

        return result

    def _generate_value(
        self,
        schema: Dict[str, Any],
        field_name: str = "",
    ) -> Any:
        """Generate a value based on schema type."""
        # Use example if provided
        if "example" in schema:
            return schema["example"]

        # Use default if provided
        if "default" in schema:
            return schema["default"]

        # Handle enum
        if "enum" in schema:
            return random.choice(schema["enum"])

        schema_type = schema.get("type", "string")
        format_type = schema.get("format", "")

        # Handle $ref
        if "$ref" in schema:
            ref_name = self._extract_schema_name(schema["$ref"])
            if ref_name in self.schemas:
                return self.generate_from_schema(self.schemas[ref_name])

        # Generate based on type
        if schema_type == "string":
            return self._generate_string(field_name, format_type, schema)
        elif schema_type == "integer":
            return self._generate_integer(schema)
        elif schema_type == "number":
            return self._generate_number(schema)
        elif schema_type == "boolean":
            return random.choice([True, False])
        elif schema_type == "array":
            items = schema.get("items", {"type": "string"})
            return [self._generate_value(items)]
        elif schema_type == "object":
            return self._generate_from_properties(
                schema.get("properties", {}),
                schema.get("required", []),
            )

        return None

    def _generate_string(
        self,
        field_name: str,
        format_type: str,
        schema: Dict[str, Any],
    ) -> str:
        """Generate a string value."""
        # Handle format types
        if format_type == "uuid":
            return str(uuid.uuid4())
        elif format_type == "date":
            return datetime.now().strftime("%Y-%m-%d")
        elif format_type == "date-time":
            return datetime.now().isoformat()
        elif format_type == "email":
            return f"test_{self._random_string(6)}@example.com"
        elif format_type == "uri" or format_type == "url":
            return f"https://example.com/{self._random_string(8)}"

        # Infer from field name
        field_lower = field_name.lower()
        if "email" in field_lower:
            return f"test_{self._random_string(6)}@example.com"
        elif "name" in field_lower:
            return f"Test {field_name.replace('_', ' ').title()}"
        elif "url" in field_lower or "uri" in field_lower:
            return f"https://example.com/{self._random_string(8)}"
        elif "description" in field_lower:
            return f"Test description for {field_name}"
        elif "title" in field_lower:
            return f"Test Title {self._random_string(4)}"
        elif "id" in field_lower and "uuid" not in field_lower:
            return str(uuid.uuid4())[:8]

        # Apply length constraints
        min_length = schema.get("minLength", 1)
        max_length = schema.get("maxLength", 50)
        length = random.randint(min_length, min(max_length, 50))

        return f"test_{self._random_string(length - 5)}"

    def _generate_integer(self, schema: Dict[str, Any]) -> int:
        """Generate an integer value."""
        minimum = schema.get("minimum", 1)
        maximum = schema.get("maximum", 1000)
        return random.randint(minimum, maximum)

    def _generate_number(self, schema: Dict[str, Any]) -> float:
        """Generate a float value."""
        minimum = schema.get("minimum", 0.0)
        maximum = schema.get("maximum", 1000.0)
        return round(random.uniform(minimum, maximum), 2)

    def _random_string(self, length: int) -> str:
        """Generate random alphanumeric string."""
        return "".join(random.choices(string.ascii_lowercase + string.digits, k=length))

    def _extract_schema_name(self, ref: str) -> str:
        """Extract schema name from $ref string."""
        # "#/components/schemas/User" -> "User"
        if ref.startswith("#/components/schemas/"):
            return ref.split("/")[-1]
        return ref
