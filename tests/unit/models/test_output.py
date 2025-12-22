"""Unit tests for ProcessedDocument model."""

from datetime import date, datetime

from src.models.calls import AllocationCall
from src.models.confidence import ConfidenceResult
from src.models.core import Citation
from src.models.enums import (
    CallDirection,
    ConfidenceBand,
    DocumentType,
    Sentiment,
)
from src.models.output import ProcessedDocument
from src.models.profile import DocumentProfile
from src.models.summaries import DocumentSummaries, KeyTakeaway
from src.models.tags import TagSet


def make_processed_document() -> ProcessedDocument:
    """Create a valid ProcessedDocument for testing."""
    c = Citation(chunk_id="c1", page=1)
    profile = DocumentProfile(
        document_id="d1",
        manager_name="BlackRock",
        title="2024 Outlook",
        publication_date=date(2024, 1, 15),
        document_type=DocumentType.ANNUAL_OUTLOOK,
        asset_classes_covered=["Equities"],
        citations=[c],
    )
    call = AllocationCall(
        asset_class_category="EQUITIES_DM",
        sub_asset_class="US_LARGE_CAP",
        call=CallDirection.OVERWEIGHT,
        rationale_bullets=["Strong earnings"],
        citations=[c],
        confidence=0.9,
        tooltip_text="Favor US equities",
    )
    takeaways = [KeyTakeaway(text=f"Takeaway {i}", citations=[c]) for i in range(3)]
    summaries = DocumentSummaries(
        document_id="d1",
        executive_summary="x" * 100,
        search_descriptor="x" * 50,
        key_takeaways=takeaways,
        citations=[c],
        confidence=0.85,
    )
    tags = TagSet(
        document_id="d1",
        asset_class_tags=["equities"],
        region_tags=["US"],
        theme_tags=[],
        risk_tags=[],
        instrument_tags=[],
        style_tags=[],
        macro_regime_tags=[],
        confidence=0.9,
    )
    confidence = ConfidenceResult(
        document_id="d1",
        extraction_coverage=0.95,
        overall_confidence=0.85,
        confidence_band=ConfidenceBand.HIGH,
        field_confidences=[],
        analyst_attention_required=False,
        attention_reasons=[],
    )
    return ProcessedDocument(
        document_id="d1",
        profile=profile,
        allocation_calls=[call],
        overall_sentiment=Sentiment.NET_POSITIVE,
        sentiment_rationale=["Bullish tone"],
        sentiment_citations=[c],
        summaries=summaries,
        tags=tags,
        confidence=confidence,
        processing_timestamp=datetime.now(),
        pipeline_version="0.1.0",
        total_processing_time_seconds=45.5,
    )


class TestProcessedDocument:
    def test_valid_document(self) -> None:
        doc = make_processed_document()
        assert doc.document_id == "d1"
        assert doc.profile.manager_name == "BlackRock"

    def test_serialize_to_json(self) -> None:
        doc = make_processed_document()
        json_str = doc.model_dump_json()
        assert "BlackRock" in json_str
        assert "d1" in json_str

    def test_to_allocator_pro_calls(self) -> None:
        doc = make_processed_document()
        calls = doc.to_allocator_pro_calls()
        assert len(calls) == 1
        assert calls[0]["manager_name"] == "BlackRock"
        assert calls[0]["call"] == "OVERWEIGHT"
        assert calls[0]["as_of_date"] == "2024-01-15"

    def test_to_search_document(self) -> None:
        doc = make_processed_document()
        search = doc.to_search_document()
        assert search["document_id"] == "d1"
        assert search["manager_name"] == "BlackRock"
        assert search["overall_sentiment"] == "NET_POSITIVE"
        assert len(search["calls"]) == 1
        assert search["calls"][0]["call"] == "OVERWEIGHT"
