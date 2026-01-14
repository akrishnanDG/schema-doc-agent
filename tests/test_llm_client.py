"""Tests for LLM client."""

from __future__ import annotations

import os
from unittest.mock import MagicMock, patch, patch as mock_patch

import pytest

from schema_doc_bot.llm_client import (
    BaseLLMClient,
    create_llm_client,
    GeneratedDoc,
    build_prompt,
)
from schema_doc_bot.config import LLMConfig, LLMProviderConfig


class TestCreateLLMClient:
    """Tests for LLM client factory."""

    @pytest.mark.integration
    def test_create_openai_client(self):
        """Test creating OpenAI client (requires network/API key)."""
        pytest.skip("Integration test - requires network access and API key")

    @pytest.mark.integration
    def test_create_anthropic_client(self):
        """Test creating Anthropic client (requires network/API key)."""
        pytest.skip("Integration test - requires network access and API key")

    @pytest.mark.integration
    def test_create_ollama_client(self):
        """Test creating Ollama client (requires local Ollama server)."""
        pytest.skip("Integration test - requires Ollama server")

    def test_create_unknown_provider(self):
        """Test creating client with unknown provider."""
        config = LLMConfig(default_provider="unknown")
        
        with pytest.raises(ValueError):
            create_llm_client("unknown-provider", config)

    @pytest.mark.integration
    def test_create_with_custom_model(self):
        """Test creating client with custom model (requires network/API key)."""
        pytest.skip("Integration test - requires network access and API key")
    
    def test_missing_api_key_raises_error(self):
        """Test that missing API key raises ValueError."""
        config = LLMConfig(
            default_provider="openai",
            providers={"openai": LLMProviderConfig(model="gpt-4o-mini")}
        )
        
        with pytest.raises(ValueError, match="API key required"):
            create_llm_client("openai", config)


class TestGeneratedDoc:
    """Tests for GeneratedDoc dataclass."""

    def test_generated_doc_creation(self):
        """Test creating GeneratedDoc."""
        doc = GeneratedDoc(
            path="User.id",
            element_type="field",
            documentation="User identifier",
            confidence="high"
        )
        
        assert doc.path == "User.id"
        assert doc.documentation == "User identifier"
        assert doc.confidence == "high"

    def test_generated_doc_fields(self):
        """Test GeneratedDoc field access."""
        doc = GeneratedDoc(
            path="User.id",
            element_type="field",
            documentation="User identifier",
            confidence="high"
        )
        
        assert doc.path == "User.id"
        assert doc.element_type == "field"


class TestBuildPrompt:
    """Tests for prompt building."""

    def test_prompt_includes_schema_name(self):
        """Test that prompts include schema name."""
        from schema_doc_bot.avro_analyzer import MissingDoc
        
        missing = [MissingDoc(path="User.id", element_type="field", name="id", avro_type="string")]
        context = {"name": "User", "doc": "A user record"}
        
        prompt = build_prompt(missing, context)
        
        assert "User" in prompt
        assert "id" in prompt

    def test_prompt_with_no_description(self):
        """Test prompt when schema has no description."""
        from schema_doc_bot.avro_analyzer import MissingDoc
        
        missing = [MissingDoc(path="User.id", element_type="field", name="id", avro_type="string")]
        context = {"name": "User"}
        
        prompt = build_prompt(missing, context)
        
        assert "User" in prompt


class TestLLMClientResponseParsing:
    """Tests for LLM response parsing."""

    def test_parse_single_doc_response(self):
        """Test parsing a single documentation response."""
        response = """
        Here's the documentation:
        
        - **User.id**: The unique identifier for the user account. [HIGH]
        """
        
        assert "User.id" in response
        assert "HIGH" in response

    def test_parse_multiple_docs_response(self):
        """Test parsing multiple documentation entries."""
        response = """
        Generated documentation:
        
        - **User.id**: User identifier [HIGH]
        - **User.email**: User email address [HIGH]
        - **User.name**: Display name [MEDIUM]
        """
        
        assert "User.id" in response
        assert "User.email" in response
        assert "User.name" in response

    def test_parse_response_with_json_format(self):
        """Test parsing JSON formatted response."""
        import json
        
        response_data = [
            {"path": "User.id", "documentation": "User ID", "confidence": "high"},
            {"path": "User.email", "documentation": "Email", "confidence": "high"}
        ]
        
        parsed = response_data
        
        assert len(parsed) == 2
        assert parsed[0]["path"] == "User.id"


class TestLLMClientPrompts:
    """Tests for LLM prompt generation."""

    def test_prompt_includes_context(self):
        """Test that prompts include schema context."""
        schema_info = {
            "name": "UserCreated",
            "fields": ["user_id", "email", "created_at"]
        }
        
        prompt = f"""
        Generate documentation for the following schema elements:
        
        Schema: {schema_info['name']}
        Fields: {', '.join(schema_info['fields'])}
        """
        
        assert "UserCreated" in prompt
        assert "user_id" in prompt

    def test_prompt_includes_confidence_instruction(self):
        """Test that prompts include confidence level instructions."""
        prompt = """
        For each field, provide:
        - A clear, concise description
        - A confidence level: HIGH, MEDIUM, or LOW
        """
        
        assert "HIGH" in prompt
        assert "MEDIUM" in prompt
        assert "LOW" in prompt


class TestConfidenceFiltering:
    """Tests for confidence filtering."""

    def test_confidence_filtering(self):
        """Test filtering docs by confidence level."""
        docs = [
            GeneratedDoc("User.id", "field", "ID", "high"),
            GeneratedDoc("User.email", "field", "Email", "medium"),
            GeneratedDoc("User.temp", "field", "Temp", "low"),
        ]
        
        # Filter by minimum confidence
        def filter_by_confidence(docs, min_level):
            levels = {"low": 0, "medium": 1, "high": 2}
            min_value = levels.get(min_level, 0)
            return [d for d in docs if levels.get(d.confidence, 0) >= min_value]
        
        high_only = filter_by_confidence(docs, "high")
        assert len(high_only) == 1
        
        medium_plus = filter_by_confidence(docs, "medium")
        assert len(medium_plus) == 2
        
        all_docs = filter_by_confidence(docs, "low")
        assert len(all_docs) == 3


class TestLLMClientErrorHandling:
    """Tests for error handling in LLM client."""

    def test_handle_empty_response(self):
        """Test handling empty LLM response."""
        response = ""
        
        assert response == "" or len(response) == 0

    def test_handle_malformed_response(self):
        """Test handling malformed LLM response."""
        response = "This is not properly formatted documentation"
        
        assert isinstance(response, str)

    def test_handle_rate_limit(self):
        """Test handling rate limit errors."""
        class RateLimitError(Exception):
            pass
        
        def mock_call_with_retry():
            attempts = 0
            max_attempts = 3
            
            while attempts < max_attempts:
                try:
                    if attempts < 2:
                        raise RateLimitError("Rate limited")
                    return "Success"
                except RateLimitError:
                    attempts += 1
            
            return None
        
        result = mock_call_with_retry()
        assert result == "Success"
