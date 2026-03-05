from __future__ import annotations

import pytest

from mcp_toolbox.analyze.schema_mapper import openapi_type_to_python


@pytest.mark.parametrize(
    ("schema", "expected"),
    [
        ({"type": "string"}, "str"),
        ({"type": "string", "format": "date-time"}, "datetime"),
        ({"type": "string", "format": "date"}, "date"),
        ({"type": "string", "format": "time"}, "time"),
        ({"type": "string", "format": "uuid"}, "UUID"),
        ({"type": "string", "format": "email"}, "EmailStr"),
        ({"type": "string", "format": "uri"}, "AnyUrl"),
        ({"type": "string", "format": "ipv4"}, "IPv4Address"),
        ({"type": "string", "format": "ipv6"}, "IPv6Address"),
        ({"type": "string", "enum": ["a", "b"]}, "Literal['a', 'b']"),
        ({"type": "integer"}, "int"),
        ({"type": "number"}, "float"),
        ({"type": "boolean"}, "bool"),
        ({"type": "array", "items": {"type": "integer"}}, "list[int]"),
        ({"type": "object", "properties": {"id": {"type": "string"}}}, "dict[str, Any]"),
        ({"type": ["string", "null"]}, "str | None"),
        ({"nullable": True, "type": "integer"}, "int | None"),
        ({"oneOf": [{"type": "integer"}, {"type": "string"}]}, "int | str"),
        ({"anyOf": [{"type": "integer"}, {"type": "string"}]}, "int | str"),
        ({"allOf": [{"$ref": "#/components/schemas/Base"}]}, "dict[str, Any]"),
        ({}, "Any"),
    ],
)
def test_openapi_type_to_python(schema: dict, expected: str) -> None:
    """openapi_type_to_python follows MCP Toolbox TechSpec type mappings."""

    assert openapi_type_to_python(schema) == expected
