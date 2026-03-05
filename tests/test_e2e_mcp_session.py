from __future__ import annotations

import importlib
import os
import sys
from pathlib import Path

import pytest
import respx
from mcp.shared.memory import create_connected_server_and_client_session

from mcp_toolbox.pipeline import PipelineConfig, run_pipeline


@pytest.mark.asyncio
async def test_generated_server_returns_structured_json_output(petstore_spec_path: Path, tmp_path: Path) -> None:
    """In-memory MCP session should return structured output for JSON tools."""

    output_dir = tmp_path / "generated_server"
    ir = run_pipeline(
        petstore_spec_path,
        output_dir,
        PipelineConfig(max_tools=20),
    )

    package_name = f"{ir.server_name}_mcp_server"
    sys.path.insert(0, str(output_dir / "src"))
    try:
        server_module = importlib.import_module(f"{package_name}.server")

        os.environ[f"{ir.server_name.upper()}_BASE_URL"] = "https://api.petstore.example.com/v1"

        with respx.mock(assert_all_called=True) as router:
            router.get("https://api.petstore.example.com/v1/pets").respond(
                200,
                json=[
                    {
                        "id": "pet-1",
                        "name": "Fluffy",
                        "status": "available",
                    }
                ],
            )

            async with create_connected_server_and_client_session(server_module.mcp) as session:
                result = await session.call_tool("list_pets", {"limit": 1, "offset": 0})

        assert result.isError is False
        assert result.structuredContent is not None
        assert "result" in result.structuredContent
        assert isinstance(result.structuredContent["result"], list)
        assert result.structuredContent["result"][0]["id"] == "pet-1"
    finally:
        sys.path = [p for p in sys.path if p != str(output_dir / "src")]
        for module_name in [name for name in list(sys.modules) if name.startswith(package_name)]:
            del sys.modules[module_name]
