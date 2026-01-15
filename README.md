# 🤖 Schema Documentation Agent

An **autonomous AI agent** that documents your Avro, JSON Schema, and Protobuf schemas automatically.

[![Python 3.9+](https://img.shields.io/badge/python-3.9+-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

## Overview

The Schema Documentation Agent connects to your Confluent Schema Registry, identifies undocumented schema elements, and uses LLMs to generate meaningful documentation. Unlike simple automation scripts, it operates as an **agent** with planning, self-review, and refinement capabilities.

```
┌──────────────────────────────────────────────────────────────┐
│                  Schema Documentation Agent                  │
├──────────────────────────────────────────────────────────────┤
│                                                              │
│   📋 Plan → 🔍 Analyze → 🤖 Generate → ✅ Review → 🔄 Refine   │
│                                                              │
│   Supports: Avro • JSON Schema • Protobuf                    │
│   LLMs: OpenAI • Anthropic • Gemini • Mistral • Ollama       │
│                                                              │
└──────────────────────────────────────────────────────────────┘
```

## Features

| Feature | Description |
|---------|-------------|
| **🧠 Agent Architecture** | Plans, reasons, self-reviews, and refines output |
| **📄 Multi-Format** | Avro, JSON Schema, and Protobuf support |
| **🔌 Multiple LLMs** | OpenAI, Anthropic, Google, Mistral, Ollama, Azure |
| **🏢 Schema Registry** | Direct integration with Confluent Schema Registry |
| **✨ Quality Control** | Auto-detects generic descriptions, re-generates |
| **🎯 Filtering** | Include/exclude schemas by pattern |
| **🔒 Dry Run** | Preview changes before applying |
| **📝 PR Creation** | Auto-creates GitHub PRs with documentation |

## Installation

### Prerequisites

- Python 3.9+
- Access to a Confluent Schema Registry
- LLM API key (or Ollama for local inference)

### Install

```bash
# Clone the repository
git clone https://github.com/akrishnanDG/schema-doc-agent.git
cd schema-doc-agent

# Install dependencies
pip install -r requirements.txt
```

### Install as CLI Tool (Optional)

```bash
# Run the install script to add `schema-doc-agent` to your PATH
./install.sh

# Add to your shell profile (~/.zshrc or ~/.bashrc)
export PATH="$HOME/.local/bin:$PATH"

# Now you can run from anywhere
schema-doc-agent --help
```

### Docker

```bash
docker build -t schema-doc-agent .
docker run --rm \
  -e SCHEMA_REGISTRY_URL="https://..." \
  -e SCHEMA_REGISTRY_USER="..." \
  -e SCHEMA_REGISTRY_PASSWORD="..." \
  -e OPENAI_API_KEY="..." \
  schema-doc-agent agent -i "my-schema-*" --dry-run
```

## Quick Start

### 1. Set Environment Variables

```bash
# Required: Schema Registry
export SCHEMA_REGISTRY_URL="https://your-registry.confluent.cloud"
export SCHEMA_REGISTRY_USER="your-api-key"
export SCHEMA_REGISTRY_PASSWORD="your-api-secret"

# Required: LLM Provider (choose one)
export OPENAI_API_KEY="sk-..."           # OpenAI
export ANTHROPIC_API_KEY="sk-ant-..."    # Anthropic
export GOOGLE_API_KEY="..."              # Google Gemini
export MISTRAL_API_KEY="..."             # Mistral

# Optional: For PR creation
export GITHUB_TOKEN="ghp_..."
export GITHUB_REPO="your-org/your-schema-repo"
```

### 2. Run the Agent

```bash
# From the project directory (no install required)
./schema-doc-agent agent -p openai -i "user-*" --dry-run

# Or if installed globally
schema-doc-agent agent -p openai -i "user-*" --dry-run

# Using local Ollama (free, private)
./schema-doc-agent agent -p ollama -i "user-*" --dry-run

# Process all schemas
./schema-doc-agent agent -p openai --dry-run

# Create actual PR (remove --dry-run)
./schema-doc-agent agent -p openai -i "user-*"
```

### 3. Example Output

```
╭──────────────────────────────────────────────────╮
│ 🤖 Schema Documentation Agent                    │
│ Autonomous documentation with planning & review  │
╰──────────────────────────────────────────────────╯

Phase 1: Planning
┌─────────────────┬────────────────┐
│ Property        │ Value          │
├─────────────────┼────────────────┤
│ Schemas         │ 3              │
│ Elements        │ 42             │
│ Estimated time  │ 2 minutes      │
│ Strategy        │ batched        │
│ LLM Provider    │ openai         │
└─────────────────┴────────────────┘

Phase 2: Analyzing Schemas
  Analyzing user-events-value (JSON)
    → 15 elements need documentation
  Analyzing order-created-value (AVRO)
    → 12 elements need documentation

Phase 3: Generating Documentation
  Documenting user-events-value...
    → Generated 15 descriptions
  Documenting order-created-value...
    → Generated 12 descriptions

Phase 4: Self-Review
  ⚠ user-events-value.metadata: Too generic

Phase 5: Refining 1 items
  Refining 1 docs for user-events-value

==================================================
┌─────────────────────┬───────┐
│ Metric              │ Value │
├─────────────────────┼───────┤
│ Schemas processed   │ 3     │
│ Elements documented │ 27    │
│ Elements refined    │ 1     │
│ Updates ready       │ 2     │
│ Errors              │ 0     │
└─────────────────────┴───────┘
```

## Commands

| Command | Description |
|---------|-------------|
| `agent` | **Recommended.** Run the full agent with planning & self-review |
| `run` | Legacy: Simple documentation without agent features |
| `analyze` | Show documentation coverage report only |
| `init` | Generate sample configuration file |
| `providers` | List available LLM providers |

### Agent Command Options

```bash
./schema-doc-agent agent [OPTIONS]

Options:
  -p, --provider TEXT     LLM provider (openai, anthropic, ollama, etc.)
  -m, --model TEXT        Override default model
  -i, --include TEXT      Subject patterns to include (can repeat)
  -e, --exclude TEXT      Subject patterns to exclude (can repeat)
  --dry-run               Preview without making changes
  --registry-url TEXT     Schema Registry URL
  --registry-user TEXT    Registry username
  --registry-password TEXT Registry password
  -c, --config PATH       Path to config file
  --help                  Show help message
```

## Configuration

### Environment Variables

| Variable | Required | Description |
|----------|----------|-------------|
| `SCHEMA_REGISTRY_URL` | Yes | Confluent Schema Registry endpoint |
| `SCHEMA_REGISTRY_USER` | Yes | API key or username |
| `SCHEMA_REGISTRY_PASSWORD` | Yes | API secret or password |
| `OPENAI_API_KEY` | If using OpenAI | OpenAI API key |
| `ANTHROPIC_API_KEY` | If using Anthropic | Anthropic API key |
| `GOOGLE_API_KEY` | If using Gemini | Google AI API key |
| `MISTRAL_API_KEY` | If using Mistral | Mistral API key |
| `OLLAMA_BASE_URL` | If using Ollama | Ollama server URL (default: localhost:11434) |
| `GITHUB_TOKEN` | For PR creation | GitHub personal access token |
| `GITHUB_REPO` | For PR creation | Repository as `owner/repo` |

### Config File

Create `schema-doc-bot.yaml`:

```yaml
schema_registry:
  url: "https://your-registry.confluent.cloud"
  include_subjects:
    - "user-*"
    - "order-*"
  exclude_subjects:
    - "*-test"
    - "*-dev"

github:
  repo: "your-org/your-schema-repo"
  base_branch: "main"

llm:
  default_provider: "openai"
  min_confidence: "low"
  providers:
    openai:
      model: "gpt-4o-mini"
    ollama:
      model: "llama3.2"
      base_url: "http://localhost:11434"

output:
  dry_run: false
```

## LLM Providers

| Provider | Model | Speed | Cost | Privacy |
|----------|-------|-------|------|---------|
| **OpenAI** | gpt-4o-mini | ⚡ Fast | $0.15/1M tokens | Cloud |
| **Anthropic** | claude-3-haiku | ⚡ Fast | $0.25/1M tokens | Cloud |
| **Google** | gemini-1.5-flash | ⚡ Fast | Free tier | Cloud |
| **Mistral** | mistral-small | ⚡ Fast | $0.20/1M tokens | Cloud (EU) |
| **Ollama** | llama3.2 | 🐢 Slow | Free | 🔒 Local |
| **Azure** | gpt-4o-mini | ⚡ Fast | Enterprise | Cloud |

### Using Ollama (Free & Private)

```bash
# Install Ollama
curl -fsSL https://ollama.com/install.sh | sh

# Pull a model
ollama pull llama3.2

# Run the agent
./schema-doc-agent agent -p ollama -i "my-schema" --dry-run
```

## Schema Format Support

### Avro
```json
{
  "type": "record",
  "name": "UserEvent",
  "fields": [
    {"name": "user_id", "type": "string", "doc": "← Generated"}
  ]
}
```

### JSON Schema
```json
{
  "type": "object",
  "properties": {
    "user_id": {
      "type": "string",
      "description": "← Generated"
    }
  }
}
```

### Protobuf
```protobuf
// Note: Schema Registry strips comments, so use options instead
import "google/protobuf/descriptor.proto";

extend google.protobuf.FieldOptions {
  optional string description = 50000;
}

message UserEvent {
  string user_id = 1 [(description) = "← Generated via option"];
}
```

## Agent Architecture

The agent operates in six phases:

```
┌─────────────────────────────────────────────────────────────┐
│ Phase 1: PLANNING                                           │
│   • Count schemas and elements                              │
│   • Estimate processing time                                │
│   • Choose strategy (single_batch/batched/progressive)      │
├─────────────────────────────────────────────────────────────┤
│ Phase 2: ANALYZING                                          │
│   • Auto-detect schema format (Avro/JSON/Protobuf)          │
│   • Identify undocumented elements                          │
│   • Calculate documentation coverage                        │
├─────────────────────────────────────────────────────────────┤
│ Phase 3: GENERATING                                         │
│   • Build context-aware prompts                             │
│   • Call LLM in batches                                     │
│   • Parse and validate responses                            │
├─────────────────────────────────────────────────────────────┤
│ Phase 4: SELF-REVIEW                                        │
│   • Check for generic descriptions                          │
│   • Flag too-short documentation                            │
│   • Identify low-confidence items                           │
├─────────────────────────────────────────────────────────────┤
│ Phase 5: REFINING                                           │
│   • Re-generate flagged items with enhanced prompts         │
│   • Re-assess quality                                       │
├─────────────────────────────────────────────────────────────┤
│ Phase 6: OUTPUT                                             │
│   • Apply documentation to schemas                          │
│   • Create GitHub PR or display dry-run                     │
└─────────────────────────────────────────────────────────────┘
```

## Filtering Schemas

Use glob patterns to select which schemas to process:

```bash
# Include specific patterns
./schema-doc-agent agent -i "user-*" -i "order-*"

# Exclude patterns
./schema-doc-agent agent -e "*-test" -e "*-internal"

# Combine
./schema-doc-agent agent -i "prod-*" -e "*-deprecated"
```

## GitHub Integration

The agent can automatically create PRs with documented schemas:

```bash
# Set GitHub credentials
export GITHUB_TOKEN="ghp_..."
export GITHUB_REPO="your-org/your-schema-repo"

# Run without --dry-run to create PR
./schema-doc-agent agent -p openai -i "user-*"
```

PR includes:
- List of all documented fields
- Confidence levels for each
- Full updated schema files

## CI/CD Integration

### GitHub Actions

Add this workflow to your **schema repository** at `.github/workflows/schema-docs.yml`:

```yaml
name: Schema Documentation

on:
  pull_request:
    paths: ['schemas/**', '**/*.avsc', '**/*.proto']
  workflow_dispatch:

jobs:
  document-schemas:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      
      - uses: actions/setup-python@v5
        with:
          python-version: '3.11'
      
      - name: Install Schema Documentation Agent
        run: pip install git+https://github.com/akrishnanDG/schema-doc-agent.git
      
      - name: Run agent
        env:
          SCHEMA_REGISTRY_URL: ${{ secrets.SCHEMA_REGISTRY_URL }}
          SCHEMA_REGISTRY_USER: ${{ secrets.SCHEMA_REGISTRY_USER }}
          SCHEMA_REGISTRY_PASSWORD: ${{ secrets.SCHEMA_REGISTRY_PASSWORD }}
          OPENAI_API_KEY: ${{ secrets.OPENAI_API_KEY }}
          GITHUB_TOKEN: ${{ secrets.GITHUB_TOKEN }}
          GITHUB_REPO: ${{ github.repository }}
        run: schema-doc-agent agent -p openai --dry-run
```

**Required Secrets** (add in repo Settings → Secrets):
| Secret | Description |
|--------|-------------|
| `SCHEMA_REGISTRY_URL` | Confluent Schema Registry URL |
| `SCHEMA_REGISTRY_USER` | API key |
| `SCHEMA_REGISTRY_PASSWORD` | API secret |
| `OPENAI_API_KEY` | OpenAI API key (or use another provider) |

### Docker

```bash
docker run --rm \
  -e SCHEMA_REGISTRY_URL="$SCHEMA_REGISTRY_URL" \
  -e SCHEMA_REGISTRY_USER="$SCHEMA_REGISTRY_USER" \
  -e SCHEMA_REGISTRY_PASSWORD="$SCHEMA_REGISTRY_PASSWORD" \
  -e OPENAI_API_KEY="$OPENAI_API_KEY" \
  akrishnandg/schema-doc-agent agent -p openai --dry-run
```

## Troubleshooting

### Connection Issues

```bash
# Test Schema Registry connectivity
curl -u "$SCHEMA_REGISTRY_USER:$SCHEMA_REGISTRY_PASSWORD" \
  "$SCHEMA_REGISTRY_URL/subjects"
```

### Slow Performance

- **Ollama**: Local models are CPU-bound. Use a smaller model (`llama3.2:1b`) or switch to cloud provider.
- **Large schemas**: Use `-i` to process specific schemas first.

### LLM Errors

- Verify API key is set correctly
- Check rate limits on your account
- For Ollama, ensure `ollama serve` is running

## Development

```bash
# Install dev dependencies
pip install -e ".[dev]"

# Run tests
pytest

# Type checking
mypy schema_doc_bot

# Linting
ruff check schema_doc_bot
```

## Project Structure

```
schema-doc-bot/
├── schema-doc-agent        # CLI entry point (executable)
├── install.sh              # Global installation script
├── schema_doc_bot/
│   ├── __init__.py
│   ├── cli.py              # CLI commands
│   ├── agent.py            # Agent orchestration
│   ├── config.py           # Configuration management
│   ├── registry_client.py  # Schema Registry client
│   ├── avro_analyzer.py    # Avro schema analyzer
│   ├── json_schema_analyzer.py  # JSON Schema analyzer
│   ├── protobuf_analyzer.py     # Protobuf analyzer
│   ├── llm_client.py       # LLM integrations
│   ├── schema_updater.py   # Avro updater
│   ├── json_schema_updater.py   # JSON Schema updater
│   └── github_client.py    # GitHub PR creation
├── tests/                  # Unit tests
├── requirements.txt
├── pyproject.toml
├── Dockerfile
└── README.md
```

## License

MIT License - see [LICENSE](LICENSE) for details.

## Contributing

Contributions welcome! Please read our contributing guidelines before submitting PRs.
