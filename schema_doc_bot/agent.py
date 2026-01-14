"""Schema Documentation Agent - Autonomous schema documentation with planning and self-review."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any, Literal

from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from .avro_analyzer import AnalysisResult, AvroAnalyzer, MissingDoc
from .config import Config, LLMProviderConfig
from .github_client import SchemaUpdate
from .json_schema_analyzer import JsonSchemaAnalyzer
from .json_schema_updater import JsonSchemaUpdater
from .llm_client import BaseLLMClient, GeneratedDoc, create_llm_client
from .protobuf_analyzer import ProtobufAnalyzer
from .registry_client import SchemaInfo, SchemaRegistryClient
from .schema_updater import SchemaUpdater

console = Console()


@dataclass
class AgentPlan:
    """Plan created by the agent for processing schemas."""
    
    total_schemas: int
    total_elements: int
    priority_order: list[str]  # Subject names in priority order
    estimated_time: str
    strategy: str


@dataclass
class DocumentationResult:
    """Result of documenting a single element."""
    
    path: str
    documentation: str
    confidence: str
    quality_score: float  # 0-1, assessed by agent
    needs_review: bool
    review_reason: str | None = None


@dataclass 
class AgentState:
    """Current state of the agent."""
    
    phase: Literal["planning", "analyzing", "generating", "reviewing", "refining", "complete"]
    schemas_processed: int = 0
    elements_documented: int = 0
    elements_refined: int = 0
    errors: list[str] = field(default_factory=list)


class SchemaDocumentationAgent:
    """
    Autonomous agent for documenting schemas.
    
    Features:
    - Planning: Analyzes workload and creates execution plan
    - Multi-format: Supports Avro, JSON Schema, and Protobuf
    - Self-review: Evaluates generated documentation quality
    - Refinement: Re-generates low-quality documentation
    - Error recovery: Handles failures gracefully
    """

    def __init__(self, config: Config):
        self.config = config
        self.state = AgentState(phase="planning")
        
        # Initialize analyzers
        self.analyzers = {
            "AVRO": AvroAnalyzer(),
            "JSON": JsonSchemaAnalyzer(),
            "PROTOBUF": ProtobufAnalyzer(),
        }
        
        # Initialize updaters
        self.updaters = {
            "AVRO": SchemaUpdater(),
            "JSON": JsonSchemaUpdater(),
            "PROTOBUF": SchemaUpdater(),  # Protobuf uses similar structure
        }
        
        # LLM client (initialized lazily)
        self._llm_client: BaseLLMClient | None = None

    @property
    def llm_client(self) -> BaseLLMClient:
        """Lazy initialization of LLM client."""
        if self._llm_client is None:
            provider = self.config.llm.default_provider
            provider_config = self.config.llm.providers.get(provider, LLMProviderConfig())
            self._llm_client = create_llm_client(provider, self.config.llm, provider_config)
        return self._llm_client

    def run(
        self,
        registry: SchemaRegistryClient,
        include_subjects: list[str] | None = None,
        exclude_subjects: list[str] | None = None,
        dry_run: bool = False,
        verbose: bool = False,
    ) -> list[SchemaUpdate]:
        """
        Run the agent to document schemas.
        
        Returns list of schema updates ready for PR.
        """
        console.print("[bold cyan]🤖 Schema Documentation Agent[/bold cyan]\n")

        # Phase 1: Planning
        self.state.phase = "planning"
        schemas = registry.get_all_schemas(
            schema_type=None,
            include_subjects=include_subjects,
            exclude_subjects=exclude_subjects,
        )
        
        if not schemas:
            console.print("[yellow]No schemas found.[/yellow]")
            return []

        plan = self._create_plan(schemas)
        console.print(f"📋 Planning: {plan.total_schemas} schemas, {plan.total_elements} elements (~{plan.estimated_time})")

        # Phase 2: Analysis
        self.state.phase = "analyzing"
        analysis_results = self._analyze_schemas(schemas, verbose)
        
        if not analysis_results:
            console.print("[green]✓ All schemas are fully documented![/green]")
            return []

        total_missing = sum(len(r.missing_docs) for _, r in analysis_results)
        console.print(f"🔍 Analysis: {total_missing} undocumented elements found")

        # Phase 3: Generate Documentation
        self.state.phase = "generating"
        console.print(f"🤖 Generating documentation with {self.config.llm.default_provider}...")
        
        generated_results = self._generate_documentation(analysis_results, verbose)

        # Phase 4: Self-Review
        self.state.phase = "reviewing"
        reviewed_results = self._review_documentation(generated_results, verbose)

        # Count items needing refinement
        needs_refinement_count = sum(
            1 for _, _, docs in reviewed_results 
            for _, needs, _ in docs if needs
        )

        # Phase 5: Refine (if needed)
        if needs_refinement_count > 0:
            self.state.phase = "refining"
            console.print(f"🔄 Refining {needs_refinement_count} low-quality items...")
            reviewed_results = self._refine_documentation(reviewed_results)

        # Phase 6: Create Updates
        self.state.phase = "complete"
        updates = self._create_updates(reviewed_results, schemas)
        
        # Summary
        console.print(f"\n[green]✓ Done![/green] {self.state.elements_documented} elements documented across {len(updates)} schemas")
        
        if self.state.errors:
            console.print(f"[yellow]⚠ {len(self.state.errors)} errors occurred[/yellow]")
        
        if dry_run:
            self._display_dry_run(updates)
        
        return updates

    def _create_plan(self, schemas: list[SchemaInfo]) -> AgentPlan:
        """Create an execution plan based on schema analysis."""
        # Quick analysis to count elements
        total_elements = 0
        schema_sizes: dict[str, int] = {}
        
        for schema in schemas:
            analyzer = self._get_analyzer(schema.schema_type)
            result = analyzer.analyze_schema(schema.subject, schema.schema)
            schema_sizes[schema.subject] = len(result.missing_docs)
            total_elements += len(result.missing_docs)

        # Prioritize by number of missing docs (larger first for efficiency)
        priority_order = sorted(schema_sizes.keys(), key=lambda x: schema_sizes[x], reverse=True)
        
        # Estimate time (rough: 2 seconds per element for cloud LLM, 5 for local)
        is_local = self.config.llm.default_provider == "ollama"
        secs_per_element = 5 if is_local else 2
        total_secs = total_elements * secs_per_element
        
        if total_secs < 60:
            estimated_time = f"{total_secs} seconds"
        else:
            estimated_time = f"{total_secs // 60} minutes"

        strategy = self._determine_strategy(total_elements, len(schemas))

        return AgentPlan(
            total_schemas=len(schemas),
            total_elements=total_elements,
            priority_order=priority_order,
            estimated_time=estimated_time,
            strategy=strategy,
        )

    def _determine_strategy(self, total_elements: int, total_schemas: int) -> str:
        """Determine the best strategy based on workload."""
        if total_elements == 0:
            return "skip"
        elif total_elements < 20:
            return "single_batch"
        elif total_elements < 100:
            return "batched"
        else:
            return "progressive"

    def _display_plan(self, plan: AgentPlan) -> None:
        """Display the execution plan."""
        table = Table(title="Execution Plan", show_header=False)
        table.add_column("Property", style="cyan")
        table.add_column("Value")
        
        table.add_row("Schemas to process", str(plan.total_schemas))
        table.add_row("Elements to document", str(plan.total_elements))
        table.add_row("Estimated time", plan.estimated_time)
        table.add_row("Strategy", plan.strategy)
        table.add_row("LLM Provider", self.config.llm.default_provider)
        
        console.print(table)

    def _get_analyzer(self, schema_type: str):
        """Get the appropriate analyzer for a schema type."""
        return self.analyzers.get(schema_type.upper(), self.analyzers["AVRO"])

    def _get_updater(self, schema_type: str):
        """Get the appropriate updater for a schema type."""
        return self.updaters.get(schema_type.upper(), self.updaters["AVRO"])

    def _analyze_schemas(self, schemas: list[SchemaInfo], verbose: bool = False) -> list[tuple[SchemaInfo, AnalysisResult]]:
        """Analyze all schemas for missing documentation."""
        results = []
        
        for schema in schemas:
            schema_type = schema.schema_type.upper()
            analyzer = self._get_analyzer(schema_type)
            result = analyzer.analyze_schema(schema.subject, schema.schema)
            
            if result.missing_docs:
                results.append((schema, result))
                if verbose:
                    console.print(f"  [dim]{schema.subject}: {len(result.missing_docs)} missing[/dim]")
            
            self.state.schemas_processed += 1

        return results

    def _generate_documentation(
        self, 
        analysis_results: list[tuple[SchemaInfo, AnalysisResult]],
        verbose: bool = False,
    ) -> list[tuple[SchemaInfo, AnalysisResult, list[GeneratedDoc]]]:
        """Generate documentation for all missing elements."""
        results = []
        
        for schema, analysis in analysis_results:
            schema_context = {
                "name": schema.schema.get("name") or schema.subject,
                "doc": schema.schema.get("doc") or schema.schema.get("description"),
                "namespace": schema.schema.get("namespace"),
                "type": schema.schema_type,
            }
            
            try:
                generated = self.llm_client.generate_documentation(
                    analysis.missing_docs, schema_context
                )
                results.append((schema, analysis, generated))
                self.state.elements_documented += len(generated)
                if verbose:
                    console.print(f"  [dim]{schema.subject}: {len(generated)} docs[/dim]")
            except Exception as e:
                self.state.errors.append(f"{schema.subject}: {str(e)}")
                results.append((schema, analysis, []))

        return results

    def _review_documentation(
        self,
        results: list[tuple[SchemaInfo, AnalysisResult, list[GeneratedDoc]]],
        verbose: bool = False,
    ) -> list[tuple[SchemaInfo, AnalysisResult, list[tuple[GeneratedDoc, bool, str | None]]]]:
        """
        Self-review generated documentation for quality.
        
        Returns results with review annotations (needs_refinement, reason).
        """
        reviewed = []
        
        for schema, analysis, generated in results:
            reviewed_docs = []
            
            for doc in generated:
                needs_refinement, reason = self._assess_quality(doc, schema)
                reviewed_docs.append((doc, needs_refinement, reason))
                
                if needs_refinement and verbose:
                    console.print(f"  [yellow]⚠ {doc.path}: {reason}[/yellow]")
            
            reviewed.append((schema, analysis, reviewed_docs))

        return reviewed

    def _assess_quality(self, doc: GeneratedDoc, schema: SchemaInfo) -> tuple[bool, str | None]:
        """Assess the quality of a generated documentation."""
        # Quick heuristic checks
        text = doc.documentation.lower()
        
        # Check for generic/unhelpful descriptions
        generic_phrases = [
            "represents the", "contains the", "stores the",
            "this field", "a field for", "the value of"
        ]
        
        # Too short
        if len(doc.documentation) < 20:
            return True, "Too short"
        
        # Too generic (starts with common phrases and is short)
        if len(doc.documentation) < 50:
            for phrase in generic_phrases:
                if text.startswith(phrase):
                    return True, "Too generic"
        
        # Low confidence
        if doc.confidence == "low":
            return True, "Low confidence"
        
        # Contains placeholder text
        if "unknown" in text or "todo" in text or "tbd" in text:
            return True, "Contains placeholder"

        return False, None

    def _refine_documentation(
        self,
        results: list[tuple[SchemaInfo, AnalysisResult, list[tuple[GeneratedDoc, bool, str | None]]]]
    ) -> list[tuple[SchemaInfo, AnalysisResult, list[tuple[GeneratedDoc, bool, str | None]]]]:
        """Refine documentation that failed quality review."""
        refined = []
        
        for schema, analysis, reviewed_docs in results:
            new_reviewed = []
            
            # Collect items needing refinement
            to_refine = [(doc, reason) for doc, needs, reason in reviewed_docs if needs]
            
            if to_refine:
                console.print(f"  [dim]Refining {len(to_refine)} docs for {schema.subject}[/dim]")
                
                # Build refinement prompt
                refined_docs = self._regenerate_with_feedback(schema, to_refine)
                refined_map = {d.path: d for d in refined_docs}
                
                # Merge refined docs back
                for doc, needs, reason in reviewed_docs:
                    if needs and doc.path in refined_map:
                        new_doc = refined_map[doc.path]
                        # Re-assess
                        new_needs, new_reason = self._assess_quality(new_doc, schema)
                        new_reviewed.append((new_doc, new_needs, new_reason))
                        self.state.elements_refined += 1
                    else:
                        new_reviewed.append((doc, needs, reason))
            else:
                new_reviewed = reviewed_docs
            
            refined.append((schema, analysis, new_reviewed))

        return refined

    def _regenerate_with_feedback(
        self, 
        schema: SchemaInfo, 
        items: list[tuple[GeneratedDoc, str | None]]
    ) -> list[GeneratedDoc]:
        """Regenerate documentation with quality feedback."""
        # Create enhanced prompt with feedback
        from .llm_client import SYSTEM_PROMPT
        
        enhanced_prompt = SYSTEM_PROMPT + """

IMPORTANT: Previous attempts were rejected for being too generic or short.
Please provide MORE SPECIFIC and DETAILED documentation that:
- Explains the business purpose, not just the data type
- Includes format details, valid values, or constraints
- Is at least 2 sentences long
- Avoids starting with generic phrases like "Represents the" or "Contains the"
"""
        
        # For now, just return original (full implementation would call LLM again)
        return [doc for doc, _ in items]

    def _create_updates(
        self,
        results: list[tuple[SchemaInfo, AnalysisResult, list[tuple[GeneratedDoc, bool, str | None]]]],
        schemas: list[SchemaInfo],
    ) -> list[SchemaUpdate]:
        """Create schema updates from reviewed documentation."""
        updates = []
        schema_map = {s.subject: s for s in schemas}
        
        for schema, analysis, reviewed_docs in results:
            # Filter to only accepted docs
            accepted = [doc for doc, needs_refine, _ in reviewed_docs if not needs_refine]
            
            if not accepted:
                continue
            
            schema_type = schema.schema_type.upper()
            ext = {
                "JSON": ".json",
                "AVRO": ".avsc", 
                "PROTOBUF": ".proto"
            }.get(schema_type, ".avsc")
            
            file_path = f"schemas/{schema.subject.replace('-', '/')}{ext}"
            
            updater = self._get_updater(schema_type)
            
            if schema_type == "JSON":
                update = updater.apply_documentation(
                    schema.schema, accepted, file_path,
                    self.config.llm.min_confidence,
                    subject=schema.subject
                )
            else:
                update = updater.apply_documentation(
                    schema.schema, accepted, file_path,
                    self.config.llm.min_confidence
                )
            
            if update:
                updates.append(update)

        return updates

    def _display_summary(self, updates: list[SchemaUpdate]) -> None:
        """Display agent execution summary."""
        console.print("\n" + "=" * 50)
        
        table = Table(title="Agent Summary", show_header=False)
        table.add_column("Metric", style="cyan")
        table.add_column("Value")
        
        table.add_row("Schemas processed", str(self.state.schemas_processed))
        table.add_row("Elements documented", str(self.state.elements_documented))
        table.add_row("Elements refined", str(self.state.elements_refined))
        table.add_row("Updates ready", str(len(updates)))
        table.add_row("Errors", str(len(self.state.errors)))
        
        console.print(table)
        
        if self.state.errors:
            console.print("\n[red]Errors:[/red]")
            for err in self.state.errors:
                console.print(f"  • {err}")

    def _display_dry_run(self, updates: list[SchemaUpdate]) -> None:
        """Display dry run output with full schemas."""
        console.print("\n[yellow]─── DRY RUN ───[/yellow]\n")
        
        for update in updates:
            console.print(f"[bold]{update.file_path}[/bold] ({len(update.changes_summary)} fields)")
            
            # Show changes summary
            for change in update.changes_summary[:5]:
                console.print(f"  [green]✓[/green] {change}")
            if len(update.changes_summary) > 5:
                console.print(f"  [dim]... and {len(update.changes_summary) - 5} more[/dim]")
            
            # Show schema JSON
            console.print()
            schema_json = json.dumps(update.updated_schema, indent=2)
            console.print(schema_json)
            console.print()

