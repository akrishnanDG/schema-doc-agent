"""LLM client for generating schema documentation."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Literal

from .avro_analyzer import MissingDoc
from .config import LLMConfig, LLMProviderConfig


@dataclass
class GeneratedDoc:
    """A generated documentation string."""

    path: str
    element_type: str
    documentation: str
    confidence: Literal["high", "medium", "low"]


SYSTEM_PROMPT = """You are a technical documentation expert specializing in Apache Avro schemas.
Your task is to generate concise, accurate documentation for schema fields and records.

Guidelines:
- Be concise but informative (1-2 sentences max)
- Focus on the purpose and meaning of the element
- Include format details for strings (e.g., ISO 8601 for dates)
- Mention constraints or valid values when applicable
- Use present tense ("Contains", "Represents", "Stores")
- Don't start with "This field" - be direct

For each element, provide:
1. A clear description of what it represents
2. Rate your confidence: HIGH (obvious meaning), MEDIUM (reasonable inference), LOW (guessing)"""


def build_prompt(missing_docs: list, schema_context: dict) -> str:
    """Build the prompt for documentation generation.
    
    Supports both Avro MissingDoc (avro_type) and JSON Schema MissingDoc (json_type).
    """
    schema_name = schema_context.get("name", "Unknown")
    schema_doc = schema_context.get("doc") or schema_context.get("description", "No description available")

    elements_text = []
    for doc in missing_docs:
        # Handle both Avro (avro_type) and JSON Schema (json_type)
        type_str = getattr(doc, 'avro_type', None) or getattr(doc, 'json_type', 'unknown')
        
        element_info = f"""
Element #{len(elements_text) + 1}:
- Path: {doc.path}
- Type: {doc.element_type}
- Name: {doc.name}
- Data Type: {type_str}"""

        if hasattr(doc, 'parent_doc') and doc.parent_doc:
            element_info += f"\n- Parent Context: {doc.parent_doc}"

        if doc.context.get("default") is not None:
            element_info += f"\n- Default Value: {doc.context['default']}"

        if doc.context.get("symbols"):
            element_info += f"\n- Enum Values: {doc.context['symbols']}"

        elements_text.append(element_info)

    return f"""Schema: {schema_name}
Schema Description: {schema_doc}

Generate documentation for these undocumented elements:
{"".join(elements_text)}

Respond in this exact format for each element:
ELEMENT #N:
DOC: <your documentation>
CONFIDENCE: <HIGH|MEDIUM|LOW>
---"""


def parse_response(response: str, missing_docs: list[MissingDoc]) -> list[GeneratedDoc]:
    """Parse the LLM response into GeneratedDoc objects."""
    import re
    
    results = []
    
    # Try parsing by ELEMENT markers first (handles various LLM formats)
    blocks = re.split(r'ELEMENT\s*#?(\d+)\s*:?\s*\n', response)
    
    if len(blocks) > 2:
        # blocks[0] is text before first ELEMENT, then alternating: number, content
        for i in range(1, len(blocks), 2):
            if i + 1 < len(blocks):
                try:
                    elem_num = int(blocks[i])
                except ValueError:
                    continue
                    
                content = blocks[i + 1]
                
                # Extract DOC (may span multiple lines)
                doc_match = re.search(r'DOC:\s*(.+?)(?=\nCONFIDENCE:|\n\n|$)', content, re.DOTALL)
                conf_match = re.search(r'CONFIDENCE:\s*(\w+)', content, re.IGNORECASE)
                
                if doc_match:
                    doc_text = doc_match.group(1).strip().replace('\n', ' ')
                    confidence: Literal["high", "medium", "low"] = "medium"
                    
                    if conf_match:
                        conf_str = conf_match.group(1).lower()
                        if conf_str in ("high", "medium", "low"):
                            confidence = conf_str  # type: ignore
                    
                    # elem_num is 1-indexed, array is 0-indexed
                    idx = elem_num - 1
                    if 0 <= idx < len(missing_docs):
                        results.append(
                            GeneratedDoc(
                                path=missing_docs[idx].path,
                                element_type=missing_docs[idx].element_type,
                                documentation=doc_text,
                                confidence=confidence,
                            )
                        )
        return results
    
    # Fallback: try splitting by --- separators
    blocks = response.split("---")
    for i, block in enumerate(blocks):
        if i >= len(missing_docs):
            break

        block = block.strip()
        if not block:
            continue

        doc_line = ""
        confidence = "medium"

        for line in block.split("\n"):
            line = line.strip()
            if line.startswith("DOC:"):
                doc_line = line[4:].strip()
            elif line.startswith("CONFIDENCE:"):
                conf_str = line[11:].strip().lower()
                if conf_str in ("high", "medium", "low"):
                    confidence = conf_str

        if doc_line and i < len(missing_docs):
            results.append(
                GeneratedDoc(
                    path=missing_docs[i].path,
                    element_type=missing_docs[i].element_type,
                    documentation=doc_line,
                    confidence=confidence,  # type: ignore
                )
            )

    return results


class BaseLLMClient(ABC):
    """Abstract base class for LLM clients."""

    def __init__(self, config: LLMProviderConfig, llm_config: LLMConfig):
        self.config = config
        self.llm_config = llm_config

    @abstractmethod
    def _call_api(self, system_prompt: str, user_prompt: str) -> str:
        """Make the actual API call. Returns the response text."""
        pass

    def generate_documentation(
        self, missing_docs: list[MissingDoc], schema_context: dict
    ) -> list[GeneratedDoc]:
        """Generate documentation for missing doc fields."""
        if not missing_docs:
            return []

        results = []
        batch_size = self.llm_config.batch_size

        for i in range(0, len(missing_docs), batch_size):
            batch = missing_docs[i : i + batch_size]
            prompt = build_prompt(batch, schema_context)
            response = self._call_api(SYSTEM_PROMPT, prompt)
            batch_results = parse_response(response, batch)
            results.extend(batch_results)

        return results


class OpenAIClient(BaseLLMClient):
    """Client for OpenAI models (GPT-4o-mini, GPT-4o, etc.)."""

    def __init__(self, config: LLMProviderConfig, llm_config: LLMConfig):
        super().__init__(config, llm_config)
        from openai import OpenAI

        kwargs = {"api_key": config.api_key}
        if config.base_url:
            kwargs["base_url"] = config.base_url

        self.client = OpenAI(**kwargs)

    def _call_api(self, system_prompt: str, user_prompt: str) -> str:
        response = self.client.chat.completions.create(
            model=self.config.model,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            temperature=self.llm_config.temperature,
        )
        return response.choices[0].message.content or ""


class AnthropicClient(BaseLLMClient):
    """Client for Anthropic models (Claude Haiku, Sonnet, Opus)."""

    def __init__(self, config: LLMProviderConfig, llm_config: LLMConfig):
        super().__init__(config, llm_config)
        from anthropic import Anthropic

        self.client = Anthropic(api_key=config.api_key)

    def _call_api(self, system_prompt: str, user_prompt: str) -> str:
        response = self.client.messages.create(
            model=self.config.model,
            max_tokens=2048,
            system=system_prompt,
            messages=[{"role": "user", "content": user_prompt}],
        )
        return response.content[0].text if response.content else ""


class GoogleClient(BaseLLMClient):
    """Client for Google Gemini models."""

    def __init__(self, config: LLMProviderConfig, llm_config: LLMConfig):
        super().__init__(config, llm_config)
        import google.generativeai as genai

        genai.configure(api_key=config.api_key)
        self.model = genai.GenerativeModel(
            config.model,
            generation_config=genai.GenerationConfig(
                temperature=llm_config.temperature,
            ),
        )

    def _call_api(self, system_prompt: str, user_prompt: str) -> str:
        # Gemini combines system + user into a single prompt
        full_prompt = f"{system_prompt}\n\n---\n\n{user_prompt}"
        response = self.model.generate_content(full_prompt)
        return response.text or ""


class MistralClient(BaseLLMClient):
    """Client for Mistral AI models."""

    def __init__(self, config: LLMProviderConfig, llm_config: LLMConfig):
        super().__init__(config, llm_config)
        from mistralai import Mistral

        self.client = Mistral(api_key=config.api_key)

    def _call_api(self, system_prompt: str, user_prompt: str) -> str:
        response = self.client.chat.complete(
            model=self.config.model,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            temperature=self.llm_config.temperature,
        )
        return response.choices[0].message.content or ""


class OllamaClient(BaseLLMClient):
    """Client for Ollama (local models)."""

    def __init__(self, config: LLMProviderConfig, llm_config: LLMConfig):
        super().__init__(config, llm_config)
        import ollama

        self.client = ollama.Client(host=config.base_url or "http://localhost:11434")

    def _call_api(self, system_prompt: str, user_prompt: str) -> str:
        response = self.client.chat(
            model=self.config.model,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            options={"temperature": self.llm_config.temperature},
        )
        return response["message"]["content"] or ""


class AzureOpenAIClient(BaseLLMClient):
    """Client for Azure OpenAI Service."""

    def __init__(self, config: LLMProviderConfig, llm_config: LLMConfig):
        super().__init__(config, llm_config)
        from openai import AzureOpenAI

        self.client = AzureOpenAI(
            api_key=config.api_key,
            azure_endpoint=config.base_url,
            api_version=config.extra.get("api_version", "2024-02-01"),
        )

    def _call_api(self, system_prompt: str, user_prompt: str) -> str:
        response = self.client.chat.completions.create(
            model=self.config.model,  # This is the deployment name in Azure
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            temperature=self.llm_config.temperature,
        )
        return response.choices[0].message.content or ""


# Registry of available providers
PROVIDERS: dict[str, type[BaseLLMClient]] = {
    "openai": OpenAIClient,
    "anthropic": AnthropicClient,
    "google": GoogleClient,
    "mistral": MistralClient,
    "ollama": OllamaClient,
    "azure": AzureOpenAIClient,
}

# Default models per provider
DEFAULT_MODELS: dict[str, str] = {
    "openai": "gpt-4o-mini",
    "anthropic": "claude-3-haiku-20240307",
    "google": "gemini-1.5-flash",
    "mistral": "mistral-small-latest",
    "ollama": "llama3.2",
    "azure": "gpt-4o-mini",
}


def get_available_providers() -> list[str]:
    """Get list of available LLM providers."""
    return list(PROVIDERS.keys())


def create_llm_client(
    provider: str,
    llm_config: LLMConfig,
    provider_config: LLMProviderConfig | None = None,
) -> BaseLLMClient:
    """
    Factory function to create the appropriate LLM client.

    Args:
        provider: Provider name (openai, anthropic, google, mistral, ollama, azure)
        llm_config: Overall LLM configuration
        provider_config: Optional override for provider-specific config

    Returns:
        Configured LLM client instance
    """
    if provider not in PROVIDERS:
        available = ", ".join(PROVIDERS.keys())
        raise ValueError(f"Unknown provider: {provider}. Available: {available}")

    # Get provider config from llm_config if not provided
    if provider_config is None:
        provider_config = llm_config.providers.get(provider, LLMProviderConfig())

    # Set default model if not specified
    if not provider_config.model:
        provider_config.model = DEFAULT_MODELS.get(provider, "")

    # Validate API key for cloud providers
    if provider not in ("ollama",) and not provider_config.api_key:
        raise ValueError(f"API key required for {provider}")

    client_class = PROVIDERS[provider]
    return client_class(provider_config, llm_config)
