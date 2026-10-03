"""
Value Extractors
================
Extract values from API responses using JSONPath expressions.
"""

import re
from dataclasses import dataclass
from typing import Any, Callable, Dict, List, Optional


@dataclass
class ValueExtractor:
    """Extracts a value from API response using JSONPath-like syntax."""

    source_path: str  # e.g., "$.data.id", "$.items[0].uuid"
    target_variable: str  # e.g., "user_id"
    transform: Optional[Callable[[Any], Any]] = None
    required: bool = True

    def extract(self, data: Any) -> Optional[Any]:
        """
        Extract value from data using the source_path.

        Supports simplified JSONPath:
        - $.field - root level field
        - $.field.nested - nested field
        - $.items[0] - array index
        - $.items[0].id - array index then field
        """
        if data is None:
            return None

        value = self._extract_path(data, self.source_path)

        if value is not None and self.transform:
            value = self.transform(value)

        return value

    def _extract_path(self, data: Any, path: str) -> Optional[Any]:
        """Extract value following the path."""
        # Remove leading $. if present
        if path.startswith("$."):
            path = path[2:]
        elif path.startswith("$"):
            path = path[1:]

        if not path:
            return data

        current = data
        # Split by . but handle array indices
        parts = self._split_path(path)

        for part in parts:
            if current is None:
                return None

            # Check for array index: field[0]
            array_match = re.match(r"(\w+)\[(\d+)\]", part)
            if array_match:
                field_name = array_match.group(1)
                index = int(array_match.group(2))

                if field_name:
                    current = self._get_field(current, field_name)
                if current is None:
                    return None

                if isinstance(current, list) and len(current) > index:
                    current = current[index]
                else:
                    return None
            elif part.isdigit():
                # Pure index: [0]
                index = int(part)
                if isinstance(current, list) and len(current) > index:
                    current = current[index]
                else:
                    return None
            else:
                # Regular field access
                current = self._get_field(current, part)

        return current

    def _split_path(self, path: str) -> List[str]:
        """Split path by dots, preserving array indices."""
        parts = []
        current = ""
        in_bracket = False

        for char in path:
            if char == "[":
                in_bracket = True
                current += char
            elif char == "]":
                in_bracket = False
                current += char
            elif char == "." and not in_bracket:
                if current:
                    parts.append(current)
                current = ""
            else:
                current += char

        if current:
            parts.append(current)

        return parts

    def _get_field(self, obj: Any, field: str) -> Optional[Any]:
        """Get field from dict or object."""
        if isinstance(obj, dict):
            return obj.get(field)
        elif hasattr(obj, field):
            return getattr(obj, field)
        return None


class TestContext:
    """Shared context between chained tests."""

    def __init__(self):
        self.variables: Dict[str, Any] = {}
        self.responses: Dict[str, Any] = {}

    def set(self, name: str, value: Any) -> None:
        """Set a context variable."""
        self.variables[name] = value

    def get(self, name: str, default: Any = None) -> Any:
        """Get a context variable."""
        return self.variables.get(name, default)

    def store_response(self, step_name: str, response_data: Any) -> None:
        """Store response data from a test step."""
        self.responses[step_name] = response_data

    def substitute(self, template: str) -> str:
        """
        Substitute {variables} in template string.

        Example: "/users/{user_id}" with context {"user_id": "123"}
        Returns: "/users/123"
        """
        result = template
        for key, value in self.variables.items():
            placeholder = f"{{{key}}}"
            if placeholder in result:
                result = result.replace(placeholder, str(value))
        return result

    def substitute_dict(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Recursively substitute variables in a dictionary."""
        result = {}
        for key, value in data.items():
            if isinstance(value, str):
                result[key] = self.substitute(value)
            elif isinstance(value, dict):
                result[key] = self.substitute_dict(value)
            elif isinstance(value, list):
                result[key] = [
                    self.substitute(v) if isinstance(v, str) else v for v in value
                ]
            else:
                result[key] = value
        return result

    def extract_and_store(
        self,
        response_data: Any,
        extractors: List[ValueExtractor],
    ) -> Dict[str, Any]:
        """
        Extract values from response and store in context.

        Returns dict of extracted values.
        """
        extracted = {}
        for extractor in extractors:
            value = extractor.extract(response_data)
            if value is not None:
                self.variables[extractor.target_variable] = value
                extracted[extractor.target_variable] = value
            elif extractor.required:
                raise ValueError(
                    f"Required value not found: {extractor.source_path} -> {extractor.target_variable}"
                )
        return extracted


# Common extractors for typical API patterns
COMMON_EXTRACTORS = {
    "id": ValueExtractor(source_path="$.id", target_variable="id"),
    "uuid": ValueExtractor(source_path="$.uuid", target_variable="uuid"),
    "data_id": ValueExtractor(source_path="$.data.id", target_variable="id"),
    "first_item_id": ValueExtractor(
        source_path="$.items[0].id", target_variable="id", required=False
    ),
    "first_data_id": ValueExtractor(
        source_path="$.data[0].id", target_variable="id", required=False
    ),
}


def create_id_extractor(
    resource_name: str,
    source_path: str = "$.id",
) -> ValueExtractor:
    """Create an ID extractor for a resource."""
    return ValueExtractor(
        source_path=source_path,
        target_variable=f"{resource_name}_id",
    )
