"""Module for applying generated documentation to JSON Schemas."""

from __future__ import annotations

import copy
from typing import Any

from .github_client import SchemaUpdate
from .llm_client import GeneratedDoc


class JsonSchemaUpdater:
    """Applies generated documentation to JSON Schemas."""

    def apply_documentation(
        self,
        schema: dict[str, Any],
        generated_docs: list[GeneratedDoc],
        file_path: str,
        min_confidence: str = "low",
        subject: str | None = None,
    ) -> SchemaUpdate | None:
        """
        Apply generated documentation to a JSON Schema.

        Args:
            schema: The original JSON Schema
            generated_docs: List of generated documentation
            file_path: Path to the schema file
            min_confidence: Minimum confidence level to apply
            subject: Schema subject name (for path matching)

        Returns:
            SchemaUpdate if changes were made, None otherwise
        """
        confidence_levels = {"high": 3, "medium": 2, "low": 1}
        min_level = confidence_levels.get(min_confidence, 1)

        # Filter by confidence
        docs_to_apply = [
            doc
            for doc in generated_docs
            if confidence_levels.get(doc.confidence, 0) >= min_level
        ]

        if not docs_to_apply:
            return None

        # Create a deep copy to modify
        updated_schema = copy.deepcopy(schema)
        changes_summary = []

        # Build a lookup map for generated docs
        doc_map = {doc.path: doc for doc in docs_to_apply}

        # Use subject as base path (matches how analyzer creates paths)
        base_path = subject or file_path.split("/")[-1].replace(".json", "")
        self._apply_to_object(updated_schema, base_path, doc_map, changes_summary)

        if not changes_summary:
            return None

        return SchemaUpdate(
            file_path=file_path,
            original_schema=schema,
            updated_schema=updated_schema,
            changes_summary=changes_summary,
        )

    def _apply_to_object(
        self,
        obj: dict[str, Any],
        path: str,
        doc_map: dict[str, GeneratedDoc],
        changes_summary: list[str],
    ) -> None:
        """Apply documentation to an object schema."""
        # Apply to root object if missing and we have a generated doc
        if not obj.get("description") and path in doc_map:
            gen_doc = doc_map[path]
            obj["description"] = gen_doc.documentation
            changes_summary.append(
                f"Added description to object `{path}` [{gen_doc.confidence}]"
            )

        # Apply to properties
        properties = obj.get("properties", {})
        for prop_name, prop_schema in properties.items():
            prop_path = f"{path}.{prop_name}"

            if not prop_schema.get("description") and prop_path in doc_map:
                gen_doc = doc_map[prop_path]
                prop_schema["description"] = gen_doc.documentation
                changes_summary.append(
                    f"Added description to property `{prop_name}` [{gen_doc.confidence}]"
                )

            # Handle nested objects
            if prop_schema.get("type") == "object":
                self._apply_to_object(prop_schema, prop_path, doc_map, changes_summary)
            elif prop_schema.get("type") == "array":
                items = prop_schema.get("items", {})
                if items.get("type") == "object":
                    self._apply_to_object(items, f"{prop_path}[]", doc_map, changes_summary)

