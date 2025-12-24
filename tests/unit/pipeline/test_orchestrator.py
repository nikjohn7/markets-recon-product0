"""Tests for pipeline orchestrator (Task 8.1)."""

from __future__ import annotations

import tempfile
from datetime import UTC, date, datetime
from pathlib import Path
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.exceptions import PipelineError
from src.models.calls import AllocationCall, CallExtractionOutput
from src.models.confidence import ConfidenceResult, FieldConfidence
from src.models.core import Citation
from src.models.enums import (
    BlockType,
    CallDirection,
    ConfidenceBand,
    Conviction,
    DocumentType,
    Sentiment,
    TagType,
)
from src.models.output import ProcessedDocument
from src.models.pipeline import CandidateSet, CleanedDocument, IngestResult, RetrievedChunk, Section
from src.models.profile import DocumentProfile
from src.models.summaries import DocumentSummaries, KeyTakeaway
from src.models.tags import Tag, TagSet
from src.pipeline.run import PIPELINE_VERSION, process_pdf


def _make_ingest_result() -> IngestResult:
    return IngestResult(
        document_id="doc-123",
        blob_id="blob-abc",
        file_hash="hash123",
        is_duplicate=False,
        source_metadata={"filename": "test.pdf"},
    )


def _make_profile() -> DocumentProfile:
    return DocumentProfile(
        document_id="doc-123",
        manager_name="Test Manager",
        title="Q1 Outlook",
        publication_date=date(2024, 1, 15),
        as_of_date=date(2024, 1, 1),
        document_type=DocumentType.QUARTERLY_OUTLOOK,
        asset_classes_covered=["equities"],
        regions=["us"],
        citations=[Citation(chunk_id="c1", page=1)],
    )


def _make_call_output() -> CallExtractionOutput:
    return CallExtractionOutput(
        document_id="doc-123",
        allocation_calls=[
            AllocationCall(
                asset_class_category="EQUITIES_DM",
                sub_asset_class="US_LARGE_CAP",
                call=CallDirection.OVERWEIGHT,
                conviction=Conviction.HIGH,
                rationale_bullets=["Strong earnings"],
                citations=[Citation(chunk_id="c1", page=1)],
                confidence=0.9,
            )
        ],
        overall_sentiment=Sentiment.NET_POSITIVE,
        sentiment_rationale=["Bullish outlook"],
        sentiment_citations=[Citation(chunk_id="c1", page=1)],
        sentiment_confidence=0.85,
        extraction_timestamp=datetime.now(UTC),
        model_version="test-model",
        total_candidates_reviewed=5,
    )


def _make_summaries() -> DocumentSummaries:
    return DocumentSummaries(
        document_id="doc-123",
        executive_summary="This is a test executive summary that meets the minimum length requirement for validation purposes. It needs to be at least one hundred characters long to pass validation.",
        search_descriptor="Test search descriptor meeting minimum length requirements for the model validation.",
        key_takeaways=[
            KeyTakeaway(text="Takeaway 1", citations=[Citation(chunk_id="c1", page=1)]),
            KeyTakeaway(text="Takeaway 2", citations=[Citation(chunk_id="c1", page=1)]),
            KeyTakeaway(text="Takeaway 3", citations=[Citation(chunk_id="c1", page=1)]),
        ],
        citations=[Citation(chunk_id="c1", page=1)],
        confidence=0.85,
    )


def _make_tags() -> TagSet:
    return TagSet(
        document_id="doc-123",
        asset_class_tags=["equities_dm"],
        region_tags=["us"],
        theme_tags=["inflation"],
        risk_tags=["duration_risk"],
        instrument_tags=[],
        style_tags=[],
        macro_regime_tags=["soft_landing"],
        all_tags=[
            Tag(tag_type=TagType.ASSET_CLASS, value="equities_dm", confidence=1.0, source="rule"),
        ],
        confidence=0.85,
    )


def _make_confidence() -> ConfidenceResult:
    return ConfidenceResult(
        document_id="doc-123",
        overall_confidence=0.85,
        confidence_band=ConfidenceBand.HIGH,
        extraction_coverage=0.9,
        field_confidences=[
            FieldConfidence(field_name="extraction", confidence=0.9, reasons=[], has_explicit_evidence=True, evidence_strength=0.9),
            FieldConfidence(field_name="profile", confidence=0.85, reasons=[], has_explicit_evidence=True, evidence_strength=0.85),
            FieldConfidence(field_name="calls", confidence=0.85, reasons=[], has_explicit_evidence=True, evidence_strength=0.85),
            FieldConfidence(field_name="summary", confidence=0.8, reasons=[], has_explicit_evidence=True, evidence_strength=0.8),
        ],
        analyst_attention_required=False,
        attention_reasons=[],
    )


@pytest.fixture
def mock_pdf_file(tmp_path: Path) -> Path:
    """Create a minimal valid PDF file."""
    pdf_path = tmp_path / "test.pdf"
    # Minimal PDF structure
    pdf_content = b"""%PDF-1.4
1 0 obj << /Type /Catalog /Pages 2 0 R >> endobj
2 0 obj << /Type /Pages /Kids [3 0 R] /Count 1 >> endobj
3 0 obj << /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] /Contents 4 0 R >> endobj
4 0 obj << /Length 44 >> stream
BT /F1 12 Tf 100 700 Td (Test content) Tj ET
endstream endobj
xref
0 5
0000000000 65535 f 
0000000009 00000 n 
0000000058 00000 n 
0000000115 00000 n 
0000000214 00000 n 
trailer << /Size 5 /Root 1 0 R >>
startxref
306
%%EOF"""
    pdf_path.write_bytes(pdf_content)
    return pdf_path


@pytest.mark.asyncio
async def test_process_pdf_file_not_found() -> None:
    """Test that FileNotFoundError is raised for missing PDF."""
    with pytest.raises(FileNotFoundError, match="PDF not found"):
        await process_pdf("/nonexistent/path.pdf")


@pytest.mark.asyncio
async def test_process_pdf_full_pipeline(mock_pdf_file: Path) -> None:
    """Test full pipeline execution with mocked stages."""
    mock_db = MagicMock()
    mock_db.execute = MagicMock()
    mock_llm = MagicMock()

    # Mock all stage functions
    with (
        patch("src.pipeline.run.stage_ingest", new_callable=AsyncMock) as mock_ingest,
        patch("src.pipeline.run.stage_extract", new_callable=AsyncMock) as mock_extract,
        patch("src.pipeline.run.stage_clean", new_callable=AsyncMock) as mock_clean,
        patch("src.pipeline.run.stage_index", new_callable=AsyncMock) as mock_index,
        patch("src.pipeline.run.stage_metadata", new_callable=AsyncMock) as mock_metadata,
        patch("src.pipeline.run.stage_candidates", new_callable=AsyncMock) as mock_candidates,
        patch("src.pipeline.run.stage_calls", new_callable=AsyncMock) as mock_calls,
        patch("src.pipeline.run.stage_summaries", new_callable=AsyncMock) as mock_summaries,
        patch("src.pipeline.run.stage_tooltips", new_callable=AsyncMock) as mock_tooltips,
        patch("src.pipeline.run.stage_tags", new_callable=AsyncMock) as mock_tags,
        patch("src.pipeline.run.stage_confidence", new_callable=AsyncMock) as mock_confidence,
    ):
        # Configure mocks
        mock_ingest.return_value = _make_ingest_result()
        mock_extract.return_value = MagicMock(extraction_coverage=0.9)
        mock_clean.return_value = MagicMock(document_id="doc-123")
        mock_index.return_value = MagicMock()
        mock_metadata.return_value = _make_profile()
        mock_candidates.return_value = CandidateSet(
            document_id="doc-123",
            candidates=[RetrievedChunk(chunk_id="c1", block_ids=["b1"], page=1, text="test", score=0.9)],
            keyword_matches={},
            total_chunks_reviewed=10,
        )
        mock_calls.return_value = _make_call_output()
        mock_summaries.return_value = _make_summaries()
        mock_tooltips.return_value = _make_call_output()
        mock_tags.return_value = _make_tags()
        mock_confidence.return_value = _make_confidence()

        # Mock LLM client methods
        mock_llm.get_provider_for_stage = MagicMock(return_value=MagicMock(value="ohmygpt"))
        mock_llm.get_config = MagicMock(return_value=MagicMock(model_name="test-model"))

        result = await process_pdf(mock_pdf_file, db=mock_db, llm_client=mock_llm)

        assert isinstance(result, ProcessedDocument)
        assert result.document_id == "doc-123"
        assert result.pipeline_version == PIPELINE_VERSION
        assert result.total_processing_time_seconds >= 0

        # Verify all stages were called
        mock_ingest.assert_called_once()
        mock_extract.assert_called_once()
        mock_clean.assert_called_once()
        mock_index.assert_called_once()
        mock_metadata.assert_called_once()
        mock_candidates.assert_called_once()
        mock_calls.assert_called_once()
        mock_summaries.assert_called_once()
        mock_tooltips.assert_called_once()
        mock_tags.assert_called_once()
        mock_confidence.assert_called_once()


@pytest.mark.asyncio
async def test_process_pdf_stage_failure(mock_pdf_file: Path) -> None:
    """Test pipeline handles stage failures gracefully."""
    from src.exceptions import ExtractionError

    mock_db = MagicMock()
    mock_db.execute = MagicMock()
    mock_llm = MagicMock()
    mock_llm.get_provider_for_stage = MagicMock(return_value=MagicMock(value="ohmygpt"))
    mock_llm.get_config = MagicMock(return_value=MagicMock(model_name="test-model"))

    with (
        patch("src.pipeline.run.stage_ingest", new_callable=AsyncMock) as mock_ingest,
        patch("src.pipeline.run.stage_extract", new_callable=AsyncMock) as mock_extract,
    ):
        mock_ingest.return_value = _make_ingest_result()
        mock_extract.side_effect = ExtractionError("Extraction failed")

        with pytest.raises(PipelineError, match="Pipeline failed"):
            await process_pdf(mock_pdf_file, db=mock_db, llm_client=mock_llm)


@pytest.mark.asyncio
async def test_process_pdf_persists_results(mock_pdf_file: Path) -> None:
    """Test that results are persisted to database."""
    mock_db = MagicMock()
    execute_calls: list[Any] = []
    mock_db.execute = MagicMock(side_effect=lambda x: execute_calls.append(x))
    mock_llm = MagicMock()
    mock_llm.get_provider_for_stage = MagicMock(return_value=MagicMock(value="ohmygpt"))
    mock_llm.get_config = MagicMock(return_value=MagicMock(model_name="test-model"))

    with (
        patch("src.pipeline.run.stage_ingest", new_callable=AsyncMock) as mock_ingest,
        patch("src.pipeline.run.stage_extract", new_callable=AsyncMock),
        patch("src.pipeline.run.stage_clean", new_callable=AsyncMock),
        patch("src.pipeline.run.stage_index", new_callable=AsyncMock),
        patch("src.pipeline.run.stage_metadata", new_callable=AsyncMock) as mock_metadata,
        patch("src.pipeline.run.stage_candidates", new_callable=AsyncMock) as mock_candidates,
        patch("src.pipeline.run.stage_calls", new_callable=AsyncMock) as mock_calls,
        patch("src.pipeline.run.stage_summaries", new_callable=AsyncMock) as mock_summaries,
        patch("src.pipeline.run.stage_tooltips", new_callable=AsyncMock) as mock_tooltips,
        patch("src.pipeline.run.stage_tags", new_callable=AsyncMock) as mock_tags,
        patch("src.pipeline.run.stage_confidence", new_callable=AsyncMock) as mock_confidence,
    ):
        mock_ingest.return_value = _make_ingest_result()
        mock_metadata.return_value = _make_profile()
        mock_candidates.return_value = CandidateSet(
            document_id="doc-123",
            candidates=[RetrievedChunk(chunk_id="c1", block_ids=["b1"], page=1, text="test", score=0.9)],
            keyword_matches={},
            total_chunks_reviewed=10,
        )
        mock_calls.return_value = _make_call_output()
        mock_summaries.return_value = _make_summaries()
        mock_tooltips.return_value = _make_call_output()
        mock_tags.return_value = _make_tags()
        mock_confidence.return_value = _make_confidence()

        await process_pdf(mock_pdf_file, db=mock_db, llm_client=mock_llm)

        # Should have multiple database calls (run start, run complete, document update, calls, summary, tags)
        assert mock_db.execute.call_count >= 5


@pytest.mark.asyncio
async def test_process_pdf_with_source_metadata(mock_pdf_file: Path) -> None:
    """Test that source metadata is passed through."""
    mock_db = MagicMock()
    mock_db.execute = MagicMock()
    mock_llm = MagicMock()
    mock_llm.get_provider_for_stage = MagicMock(return_value=MagicMock(value="ohmygpt"))
    mock_llm.get_config = MagicMock(return_value=MagicMock(model_name="test-model"))

    with (
        patch("src.pipeline.run.stage_ingest", new_callable=AsyncMock) as mock_ingest,
        patch("src.pipeline.run.stage_extract", new_callable=AsyncMock),
        patch("src.pipeline.run.stage_clean", new_callable=AsyncMock),
        patch("src.pipeline.run.stage_index", new_callable=AsyncMock),
        patch("src.pipeline.run.stage_metadata", new_callable=AsyncMock) as mock_metadata,
        patch("src.pipeline.run.stage_candidates", new_callable=AsyncMock) as mock_candidates,
        patch("src.pipeline.run.stage_calls", new_callable=AsyncMock) as mock_calls,
        patch("src.pipeline.run.stage_summaries", new_callable=AsyncMock) as mock_summaries,
        patch("src.pipeline.run.stage_tooltips", new_callable=AsyncMock) as mock_tooltips,
        patch("src.pipeline.run.stage_tags", new_callable=AsyncMock) as mock_tags,
        patch("src.pipeline.run.stage_confidence", new_callable=AsyncMock) as mock_confidence,
    ):
        mock_ingest.return_value = _make_ingest_result()
        mock_metadata.return_value = _make_profile()
        mock_candidates.return_value = CandidateSet(
            document_id="doc-123",
            candidates=[RetrievedChunk(chunk_id="c1", block_ids=["b1"], page=1, text="test", score=0.9)],
            keyword_matches={},
            total_chunks_reviewed=10,
        )
        mock_calls.return_value = _make_call_output()
        mock_summaries.return_value = _make_summaries()
        mock_tooltips.return_value = _make_call_output()
        mock_tags.return_value = _make_tags()
        mock_confidence.return_value = _make_confidence()

        custom_metadata = {"source": "email", "sender": "analyst@example.com"}
        await process_pdf(mock_pdf_file, source_metadata=custom_metadata, db=mock_db, llm_client=mock_llm)

        # Verify ingest was called with custom metadata
        call_args = mock_ingest.call_args
        assert call_args[0][1] == custom_metadata
