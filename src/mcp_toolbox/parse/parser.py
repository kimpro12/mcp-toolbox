from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

from openapi_pydantic import OpenAPI as OpenAPI31
from openapi_pydantic.v3.v3_0 import OpenAPI as OpenAPI30
from prance import ResolvingParser

SpecSource = str | Path


@dataclass
class ParsedSpec:
    """Resolved and normalized OpenAPI spec representation."""

    raw: dict[str, Any]
    title: str
    version: str
    description: str
    base_url: str
    paths: dict[str, Any]
    security_schemes: dict[str, Any]
    schemas: dict[str, Any]
    global_security: list[dict[str, Any]]


def parse_spec(spec_path: SpecSource) -> ParsedSpec:
    """Load an OpenAPI specification, resolve references, and validate its model.

    Args:
        spec_path: Local path or URL to YAML/JSON OpenAPI document.

    Returns:
        ParsedSpec containing a resolved document and frequently-used sections.
    """

    source = _normalize_source(spec_path)
    resolved = _resolve_with_prance(source)
    _validate_with_openapi_pydantic(resolved)

    info = resolved.get("info", {}) if isinstance(resolved.get("info", {}), dict) else {}
    servers = resolved.get("servers", []) if isinstance(resolved.get("servers", []), list) else []
    components = resolved.get("components", {}) if isinstance(resolved.get("components", {}), dict) else {}

    base_url = ""
    if servers and isinstance(servers[0], dict):
        base_url = str(servers[0].get("url", ""))

    return ParsedSpec(
        raw=resolved,
        title=str(info.get("title", "API")),
        version=str(info.get("version", "")),
        description=str(info.get("description", "")),
        base_url=base_url,
        paths=resolved.get("paths", {}) if isinstance(resolved.get("paths", {}), dict) else {},
        security_schemes=components.get("securitySchemes", {})
        if isinstance(components.get("securitySchemes", {}), dict)
        else {},
        schemas=components.get("schemas", {}) if isinstance(components.get("schemas", {}), dict) else {},
        global_security=resolved.get("security", []) if isinstance(resolved.get("security", []), list) else [],
    )


def _normalize_source(spec_path: SpecSource) -> str:
    """Normalize local path/URL into source string accepted by prance parser."""

    source = str(spec_path)
    parsed_url = urlparse(source)
    if parsed_url.scheme in {"http", "https"} and parsed_url.netloc:
        return source

    path = Path(source).expanduser().resolve()
    return str(path)


def _resolve_with_prance(source: str) -> dict[str, Any]:
    """Resolve an OpenAPI spec with prance including external $ref references."""

    parser = ResolvingParser(
        source,
        backend="openapi-spec-validator",
        strict=False,
        lazy=False,
    )

    resolved = parser.specification
    if not isinstance(resolved, dict):
        raise ValueError("Resolved OpenAPI specification is not an object.")

    return resolved


def _validate_with_openapi_pydantic(resolved: dict[str, Any]) -> None:
    """Validate resolved document with openapi-pydantic models (3.0 and 3.1)."""

    version = str(resolved.get("openapi", ""))
    if version.startswith("3.0"):
        OpenAPI30.model_validate(resolved)
        return

    OpenAPI31.model_validate(resolved)
