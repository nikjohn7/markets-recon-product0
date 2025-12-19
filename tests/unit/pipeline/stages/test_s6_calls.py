"""Unit tests for Stage 6 call extraction."""

from __future__ import annotations

from datetime import date

import pytest
from src.exceptions import ExtractionError, ValidationError
from src.models.calls import CallExtractionOutput
from src.models.enums import CallDirection, Conviction, DocumentType, IndicatorDirection, Sentiment
from src.models.pipeline import CandidateSet, RetrievedChunk
from src.models.profile import DocumentProfile
from src.pipeline.stages.s6_calls import CallExtractionLLM, CallLLM, stage_calls


class DummyLLMClient:
    """Stub LLM client returning a preconfigured response."""

    def __init__(self, response: CallExtractionLLM):
        self.response = response
        self.last_prompt: str | None = None
        self.last_stage = None

    async def complete_json(self, prompt: str, response_model, stage):  # noqa: ARG002
        self.last_prompt = prompt
        self.last_stage = stage
        return self.response

    def get_provider_for_stage(self, stage):  # noqa: ARG002
        """Return dummy provider."""
        return "test-provider"

    def get_config(self, provider):  # noqa: ARG002
        """Return dummy provider config."""
        class DummyConfig:
            model_name = "test-model-v1"
        return DummyConfig()


def _make_profile(document_id: str, manager_name: str = "BlackRock") -> DocumentProfile:
    """Create a minimal DocumentProfile for testing."""
    return DocumentProfile(
        document_id=document_id,
        manager_name=manager_name,
        title="Test Outlook",
        publication_date=date(2024, 1, 15),
        as_of_date=None,
        document_type=DocumentType.ANNUAL_OUTLOOK,
        asset_classes_covered=["EQUITIES", "FIXED_INCOME"],
        regions=["GLOBAL"],
        time_horizon=None,
        intended_audience=None,
        citations=[
            {
                "chunk_id": "doc_0",
                "page": 1,
                "text_span": "BlackRock 2024 Outlook",
            }
        ],
        manager_name_uncertain=False,
        publication_date_uncertain=False,
    )


def _make_candidate_set(
    document_id: str,
    chunks: list[tuple[str, int, str]],
) -> CandidateSet:
    """Create a CandidateSet with test chunks.

    Args:
        document_id: Document ID
        chunks: List of (chunk_id, page, text) tuples

    Returns:
        CandidateSet with retrieved chunks
    """
    candidates = [
        RetrievedChunk(
            chunk_id=chunk_id,
            block_ids=[f"b{i}"],
            page=page,
            text=text,
            score=0.9,
            section="Main",
        )
        for i, (chunk_id, page, text) in enumerate(chunks)
    ]

    return CandidateSet(
        document_id=document_id,
        candidates=candidates,
        keyword_matches={},
        total_chunks_reviewed=len(chunks),
    )


@pytest.mark.asyncio
async def test_stage_calls_extracts_calls_and_sentiment():
    """Stage 6 returns CallExtractionOutput with calls and sentiment."""
    profile = _make_profile("doc_calls_1")
    candidate_set = _make_candidate_set(
        "doc_calls_1",
        [
            ("doc_calls_1_0", 1, "We are overweight US equities due to strong earnings growth."),
            ("doc_calls_1_1", 2, "Overall we remain constructive on risk assets."),
        ],
    )

    llm_output = CallExtractionLLM(
        allocation_calls=[
            CallLLM(
                asset_class_category="EQ_DM",
                sub_asset_class="EQ_US",
                call=CallDirection.OVERWEIGHT,
                conviction=Conviction.HIGH,
                time_horizon=None,
                rationale_bullets=["Strong earnings growth", "Positive momentum"],
                key_indicators=[
                    {
                        "name": "GDP growth",
                        "direction": "RISING",
                        "why_it_matters": "Supports equity valuations",
                    }
                ],
                key_risks=["Fed tightening"],
                citations=[
                    {"chunk_id": "doc_calls_1_0", "page": 1, "text_span": "overweight US equities"}
                ],
                confidence=0.9,
                needs_analyst_review=False,
                review_reason=None,
            )
        ],
        overall_sentiment=Sentiment.NET_POSITIVE,
        sentiment_rationale=["Constructive on risk assets", "Positive economic outlook"],
        sentiment_citations=[
            {"chunk_id": "doc_calls_1_1", "page": 2, "text_span": "remain constructive"}
        ],
        sentiment_confidence=0.85,
    )

    llm_client = DummyLLMClient(response=llm_output)
    output = await stage_calls(profile, candidate_set, llm_client=llm_client)

    assert isinstance(output, CallExtractionOutput)
    assert output.document_id == "doc_calls_1"
    assert len(output.allocation_calls) == 1
    assert output.allocation_calls[0].asset_class_category == "EQ_DM"
    assert output.allocation_calls[0].sub_asset_class == "EQ_US"
    assert output.allocation_calls[0].call == CallDirection.OVERWEIGHT
    assert output.allocation_calls[0].conviction == Conviction.HIGH
    assert len(output.allocation_calls[0].rationale_bullets) == 2
    assert len(output.allocation_calls[0].key_indicators) == 1
    assert output.allocation_calls[0].key_indicators[0].name == "GDP growth"
    assert output.allocation_calls[0].key_indicators[0].direction == IndicatorDirection.RISING
    assert output.overall_sentiment == Sentiment.NET_POSITIVE
    assert output.sentiment_confidence == 0.85
    assert output.total_candidates_reviewed == 2


@pytest.mark.asyncio
async def test_stage_calls_handles_uncertain_calls():
    """Stage 6 preserves UNCERTAIN calls and review flags."""
    profile = _make_profile("doc_calls_2")
    candidate_set = _make_candidate_set(
        "doc_calls_2",
        [
            ("doc_calls_2_0", 1, "We have mixed views on European equities."),
        ],
    )

    llm_output = CallExtractionLLM(
        allocation_calls=[
            CallLLM(
                asset_class_category="EQ_DM",
                sub_asset_class="EQ_EUROPE",
                call=CallDirection.UNCERTAIN,
                conviction=None,
                time_horizon=None,
                rationale_bullets=["Mixed signals from economic data"],
                key_indicators=[],
                key_risks=[],
                citations=[
                    {"chunk_id": "doc_calls_2_0", "page": 1, "text_span": "mixed views"}
                ],
                confidence=0.4,
                needs_analyst_review=True,
                review_reason="Ambiguous positioning language",
            )
        ],
        overall_sentiment=Sentiment.NEUTRAL,
        sentiment_rationale=["Balanced outlook"],
        sentiment_citations=[
            {"chunk_id": "doc_calls_2_0", "page": 1, "text_span": "mixed views"}
        ],
        sentiment_confidence=0.6,
    )

    llm_client = DummyLLMClient(response=llm_output)
    output = await stage_calls(profile, candidate_set, llm_client=llm_client)

    assert len(output.allocation_calls) == 1
    assert output.allocation_calls[0].call == CallDirection.UNCERTAIN
    assert output.allocation_calls[0].needs_analyst_review is True
    assert output.allocation_calls[0].review_reason == "Ambiguous positioning language"
    assert output.allocation_calls[0].confidence == 0.4


@pytest.mark.asyncio
async def test_stage_calls_detects_duplicate_calls():
    """Stage 6 raises ValidationError for duplicate (category, sub_asset) pairs."""
    profile = _make_profile("doc_calls_3")
    candidate_set = _make_candidate_set(
        "doc_calls_3",
        [
            ("doc_calls_3_0", 1, "We are overweight US equities."),
            ("doc_calls_3_1", 2, "We are also bullish on US equities."),
        ],
    )

    llm_output = CallExtractionLLM(
        allocation_calls=[
            CallLLM(
                asset_class_category="EQ_DM",
                sub_asset_class="EQ_US",
                call=CallDirection.OVERWEIGHT,
                conviction=None,
                time_horizon=None,
                rationale_bullets=["Strong growth"],
                key_indicators=[],
                key_risks=[],
                citations=[
                    {"chunk_id": "doc_calls_3_0", "page": 1, "text_span": "overweight US equities"}
                ],
                confidence=0.9,
                needs_analyst_review=False,
                review_reason=None,
            ),
            CallLLM(
                asset_class_category="EQ_DM",
                sub_asset_class="EQ_US",
                call=CallDirection.OVERWEIGHT,
                conviction=Conviction.HIGH,
                time_horizon=None,
                rationale_bullets=["Bullish signals"],
                key_indicators=[],
                key_risks=[],
                citations=[
                    {"chunk_id": "doc_calls_3_1", "page": 2, "text_span": "bullish on US equities"}
                ],
                confidence=0.85,
                needs_analyst_review=False,
                review_reason=None,
            ),
        ],
        overall_sentiment=Sentiment.NET_POSITIVE,
        sentiment_rationale=["Positive outlook"],
        sentiment_citations=[
            {"chunk_id": "doc_calls_3_0", "page": 1, "text_span": "overweight"}
        ],
        sentiment_confidence=0.8,
    )

    llm_client = DummyLLMClient(response=llm_output)

    with pytest.raises(ValidationError, match="Duplicate call detected: EQ_DM / EQ_US"):
        await stage_calls(profile, candidate_set, llm_client=llm_client)


@pytest.mark.asyncio
async def test_stage_calls_multiple_calls_different_assets():
    """Stage 6 handles multiple calls for different asset classes."""
    profile = _make_profile("doc_calls_4")
    candidate_set = _make_candidate_set(
        "doc_calls_4",
        [
            ("doc_calls_4_0", 1, "Overweight US equities, underweight German Bunds."),
        ],
    )

    llm_output = CallExtractionLLM(
        allocation_calls=[
            CallLLM(
                asset_class_category="EQ_DM",
                sub_asset_class="EQ_US",
                call=CallDirection.OVERWEIGHT,
                conviction=None,
                time_horizon=None,
                rationale_bullets=["Strong fundamentals"],
                key_indicators=[],
                key_risks=[],
                citations=[
                    {"chunk_id": "doc_calls_4_0", "page": 1, "text_span": "Overweight US equities"}
                ],
                confidence=0.9,
                needs_analyst_review=False,
                review_reason=None,
            ),
            CallLLM(
                asset_class_category="FI_SOV_EUROPE",
                sub_asset_class="GERMAN_BUNDS",
                call=CallDirection.UNDERWEIGHT,
                conviction=None,
                time_horizon=None,
                rationale_bullets=["Negative real yields"],
                key_indicators=[],
                key_risks=[],
                citations=[
                    {"chunk_id": "doc_calls_4_0", "page": 1, "text_span": "underweight German Bunds"}
                ],
                confidence=0.85,
                needs_analyst_review=False,
                review_reason=None,
            ),
        ],
        overall_sentiment=Sentiment.NET_POSITIVE,
        sentiment_rationale=["Positive on equities"],
        sentiment_citations=[
            {"chunk_id": "doc_calls_4_0", "page": 1, "text_span": "Overweight US equities"}
        ],
        sentiment_confidence=0.8,
    )

    llm_client = DummyLLMClient(response=llm_output)
    output = await stage_calls(profile, candidate_set, llm_client=llm_client)

    assert len(output.allocation_calls) == 2
    assert output.allocation_calls[0].sub_asset_class == "EQ_US"
    assert output.allocation_calls[0].call == CallDirection.OVERWEIGHT
    assert output.allocation_calls[1].sub_asset_class == "GERMAN_BUNDS"
    assert output.allocation_calls[1].call == CallDirection.UNDERWEIGHT


@pytest.mark.asyncio
async def test_stage_calls_raises_on_empty_candidates():
    """Stage 6 raises ExtractionError when no candidates available."""
    profile = _make_profile("doc_calls_empty")
    candidate_set = CandidateSet(
        document_id="doc_calls_empty",
        candidates=[],
        keyword_matches={},
        total_chunks_reviewed=0,
    )

    # LLM client won't be called, but create one anyway
    llm_client = DummyLLMClient(response=CallExtractionLLM(
        allocation_calls=[],
        overall_sentiment=Sentiment.NEUTRAL,
        sentiment_rationale=["No data"],
        sentiment_citations=[{"chunk_id": "dummy", "page": 1}],  # Need at least one
        sentiment_confidence=0.0,
    ))

    with pytest.raises(ExtractionError, match="No candidate chunks available"):
        await stage_calls(profile, candidate_set, llm_client=llm_client)


@pytest.mark.asyncio
async def test_stage_calls_parses_citations_correctly():
    """Stage 6 correctly parses citations with text_span."""
    profile = _make_profile("doc_calls_5")
    candidate_set = _make_candidate_set(
        "doc_calls_5",
        [
            ("doc_calls_5_0", 1, "We prefer gold due to inflation hedging."),
        ],
    )

    llm_output = CallExtractionLLM(
        allocation_calls=[
            CallLLM(
                asset_class_category="ALT_COMMODITIES",
                sub_asset_class="GOLD",
                call=CallDirection.OVERWEIGHT,
                conviction=None,
                time_horizon=None,
                rationale_bullets=["Inflation hedge"],
                key_indicators=[],
                key_risks=[],
                citations=[
                    {
                        "chunk_id": "doc_calls_5_0",
                        "page": 1,
                        "text_span": "prefer gold due to inflation hedging",
                    }
                ],
                confidence=0.85,
                needs_analyst_review=False,
                review_reason=None,
            )
        ],
        overall_sentiment=Sentiment.NEUTRAL,
        sentiment_rationale=["Cautious optimism"],
        sentiment_citations=[
            {"chunk_id": "doc_calls_5_0", "page": 1, "text_span": "inflation hedging"}
        ],
        sentiment_confidence=0.7,
    )

    llm_client = DummyLLMClient(response=llm_output)
    output = await stage_calls(profile, candidate_set, llm_client=llm_client)

    assert len(output.allocation_calls[0].citations) == 1
    assert output.allocation_calls[0].citations[0].chunk_id == "doc_calls_5_0"
    assert output.allocation_calls[0].citations[0].page == 1
    assert output.allocation_calls[0].citations[0].text_span == "prefer gold due to inflation hedging"


@pytest.mark.asyncio
async def test_stage_calls_handles_missing_text_span():
    """Stage 6 handles citations without text_span."""
    profile = _make_profile("doc_calls_6")
    candidate_set = _make_candidate_set(
        "doc_calls_6",
        [
            ("doc_calls_6_0", 1, "Underweight high yield bonds."),
        ],
    )

    llm_output = CallExtractionLLM(
        allocation_calls=[
            CallLLM(
                asset_class_category="FI_HY",
                sub_asset_class="HY_US",
                call=CallDirection.UNDERWEIGHT,
                conviction=None,
                time_horizon=None,
                rationale_bullets=["Credit risk elevated"],
                key_indicators=[],
                key_risks=[],
                citations=[
                    {"chunk_id": "doc_calls_6_0", "page": 1}  # No text_span
                ],
                confidence=0.8,
                needs_analyst_review=False,
                review_reason=None,
            )
        ],
        overall_sentiment=Sentiment.NET_NEGATIVE,
        sentiment_rationale=["Cautious on credit"],
        sentiment_citations=[
            {"chunk_id": "doc_calls_6_0", "page": 1}
        ],
        sentiment_confidence=0.75,
    )

    llm_client = DummyLLMClient(response=llm_output)
    output = await stage_calls(profile, candidate_set, llm_client=llm_client)

    assert len(output.allocation_calls[0].citations) == 1
    assert output.allocation_calls[0].citations[0].text_span is None


@pytest.mark.asyncio
async def test_stage_calls_includes_model_version():
    """Stage 6 captures LLM model version in output."""
    profile = _make_profile("doc_calls_7")
    candidate_set = _make_candidate_set(
        "doc_calls_7",
        [
            ("doc_calls_7_0", 1, "Neutral on emerging markets."),
        ],
    )

    llm_output = CallExtractionLLM(
        allocation_calls=[
            CallLLM(
                asset_class_category="EQ_EM",
                sub_asset_class="EQ_EM_BROAD",
                call=CallDirection.NEUTRAL,
                conviction=None,
                time_horizon=None,
                rationale_bullets=["Mixed signals"],
                key_indicators=[],
                key_risks=[],
                citations=[
                    {"chunk_id": "doc_calls_7_0", "page": 1}
                ],
                confidence=0.7,
                needs_analyst_review=False,
                review_reason=None,
            )
        ],
        overall_sentiment=Sentiment.NEUTRAL,
        sentiment_rationale=["Balanced view"],
        sentiment_citations=[
            {"chunk_id": "doc_calls_7_0", "page": 1}
        ],
        sentiment_confidence=0.65,
    )

    llm_client = DummyLLMClient(response=llm_output)
    output = await stage_calls(profile, candidate_set, llm_client=llm_client)

    assert output.model_version == "test-model-v1"


@pytest.mark.asyncio
async def test_stage_calls_preserves_key_risks():
    """Stage 6 preserves key_risks from LLM output."""
    profile = _make_profile("doc_calls_8")
    candidate_set = _make_candidate_set(
        "doc_calls_8",
        [
            ("doc_calls_8_0", 1, "Overweight tech, but risks include regulation."),
        ],
    )

    llm_output = CallExtractionLLM(
        allocation_calls=[
            CallLLM(
                asset_class_category="EQ_SECTORS",
                sub_asset_class="EQ_TECH",
                call=CallDirection.OVERWEIGHT,
                conviction=Conviction.MEDIUM,
                time_horizon=None,
                rationale_bullets=["Innovation tailwinds"],
                key_indicators=[],
                key_risks=["Regulatory headwinds", "Valuation concerns"],
                citations=[
                    {"chunk_id": "doc_calls_8_0", "page": 1}
                ],
                confidence=0.85,
                needs_analyst_review=False,
                review_reason=None,
            )
        ],
        overall_sentiment=Sentiment.NET_POSITIVE,
        sentiment_rationale=["Tech-driven growth"],
        sentiment_citations=[
            {"chunk_id": "doc_calls_8_0", "page": 1}
        ],
        sentiment_confidence=0.8,
    )

    llm_client = DummyLLMClient(response=llm_output)
    output = await stage_calls(profile, candidate_set, llm_client=llm_client)

    assert len(output.allocation_calls[0].key_risks) == 2
    assert "Regulatory headwinds" in output.allocation_calls[0].key_risks
    assert "Valuation concerns" in output.allocation_calls[0].key_risks


@pytest.mark.asyncio
async def test_stage_calls_builds_prompt_with_profile():
    """Stage 6 builds prompt with document profile metadata."""
    profile = _make_profile("doc_calls_9", manager_name="Vanguard")
    candidate_set = _make_candidate_set(
        "doc_calls_9",
        [
            ("doc_calls_9_0", 1, "We are overweight bonds."),
        ],
    )

    llm_output = CallExtractionLLM(
        allocation_calls=[],
        overall_sentiment=Sentiment.NEUTRAL,
        sentiment_rationale=["No strong views"],
        sentiment_citations=[
            {"chunk_id": "doc_calls_9_0", "page": 1}
        ],
        sentiment_confidence=0.5,
    )

    llm_client = DummyLLMClient(response=llm_output)
    await stage_calls(profile, candidate_set, llm_client=llm_client)

    # Verify prompt contains manager name and document type
    assert llm_client.last_prompt is not None
    assert "Vanguard" in llm_client.last_prompt
    assert "ANNUAL_OUTLOOK" in llm_client.last_prompt
    assert "doc_calls_9_0" in llm_client.last_prompt
