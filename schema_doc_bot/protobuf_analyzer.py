"""Analyzer for finding missing documentation in Protobuf schemas."""

from __future__ import annotations

import re
from typing import Any

from .avro_analyzer import AnalysisResult, MissingDoc


class ProtobufAnalyzer:
    """
    Analyzes Protobuf schemas to find missing documentation.
    
    Note: Schema Registry strips comments from Protobuf schemas, so documentation
    must be done via custom options/annotations, not comments.
    
    Supported documentation patterns:
    1. Custom field options: [(description) = "..."]
    2. google.protobuf options with doc extensions
    3. confluent.field_meta options
    """

    # Common documentation option patterns
    DOC_OPTION_PATTERNS = [
        r'\[\s*\(\s*description\s*\)\s*=\s*"([^"]*)"\s*\]',
        r'\[\s*\(\s*doc\s*\)\s*=\s*"([^"]*)"\s*\]',
        r'\[\s*\(\s*comment\s*\)\s*=\s*"([^"]*)"\s*\]',
        r'\[\s*\(\s*field_doc\s*\)\s*=\s*"([^"]*)"\s*\]',
        # Confluent meta
        r'\[\s*confluent\.field_meta\s*=\s*\{\s*doc\s*:\s*"([^"]*)"\s*\}\s*\]',
    ]

    def analyze_schema(self, subject: str, schema: str | dict[str, Any]) -> AnalysisResult:
        """
        Analyze a Protobuf schema for missing documentation.
        
        Args:
            subject: Schema subject name
            schema: Protobuf schema (string or dict with 'schema' key)
        """
        # Handle both string and dict formats
        if isinstance(schema, dict):
            schema_str = schema.get("schema", str(schema))
        else:
            schema_str = schema

        missing_docs: list[MissingDoc] = []
        total = 0
        documented = 0

        # Parse messages
        messages = self._parse_messages(schema_str, subject)
        
        for msg_name, msg_content, has_doc in messages:
            total += 1
            msg_path = f"{subject}.{msg_name}" if msg_name != subject else subject
            
            if has_doc:
                documented += 1
            else:
                missing_docs.append(
                    MissingDoc(
                        path=msg_path,
                        element_type="message",
                        name=msg_name,
                        avro_type="message",
                        context={"proto_type": "message"},
                    )
                )

            # Parse fields within message
            fields = self._parse_fields(msg_content)
            for field_name, field_type, has_field_doc in fields:
                total += 1
                field_path = f"{msg_path}.{field_name}"
                
                if has_field_doc:
                    documented += 1
                else:
                    missing_docs.append(
                        MissingDoc(
                            path=field_path,
                            element_type="field",
                            name=field_name,
                            avro_type=field_type,
                            context={"proto_type": field_type},
                        )
                    )

        # Parse enums
        enums = self._parse_enums(schema_str, subject)
        for enum_name, enum_values, has_doc in enums:
            total += 1
            enum_path = f"{subject}.{enum_name}"
            
            if has_doc:
                documented += 1
            else:
                missing_docs.append(
                    MissingDoc(
                        path=enum_path,
                        element_type="enum",
                        name=enum_name,
                        avro_type="enum",
                        context={"values": enum_values},
                    )
                )

        return AnalysisResult(
            subject=subject,
            schema={"raw": schema_str} if isinstance(schema_str, str) else schema,
            missing_docs=missing_docs,
            total_elements=total,
            documented_elements=documented,
        )

    def _has_doc_option(self, text: str) -> bool:
        """Check if text contains a documentation option."""
        for pattern in self.DOC_OPTION_PATTERNS:
            if re.search(pattern, text):
                return True
        return False

    def _extract_doc(self, text: str) -> str | None:
        """Extract documentation from options if present."""
        for pattern in self.DOC_OPTION_PATTERNS:
            match = re.search(pattern, text)
            if match:
                return match.group(1)
        return None

    def _parse_messages(self, schema: str, subject: str) -> list[tuple[str, str, bool]]:
        """Parse message definitions from Protobuf schema."""
        messages = []
        
        # Pattern to match message with optional options
        # message User { option (description) = "..."; ... }
        pattern = r'message\s+(\w+)\s*\{([^}]*(?:\{[^}]*\}[^}]*)*)\}'
        
        for match in re.finditer(pattern, schema, re.DOTALL):
            msg_name = match.group(1)
            msg_content = match.group(2)
            
            # Check for message-level option
            msg_option_pattern = r'option\s+\(\s*(?:description|doc)\s*\)\s*=\s*"[^"]*"'
            has_doc = bool(re.search(msg_option_pattern, msg_content))
            
            messages.append((msg_name, msg_content, has_doc))
        
        return messages

    def _parse_fields(self, message_content: str) -> list[tuple[str, str, bool]]:
        """Parse field definitions from message content."""
        fields = []
        
        # Pattern for field: [modifier] type name = number [options];
        # e.g., optional string id = 1 [(description) = "User ID"];
        pattern = r'(optional|required|repeated)?\s*(\w+)\s+(\w+)\s*=\s*\d+\s*([^;]*);'
        
        for match in re.finditer(pattern, message_content, re.DOTALL):
            modifier = match.group(1) or ""
            field_type = match.group(2)
            field_name = match.group(3)
            options_part = match.group(4)
            
            # Check if field has documentation option
            has_doc = self._has_doc_option(options_part) if options_part else False
            
            full_type = f"{modifier} {field_type}".strip() if modifier else field_type
            fields.append((field_name, full_type, has_doc))
        
        return fields

    def _parse_enums(self, schema: str, subject: str) -> list[tuple[str, list[str], bool]]:
        """Parse enum definitions from Protobuf schema."""
        enums = []
        
        # Pattern to match enum
        pattern = r'enum\s+(\w+)\s*\{([^}]*)\}'
        
        for match in re.finditer(pattern, schema, re.DOTALL):
            enum_name = match.group(1)
            enum_content = match.group(2)
            
            # Check for enum-level option
            enum_option_pattern = r'option\s+\(\s*(?:description|doc)\s*\)\s*=\s*"[^"]*"'
            has_doc = bool(re.search(enum_option_pattern, enum_content))
            
            # Extract enum values
            values = re.findall(r'(\w+)\s*=', enum_content)
            
            enums.append((enum_name, values, has_doc))
        
        return enums


def get_protobuf_doc_example() -> str:
    """Return an example of how to document Protobuf schemas for Schema Registry."""
    return '''
// Protobuf documentation for Schema Registry must use options, not comments.
// Comments are stripped when schemas are registered.

syntax = "proto3";

import "google/protobuf/descriptor.proto";

// Define custom documentation option
extend google.protobuf.FieldOptions {
  optional string description = 50000;
}

extend google.protobuf.MessageOptions {
  optional string message_doc = 50001;
}

message User {
  option (message_doc) = "Represents a user in the system";
  
  string id = 1 [(description) = "Unique identifier for the user"];
  string email = 2 [(description) = "User email address in RFC 5322 format"];
  string name = 3 [(description) = "Display name of the user"];
}

// Alternative: Confluent-style meta
message Order {
  string order_id = 1 [confluent.field_meta = { doc: "Unique order identifier" }];
}
'''
