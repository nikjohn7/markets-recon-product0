"""Unit tests for allocation call models."""

from datetime import datetime

import pytest
from pydantic import ValidationError

from models.calls import AllocationCall, CallExtractionOutput, KeyIndicator
from models.core import Citation
from models.enums import CallDirection, IndicatorDirection, Sentiment


class TestKeyIndicator:
    def test_valid_indicator(self) -> None:
        ki = KeyIndicator(
            name="Inflation trend", direction=IndicatorDirection.RISING, why_it_matters="Impacts rates"
        )
        assert ki.name == "Inflation trend"

    def test_why_it_matters_max_length(self) -> None:
        with pytest.raises(ValidationError):
            KeyIndicator(name="X", direction=IndicatorDirection.STABLE, why_it_matters="x" * 201)


class TestAllocationCall:
    def test_valid_call(self) -> None:
        c = Citation(chunk_id="c1", page=1)
        call = AllocationCall(
            asset_class_category="EQUITIES_DM",
            sub_asset_class="US_LARGE_CAP",
            call=CallDirection.OVERWEIGHT,
            rationale_bullets=["Strong earnings growth"],
            citations=[c],
            confidence=0.85,
        )
        assert call.call == CallDirection.OVERWEIGHT

    def test_rationale_bullets_not_empty(self) -> None:
        c = Citation(chunk_id="c1", page=1)
        with pytest.raises(ValidationError):
            AllocationCall(
                asset_class_category="EQ",
                sub_asset_class="US",
                call=CallDirection.NEUTRAL,
                rationale_bullets=["Valid", "  "],  # Empty after strip
                citations=[c],
                confidence=0.5,
            )

    def test_rationale_min_length(self) -> None:
        c = Citation(chunk_id="c1", page=1)
        with pytest.raises(ValidationError):
            AllocationCall(
                asset_class_category="EQ",
                sub_asset_class="US",
                call=CallDirection.NEUTRAL,
                rationale_bullets=[],
                citations=[c],
                confidence=0.5,
            )

    def test_citations_min_max(self) -> None:
        with pytest.raises(ValidationError):
            AllocationCall(
                asset_class_category="EQ",
                sub_asset_class="US",
                call=CallDirection.NEUTRAL,
                rationale_bullets=["Reason"],
                citations=[],
                confidence=0.5,
            )
        c = Citation(chunk_id="c1", page=1)
        with pytest.raises(ValidationError):
            AllocationCall(
                asset_class_category="EQ",
                sub_asset_class="US",
                call=CallDirection.NEUTRAL,
                rationale_bullets=["Reason"],
                citations=[c, c, c, c],  # max 3
                confidence=0.5,
            )

    def test_confidence_bounds(self) -> None:
        c = Citation(chunk_id="c1", page=1)
        with pytest.raises(ValidationError):
            AllocationCall(
                asset_class_category="EQ",
                sub_asset_class="US",
                call=CallDirection.NEUTRAL,
                rationale_bullets=["Reason"],
                citations=[c],
                confidence=1.1,
            )

    def test_tooltip_max_length(self) -> None:
        c = Citation(chunk_id="c1", page=1)
        with pytest.raises(ValidationError):
            AllocationCall(
                asset_class_category="EQ",
                sub_asset_class="US",
                call=CallDirection.NEUTRAL,
                rationale_bullets=["Reason"],
                citations=[c],
                confidence=0.5,
                tooltip_text="x" * 151,
            )


class TestCallExtractionOutput:
    def test_valid_output(self) -> None:
        c = Citation(chunk_id="c1", page=1)
        output = CallExtractionOutput(
            document_id="d1",
            allocation_calls=[],
            overall_sentiment=Sentiment.NET_POSITIVE,
            sentiment_rationale=["Bullish tone"],
            sentiment_citations=[c],
            sentiment_confidence=0.9,
            extraction_timestamp=datetime.now(),
            model_version="1.0",
            total_candidates_reviewed=10,
        )
        assert output.overall_sentiment == Sentiment.NET_POSITIVE

    def test_sentiment_rationale_required(self) -> None:
        c = Citation(chunk_id="c1", page=1)
        with pytest.raises(ValidationError):
            CallExtractionOutput(
                document_id="d1",
                allocation_calls=[],
                overall_sentiment=Sentiment.NEUTRAL,
                sentiment_rationale=[],
                sentiment_citations=[c],
                sentiment_confidence=0.5,
                extraction_timestamp=datetime.now(),
                model_version="1.0",
                total_candidates_reviewed=5,
            )

    def test_sentiment_citations_required(self) -> None:
        with pytest.raises(ValidationError):
            CallExtractionOutput(
                document_id="d1",
                allocation_calls=[],
                overall_sentiment=Sentiment.NEUTRAL,
                sentiment_rationale=["Mixed tone"],
                sentiment_citations=[],
                sentiment_confidence=0.5,
                extraction_timestamp=datetime.now(),
                model_version="1.0",
                total_candidates_reviewed=5,
            )

    def test_sentiment_rationale_not_empty(self) -> None:
        c = Citation(chunk_id="c1", page=1)
        with pytest.raises(ValidationError):
            CallExtractionOutput(
                document_id="d1",
                allocation_calls=[],
                overall_sentiment=Sentiment.NEUTRAL,
                sentiment_rationale=["Valid rationale", "  "],  # Empty after strip
                sentiment_citations=[c],
                sentiment_confidence=0.5,
                extraction_timestamp=datetime.now(),
                model_version="1.0",
                total_candidates_reviewed=5,
            )
