"""Unit tests for Stage 8 tooltip generation."""

from __future__ import annotations

from datetime import datetime

import pytest
from src.exceptions import ValidationError
from src.models.calls import AllocationCall, CallExtractionOutput
from src.models.core import Citation
from src.models.enums import CallDirection, Conviction, Sentiment
from src.pipeline.stages.s8_tooltips import (
    TooltipGenerationLLM,
    TooltipItem,
    _validate_tooltip_quality,
    stage_tooltips,
)


class DummyLLMClient:
    """Stub LLM client returning a preconfigured response."""

    def __init__(self, response: TooltipGenerationLLM):
        self.response = response
        self.last_prompt: str | None = None
        self.last_stage = None

    async def complete_json(self, prompt: str, response_model, stage):  # noqa: ARG002
        self.last_prompt = prompt
        self.last_stage = stage
        return self.response


def _make_call(
    sub_asset: str,
    direction: CallDirection = CallDirection.OVERWEIGHT,
    category: str = "FIXED_INCOME_SOVEREIGNS_EUROPE",
) -> AllocationCall:
    """Create a minimal AllocationCall for testing."""
    return AllocationCall(
        asset_class_category=category,
        sub_asset_class=sub_asset,
        call=direction,
        conviction=Conviction.MEDIUM,
        time_horizon=None,
        rationale_bullets=["Strong fundamentals", "Positive technicals"],
        key_indicators=[],
        key_risks=["Policy uncertainty"],
        citations=[Citation(chunk_id="doc_0", page=1, text_span="Test citation")],
        confidence=0.85,
        needs_analyst_review=False,
    )


def _make_call_extraction(
    document_id: str,
    calls: list[AllocationCall],
) -> CallExtractionOutput:
    """Create a minimal CallExtractionOutput for testing."""
    return CallExtractionOutput(
        document_id=document_id,
        allocation_calls=calls,
        overall_sentiment=Sentiment.NET_POSITIVE,
        sentiment_rationale=["Strong macro backdrop"],
        sentiment_citations=[Citation(chunk_id="doc_0", page=1, text_span="Positive outlook")],
        sentiment_confidence=0.80,
        extraction_timestamp=datetime.now(),
        model_version="test-model-v1",
        total_candidates_reviewed=10,
    )


@pytest.mark.asyncio
async def test_stage_tooltips_success():
    """Test successful tooltip generation for multiple calls."""
    # Arrange
    calls = [
        _make_call("GERMAN_BUNDS", CallDirection.OVERWEIGHT),
        _make_call("US_HY", CallDirection.UNDERWEIGHT, "FIXED_INCOME_CORPORATE_HY"),
    ]
    call_extraction = _make_call_extraction("doc_123", calls)

    llm_response = TooltipGenerationLLM(
        tooltips=[
            TooltipItem(
                sub_asset_class="GERMAN_BUNDS",
                tooltip_text="Overweight Bunds as quality hedge; expects easing inflation and flight-to-safety.",
            ),
            TooltipItem(
                sub_asset_class="US_HY",
                tooltip_text="Underweight US HY on tight spreads; watch Fed policy pivot and recession signals.",
            ),
        ]
    )

    llm_client = DummyLLMClient(llm_response)

    # Act
    result = await stage_tooltips(call_extraction, llm_client=llm_client)

    # Assert
    assert result.document_id == "doc_123"
    assert len(result.allocation_calls) == 2

    # Check first call
    assert result.allocation_calls[0].sub_asset_class == "GERMAN_BUNDS"
    assert result.allocation_calls[0].tooltip_text is not None
    assert "Overweight Bunds" in result.allocation_calls[0].tooltip_text
    assert len(result.allocation_calls[0].tooltip_text) <= 150

    # Check second call
    assert result.allocation_calls[1].sub_asset_class == "US_HY"
    assert result.allocation_calls[1].tooltip_text is not None
    assert "Underweight US HY" in result.allocation_calls[1].tooltip_text
    assert len(result.allocation_calls[1].tooltip_text) <= 150


@pytest.mark.asyncio
async def test_stage_tooltips_no_calls():
    """Test tooltip generation with no calls (edge case)."""
    # Arrange
    call_extraction = _make_call_extraction("doc_456", [])

    # Act
    result = await stage_tooltips(call_extraction)

    # Assert
    assert result.document_id == "doc_456"
    assert len(result.allocation_calls) == 0


@pytest.mark.asyncio
async def test_stage_tooltips_count_mismatch():
    """Test error when tooltip count doesn't match call count."""
    # Arrange
    calls = [
        _make_call("GERMAN_BUNDS"),
        _make_call("US_HY", CallDirection.UNDERWEIGHT),
    ]
    call_extraction = _make_call_extraction("doc_789", calls)

    # LLM returns only 1 tooltip instead of 2
    llm_response = TooltipGenerationLLM(
        tooltips=[
            TooltipItem(
                sub_asset_class="GERMAN_BUNDS",
                tooltip_text="Overweight Bunds as quality hedge.",
            ),
        ]
    )

    llm_client = DummyLLMClient(llm_response)

    # Act & Assert
    with pytest.raises(ValidationError, match="Tooltip count mismatch"):
        await stage_tooltips(call_extraction, llm_client=llm_client)


@pytest.mark.asyncio
async def test_stage_tooltips_missing_asset():
    """Test error when tooltip is missing for a call's asset."""
    # Arrange
    calls = [
        _make_call("GERMAN_BUNDS"),
        _make_call("US_HY", CallDirection.UNDERWEIGHT),
    ]
    call_extraction = _make_call_extraction("doc_101", calls)

    # LLM returns tooltip for wrong asset
    llm_response = TooltipGenerationLLM(
        tooltips=[
            TooltipItem(
                sub_asset_class="GERMAN_BUNDS",
                tooltip_text="Overweight Bunds as quality hedge.",
            ),
            TooltipItem(
                sub_asset_class="WRONG_ASSET",  # Wrong asset!
                tooltip_text="Some tooltip text.",
            ),
        ]
    )

    llm_client = DummyLLMClient(llm_response)

    # Act & Assert
    with pytest.raises(ValidationError, match="sub_asset_class mismatch.*expected US_HY"):
        await stage_tooltips(call_extraction, llm_client=llm_client)


def test_validate_tooltip_quality_valid():
    """Test tooltip validation with valid tooltip."""
    # Arrange
    tooltip = "Overweight Bunds as quality hedge; expects easing inflation."

    # Act & Assert - should not raise
    _validate_tooltip_quality(tooltip, "GERMAN_BUNDS")


def test_validate_tooltip_quality_char_limit_exceeded():
    """Test tooltip validation when character limit is exceeded."""
    # Arrange - 151 characters (exceeds 150 limit)
    tooltip = "A" * 151

    # Act & Assert
    with pytest.raises(ValidationError, match="exceeds 150 characters"):
        _validate_tooltip_quality(tooltip, "GERMAN_BUNDS")


def test_validate_tooltip_quality_word_count_warning(caplog):
    """Test tooltip validation logs warning when word count exceeds 25."""
    # Arrange - 30 words
    tooltip = " ".join(["word"] * 30)  # 30 words, but under char limit

    # Act
    _validate_tooltip_quality(tooltip, "GERMAN_BUNDS")

    # Assert - should log warning
    assert "exceeds 25 words" in caplog.text


def test_validate_tooltip_quality_generic_pattern_warning(caplog):
    """Test tooltip validation logs warning for generic patterns."""
    # Arrange - generic tooltip
    tooltip = "Positive on bonds."

    # Act
    _validate_tooltip_quality(tooltip, "GERMAN_BUNDS")

    # Assert - should log warning
    assert "may be too generic" in caplog.text


@pytest.mark.asyncio
async def test_stage_tooltips_mutates_in_place():
    """Test that stage_tooltips mutates CallExtractionOutput in place."""
    # Arrange
    calls = [_make_call("GERMAN_BUNDS")]
    call_extraction = _make_call_extraction("doc_202", calls)

    llm_response = TooltipGenerationLLM(
        tooltips=[
            TooltipItem(
                sub_asset_class="GERMAN_BUNDS",
                tooltip_text="Test tooltip text.",
            ),
        ]
    )

    llm_client = DummyLLMClient(llm_response)

    # Store original reference
    original_call = call_extraction.allocation_calls[0]

    # Act
    result = await stage_tooltips(call_extraction, llm_client=llm_client)

    # Assert - same object reference (mutated in place)
    assert result is call_extraction
    assert result.allocation_calls[0] is original_call
    assert original_call.tooltip_text == "Test tooltip text."


@pytest.mark.asyncio
async def test_stage_tooltips_prompt_includes_calls(caplog):  # noqa: ARG001
    """Test that LLM prompt is built correctly with call details."""
    # Arrange
    calls = [_make_call("GERMAN_BUNDS", CallDirection.OVERWEIGHT)]
    call_extraction = _make_call_extraction("doc_303", calls)

    llm_response = TooltipGenerationLLM(
        tooltips=[
            TooltipItem(
                sub_asset_class="GERMAN_BUNDS",
                tooltip_text="Test tooltip.",
            ),
        ]
    )

    llm_client = DummyLLMClient(llm_response)

    # Act
    await stage_tooltips(call_extraction, llm_client=llm_client)

    # Assert - check prompt was built and passed to LLM
    assert llm_client.last_prompt is not None
    assert "GERMAN_BUNDS" in llm_client.last_prompt
    assert "OVERWEIGHT" in llm_client.last_prompt


@pytest.mark.asyncio
async def test_stage_tooltips_multiple_calls_all_updated():
    """Test all calls get tooltips when multiple calls present."""
    # Arrange - 3 calls
    calls = [
        _make_call("GERMAN_BUNDS", CallDirection.OVERWEIGHT),
        _make_call("US_HY", CallDirection.UNDERWEIGHT, "FIXED_INCOME_CORPORATE_HY"),
        _make_call("EM_EQUITIES", CallDirection.NEUTRAL, "EQUITIES_EM"),
    ]
    call_extraction = _make_call_extraction("doc_404", calls)

    llm_response = TooltipGenerationLLM(
        tooltips=[
            TooltipItem(
                sub_asset_class="GERMAN_BUNDS",
                tooltip_text="Overweight Bunds as quality hedge.",
            ),
            TooltipItem(
                sub_asset_class="US_HY",
                tooltip_text="Underweight US HY on tight spreads.",
            ),
            TooltipItem(
                sub_asset_class="EM_EQUITIES",
                tooltip_text="Neutral on EM equities; balanced outlook.",
            ),
        ]
    )

    llm_client = DummyLLMClient(llm_response)

    # Act
    result = await stage_tooltips(call_extraction, llm_client=llm_client)

    # Assert - all calls have tooltips
    assert len(result.allocation_calls) == 3
    for call in result.allocation_calls:
        assert call.tooltip_text is not None
        assert len(call.tooltip_text) > 0
        assert len(call.tooltip_text) <= 150
