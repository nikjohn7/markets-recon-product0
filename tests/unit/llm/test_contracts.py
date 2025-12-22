"""Unit tests for LLM output validation guardrails."""

from __future__ import annotations

from datetime import UTC, datetime

import pytest
from pydantic import BaseModel
from src.exceptions import ValidationError
from src.llm.contracts import (
    extract_citations,
    find_hallucination_markers,
    validate_citations,
    validate_llm_output,
    validate_taxonomy,
)
from src.models.calls import AllocationCall, CallExtractionOutput
from src.models.core import Citation
from src.models.enums import CallDirection, Sentiment
from src.models.pipeline import Chunk
from src.models.profile import DocumentProfile


class SimpleOutput(BaseModel):
    """Simple output model for hallucination checks."""

    note: str


def test_extract_citations_walks_nested_models():
    """Ensure citations are found in nested structures."""
    citation = Citation(chunk_id="doc_1", block_ids=["b1"], page=1, text_span="text")
    profile = DocumentProfile(
        document_id="doc_1",
        manager_name="Acme",
        title="Outlook",
        publication_date=None,
        as_of_date=None,
        document_type="ANNUAL_OUTLOOK",
        asset_classes_covered=["EQUITIES"],
        regions=[],
        time_horizon=None,
        intended_audience=None,
        citations=[citation],
    )
    citations = extract_citations(profile)
    assert citations == [citation]


def test_validate_citations_accepts_valid_chunk_ids():
    """Valid citations should pass validation."""
    citation = Citation(chunk_id="doc_1", block_ids=["b1"], page=1, text_span="text")
    output = DocumentProfile(
        document_id="doc_1",
        manager_name="Acme",
        title="Outlook",
        publication_date=None,
        as_of_date=None,
        document_type="ANNUAL_OUTLOOK",
        asset_classes_covered=["EQUITIES"],
        regions=[],
        time_horizon=None,
        intended_audience=None,
        citations=[citation],
    )
    validate_citations(output, {"doc_1"})


def test_validate_citations_rejects_invalid_chunk_ids():
    """Invalid citations should raise ValidationError."""
    citation = Citation(chunk_id="doc_2", block_ids=["b1"], page=1, text_span="text")
    output = DocumentProfile(
        document_id="doc_1",
        manager_name="Acme",
        title="Outlook",
        publication_date=None,
        as_of_date=None,
        document_type="ANNUAL_OUTLOOK",
        asset_classes_covered=["EQUITIES"],
        regions=[],
        time_horizon=None,
        intended_audience=None,
        citations=[citation],
    )
    with pytest.raises(ValidationError, match="Invalid citation chunk_id"):
        validate_citations(output, {"doc_1"})


def test_validate_taxonomy_rejects_mismatched_category():
    """Mismatched taxonomy pair should raise ValidationError."""
    citation = Citation(chunk_id="doc_1", block_ids=["b1"], page=1, text_span="text")
    call = AllocationCall(
        asset_class_category="FI_SOV_NA",
        sub_asset_class="GERMAN_BUNDS",
        call=CallDirection.OVERWEIGHT,
        conviction=None,
        time_horizon=None,
        rationale_bullets=["Strong yields"],
        key_indicators=[],
        key_risks=[],
        actionable_takeaways=[],
        tooltip_text=None,
        citations=[citation],
        confidence=0.75,
        needs_analyst_review=False,
        review_reason=None,
    )
    output = CallExtractionOutput(
        document_id="doc_1",
        allocation_calls=[call],
        overall_sentiment=Sentiment.NET_POSITIVE,
        sentiment_rationale=["Rising growth outlook"],
        sentiment_citations=[citation],
        sentiment_confidence=0.7,
        extraction_timestamp=datetime.now(UTC),
        model_version="test",
        total_candidates_reviewed=2,
    )
    with pytest.raises(ValidationError, match="Mismatched taxonomy"):
        validate_taxonomy(output)


def test_find_hallucination_markers_detects_dates():
    """Detect hallucinated dates not present in source text."""
    output = SimpleOutput(note="Published on 2025-01-01")
    chunks = [
        Chunk(
            chunk_id="doc_1",
            block_ids=["b1"],
            page=1,
            text="No dates here.",
            section=None,
        )
    ]
    matches = find_hallucination_markers(output, chunks)
    assert "2025-01-01" in matches


def test_validate_llm_output_allows_markers_in_source():
    """Allow markers when they exist in source text."""
    output = SimpleOutput(note="Allocation was +5% on 2024-06-01.")
    chunks = [
        Chunk(
            chunk_id="doc_1",
            block_ids=["b1"],
            page=1,
            text="The allocation was +5% on 2024-06-01.",
            section=None,
        )
    ]
    validate_llm_output(output, chunks)


def test_find_hallucination_markers_handles_long_quotes_without_false_positive():
    """Quoted long text should match source text without false positives."""
    quoted_text = "This sentence is intentionally long enough to cross the threshold."
    output = SimpleOutput(note=f'"{quoted_text}"')
    chunks = [
        Chunk(
            chunk_id="doc_1",
            block_ids=["b1"],
            page=1,
            text=f"Context: {quoted_text} Additional context.",
            section=None,
        )
    ]
    matches = find_hallucination_markers(output, chunks)
    assert not matches


def test_find_hallucination_markers_ignores_unquoted_long_text():
    """Long unquoted text should not trigger hallucination detection."""
    long_text = "This sentence is intentionally long enough to cross the threshold without quotes."
    output = SimpleOutput(note=long_text)
    chunks = [
        Chunk(
            chunk_id="doc_1",
            block_ids=["b1"],
            page=1,
            text="No matching content required for unquoted long text.",
            section=None,
        )
    ]
    matches = find_hallucination_markers(output, chunks)
    assert not matches
