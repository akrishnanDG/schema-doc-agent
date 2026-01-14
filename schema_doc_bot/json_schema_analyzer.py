"""Analyzer for finding missing documentation in JSON Schemas."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

# Use shared classes from avro_analyzer for compatibility
from .avro_analyzer import AnalysisResult, MissingDoc as AvroMissingDoc


@dataclass
class MissingDoc:
    """Represents a schema element missing documentation."""

    path: str
    element_type: str  # "object", "property", "array"
    name: str
    json_type: str | dict
    context: dict[str, Any] = field(default_factory=dict)
    
    # Add avro_type alias for compatibility with LLM client
    @property
    def avro_type(self) -> str:
        return str(self.json_type)


class JsonSchemaAnalyzer:
    """Analyzes JSON Schemas to find missing description fields."""

    def analyze_schema(self, subject: str, schema: dict[str, Any]) -> AnalysisResult:
        """Analyze a JSON Schema for missing documentation."""
        missing_docs: list[MissingDoc] = []
        total = 0
        documented = 0

        # Check root object
        if schema.get("type") == "object":
            t, d = self._analyze_object(schema, subject, missing_docs)
            total += t
            documented += d

        # Convert to shared AnalysisResult format
        # Convert MissingDoc to AvroMissingDoc for compatibility
        converted_docs = [
            AvroMissingDoc(
                path=doc.path,
                element_type=doc.element_type,
                name=doc.name,
                avro_type=str(doc.json_type),
                context=doc.context,
            )
            for doc in missing_docs
        ]
        
        return AnalysisResult(
            subject=subject,
            schema=schema,
            missing_docs=converted_docs,
            total_elements=total,
            documented_elements=documented,
        )

    def _analyze_object(
        self,
        obj: dict[str, Any],
        path: str,
        missing_docs: list[MissingDoc],
    ) -> tuple[int, int]:
        """Analyze an object schema."""
        total = 0
        documented = 0

        # Check the object itself
        total += 1
        if obj.get("description"):
            documented += 1
        else:
            missing_docs.append(
                MissingDoc(
                    path=path,
                    element_type="object",
                    name=path.split(".")[-1],
                    json_type="object",
                    context={"title": obj.get("title")},
                )
            )

        # Check properties
        properties = obj.get("properties", {})
        for prop_name, prop_schema in properties.items():
            prop_path = f"{path}.{prop_name}"
            total += 1

            if prop_schema.get("description"):
                documented += 1
            else:
                # Determine the type
                prop_type = self._get_type_string(prop_schema)
                missing_docs.append(
                    MissingDoc(
                        path=prop_path,
                        element_type="property",
                        name=prop_name,
                        json_type=prop_type,
                        context={
                            "connect_index": prop_schema.get("connect.index"),
                            "connect_type": self._get_connect_type(prop_schema),
                        },
                    )
                )

            # Recursively analyze nested objects
            if prop_schema.get("type") == "object":
                t, d = self._analyze_object(prop_schema, prop_path, missing_docs)
                total += t
                documented += d
            elif prop_schema.get("type") == "array":
                items = prop_schema.get("items", {})
                if items.get("type") == "object":
                    t, d = self._analyze_object(items, f"{prop_path}[]", missing_docs)
                    total += t
                    documented += d

        return total, documented

    def _get_type_string(self, schema: dict[str, Any]) -> str:
        """Get a readable type string from a JSON schema."""
        if "oneOf" in schema:
            types = []
            for option in schema["oneOf"]:
                if option.get("type") == "null":
                    continue
                t = option.get("type", "unknown")
                if "connect.type" in option:
                    t = option["connect.type"]
                types.append(t)
            if types:
                return f"nullable<{types[0]}>"
            return "null"
        
        t = schema.get("type", "unknown")
        if "connect.type" in schema:
            return schema["connect.type"]
        return t

    def _get_connect_type(self, schema: dict[str, Any]) -> str | None:
        """Extract connect.type from schema."""
        if "oneOf" in schema:
            for option in schema["oneOf"]:
                if "connect.type" in option:
                    return option["connect.type"]
        return schema.get("connect.type")

