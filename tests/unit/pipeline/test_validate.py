"""Tests for output validator (Task 8.3)."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from src.pipeline.validate import (
    validate_citations,
    validate_output,
    validate_schema,
    validate_tags,
    validate_taxonomy,
)


def _make_valid_output() -> dict[str, Any]:
    """Create a valid ProcessedDocument dict."""
    return {
        "document_id": "doc-123",
        "profile": {
            "document_id": "doc-123",
            "manager_name": "Test Manager",
            "title": "Q1 Outlook",
            "publication_date": "2024-01-15",
            "as_of_date": "2024-01-01",
            "document_type": "QUARTERLY_OUTLOOK",
            "asset_classes_covered": ["equities"],
            "regions": ["us"],
            "citations": [{"chunk_id": "c1", "page": 1}],
        },
        "allocation_calls": [
            {
                "asset_class_category": "EQ_DM",
                "sub_asset_class": "EQ_US",
                "call": "OVERWEIGHT",
                "conviction": "HIGH",
                "rationale_bullets": ["Strong earnings"],
                "citations": [{"chunk_id": "c1", "page": 1}],
                "confidence": 0.9,
            }
        ],
        "overall_sentiment": "NET_POSITIVE",
        "sentiment_rationale": ["Bullish outlook"],
        "sentiment_citations": [{"chunk_id": "c1", "page": 1}],
        "summaries": {
            "document_id": "doc-123",
            "executive_summary": "A" * 100,
            "search_descriptor": "B" * 50,
            "key_takeaways": [
                {"text": "Takeaway 1", "citations": [{"chunk_id": "c1", "page": 1}]},
                {"text": "Takeaway 2", "citations": [{"chunk_id": "c1", "page": 1}]},
                {"text": "Takeaway 3", "citations": [{"chunk_id": "c1", "page": 1}]},
            ],
            "citations": [{"chunk_id": "c1", "page": 1}],
            "confidence": 0.85,
        },
        "tags": {
            "document_id": "doc-123",
            "asset_class_tags": ["eq_dm"],
            "region_tags": ["us"],
            "theme_tags": ["inflation"],
            "risk_tags": ["duration_risk"],
            "instrument_tags": [],
            "style_tags": [],
            "macro_regime_tags": ["soft_landing"],
            "all_tags": [],
            "confidence": 0.85,
        },
        "confidence": {
            "document_id": "doc-123",
            "overall_confidence": 0.85,
            "confidence_band": "HIGH",
            "extraction_coverage": 0.9,
            "field_confidences": [],
            "analyst_attention_required": False,
            "attention_reasons": [],
        },
        "processing_timestamp": datetime.now(UTC).isoformat(),
        "pipeline_version": "0.1.0",
        "total_processing_time_seconds": 10.5,
    }


def test_validate_schema_valid() -> None:
    """Test schema validation passes for valid output."""
    data = _make_valid_output()
    errors = validate_schema(data)
    assert errors == []


def test_validate_schema_missing_field() -> None:
    """Test schema validation catches missing required fields."""
    data = _make_valid_output()
    del data["document_id"]
    errors = validate_schema(data)
    assert len(errors) > 0
    assert "document_id" in errors[0]


def test_validate_taxonomy_valid() -> None:
    """Test taxonomy validation passes for valid codes."""
    data = _make_valid_output()
    errors = validate_taxonomy(data)
    assert errors == []


def test_validate_taxonomy_invalid_category() -> None:
    """Test taxonomy validation catches invalid category."""
    data = _make_valid_output()
    data["allocation_calls"][0]["asset_class_category"] = "INVALID_CAT"
    errors = validate_taxonomy(data)
    assert any("invalid category" in e for e in errors)


def test_validate_taxonomy_invalid_sub_asset() -> None:
    """Test taxonomy validation catches invalid sub_asset."""
    data = _make_valid_output()
    data["allocation_calls"][0]["sub_asset_class"] = "INVALID_SUB"
    errors = validate_taxonomy(data)
    assert any("invalid sub_asset" in e for e in errors)


def test_validate_tags_valid() -> None:
    """Test tag validation passes for valid tags."""
    data = _make_valid_output()
    errors = validate_tags(data)
    assert errors == []


def test_validate_tags_invalid_theme() -> None:
    """Test tag validation catches invalid theme tag."""
    data = _make_valid_output()
    data["tags"]["theme_tags"] = ["invalid_theme_xyz"]
    errors = validate_tags(data)
    assert len(errors) == 1
    assert "theme_tags" in errors[0]


def test_validate_citations_valid() -> None:
    """Test citation validation passes for valid citations."""
    data = _make_valid_output()
    errors = validate_citations(data)
    assert errors == []


def test_validate_citations_missing() -> None:
    """Test citation validation catches missing citations."""
    data = _make_valid_output()
    data["allocation_calls"][0]["citations"] = []
    errors = validate_citations(data)
    assert len(errors) == 1
    assert "missing citations" in errors[0]


def test_validate_output_all_valid() -> None:
    """Test full validation passes for valid output."""
    data = _make_valid_output()
    errors = validate_output(data)
    assert errors == []


def test_validate_output_multiple_errors() -> None:
    """Test full validation catches multiple errors."""
    data = _make_valid_output()
    data["allocation_calls"][0]["asset_class_category"] = "INVALID"
    data["allocation_calls"][0]["sub_asset_class"] = "INVALID"
    errors = validate_output(data)
    assert len(errors) == 2
