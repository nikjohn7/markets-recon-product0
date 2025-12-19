"""Unit tests for confidence models."""

import pytest
from pydantic import ValidationError

from models.confidence import ConfidenceResult, FieldConfidence, compute_confidence_band
from models.enums import ConfidenceBand


class TestComputeConfidenceBand:
    def test_high_band(self) -> None:
        assert compute_confidence_band(0.80) == ConfidenceBand.HIGH
        assert compute_confidence_band(0.95) == ConfidenceBand.HIGH
        assert compute_confidence_band(1.0) == ConfidenceBand.HIGH

    def test_medium_band(self) -> None:
        assert compute_confidence_band(0.60) == ConfidenceBand.MEDIUM
        assert compute_confidence_band(0.79) == ConfidenceBand.MEDIUM

    def test_low_band(self) -> None:
        assert compute_confidence_band(0.59) == ConfidenceBand.LOW
        assert compute_confidence_band(0.0) == ConfidenceBand.LOW


class TestFieldConfidence:
    def test_valid_field_confidence(self) -> None:
        fc = FieldConfidence(
            field_name="manager_name",
            confidence=0.9,
            reasons=["Explicit mention"],
            has_explicit_evidence=True,
            evidence_strength=0.95,
        )
        assert fc.field_name == "manager_name"

    def test_confidence_bounds(self) -> None:
        with pytest.raises(ValidationError):
            FieldConfidence(
                field_name="x",
                confidence=1.1,
                reasons=[],
                has_explicit_evidence=False,
                evidence_strength=0.5,
            )


class TestConfidenceResult:
    def test_valid_result_high(self) -> None:
        cr = ConfidenceResult(
            document_id="d1",
            extraction_coverage=0.95,
            overall_confidence=0.85,
            confidence_band=ConfidenceBand.HIGH,
            field_confidences=[],
            analyst_attention_required=False,
            attention_reasons=[],
        )
        assert cr.confidence_band == ConfidenceBand.HIGH

    def test_valid_result_low(self) -> None:
        cr = ConfidenceResult(
            document_id="d1",
            extraction_coverage=0.5,
            overall_confidence=0.45,
            confidence_band=ConfidenceBand.LOW,
            field_confidences=[],
            analyst_attention_required=True,
            attention_reasons=["Low extraction coverage"],
        )
        assert cr.confidence_band == ConfidenceBand.LOW

    def test_band_must_match_confidence(self) -> None:
        with pytest.raises(ValidationError):
            ConfidenceResult(
                document_id="d1",
                extraction_coverage=0.9,
                overall_confidence=0.85,  # Should be HIGH
                confidence_band=ConfidenceBand.LOW,  # Mismatch
                field_confidences=[],
                analyst_attention_required=False,
                attention_reasons=[],
            )

    def test_boundary_080_is_high(self) -> None:
        cr = ConfidenceResult(
            document_id="d1",
            extraction_coverage=0.9,
            overall_confidence=0.80,
            confidence_band=ConfidenceBand.HIGH,
            field_confidences=[],
            analyst_attention_required=False,
            attention_reasons=[],
        )
        assert cr.confidence_band == ConfidenceBand.HIGH

    def test_boundary_060_is_medium(self) -> None:
        cr = ConfidenceResult(
            document_id="d1",
            extraction_coverage=0.9,
            overall_confidence=0.60,
            confidence_band=ConfidenceBand.MEDIUM,
            field_confidences=[],
            analyst_attention_required=False,
            attention_reasons=[],
        )
        assert cr.confidence_band == ConfidenceBand.MEDIUM
