# Changelog

## 0.2.0 - 2026-03-04

### Added

- v2 gap analysis and phase-driven upgrade path.
- Normalized schema IR (`schema_ir.py`) and dedicated type mapper (`type_mapper.py`).
- Deterministic generation snapshots for key generated files.
- Structured JSON outputs with `TypeAdapter` validation in generated tools.
- In-memory MCP E2E test using `create_connected_server_and_client_session()`.
- Retry/backoff HTTP client utilities with env-configurable timeout/retry settings.
- Operation-aware auth detection and OAuth2 client-credentials scaffold metadata.
- Explainable tool selection via `preview --explain-selection`.
- Pagination pattern detection and `get_pagination_hints()` generation.
- Template override support with `--template-dir`.
- Documentation: template authoring + troubleshooting guides.
- `Makefile` with CI-friendly commands.

### Changed

- Default `--max-tools` lowered to `12`.
- Package version bumped from `0.1.0` to `0.2.0`.
- Generated server templates upgraded to v0.2.0 markers.

### Notes

- Advanced discriminator/polymorphic modeling remains best-effort in this release.
