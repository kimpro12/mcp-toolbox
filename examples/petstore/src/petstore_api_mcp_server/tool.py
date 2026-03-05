"""Tool metadata for Petstore API MCP server."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass
class ToolMeta:
    """Metadata descriptor for generated MCP tool."""

    name: str
    method: str
    path: str
    description: str
