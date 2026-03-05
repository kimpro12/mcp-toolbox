from __future__ import annotations

from pathlib import Path

from mcp_toolbox.config import load_toolbox_settings


def test_load_toolbox_settings_reads_pyproject_values(tmp_path: Path) -> None:
    """Settings loader should pick values from nearest pyproject tool section."""

    pyproject = tmp_path / "pyproject.toml"
    pyproject.write_text(
        """
[tool.mcp_toolbox]
default_max_tools = 9
default_transport = "sse"
default_body_style = "json"
default_enum_style = "strenum"
watch_interval_seconds = 2.5
""".strip(),
        encoding="utf-8",
    )

    settings = load_toolbox_settings(tmp_path)

    assert settings.default_max_tools == 9
    assert settings.default_transport == "sse"
    assert settings.default_body_style == "json"
    assert settings.default_enum_style == "strenum"
    assert settings.watch_interval_seconds == 2.5


def test_load_toolbox_settings_env_overrides_pyproject(tmp_path: Path, monkeypatch) -> None:
    """Environment variables should override pyproject defaults."""

    pyproject = tmp_path / "pyproject.toml"
    pyproject.write_text(
        """
[tool.mcp_toolbox]
default_max_tools = 9
default_transport = "sse"
""".strip(),
        encoding="utf-8",
    )

    monkeypatch.setenv("MCP_TOOLBOX_DEFAULT_MAX_TOOLS", "15")
    monkeypatch.setenv("MCP_TOOLBOX_DEFAULT_TRANSPORT", "streamable-http")

    settings = load_toolbox_settings(tmp_path)

    assert settings.default_max_tools == 15
    assert settings.default_transport == "streamable-http"


def test_load_toolbox_settings_falls_back_to_defaults(tmp_path: Path) -> None:
    """Without pyproject/env overrides, loader should return default settings."""

    settings = load_toolbox_settings(tmp_path)

    assert settings.default_max_tools == 12
    assert settings.default_transport == "stdio"
    assert settings.default_body_style == "auto"
    assert settings.default_enum_style == "literal"
    assert settings.watch_interval_seconds == 1.0
