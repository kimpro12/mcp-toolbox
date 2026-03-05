.PHONY: install lint format-check test check smoke

install:
	python -m pip install -e ".[dev]"

lint:
	python -m ruff check .

format-check:
	python -m ruff format . --check

test:
	python -m pytest -q

check: lint format-check test

smoke:
	rm -rf /tmp/mcp-smoke-out
	mcp-toolbox generate --spec tests/fixtures/petstore.yaml -o /tmp/mcp-smoke-out
	python -m ruff check /tmp/mcp-smoke-out
