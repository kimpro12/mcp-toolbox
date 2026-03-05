from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from .schema_ir import SchemaIR, normalize_schema


@dataclass
class TypeRef:
    """Type annotation mapping result for schema-driven code generation."""

    annotation: str
    imports: set[str] = field(default_factory=set)
    is_model: bool = False


def map_schema_to_typeref(schema: dict[str, Any] | None, enum_style: str = "literal") -> TypeRef:
    """Map an OpenAPI schema to a Python type annotation and required imports."""

    ir = normalize_schema(schema)
    typeref = _map_ir_to_typeref(ir, enum_style=enum_style)

    if ir.nullable and typeref.annotation != "None" and "| None" not in typeref.annotation:
        typeref.annotation = f"{typeref.annotation} | None"

    return typeref


def _map_ir_to_typeref(schema_ir: SchemaIR, enum_style: str = "literal") -> TypeRef:
    """Recursively map normalized schema IR to a TypeRef."""

    if schema_ir.one_of:
        return _map_union(schema_ir.one_of, enum_style=enum_style)

    if schema_ir.any_of:
        return _map_union(schema_ir.any_of, enum_style=enum_style)

    if schema_ir.all_of:
        # allOf is handled in model builder; mapper keeps safe fallback for tool params.
        return TypeRef(annotation="dict[str, Any]", imports={"typing:Any"}, is_model=False)

    schema_type = schema_ir.schema_type

    if isinstance(schema_type, list):
        non_null = [item for item in schema_type if item != "null"]
        if not non_null:
            return TypeRef(annotation="None")

        narrowed = SchemaIR(
            raw=schema_ir.raw,
            schema_type=non_null[0],
            schema_format=schema_ir.schema_format,
            enum_values=schema_ir.enum_values,
            nullable="null" in schema_type,
            properties=schema_ir.properties,
            required=schema_ir.required,
            items=schema_ir.items,
            one_of=schema_ir.one_of,
            any_of=schema_ir.any_of,
            all_of=schema_ir.all_of,
            additional_properties=schema_ir.additional_properties,
        )
        mapped = _map_ir_to_typeref(narrowed, enum_style=enum_style)
        if narrowed.nullable and mapped.annotation != "None" and "| None" not in mapped.annotation:
            mapped.annotation = f"{mapped.annotation} | None"
        return mapped

    if schema_type == "string":
        if schema_ir.enum_values:
            if enum_style == "strenum":
                return TypeRef(annotation="str")
            literal_values = ", ".join(repr(str(value)) for value in schema_ir.enum_values)
            return TypeRef(
                annotation=f"Literal[{literal_values}]",
                imports={"typing:Literal"},
            )

        fmt = (schema_ir.schema_format or "").lower()
        fmt_map: dict[str, tuple[str, set[str]]] = {
            "date-time": ("datetime", {"datetime:datetime"}),
            "date": ("date", {"datetime:date"}),
            "time": ("time", {"datetime:time"}),
            "uuid": ("UUID", {"uuid:UUID"}),
            "email": ("EmailStr", {"pydantic:EmailStr"}),
            "uri": ("AnyUrl", {"pydantic:AnyUrl"}),
            "ipv4": ("IPv4Address", {"ipaddress:IPv4Address"}),
            "ipv6": ("IPv6Address", {"ipaddress:IPv6Address"}),
            "byte": ("bytes", set()),
            "binary": ("bytes", set()),
            "password": ("SecretStr", {"pydantic:SecretStr"}),
        }
        if fmt in fmt_map:
            annotation, imports = fmt_map[fmt]
            return TypeRef(annotation=annotation, imports=imports)
        return TypeRef(annotation="str")

    if schema_type == "integer":
        return TypeRef(annotation="int")

    if schema_type == "number":
        return TypeRef(annotation="float")

    if schema_type == "boolean":
        return TypeRef(annotation="bool")

    if schema_type == "null":
        return TypeRef(annotation="None")

    if schema_type == "array":
        if schema_ir.items is None:
            return TypeRef(annotation="list[Any]", imports={"typing:Any"})
        inner = _map_ir_to_typeref(schema_ir.items, enum_style=enum_style)
        return TypeRef(annotation=f"list[{inner.annotation}]", imports=set(inner.imports), is_model=inner.is_model)

    if schema_type == "object":
        if schema_ir.properties:
            return TypeRef(annotation="dict[str, Any]", imports={"typing:Any"}, is_model=True)

        if isinstance(schema_ir.additional_properties, SchemaIR):
            value_typeref = _map_ir_to_typeref(schema_ir.additional_properties, enum_style=enum_style)
            return TypeRef(
                annotation=f"dict[str, {value_typeref.annotation}]",
                imports=set(value_typeref.imports),
                is_model=False,
            )

        return TypeRef(annotation="dict[str, Any]", imports={"typing:Any"}, is_model=False)

    if schema_ir.properties:
        return TypeRef(annotation="dict[str, Any]", imports={"typing:Any"}, is_model=True)

    return TypeRef(annotation="Any", imports={"typing:Any"})


def _map_union(variants: list[SchemaIR], enum_style: str = "literal") -> TypeRef:
    """Map oneOf/anyOf variants into union annotation."""

    annotations: list[str] = []
    imports: set[str] = set()
    has_model = False

    for variant in variants:
        mapped = _map_ir_to_typeref(variant, enum_style=enum_style)
        annotations.append(mapped.annotation)
        imports.update(mapped.imports)
        has_model = has_model or mapped.is_model

    unique_annotations: list[str] = []
    for annotation in annotations:
        if annotation not in unique_annotations:
            unique_annotations.append(annotation)

    if not unique_annotations:
        return TypeRef(annotation="Any", imports={"typing:Any"})

    if len(unique_annotations) == 1:
        return TypeRef(annotation=unique_annotations[0], imports=imports, is_model=has_model)

    return TypeRef(annotation=" | ".join(unique_annotations), imports=imports, is_model=has_model)
