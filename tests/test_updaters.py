"""Tests for schema updaters."""

from __future__ import annotations

import copy
import json

import pytest

from schema_doc_bot.schema_updater import SchemaUpdater
from schema_doc_bot.json_schema_updater import JsonSchemaUpdater
from schema_doc_bot.llm_client import GeneratedDoc


class TestAvroSchemaUpdater:
    """Tests for Avro schema updater."""

    def test_update_record_doc(self):
        """Test adding doc to a record."""
        schema = {
            "type": "record",
            "name": "User",
            "fields": [
                {"name": "id", "type": "string"}
            ]
        }
        
        docs = [
            GeneratedDoc(path="User", element_type="record", documentation="A user record", confidence="high")
        ]
        
        updater = SchemaUpdater()
        result = updater.apply_documentation(copy.deepcopy(schema), docs, "test.avsc")
        
        assert result is not None
        assert result.updated_schema["doc"] == "A user record"

    def test_update_field_doc(self):
        """Test adding doc to a field."""
        schema = {
            "type": "record",
            "name": "User",
            "fields": [
                {"name": "id", "type": "string"},
                {"name": "email", "type": "string"}
            ]
        }
        
        docs = [
            GeneratedDoc(path="User.id", element_type="field", documentation="User identifier", confidence="high"),
            GeneratedDoc(path="User.email", element_type="field", documentation="User email address", confidence="high")
        ]
        
        updater = SchemaUpdater()
        result = updater.apply_documentation(copy.deepcopy(schema), docs, "test.avsc")
        
        assert result is not None
        assert result.updated_schema["fields"][0]["doc"] == "User identifier"
        assert result.updated_schema["fields"][1]["doc"] == "User email address"

    def test_update_nested_record(self):
        """Test adding doc to nested record."""
        schema = {
            "type": "record",
            "name": "Order",
            "fields": [
                {
                    "name": "customer",
                    "type": {
                        "type": "record",
                        "name": "Customer",
                        "fields": [
                            {"name": "name", "type": "string"}
                        ]
                    }
                }
            ]
        }
        
        docs = [
            GeneratedDoc(path="Order", element_type="record", documentation="An order record", confidence="high"),
            GeneratedDoc(path="Customer", element_type="record", documentation="Customer information", confidence="high"),
            GeneratedDoc(path="Customer.name", element_type="field", documentation="Customer name", confidence="high")
        ]
        
        updater = SchemaUpdater()
        result = updater.apply_documentation(copy.deepcopy(schema), docs, "test.avsc")
        
        assert result is not None
        # Check that at least the top-level record was updated
        assert "doc" in result.updated_schema

    def test_filter_by_confidence(self):
        """Test that low confidence docs are filtered out."""
        schema = {
            "type": "record",
            "name": "User",
            "fields": [
                {"name": "id", "type": "string"}
            ]
        }
        
        docs = [
            GeneratedDoc(path="User.id", element_type="field", documentation="ID", confidence="low")
        ]
        
        updater = SchemaUpdater()
        result = updater.apply_documentation(copy.deepcopy(schema), docs, "test.avsc", min_confidence="high")
        
        # Should be None because only low confidence doc was filtered out
        assert result is None

    def test_no_matching_paths(self):
        """Test when no docs match the schema paths."""
        schema = {
            "type": "record",
            "name": "User",
            "fields": [
                {"name": "id", "type": "string"}
            ]
        }
        
        docs = [
            GeneratedDoc(path="Order.id", element_type="field", documentation="Wrong path", confidence="high")
        ]
        
        updater = SchemaUpdater()
        result = updater.apply_documentation(copy.deepcopy(schema), docs, "test.avsc")
        
        # Should return None because no paths matched
        # The doc for Order.id won't apply to User schema
        assert result is None or "doc" not in result.updated_schema.get("fields", [{}])[0]

    def test_empty_docs_list(self):
        """Test with empty docs list."""
        schema = {
            "type": "record",
            "name": "User",
            "fields": [
                {"name": "id", "type": "string"}
            ]
        }
        
        updater = SchemaUpdater()
        result = updater.apply_documentation(copy.deepcopy(schema), [], "test.avsc")
        
        assert result is None


class TestJsonSchemaUpdater:
    """Tests for JSON Schema updater."""

    def test_update_root_description(self):
        """Test adding description to root object."""
        schema = {
            "type": "object",
            "properties": {
                "id": {"type": "string"}
            }
        }
        
        docs = [
            GeneratedDoc(path="test-subject", element_type="object", documentation="A user object", confidence="high")
        ]
        
        updater = JsonSchemaUpdater()
        result = updater.apply_documentation(copy.deepcopy(schema), docs, "test.json", subject="test-subject")
        
        assert result is not None
        assert result.updated_schema["description"] == "A user object"

    def test_update_property_description(self):
        """Test adding description to properties."""
        schema = {
            "type": "object",
            "properties": {
                "id": {"type": "string"},
                "email": {"type": "string"}
            }
        }
        
        docs = [
            GeneratedDoc(path="test-subject.id", element_type="property", documentation="User ID", confidence="high"),
            GeneratedDoc(path="test-subject.email", element_type="property", documentation="Email address", confidence="high")
        ]
        
        updater = JsonSchemaUpdater()
        result = updater.apply_documentation(copy.deepcopy(schema), docs, "test.json", subject="test-subject")
        
        assert result is not None
        assert result.updated_schema["properties"]["id"]["description"] == "User ID"
        assert result.updated_schema["properties"]["email"]["description"] == "Email address"

    def test_update_nested_property(self):
        """Test adding description to nested properties."""
        schema = {
            "type": "object",
            "properties": {
                "address": {
                    "type": "object",
                    "properties": {
                        "city": {"type": "string"},
                        "zip": {"type": "string"}
                    }
                }
            }
        }
        
        docs = [
            GeneratedDoc(path="test-subject.address", element_type="object", documentation="User address", confidence="high"),
            GeneratedDoc(path="test-subject.address.city", element_type="property", documentation="City name", confidence="high")
        ]
        
        updater = JsonSchemaUpdater()
        result = updater.apply_documentation(copy.deepcopy(schema), docs, "test.json", subject="test-subject")
        
        assert result is not None
        assert result.updated_schema["properties"]["address"]["description"] == "User address"
        assert result.updated_schema["properties"]["address"]["properties"]["city"]["description"] == "City name"

    def test_preserve_existing_descriptions(self):
        """Test that no changes when no new docs provided."""
        schema = {
            "type": "object",
            "description": "Existing",
            "properties": {
                "id": {"type": "string", "description": "Existing ID"}
            }
        }
        
        docs = []  # No updates
        
        updater = JsonSchemaUpdater()
        result = updater.apply_documentation(copy.deepcopy(schema), docs, "test.json", subject="test-subject")
        
        # No changes, should return None
        assert result is None

    def test_update_connect_schema(self):
        """Test updating Kafka Connect JSON Schema format."""
        schema = {
            "type": "object",
            "connect.name": "io.example.User",
            "properties": {
                "ID": {
                    "type": "integer",
                    "connect.index": 0
                },
                "NAME": {
                    "type": "string",
                    "connect.index": 1
                }
            }
        }
        
        docs = [
            GeneratedDoc(path="test-subject.ID", element_type="property", documentation="User ID", confidence="high"),
            GeneratedDoc(path="test-subject.NAME", element_type="property", documentation="User name", confidence="high")
        ]
        
        updater = JsonSchemaUpdater()
        result = updater.apply_documentation(copy.deepcopy(schema), docs, "test.json", subject="test-subject")
        
        assert result is not None
        assert result.updated_schema["properties"]["ID"]["description"] == "User ID"
        assert result.updated_schema["properties"]["NAME"]["description"] == "User name"
        # Preserve connect metadata
        assert result.updated_schema["properties"]["ID"]["connect.index"] == 0

    def test_empty_schema(self):
        """Test with empty schema."""
        updater = JsonSchemaUpdater()
        result = updater.apply_documentation({}, [], "test.json", subject="test-subject")
        
        assert result is None


class TestUpdaterIntegration:
    """Integration tests for updaters."""

    def test_full_avro_workflow(self):
        """Test complete Avro update workflow."""
        schema = {
            "type": "record",
            "name": "UserCreated",
            "namespace": "com.example.events",
            "fields": [
                {"name": "user_id", "type": "string"},
                {"name": "email", "type": "string"},
                {"name": "created_at", "type": "long"}
            ]
        }
        
        docs = [
            GeneratedDoc(path="UserCreated", element_type="record", documentation="Event emitted when a new user is created", confidence="high"),
            GeneratedDoc(path="UserCreated.user_id", element_type="field", documentation="Unique identifier for the user", confidence="high"),
            GeneratedDoc(path="UserCreated.email", element_type="field", documentation="User's email address", confidence="high"),
            GeneratedDoc(path="UserCreated.created_at", element_type="field", documentation="Unix timestamp of creation", confidence="medium")
        ]
        
        updater = SchemaUpdater()
        result = updater.apply_documentation(copy.deepcopy(schema), docs, "user-created.avsc")
        
        assert result is not None
        assert result.updated_schema["doc"] == "Event emitted when a new user is created"
        assert result.updated_schema["fields"][0]["doc"] == "Unique identifier for the user"
        assert result.updated_schema["fields"][1]["doc"] == "User's email address"
        assert result.updated_schema["fields"][2]["doc"] == "Unix timestamp of creation"
        # Preserve original fields
        assert result.updated_schema["namespace"] == "com.example.events"

    def test_full_json_schema_workflow(self):
        """Test complete JSON Schema update workflow."""
        schema = {
            "type": "object",
            "properties": {
                "user_id": {"type": "string"},
                "profile": {
                    "type": "object",
                    "properties": {
                        "name": {"type": "string"},
                        "bio": {"type": "string"}
                    }
                }
            }
        }
        
        docs = [
            GeneratedDoc(path="test-subject", element_type="object", documentation="User profile data", confidence="high"),
            GeneratedDoc(path="test-subject.user_id", element_type="property", documentation="Unique user identifier", confidence="high"),
            GeneratedDoc(path="test-subject.profile", element_type="object", documentation="User profile information", confidence="high"),
            GeneratedDoc(path="test-subject.profile.name", element_type="property", documentation="Display name", confidence="high"),
            GeneratedDoc(path="test-subject.profile.bio", element_type="property", documentation="User biography", confidence="medium")
        ]
        
        updater = JsonSchemaUpdater()
        result = updater.apply_documentation(copy.deepcopy(schema), docs, "test.json", subject="test-subject")
        
        assert result is not None
        assert result.updated_schema["description"] == "User profile data"
        assert result.updated_schema["properties"]["user_id"]["description"] == "Unique user identifier"
        assert result.updated_schema["properties"]["profile"]["description"] == "User profile information"
        assert result.updated_schema["properties"]["profile"]["properties"]["name"]["description"] == "Display name"
        assert result.updated_schema["properties"]["profile"]["properties"]["bio"]["description"] == "User biography"
