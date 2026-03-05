from __future__ import annotations

from pathlib import Path

from mcp_toolbox.analyze import AnalyzerConfig, analyze_spec
from mcp_toolbox.generate import MCPGenerator, format_project
from mcp_toolbox.parse import parse_spec


def test_petstore_generation_snapshots(tmp_path: Path, petstore_spec_path: Path) -> None:
    """Generated key files should remain deterministic across runs."""

    ir = analyze_spec(parse_spec(petstore_spec_path), AnalyzerConfig(max_tools=20))

    output_dir = tmp_path / "snapshot_output"
    MCPGenerator().generate(ir, output_dir)
    format_project(output_dir)

    package_dir = output_dir / "src" / f"{ir.server_name}_mcp_server"
    generated_files = {
        "server.py.snap": package_dir / "server.py",
        "client.py.snap": package_dir / "client.py",
        "models.py.snap": package_dir / "models.py",
        "tool.py.snap": package_dir / "tool.py",
        "tools/list_pets.py.snap": package_dir / "tools" / "list_pets.py",
    }

    snapshot_dir = Path(__file__).parent / "snapshots" / "petstore"

    for snapshot_name, generated_path in generated_files.items():
        expected_path = snapshot_dir / snapshot_name
        assert expected_path.exists(), f"Missing snapshot file: {expected_path}"

        generated_content = generated_path.read_text(encoding="utf-8")
        expected_content = expected_path.read_text(encoding="utf-8")

        assert generated_content == expected_content
