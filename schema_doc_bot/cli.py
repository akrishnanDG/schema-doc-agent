"""Command-line interface for Schema Documentation Agent."""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Literal

import click
from dotenv import load_dotenv
from rich.console import Console
from rich.panel import Panel
from rich.progress import Progress, SpinnerColumn, TextColumn
from rich.table import Table

from .avro_analyzer import AnalysisResult, AvroAnalyzer
from .config import (
    Config,
    LLMProviderConfig,
    generate_sample_config,
    load_config,
)
from .github_client import GitHubClient, SchemaUpdate
from .llm_client import (
    GeneratedDoc,
    create_llm_client,
    get_available_providers,
)
from .registry_client import SchemaRegistryClient
from .schema_updater import SchemaUpdater

console = Console()


@click.group()
@click.version_option(version="2.0.0")
@click.option(
    "--config",
    "-c",
    "config_path",
    type=click.Path(exists=False, path_type=Path),
    help="Path to config file (default: schema-doc-bot.yaml)",
)
@click.pass_context
def cli(ctx: click.Context, config_path: Path | None):
    """Schema Documentation Agent: Autonomous documentation for Avro, JSON Schema, and Protobuf."""
    load_dotenv()
    ctx.ensure_object(dict)
    ctx.obj["config"] = load_config(config_path)


@cli.command()
@click.pass_context
def init(ctx: click.Context):
    """Generate a sample configuration file."""
    output_path = Path("schema-doc-bot.yaml")
    
    if output_path.exists():
        if not click.confirm(f"{output_path} already exists. Overwrite?"):
            return
    
    output_path.write_text(generate_sample_config())
    console.print(f"[green]✓ Created {output_path}[/green]")
    console.print("\nEdit the file and set your credentials via environment variables:")
    console.print("  export GITHUB_TOKEN=ghp_...")
    console.print("  export OPENAI_API_KEY=sk-...")


@cli.command()
@click.pass_context
def providers(ctx: click.Context):
    """List available LLM providers."""
    table = Table(title="Available LLM Providers")
    table.add_column("Provider", style="cyan")
    table.add_column("Default Model")
    table.add_column("Env Variable")
    table.add_column("Notes")

    provider_info = [
        ("openai", "gpt-4o-mini", "OPENAI_API_KEY", "Cheapest quality option"),
        ("anthropic", "claude-3-haiku-20240307", "ANTHROPIC_API_KEY", "Fast and capable"),
        ("google", "gemini-1.5-flash", "GOOGLE_API_KEY", "Google Gemini"),
        ("mistral", "mistral-small-latest", "MISTRAL_API_KEY", "EU-based option"),
        ("ollama", "llama3.2", "OLLAMA_BASE_URL", "Local, free, private"),
        ("azure", "gpt-4o-mini", "AZURE_OPENAI_API_KEY", "Enterprise Azure OpenAI"),
    ]

    for name, model, env, notes in provider_info:
        table.add_row(name, model, env, notes)

    console.print(table)


@cli.command()
@click.option("--registry-url", envvar="SCHEMA_REGISTRY_URL", help="Schema Registry URL")
@click.option("--registry-user", envvar="SCHEMA_REGISTRY_USER", help="Registry username")
@click.option("--registry-password", envvar="SCHEMA_REGISTRY_PASSWORD", help="Registry password")
@click.option("--github-token", envvar="GITHUB_TOKEN", help="GitHub PAT")
@click.option("--github-repo", envvar="GITHUB_REPO", help="GitHub repository (owner/repo)")
@click.option("--include", "-i", "include_subjects", multiple=True, help="Subject patterns to include (glob)")
@click.option("--exclude", "-e", "exclude_subjects", multiple=True, help="Subject patterns to exclude (glob)")
@click.option("--provider", "-p", help="LLM provider (openai, anthropic, google, mistral, ollama, azure)")
@click.option("--model", "-m", help="Model to use (overrides config)")
@click.option("--min-confidence", type=click.Choice(["high", "medium", "low"]), help="Minimum confidence")
@click.option("--base-branch", help="Base branch for PR")
@click.option("--dry-run", is_flag=True, help="Preview without making changes")
@click.pass_context
def run(
    ctx: click.Context,
    registry_url: str | None,
    registry_user: str | None,
    registry_password: str | None,
    github_token: str | None,
    github_repo: str | None,
    include_subjects: tuple[str, ...],
    exclude_subjects: tuple[str, ...],
    provider: str | None,
    model: str | None,
    min_confidence: str | None,
    base_branch: str | None,
    dry_run: bool,
):
    """Run Schema Doc-Bot: pull from registry, generate docs, create PR."""
    config: Config = ctx.obj["config"]
    
    # Apply CLI overrides
    if registry_url:
        config.schema_registry.url = registry_url
    if registry_user:
        config.schema_registry.username = registry_user
    if registry_password:
        config.schema_registry.password = registry_password
    if include_subjects:
        config.schema_registry.include_subjects = list(include_subjects)
    if exclude_subjects:
        config.schema_registry.exclude_subjects = list(exclude_subjects)
    if github_token:
        config.github.token = github_token
    if github_repo:
        config.github.repo = github_repo
    if provider:
        config.llm.default_provider = provider
    if min_confidence:
        config.llm.min_confidence = min_confidence  # type: ignore
    if base_branch:
        config.github.base_branch = base_branch
    if dry_run:
        config.output.dry_run = True

    # Validate required config
    if not config.schema_registry.url:
        console.print("[red]Error: Schema Registry URL required[/red]")
        console.print("Set via --registry-url or SCHEMA_REGISTRY_URL env var")
        sys.exit(1)
    if not config.output.dry_run and not config.github.is_configured():
        console.print("[red]Error: GitHub token and repo required (or use --dry-run)[/red]")
        sys.exit(1)

    _run_doc_bot(config, model)


@cli.command("run-from-repo")
@click.option("--github-token", envvar="GITHUB_TOKEN", help="GitHub PAT")
@click.option("--github-repo", envvar="GITHUB_REPO", help="GitHub repository (owner/repo)")
@click.option("--schema-path", help="Path to schemas in repo")
@click.option("--include", "-i", "include_patterns", multiple=True, help="File patterns to include (glob)")
@click.option("--exclude", "-e", "exclude_patterns", multiple=True, help="File patterns to exclude (glob)")
@click.option("--provider", "-p", help="LLM provider")
@click.option("--model", "-m", help="Model to use")
@click.option("--min-confidence", type=click.Choice(["high", "medium", "low"]), help="Minimum confidence")
@click.option("--base-branch", help="Base branch for PR")
@click.option("--dry-run", is_flag=True, help="Preview without making changes")
@click.pass_context
def run_from_repo(
    ctx: click.Context,
    github_token: str | None,
    github_repo: str | None,
    schema_path: str | None,
    include_patterns: tuple[str, ...],
    exclude_patterns: tuple[str, ...],
    provider: str | None,
    model: str | None,
    min_confidence: str | None,
    base_branch: str | None,
    dry_run: bool,
):
    """Run Schema Doc-Bot directly on schemas in a GitHub repository."""
    config: Config = ctx.obj["config"]
    
    # Apply CLI overrides
    if github_token:
        config.github.token = github_token
    if github_repo:
        config.github.repo = github_repo
    if schema_path:
        config.github.schema_path = schema_path
    if include_patterns:
        config.github.include_patterns = list(include_patterns)
    if exclude_patterns:
        config.github.exclude_patterns = list(exclude_patterns)
    if provider:
        config.llm.default_provider = provider
    if min_confidence:
        config.llm.min_confidence = min_confidence  # type: ignore
    if base_branch:
        config.github.base_branch = base_branch
    if dry_run:
        config.output.dry_run = True

    if not config.github.is_configured():
        console.print("[red]Error: GitHub token and repo required[/red]")
        sys.exit(1)

    _run_from_github(config, model)


@cli.command()
@click.option("--registry-url", envvar="SCHEMA_REGISTRY_URL", help="Schema Registry URL")
@click.option("--registry-user", envvar="SCHEMA_REGISTRY_USER", help="Registry username")
@click.option("--registry-password", envvar="SCHEMA_REGISTRY_PASSWORD", help="Registry password")
@click.option("--include", "-i", "include_subjects", multiple=True, help="Subject patterns to include (glob)")
@click.option("--exclude", "-e", "exclude_subjects", multiple=True, help="Subject patterns to exclude (glob)")
@click.pass_context
def analyze(
    ctx: click.Context,
    registry_url: str | None,
    registry_user: str | None,
    registry_password: str | None,
    include_subjects: tuple[str, ...],
    exclude_subjects: tuple[str, ...],
):
    """Analyze schemas and show documentation coverage report."""
    config: Config = ctx.obj["config"]
    
    if registry_url:
        config.schema_registry.url = registry_url
    if registry_user:
        config.schema_registry.username = registry_user
    if registry_password:
        config.schema_registry.password = registry_password
    if include_subjects:
        config.schema_registry.include_subjects = list(include_subjects)
    if exclude_subjects:
        config.schema_registry.exclude_subjects = list(exclude_subjects)

    if not config.schema_registry.url:
        console.print("[red]Error: Schema Registry URL required[/red]")
        sys.exit(1)

    console.print(
        Panel.fit(
            "[bold cyan]📊 Schema Documentation Analysis[/bold cyan]",
            border_style="cyan",
        )
    )

    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        console=console,
    ) as progress:
        task = progress.add_task("Connecting to Schema Registry...", total=None)
        registry = SchemaRegistryClient(
            config.schema_registry.url,
            config.schema_registry.username,
            config.schema_registry.password,
        )

        if not registry.check_connectivity():
            console.print("[red]Error: Cannot connect to Schema Registry[/red]")
            sys.exit(1)
        progress.update(task, completed=True)

        task = progress.add_task("Fetching and analyzing schemas...", total=None)
        schemas = registry.get_all_schemas(
            schema_type=None,
            include_subjects=config.schema_registry.include_subjects or None,
            exclude_subjects=config.schema_registry.exclude_subjects or None,
        )
        
        from .json_schema_analyzer import JsonSchemaAnalyzer
        avro_analyzer = AvroAnalyzer()
        json_analyzer = JsonSchemaAnalyzer()

        results: list[AnalysisResult] = []
        for schema_info in schemas:
            if schema_info.schema_type.upper() == "JSON":
                result = json_analyzer.analyze_schema(schema_info.subject, schema_info.schema)
            else:
                result = avro_analyzer.analyze_schema(schema_info.subject, schema_info.schema)
            results.append(result)

        progress.update(task, completed=True)

    _display_full_analysis(results)


@cli.command()
@click.argument("paths", nargs=-1, type=click.Path(exists=True, path_type=Path))
@click.option("--provider", "-p", help="LLM provider")
@click.option("--model", "-m", help="Model to use")
@click.option("--min-confidence", type=click.Choice(["high", "medium", "low"]), help="Minimum confidence")
@click.option("--output", "-o", type=click.Path(path_type=Path), help="Output directory")
@click.pass_context
def local(
    ctx: click.Context,
    paths: tuple[Path, ...],
    provider: str | None,
    model: str | None,
    min_confidence: str | None,
    output: Path | None,
):
    """Run on local .avsc files without GitHub integration."""
    from .local_runner import run_local

    config: Config = ctx.obj["config"]
    
    if provider:
        config.llm.default_provider = provider
    if min_confidence:
        config.llm.min_confidence = min_confidence  # type: ignore

    if not paths:
        console.print("[yellow]No paths specified. Usage: schema-doc-bot local path/to/schemas[/yellow]")
        return

    # Get the provider config
    provider_name = config.llm.default_provider
    provider_config = config.llm.providers.get(provider_name, LLMProviderConfig())
    
    if model:
        provider_config.model = model

    if provider_name not in ("ollama",) and not provider_config.api_key:
        console.print(f"[red]Error: API key required for {provider_name}[/red]")
        sys.exit(1)

    run_local(
        schema_paths=list(paths),
        llm_provider=provider_name,  # type: ignore
        api_key=provider_config.api_key,
        model=provider_config.model,
        min_confidence=config.llm.min_confidence,
        output_dir=output,
    )


@cli.command()
@click.option("--registry-url", envvar="SCHEMA_REGISTRY_URL", help="Schema Registry URL")
@click.option("--registry-user", envvar="SCHEMA_REGISTRY_USER", help="Registry username")
@click.option("--registry-password", envvar="SCHEMA_REGISTRY_PASSWORD", help="Registry password")
@click.option("--include", "-i", "include_subjects", multiple=True, help="Subject patterns to include")
@click.option("--exclude", "-e", "exclude_subjects", multiple=True, help="Subject patterns to exclude")
@click.option("--provider", "-p", help="LLM provider")
@click.option("--model", "-m", help="Model to use")
@click.option("--dry-run", is_flag=True, help="Preview without making changes")
@click.option("--verbose", "-v", is_flag=True, help="Show detailed progress")
@click.pass_context
def agent(
    ctx: click.Context,
    registry_url: str | None,
    registry_user: str | None,
    registry_password: str | None,
    include_subjects: tuple[str, ...],
    exclude_subjects: tuple[str, ...],
    provider: str | None,
    model: str | None,
    dry_run: bool,
    verbose: bool,
):
    """
    Run the Schema Documentation Agent (recommended).
    
    The agent provides:
    - Planning: Analyzes workload and estimates time
    - Multi-format: Supports Avro, JSON Schema, and Protobuf  
    - Self-review: Evaluates and refines generated documentation
    - Error recovery: Handles failures gracefully
    """
    from .agent import SchemaDocumentationAgent
    
    config: Config = ctx.obj["config"]
    
    # Apply CLI overrides
    if registry_url:
        config.schema_registry.url = registry_url
    if registry_user:
        config.schema_registry.username = registry_user
    if registry_password:
        config.schema_registry.password = registry_password
    if include_subjects:
        config.schema_registry.include_subjects = list(include_subjects)
    if exclude_subjects:
        config.schema_registry.exclude_subjects = list(exclude_subjects)
    if provider:
        config.llm.default_provider = provider
    if model:
        provider_name = config.llm.default_provider
        if provider_name not in config.llm.providers:
            config.llm.providers[provider_name] = LLMProviderConfig()
        config.llm.providers[provider_name].model = model
    if dry_run:
        config.output.dry_run = True

    # Validate
    if not config.schema_registry.url:
        console.print("[red]Error: Schema Registry URL required[/red]")
        sys.exit(1)

    # Initialize registry client
    registry = SchemaRegistryClient(
        config.schema_registry.url,
        config.schema_registry.username,
        config.schema_registry.password,
    )
    
    if not registry.check_connectivity():
        console.print("[red]Error: Cannot connect to Schema Registry[/red]")
        sys.exit(1)

    # Run the agent
    doc_agent = SchemaDocumentationAgent(config)
    updates = doc_agent.run(
        registry=registry,
        include_subjects=config.schema_registry.include_subjects or None,
        exclude_subjects=config.schema_registry.exclude_subjects or None,
        dry_run=config.output.dry_run,
        verbose=verbose,
    )

    # Create PR if not dry run and we have updates
    if updates and not config.output.dry_run:
        if config.github.is_configured():
            console.print("\n[bold]Creating PR...[/bold]")
            github = GitHubClient(config.github.token, config.github.repo)
            pr_url = github.create_documentation_pr(updates, config.github.base_branch)
            if pr_url:
                console.print(f"[green]✓ PR created: {pr_url}[/green]")
        else:
            console.print("[yellow]GitHub not configured. Skipping PR creation.[/yellow]")


# ============================================================================
# Helper Functions (Legacy - use 'agent' command instead)
# ============================================================================


def _run_doc_bot(config: Config, model_override: str | None = None) -> None:
    """Main flow: Registry → Analyze → Generate → PR."""
    console.print(
        Panel.fit(
            "[bold cyan]🤖 Schema Documentation Agent[/bold cyan]\n"
            "Automatically documenting your schemas",
            border_style="cyan",
        )
    )

    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        console=console,
    ) as progress:
        # Connect to registry
        task = progress.add_task("Connecting to Schema Registry...", total=None)
        registry = SchemaRegistryClient(
            config.schema_registry.url,
            config.schema_registry.username,
            config.schema_registry.password,
        )

        if not registry.check_connectivity():
            console.print("[red]Error: Cannot connect to Schema Registry[/red]")
            sys.exit(1)
        progress.update(task, completed=True)

        # Fetch schemas (with filtering) - supports both AVRO and JSON
        task = progress.add_task("Fetching schemas...", total=None)
        schemas = registry.get_all_schemas(
            schema_type=None,  # Fetch all types (AVRO, JSON, etc.)
            include_subjects=config.schema_registry.include_subjects or None,
            exclude_subjects=config.schema_registry.exclude_subjects or None,
        )
        progress.update(task, completed=True)
        
        filter_msg = ""
        if config.schema_registry.include_subjects:
            filter_msg += f" (include: {', '.join(config.schema_registry.include_subjects)})"
        if config.schema_registry.exclude_subjects:
            filter_msg += f" (exclude: {', '.join(config.schema_registry.exclude_subjects)})"
        console.print(f"Found [green]{len(schemas)}[/green] schemas{filter_msg}")

        if not schemas:
            console.print("[yellow]No schemas found. Exiting.[/yellow]")
            return

        # Analyze (auto-detect AVRO vs JSON Schema)
        task = progress.add_task("Analyzing schemas for missing docs...", total=None)
        from .json_schema_analyzer import JsonSchemaAnalyzer
        avro_analyzer = AvroAnalyzer()
        json_analyzer = JsonSchemaAnalyzer()
        analysis_results: list[AnalysisResult] = []

        for schema_info in schemas:
            # Choose analyzer based on schema type
            schema_type_str = schema_info.schema_type.upper()
            
            if schema_type_str == "JSON":
                result = json_analyzer.analyze_schema(schema_info.subject, schema_info.schema)
            else:
                result = avro_analyzer.analyze_schema(schema_info.subject, schema_info.schema)
            
            if result.missing_docs:
                analysis_results.append(result)

        progress.update(task, completed=True)

    _display_analysis_summary(analysis_results)

    if not analysis_results:
        console.print("\n[green]✓ All schemas are fully documented![/green]")
        return

    total_missing = sum(len(r.missing_docs) for r in analysis_results)
    console.print(
        f"\n[yellow]Found {total_missing} undocumented elements "
        f"across {len(analysis_results)} schemas[/yellow]"
    )

    if not config.output.dry_run and not click.confirm("\nProceed with generating documentation?"):
        return

    # Generate documentation
    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        console=console,
    ) as progress:
        task = progress.add_task("Generating documentation with AI...", total=None)

        provider_name = config.llm.default_provider
        provider_config = config.llm.providers.get(provider_name, LLMProviderConfig())
        if model_override:
            provider_config.model = model_override

        try:
            llm_client = create_llm_client(provider_name, config.llm, provider_config)
        except ValueError as e:
            console.print(f"[red]Error: {e}[/red]")
            sys.exit(1)

        # Track schema type along with results
        all_generated: list[tuple[AnalysisResult, list[GeneratedDoc], str]] = []

        for result in analysis_results:
            # Detect schema type from structure
            schema_type = "JSON" if result.schema.get("type") == "object" and "properties" in result.schema else "AVRO"
            
            schema_context = {
                "name": result.schema.get("name") or result.subject,
                "doc": result.schema.get("doc") or result.schema.get("description"),
                "namespace": result.schema.get("namespace"),
            }
            generated = llm_client.generate_documentation(result.missing_docs, schema_context)
            all_generated.append((result, generated, schema_type))

        progress.update(task, completed=True)

    # Apply documentation
    console.print("\n[bold]Generated Documentation:[/bold]")
    from .json_schema_updater import JsonSchemaUpdater
    avro_updater = SchemaUpdater()
    json_updater = JsonSchemaUpdater()
    schema_updates: list[SchemaUpdate] = []

    for result, generated, schema_type in all_generated:
        if generated:
            ext = ".json" if schema_type == "JSON" else ".avsc"
            file_path = f"schemas/{result.subject.replace('-', '/')}{ext}"
            
            # Use appropriate updater
            if schema_type == "JSON":
                update = json_updater.apply_documentation(
                    result.schema, generated, file_path, config.llm.min_confidence,
                    subject=result.subject
                )
            else:
                update = avro_updater.apply_documentation(
                    result.schema, generated, file_path, config.llm.min_confidence
                )
            
            if update:
                schema_updates.append(update)
                _display_generated_docs(result.subject, generated)

    if not schema_updates:
        console.print("[yellow]No documentation met the confidence threshold.[/yellow]")
        return

    # Create PR
    console.print(f"\n[bold]Creating PR with {len(schema_updates)} schema updates...[/bold]")

    if config.output.dry_run:
        import json
        console.print("\n[yellow]DRY RUN - No changes will be made[/yellow]")
        for update in schema_updates:
            console.print(f"\n[bold cyan]Updated Schema: {update.file_path}[/bold cyan]")
            console.print(f"[dim]Changes: {len(update.changes_summary)} fields documented[/dim]")
            for change in update.changes_summary:
                console.print(f"  [green]✓[/green] {change}")
            console.print()
            # Pretty print the full updated schema
            schema_json = json.dumps(update.updated_schema, indent=2)
            console.print(schema_json)
        return

    github = GitHubClient(config.github.token, config.github.repo)
    pr_url = github.create_documentation_pr(
        schema_updates, config.github.base_branch, config.output.dry_run
    )

    if pr_url:
        console.print(f"\n[green]✓ PR created successfully![/green]")
        console.print(f"  [link={pr_url}]{pr_url}[/link]")


def _run_from_github(config: Config, model_override: str | None = None) -> None:
    """Run from GitHub repository directly."""
    console.print(
        Panel.fit(
            "[bold cyan]🤖 Schema Doc-Bot (Repository Mode)[/bold cyan]\n"
            "Documenting schemas directly from GitHub",
            border_style="cyan",
        )
    )

    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        console=console,
    ) as progress:
        task = progress.add_task("Connecting to GitHub...", total=None)
        github = GitHubClient(config.github.token, config.github.repo)
        progress.update(task, completed=True)

        task = progress.add_task("Finding schema files...", total=None)
        schema_files = github.find_schema_files(
            config.github.schema_path,
            config.github.file_extension,
            include_patterns=config.github.include_patterns or None,
            exclude_patterns=config.github.exclude_patterns or None,
        )
        progress.update(task, completed=True)

        filter_msg = ""
        if config.github.include_patterns:
            filter_msg += f" (include: {', '.join(config.github.include_patterns)})"
        if config.github.exclude_patterns:
            filter_msg += f" (exclude: {', '.join(config.github.exclude_patterns)})"
        console.print(f"Found [green]{len(schema_files)}[/green] schema files{filter_msg}")

        if not schema_files:
            console.print("[yellow]No schema files found. Exiting.[/yellow]")
            return

        task = progress.add_task("Analyzing schemas...", total=None)
        analyzer = AvroAnalyzer()
        schemas_to_process: list[tuple[str, dict, AnalysisResult]] = []

        for file_path, schema in schema_files:
            result = analyzer.analyze_schema(file_path, schema)
            if result.missing_docs:
                schemas_to_process.append((file_path, schema, result))

        progress.update(task, completed=True)

    if not schemas_to_process:
        console.print("\n[green]✓ All schemas are fully documented![/green]")
        return

    total_missing = sum(len(r.missing_docs) for _, _, r in schemas_to_process)
    console.print(
        f"\n[yellow]Found {total_missing} undocumented elements "
        f"across {len(schemas_to_process)} schemas[/yellow]"
    )

    if not config.output.dry_run and not click.confirm("\nProceed with generating documentation?"):
        return

    # Generate
    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        console=console,
    ) as progress:
        task = progress.add_task("Generating documentation with AI...", total=None)

        provider_name = config.llm.default_provider
        provider_config = config.llm.providers.get(provider_name, LLMProviderConfig())
        if model_override:
            provider_config.model = model_override

        try:
            llm_client = create_llm_client(provider_name, config.llm, provider_config)
        except ValueError as e:
            console.print(f"[red]Error: {e}[/red]")
            sys.exit(1)

        updater = SchemaUpdater()
        schema_updates: list[SchemaUpdate] = []

        for file_path, schema, result in schemas_to_process:
            schema_context = {
                "name": schema.get("name"),
                "doc": schema.get("doc"),
                "namespace": schema.get("namespace"),
            }
            generated = llm_client.generate_documentation(result.missing_docs, schema_context)

            if generated:
                update = updater.apply_documentation(
                    schema, generated, file_path, config.llm.min_confidence
                )
                if update:
                    schema_updates.append(update)
                    _display_generated_docs(file_path, generated)

        progress.update(task, completed=True)

    if not schema_updates:
        console.print("[yellow]No documentation met the confidence threshold.[/yellow]")
        return

    console.print(f"\n[bold]Creating PR with {len(schema_updates)} schema updates...[/bold]")

    pr_url = github.create_documentation_pr(
        schema_updates, config.github.base_branch, config.output.dry_run
    )

    if pr_url:
        console.print(f"\n[green]✓ PR created successfully![/green]")
        console.print(f"  [link={pr_url}]{pr_url}[/link]")
    elif config.output.dry_run:
        console.print("\n[yellow]DRY RUN completed - no changes made[/yellow]")


def _display_analysis_summary(results: list[AnalysisResult]) -> None:
    """Display a summary table of analysis results."""
    if not results:
        return

    table = Table(title="Schemas Needing Documentation")
    table.add_column("Schema", style="cyan")
    table.add_column("Missing", justify="right", style="red")
    table.add_column("Coverage", justify="right")

    for result in results[:20]:
        coverage = f"{result.coverage_percent:.0f}%"
        coverage_style = (
            "green"
            if result.coverage_percent >= 80
            else "yellow" if result.coverage_percent >= 50 else "red"
        )
        table.add_row(
            result.subject,
            str(len(result.missing_docs)),
            f"[{coverage_style}]{coverage}[/{coverage_style}]",
        )

    if len(results) > 20:
        table.add_row("...", f"+{len(results) - 20} more", "")

    console.print(table)


def _display_full_analysis(results: list[AnalysisResult]) -> None:
    """Display full analysis with coverage breakdown."""
    total_elements = sum(r.total_elements for r in results)
    documented = sum(r.documented_elements for r in results)
    overall_coverage = (documented / total_elements * 100) if total_elements else 100

    console.print(f"\n[bold]Overall Documentation Coverage: {overall_coverage:.1f}%[/bold]")
    console.print(f"Total elements: {total_elements}, Documented: {documented}\n")

    table = Table(title="Coverage by Schema")
    table.add_column("Schema", style="cyan")
    table.add_column("Total", justify="right")
    table.add_column("Documented", justify="right", style="green")
    table.add_column("Missing", justify="right", style="red")
    table.add_column("Coverage", justify="right")

    for result in sorted(results, key=lambda r: r.coverage_percent):
        coverage = f"{result.coverage_percent:.0f}%"
        coverage_style = (
            "green"
            if result.coverage_percent >= 80
            else "yellow" if result.coverage_percent >= 50 else "red"
        )
        table.add_row(
            result.subject,
            str(result.total_elements),
            str(result.documented_elements),
            str(len(result.missing_docs)),
            f"[{coverage_style}]{coverage}[/{coverage_style}]",
        )

    console.print(table)


def _display_generated_docs(subject: str, docs: list[GeneratedDoc]) -> None:
    """Display generated documentation for a schema."""
    console.print(f"\n[bold cyan]{subject}[/bold cyan]")
    for doc in docs[:5]:
        conf_color = {"high": "green", "medium": "yellow", "low": "red"}.get(
            doc.confidence, "white"
        )
        truncated = doc.documentation[:60] + "..." if len(doc.documentation) > 60 else doc.documentation
        console.print(
            f"  • {doc.path}: {truncated} "
            f"[{conf_color}][{doc.confidence}][/{conf_color}]"
        )
    if len(docs) > 5:
        console.print(f"  ... and {len(docs) - 5} more")


def main():
    """Entry point for the CLI."""
    cli()


if __name__ == "__main__":
    main()
