"""Local runner for testing Schema Doc-Bot on local Avro files."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Literal

from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from .avro_analyzer import AnalysisResult, AvroAnalyzer
from .config import LLMConfig, LLMProviderConfig
from .llm_client import create_llm_client
from .schema_updater import SchemaUpdater

console = Console()


def run_local(
    schema_paths: list[Path],
    llm_provider: str,
    api_key: str,
    model: str | None = None,
    min_confidence: str = "low",
    output_dir: Path | None = None,
) -> None:
    """
    Run Schema Doc-Bot on local Avro schema files.

    Args:
        schema_paths: List of paths to .avsc files or directories
        llm_provider: LLM provider to use
        api_key: API key for the LLM provider
        model: Model override
        min_confidence: Minimum confidence threshold
        output_dir: Directory to write updated schemas (None = print to stdout)
    """
    console.print(
        Panel.fit(
            "[bold cyan]🤖 Schema Doc-Bot (Local Mode)[/bold cyan]\n"
            "Documenting local Avro schema files",
            border_style="cyan",
        )
    )

    # Collect all schema files
    schema_files: list[Path] = []
    for path in schema_paths:
        if path.is_file() and path.suffix == ".avsc":
            schema_files.append(path)
        elif path.is_dir():
            schema_files.extend(path.glob("**/*.avsc"))

    if not schema_files:
        console.print("[yellow]No .avsc files found[/yellow]")
        return

    console.print(f"Found [green]{len(schema_files)}[/green] schema files")

    # Load and analyze schemas
    analyzer = AvroAnalyzer()
    schemas_to_process: list[tuple[Path, dict, AnalysisResult]] = []

    for file_path in schema_files:
        try:
            with open(file_path) as f:
                schema = json.load(f)
            result = analyzer.analyze_schema(file_path.name, schema)
            if result.missing_docs:
                schemas_to_process.append((file_path, schema, result))
        except json.JSONDecodeError as e:
            console.print(f"[red]Error parsing {file_path}: {e}[/red]")
        except Exception as e:
            console.print(f"[red]Error reading {file_path}: {e}[/red]")

    # Display analysis
    _display_analysis(schemas_to_process)

    if not schemas_to_process:
        console.print("\n[green]✓ All schemas are fully documented![/green]")
        return

    total_missing = sum(len(r.missing_docs) for _, _, r in schemas_to_process)
    console.print(
        f"\n[yellow]Found {total_missing} undocumented elements "
        f"across {len(schemas_to_process)} schemas[/yellow]"
    )

    # Create LLM config
    llm_config = LLMConfig(
        default_provider=llm_provider,
        min_confidence=min_confidence,  # type: ignore
    )
    provider_config = LLMProviderConfig(
        api_key=api_key,
        model=model or "",
    )

    # Generate documentation
    console.print("\n[bold]Generating documentation...[/bold]")
    
    try:
        llm_client = create_llm_client(llm_provider, llm_config, provider_config)
    except ValueError as e:
        console.print(f"[red]Error: {e}[/red]")
        return

    updater = SchemaUpdater()

    for file_path, schema, result in schemas_to_process:
        console.print(f"\n[cyan]{file_path.name}[/cyan]")

        schema_context = {
            "name": schema.get("name"),
            "doc": schema.get("doc"),
            "namespace": schema.get("namespace"),
        }

        generated = llm_client.generate_documentation(result.missing_docs, schema_context)

        if not generated:
            console.print("  [yellow]No documentation generated[/yellow]")
            continue

        # Display generated docs
        for doc in generated:
            conf_color = {"high": "green", "medium": "yellow", "low": "red"}.get(
                doc.confidence, "white"
            )
            truncated = doc.documentation[:70] + "..." if len(doc.documentation) > 70 else doc.documentation
            console.print(
                f"  • [bold]{doc.path.split('.')[-1]}[/bold]: {truncated} "
                f"[{conf_color}][{doc.confidence}][/{conf_color}]"
            )

        # Apply documentation
        update = updater.apply_documentation(
            schema, generated, str(file_path), min_confidence
        )

        if update and output_dir:
            output_path = output_dir / file_path.name
            output_path.parent.mkdir(parents=True, exist_ok=True)
            with open(output_path, "w") as f:
                json.dump(update.updated_schema, f, indent=2)
            console.print(f"  [green]Wrote: {output_path}[/green]")


def _display_analysis(schemas: list[tuple[Path, dict, AnalysisResult]]) -> None:
    """Display analysis results in a table."""
    if not schemas:
        return

    table = Table(title="Schemas Needing Documentation")
    table.add_column("File", style="cyan")
    table.add_column("Schema", style="white")
    table.add_column("Missing", justify="right", style="red")
    table.add_column("Coverage", justify="right")

    for file_path, schema, result in schemas:
        coverage = f"{result.coverage_percent:.0f}%"
        coverage_style = (
            "green"
            if result.coverage_percent >= 80
            else "yellow" if result.coverage_percent >= 50 else "red"
        )
        table.add_row(
            file_path.name,
            schema.get("name", "unknown"),
            str(len(result.missing_docs)),
            f"[{coverage_style}]{coverage}[/{coverage_style}]",
        )

    console.print(table)
