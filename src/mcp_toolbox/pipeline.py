from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from rich.console import Console
from rich.progress import Progress

from mcp_toolbox.analyze import AnalyzerConfig, ServerIR, analyze_spec
from mcp_toolbox.generate import MCPGenerator, format_project, validate_syntax
from mcp_toolbox.parse import parse_spec
from mcp_toolbox.validate import validate_spec

console = Console()


@dataclass
class PipelineConfig:
    """Configuration for orchestrating the generation pipeline."""

    server_name: str | None = None
    max_tools: int = 12
    filter_tags: list[str] | None = None
    include_tags: list[str] | None = None
    exclude_tags: list[str] | None = None
    prefer_tags: list[str] | None = None
    body_style: str = "auto"
    enum_style: str = "literal"
    transport_default: str = "stdio"
    template_dir: Path | None = None
    dry_run: bool = False


def run_pipeline(spec_path: str | Path, output_dir: Path, config: PipelineConfig) -> ServerIR:
    """Execute the full OpenAPI-to-MCP generation pipeline.

    Args:
        spec_path: Local path or URL to OpenAPI specification.
        output_dir: Generation destination directory.
        config: Pipeline execution options.

    Returns:
        Generated ServerIR object.

    Raises:
        SystemExit: If validation or syntax checks fail.
    """

    total_steps = 6 if not config.dry_run else 3

    with Progress() as progress:
        task = progress.add_task("Generating MCP server...", total=total_steps)

        progress.update(task, description="Validating spec...")
        validation = validate_spec(spec_path)
        if not validation.is_valid:
            console.print("[red]Validation failed:[/red]")
            for err in validation.errors:
                console.print(f" [red]✗[/red] {err}")
            raise SystemExit(1)

        for warning in validation.warnings:
            console.print(f"[yellow]⚠ {warning}[/yellow]")
        progress.advance(task)

        progress.update(task, description="Parsing spec...")
        parsed = parse_spec(spec_path)
        progress.advance(task)

        progress.update(task, description="Analyzing operations...")
        analyzer_config = AnalyzerConfig(
            filter_tags=config.filter_tags,
            include_tags=config.include_tags,
            exclude_tags=config.exclude_tags,
            prefer_tags=config.prefer_tags,
            max_tools=config.max_tools,
            server_name=config.server_name,
            body_style=config.body_style,
            enum_style=config.enum_style,
        )
        ir = analyze_spec(parsed, analyzer_config)
        progress.advance(task)

        if config.dry_run:
            console.print()
            console.print("[green]✓ Dry run complete[/green]")
            console.print(f" API: {ir.server_title}")
            console.print(f" Tools (planned): {len(ir.tools)}")
            console.print(f" Auth: {ir.auth.auth_type.value}")
            return ir

        progress.update(task, description="Generating code...")
        generator = MCPGenerator(template_dir=config.template_dir)
        files = generator.generate(ir, output_dir, default_transport=config.transport_default)
        progress.advance(task)

        progress.update(task, description="Formatting code...")
        format_project(output_dir)
        progress.advance(task)

        progress.update(task, description="Validating syntax...")
        all_valid = True
        for generated_file in files:
            if generated_file.suffix != ".py":
                continue
            valid, err = validate_syntax(generated_file)
            if not valid:
                console.print(f"[red]Syntax error in {generated_file.name}:[/red] {err}")
                all_valid = False
        progress.advance(task)

    if not all_valid:
        raise SystemExit(1)

    console.print()
    console.print(f"[green]✓ Generated MCP server in {output_dir}[/green]")
    console.print(f" Tools: {len(ir.tools)}")
    console.print(f" Auth: {ir.auth.auth_type.value}")
    console.print()
    console.print("To run your server:")
    console.print(f" cd {output_dir}")
    console.print(" pip install -e .")
    console.print(f" {ir.server_name}-mcp-server")

    return ir
