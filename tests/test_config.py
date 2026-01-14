"""Tests for configuration management."""

from __future__ import annotations

import os
import tempfile
from pathlib import Path

import pytest
import yaml

from schema_doc_bot.config import Config, load_config


class TestConfigLoading:
    """Tests for config file loading."""

    def test_load_default_config(self):
        """Test loading config when no file exists."""
        config = load_config(None)
        
        assert config is not None
        assert config.llm.default_provider == "openai"

    def test_load_config_from_file(self):
        """Test loading config from YAML file."""
        config_content = """
schema_registry:
  url: "https://test-registry.example.com"
  include_subjects:
    - "user-*"
    - "order-*"
  exclude_subjects:
    - "*-test"

llm:
  default_provider: "anthropic"
  min_confidence: "high"
  providers:
    anthropic:
      model: "claude-3-haiku-20240307"

github:
  repo: "test-org/test-repo"
  base_branch: "develop"
"""
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
            f.write(config_content)
            f.flush()
            
            try:
                config = load_config(Path(f.name))
                
                assert config.schema_registry.url == "https://test-registry.example.com"
                assert "user-*" in config.schema_registry.include_subjects
                assert "*-test" in config.schema_registry.exclude_subjects
                assert config.llm.default_provider == "anthropic"
                assert config.llm.min_confidence == "high"
                assert config.github.repo == "test-org/test-repo"
                assert config.github.base_branch == "develop"
            finally:
                os.unlink(f.name)

    def test_env_vars_override_config(self, monkeypatch):
        """Test that environment variables override config file."""
        monkeypatch.setenv("SCHEMA_REGISTRY_URL", "https://env-registry.example.com")
        monkeypatch.setenv("GITHUB_REPO", "env-org/env-repo")
        
        config = load_config(None)
        
        assert config.schema_registry.url == "https://env-registry.example.com"
        assert config.github.repo == "env-org/env-repo"

    def test_load_invalid_yaml(self):
        """Test loading invalid YAML file."""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
            f.write("invalid: yaml: content: [")
            f.flush()
            
            try:
                # Should not crash, falls back to defaults
                config = load_config(Path(f.name))
                assert config is not None
            except yaml.YAMLError:
                # Also acceptable - YAML error is expected
                pass
            finally:
                os.unlink(f.name)


class TestConfigDefaults:
    """Tests for config default values."""

    def test_llm_defaults(self):
        """Test default LLM configuration."""
        config = load_config(None)
        
        assert config.llm.default_provider == "openai"
        assert config.llm.min_confidence in ["low", "medium", "high"]

    def test_github_defaults(self):
        """Test default GitHub configuration."""
        config = load_config(None)
        
        assert config.github.base_branch == "main"

    def test_output_defaults(self):
        """Test default output configuration."""
        config = load_config(None)
        
        assert config.output.dry_run is False


class TestSubjectFiltering:
    """Tests for subject filtering configuration."""

    def test_include_patterns(self):
        """Test include pattern matching."""
        import fnmatch
        
        patterns = ["user-*", "order-*"]
        
        assert any(fnmatch.fnmatch("user-events", p) for p in patterns)
        assert any(fnmatch.fnmatch("order-created", p) for p in patterns)
        assert not any(fnmatch.fnmatch("payment-received", p) for p in patterns)

    def test_exclude_patterns(self):
        """Test exclude pattern matching."""
        import fnmatch
        
        patterns = ["*-test", "*-dev"]
        
        assert any(fnmatch.fnmatch("user-test", p) for p in patterns)
        assert any(fnmatch.fnmatch("order-dev", p) for p in patterns)
        assert not any(fnmatch.fnmatch("user-events", p) for p in patterns)

    def test_combined_filtering(self):
        """Test combined include and exclude filtering."""
        import fnmatch
        
        include = ["user-*"]
        exclude = ["*-test"]
        
        def matches(subject):
            if include and not any(fnmatch.fnmatch(subject, p) for p in include):
                return False
            if exclude and any(fnmatch.fnmatch(subject, p) for p in exclude):
                return False
            return True
        
        assert matches("user-events")
        assert not matches("user-test")  # Excluded
        assert not matches("order-events")  # Not included
