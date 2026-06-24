"""Integration tests for Stage 7 - Summary generation."""

from __future__ import annotations

from datetime import UTC, date, datetime
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest
from src.exceptions import ExtractionError
from src.models.calls import AllocationCall, CallExtractionOutput
from src.models.core import Citation
from src.models.enums import CallDirection, Conviction, DocumentType, Sentiment
from src.models.pipeline import RetrievedChunk
from src.models.profile import DocumentProfile
from src.pipeline.stages.s7_summaries import stage_summaries
from src.pipeline.stages.s10_confidence import score_summary_evidence
from src.retrieval.indexer import DocumentIndex


def _build_call_extraction() -> CallExtractionOutput:
    call = AllocationCall(
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
    )

    return CallExtractionOutput(
        document_id="doc_summary",
        allocation_calls=[call],
        overall_sentiment=Sentiment.NEUTRAL,
        sentiment_rationale=["Balanced outlook."],
        sentiment_citations=[Citation(chunk_id="chunk_2", page=2)],
        sentiment_confidence=0.73,
        extraction_timestamp=datetime.now(UTC),
        model_version="test-model",
        total_candidates_reviewed=3,
    )


@pytest.mark.asyncio
async def test_stage_summaries_with_mock_llm(mock_llm_client):
    """Stage 7 should return DocumentSummaries with validated citations."""
    profile = DocumentProfile(
        document_id="doc_summary",
        manager_name="BlackRock",
        title="Mid-Year Investment Outlook 2025",
        publication_date=date(2025, 7, 15),
        as_of_date=date(2025, 6, 30),
        document_type=DocumentType.MID_YEAR_OUTLOOK,
        asset_classes_covered=["EQUITIES", "FIXED_INCOME"],
        regions=["US", "EUROPE"],
        time_horizon="6-12 months",
        intended_audience="Institutional investors",
        citations=[Citation(chunk_id="chunk_1", page=1)],
        manager_name_uncertain=False,
        publication_date_uncertain=False,
    )

    call_extraction = _build_call_extraction()

    retrieved_chunks = [
        RetrievedChunk(
            chunk_id="chunk_1",
            block_ids=["b1"],
            page=1,
            text="Manager overview and outlook.",
            score=0.9,
            section="Overview",
        ),
        RetrievedChunk(
            chunk_id="chunk_2",
            block_ids=["b2"],
            page=2,
            text="Sentiment context and macro themes.",
            score=0.85,
            section="Macro",
        ),
        RetrievedChunk(
            chunk_id="chunk_3",
            block_ids=["b3"],
            page=3,
            text="Risks include inflation reacceleration.",
            score=0.8,
            section="Risks",
        ),
        RetrievedChunk(
            chunk_id="chunk_4",
            block_ids=["b4"],
            page=4,
            text="European sovereign duration is favored.",
            score=0.82,
            section="Fixed Income",
        ),
        RetrievedChunk(
            chunk_id="chunk_6",
            block_ids=["b6"],
            page=6,
            text="US equities neutral as valuations remain full.",
            score=0.78,
            section="Equities",
        ),
    ]

    index = DocumentIndex(document_id="doc_summary")
    index.query = AsyncMock(side_effect=[retrieved_chunks, retrieved_chunks, retrieved_chunks])

    summaries = await stage_summaries(
        document_id="doc_summary",
        index=index,
        call_extraction=call_extraction,
        profile=profile,
        llm_client=mock_llm_client,
    )

    assert summaries.document_id == "doc_summary"
    assert summaries.confidence == pytest.approx(score_summary_evidence(summaries, retrieved_chunks))
    assert len(summaries.key_takeaways) == 3


@pytest.mark.asyncio
async def test_stage_summaries_rejects_unknown_citations(mock_llm_client):
    """Stage 7 should fail when citations reference unknown chunks."""
    document_id = f"doc_summary_{uuid4().hex}"
    profile = DocumentProfile(
        document_id=document_id,
        manager_name="BlackRock",
        title="Outlook",
        publication_date=None,
        as_of_date=None,
        document_type=DocumentType.OTHER,
        asset_classes_covered=["EQUITIES"],
        regions=[],
        time_horizon=None,
        intended_audience=None,
        citations=[Citation(chunk_id="chunk_1", page=1)],
        manager_name_uncertain=True,
        publication_date_uncertain=True,
    )

    call_extraction = _build_call_extraction().model_copy(update={"document_id": document_id})

    bad_chunks = [
        RetrievedChunk(
            chunk_id="chunk_x",
            block_ids=["bx"],
            page=1,
            text="No matching citations here.",
            score=0.9,
            section="Overview",
        )
    ]

    index = DocumentIndex(document_id=document_id)
    index.query = AsyncMock(side_effect=[bad_chunks, bad_chunks, bad_chunks])

    with pytest.raises(ExtractionError, match="Summary generation failed"):
        await stage_summaries(
            document_id=document_id,
            index=index,
            call_extraction=call_extraction,
            profile=profile,
            llm_client=mock_llm_client,
        )
