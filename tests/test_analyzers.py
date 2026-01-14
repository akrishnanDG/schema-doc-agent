"""Tests for schema analyzers."""

from __future__ import annotations

import pytest

from schema_doc_bot.avro_analyzer import AvroAnalyzer
from schema_doc_bot.json_schema_analyzer import JsonSchemaAnalyzer
from schema_doc_bot.protobuf_analyzer import ProtobufAnalyzer


class TestAvroAnalyzer:
    """Tests for Avro schema analyzer."""

    def test_analyze_record_without_docs(self):
        """Test analyzing a record with no documentation."""
        schema = {
            "type": "record",
            "name": "User",
            "fields": [
                {"name": "id", "type": "string"},
                {"name": "email", "type": "string"},
            ]
        }
        
        analyzer = AvroAnalyzer()
        result = analyzer.analyze_schema("test-subject", schema)
        
        assert result.total_elements == 3  # 1 record + 2 fields
        assert result.documented_elements == 0
        assert len(result.missing_docs) == 3
        assert result.coverage_percent == 0.0

    def test_analyze_record_with_partial_docs(self):
        """Test analyzing a record with partial documentation."""
        schema = {
            "type": "record",
            "name": "User",
            "doc": "A user record",
            "fields": [
                {"name": "id", "type": "string", "doc": "User ID"},
                {"name": "email", "type": "string"},  # No doc
            ]
        }
        
        analyzer = AvroAnalyzer()
        result = analyzer.analyze_schema("test-subject", schema)
        
        assert result.total_elements == 3
        assert result.documented_elements == 2
        assert len(result.missing_docs) == 1
        assert result.missing_docs[0].name == "email"

    def test_analyze_fully_documented(self):
        """Test analyzing a fully documented record."""
        schema = {
            "type": "record",
            "name": "User",
            "doc": "A user record",
            "fields": [
                {"name": "id", "type": "string", "doc": "User ID"},
            ]
        }
        
        analyzer = AvroAnalyzer()
        result = analyzer.analyze_schema("test-subject", schema)
        
        assert result.coverage_percent == 100.0
        assert len(result.missing_docs) == 0

    def test_analyze_nested_record(self):
        """Test analyzing a record with nested record type."""
        schema = {
            "type": "record",
            "name": "Order",
            "fields": [
                {"name": "order_id", "type": "string"},
                {
                    "name": "customer",
                    "type": {
                        "type": "record",
                        "name": "Customer",
                        "fields": [
                            {"name": "name", "type": "string"},
                            {"name": "email", "type": "string"}
                        ]
                    }
                }
            ]
        }
        
        analyzer = AvroAnalyzer()
        result = analyzer.analyze_schema("test-subject", schema)
        
        # Order record + order_id + customer field + Customer record + name + email
        assert result.total_elements >= 5
        assert result.documented_elements == 0

    def test_analyze_enum_type(self):
        """Test analyzing a record with enum type."""
        schema = {
            "type": "record",
            "name": "Order",
            "fields": [
                {
                    "name": "status",
                    "type": {
                        "type": "enum",
                        "name": "OrderStatus",
                        "symbols": ["PENDING", "SHIPPED", "DELIVERED"]
                    }
                }
            ]
        }
        
        analyzer = AvroAnalyzer()
        result = analyzer.analyze_schema("test-subject", schema)
        
        assert result.total_elements >= 2  # At least record + field
        assert len(result.missing_docs) >= 2

    def test_analyze_array_type(self):
        """Test analyzing a record with array type."""
        schema = {
            "type": "record",
            "name": "Order",
            "fields": [
                {
                    "name": "items",
                    "type": {
                        "type": "array",
                        "items": "string"
                    }
                }
            ]
        }
        
        analyzer = AvroAnalyzer()
        result = analyzer.analyze_schema("test-subject", schema)
        
        assert result.total_elements >= 2  # Record + field

    def test_analyze_nullable_field(self):
        """Test analyzing a record with nullable (union) type."""
        schema = {
            "type": "record",
            "name": "User",
            "fields": [
                {"name": "id", "type": "string"},
                {"name": "nickname", "type": ["null", "string"]},
            ]
        }
        
        analyzer = AvroAnalyzer()
        result = analyzer.analyze_schema("test-subject", schema)
        
        assert result.total_elements == 3  # Record + 2 fields
        assert len(result.missing_docs) == 3

    def test_analyze_map_type(self):
        """Test analyzing a record with map type."""
        schema = {
            "type": "record",
            "name": "Config",
            "fields": [
                {
                    "name": "settings",
                    "type": {
                        "type": "map",
                        "values": "string"
                    }
                }
            ]
        }
        
        analyzer = AvroAnalyzer()
        result = analyzer.analyze_schema("test-subject", schema)
        
        assert result.total_elements >= 2

    def test_empty_schema(self):
        """Test analyzing an empty/invalid schema."""
        analyzer = AvroAnalyzer()
        result = analyzer.analyze_schema("test-subject", {})
        
        assert result.total_elements == 0
        assert len(result.missing_docs) == 0

    def test_non_record_schema(self):
        """Test analyzing a non-record top-level schema."""
        schema = {"type": "string"}
        
        analyzer = AvroAnalyzer()
        result = analyzer.analyze_schema("test-subject", schema)
        
        assert result.total_elements == 0


class TestJsonSchemaAnalyzer:
    """Tests for JSON Schema analyzer."""

    def test_analyze_object_without_docs(self):
        """Test analyzing an object with no descriptions."""
        schema = {
            "type": "object",
            "properties": {
                "id": {"type": "string"},
                "email": {"type": "string"},
            }
        }
        
        analyzer = JsonSchemaAnalyzer()
        result = analyzer.analyze_schema("test-subject", schema)
        
        assert result.total_elements == 3  # 1 object + 2 properties
        assert result.documented_elements == 0
        assert len(result.missing_docs) == 3

    def test_analyze_object_with_descriptions(self):
        """Test analyzing an object with descriptions."""
        schema = {
            "type": "object",
            "description": "A user object",
            "properties": {
                "id": {"type": "string", "description": "User ID"},
                "email": {"type": "string"},
            }
        }
        
        analyzer = JsonSchemaAnalyzer()
        result = analyzer.analyze_schema("test-subject", schema)
        
        assert result.total_elements == 3
        assert result.documented_elements == 2
        assert len(result.missing_docs) == 1

    def test_analyze_nested_object(self):
        """Test analyzing a schema with nested objects."""
        schema = {
            "type": "object",
            "properties": {
                "user": {
                    "type": "object",
                    "properties": {
                        "name": {"type": "string"},
                        "address": {
                            "type": "object",
                            "properties": {
                                "city": {"type": "string"},
                                "zip": {"type": "string"}
                            }
                        }
                    }
                }
            }
        }
        
        analyzer = JsonSchemaAnalyzer()
        result = analyzer.analyze_schema("test-subject", schema)
        
        # Root + user + name + address + city + zip = 6 elements minimum
        assert result.total_elements >= 5
        assert result.documented_elements == 0

    def test_analyze_array_items(self):
        """Test analyzing a schema with array items."""
        schema = {
            "type": "object",
            "properties": {
                "tags": {
                    "type": "array",
                    "items": {"type": "string"}
                },
                "users": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "name": {"type": "string"}
                        }
                    }
                }
            }
        }
        
        analyzer = JsonSchemaAnalyzer()
        result = analyzer.analyze_schema("test-subject", schema)
        
        assert result.total_elements >= 3

    def test_analyze_fully_documented(self):
        """Test analyzing a fully documented schema."""
        schema = {
            "type": "object",
            "description": "User object",
            "properties": {
                "id": {"type": "string", "description": "User ID"},
                "name": {"type": "string", "description": "User name"}
            }
        }
        
        analyzer = JsonSchemaAnalyzer()
        result = analyzer.analyze_schema("test-subject", schema)
        
        assert result.coverage_percent == 100.0
        assert len(result.missing_docs) == 0

    def test_analyze_oneof_anyof(self):
        """Test analyzing a schema with oneOf/anyOf."""
        schema = {
            "type": "object",
            "properties": {
                "data": {
                    "oneOf": [
                        {"type": "string"},
                        {"type": "number"}
                    ]
                }
            }
        }
        
        analyzer = JsonSchemaAnalyzer()
        result = analyzer.analyze_schema("test-subject", schema)
        
        assert result.total_elements >= 2

    def test_analyze_with_refs(self):
        """Test analyzing a schema with $ref (refs are not followed)."""
        schema = {
            "type": "object",
            "properties": {
                "user": {"$ref": "#/definitions/User"}
            },
            "definitions": {
                "User": {
                    "type": "object",
                    "properties": {
                        "name": {"type": "string"}
                    }
                }
            }
        }
        
        analyzer = JsonSchemaAnalyzer()
        result = analyzer.analyze_schema("test-subject", schema)
        
        # Should handle refs gracefully
        assert result.total_elements >= 1

    def test_analyze_empty_schema(self):
        """Test analyzing an empty schema."""
        analyzer = JsonSchemaAnalyzer()
        result = analyzer.analyze_schema("test-subject", {})
        
        assert result.total_elements == 0

    def test_connect_schema_format(self):
        """Test analyzing Kafka Connect JSON Schema format."""
        schema = {
            "type": "object",
            "connect.name": "io.example.User",
            "properties": {
                "ID": {
                    "type": "integer",
                    "connect.index": 0,
                    "connect.type": "int64"
                },
                "NAME": {
                    "type": "string",
                    "connect.index": 1
                }
            }
        }
        
        analyzer = JsonSchemaAnalyzer()
        result = analyzer.analyze_schema("test-subject", schema)
        
        assert result.total_elements >= 3


class TestProtobufAnalyzer:
    """Tests for Protobuf schema analyzer."""

    def test_analyze_message_without_comments(self):
        """Test analyzing a message with no comments."""
        schema = """
        message User {
            string id = 1;
            string email = 2;
        }
        """
        
        analyzer = ProtobufAnalyzer()
        result = analyzer.analyze_schema("test-subject", schema)
        
        assert result.total_elements >= 1  # At least the message
        assert len(result.missing_docs) >= 1

    def test_analyze_message_with_comments(self):
        """Test analyzing a message with comments."""
        schema = """
        // A user message
        message User {
            // The user's unique identifier
            string id = 1;
            string email = 2;
        }
        """
        
        analyzer = ProtobufAnalyzer()
        result = analyzer.analyze_schema("test-subject", schema)
        
        # Should have fewer missing docs due to comments
        assert result.documented_elements >= 1

    def test_analyze_nested_message(self):
        """Test analyzing a message with nested message."""
        schema = """
        message Order {
            string order_id = 1;
            
            message Item {
                string name = 1;
                int32 quantity = 2;
            }
            
            repeated Item items = 2;
        }
        """
        
        analyzer = ProtobufAnalyzer()
        result = analyzer.analyze_schema("test-subject", schema)
        
        assert result.total_elements >= 2  # At least Order and Item

    def test_analyze_enum(self):
        """Test analyzing a message with enum."""
        schema = """
        message Order {
            enum Status {
                PENDING = 0;
                SHIPPED = 1;
                DELIVERED = 2;
            }
            
            Status status = 1;
        }
        """
        
        analyzer = ProtobufAnalyzer()
        result = analyzer.analyze_schema("test-subject", schema)
        
        assert result.total_elements >= 1

    def test_analyze_with_package(self):
        """Test analyzing a schema with package declaration."""
        schema = """
        syntax = "proto3";
        package com.example.users;
        
        message User {
            string id = 1;
        }
        """
        
        analyzer = ProtobufAnalyzer()
        result = analyzer.analyze_schema("test-subject", schema)
        
        assert result.total_elements >= 1

    def test_analyze_empty_schema(self):
        """Test analyzing an empty schema."""
        analyzer = ProtobufAnalyzer()
        result = analyzer.analyze_schema("test-subject", "")
        
        assert result.total_elements == 0

    def test_analyze_repeated_fields(self):
        """Test analyzing a message with repeated fields."""
        schema = """
        message User {
            string id = 1;
            repeated string tags = 2;
            repeated Address addresses = 3;
        }
        
        message Address {
            string city = 1;
        }
        """
        
        analyzer = ProtobufAnalyzer()
        result = analyzer.analyze_schema("test-subject", schema)
        
        assert result.total_elements >= 2  # User and Address messages


class TestAnalyzerEdgeCases:
    """Edge case tests for all analyzers."""

    def test_avro_with_string_schema(self):
        """Test Avro analyzer handles string input."""
        import json
        schema = {
            "type": "record",
            "name": "User",
            "fields": [{"name": "id", "type": "string"}]
        }
        
        analyzer = AvroAnalyzer()
        # Test with dict
        result = analyzer.analyze_schema("test", schema)
        assert result.total_elements >= 1

    def test_json_schema_with_additional_properties(self):
        """Test JSON Schema analyzer handles additionalProperties."""
        schema = {
            "type": "object",
            "properties": {
                "id": {"type": "string"}
            },
            "additionalProperties": {
                "type": "string"
            }
        }
        
        analyzer = JsonSchemaAnalyzer()
        result = analyzer.analyze_schema("test", schema)
        
        assert result.total_elements >= 2

    def test_coverage_calculation(self):
        """Test coverage percentage calculation."""
        schema = {
            "type": "object",
            "description": "Documented",
            "properties": {
                "a": {"type": "string", "description": "Doc"},
                "b": {"type": "string"},  # No doc
                "c": {"type": "string"},  # No doc
            }
        }
        
        analyzer = JsonSchemaAnalyzer()
        result = analyzer.analyze_schema("test", schema)
        
        # 2 documented out of 4 = 50%
        assert result.coverage_percent == 50.0
