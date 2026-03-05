from __future__ import annotations

import os
from pathlib import Path
from typing import Any, Literal

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

try:
    import tomllib
except ModuleNotFoundError:  # pragma: no cover - Python 3.10 fallback
    import tomli as tomllib  # type: ignore[no-redef]


class ToolboxSettings(BaseSettings):
    """Application-level settings for MCP Toolbox.

    Values can be overridden via environment variables using the
    ``MCP_TOOLBOX_`` prefix.
    """

    model_config = SettingsConfigDict(env_prefix="MCP_TOOLBOX_", extra="ignore")

    default_max_tools: int = Field(default=12, ge=1, le=500)
    default_transport: Literal["stdio", "sse", "streamable-http"] = "stdio"
    default_body_style: Literal["auto", "json", "form", "multipart"] = "auto"
    default_enum_style: Literal["literal", "strenum"] = "literal"
    watch_interval_seconds: float = Field(default=1.0, gt=0)


def load_toolbox_settings(cwd: Path | None = None) -> ToolboxSettings:
    """Load effective settings with precedence: env > pyproject > defaults."""

    env_settings = ToolboxSettings()

    pyproject_values = _read_pyproject_toolbox_config(cwd or Path.cwd())
    if not pyproject_values:
        return env_settings

    merged = env_settings.model_dump()
    env_names = {
        "default_max_tools": "MCP_TOOLBOX_DEFAULT_MAX_TOOLS",
        "default_transport": "MCP_TOOLBOX_DEFAULT_TRANSPORT",
        "default_body_style": "MCP_TOOLBOX_DEFAULT_BODY_STYLE",
        "default_enum_style": "MCP_TOOLBOX_DEFAULT_ENUM_STYLE",
        "watch_interval_seconds": "MCP_TOOLBOX_WATCH_INTERVAL_SECONDS",
    }

    for key, value in pyproject_values.items():
        if key not in merged:
            continue
        env_name = env_names.get(key)
        if env_name and env_name in os.environ:
            continue
        merged[key] = value

    return ToolboxSettings.model_validate(merged)


def _read_pyproject_toolbox_config(cwd: Path) -> dict[str, Any]:
    """Read `[tool.mcp_toolbox]` values from nearest pyproject.toml."""

    pyproject_path = _find_pyproject(cwd)
    if pyproject_path is None:
        return {}

    try:
        data = tomllib.loads(pyproject_path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}

    tool = data.get("tool", {}) if isinstance(data.get("tool", {}), dict) else {}
    toolbox = tool.get("mcp_toolbox", {}) if isinstance(tool.get("mcp_toolbox", {}), dict) else {}

    allowed_keys = {
        "default_max_tools",
        "default_transport",
        "default_body_style",
        "default_enum_style",
        "watch_interval_seconds",
    }

    return {key: value for key, value in toolbox.items() if key in allowed_keys}


def _find_pyproject(start: Path) -> Path | None:
    """Find nearest pyproject.toml from start path upward."""

    current = start.resolve()
    if current.is_file():
        current = current.parent

    for directory in [current, *current.parents]:
        candidate = directory / "pyproject.toml"
        if candidate.exists():
            return candidate

    return None
