"""Integration tests for Stage 9 - Tag generation."""

from __future__ import annotations

from datetime import UTC, date, datetime
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest
from src.exceptions import ValidationError
from src.models.calls import AllocationCall, CallExtractionOutput
from src.models.core import Citation
from src.models.document import DocumentBlock
from src.models.enums import BlockType, CallDirection, Conviction, DocumentType, Sentiment
from src.models.pipeline import CleanedDocument, RetrievedChunk, Section
from src.models.profile import DocumentProfile
from src.pipeline.stages.s9_tags import stage_tags
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
        document_id="doc_tags",
        allocation_calls=[call],
        overall_sentiment=Sentiment.NEUTRAL,
        sentiment_rationale=["Balanced outlook."],
        sentiment_citations=[Citation(chunk_id="chunk_2", page=2)],
        sentiment_confidence=0.73,
        extraction_timestamp=datetime.now(UTC),
        model_version="test-model",
        total_candidates_reviewed=2,
    )


@pytest.mark.asyncio
async def test_stage_tags_with_mock_llm(mock_llm_client):
    """Stage 9 should return TagSet with deterministic and LLM tags."""
    profile = DocumentProfile(
        document_id="doc_tags",
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

    cleaned_doc = CleanedDocument(
        document_id="doc_tags",
        blocks=[
            DocumentBlock(
                block_id="block_1",
                page=1,
                text="Macro outlook highlights rate cuts.",
                block_type=BlockType.PARAGRAPH,
                bbox=None,
                confidence=1.0,
            )
        ],
        sections=[
            Section(
                section_id="doc_tags_sec_0",
                title="Overview",
                start_block_id="block_1",
                end_block_id="block_1",
                section_type=None,
            )
        ],
        removed_boilerplate_count=0,
        disclaimer_block_id=None,
    )

    call_extraction = _build_call_extraction()

    retrieved_chunks = [
        RetrievedChunk(
            chunk_id="chunk_1",
            block_ids=["block_1"],
            page=1,
            text="Macro outlook highlights rate cuts and inflation risks.",
            score=0.9,
            section="Overview",
        )
    ]

    index = DocumentIndex(document_id="doc_tags")
    index.query = AsyncMock(side_effect=[retrieved_chunks, retrieved_chunks, retrieved_chunks])

    tagset = await stage_tags(
        document_id="doc_tags",
        cleaned_document=cleaned_doc,
        call_extraction=call_extraction,
        profile=profile,
        index=index,
        llm_client=mock_llm_client,
    )

    assert tagset.document_id == "doc_tags"
    assert "FI_SOV_EUROPE" in tagset.asset_class_tags
    assert "us" in tagset.region_tags
    assert "inflation" in tagset.theme_tags
    assert tagset.all_tags


@pytest.mark.asyncio
async def test_stage_tags_requires_asset_class_tags(mock_llm_client):
    """Stage 9 should fail when no calls produce asset class tags."""
    document_id = f"doc_tags_{uuid4().hex}"
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

    cleaned_doc = CleanedDocument(
        document_id=document_id,
        blocks=[],
        sections=[],
        removed_boilerplate_count=0,
        disclaimer_block_id=None,
    )

    call_extraction = CallExtractionOutput(
        document_id=document_id,
        allocation_calls=[],
        overall_sentiment=Sentiment.NEUTRAL,
        sentiment_rationale=["No calls."],
        sentiment_citations=[Citation(chunk_id="chunk_2", page=2)],
        sentiment_confidence=0.5,
        extraction_timestamp=datetime.now(UTC),
        model_version="test-model",
        total_candidates_reviewed=0,
    )

    index = DocumentIndex(document_id=document_id)
    index.query = AsyncMock(return_value=[])

    with pytest.raises(ValidationError, match="No asset class tags generated"):
        await stage_tags(
            document_id=document_id,
            cleaned_document=cleaned_doc,
            call_extraction=call_extraction,
            profile=profile,
            index=index,
            llm_client=mock_llm_client,
        )
