from __future__ import annotations

from typing import Any

from mcp_toolbox.utils import sanitize_identifier, to_snake_case

from .models import ParamDef, ParamLocation
from .type_mapper import map_schema_to_typeref


def openapi_type_to_python(schema: dict[str, Any] | None, enum_style: str = "literal") -> str:
    """Convert an OpenAPI schema object into a Python type annotation string."""

    return map_schema_to_typeref(schema, enum_style=enum_style).annotation


def schema_to_params(
    schema: dict[str, Any],
    required_fields: list[str],
    enum_style: str = "literal",
) -> list[ParamDef]:
    """Convert object schema properties into ParamDef instances."""

    properties = schema.get("properties", {}) if isinstance(schema.get("properties", {}), dict) else {}
    params: list[ParamDef] = []

    for prop_name, prop_schema in properties.items():
        schema_obj = prop_schema if isinstance(prop_schema, dict) else {}
        enum_raw = schema_obj.get("enum")
        enum_values = [str(value) for value in enum_raw] if isinstance(enum_raw, list) else None

        params.append(
            ParamDef(
                name=prop_name,
                python_name=sanitize_identifier(to_snake_case(prop_name)),
                python_type=openapi_type_to_python(schema_obj, enum_style=enum_style),
                location=ParamLocation.BODY,
                required=prop_name in required_fields,
                description=str(schema_obj.get("description", "")),
                default=schema_obj.get("default"),
                enum_values=enum_values,
                constraints=_extract_constraints(schema_obj),
            )
        )

    return params


def _extract_constraints(schema: dict[str, Any]) -> dict[str, Any]:
    """Extract Field-compatible constraint metadata from schema."""

    constraint_keys = {
        "minimum",
        "maximum",
        "exclusiveMinimum",
        "exclusiveMaximum",
        "multipleOf",
        "minLength",
        "maxLength",
        "pattern",
        "minItems",
        "maxItems",
        "uniqueItems",
    }

    constraints: dict[str, Any] = {}
    for key in constraint_keys:
        if key in schema:
            constraints[key] = schema[key]

    return constraints
