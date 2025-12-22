"""Unit tests for Stage 7 summary generation."""

from __future__ import annotations

from datetime import date
from unittest.mock import MagicMock

import pytest
from src.exceptions import ExtractionError, ValidationError
from src.models.calls import AllocationCall, CallExtractionOutput
from src.models.enums import CallDirection, Conviction, DocumentType, Sentiment
from src.models.pipeline import RetrievedChunk
from src.models.profile import DocumentProfile
from src.models.summaries import DocumentSummaries
from src.pipeline.stages.s7_summaries import (
    KeyTakeawayLLM,
    SummaryGenerationLLM,
    _parse_citation,
    _parse_key_takeaway,
    _retrieve_key_passages,
    stage_summaries,
)
from src.retrieval.indexer import DocumentIndex


class DummyLLMClient:
    """Stub LLM client returning a preconfigured response."""

    def __init__(self, response: SummaryGenerationLLM):
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


def _make_call_extraction(
    document_id: str,
    calls: list[tuple[str, str, CallDirection]],
) -> CallExtractionOutput:
    """Create a minimal CallExtractionOutput for testing.

    Args:
        document_id: Document ID
        calls: List of (category, sub_asset, direction) tuples

    Returns:
        CallExtractionOutput with allocation calls
    """
    allocation_calls = [
        AllocationCall(
            asset_class_category=category,
            sub_asset_class=sub_asset,
            call=direction,
            conviction=Conviction.MEDIUM,
            time_horizon=None,
            rationale_bullets=["Test rationale"],
            key_indicators=[],
            key_risks=[],
            citations=[{"chunk_id": f"{document_id}_0", "page": 1}],
            confidence=0.8,
            needs_analyst_review=False,
            review_reason=None,
        )
        for category, sub_asset, direction in calls
    ]

    return CallExtractionOutput(
        document_id=document_id,
        allocation_calls=allocation_calls,
        overall_sentiment=Sentiment.NET_POSITIVE,
        sentiment_rationale=["Constructive outlook"],
        sentiment_citations=[{"chunk_id": f"{document_id}_0", "page": 1}],
        sentiment_confidence=0.85,
        total_candidates_reviewed=10,
        extraction_timestamp=date(2024, 1, 15),
        model_version="test-model",
    )


def _make_mock_index(chunks: list[tuple[str, int, str, float]]) -> MagicMock:
    """Create a mock DocumentIndex that returns predefined chunks.

    Args:
        chunks: List of (chunk_id, page, text, score) tuples

    Returns:
        Mock DocumentIndex
    """
    mock_index = MagicMock(spec=DocumentIndex)

    async def query_side_effect(query: str, top_k: int = 10, **kwargs):  # noqa: ARG001
        """Return chunks for any query."""
        return [
            RetrievedChunk(
                chunk_id=chunk_id,
                block_ids=[f"b{i}"],
                page=page,
                text=text,
                score=score,
                section="Main",
            )
            for i, (chunk_id, page, text, score) in enumerate(chunks[:top_k])
        ]

    mock_index.query = MagicMock(side_effect=query_side_effect)
    return mock_index


@pytest.mark.asyncio
async def test_stage_summaries_generates_complete_output():
    """Stage 7 returns DocumentSummaries with all components."""
    profile = _make_profile("doc_sum_1")
    call_extraction = _make_call_extraction(
        "doc_sum_1",
        [
            ("EQ_DM", "EQ_US", CallDirection.OVERWEIGHT),
            ("FI_IG", "IG_US", CallDirection.NEUTRAL),
        ],
    )

    chunks = [
        (
            "doc_sum_1_0",
            1,
            "We are overweight US equities due to strong earnings growth and favorable valuations.",
            0.95,
        ),
        (
            "doc_sum_1_1",
            2,
            "Investment grade credit remains neutral as spreads have compressed.",
            0.88,
        ),
        (
            "doc_sum_1_2",
            3,
            "Overall we maintain a constructive outlook on risk assets.",
            0.82,
        ),
    ]
    mock_index = _make_mock_index(chunks)

    llm_output = SummaryGenerationLLM(
        executive_summary=(
            "This annual outlook from BlackRock emphasizes overweight positioning in US equities "
            "driven by strong earnings growth and favorable valuations, while maintaining neutral "
            "stance on investment grade credit given spread compression. The manager argues that "
            "macroeconomic tailwinds support risk assets despite elevated volatility. Key risks "
            "include potential Fed tightening and geopolitical uncertainty affecting global markets."
        ),
        search_descriptor=(
            "Annual outlook emphasizing US equity overweight due to earnings growth; "
            "neutral on IG credit with spread compression concerns; highlights macro support for risk assets."
        ),
        key_takeaways=[
            KeyTakeawayLLM(
                text="Overweight US equities on strong earnings growth and favorable valuations",
                citations=[{"chunk_id": "doc_sum_1_0", "page": 1, "text_span": "overweight US equities"}],
            ),
            KeyTakeawayLLM(
                text="Neutral on investment grade credit as spreads have compressed to tight levels",
                citations=[{"chunk_id": "doc_sum_1_1", "page": 2, "text_span": "neutral"}],
            ),
            KeyTakeawayLLM(
                text="Constructive outlook on risk assets supported by macroeconomic tailwinds",
                citations=[{"chunk_id": "doc_sum_1_2", "page": 3, "text_span": "constructive outlook"}],
            ),
        ],
        citations=[
            {"chunk_id": "doc_sum_1_0", "page": 1, "text_span": "overweight US equities"},
            {"chunk_id": "doc_sum_1_2", "page": 3, "text_span": "constructive outlook"},
        ],
        confidence=0.9,
    )

    llm_client = DummyLLMClient(response=llm_output)
    output = await stage_summaries(
        document_id="doc_sum_1",
        index=mock_index,
        call_extraction=call_extraction,
        profile=profile,
        llm_client=llm_client,
    )

    assert isinstance(output, DocumentSummaries)
    assert output.document_id == "doc_sum_1"
    assert len(output.executive_summary) > 0
    assert "BlackRock" in output.executive_summary
    assert "overweight" in output.executive_summary.lower()
    assert len(output.search_descriptor) > 0
    assert len(output.key_takeaways) == 3
    assert all(len(t.citations) >= 1 for t in output.key_takeaways)
    assert len(output.citations) == 2
    assert output.confidence == 0.9


@pytest.mark.asyncio
async def test_stage_summaries_validates_word_counts():
    """Stage 7 logs warnings for word count violations but doesn't fail."""
    profile = _make_profile("doc_sum_2")
    call_extraction = _make_call_extraction(
        "doc_sum_2",
        [("EQ_DM", "EQ_US", CallDirection.OVERWEIGHT)],
    )

    chunks = [
        ("doc_sum_2_0", 1, "Overweight US equities.", 0.9),
    ]
    mock_index = _make_mock_index(chunks)

    # Executive summary with only 50 words (below 120 minimum)
    short_summary = " ".join(["word"] * 50)

    llm_output = SummaryGenerationLLM(
        executive_summary=short_summary,
        search_descriptor="Short descriptor with exactly twenty words here to meet minimum requirement test case validation",
        key_takeaways=[
            KeyTakeawayLLM(
                text="Takeaway one",
                citations=[{"chunk_id": "doc_sum_2_0", "page": 1}],
            ),
            KeyTakeawayLLM(
                text="Takeaway two",
                citations=[{"chunk_id": "doc_sum_2_0", "page": 1}],
            ),
            KeyTakeawayLLM(
                text="Takeaway three",
                citations=[{"chunk_id": "doc_sum_2_0", "page": 1}],
            ),
        ],
        citations=[{"chunk_id": "doc_sum_2_0", "page": 1}],
        confidence=0.7,
    )

    llm_client = DummyLLMClient(response=llm_output)

    # Should complete successfully despite word count issues (only logs warning)
    output = await stage_summaries(
        document_id="doc_sum_2",
        index=mock_index,
        call_extraction=call_extraction,
        profile=profile,
        llm_client=llm_client,
    )

    assert isinstance(output, DocumentSummaries)
    assert output.document_id == "doc_sum_2"


@pytest.mark.asyncio
async def test_stage_summaries_parses_citations_with_text_span():
    """Stage 7 correctly parses citations with text_span."""
    profile = _make_profile("doc_sum_3")
    call_extraction = _make_call_extraction(
        "doc_sum_3",
        [("EQ_DM", "EQ_US", CallDirection.OVERWEIGHT)],
    )

    chunks = [
        ("doc_sum_3_0", 1, "Bullish on equities.", 0.9),
    ]
    mock_index = _make_mock_index(chunks)

    llm_output = SummaryGenerationLLM(
        executive_summary=(
            "This outlook presents a bullish stance on US equities driven by earnings momentum "
            "and accommodative monetary policy. The manager expects continued outperformance "
            "supported by strong fundamentals and technical factors. Key risks include inflation "
            "persistence and potential policy missteps affecting market sentiment and valuations."
        ),
        search_descriptor=(
            "Bullish outlook on US equities with earnings momentum driving "
            "outperformance; highlights accommodative policy support."
        ),
        key_takeaways=[
            KeyTakeawayLLM(
                text="Bullish on equities with strong earnings momentum",
                citations=[
                    {
                        "chunk_id": "doc_sum_3_0",
                        "page": 1,
                        "text_span": "Bullish on equities",
                    }
                ],
            ),
            KeyTakeawayLLM(
                text="Accommodative policy supports market valuations",
                citations=[{"chunk_id": "doc_sum_3_0", "page": 1, "text_span": "policy support"}],
            ),
            KeyTakeawayLLM(
                text="Key risks include inflation and policy errors",
                citations=[{"chunk_id": "doc_sum_3_0", "page": 1}],
            ),
        ],
        citations=[
            {"chunk_id": "doc_sum_3_0", "page": 1, "text_span": "Bullish on equities"}
        ],
        confidence=0.85,
    )

    llm_client = DummyLLMClient(response=llm_output)
    output = await stage_summaries(
        document_id="doc_sum_3",
        index=mock_index,
        call_extraction=call_extraction,
        profile=profile,
        llm_client=llm_client,
    )

    # Check executive summary citation
    assert len(output.citations) == 1
    assert output.citations[0].chunk_id == "doc_sum_3_0"
    assert output.citations[0].page == 1
    assert output.citations[0].text_span == "Bullish on equities"

    # Check takeaway citations
    assert output.key_takeaways[0].citations[0].text_span == "Bullish on equities"
    assert output.key_takeaways[1].citations[0].text_span == "policy support"
    assert output.key_takeaways[2].citations[0].text_span is None


@pytest.mark.asyncio
async def test_stage_summaries_handles_five_takeaways():
    """Stage 7 handles maximum 5 key takeaways."""
    profile = _make_profile("doc_sum_4")
    call_extraction = _make_call_extraction(
        "doc_sum_4",
        [("EQ_DM", "EQ_US", CallDirection.OVERWEIGHT)],
    )

    chunks = [
        ("doc_sum_4_0", 1, "Five takeaways document.", 0.9),
    ]
    mock_index = _make_mock_index(chunks)

    llm_output = SummaryGenerationLLM(
        executive_summary=(
            "This comprehensive outlook provides detailed analysis across multiple asset classes "
            "and regions with specific tactical recommendations. The manager presents a nuanced "
            "view incorporating macroeconomic trends, policy developments, and market dynamics. "
            "Key themes include positioning for inflation normalization and seeking quality opportunities."
        ),
        search_descriptor=(
            "Comprehensive multi-asset outlook with tactical recommendations "
            "focusing on inflation normalization and quality positioning."
        ),
        key_takeaways=[
            KeyTakeawayLLM(
                text="Takeaway one",
                citations=[{"chunk_id": "doc_sum_4_0", "page": 1}],
            ),
            KeyTakeawayLLM(
                text="Takeaway two",
                citations=[{"chunk_id": "doc_sum_4_0", "page": 1}],
            ),
            KeyTakeawayLLM(
                text="Takeaway three",
                citations=[{"chunk_id": "doc_sum_4_0", "page": 1}],
            ),
            KeyTakeawayLLM(
                text="Takeaway four",
                citations=[{"chunk_id": "doc_sum_4_0", "page": 1}],
            ),
            KeyTakeawayLLM(
                text="Takeaway five",
                citations=[{"chunk_id": "doc_sum_4_0", "page": 1}],
            ),
        ],
        citations=[{"chunk_id": "doc_sum_4_0", "page": 1}],
        confidence=0.9,
    )

    llm_client = DummyLLMClient(response=llm_output)
    output = await stage_summaries(
        document_id="doc_sum_4",
        index=mock_index,
        call_extraction=call_extraction,
        profile=profile,
        llm_client=llm_client,
    )

    assert len(output.key_takeaways) == 5


@pytest.mark.asyncio
async def test_stage_summaries_retrieves_relevant_passages():
    """Stage 7 retrieves passages using document metadata and calls."""
    profile = _make_profile("doc_sum_5", manager_name="Vanguard")
    call_extraction = _make_call_extraction(
        "doc_sum_5",
        [
            ("EQ_DM", "EQ_US", CallDirection.OVERWEIGHT),
            ("FI_SOV_EUROPE", "GERMAN_BUNDS", CallDirection.UNDERWEIGHT),
        ],
    )

    chunks = [
        ("doc_sum_5_0", 1, "Vanguard annual outlook.", 0.95),
        ("doc_sum_5_1", 2, "US equities look attractive.", 0.90),
        ("doc_sum_5_2", 3, "German Bunds face headwinds.", 0.85),
    ]
    mock_index = _make_mock_index(chunks)

    # Test the chunk retrieval function directly
    retrieved_chunks = await _retrieve_key_passages(
        index=mock_index,
        profile=profile,
        call_extraction=call_extraction,
        top_k=5,
    )

    # Verify queries were made
    assert mock_index.query.called
    # Verify chunks were retrieved
    assert len(retrieved_chunks) > 0
    # Verify deduplication (no duplicate chunk_ids)
    chunk_ids = [c.chunk_id for c in retrieved_chunks]
    assert len(chunk_ids) == len(set(chunk_ids))


@pytest.mark.asyncio
async def test_stage_summaries_handles_no_calls():
    """Stage 7 generates summaries even when no allocation calls were extracted."""
    profile = _make_profile("doc_sum_6")
    call_extraction = _make_call_extraction("doc_sum_6", [])  # No calls

    chunks = [
        ("doc_sum_6_0", 1, "Macro commentary without specific calls.", 0.9),
    ]
    mock_index = _make_mock_index(chunks)

    llm_output = SummaryGenerationLLM(
        executive_summary=(
            "This document provides high-level macroeconomic commentary without specific "
            "asset allocation recommendations. The manager discusses global economic trends "
            "and policy developments while noting heightened uncertainty in current environment. "
            "No explicit positioning guidance is provided for tactical allocation decisions today."
        ),
        search_descriptor=(
            "Macroeconomic commentary without specific allocation calls; "
            "discusses trends and uncertainty in global markets."
        ),
        key_takeaways=[
            KeyTakeawayLLM(
                text="High-level macro commentary provided",
                citations=[{"chunk_id": "doc_sum_6_0", "page": 1}],
            ),
            KeyTakeawayLLM(
                text="No specific allocation calls included",
                citations=[{"chunk_id": "doc_sum_6_0", "page": 1}],
            ),
            KeyTakeawayLLM(
                text="Heightened uncertainty noted",
                citations=[{"chunk_id": "doc_sum_6_0", "page": 1}],
            ),
        ],
        citations=[{"chunk_id": "doc_sum_6_0", "page": 1}],
        confidence=0.7,
    )

    llm_client = DummyLLMClient(response=llm_output)
    output = await stage_summaries(
        document_id="doc_sum_6",
        index=mock_index,
        call_extraction=call_extraction,
        profile=profile,
        llm_client=llm_client,
    )

    assert isinstance(output, DocumentSummaries)
    assert len(output.key_takeaways) == 3


@pytest.mark.asyncio
async def test_stage_summaries_builds_prompt_with_metadata():
    """Stage 7 builds prompt with document profile and call data."""
    profile = _make_profile("doc_sum_7", manager_name="JPMorgan")
    call_extraction = _make_call_extraction(
        "doc_sum_7",
        [("EQ_DM", "EQ_US", CallDirection.OVERWEIGHT)],
    )

    chunks = [
        ("doc_sum_7_0", 1, "Test content.", 0.9),
    ]
    mock_index = _make_mock_index(chunks)

    llm_output = SummaryGenerationLLM(
        executive_summary=(
            "JPMorgan annual outlook emphasizes overweight positioning in US equities "
            "supported by earnings growth expectations and accommodative policy backdrop. "
            "The manager maintains constructive view despite near-term volatility risks "
            "and highlights opportunities in cyclical sectors benefiting from economic recovery momentum."
        ),
        search_descriptor=(
            "JPMorgan outlook with US equity overweight driven by earnings "
            "and policy support; constructive despite volatility risks."
        ),
        key_takeaways=[
            KeyTakeawayLLM(
                text="Overweight US equities on earnings growth",
                citations=[{"chunk_id": "doc_sum_7_0", "page": 1}],
            ),
            KeyTakeawayLLM(
                text="Constructive view despite volatility",
                citations=[{"chunk_id": "doc_sum_7_0", "page": 1}],
            ),
            KeyTakeawayLLM(
                text="Cyclical sectors offer opportunities",
                citations=[{"chunk_id": "doc_sum_7_0", "page": 1}],
            ),
        ],
        citations=[{"chunk_id": "doc_sum_7_0", "page": 1}],
        confidence=0.85,
    )

    llm_client = DummyLLMClient(response=llm_output)
    await stage_summaries(
        document_id="doc_sum_7",
        index=mock_index,
        call_extraction=call_extraction,
        profile=profile,
        llm_client=llm_client,
    )

    # Verify prompt contains metadata
    assert llm_client.last_prompt is not None
    assert "JPMorgan" in llm_client.last_prompt
    assert "ANNUAL_OUTLOOK" in llm_client.last_prompt
    assert "EQ_US" in llm_client.last_prompt


@pytest.mark.asyncio
async def test_parse_citation_raises_on_invalid_dict():
    """Citation parsing raises ValidationError for invalid dicts."""
    invalid_citation = {"page": 1}  # Missing chunk_id

    with pytest.raises(ValidationError, match="Invalid citation dict"):
        _parse_citation(invalid_citation)


@pytest.mark.asyncio
async def test_parse_key_takeaway_raises_on_invalid_citation():
    """Key takeaway parsing raises ValidationError for invalid citations."""
    invalid_takeaway = KeyTakeawayLLM(
        text="Test takeaway",
        citations=[{"page": 1}],  # Missing chunk_id
    )

    with pytest.raises(ValidationError, match="Invalid takeaway citations"):
        _parse_key_takeaway(invalid_takeaway)


@pytest.mark.asyncio
async def test_stage_summaries_raises_on_llm_failure():
    """Stage 7 raises ExtractionError when LLM call fails."""
    profile = _make_profile("doc_sum_fail")
    call_extraction = _make_call_extraction(
        "doc_sum_fail",
        [("EQ_DM", "EQ_US", CallDirection.OVERWEIGHT)],
    )

    chunks = [
        ("doc_sum_fail_0", 1, "Test content.", 0.9),
    ]
    mock_index = _make_mock_index(chunks)

    # Create LLM client that raises an exception
    class FailingLLMClient:
        async def complete_json(self, prompt, response_model, stage):  # noqa: ARG002
            msg = "LLM API error"
            raise RuntimeError(msg)

    failing_client = FailingLLMClient()

    with pytest.raises(ExtractionError, match="Summary generation failed"):
        await stage_summaries(
            document_id="doc_sum_fail",
            index=mock_index,
            call_extraction=call_extraction,
            profile=profile,
            llm_client=failing_client,
        )
