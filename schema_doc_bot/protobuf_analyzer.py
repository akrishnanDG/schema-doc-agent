"""Analyzer for finding missing documentation in Protobuf schemas."""

from __future__ import annotations

import re
from typing import Any

from .avro_analyzer import AnalysisResult, MissingDoc


class ProtobufAnalyzer:
    """Analyzes Protobuf schemas to find missing comments/documentation."""

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
        
        for msg_name, msg_content, msg_comment in messages:
            total += 1
            msg_path = f"{subject}.{msg_name}" if msg_name != subject else subject
            
            if msg_comment:
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
            for field_name, field_type, field_comment in fields:
                total += 1
                field_path = f"{msg_path}.{field_name}"
                
                if field_comment:
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
        for enum_name, enum_values, enum_comment in enums:
            total += 1
            enum_path = f"{subject}.{enum_name}"
            
            if enum_comment:
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

    def _parse_messages(self, schema: str, subject: str) -> list[tuple[str, str, str | None]]:
        """Parse message definitions from Protobuf schema."""
        messages = []
        
        # Pattern to match message with optional preceding comment
        pattern = r'(?:/\*\*(.*?)\*/\s*|//\s*(.*?)\n\s*)?message\s+(\w+)\s*\{([^}]*)\}'
        
        for match in re.finditer(pattern, schema, re.DOTALL):
            block_comment = match.group(1)
            line_comment = match.group(2)
            msg_name = match.group(3)
            msg_content = match.group(4)
            
            comment = None
            if block_comment:
                comment = block_comment.strip()
            elif line_comment:
                comment = line_comment.strip()
            
            messages.append((msg_name, msg_content, comment))
        
        return messages

    def _parse_fields(self, message_content: str) -> list[tuple[str, str, str | None]]:
        """Parse field definitions from message content."""
        fields = []
        
        # Pattern for field with optional comment
        # Handles: optional/required/repeated type name = number; // comment
        pattern = r'(?:/\*\*(.*?)\*/\s*|//\s*(.*?)\n\s*)?(optional|required|repeated)?\s*(\w+)\s+(\w+)\s*='
        
        for match in re.finditer(pattern, message_content, re.DOTALL):
            block_comment = match.group(1)
            line_comment = match.group(2)
            modifier = match.group(3) or ""
            field_type = match.group(4)
            field_name = match.group(5)
            
            comment = None
            if block_comment:
                comment = block_comment.strip()
            elif line_comment:
                comment = line_comment.strip()
            
            full_type = f"{modifier} {field_type}".strip() if modifier else field_type
            fields.append((field_name, full_type, comment))
        
        # Also check for inline comments after field definition
        inline_pattern = r'(\w+)\s+(\w+)\s*=\s*\d+\s*;\s*//\s*(.+?)$'
        for match in re.finditer(inline_pattern, message_content, re.MULTILINE):
            field_type = match.group(1)
            field_name = match.group(2)
            comment = match.group(3).strip()
            
            # Update existing field with comment if found
            for i, (name, ftype, existing_comment) in enumerate(fields):
                if name == field_name and not existing_comment:
                    fields[i] = (name, ftype, comment)
                    break
        
        return fields

    def _parse_enums(self, schema: str, subject: str) -> list[tuple[str, list[str], str | None]]:
        """Parse enum definitions from Protobuf schema."""
        enums = []
        
        # Pattern to match enum with optional preceding comment
        pattern = r'(?:/\*\*(.*?)\*/\s*|//\s*(.*?)\n\s*)?enum\s+(\w+)\s*\{([^}]*)\}'
        
        for match in re.finditer(pattern, schema, re.DOTALL):
            block_comment = match.group(1)
            line_comment = match.group(2)
            enum_name = match.group(3)
            enum_content = match.group(4)
            
            comment = None
            if block_comment:
                comment = block_comment.strip()
            elif line_comment:
                comment = line_comment.strip()
            
            # Extract enum values
            values = re.findall(r'(\w+)\s*=', enum_content)
            
            enums.append((enum_name, values, comment))
        
        return enums

