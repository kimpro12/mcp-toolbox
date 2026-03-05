from __future__ import annotations

from pathlib import Path

from mcp_toolbox.validate import validate_spec


def test_validate_spec_valid_fixture(petstore_spec_path: Path) -> None:
    """Validator accepts the Petstore fixture as valid OpenAPI 3.1."""

    result = validate_spec(petstore_spec_path)
    assert result.is_valid is True
    assert result.errors == []
    assert result.spec_version == "3.1"


def test_validate_spec_invalid_missing_required(tmp_path: Path) -> None:
    """Validator rejects malformed specs with clear errors."""

    invalid_spec = tmp_path / "invalid.yaml"
    invalid_spec.write_text(
        """
openapi: 3.1.0
paths: {}
""".strip(),
        encoding="utf-8",
    )

    result = validate_spec(invalid_spec)
    assert result.is_valid is False
    assert result.errors


def test_validate_spec_wrong_format(tmp_path: Path) -> None:
    """Validator handles invalid file format gracefully."""

    invalid = tmp_path / "invalid.json"
    invalid.write_text("not valid json", encoding="utf-8")

    result = validate_spec(invalid)
    assert result.is_valid is False
    assert result.errors


def test_validate_spec_swagger_2_detection(tmp_path: Path) -> None:
    """Validator flags Swagger 2.0 with warning."""

    swagger_spec = tmp_path / "swagger.yaml"
    swagger_spec.write_text(
        """
swagger: "2.0"
info:
  title: Legacy API
  version: "1.0"
paths: {}
""".strip(),
        encoding="utf-8",
    )

    result = validate_spec(swagger_spec)
    assert result.spec_version == "2.0"
    assert any("Swagger 2.0" in warning for warning in result.warnings)
