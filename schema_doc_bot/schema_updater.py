"""Module for applying generated documentation to Avro schemas."""

from __future__ import annotations

import copy
from typing import Any

from .github_client import SchemaUpdate
from .llm_client import GeneratedDoc


class SchemaUpdater:
    """Applies generated documentation to Avro schemas."""

    def apply_documentation(
        self,
        schema: dict[str, Any],
        generated_docs: list[GeneratedDoc],
        file_path: str,
        min_confidence: str = "low",
    ) -> SchemaUpdate | None:
        """
        Apply generated documentation to a schema.

        Args:
            schema: The original Avro schema
            generated_docs: List of generated documentation
            file_path: Path to the schema file
            min_confidence: Minimum confidence level to apply ("high", "medium", "low")

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

        # Apply documentation to the schema
        schema_name = schema.get("name", "unknown")
        self._apply_to_record(updated_schema, schema_name, doc_map, changes_summary)

        if not changes_summary:
            return None

        return SchemaUpdate(
            file_path=file_path,
            original_schema=schema,
            updated_schema=updated_schema,
            changes_summary=changes_summary,
        )

    def _apply_to_record(
        self,
        record: dict[str, Any],
        path_prefix: str,
        doc_map: dict[str, GeneratedDoc],
        changes_summary: list[str],
    ) -> None:
        """Recursively apply documentation to a record schema."""
        record_name = record.get("name", "unknown")
        record_path = path_prefix

        # Apply doc to record if missing and we have a generated doc
        if not record.get("doc") and record_path in doc_map:
            gen_doc = doc_map[record_path]
            record["doc"] = gen_doc.documentation
            changes_summary.append(
                f"Added doc to record `{record_name}` [{gen_doc.confidence}]"
            )

        # Apply docs to fields
        for field in record.get("fields", []):
            field_name = field.get("name", "unknown")
            field_path = f"{record_path}.{field_name}"

            if not field.get("doc") and field_path in doc_map:
                gen_doc = doc_map[field_path]
                field["doc"] = gen_doc.documentation
                changes_summary.append(
                    f"Added doc to field `{record_name}.{field_name}` [{gen_doc.confidence}]"
                )

            # Handle nested types
            self._apply_to_nested(
                field.get("type"), field_path, doc_map, changes_summary
            )

    def _apply_to_nested(
        self,
        avro_type: Any,
        path_prefix: str,
        doc_map: dict[str, GeneratedDoc],
        changes_summary: list[str],
    ) -> None:
        """Apply documentation to nested type definitions."""
        if isinstance(avro_type, dict):
            type_name = avro_type.get("type")

            if type_name == "record":
                nested_name = avro_type.get("name", "unknown")
                nested_path = f"{path_prefix}.{nested_name}"
                self._apply_to_record(avro_type, nested_path, doc_map, changes_summary)

            elif type_name == "enum":
                enum_name = avro_type.get("name", "unknown")
                enum_path = f"{path_prefix}.{enum_name}"
                if not avro_type.get("doc") and enum_path in doc_map:
                    gen_doc = doc_map[enum_path]
                    avro_type["doc"] = gen_doc.documentation
                    changes_summary.append(
                        f"Added doc to enum `{enum_name}` [{gen_doc.confidence}]"
                    )

            elif type_name == "array":
                self._apply_to_nested(
                    avro_type.get("items"), path_prefix, doc_map, changes_summary
                )

            elif type_name == "map":
                self._apply_to_nested(
                    avro_type.get("values"), path_prefix, doc_map, changes_summary
                )

        elif isinstance(avro_type, list):
            # Union type
            for variant in avro_type:
                self._apply_to_nested(variant, path_prefix, doc_map, changes_summary)

