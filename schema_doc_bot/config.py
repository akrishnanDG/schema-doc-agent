"""Configuration management for Schema Doc-Bot."""

from __future__ import annotations

import fnmatch
import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Literal

import yaml


def matches_patterns(name: str, patterns: list[str]) -> bool:
    """Check if a name matches any of the glob patterns."""
    if not patterns:
        return False
    return any(fnmatch.fnmatch(name, pattern) for pattern in patterns)


def filter_subjects(
    subjects: list[str],
    include_patterns: list[str],
    exclude_patterns: list[str],
) -> list[str]:
    """
    Filter subjects based on include/exclude patterns.
    
    Args:
        subjects: List of subject names
        include_patterns: Glob patterns to include (empty = include all)
        exclude_patterns: Glob patterns to exclude
        
    Returns:
        Filtered list of subjects
    """
    result = []
    for subject in subjects:
        # If include patterns specified, subject must match at least one
        if include_patterns and not matches_patterns(subject, include_patterns):
            continue
        # If subject matches any exclude pattern, skip it
        if matches_patterns(subject, exclude_patterns):
            continue
        result.append(subject)
    return result


@dataclass
class SchemaRegistryConfig:
    """Schema Registry configuration."""

    url: str = ""
    username: str = ""
    password: str = ""
    
    # Subject filtering
    include_subjects: list[str] = field(default_factory=list)  # Glob patterns to include
    exclude_subjects: list[str] = field(default_factory=list)  # Glob patterns to exclude

    def is_configured(self) -> bool:
        return bool(self.url)


@dataclass
class GitHubConfig:
    """GitHub configuration."""

    token: str = ""
    repo: str = ""
    base_branch: str = "main"
    schema_path: str = "schemas"
    file_extension: str = ".avsc"
    
    # File filtering
    include_patterns: list[str] = field(default_factory=list)  # Glob patterns to include
    exclude_patterns: list[str] = field(default_factory=list)  # Glob patterns to exclude

    def is_configured(self) -> bool:
        return bool(self.token and self.repo)


@dataclass
class LLMProviderConfig:
    """Configuration for a single LLM provider."""

    api_key: str = ""
    model: str = ""
    base_url: str = ""  # For custom endpoints (Ollama, Azure, etc.)
    extra: dict[str, Any] = field(default_factory=dict)


@dataclass
class LLMConfig:
    """LLM configuration."""

    default_provider: str = "openai"
    min_confidence: Literal["high", "medium", "low"] = "low"
    batch_size: int = 15
    temperature: float = 0.3
    providers: dict[str, LLMProviderConfig] = field(default_factory=dict)

    def __post_init__(self):
        # Set default models if not specified
        default_models = {
            "openai": "gpt-4o-mini",
            "anthropic": "claude-3-haiku-20240307",
            "google": "gemini-1.5-flash",
            "mistral": "mistral-small-latest",
            "ollama": "llama3.2",
            "azure": "gpt-4o-mini",
        }
        for name, provider in self.providers.items():
            if not provider.model and name in default_models:
                provider.model = default_models[name]


@dataclass
class OutputConfig:
    """Output and formatting configuration."""

    dry_run: bool = False
    verbose: bool = False
    output_dir: str = ""
    create_pr: bool = True


@dataclass
class Config:
    """Main configuration container."""

    schema_registry: SchemaRegistryConfig = field(default_factory=SchemaRegistryConfig)
    github: GitHubConfig = field(default_factory=GitHubConfig)
    llm: LLMConfig = field(default_factory=LLMConfig)
    output: OutputConfig = field(default_factory=OutputConfig)


def load_config(config_path: Path | None = None) -> Config:
    """
    Load configuration from file and environment variables.
    
    Priority (highest to lowest):
    1. Environment variables
    2. Config file
    3. Defaults
    """
    config = Config()
    
    # Try to find config file
    if config_path is None:
        for candidate in [
            Path("schema-doc-bot.yaml"),
            Path("schema-doc-bot.yml"),
            Path.home() / ".config" / "schema-doc-bot" / "config.yaml",
            Path.home() / ".schema-doc-bot.yaml",
        ]:
            if candidate.exists():
                config_path = candidate
                break
    
    # Load from file if found
    if config_path and config_path.exists():
        config = _load_from_file(config_path)
    
    # Override with environment variables
    config = _apply_env_overrides(config)
    
    return config


def _load_from_file(path: Path) -> Config:
    """Load configuration from a YAML file."""
    with open(path) as f:
        data = yaml.safe_load(f) or {}
    
    return _dict_to_config(data)


def _dict_to_config(data: dict[str, Any]) -> Config:
    """Convert a dictionary to a Config object."""
    config = Config()
    
    # Schema Registry
    if "schema_registry" in data:
        sr = data["schema_registry"]
        config.schema_registry = SchemaRegistryConfig(
            url=sr.get("url", ""),
            username=sr.get("username", ""),
            password=sr.get("password", ""),
            include_subjects=sr.get("include_subjects", []),
            exclude_subjects=sr.get("exclude_subjects", []),
        )
    
    # GitHub
    if "github" in data:
        gh = data["github"]
        config.github = GitHubConfig(
            token=gh.get("token", ""),
            repo=gh.get("repo", ""),
            base_branch=gh.get("base_branch", "main"),
            schema_path=gh.get("schema_path", "schemas"),
            file_extension=gh.get("file_extension", ".avsc"),
            include_patterns=gh.get("include_patterns", []),
            exclude_patterns=gh.get("exclude_patterns", []),
        )
    
    # LLM
    if "llm" in data:
        llm = data["llm"]
        providers = {}
        for name, pconfig in llm.get("providers", {}).items():
            providers[name] = LLMProviderConfig(
                api_key=pconfig.get("api_key", ""),
                model=pconfig.get("model", ""),
                base_url=pconfig.get("base_url", ""),
                extra=pconfig.get("extra", {}),
            )
        
        config.llm = LLMConfig(
            default_provider=llm.get("default_provider", "openai"),
            min_confidence=llm.get("min_confidence", "low"),
            batch_size=llm.get("batch_size", 15),
            temperature=llm.get("temperature", 0.3),
            providers=providers,
        )
    
    # Output
    if "output" in data:
        out = data["output"]
        config.output = OutputConfig(
            dry_run=out.get("dry_run", False),
            verbose=out.get("verbose", False),
            output_dir=out.get("output_dir", ""),
            create_pr=out.get("create_pr", True),
        )
    
    return config


def _apply_env_overrides(config: Config) -> Config:
    """Apply environment variable overrides to config."""
    # Schema Registry
    if url := os.getenv("SCHEMA_REGISTRY_URL"):
        config.schema_registry.url = url
    if user := os.getenv("SCHEMA_REGISTRY_USER"):
        config.schema_registry.username = user
    if pwd := os.getenv("SCHEMA_REGISTRY_PASSWORD"):
        config.schema_registry.password = pwd
    
    # GitHub
    if token := os.getenv("GITHUB_TOKEN"):
        config.github.token = token
    if repo := os.getenv("GITHUB_REPO"):
        config.github.repo = repo
    
    # LLM API Keys (add to providers if not already configured)
    env_keys = {
        "openai": "OPENAI_API_KEY",
        "anthropic": "ANTHROPIC_API_KEY",
        "google": "GOOGLE_API_KEY",
        "mistral": "MISTRAL_API_KEY",
        "azure": "AZURE_OPENAI_API_KEY",
    }
    
    for provider, env_var in env_keys.items():
        if api_key := os.getenv(env_var):
            if provider not in config.llm.providers:
                config.llm.providers[provider] = LLMProviderConfig()
            config.llm.providers[provider].api_key = api_key
    
    # Azure-specific
    if azure_endpoint := os.getenv("AZURE_OPENAI_ENDPOINT"):
        if "azure" not in config.llm.providers:
            config.llm.providers["azure"] = LLMProviderConfig()
        config.llm.providers["azure"].base_url = azure_endpoint
    
    # Ollama base URL
    if ollama_url := os.getenv("OLLAMA_BASE_URL"):
        if "ollama" not in config.llm.providers:
            config.llm.providers["ollama"] = LLMProviderConfig()
        config.llm.providers["ollama"].base_url = ollama_url
    
    return config


def save_config(config: Config, path: Path) -> None:
    """Save configuration to a YAML file."""
    data = {
        "schema_registry": {
            "url": config.schema_registry.url,
            "username": config.schema_registry.username,
            # Don't save password
        },
        "github": {
            "repo": config.github.repo,
            "base_branch": config.github.base_branch,
            "schema_path": config.github.schema_path,
            "file_extension": config.github.file_extension,
            # Don't save token
        },
        "llm": {
            "default_provider": config.llm.default_provider,
            "min_confidence": config.llm.min_confidence,
            "batch_size": config.llm.batch_size,
            "temperature": config.llm.temperature,
            "providers": {
                name: {
                    "model": p.model,
                    "base_url": p.base_url,
                    # Don't save api_key
                }
                for name, p in config.llm.providers.items()
            },
        },
        "output": {
            "dry_run": config.output.dry_run,
            "verbose": config.output.verbose,
            "output_dir": config.output.output_dir,
            "create_pr": config.output.create_pr,
        },
    }
    
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w") as f:
        yaml.dump(data, f, default_flow_style=False, sort_keys=False)


def generate_sample_config() -> str:
    """Generate a sample configuration file."""
    return '''# Schema Doc-Bot Configuration
# Copy this to schema-doc-bot.yaml and customize

schema_registry:
  url: "https://your-registry.confluent.cloud"
  username: ""  # Or set SCHEMA_REGISTRY_USER env var
  password: ""  # Or set SCHEMA_REGISTRY_PASSWORD env var
  
  # Filter which subjects to process (glob patterns)
  include_subjects: []    # Empty = include all. Examples: ["user-*", "order-*-value"]
  exclude_subjects: []    # Examples: ["*-test", "legacy-*"]

github:
  repo: "your-org/your-schema-repo"
  base_branch: "main"
  schema_path: "schemas"  # Root path to search for .avsc files
  file_extension: ".avsc"
  # token: set GITHUB_TOKEN env var
  
  # Filter which files to process (glob patterns)
  include_patterns: []    # Empty = include all. Examples: ["users/*", "orders/**/*.avsc"]
  exclude_patterns: []    # Examples: ["test/*", "*_test.avsc"]

llm:
  default_provider: "openai"  # openai, anthropic, google, mistral, ollama, azure
  min_confidence: "low"       # high, medium, low
  batch_size: 15              # Elements per LLM request
  temperature: 0.3

  providers:
    openai:
      model: "gpt-4o-mini"
      # api_key: set OPENAI_API_KEY env var

    anthropic:
      model: "claude-3-haiku-20240307"
      # api_key: set ANTHROPIC_API_KEY env var

    google:
      model: "gemini-1.5-flash"
      # api_key: set GOOGLE_API_KEY env var

    mistral:
      model: "mistral-small-latest"
      # api_key: set MISTRAL_API_KEY env var

    ollama:
      model: "llama3.2"
      base_url: "http://localhost:11434"  # Or set OLLAMA_BASE_URL env var

    azure:
      model: "gpt-4o-mini"
      base_url: ""  # Your Azure OpenAI endpoint, or set AZURE_OPENAI_ENDPOINT
      # api_key: set AZURE_OPENAI_API_KEY env var

output:
  dry_run: false
  verbose: false
  create_pr: true
  output_dir: ""  # For local file output instead of PR
'''

