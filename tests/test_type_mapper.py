from __future__ import annotations

from mcp_toolbox.analyze.type_mapper import TypeRef, map_schema_to_typeref


def test_map_schema_to_typeref_returns_typeref() -> None:
    """Mapper should return TypeRef with annotation metadata."""

    result = map_schema_to_typeref({"type": "string"})

    assert isinstance(result, TypeRef)
    assert result.annotation == "str"
    assert result.imports == set()


def test_map_schema_to_typeref_union_for_oneof() -> None:
    """oneOf should map to union annotation."""

    result = map_schema_to_typeref({"oneOf": [{"type": "integer"}, {"type": "string"}]})

    assert result.annotation == "int | str"


def test_map_schema_to_typeref_nullable_type_list() -> None:
    """OpenAPI 3.1 nullable types should map to optional unions."""

    result = map_schema_to_typeref({"type": ["string", "null"]})

    assert result.annotation == "str | None"


def test_map_schema_to_typeref_additional_properties_schema() -> None:
    """Object additionalProperties schema should map to typed dict values."""

    result = map_schema_to_typeref(
        {
            "type": "object",
            "additionalProperties": {
                "type": "integer",
            },
        }
    )

    assert result.annotation == "dict[str, int]"


def test_map_schema_to_typeref_datetime_import() -> None:
    """date-time format should register datetime import metadata."""

    result = map_schema_to_typeref({"type": "string", "format": "date-time"})

    assert result.annotation == "datetime"
    assert "datetime:datetime" in result.imports


def test_map_schema_to_typeref_strenum_mode_uses_str() -> None:
    """strenum mode should map string enums to plain str annotation."""

    result = map_schema_to_typeref({"type": "string", "enum": ["a", "b"]}, enum_style="strenum")

    assert result.annotation == "str"
