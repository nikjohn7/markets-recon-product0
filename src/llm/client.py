"""Multi-provider LLM client with unified interface for pipeline stages.

Supports multiple providers:
- Anthropic (Claude Haiku 4.5) - Native SDK
- MegaLLM (GPT-OSS-120b) - OpenAI-compatible API
- Nebius (GLM-4.5-Air) - OpenAI-compatible API
- DeepInfra (Qwen3-235B) - OpenAI-compatible API
"""

from __future__ import annotations

import asyncio
import hashlib
import json
import logging
from dataclasses import dataclass
from enum import Enum
from typing import TYPE_CHECKING, TypeVar

import anthropic
from anthropic import AsyncAnthropic
from openai import APIConnectionError, APIError, AsyncOpenAI, RateLimitError
from pydantic import BaseModel

from src.config.settings import get_settings
from src.exceptions import LLMError

if TYPE_CHECKING:
    from openai.types.chat import ChatCompletionMessageParam

logger = logging.getLogger(__name__)

T = TypeVar("T", bound=BaseModel)


class LLMProvider(str, Enum):
    """Supported LLM providers."""

    ANTHROPIC = "anthropic"  # Claude Haiku 4.5
    MEGALLM = "megallm"  # GPT-OSS-120b
    NEBIUS = "nebius"  # GLM-4.5-Air
    DEEPINFRA = "deepinfra"  # Qwen3-235B


class PipelineStage(str, Enum):
    """Pipeline stages that use LLM."""

    METADATA = "metadata"  # S4
    CANDIDATES = "candidates"  # S5
    CALLS = "calls"  # S6
    VERIFICATION = "verification"  # S6 verification pass
    SUMMARIES = "summaries"  # S7
    TOOLTIPS = "tooltips"  # S8
    TAGS = "tags"  # S9


@dataclass(frozen=True)
class ProviderConfig:
    """Configuration for an LLM provider."""

    base_url: str
    model_name: str
    default_temperature: float = 0.0
    max_tokens: int = 4096


# Provider configurations
PROVIDER_CONFIGS: dict[LLMProvider, ProviderConfig] = {
    LLMProvider.ANTHROPIC: ProviderConfig(
        base_url="",  # Not used - native SDK
        model_name="claude-haiku-4-5-20241022",
        default_temperature=0.0,
    ),
    LLMProvider.MEGALLM: ProviderConfig(
        base_url="https://ai.megallm.io/v1",
        model_name="openai-gpt-oss-120b",
        default_temperature=0.0,
    ),
    LLMProvider.NEBIUS: ProviderConfig(
        base_url="https://api.tokenfactory.nebius.com/v1/",
        model_name="zai-org/GLM-4.5-Air",
        default_temperature=0.0,
    ),
    LLMProvider.DEEPINFRA: ProviderConfig(
        base_url="https://api.deepinfra.com/v1/openai",
        model_name="Qwen/Qwen3-235B-A22B-Instruct-2507",
        default_temperature=0.6,  # Qwen works better with 0.5-0.7
    ),
}


# Stage to provider mapping
STAGE_PROVIDER_MAP: dict[PipelineStage, LLMProvider] = {
    PipelineStage.METADATA: LLMProvider.ANTHROPIC,  # Claude Haiku 4.5
    PipelineStage.CANDIDATES: LLMProvider.MEGALLM,  # GPT-OSS-120b
    PipelineStage.CALLS: LLMProvider.ANTHROPIC,  # Claude Haiku 4.5
    PipelineStage.VERIFICATION: LLMProvider.NEBIUS,  # GLM-4.5-Air
    PipelineStage.SUMMARIES: LLMProvider.NEBIUS,  # GLM-4.5-Air
    PipelineStage.TOOLTIPS: LLMProvider.DEEPINFRA,  # Qwen3-235B
    PipelineStage.TAGS: LLMProvider.DEEPINFRA,  # Qwen3-235B
}


class LLMClient:
    """Multi-provider LLM client with unified interface.

    Supports automatic provider selection based on pipeline stage,
    or explicit provider selection for flexibility.

    Attributes:
        openai_clients: Dict of AsyncOpenAI clients per provider (MegaLLM, Nebius, DeepInfra)
        anthropic_client: AsyncAnthropic client for Anthropic provider
        max_retries: Maximum number of retry attempts on rate limits
        base_delay: Base delay in seconds for exponential backoff
    """

    def __init__(
        self,
        api_keys: dict[LLMProvider, str] | None = None,
        max_retries: int = 3,
        base_delay: float = 1.0,
    ):
        """Initialize the multi-provider LLM client.

        Args:
            api_keys: Dict mapping providers to API keys (if None, loaded from settings)
            max_retries: Maximum retry attempts on rate limits
            base_delay: Base delay in seconds for exponential backoff
        """
        self.max_retries = max_retries
        self.base_delay = base_delay
        self.openai_clients: dict[LLMProvider, AsyncOpenAI] = {}
        self.anthropic_client: AsyncAnthropic | None = None

        # Load API keys from settings if not provided
        if api_keys is None:
            settings = get_settings()
            api_keys = {
                LLMProvider.ANTHROPIC: settings.anthropic_api_key.get_secret_value(),
                LLMProvider.MEGALLM: settings.megallm_api_key.get_secret_value(),
                LLMProvider.NEBIUS: settings.nebius_api_key.get_secret_value(),
                LLMProvider.DEEPINFRA: settings.deepinfra_api_key.get_secret_value(),
            }

        # Initialize Anthropic client separately (native SDK)
        if LLMProvider.ANTHROPIC in api_keys:
            self.anthropic_client = AsyncAnthropic(
                api_key=api_keys[LLMProvider.ANTHROPIC],
            )

        # Initialize OpenAI-compatible clients for other providers
        for provider, config in PROVIDER_CONFIGS.items():
            if provider == LLMProvider.ANTHROPIC:
                continue  # Skip - handled above with native SDK
            if provider in api_keys:
                self.openai_clients[provider] = AsyncOpenAI(
                    api_key=api_keys[provider],
                    base_url=config.base_url,
                )

    def get_provider_for_stage(self, stage: PipelineStage) -> LLMProvider:
        """Get the configured provider for a pipeline stage.

        Args:
            stage: The pipeline stage

        Returns:
            The LLM provider to use for this stage
        """
        return STAGE_PROVIDER_MAP[stage]

    def get_config(self, provider: LLMProvider) -> ProviderConfig:
        """Get configuration for a provider.

        Args:
            provider: The LLM provider

        Returns:
            Provider configuration
        """
        return PROVIDER_CONFIGS[provider]

    async def complete(
        self,
        prompt: str,
        stage: PipelineStage | None = None,
        provider: LLMProvider | None = None,
        max_tokens: int | None = None,
        temperature: float | None = None,
        system_prompt: str | None = None,
    ) -> str:
        """Call LLM with automatic provider selection based on stage.

        Args:
            prompt: The prompt text to send
            stage: Pipeline stage (auto-selects provider if specified)
            provider: Explicit provider override (takes precedence over stage)
            max_tokens: Maximum tokens in response (defaults to provider config)
            temperature: Sampling temperature (defaults to provider config)
            system_prompt: Optional system prompt

        Returns:
            The model's response text

        Raises:
            LLMError: If API call fails after all retries
            ValueError: If neither stage nor provider specified
        """
        # Determine provider
        if provider is None:
            if stage is None:
                raise ValueError("Either stage or provider must be specified")
            provider = self.get_provider_for_stage(stage)

        config = self.get_config(provider)

        # Use defaults from config if not specified
        max_tokens = max_tokens or config.max_tokens
        temperature = temperature if temperature is not None else config.default_temperature

        # Route to appropriate implementation
        if provider == LLMProvider.ANTHROPIC:
            return await self._complete_anthropic(
                prompt=prompt,
                stage=stage,
                max_tokens=max_tokens,
                temperature=temperature,
                system_prompt=system_prompt,
            )
        else:
            return await self._complete_openai(
                prompt=prompt,
                provider=provider,
                stage=stage,
                max_tokens=max_tokens,
                temperature=temperature,
                system_prompt=system_prompt,
            )

    async def _complete_anthropic(
        self,
        prompt: str,
        stage: PipelineStage | None,
        max_tokens: int,
        temperature: float,
        system_prompt: str | None,
    ) -> str:
        """Call Anthropic API using native SDK.

        Args:
            prompt: The prompt text to send
            stage: Pipeline stage for logging
            max_tokens: Maximum tokens in response
            temperature: Sampling temperature
            system_prompt: Optional system prompt

        Returns:
            The model's response text

        Raises:
            LLMError: If API call fails after all retries
        """
        if self.anthropic_client is None:
            raise LLMError("No API key configured for provider: anthropic")

        config = self.get_config(LLMProvider.ANTHROPIC)
        prompt_hash = self._hash_text(prompt)
        prompt_tokens = self.count_tokens(prompt)

        # Safe logging
        logger.info(
            "LLM request",
            extra={
                "provider": "anthropic",
                "model": config.model_name,
                "stage": stage.value if stage else None,
                "prompt_hash": prompt_hash,
                "prompt_tokens": prompt_tokens,
                "max_tokens": max_tokens,
                "temperature": temperature,
            },
        )

        if logger.isEnabledFor(logging.DEBUG):
            preview = self._truncate_text(prompt, max_length=200)
            logger.debug(f"Prompt preview: {preview}")

        # Build messages - Anthropic format
        messages: list[anthropic.types.MessageParam] = [{"role": "user", "content": prompt}]

        # Build create kwargs - only include system if provided
        create_kwargs: dict[str, object] = {
            "model": config.model_name,
            "max_tokens": max_tokens,
            "temperature": temperature,
            "messages": messages,
        }
        if system_prompt:
            create_kwargs["system"] = system_prompt

        # Retry loop with exponential backoff
        last_error: Exception | None = None
        for attempt in range(self.max_retries):
            try:
                response = await self.anthropic_client.messages.create(**create_kwargs)  # type: ignore[call-overload]

                # Extract text from content blocks
                response_text = self._extract_anthropic_text(response)
                response_hash = self._hash_text(response_text)

                logger.info(
                    "LLM response received",
                    extra={
                        "provider": "anthropic",
                        "model": config.model_name,
                        "response_hash": response_hash,
                        "input_tokens": response.usage.input_tokens,
                        "output_tokens": response.usage.output_tokens,
                    },
                )

                if logger.isEnabledFor(logging.DEBUG):
                    preview = self._truncate_text(response_text, max_length=200)
                    logger.debug(f"Response preview: {preview}")

                return response_text

            except anthropic.RateLimitError as e:
                last_error = e
                if attempt < self.max_retries - 1:
                    delay = self.base_delay * (2**attempt)
                    logger.warning(
                        f"Rate limit hit on anthropic, retrying in {delay}s "
                        f"(attempt {attempt + 1}/{self.max_retries})"
                    )
                    await asyncio.sleep(delay)
                else:
                    logger.error(f"Rate limit exceeded after {self.max_retries} attempts")

            except (anthropic.APIError, anthropic.APIConnectionError) as e:
                last_error = e
                logger.error(f"API error from anthropic: {e}")
                break

            except Exception as e:
                last_error = e
                logger.error(f"Unexpected error during LLM call to anthropic: {e}")
                break

        error_msg = f"LLM API call failed (anthropic): {last_error}"
        raise LLMError(error_msg) from last_error

    def _extract_anthropic_text(self, response: anthropic.types.Message) -> str:
        """Extract text content from Anthropic response.

        Anthropic returns content as a list of content blocks.
        Each block can be TextBlock or ToolUseBlock.
        We concatenate all text blocks.

        Args:
            response: Anthropic Message response

        Returns:
            Concatenated text from all text blocks
        """
        text_parts = []
        for block in response.content:
            if block.type == "text":
                text_parts.append(block.text)
        return "".join(text_parts)

    async def _complete_openai(
        self,
        prompt: str,
        provider: LLMProvider,
        stage: PipelineStage | None,
        max_tokens: int,
        temperature: float,
        system_prompt: str | None,
    ) -> str:
        """Call OpenAI-compatible API.

        Args:
            prompt: The prompt text to send
            provider: The LLM provider to use
            stage: Pipeline stage for logging
            max_tokens: Maximum tokens in response
            temperature: Sampling temperature
            system_prompt: Optional system prompt

        Returns:
            The model's response text

        Raises:
            LLMError: If API call fails after all retries
        """
        if provider not in self.openai_clients:
            raise LLMError(f"No API key configured for provider: {provider.value}")

        config = self.get_config(provider)
        client = self.openai_clients[provider]

        prompt_hash = self._hash_text(prompt)
        prompt_tokens = self.count_tokens(prompt)

        # Safe logging
        logger.info(
            "LLM request",
            extra={
                "provider": provider.value,
                "model": config.model_name,
                "stage": stage.value if stage else None,
                "prompt_hash": prompt_hash,
                "prompt_tokens": prompt_tokens,
                "max_tokens": max_tokens,
                "temperature": temperature,
            },
        )

        if logger.isEnabledFor(logging.DEBUG):
            preview = self._truncate_text(prompt, max_length=200)
            logger.debug(f"Prompt preview: {preview}")

        # Build messages
        messages: list[ChatCompletionMessageParam] = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})

        # Retry loop with exponential backoff
        last_error: Exception | None = None
        for attempt in range(self.max_retries):
            try:
                response = await client.chat.completions.create(
                    model=config.model_name,
                    messages=messages,
                    max_tokens=max_tokens,
                    temperature=temperature,
                )

                response_text = response.choices[0].message.content or ""
                response_hash = self._hash_text(response_text)

                logger.info(
                    "LLM response received",
                    extra={
                        "provider": provider.value,
                        "model": config.model_name,
                        "response_hash": response_hash,
                        "prompt_tokens": response.usage.prompt_tokens if response.usage else None,
                        "completion_tokens": response.usage.completion_tokens
                        if response.usage
                        else None,
                    },
                )

                if logger.isEnabledFor(logging.DEBUG):
                    preview = self._truncate_text(response_text, max_length=200)
                    logger.debug(f"Response preview: {preview}")

                return response_text

            except RateLimitError as e:
                last_error = e
                if attempt < self.max_retries - 1:
                    delay = self.base_delay * (2**attempt)
                    logger.warning(
                        f"Rate limit hit on {provider.value}, retrying in {delay}s "
                        f"(attempt {attempt + 1}/{self.max_retries})"
                    )
                    await asyncio.sleep(delay)
                else:
                    logger.error(f"Rate limit exceeded after {self.max_retries} attempts")

            except (APIError, APIConnectionError) as e:
                last_error = e
                logger.error(f"API error from {provider.value}: {e}")
                break

            except Exception as e:
                last_error = e
                logger.error(f"Unexpected error during LLM call to {provider.value}: {e}")
                break

        error_msg = f"LLM API call failed ({provider.value}): {last_error}"
        raise LLMError(error_msg) from last_error

    async def complete_json(
        self,
        prompt: str,
        response_model: type[T],
        stage: PipelineStage | None = None,
        provider: LLMProvider | None = None,
        max_tokens: int | None = None,
        temperature: float | None = None,
        system_prompt: str | None = None,
    ) -> T:
        """Call LLM and parse response as JSON matching a Pydantic model.

        Args:
            prompt: The prompt text to send
            response_model: Pydantic model class to validate response against
            stage: Pipeline stage (auto-selects provider if specified)
            provider: Explicit provider override
            max_tokens: Maximum tokens in response
            temperature: Sampling temperature
            system_prompt: Optional system prompt

        Returns:
            Validated Pydantic model instance

        Raises:
            LLMError: If API call fails or response doesn't match schema
        """
        schema = response_model.model_json_schema()
        enhanced_prompt = f"""{prompt}

## Output Schema
Return ONLY valid JSON matching this schema (no explanation, no markdown, no code blocks):

{json.dumps(schema, indent=2)}

## Output (JSON only)
"""

        try:
            response_text = await self.complete(
                prompt=enhanced_prompt,
                stage=stage,
                provider=provider,
                max_tokens=max_tokens,
                temperature=temperature,
                system_prompt=system_prompt,
            )

            # Clean response - remove markdown code blocks if present
            response_text = self._clean_json_response(response_text)

            # Parse and validate JSON
            validated = response_model.model_validate_json(response_text)
            logger.info(
                "JSON response validated",
                extra={"model_type": response_model.__name__},
            )
            return validated

        except Exception as e:
            if isinstance(e, LLMError):
                raise
            error_msg = f"Failed to validate LLM response against {response_model.__name__}: {e}"
            logger.error(error_msg)
            raise LLMError(error_msg) from e

    def _clean_json_response(self, text: str) -> str:
        """Clean JSON response by removing markdown code blocks.

        Args:
            text: Raw response text

        Returns:
            Cleaned JSON string
        """
        text = text.strip()

        # Remove markdown code blocks
        if text.startswith("```json"):
            text = text[7:]
        elif text.startswith("```"):
            text = text[3:]

        if text.endswith("```"):
            text = text[:-3]

        return text.strip()

    def count_tokens(self, text: str) -> int:
        """Estimate token count for text.

        Uses a simple heuristic: ~4 characters per token.

        Args:
            text: The text to count tokens for

        Returns:
            Estimated token count
        """
        return len(text) // 4

    def _hash_text(self, text: str) -> str:
        """Compute SHA-256 hash of text for logging.

        Args:
            text: Text to hash

        Returns:
            Hex digest of hash (first 16 characters)
        """
        return hashlib.sha256(text.encode()).hexdigest()[:16]

    def _truncate_text(self, text: str, max_length: int = 200) -> str:
        """Truncate text for debug logging.

        Args:
            text: Text to truncate
            max_length: Maximum length

        Returns:
            Truncated text with ellipsis if needed
        """
        if len(text) <= max_length:
            return text
        return text[:max_length] + "..."


# Convenience function for quick access
def get_stage_model_info(stage: PipelineStage) -> tuple[LLMProvider, str]:
    """Get provider and model name for a pipeline stage.

    Args:
        stage: The pipeline stage

    Returns:
        Tuple of (provider, model_name)
    """
    provider = STAGE_PROVIDER_MAP[stage]
    config = PROVIDER_CONFIGS[provider]
    return provider, config.model_name
