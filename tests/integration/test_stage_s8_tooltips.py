"""Integration tests for Stage 8 - Tooltip generation."""

from __future__ import annotations

from datetime import UTC, datetime

import pytest
from src.exceptions import ValidationError
from src.models.calls import AllocationCall, CallExtractionOutput
from src.models.core import Citation
from src.models.enums import CallDirection, Conviction, Sentiment
from src.pipeline.stages.s8_tooltips import stage_tooltips


def _build_call_extraction() -> CallExtractionOutput:
    calls = [
        AllocationCall(
            asset_class_category="FI_SOV_EUROPE",
            sub_asset_class="GERMAN_BUNDS",
            call=CallDirection.OVERWEIGHT,
            conviction=Conviction.MEDIUM,
            time_horizon="6-12 months",
            rationale_bullets=["ECB easing cycle supports duration demand."],
            key_indicators=[],
            key_risks=["Inflation reacceleration"],
            actionable_takeaways=[],
            tooltip_text=None,
            citations=[Citation(chunk_id="chunk_4", page=4)],
            confidence=0.84,
            needs_analyst_review=False,
            review_reason=None,
        ),
        AllocationCall(
            asset_class_category="EQ_DM",
            sub_asset_class="EQ_US",
            call=CallDirection.NEUTRAL,
            conviction=Conviction.LOW,
            time_horizon=None,
            rationale_bullets=["Valuations look full relative to earnings momentum."],
            key_indicators=[],
            key_risks=["Valuation risk"],
            actionable_takeaways=[],
            tooltip_text=None,
            citations=[Citation(chunk_id="chunk_6", page=6)],
            confidence=0.62,
            needs_analyst_review=False,
            review_reason=None,
        ),
    ]

    return CallExtractionOutput(
        document_id="doc_tooltips",
        allocation_calls=calls,
        overall_sentiment=Sentiment.NEUTRAL,
        sentiment_rationale=["Balanced outlook."],
        sentiment_citations=[Citation(chunk_id="chunk_2", page=2)],
        sentiment_confidence=0.73,
        extraction_timestamp=datetime.now(UTC),
        model_version="test-model",
        total_candidates_reviewed=2,
    )


@pytest.mark.asyncio
async def test_stage_tooltips_with_mock_llm(mock_llm_client):
    """Stage 8 should attach tooltips to calls."""
    call_extraction = _build_call_extraction()

    output = await stage_tooltips(call_extraction, llm_client=mock_llm_client)

    tooltips = [call.tooltip_text for call in output.allocation_calls]
    assert all(tooltip for tooltip in tooltips)


@pytest.mark.asyncio
async def test_stage_tooltips_rejects_count_mismatch(mock_llm_client):
    """Stage 8 should error when tooltip count does not match call count."""
    call_extraction = _build_call_extraction()
    call_extraction.allocation_calls = call_extraction.allocation_calls[:1]

    with pytest.raises(ValidationError, match="Tooltip count mismatch"):
        await stage_tooltips(call_extraction, llm_client=mock_llm_client)
