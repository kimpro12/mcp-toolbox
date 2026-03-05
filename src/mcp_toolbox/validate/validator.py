from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from urllib.error import URLError
from urllib.parse import urlparse
from urllib.request import urlopen

import yaml
from openapi_spec_validator import validate as openapi_validate

SpecSource = str | Path


@dataclass
class ValidationResult:
    """Result object returned by OpenAPI specification validation."""

    is_valid: bool
    errors: list[str]
    warnings: list[str]
    spec_version: str


def validate_spec(spec_path: SpecSource) -> ValidationResult:
    """Validate an OpenAPI or Swagger specification.

    Args:
        spec_path: Local filesystem path or an HTTP/HTTPS URL.

    Returns:
        ValidationResult with validity status, errors, warnings, and detected
        specification version.
    """

    errors: list[str] = []
    warnings: list[str] = []

    try:
        spec_dict, source_hint = _load_spec(spec_path)
    except (FileNotFoundError, PermissionError) as exc:
        return ValidationResult(
            is_valid=False,
            errors=[str(exc)],
            warnings=[],
            spec_version="unknown",
        )
    except (URLError, ValueError, yaml.YAMLError, json.JSONDecodeError) as exc:
        return ValidationResult(
            is_valid=False,
            errors=[_humanize_error(exc)],
            warnings=[],
            spec_version="unknown",
        )

    spec_version = _detect_spec_version(spec_dict)
    if spec_version == "2.0":
        warnings.append("Swagger 2.0 detected. Support is partial in MVP; conversion quality may vary.")

    try:
        openapi_validate(spec_dict)
    except Exception as exc:  # openapi-spec-validator exposes multiple exception types.
        errors.append(_humanize_error(exc))

    if not spec_dict:
        errors.append("Specification file is empty.")

    if spec_version == "unknown":
        warnings.append(
            f"Could not detect spec version from source '{source_hint}'. Expected 'openapi' or 'swagger' field."
        )

    return ValidationResult(
        is_valid=not errors,
        errors=errors,
        warnings=warnings,
        spec_version=spec_version,
    )


def _load_spec(spec_path: SpecSource) -> tuple[dict[str, Any], str]:
    """Load and parse a specification from local path or URL."""

    source = str(spec_path)
    if _is_url(source):
        with urlopen(source) as response:  # nosec B310 - expected for user-provided spec URLs.
            payload = response.read().decode("utf-8")
        extension = Path(urlparse(source).path).suffix.lower()
        return _parse_payload(payload, extension), source

    path = Path(source).expanduser()
    if not path.exists():
        raise FileNotFoundError(f"Spec file not found: {path}")
    if not path.is_file():
        raise FileNotFoundError(f"Spec path is not a file: {path}")
    if not path.stat().st_size:
        return {}, source

    try:
        payload = path.read_text(encoding="utf-8")
    except PermissionError as exc:
        raise PermissionError(f"Spec file is not readable: {path}") from exc

    return _parse_payload(payload, path.suffix.lower()), source


def _parse_payload(payload: str, extension: str) -> dict[str, Any]:
    """Parse text payload as YAML or JSON based on hint and content."""

    parsers: list[Any]
    if extension == ".json":
        parsers = [json.loads, yaml.safe_load]
    elif extension in {".yaml", ".yml"}:
        parsers = [yaml.safe_load, json.loads]
    else:
        parsers = [yaml.safe_load, json.loads]

    last_error: Exception | None = None
    parsed: Any = None
    for parser in parsers:
        try:
            parsed = parser(payload)
            break
        except Exception as exc:  # noqa: BLE001 - parser fallback intentionally broad.
            last_error = exc

    if parsed is None:
        if last_error:
            raise last_error
        raise ValueError("Unable to parse spec payload.")

    if not isinstance(parsed, dict):
        raise ValueError("Spec root must be a JSON/YAML object.")

    return parsed


def _detect_spec_version(spec: dict[str, Any]) -> str:
    """Detect OpenAPI/Swagger version from top-level fields."""

    openapi_version = spec.get("openapi")
    if isinstance(openapi_version, str):
        if openapi_version.startswith("3.1"):
            return "3.1"
        if openapi_version.startswith("3.0"):
            return "3.0"
        return openapi_version

    swagger_version = spec.get("swagger")
    if isinstance(swagger_version, str):
        if swagger_version.startswith("2.0"):
            return "2.0"
        return swagger_version

    return "unknown"


def _humanize_error(exc: Exception) -> str:
    """Transform parser/validator errors into concise messages."""

    message = str(exc).strip() or exc.__class__.__name__

    replacements = {
        "is not valid under any of the given schemas": "does not match expected OpenAPI schema",
        "Failed validating": "Validation failed:",
        "'": "",
    }
    for old, new in replacements.items():
        message = message.replace(old, new)

    return message


def _is_url(source: str) -> bool:
    """Return True if the provided source string is an HTTP(S) URL."""

    parsed = urlparse(source)
    return parsed.scheme in {"http", "https"} and bool(parsed.netloc)
