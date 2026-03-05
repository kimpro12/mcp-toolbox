from __future__ import annotations

from pathlib import Path

import pytest

from mcp_toolbox.analyze import AnalyzerConfig, ServerIR, analyze_spec
from mcp_toolbox.parse import ParsedSpec, parse_spec


@pytest.fixture
def petstore_spec_path() -> Path:
    """Return path to the Petstore OpenAPI fixture."""

    return Path(__file__).parent / "fixtures" / "petstore.yaml"


@pytest.fixture
def parsed_petstore(petstore_spec_path: Path) -> ParsedSpec:
    """Return parsed Petstore spec fixture."""

    return parse_spec(petstore_spec_path)


@pytest.fixture
def analyzed_petstore(parsed_petstore: ParsedSpec) -> ServerIR:
    """Return analyzed IR for Petstore fixture."""

    return analyze_spec(parsed_petstore, AnalyzerConfig(max_tools=20))
