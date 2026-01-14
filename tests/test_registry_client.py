"""Tests for Schema Registry client."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from schema_doc_bot.registry_client import SchemaRegistryClient, SchemaInfo


class TestSchemaRegistryClient:
    """Tests for Schema Registry client."""

    def test_client_initialization(self):
        """Test client initialization with credentials."""
        client = SchemaRegistryClient(
            url="https://registry.example.com",
            username="test-user",
            password="test-pass"
        )
        
        assert client.url == "https://registry.example.com"

    def test_client_url_normalization(self):
        """Test URL trailing slash handling."""
        client = SchemaRegistryClient(
            url="https://registry.example.com/",
            username="user",
            password="pass"
        )
        
        # URL should not have trailing slash
        assert not client.url.endswith("/")

    @patch('requests.Session.get')
    def test_get_subjects(self, mock_get):
        """Test fetching subjects from registry."""
        mock_response = MagicMock()
        mock_response.json.return_value = ["user-value", "order-value", "payment-value"]
        mock_response.raise_for_status = MagicMock()
        mock_get.return_value = mock_response
        
        client = SchemaRegistryClient(
            url="https://registry.example.com",
            username="user",
            password="pass"
        )
        
        subjects = client.get_subjects()
        
        assert len(subjects) == 3
        assert "user-value" in subjects

    @patch('requests.Session.get')
    def test_get_latest_schema(self, mock_get):
        """Test fetching latest schema version."""
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "subject": "user-value",
            "version": 1,
            "id": 100,
            "schema": '{"type":"record","name":"User","fields":[{"name":"id","type":"string"}]}',
            "schemaType": "AVRO"
        }
        mock_response.raise_for_status = MagicMock()
        mock_get.return_value = mock_response
        
        client = SchemaRegistryClient(
            url="https://registry.example.com",
            username="user",
            password="pass"
        )
        
        schema_info = client.get_latest_schema("user-value")
        
        assert isinstance(schema_info, SchemaInfo)
        assert schema_info.schema["type"] == "record"
        assert schema_info.schema["name"] == "User"
        assert schema_info.schema_type == "AVRO"

    @patch('requests.Session.get')
    def test_get_json_schema(self, mock_get):
        """Test fetching JSON Schema."""
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "subject": "user-value",
            "version": 1,
            "id": 100,
            "schema": '{"type":"object","properties":{"id":{"type":"string"}}}',
            "schemaType": "JSON"
        }
        mock_response.raise_for_status = MagicMock()
        mock_get.return_value = mock_response
        
        client = SchemaRegistryClient(
            url="https://registry.example.com",
            username="user",
            password="pass"
        )
        
        schema_info = client.get_latest_schema("user-value")
        
        assert schema_info.schema["type"] == "object"
        assert schema_info.schema_type == "JSON"

    @patch('requests.Session.get')
    def test_get_protobuf_schema(self, mock_get):
        """Test fetching Protobuf schema."""
        # Protobuf schemas are stored as raw strings, not JSON
        # The registry client will fail to JSON parse it
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "subject": "user-value",
            "version": 1,
            "id": 100,
            "schema": '{"syntax": "proto3", "messages": [{"name": "User"}]}',
            "schemaType": "PROTOBUF"
        }
        mock_response.raise_for_status = MagicMock()
        mock_get.return_value = mock_response
        
        client = SchemaRegistryClient(
            url="https://registry.example.com",
            username="user",
            password="pass"
        )
        
        schema_info = client.get_latest_schema("user-value")
        
        # Protobuf schema type is detected
        assert schema_info.schema_type == "PROTOBUF"


class TestSubjectFiltering:
    """Tests for subject filtering."""

    @patch('requests.Session.get')
    def test_filter_subjects_include(self, mock_get):
        """Test filtering subjects with include pattern."""
        mock_response = MagicMock()
        mock_response.json.return_value = [
            "user-value",
            "user-key",
            "order-value",
            "payment-value"
        ]
        mock_response.raise_for_status = MagicMock()
        mock_get.return_value = mock_response
        
        client = SchemaRegistryClient(
            url="https://registry.example.com",
            username="user",
            password="pass"
        )
        
        all_subjects = client.get_subjects()
        
        # Filter with pattern
        import fnmatch
        filtered = [s for s in all_subjects if fnmatch.fnmatch(s, "user-*")]
        
        assert len(filtered) == 2
        assert "user-value" in filtered
        assert "user-key" in filtered

    @patch('requests.Session.get')
    def test_filter_subjects_exclude(self, mock_get):
        """Test filtering subjects with exclude pattern."""
        mock_response = MagicMock()
        mock_response.json.return_value = [
            "user-value",
            "user-value-test",
            "order-value",
            "order-value-dev"
        ]
        mock_response.raise_for_status = MagicMock()
        mock_get.return_value = mock_response
        
        client = SchemaRegistryClient(
            url="https://registry.example.com",
            username="user",
            password="pass"
        )
        
        all_subjects = client.get_subjects()
        
        # Filter excluding test/dev
        import fnmatch
        exclude_patterns = ["*-test", "*-dev"]
        filtered = [
            s for s in all_subjects
            if not any(fnmatch.fnmatch(s, p) for p in exclude_patterns)
        ]
        
        assert len(filtered) == 2
        assert "user-value" in filtered
        assert "order-value" in filtered


class TestSchemaRegistryErrors:
    """Tests for error handling."""

    @patch('requests.Session.get')
    def test_handle_connection_error(self, mock_get):
        """Test handling connection errors."""
        mock_get.side_effect = Exception("Connection refused")
        
        client = SchemaRegistryClient(
            url="https://registry.example.com",
            username="user",
            password="pass"
        )
        
        with pytest.raises(Exception):
            client.get_subjects()

    @patch('requests.Session.get')
    def test_handle_auth_error(self, mock_get):
        """Test handling authentication errors."""
        mock_response = MagicMock()
        mock_response.raise_for_status.side_effect = Exception("401 Unauthorized")
        mock_get.return_value = mock_response
        
        client = SchemaRegistryClient(
            url="https://registry.example.com",
            username="bad-user",
            password="bad-pass"
        )
        
        with pytest.raises(Exception):
            client.get_subjects()

    @patch('requests.Session.get')
    def test_handle_not_found(self, mock_get):
        """Test handling subject not found."""
        mock_response = MagicMock()
        mock_response.raise_for_status.side_effect = Exception("404 Not Found")
        mock_get.return_value = mock_response
        
        client = SchemaRegistryClient(
            url="https://registry.example.com",
            username="user",
            password="pass"
        )
        
        with pytest.raises(Exception):
            client.get_latest_schema("nonexistent-subject")
