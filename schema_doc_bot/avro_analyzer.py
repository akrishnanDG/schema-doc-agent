"""Analyzer for finding missing documentation in Avro schemas."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class MissingDoc:
    """Represents a schema element missing documentation."""

    path: str  # e.g., "UserEvent.user_id" or "UserEvent"
    element_type: str  # "record", "field", "enum"
    name: str
    avro_type: str | dict  # The Avro type definition
    parent_doc: str | None = None  # Parent record's doc if available
    context: dict[str, Any] = field(default_factory=dict)


@dataclass
class AnalysisResult:
    """Results from analyzing a schema for missing documentation."""

    subject: str
    schema: dict[str, Any]
    missing_docs: list[MissingDoc]
    total_elements: int
    documented_elements: int

    @property
    def coverage_percent(self) -> float:
        """Calculate documentation coverage percentage."""
        if self.total_elements == 0:
            return 100.0
        return (self.documented_elements / self.total_elements) * 100


class AvroAnalyzer:
    """Analyzes Avro schemas to find missing doc fields."""

    def analyze_schema(self, subject: str, schema: dict[str, Any]) -> AnalysisResult:
        """Analyze an Avro schema for missing documentation."""
        missing_docs: list[MissingDoc] = []
        total = 0
        documented = 0

        # Analyze based on schema type
        schema_type = schema.get("type")

        if schema_type == "record":
            t, d = self._analyze_record(schema, "", missing_docs)
            total += t
            documented += d
        elif schema_type == "enum":
            total += 1
            if schema.get("doc"):
                documented += 1
            else:
                missing_docs.append(
                    MissingDoc(
                        path=schema.get("name", "unknown"),
                        element_type="enum",
                        name=schema.get("name", "unknown"),
                        avro_type="enum",
                        context={"symbols": schema.get("symbols", [])},
                    )
                )

        return AnalysisResult(
            subject=subject,
            schema=schema,
            missing_docs=missing_docs,
            total_elements=total,
            documented_elements=documented,
        )

    def _analyze_record(
        self,
        record: dict[str, Any],
        path_prefix: str,
        missing_docs: list[MissingDoc],
    ) -> tuple[int, int]:
        """Recursively analyze a record schema."""
        total = 0
        documented = 0

        record_name = record.get("name", "unknown")
        record_path = f"{path_prefix}.{record_name}" if path_prefix else record_name
        record_doc = record.get("doc")

        # Count the record itself
        total += 1
        if record_doc:
            documented += 1
        else:
            missing_docs.append(
                MissingDoc(
                    path=record_path,
                    element_type="record",
                    name=record_name,
                    avro_type="record",
                    context={
                        "namespace": record.get("namespace"),
                        "fields": [f.get("name") for f in record.get("fields", [])],
                    },
                )
            )

        # Analyze fields
        for fld in record.get("fields", []):
            field_name = fld.get("name", "unknown")
            field_path = f"{record_path}.{field_name}"
            field_doc = fld.get("doc")
            field_type = fld.get("type")

            total += 1
            if field_doc:
                documented += 1
            else:
                missing_docs.append(
                    MissingDoc(
                        path=field_path,
                        element_type="field",
                        name=field_name,
                        avro_type=self._simplify_type(field_type),
                        parent_doc=record_doc,
                        context={
                            "record_name": record_name,
                            "default": fld.get("default"),
                            "full_type": field_type,
                        },
                    )
                )

            # Recursively analyze nested records
            nested_total, nested_documented = self._analyze_nested_types(
                field_type, field_path, missing_docs
            )
            total += nested_total
            documented += nested_documented

        return total, documented

    def _analyze_nested_types(
        self,
        avro_type: Any,
        path_prefix: str,
        missing_docs: list[MissingDoc],
    ) -> tuple[int, int]:
        """Analyze nested type definitions."""
        total = 0
        documented = 0

        if isinstance(avro_type, dict):
            type_name = avro_type.get("type")
            if type_name == "record":
                t, d = self._analyze_record(avro_type, path_prefix, missing_docs)
                total += t
                documented += d
            elif type_name == "array":
                t, d = self._analyze_nested_types(
                    avro_type.get("items"), path_prefix, missing_docs
                )
                total += t
                documented += d
            elif type_name == "map":
                t, d = self._analyze_nested_types(
                    avro_type.get("values"), path_prefix, missing_docs
                )
                total += t
                documented += d
            elif type_name == "enum":
                total += 1
                if avro_type.get("doc"):
                    documented += 1
                else:
                    enum_name = avro_type.get("name", "unknown")
                    missing_docs.append(
                        MissingDoc(
                            path=f"{path_prefix}.{enum_name}",
                            element_type="enum",
                            name=enum_name,
                            avro_type="enum",
                            context={"symbols": avro_type.get("symbols", [])},
                        )
                    )
        elif isinstance(avro_type, list):
            # Union type - analyze each variant
            for variant in avro_type:
                t, d = self._analyze_nested_types(variant, path_prefix, missing_docs)
                total += t
                documented += d

        return total, documented

    def _simplify_type(self, avro_type: Any) -> str:
        """Create a human-readable type string."""
        if isinstance(avro_type, str):
            return avro_type
        elif isinstance(avro_type, list):
            # Union type
            types = [self._simplify_type(t) for t in avro_type]
            return f"union<{', '.join(types)}>"
        elif isinstance(avro_type, dict):
            type_name = avro_type.get("type", "unknown")
            if type_name == "array":
                items = self._simplify_type(avro_type.get("items", "unknown"))
                return f"array<{items}>"
            elif type_name == "map":
                values = self._simplify_type(avro_type.get("values", "unknown"))
                return f"map<{values}>"
            elif type_name == "enum":
                return f"enum({avro_type.get('name', 'unknown')})"
            elif type_name == "record":
                return f"record({avro_type.get('name', 'unknown')})"
            else:
                return type_name
        return str(avro_type)

