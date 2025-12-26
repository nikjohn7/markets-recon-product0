"""Integration tests for Stage 10 - Confidence scoring."""

from __future__ import annotations

from datetime import date

import pytest

from src.models.calls import AllocationCall
from src.models.confidence import ConfidenceResult
from src.models.core import Citation
from src.models.document import DocumentBlock, DocumentJSON
from src.models.enums import (
    BlockType,
    CallDirection,
    ConfidenceBand,
    Conviction,
    DocumentType,
)
from src.models.pipeline import RetrievedChunk
from src.models.profile import DocumentProfile
from src.models.summaries import DocumentSummaries, KeyTakeaway
from src.pipeline.stages.s10_confidence import stage_confidence


def _build_document() -> DocumentJSON:
    blocks = [
        DocumentBlock(
            block_id="1_0",
            page=1,
            text="Macro Outlook",
            block_type=BlockType.HEADING,
            bbox=None,
            confidence=1.0,
        ),
        DocumentBlock(
            block_id="1_1",
            page=1,
            text="We are overweight German Bunds due to easing policy.",
            block_type=BlockType.PARAGRAPH,
            bbox=None,
            confidence=1.0,
        ),
    ]

    return DocumentJSON(
        document_id="doc_conf",
        blob_id="blob123",
        file_hash="hash123",
        blocks=blocks,
        tables=[],
        page_count=1,
        extraction_coverage=1.0,
        ocr_pages=[],
        vision_pages=[],
    )


def _build_profile() -> DocumentProfile:
    return DocumentProfile(
        document_id="doc_conf",
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


def _build_calls() -> list[AllocationCall]:
    return [
        AllocationCall(
            asset_class_category="FI_SOV_EUROPE",
            sub_asset_class="GERMAN_BUNDS",
            call=CallDirection.OVERWEIGHT,
            conviction=Conviction.MEDIUM,
            time_horizon="6-12 months",
            rationale_bullets=["ECB easing supports duration demand."],
            key_indicators=[],
            key_risks=["Inflation reacceleration"],
            actionable_takeaways=[],
            tooltip_text=None,
            citations=[Citation(chunk_id="chunk_2", page=1)],
            confidence=0.84,
            needs_analyst_review=False,
            review_reason=None,
        )
    ]


def _build_summaries() -> DocumentSummaries:
    summary_text = " ".join(["Summary"] * 120)
    search_descriptor = " ".join(["Descriptor"] * 15)

    return DocumentSummaries(
        document_id="doc_conf",
        executive_summary=summary_text,
        search_descriptor=search_descriptor,
        key_takeaways=[
            KeyTakeaway(text="Takeaway one.", citations=[Citation(chunk_id="chunk_1", page=1)]),
            KeyTakeaway(text="Takeaway two.", citations=[Citation(chunk_id="chunk_1", page=1)]),
            KeyTakeaway(text="Takeaway three.", citations=[Citation(chunk_id="chunk_1", page=1)]),
        ],
        citations=[Citation(chunk_id="chunk_1", page=1)],
        confidence=0.81,
    )


@pytest.mark.asyncio
async def test_stage_confidence_returns_result():
    """Stage 10 should compute a ConfidenceResult for valid inputs."""
    source_chunks = [
        RetrievedChunk(
            chunk_id="chunk_1",
            block_ids=["1_0"],
            page=1,
            text="BlackRock Mid-Year Investment Outlook 2025.",
            score=0.9,
            section="Overview",
        ),
        RetrievedChunk(
            chunk_id="chunk_2",
            block_ids=["1_1"],
            page=1,
            text="We are overweight German Bunds due to easing policy.",
            score=0.9,
            section="Overview",
        ),
    ]

    result = await stage_confidence(
        doc=_build_document(),
        profile=_build_profile(),
        calls=_build_calls(),
        summaries=_build_summaries(),
        source_chunks=source_chunks,
    )

    assert isinstance(result, ConfidenceResult)
    assert result.document_id == "doc_conf"
    assert result.confidence_band in {ConfidenceBand.HIGH, ConfidenceBand.MEDIUM, ConfidenceBand.LOW}
    assert result.field_confidences


@pytest.mark.asyncio
async def test_stage_confidence_handles_missing_chunks():
    """Stage 10 should handle missing evidence chunks without crashing."""
    result = await stage_confidence(
        doc=_build_document(),
        profile=_build_profile(),
        calls=_build_calls(),
        summaries=_build_summaries(),
        source_chunks=[],
    )

    assert isinstance(result, ConfidenceResult)
    assert result.overall_confidence >= 0.0
