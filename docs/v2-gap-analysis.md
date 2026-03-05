# MCP Toolbox v2 Gap Analysis

Date: 2026-03-04

## Phase 0 baseline checks

Commands run:

```bash
python -m pytest -q
python -m ruff check .
python -m ruff format . --check
```

Result:

- `pytest`: pass
- `ruff check`: pass
- `ruff format --check`: pass

Generation smoke checks run:

```bash
mcp-toolbox generate --spec tests/fixtures/petstore.yaml -o /tmp/v2-phase0-pet
mcp-toolbox generate --spec tests/fixtures/github-issues.yaml -o /tmp/v2-phase0-gh
ruff check /tmp/v2-phase0-pet /tmp/v2-phase0-gh
```

Result:

- Both specs generate successfully.
- Generated projects are Ruff-clean.

---

## Current gaps vs Document v2

### 1) Response parsing + structured outputs

**Current state**

- Generated tools always return `str` (raw `response.text`).
- JSON responses are not validated against generated Pydantic models.
- `structured_output=True` is not emitted on tools.

**Target (v2)**

- JSON endpoints should return typed structured outputs (`BaseModel` / `list` / `dict`).
- Non-JSON endpoints can fall back to text/bytes.

**Files to change**

- `src/mcp_toolbox/analyze/models.py`
- `src/mcp_toolbox/analyze/analyzer.py`
- `src/mcp_toolbox/generate/templates/server.py.jinja2`
- `src/mcp_toolbox/generate/templates/models.py.jinja2`
- `src/mcp_toolbox/generate/generator.py`

---

### 2) Model generation quality (Pydantic v2)

**Current state**

- Basic model generation exists.
- Constraints are not emitted as `Annotated[..., Field(...)]`.
- `oneOf/anyOf` are simplified in type mapping.
- Discriminators are not handled.
- Enum mode (`strenum` vs `literal`) is not configurable.

**Target (v2)**

- Dedicated type mapping + schema IR pipeline.
- Better support for unions/discriminators.
- Deterministic model ordering and forward-ref rebuild support.

**Files to change**

- `src/mcp_toolbox/analyze/schema_ir.py` (new)
- `src/mcp_toolbox/analyze/type_mapper.py` (new)
- `src/mcp_toolbox/analyze/analyzer.py`
- `src/mcp_toolbox/generate/templates/models.py.jinja2`
- `src/mcp_toolbox/generate/generator.py`

---

### 3) Auth detection coverage

**Current state**

- Global security scheme detection exists for bearer/apiKey/basic/oauth2.
- Operation-level security overrides are not evaluated.
- Multiple-scheme precedence is simplistic and global-only.
- OAuth2 flow scaffolding is minimal (token env only).

**Target (v2)**

- Resolve auth per operation (fallback to global).
- Preferred precedence: bearer > apiKey header > apiKey query > basic.
- Better OAuth2 client-credentials skeleton docs.

**Files to change**

- `src/mcp_toolbox/analyze/models.py`
- `src/mcp_toolbox/analyze/analyzer.py`
- `src/mcp_toolbox/generate/templates/auth.py.jinja2`
- `src/mcp_toolbox/generate/templates/server.py.jinja2`
- `src/mcp_toolbox/generate/templates/env_example.jinja2`
- `src/mcp_toolbox/generate/templates/readme.md.jinja2`

---

### 4) Tool curation and defaults

**Current state**

- `--max-tools` default is 20.
- Basic truncation heuristic: prioritize GET endpoints.
- No explanation mode for inclusion/exclusion.

**Target (v2)**

- Default max tools = 12.
- Explainable selection in `preview --explain-selection`.
- Better scoring/curation heuristics and deterministic ranking.

**Files to change**

- `src/mcp_toolbox/analyze/models.py`
- `src/mcp_toolbox/analyze/analyzer.py`
- `src/mcp_toolbox/cli.py`
- `src/mcp_toolbox/pipeline.py`
- `src/mcp_toolbox/config.py`

---

### 5) Template override support

**Current state**

- Generation always loads built-in templates from package.
- No `--template-dir` to override templates.

**Target (v2)**

- Support `--template-dir` where matching template files override built-ins.

**Files to change**

- `src/mcp_toolbox/generate/generator.py`
- `src/mcp_toolbox/cli.py`
- `src/mcp_toolbox/pipeline.py`
- `README.md`

---

### 6) Client reliability: retries + env-configurable timeouts

**Current state**

- Shared `httpx.AsyncClient` with static timeout/limits.
- No retry/backoff for 429/5xx.

**Target (v2)**

- Retry loop/backoff for retryable status codes.
- Timeouts/retry attempts configurable via env vars.

**Files to change**

- `src/mcp_toolbox/generate/templates/client.py.jinja2`
- `src/mcp_toolbox/generate/templates/server.py.jinja2`
- `src/mcp_toolbox/generate/templates/env_example.jinja2`
- `src/mcp_toolbox/generate/templates/readme.md.jinja2`

---

### 7) Testing surface (snapshot + E2E in-memory MCP session)

**Current state**

- Unit and integration tests exist.
- No snapshot tests for generated source files.
- No in-memory MCP session E2E test for generated server.

**Target (v2)**

- Snapshot tests for generated `server.py`, `client.py`, model file(s), and one tool module.
- In-memory MCP session E2E with mocked HTTP responses.

**Files to add/change**

- `tests/snapshots/...` (new)
- `tests/test_snapshots.py` (new)
- `tests/test_e2e_mcp_session.py` (new)
- `tests/fixtures/...` (expand as needed)

---

## Planned implementation order

1. **Phase 1**: IR hardening + determinism + snapshot tests.
2. **Phase 2**: Structured outputs + stronger model generation.
3. **Phase 3**: Retries/backoff + auth improvements.
4. **Phase 4**: Tool curation defaults/explain mode + pagination hints.
5. **Phase 5**: Template override + docs/release polish.

All phases will be implemented in small commits, each keeping `pytest` and Ruff green.
