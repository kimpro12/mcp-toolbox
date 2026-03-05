from __future__ import annotations

from pathlib import Path

from typer.testing import CliRunner

from mcp_toolbox.cli import app

runner = CliRunner()


def test_cli_help_shows_commands() -> None:
    """Top-level CLI help should list all supported commands."""

    result = runner.invoke(app, ["--help"])

    assert result.exit_code == 0
    assert "generate" in result.stdout
    assert "validate" in result.stdout
    assert "preview" in result.stdout
    assert "watch" in result.stdout


def test_cli_validate_success(petstore_spec_path: Path) -> None:
    """validate command should report success for valid fixture."""

    result = runner.invoke(app, ["validate", str(petstore_spec_path)])

    assert result.exit_code == 0
    assert "Specification is valid" in result.stdout


def test_cli_preview_outputs_tools(petstore_spec_path: Path) -> None:
    """preview command should print analyzed tool names."""

    result = runner.invoke(app, ["preview", str(petstore_spec_path), "--max-tools", "10"])

    assert result.exit_code == 0
    assert "list_pets" in result.stdout
    assert "create_pet" in result.stdout


def test_cli_preview_explain_selection_shows_excluded(petstore_spec_path: Path) -> None:
    """Explain-selection mode should show inclusion/exclusion reasoning."""

    result = runner.invoke(
        app,
        ["preview", str(petstore_spec_path), "--max-tools", "2", "--explain-selection"],
    )

    assert result.exit_code == 0
    assert "Excluded Tools" in result.stdout
    assert "lower priority rank" in result.stdout


def test_cli_generate_dry_run(petstore_spec_path: Path, tmp_path: Path) -> None:
    """dry-run mode should not create generated files."""

    output_dir = tmp_path / "dry_run_output"
    result = runner.invoke(
        app,
        [
            "generate",
            "--spec",
            str(petstore_spec_path),
            "--output",
            str(output_dir),
            "--dry-run",
        ],
    )

    assert result.exit_code == 0
    assert not output_dir.exists()


def test_cli_generate_dry_run_positional_spec(petstore_spec_path: Path, tmp_path: Path) -> None:
    """generate command should also accept positional spec path."""

    output_dir = tmp_path / "dry_run_positional_output"
    result = runner.invoke(
        app,
        [
            "generate",
            str(petstore_spec_path),
            "--output",
            str(output_dir),
            "--dry-run",
        ],
    )

    assert result.exit_code == 0
    assert not output_dir.exists()


def test_cli_generate_rejects_invalid_transport(petstore_spec_path: Path, tmp_path: Path) -> None:
    """generate should reject unsupported transport values."""

    output_dir = tmp_path / "invalid_transport_output"
    result = runner.invoke(
        app,
        [
            "generate",
            str(petstore_spec_path),
            "--output",
            str(output_dir),
            "--transport",
            "ws",
            "--dry-run",
        ],
    )

    assert result.exit_code != 0
    assert "Unsupported transport" in result.output


def test_cli_generate_with_template_dir_override(petstore_spec_path: Path, tmp_path: Path) -> None:
    """CLI should use template overrides from --template-dir."""

    template_dir = tmp_path / "templates"
    template_dir.mkdir(parents=True, exist_ok=True)
    (template_dir / "server.py.jinja2").write_text(
        '''
"""CLI override template."""
from __future__ import annotations

OVERRIDDEN_TEMPLATE = True


def main() -> None:
    return None
'''.strip(),
        encoding="utf-8",
    )

    output_dir = tmp_path / "template_override_output"
    result = runner.invoke(
        app,
        [
            "generate",
            str(petstore_spec_path),
            "--output",
            str(output_dir),
            "--template-dir",
            str(template_dir),
        ],
    )

    assert result.exit_code == 0
    server_file = output_dir / "src" / "petstore_api_mcp_server" / "server.py"
    assert server_file.exists()
    assert "OVERRIDDEN_TEMPLATE = True" in server_file.read_text(encoding="utf-8")


def test_cli_generate_rejects_invalid_body_style(petstore_spec_path: Path, tmp_path: Path) -> None:
    """generate should reject unsupported body-style values."""

    output_dir = tmp_path / "invalid_body_style_output"
    result = runner.invoke(
        app,
        [
            "generate",
            str(petstore_spec_path),
            "--output",
            str(output_dir),
            "--body-style",
            "xml",
            "--dry-run",
        ],
    )

    assert result.exit_code != 0
    assert "Unsupported body style" in result.output


def test_cli_generate_rejects_invalid_enum_style(petstore_spec_path: Path, tmp_path: Path) -> None:
    """generate should reject unsupported enum style values."""

    output_dir = tmp_path / "invalid_enum_style_output"
    result = runner.invoke(
        app,
        [
            "generate",
            str(petstore_spec_path),
            "--output",
            str(output_dir),
            "--enums",
            "enumclass",
            "--dry-run",
        ],
    )

    assert result.exit_code != 0
    assert "Unsupported enum style" in result.output


def test_cli_watch_once_generates_project(petstore_spec_path: Path, tmp_path: Path) -> None:
    """watch --once should perform a single generation pass and exit."""

    output_dir = tmp_path / "watch_once_output"
    result = runner.invoke(
        app,
        [
            "watch",
            str(petstore_spec_path),
            "--output",
            str(output_dir),
            "--once",
        ],
    )

    assert result.exit_code == 0
    server_file = output_dir / "src" / "petstore_api_mcp_server" / "server.py"
    assert server_file.exists()
