# Troubleshooting

## 1) Validation fails with cryptic schema errors

Try:

```bash
mcp-toolbox validate path/to/spec.yaml
```

Common causes:

- Missing `info.title` or `info.version`
- Invalid `paths` structure
- YAML values parsed as dates (quote version strings like `"2022-11-28"`)

## 2) `$ref` not resolving

- Prefer absolute or correct relative ref paths.
- For URL specs, ensure referenced files are reachable from the same host/path.

## 3) Generated code imports but server exits quickly

- Check auth + base URL env vars.
- Ensure command transport is valid (`stdio`, `sse`, `streamable-http`).

## 4) OAuth2 server generated but token flow not automatic

Current v2 generates auth scaffolding and env variables.
You still need to provide an access token (or implement token bootstrap logic in generated auth module).

## 5) Too many/too few generated tools

- Use `--max-tools` to tune output size (default 12).
- Use `--tag` to narrow scope.
- Use `preview --explain-selection` to inspect inclusion/exclusion reasons.

## 6) Template override not being applied

- Confirm `--template-dir` points to a directory.
- Ensure file names match template names exactly (e.g. `server.py.jinja2`).

## 7) CI check failures

Use the same local commands as CI:

```bash
python -m pip install -e ".[dev]"
python -m ruff check .
python -m ruff format . --check
python -m pytest -q
```
