"""Unit tests for multi-provider LLM client."""

from __future__ import annotations

import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from anthropic.types import Message, TextBlock, Usage
from openai.types.chat import ChatCompletion, ChatCompletionMessage
from openai.types.chat.chat_completion import Choice
from openai.types.completion_usage import CompletionUsage
from pydantic import BaseModel
from src.llm.client import (
    PROVIDER_CONFIGS,
    STAGE_PROVIDER_MAP,
    LLMClient,
    LLMProvider,
    PipelineStage,
    get_stage_model_info,
)


class SampleResponse(BaseModel):
    """Sample Pydantic model for testing JSON responses."""

    asset_class: str
    direction: str
    confidence: float


@pytest.fixture
def mock_api_keys() -> dict[LLMProvider, str]:
    """Mock API keys for testing."""
    return {
        LLMProvider.ANTHROPIC: "test-anthropic-key",
        LLMProvider.MEGALLM: "test-megallm-key",
        LLMProvider.NEBIUS: "test-nebius-key",
        LLMProvider.DEEPINFRA: "test-deepinfra-key",
    }


@pytest.fixture
def llm_client(mock_api_keys: dict[LLMProvider, str]) -> LLMClient:
    """Create an LLM client instance for testing."""
    return LLMClient(api_keys=mock_api_keys)


@pytest.fixture
def mock_completion() -> ChatCompletion:
    """Create a mock OpenAI ChatCompletion response."""
    return ChatCompletion(
        id="chatcmpl-123",
        choices=[
            Choice(
                finish_reason="stop",
                index=0,
                message=ChatCompletionMessage(
                    content="This is a test response",
                    role="assistant",
                ),
            )
        ],
        created=1234567890,
        model="test-model",
        object="chat.completion",
        usage=CompletionUsage(
            completion_tokens=50,
            prompt_tokens=100,
            total_tokens=150,
        ),
    )


@pytest.fixture
def mock_json_completion() -> ChatCompletion:
    """Create a mock ChatCompletion with JSON content."""
    json_response = {
        "asset_class": "EQUITIES",
        "direction": "OVERWEIGHT",
        "confidence": 0.85,
    }
    return ChatCompletion(
        id="chatcmpl-456",
        choices=[
            Choice(
                finish_reason="stop",
                index=0,
                message=ChatCompletionMessage(
                    content=json.dumps(json_response),
                    role="assistant",
                ),
            )
        ],
        created=1234567890,
        model="test-model",
        object="chat.completion",
        usage=CompletionUsage(
            completion_tokens=25,
            prompt_tokens=150,
            total_tokens=175,
        ),
    )


@pytest.fixture
def mock_anthropic_message() -> Message:
    """Create a mock Anthropic Message response."""
    return Message(
        id="msg_123",
        type="message",
        role="assistant",
        content=[TextBlock(type="text", text="This is a test response")],
        model="claude-haiku-4-5-20241022",
        stop_reason="end_turn",
        usage=Usage(input_tokens=100, output_tokens=50),
    )


@pytest.fixture
def mock_anthropic_json_message() -> Message:
    """Create a mock Anthropic Message with JSON content."""
    json_response = {
        "asset_class": "EQUITIES",
        "direction": "OVERWEIGHT",
        "confidence": 0.85,
    }
    return Message(
        id="msg_456",
        type="message",
        role="assistant",
        content=[TextBlock(type="text", text=json.dumps(json_response))],
        model="claude-haiku-4-5-20241022",
        stop_reason="end_turn",
        usage=Usage(input_tokens=150, output_tokens=25),
    )


class TestLLMClientInitialization:
    """Test LLM client initialization."""

    def test_init_with_api_keys(self, mock_api_keys: dict[LLMProvider, str]):
        """Test initialization with explicit API keys."""
        client = LLMClient(api_keys=mock_api_keys)
        # Anthropic uses separate client (native SDK)
        assert client.anthropic_client is not None
        # Other providers use OpenAI-compatible clients
        assert LLMProvider.MEGALLM in client.openai_clients
        assert LLMProvider.NEBIUS in client.openai_clients
        assert LLMProvider.DEEPINFRA in client.openai_clients
        # Anthropic should NOT be in openai_clients
        assert LLMProvider.ANTHROPIC not in client.openai_clients

    def test_init_with_custom_settings(self, mock_api_keys: dict[LLMProvider, str]):
        """Test initialization with custom retry settings."""
        client = LLMClient(
            api_keys=mock_api_keys,
            max_retries=5,
            base_delay=2.0,
        )
        assert client.max_retries == 5
        assert client.base_delay == 2.0


class TestProviderConfiguration:
    """Test provider configuration and mapping."""

    def test_all_providers_configured(self):
        """Test that all providers have configurations."""
        for provider in LLMProvider:
            assert provider in PROVIDER_CONFIGS
            config = PROVIDER_CONFIGS[provider]
            # Anthropic has empty base_url (uses native SDK)
            if provider != LLMProvider.ANTHROPIC:
                assert config.base_url
            assert config.model_name

    def test_all_stages_have_provider(self):
        """Test that all pipeline stages have a provider mapping."""
        for stage in PipelineStage:
            assert stage in STAGE_PROVIDER_MAP
            provider = STAGE_PROVIDER_MAP[stage]
            assert provider in LLMProvider

    def test_get_provider_for_stage(self, llm_client: LLMClient):
        """Test getting provider for each stage."""
        assert llm_client.get_provider_for_stage(PipelineStage.METADATA) == LLMProvider.ANTHROPIC
        assert llm_client.get_provider_for_stage(PipelineStage.CANDIDATES) == LLMProvider.MEGALLM
        assert llm_client.get_provider_for_stage(PipelineStage.CALLS) == LLMProvider.ANTHROPIC
        assert llm_client.get_provider_for_stage(PipelineStage.VERIFICATION) == LLMProvider.NEBIUS
        assert llm_client.get_provider_for_stage(PipelineStage.SUMMARIES) == LLMProvider.NEBIUS
        assert llm_client.get_provider_for_stage(PipelineStage.TOOLTIPS) == LLMProvider.DEEPINFRA
        assert llm_client.get_provider_for_stage(PipelineStage.TAGS) == LLMProvider.DEEPINFRA

    def test_get_stage_model_info(self):
        """Test the get_stage_model_info helper function."""
        provider, model = get_stage_model_info(PipelineStage.METADATA)
        assert provider == LLMProvider.ANTHROPIC
        assert model == "claude-haiku-4-5-20241022"

        provider, model = get_stage_model_info(PipelineStage.TAGS)
        assert provider == LLMProvider.DEEPINFRA
        assert model == "Qwen/Qwen3-235B-A22B-Instruct-2507"

    def test_provider_configs(self):
        """Test specific provider configurations."""
        # Anthropic - Claude Haiku (native SDK, no base_url)
        config = PROVIDER_CONFIGS[LLMProvider.ANTHROPIC]
        assert config.base_url == ""  # Not used for native SDK
        assert "claude-haiku" in config.model_name
        assert config.default_temperature == 0.0

        # DeepInfra - Qwen (should have higher temperature)
        config = PROVIDER_CONFIGS[LLMProvider.DEEPINFRA]
        assert "deepinfra.com" in config.base_url
        assert "Qwen" in config.model_name
        assert config.default_temperature == 0.6


class TestLLMClientComplete:
    """Test the complete() method."""

    @pytest.mark.asyncio
    async def test_successful_completion_with_anthropic(
        self,
        llm_client: LLMClient,
        mock_anthropic_message: Message,
    ):
        """Test successful API completion using Anthropic native SDK."""
        with patch.object(
            llm_client.anthropic_client.messages,
            "create",
            new_callable=AsyncMock,
        ) as mock_create:
            mock_create.return_value = mock_anthropic_message

            response = await llm_client.complete(
                prompt="Test prompt",
                stage=PipelineStage.METADATA,  # Uses ANTHROPIC
            )

            assert response == "This is a test response"
            mock_create.assert_called_once()
            # Verify Anthropic-specific call signature
            call_kwargs = mock_create.call_args.kwargs
            assert "model" in call_kwargs
            assert "messages" in call_kwargs
            assert call_kwargs["messages"][0]["role"] == "user"

    @pytest.mark.asyncio
    async def test_successful_completion_with_openai_provider(
        self,
        llm_client: LLMClient,
        mock_completion: ChatCompletion,
    ):
        """Test successful API completion with OpenAI-compatible provider."""
        with patch.object(
            llm_client.openai_clients[LLMProvider.NEBIUS].chat.completions,
            "create",
            new_callable=AsyncMock,
        ) as mock_create:
            mock_create.return_value = mock_completion

            response = await llm_client.complete(
                prompt="Test prompt",
                provider=LLMProvider.NEBIUS,
            )

            assert response == "This is a test response"
            mock_create.assert_called_once()

    @pytest.mark.asyncio
    async def test_error_when_no_stage_or_provider(self, llm_client: LLMClient):
        """Test that ValueError is raised when neither stage nor provider specified."""
        with pytest.raises(ValueError, match="Either stage or provider must be specified"):
            await llm_client.complete(prompt="Test prompt")

    @pytest.mark.asyncio
    async def test_provider_overrides_stage(
        self,
        llm_client: LLMClient,
        mock_completion: ChatCompletion,
    ):
        """Test that explicit provider overrides stage-based routing."""
        # Stage METADATA would use ANTHROPIC, but we explicitly specify NEBIUS
        with patch.object(
            llm_client.openai_clients[LLMProvider.NEBIUS].chat.completions,
            "create",
            new_callable=AsyncMock,
        ) as mock_create:
            mock_create.return_value = mock_completion

            response = await llm_client.complete(
                prompt="Test prompt",
                stage=PipelineStage.METADATA,  # Would use ANTHROPIC
                provider=LLMProvider.NEBIUS,  # But we override
            )

            assert response == "This is a test response"
            mock_create.assert_called_once()

    @pytest.mark.asyncio
    async def test_anthropic_system_prompt_handling(
        self,
        llm_client: LLMClient,
        mock_anthropic_message: Message,
    ):
        """Test that system prompts are passed correctly to Anthropic."""
        with patch.object(
            llm_client.anthropic_client.messages,
            "create",
            new_callable=AsyncMock,
        ) as mock_create:
            mock_create.return_value = mock_anthropic_message

            await llm_client.complete(
                prompt="Test prompt",
                provider=LLMProvider.ANTHROPIC,
                system_prompt="You are a helpful assistant.",
            )

            call_kwargs = mock_create.call_args.kwargs
            assert call_kwargs["system"] == "You are a helpful assistant."


class TestLLMClientCompleteJSON:
    """Test the complete_json() method."""

    @pytest.mark.asyncio
    async def test_successful_json_parsing_anthropic(
        self,
        llm_client: LLMClient,
        mock_anthropic_json_message: Message,
    ):
        """Test successful JSON response parsing with Anthropic."""
        with patch.object(
            llm_client.anthropic_client.messages,
            "create",
            new_callable=AsyncMock,
        ) as mock_create:
            mock_create.return_value = mock_anthropic_json_message

            result = await llm_client.complete_json(
                prompt="Extract allocation calls",
                response_model=SampleResponse,
                stage=PipelineStage.CALLS,  # Uses ANTHROPIC
            )

            assert isinstance(result, SampleResponse)
            assert result.asset_class == "EQUITIES"
            assert result.direction == "OVERWEIGHT"
            assert result.confidence == 0.85

    @pytest.mark.asyncio
    async def test_json_with_markdown_code_blocks_anthropic(
        self,
        llm_client: LLMClient,
    ):
        """Test JSON parsing handles markdown code blocks with Anthropic."""
        json_in_markdown = (
            '```json\n{"asset_class": "BONDS", "direction": "NEUTRAL", "confidence": 0.7}\n```'
        )
        mock_message = Message(
            id="msg_789",
            type="message",
            role="assistant",
            content=[TextBlock(type="text", text=json_in_markdown)],
            model="claude-haiku-4-5-20241022",
            stop_reason="end_turn",
            usage=Usage(input_tokens=50, output_tokens=10),
        )

        with patch.object(
            llm_client.anthropic_client.messages,
            "create",
            new_callable=AsyncMock,
        ) as mock_create:
            mock_create.return_value = mock_message

            result = await llm_client.complete_json(
                prompt="Extract",
                response_model=SampleResponse,
                stage=PipelineStage.METADATA,  # Uses ANTHROPIC
            )

            assert result.asset_class == "BONDS"
            assert result.direction == "NEUTRAL"


class TestLLMClientHelperMethods:
    """Test helper methods."""

    def test_count_tokens(self, llm_client: LLMClient):
        """Test token counting heuristic."""
        text = "This is a test string with some words"  # 38 chars
        token_count = llm_client.count_tokens(text)
        assert token_count == 9  # 38 // 4

    def test_hash_text(self, llm_client: LLMClient):
        """Test text hashing for logging."""
        text = "Test prompt text"
        hash1 = llm_client._hash_text(text)
        hash2 = llm_client._hash_text(text)

        # Same text should produce same hash
        assert hash1 == hash2
        # Hash should be 16 characters
        assert len(hash1) == 16

        # Different text should produce different hash
        hash3 = llm_client._hash_text("Different text")
        assert hash1 != hash3

    def test_truncate_text(self, llm_client: LLMClient):
        """Test text truncation for logging."""
        short_text = "Short text"
        assert llm_client._truncate_text(short_text, max_length=100) == short_text

        long_text = "A" * 500
        truncated = llm_client._truncate_text(long_text, max_length=200)
        assert len(truncated) == 203  # 200 chars + "..."
        assert truncated.endswith("...")

    def test_clean_json_response(self, llm_client: LLMClient):
        """Test cleaning JSON responses."""
        # Plain JSON
        assert llm_client._clean_json_response('{"key": "value"}') == '{"key": "value"}'

        # With markdown code block
        assert (
            llm_client._clean_json_response('```json\n{"key": "value"}\n```') == '{"key": "value"}'
        )

        # With generic code block
        assert llm_client._clean_json_response('```\n{"key": "value"}\n```') == '{"key": "value"}'

        # With whitespace
        assert llm_client._clean_json_response('  {"key": "value"}  ') == '{"key": "value"}'

    def test_extract_anthropic_text(self, llm_client: LLMClient):
        """Test extracting text from Anthropic response content blocks."""
        # Single text block
        message = Message(
            id="msg_test",
            type="message",
            role="assistant",
            content=[TextBlock(type="text", text="Hello world")],
            model="test-model",
            stop_reason="end_turn",
            usage=Usage(input_tokens=10, output_tokens=5),
        )
        assert llm_client._extract_anthropic_text(message) == "Hello world"

        # Multiple text blocks
        message_multi = Message(
            id="msg_test2",
            type="message",
            role="assistant",
            content=[
                TextBlock(type="text", text="Part 1"),
                TextBlock(type="text", text=" Part 2"),
            ],
            model="test-model",
            stop_reason="end_turn",
            usage=Usage(input_tokens=10, output_tokens=10),
        )
        assert llm_client._extract_anthropic_text(message_multi) == "Part 1 Part 2"


class TestLLMClientLogging:
    """Test safe logging behavior."""

    @pytest.mark.asyncio
    async def test_logging_does_not_expose_api_key(
        self,
        llm_client: LLMClient,
        mock_anthropic_message: Message,
        caplog: pytest.LogCaptureFixture,
    ):
        """Test that API keys are never logged."""
        with patch.object(
            llm_client.anthropic_client.messages,
            "create",
            new_callable=AsyncMock,
        ) as mock_create:
            mock_create.return_value = mock_anthropic_message

            await llm_client.complete(prompt="Test prompt", stage=PipelineStage.METADATA)

            # Check that no log message contains API keys
            for record in caplog.records:
                msg = record.getMessage()
                assert "test-anthropic-key" not in msg
                assert "test-megallm-key" not in msg
                assert "test-nebius-key" not in msg
                assert "test-deepinfra-key" not in msg
