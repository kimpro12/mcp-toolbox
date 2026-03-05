from __future__ import annotations

import time
from pathlib import Path
from typing import Annotated
from urllib.parse import urlparse

import typer
from rich.console import Console
from rich.table import Table

from mcp_toolbox.analyze import AnalyzerConfig, analyze_spec, explain_tool_selection
from mcp_toolbox.config import load_toolbox_settings
from mcp_toolbox.parse import parse_spec
from mcp_toolbox.pipeline import PipelineConfig, run_pipeline
from mcp_toolbox.validate import validate_spec

app = typer.Typer(
    name="mcp-toolbox",
    help="Generate production-ready MCP servers from OpenAPI specs.",
    no_args_is_help=True,
)

console = Console()


@app.command()
def generate(
    spec: Annotated[
        str | None,
        typer.Argument(help="Path or URL to OpenAPI spec (YAML/JSON)", show_default=False),
    ] = None,
    spec_option: Annotated[
        str | None,
        typer.Option("--spec", help="Path or URL to OpenAPI spec (YAML/JSON)"),
    ] = None,
    output: Annotated[Path, typer.Option("--output", "-o", help="Output directory")] = Path("./output"),
    name: Annotated[str | None, typer.Option("--name", "-n", help="Server name override")] = None,
    transport_default: Annotated[
        str | None,
        typer.Option("--transport-default", "--transport", help="Default transport (stdio/sse/streamable-http)"),
    ] = None,
    max_tools: Annotated[int | None, typer.Option(help="Maximum number of tools to generate", min=1)] = None,
    filter_tags: Annotated[
        list[str] | None,
        typer.Option("--tag", "--filter-tags", help="Only generate tools for these tags"),
    ] = None,
    include_tags: Annotated[
        list[str] | None,
        typer.Option("--include-tags", help="Include tools that match these tags"),
    ] = None,
    exclude_tags: Annotated[
        list[str] | None,
        typer.Option("--exclude-tags", help="Exclude tools that match these tags"),
    ] = None,
    prefer_tags: Annotated[
        list[str] | None,
        typer.Option("--prefer-tags", help="Prefer these tags when trimming by max-tools"),
    ] = None,
    body_style: Annotated[
        str | None,
        typer.Option("--body-style", help="Preferred request body style: auto/json/form/multipart"),
    ] = None,
    enum_style: Annotated[
        str | None,
        typer.Option("--enums", help="Enum style: literal/strenum"),
    ] = None,
    template_dir: Annotated[
        Path | None,
        typer.Option("--template-dir", help="Directory containing template overrides"),
    ] = None,
    dry_run: Annotated[bool, typer.Option("--dry-run", help="Preview without generating files")] = False,
) -> None:
    """Generate an MCP server from an OpenAPI specification."""

    selected_spec = spec_option or spec
    if not selected_spec:
        raise typer.BadParameter("Provide a spec path/URL via positional argument or --spec option.")

    if template_dir is not None and not template_dir.is_dir():
        raise typer.BadParameter(f"Template directory does not exist: {template_dir}")

    settings = load_toolbox_settings(Path.cwd())

    resolved_transport = transport_default or settings.default_transport
    _validate_transport(resolved_transport)

    resolved_body_style = body_style or settings.default_body_style
    _validate_body_style(resolved_body_style)

    resolved_enum_style = enum_style or settings.default_enum_style
    _validate_enum_style(resolved_enum_style)

    resolved_max_tools = max_tools or settings.default_max_tools

    config = PipelineConfig(
        server_name=name,
        max_tools=resolved_max_tools,
        filter_tags=filter_tags,
        include_tags=include_tags,
        exclude_tags=exclude_tags,
        prefer_tags=prefer_tags,
        body_style=resolved_body_style,
        enum_style=resolved_enum_style,
        transport_default=resolved_transport,
        template_dir=template_dir,
        dry_run=dry_run,
    )
    run_pipeline(selected_spec, output, config)


@app.command()
def watch(
    spec: Annotated[
        str | None,
        typer.Argument(help="Path or URL to OpenAPI spec (YAML/JSON)", show_default=False),
    ] = None,
    spec_option: Annotated[
        str | None,
        typer.Option("--spec", help="Path or URL to OpenAPI spec (YAML/JSON)"),
    ] = None,
    output: Annotated[Path, typer.Option("--output", "-o", help="Output directory")] = Path("./output"),
    name: Annotated[str | None, typer.Option("--name", "-n", help="Server name override")] = None,
    transport_default: Annotated[
        str | None,
        typer.Option("--transport-default", "--transport", help="Default transport (stdio/sse/streamable-http)"),
    ] = None,
    max_tools: Annotated[int | None, typer.Option(help="Maximum number of tools to generate", min=1)] = None,
    filter_tags: Annotated[
        list[str] | None,
        typer.Option("--tag", "--filter-tags", help="Only generate tools for these tags"),
    ] = None,
    include_tags: Annotated[
        list[str] | None,
        typer.Option("--include-tags", help="Include tools that match these tags"),
    ] = None,
    exclude_tags: Annotated[
        list[str] | None,
        typer.Option("--exclude-tags", help="Exclude tools that match these tags"),
    ] = None,
    prefer_tags: Annotated[
        list[str] | None,
        typer.Option("--prefer-tags", help="Prefer these tags when trimming by max-tools"),
    ] = None,
    body_style: Annotated[
        str | None,
        typer.Option("--body-style", help="Preferred request body style: auto/json/form/multipart"),
    ] = None,
    enum_style: Annotated[
        str | None,
        typer.Option("--enums", help="Enum style: literal/strenum"),
    ] = None,
    template_dir: Annotated[
        Path | None,
        typer.Option("--template-dir", help="Directory containing template overrides"),
    ] = None,
    interval: Annotated[float | None, typer.Option("--interval", help="Watch polling interval in seconds")] = None,
    once: Annotated[bool, typer.Option("--once", help="Generate once then exit")] = False,
) -> None:
    """Watch local files and regenerate when changes are detected."""

    selected_spec = spec_option or spec
    if not selected_spec:
        raise typer.BadParameter("Provide a spec path/URL via positional argument or --spec option.")

    if template_dir is not None and not template_dir.is_dir():
        raise typer.BadParameter(f"Template directory does not exist: {template_dir}")

    settings = load_toolbox_settings(Path.cwd())

    resolved_transport = transport_default or settings.default_transport
    _validate_transport(resolved_transport)

    resolved_body_style = body_style or settings.default_body_style
    _validate_body_style(resolved_body_style)

    resolved_enum_style = enum_style or settings.default_enum_style
    _validate_enum_style(resolved_enum_style)

    resolved_max_tools = max_tools or settings.default_max_tools
    resolved_interval = interval or settings.watch_interval_seconds

    config = PipelineConfig(
        server_name=name,
        max_tools=resolved_max_tools,
        filter_tags=filter_tags,
        include_tags=include_tags,
        exclude_tags=exclude_tags,
        prefer_tags=prefer_tags,
        body_style=resolved_body_style,
        enum_style=resolved_enum_style,
        transport_default=resolved_transport,
        template_dir=template_dir,
        dry_run=False,
    )

    run_pipeline(selected_spec, output, config)

    if once or _is_url(selected_spec):
        if _is_url(selected_spec) and not once:
            console.print("[yellow]Watch mode for URL specs is one-shot only.[/yellow]")
        return

    watch_paths = [Path(selected_spec).expanduser().resolve()]
    if template_dir is not None:
        watch_paths.append(template_dir.resolve())

    last_state = _snapshot_files(watch_paths)

    console.print(f"[cyan]Watching for changes every {resolved_interval:.2f}s... (Ctrl+C to stop)[/cyan]")
    try:
        while True:
            time.sleep(resolved_interval)
            current_state = _snapshot_files(watch_paths)
            if current_state != last_state:
                console.print("[cyan]Change detected. Regenerating...[/cyan]")
                try:
                    run_pipeline(selected_spec, output, config)
                except SystemExit:
                    console.print("[red]Generation failed; watching for next change...[/red]")
                last_state = current_state
    except KeyboardInterrupt:
        console.print("[yellow]Watch stopped.[/yellow]")


@app.command()
def validate(
    spec: Annotated[str, typer.Argument(help="Path or URL to OpenAPI spec")],
) -> None:
    """Validate an OpenAPI specification for MCP server generation."""

    result = validate_spec(spec)

    console.print(f"Spec version: {result.spec_version}")
    for warning in result.warnings:
        console.print(f"[yellow]⚠ {warning}[/yellow]")

    if result.is_valid:
        console.print("[green]✓ Specification is valid[/green]")
        raise typer.Exit(code=0)

    console.print("[red]✗ Specification is invalid[/red]")
    for err in result.errors:
        console.print(f" - {err}")
    raise typer.Exit(code=1)


@app.command()
def preview(
    spec: Annotated[str, typer.Argument(help="Path or URL to OpenAPI spec")],
    max_tools: Annotated[int | None, typer.Option(help="Max tools", min=1)] = None,
    filter_tags: Annotated[
        list[str] | None,
        typer.Option("--tag", "--filter-tags", help="Only preview tools for these tags"),
    ] = None,
    include_tags: Annotated[
        list[str] | None,
        typer.Option("--include-tags", help="Include tools that match these tags"),
    ] = None,
    exclude_tags: Annotated[
        list[str] | None,
        typer.Option("--exclude-tags", help="Exclude tools that match these tags"),
    ] = None,
    prefer_tags: Annotated[
        list[str] | None,
        typer.Option("--prefer-tags", help="Prefer these tags when trimming by max-tools"),
    ] = None,
    body_style: Annotated[
        str | None,
        typer.Option("--body-style", help="Preferred request body style: auto/json/form/multipart"),
    ] = None,
    enum_style: Annotated[
        str | None,
        typer.Option("--enums", help="Enum style: literal/strenum"),
    ] = None,
    explain_selection: Annotated[
        bool,
        typer.Option("--explain-selection", help="Explain why tools were included/excluded"),
    ] = False,
) -> None:
    """Preview the tools that would be generated without writing files."""

    validation = validate_spec(spec)
    if not validation.is_valid:
        console.print("[red]Validation failed:[/red]")
        for err in validation.errors:
            console.print(f" - {err}")
        raise typer.Exit(code=1)

    settings = load_toolbox_settings(Path.cwd())
    resolved_max_tools = max_tools or settings.default_max_tools
    resolved_body_style = body_style or settings.default_body_style
    resolved_enum_style = enum_style or settings.default_enum_style

    _validate_body_style(resolved_body_style)
    _validate_enum_style(resolved_enum_style)

    parsed = parse_spec(spec)
    config = AnalyzerConfig(
        max_tools=resolved_max_tools,
        filter_tags=filter_tags,
        include_tags=include_tags,
        exclude_tags=exclude_tags,
        prefer_tags=prefer_tags,
        body_style=resolved_body_style,
        enum_style=resolved_enum_style,
    )
    ir = analyze_spec(parsed, config)

    table = Table(title=f"MCP Tool Preview — {ir.server_title}")
    table.add_column("Tool", style="cyan")
    table.add_column("Method", style="magenta")
    table.add_column("Path", style="green")
    table.add_column("Description")
    table.add_column("Tags")

    if explain_selection:
        table.add_column("Selection Reason")

    for tool in ir.tools:
        row = [
            tool.name,
            tool.http_method,
            tool.path,
            tool.description,
            ", ".join(tool.tags),
        ]
        if explain_selection:
            row.append(tool.selection_reason or "Included")
        table.add_row(*row)

    console.print(table)

    if explain_selection:
        decisions = explain_tool_selection(parsed, config)
        excluded = [decision for decision in decisions if not decision.included]

        if excluded:
            excluded_table = Table(title="Excluded Tools")
            excluded_table.add_column("Tool", style="yellow")
            excluded_table.add_column("Method", style="magenta")
            excluded_table.add_column("Path", style="green")
            excluded_table.add_column("Rank")
            excluded_table.add_column("Reason")

            for decision in excluded:
                excluded_table.add_row(
                    decision.name,
                    decision.method,
                    decision.path,
                    str(decision.rank),
                    decision.reason,
                )

            console.print()
            console.print(excluded_table)

    console.print(f"\nAuth: [bold]{ir.auth.auth_type.value}[/bold]")


def _snapshot_files(paths: list[Path]) -> dict[str, int]:
    """Create a stable map of file mtimes for watch mode."""

    snapshot: dict[str, int] = {}
    for path in paths:
        if path.is_file():
            snapshot[str(path)] = path.stat().st_mtime_ns
            continue

        if path.is_dir():
            for file_path in sorted(path.rglob("*")):
                if file_path.is_file():
                    snapshot[str(file_path)] = file_path.stat().st_mtime_ns

    return snapshot


def _is_url(value: str) -> bool:
    """Return True when provided spec input looks like an HTTP(S) URL."""

    parsed = urlparse(value)
    return parsed.scheme in {"http", "https"} and bool(parsed.netloc)


def _validate_transport(value: str) -> None:
    """Validate transport option value."""

    allowed_transports = {"stdio", "sse", "streamable-http"}
    if value not in allowed_transports:
        raise typer.BadParameter(
            f"Unsupported transport '{value}'. Choose one of: {', '.join(sorted(allowed_transports))}."
        )


def _validate_body_style(value: str) -> None:
    """Validate body style option value."""

    allowed_styles = {"auto", "json", "form", "multipart"}
    if value not in allowed_styles:
        raise typer.BadParameter(
            f"Unsupported body style '{value}'. Choose one of: {', '.join(sorted(allowed_styles))}."
        )


def _validate_enum_style(value: str) -> None:
    """Validate enum style option value."""

    allowed_styles = {"literal", "strenum"}
    if value not in allowed_styles:
        raise typer.BadParameter(
            f"Unsupported enum style '{value}'. Choose one of: {', '.join(sorted(allowed_styles))}."
        )


if __name__ == "__main__":
    app()
