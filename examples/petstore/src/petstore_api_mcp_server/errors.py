"""Error classes for Petstore API MCP server."""

from __future__ import annotations


class APIRequestError(Exception):
    """Raised when outbound API request fails."""
