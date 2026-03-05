# Template Authoring Guide

MCP Toolbox templates are Jinja2 files loaded from:

- Built-in: `src/mcp_toolbox/generate/templates/`
- Optional overrides: `--template-dir <dir>`

When `--template-dir` is provided, any matching file name overrides the built-in template while non-overridden templates still use packaged defaults.

## Supported template filenames

- `server.py.jinja2`
- `client.py.jinja2`
- `auth.py.jinja2`
- `models.py.jinja2`
- `errors.py.jinja2`
- `tool.py.jinja2`
- `tool_module.py.jinja2`
- `tools_init.py.jinja2`
- `pyproject.toml.jinja2`
- `readme.md.jinja2`
- `env_example.jinja2`
- `init.py.jinja2`
- `conftest.py.jinja2`

## Context variables

Core variables available to all templates:

- `server_name`, `server_title`, `server_description`, `base_url`
- `tools` (list of `ToolDefinition`)
- `models` / `rendered_models`
- `auth` (`AuthConfig`)
- `dependencies`
- import helper lists (`typing_imports`, `datetime_imports`, ...)

## Example override

Create a folder and override one file:

```bash
mkdir -p my-templates
cat > my-templates/server.py.jinja2 <<'J2'
"""Custom server for {{ server_title }}."""
from __future__ import annotations

CUSTOM_TEMPLATE_MARKER = "{{ server_name }}"


def main() -> None:
    return None
J2

mcp-toolbox generate --spec tests/fixtures/petstore.yaml -o out --template-dir my-templates
```

## Tips

- Keep generated files Ruff-clean.
- Preserve required entrypoints (`main()` in `server.py`).
- Use deterministic output (avoid timestamps/random IDs in templates).
