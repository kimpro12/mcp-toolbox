from __future__ import annotations

import re

from mcp_toolbox.utils import (
    http_method_to_verb,
    path_to_resource_name,
    sanitize_identifier,
    to_snake_case,
    truncate_description,
)

TOOL_NAME_PATTERN = re.compile(r"^[a-zA-Z0-9_-]{1,64}$")


def build_tool_name(http_method: str, path: str, operation_id: str | None = None) -> str:
    """Create a deterministic, snake_case tool name for an operation."""

    if operation_id:
        base_name = to_snake_case(operation_id)
    else:
        resource = path_to_resource_name(path)
        if http_method.upper() == "GET" and "{" in path:
            verb = "get"
        else:
            verb = http_method_to_verb(http_method)
        base_name = f"{verb}_{resource}"

    candidate = sanitize_identifier(to_snake_case(base_name))
    if not candidate:
        candidate = "tool"

    return candidate[:64]


def ensure_unique_name(candidate: str, used_names: set[str]) -> str:
    """Ensure generated tool name uniqueness using numeric suffixes."""

    if candidate not in used_names:
        used_names.add(candidate)
        return candidate

    index = 2
    while True:
        suffix = f"_{index}"
        truncated = candidate[: 64 - len(suffix)]
        variant = f"{truncated}{suffix}"
        if variant not in used_names:
            used_names.add(variant)
            return variant
        index += 1


def is_valid_tool_name(name: str) -> bool:
    """Return True if a generated tool name matches MCP constraints."""

    return bool(TOOL_NAME_PATTERN.match(name))


def build_tool_description(
    http_method: str,
    path: str,
    summary: str | None,
    description: str | None,
) -> str:
    """Build an LLM-friendly operation description that starts with a verb."""

    verb = _description_verb(http_method=http_method, path=path)
    resource = path_to_resource_name(path).replace("_", " ")

    selected = ""
    if summary:
        selected = summary.strip()
    elif description:
        selected = truncate_description(description.strip(), max_length=200)

    if not selected:
        return f"{verb} {resource}."

    normalized = selected[0].upper() + selected[1:] if selected else selected
    first_word = normalized.split(" ", 1)[0].strip(".,:;!?()").lower()
    allowed_verbs = {
        "list",
        "get",
        "create",
        "update",
        "delete",
        "retrieve",
        "fetch",
        "search",
        "read",
    }

    if first_word in allowed_verbs:
        return truncate_description(normalized, max_length=200)

    return truncate_description(f"{verb} {normalized[0].lower() + normalized[1:]}", max_length=200)


def _description_verb(http_method: str, path: str) -> str:
    """Pick a sentence-case verb from HTTP method and path shape."""

    method = http_method.upper()
    if method == "GET" and "{" in path:
        return "Get"

    mapping = {
        "GET": "List",
        "POST": "Create",
        "PUT": "Update",
        "PATCH": "Update",
        "DELETE": "Delete",
    }
    return mapping.get(method, method.title())
