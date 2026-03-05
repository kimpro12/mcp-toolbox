from __future__ import annotations

import keyword
import re


def to_snake_case(name: str) -> str:
    """Convert an arbitrary string to snake_case.

    Supports camelCase, PascalCase, kebab-case, and whitespace-separated input.
    """

    raw = name.strip()
    if not raw:
        return ""

    normalized = re.sub(r"[\-\s./]+", "_", raw)
    normalized = re.sub(r"(.)([A-Z][a-z]+)", r"\1_\2", normalized)
    normalized = re.sub(r"([a-z0-9])([A-Z])", r"\1_\2", normalized)
    normalized = re.sub(r"[^\w]", "_", normalized, flags=re.UNICODE)
    normalized = re.sub(r"_+", "_", normalized)

    return normalized.strip("_").lower()


def to_pascal_case(name: str) -> str:
    """Convert an arbitrary string to PascalCase."""

    if not name.strip():
        return ""

    snake = to_snake_case(name)
    parts = [part for part in snake.split("_") if part]
    return "".join(part[:1].upper() + part[1:] for part in parts)


def sanitize_identifier(name: str) -> str:
    """Return a safe Python identifier from arbitrary text.

    Invalid characters are replaced with underscores. If the identifier starts
    with a digit, an underscore is prepended.
    """

    if not name:
        return "_"

    sanitized = re.sub(r"[^\w]", "_", name, flags=re.UNICODE)
    sanitized = re.sub(r"_+", "_", sanitized).strip("_")

    if not sanitized:
        sanitized = "_"

    if sanitized[0].isdigit():
        sanitized = f"_{sanitized}"

    if keyword.iskeyword(sanitized):
        sanitized = f"{sanitized}_"

    return sanitized


def truncate_description(text: str, max_length: int = 200) -> str:
    """Truncate text at a word boundary and append ellipsis when needed."""

    stripped = text.strip()
    if len(stripped) <= max_length:
        return stripped

    if max_length <= 3:
        return "." * max_length

    candidate = stripped[: max_length - 3].rstrip()
    if " " in candidate:
        candidate = candidate.rsplit(" ", 1)[0]

    return f"{candidate}..."


def http_method_to_verb(method: str) -> str:
    """Map an HTTP method to a concise action verb."""

    mapping = {
        "GET": "list",
        "POST": "create",
        "PUT": "update",
        "PATCH": "update",
        "DELETE": "delete",
    }
    return mapping.get(method.upper(), method.lower())


def path_to_resource_name(path: str) -> str:
    """Extract a resource name from a URL path.

    Example:
        /api/v1/users/{id}/orders -> orders
    """

    segments = [segment for segment in path.split("/") if segment]
    candidates = [segment for segment in segments if not (segment.startswith("{") and segment.endswith("}"))]

    if not candidates:
        return "resource"

    return to_snake_case(candidates[-1]) or "resource"
