from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class SchemaIR:
    """Normalized schema object used by type mapping and model analysis."""

    raw: dict[str, Any] = field(default_factory=dict)
    schema_type: str | list[str] | None = None
    schema_format: str | None = None
    enum_values: list[Any] = field(default_factory=list)
    nullable: bool = False
    properties: dict[str, SchemaIR] = field(default_factory=dict)
    required: list[str] = field(default_factory=list)
    items: SchemaIR | None = None
    one_of: list[SchemaIR] = field(default_factory=list)
    any_of: list[SchemaIR] = field(default_factory=list)
    all_of: list[SchemaIR] = field(default_factory=list)
    additional_properties: SchemaIR | bool | None = None


def normalize_schema(schema: dict[str, Any] | None) -> SchemaIR:
    """Normalize a raw OpenAPI schema dictionary into a SchemaIR object."""

    if not isinstance(schema, dict):
        return SchemaIR()

    schema_type_raw = schema.get("type")
    schema_format = schema.get("format")

    nullable = bool(schema.get("nullable", False))
    if isinstance(schema_type_raw, list) and "null" in schema_type_raw:
        nullable = True

    properties: dict[str, SchemaIR] = {}
    raw_properties = schema.get("properties")
    if isinstance(raw_properties, dict):
        for key, value in raw_properties.items():
            if isinstance(value, dict):
                properties[str(key)] = normalize_schema(value)

    required_raw = schema.get("required")
    required = [str(item) for item in required_raw] if isinstance(required_raw, list) else []

    items_schema = schema.get("items") if isinstance(schema.get("items"), dict) else None

    additional_properties_raw = schema.get("additionalProperties")
    if isinstance(additional_properties_raw, dict):
        additional_properties: SchemaIR | bool | None = normalize_schema(additional_properties_raw)
    elif isinstance(additional_properties_raw, bool):
        additional_properties = additional_properties_raw
    else:
        additional_properties = None

    return SchemaIR(
        raw=schema,
        schema_type=schema_type_raw if isinstance(schema_type_raw, (str, list)) else None,
        schema_format=str(schema_format) if isinstance(schema_format, str) else None,
        enum_values=list(schema.get("enum", [])) if isinstance(schema.get("enum"), list) else [],
        nullable=nullable,
        properties=properties,
        required=required,
        items=normalize_schema(items_schema) if isinstance(items_schema, dict) else None,
        one_of=_normalize_composed_schemas(schema.get("oneOf")),
        any_of=_normalize_composed_schemas(schema.get("anyOf")),
        all_of=_normalize_composed_schemas(schema.get("allOf")),
        additional_properties=additional_properties,
    )


def _normalize_composed_schemas(values: Any) -> list[SchemaIR]:
    """Normalize composition arrays (oneOf/anyOf/allOf)."""

    if not isinstance(values, list):
        return []

    normalized: list[SchemaIR] = []
    for item in values:
        if isinstance(item, dict):
            normalized.append(normalize_schema(item))
    return normalized
