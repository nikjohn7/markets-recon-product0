"""Unit tests for tag models."""

import pytest
from pydantic import ValidationError

from models.enums import TagType
from models.tags import Tag, TagSet


class TestTag:
    def test_valid_tag(self) -> None:
        t = Tag(tag_type=TagType.THEME, value="inflation", confidence=0.9, source="llm")
        assert t.tag_type == TagType.THEME
        assert t.source == "llm"

    def test_confidence_bounds(self) -> None:
        Tag(tag_type=TagType.REGION, value="US", confidence=0.0, source="rule")
        Tag(tag_type=TagType.REGION, value="US", confidence=1.0, source="rule")
        with pytest.raises(ValidationError):
            Tag(tag_type=TagType.REGION, value="US", confidence=1.1, source="rule")
        with pytest.raises(ValidationError):
            Tag(tag_type=TagType.REGION, value="US", confidence=-0.1, source="rule")

    def test_source_must_be_rule_or_llm(self) -> None:
        Tag(tag_type=TagType.THEME, value="inflation", confidence=0.9, source="rule")
        Tag(tag_type=TagType.THEME, value="inflation", confidence=0.9, source="llm")
        with pytest.raises(ValidationError):
            Tag(tag_type=TagType.THEME, value="inflation", confidence=0.9, source="invalid")


class TestTagSet:
    def test_valid_tagset(self) -> None:
        ts = TagSet(
            document_id="d1",
            asset_class_tags=["equities"],
            region_tags=["US", "Europe"],
            theme_tags=["inflation"],
            risk_tags=[],
            instrument_tags=[],
            style_tags=[],
            macro_regime_tags=["late_cycle"],
            confidence=0.85,
        )
        assert ts.document_id == "d1"
        assert len(ts.region_tags) == 2

    def test_all_tag_categories_present(self) -> None:
        # Ensure all 7 tag categories are required
        with pytest.raises(ValidationError):
            TagSet(
                document_id="d1",
                asset_class_tags=["equities"],
                # Missing other tag categories
                confidence=0.5,
            )

    def test_confidence_bounds(self) -> None:
        base = {
            "document_id": "d1",
            "asset_class_tags": [],
            "region_tags": [],
            "theme_tags": [],
            "risk_tags": [],
            "instrument_tags": [],
            "style_tags": [],
            "macro_regime_tags": [],
        }
        TagSet(**base, confidence=0.0)
        TagSet(**base, confidence=1.0)
        with pytest.raises(ValidationError):
            TagSet(**base, confidence=1.1)
