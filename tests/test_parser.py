from __future__ import annotations

from pathlib import Path

from mcp_toolbox.parse import parse_spec


def test_parse_spec_extracts_core_sections(petstore_spec_path: Path) -> None:
    """Parser extracts top-level metadata and key sections."""

    parsed = parse_spec(petstore_spec_path)

    assert parsed.title == "Petstore API"
    assert parsed.version == "1.0.0"
    assert parsed.base_url == "https://api.petstore.example.com/v1"
    assert "/pets" in parsed.paths
    assert "ApiKeyAuth" in parsed.security_schemes
    assert "Pet" in parsed.schemas


def test_parse_spec_resolves_refs(petstore_spec_path: Path) -> None:
    """Parser resolves $ref references into concrete schema objects."""

    parsed = parse_spec(petstore_spec_path)
    list_pets_schema = parsed.paths["/pets"]["get"]["responses"]["200"]["content"]["application/json"]["schema"]

    item_schema = list_pets_schema["items"]
    assert "$ref" not in item_schema
    assert item_schema["type"] == "object"
    assert "properties" in item_schema


def test_parse_spec_handles_missing_optional_sections(tmp_path: Path) -> None:
    """Parser fills missing optional sections with safe defaults."""

    spec = tmp_path / "minimal.yaml"
    spec.write_text(
        """
openapi: 3.1.0
info:
  title: Minimal
  version: "1.0"
paths: {}
""".strip(),
        encoding="utf-8",
    )

    parsed = parse_spec(spec)
    assert parsed.base_url == ""
    assert parsed.schemas == {}
    assert parsed.security_schemes == {}
    assert parsed.global_security == []
