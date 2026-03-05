from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest

from mcp_toolbox.pipeline import PipelineConfig, run_pipeline

try:
    import tomllib
except ModuleNotFoundError:  # pragma: no cover - Python 3.10 fallback
    import tomli as tomllib  # type: ignore[no-redef]


def test_full_pipeline_petstore(petstore_spec_path: Path, tmp_path: Path) -> None:
    """End-to-end generation should produce a runnable server project."""

    output_dir = tmp_path / "petstore_project"
    ir = run_pipeline(
        petstore_spec_path,
        output_dir,
        PipelineConfig(max_tools=20),
    )

    package_dir = output_dir / "src" / f"{ir.server_name}_mcp_server"
    server_file = package_dir / "server.py"
    pyproject_file = output_dir / "pyproject.toml"
    readme_file = output_dir / "README.md"

    assert server_file.exists()
    assert pyproject_file.exists()
    assert readme_file.exists()

    compile(server_file.read_text(encoding="utf-8"), str(server_file), "exec")

    parsed_toml = tomllib.loads(pyproject_file.read_text(encoding="utf-8"))
    assert parsed_toml["project"]["name"].endswith("-mcp-server")
    assert "| Tool | Method | Path | Description |" in readme_file.read_text(encoding="utf-8")


def test_full_pipeline_dry_run(petstore_spec_path: Path, tmp_path: Path) -> None:
    """Dry-run should analyze but never write output files."""

    output_dir = tmp_path / "dry_run_project"
    run_pipeline(
        petstore_spec_path,
        output_dir,
        PipelineConfig(max_tools=20, dry_run=True),
    )

    assert not output_dir.exists()


def test_generated_code_passes_ruff(petstore_spec_path: Path, tmp_path: Path) -> None:
    """Generated code should pass Ruff check with zero errors."""

    output_dir = tmp_path / "ruff_project"
    run_pipeline(
        petstore_spec_path,
        output_dir,
        PipelineConfig(max_tools=20),
    )

    result = subprocess.run(
        [sys.executable, "-m", "ruff", "check", str(output_dir)],
        capture_output=True,
        text=True,
        check=False,
    )

    if result.returncode != 0 and "No module named ruff" in (result.stderr + result.stdout):
        pytest.skip("ruff is not installed in test environment")

    assert result.returncode == 0, result.stdout + result.stderr
