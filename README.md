# MCP Toolbox

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

Generate production-ready MCP servers from OpenAPI specs in one command.

<!-- ![Demo](demo.gif) -->

## Quick Start

```bash
pip install -e ".[dev]"
mcp-toolbox generate --spec tests/fixtures/petstore.yaml -o ./output
cd output && pip install -e .
```

## Features

- OpenAPI 3.0/3.1 validation with clear error reporting
- YAML, JSON, local files, and URL inputs
- `$ref` resolution with `prance` (including external refs)
- Typed OpenAPI parsing with `openapi-pydantic`
- Deterministic tool/model ordering and snapshot-backed generation checks
- Structured JSON tool outputs using Pydantic v2 `TypeAdapter`
- Generated Pydantic models from `components/schemas`
- Request-body generation for JSON, `multipart/form-data`, and `application/x-www-form-urlencoded`
- Retry/backoff-aware HTTP client with env-configurable timeout + retry settings
- Auth scaffolding for bearer, oauth2, api key (header/query/cookie), and basic
- Tool curation with explainable selection (`preview --explain-selection`)
- Template override support with `--template-dir`
- Config precedence: CLI > env (`MCP_TOOLBOX_*`) > `pyproject.toml` (`[tool.mcp_toolbox]`) > defaults
- Optional watch mode for local specs (`mcp-toolbox watch`)

## Current Limitations

- `oneOf` / `anyOf` are mapped to Python unions but complex discriminator behavior is still best-effort.
- XML/custom media types are not deeply modeled (JSON/form flows are primary).
- OAuth2 client-credentials generation provides scaffold/env wiring; full token lifecycle automation is left to integrators.

## Example Generated Output

```python
@mcp.tool(structured_output=True)
async def list_pets(limit: int | None = 20, offset: int | None = 0) -> list[dict[str, Any]]:
    """List pets"""
    response = await request_with_retry(
        ctx.client,
        "GET",
        "/pets",
        max_retries=ctx.max_retries,
        backoff_seconds=ctx.backoff_seconds,
        request_kwargs={"params": {"limit": limit, "offset": offset}},
    )
    response.raise_for_status()
    return TypeAdapter(list[dict[str, Any]]).validate_python(response.json())
```

## CLI Options (`generate`)

| Option | Description | Default |
|---|---|---|
| `<spec>` or `--spec` | Path or URL to OpenAPI spec | required (provide one) |
| `-o, --output` | Output directory for generated server | `./output` |
| `-n, --name` | Override auto-detected server name | auto |
| `--max-tools` | Maximum number of generated tools | `12` |
| `--tag`, `--filter-tags` | Include only matching tags (repeatable) | none |
| `--include-tags` | Include tools by tag (repeatable) | none |
| `--exclude-tags` | Exclude tools by tag (repeatable) | none |
| `--prefer-tags` | Prioritize these tags during tool trimming | none |
| `--body-style` | Preferred request body style (`auto/json/form/multipart`) | `auto` |
| `--enums` | Enum style (`literal/strenum`) | `literal` |
| `--dry-run` | Analyze only, do not write files | `false` |
| `--transport-default`, `--transport` | Default transport embedded in generated `server.py` | `stdio` |
| `--template-dir` | Override built-in templates with local files | none |

`watch` command is available for local specs:

```bash
mcp-toolbox watch --spec tests/fixtures/petstore.yaml -o ./output
```

## CI-Friendly Commands

```bash
python -m pip install -e ".[dev]"
python -m ruff check .
python -m ruff format . --check
python -m pytest -q
```

## Docs

- Gap analysis: `docs/v2-gap-analysis.md`
- Template authoring: `docs/template-authoring.md`
- Troubleshooting: `docs/troubleshooting.md`

## Comparison

| Capability | MCP Toolbox | Hand-written MCP server | Generic OpenAPI client generator |
|---|---|---|---|
| One-command MCP server generation | ✅ | ❌ | ❌ |
| MCP tool naming + descriptions | ✅ | manual | ❌ |
| OpenAPI validation + parsing pipeline | ✅ | manual | partial |
| FastMCP-ready async server scaffold | ✅ | manual | ❌ |
| Customizable templates | ✅ | n/a | limited |

## Contributing

1. Fork the repo
2. Create a branch: `git checkout -b feature/my-change`
3. Run checks: `python -m ruff check . && python -m pytest -q`
4. Open a pull request

## License

MIT — see [LICENSE](LICENSE).
