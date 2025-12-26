"""Unit tests for core models (Citation, BoundingBox)."""

import pytest
from pydantic import ValidationError
from src.models.core import BoundingBox, Citation


class TestCitation:
    def test_valid_citation(self) -> None:
        c = Citation(chunk_id="chunk_1", page=1)
        assert c.chunk_id == "chunk_1"
        assert c.page == 1
        assert c.block_ids == []
        assert c.text_span is None

    def test_citation_with_all_fields(self) -> None:
        c = Citation(
            chunk_id="c1",
            block_ids=["b1", "b2"],
            page=5,
            text_span="Some text",
        )
        assert c.block_ids == ["b1", "b2"]
        assert c.text_span == "Some text"

    def test_citation_is_frozen(self) -> None:
        c = Citation(chunk_id="c1", page=1)
        with pytest.raises(ValidationError):
            c.chunk_id = "c2"  # type: ignore[misc]

    def test_page_must_be_positive(self) -> None:
        with pytest.raises(ValidationError):
            Citation(chunk_id="c1", page=0)
        with pytest.raises(ValidationError):
            Citation(chunk_id="c1", page=-1)

    def test_text_span_max_200_chars(self) -> None:
        # Exactly 200 chars should work
        Citation(chunk_id="c1", page=1, text_span="x" * 200)
        # 201 chars should fail
        with pytest.raises(ValidationError):
            Citation(chunk_id="c1", page=1, text_span="x" * 201)


class TestBoundingBox:
    def test_valid_bbox(self) -> None:
        b = BoundingBox(x0=0.0, y0=0.0, x1=1.0, y1=1.0)
        assert b.x0 == 0.0
        assert b.y1 == 1.0

    def test_bbox_boundary_values(self) -> None:
        # Min boundary
        BoundingBox(x0=0, y0=0, x1=0, y1=0)
        # Max boundary
        BoundingBox(x0=1, y0=1, x1=1, y1=1)

    def test_bbox_rejects_negative(self) -> None:
        with pytest.raises(ValidationError):
            BoundingBox(x0=-0.1, y0=0, x1=1, y1=1)

    def test_bbox_rejects_over_one(self) -> None:
        with pytest.raises(ValidationError):
            BoundingBox(x0=0, y0=0, x1=1.1, y1=1)
