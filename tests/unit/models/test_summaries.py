"""Unit tests for summary models."""

import pytest
from pydantic import ValidationError
from src.models.core import Citation
from src.models.summaries import DocumentSummaries, KeyTakeaway


class TestKeyTakeaway:
    def test_valid_takeaway(self) -> None:
        c = Citation(chunk_id="c1", page=1)
        t = KeyTakeaway(text="Key insight here", citations=[c])
        assert t.text == "Key insight here"

    def test_text_max_length(self) -> None:
        c = Citation(chunk_id="c1", page=1)
        with pytest.raises(ValidationError):
            KeyTakeaway(text="x" * 201, citations=[c])

    def test_citations_required(self) -> None:
        with pytest.raises(ValidationError):
            KeyTakeaway(text="Some text", citations=[])


class TestDocumentSummaries:
    def test_valid_summaries(self) -> None:
        c = Citation(chunk_id="c1", page=1)
        takeaways = [KeyTakeaway(text=f"Takeaway {i}", citations=[c]) for i in range(3)]
        s = DocumentSummaries(
            document_id="d1",
            executive_summary="x" * 100,
            search_descriptor="x" * 50,
            key_takeaways=takeaways,
            citations=[c],
            confidence=0.85,
        )
        assert s.document_id == "d1"

    def test_executive_summary_min_length(self) -> None:
        c = Citation(chunk_id="c1", page=1)
        takeaways = [KeyTakeaway(text=f"Takeaway {i}", citations=[c]) for i in range(3)]
        with pytest.raises(ValidationError):
            DocumentSummaries(
                document_id="d1",
                executive_summary="x" * 99,  # min 100
                search_descriptor="x" * 50,
                key_takeaways=takeaways,
                citations=[c],
                confidence=0.5,
            )

    def test_executive_summary_max_length(self) -> None:
        c = Citation(chunk_id="c1", page=1)
        takeaways = [KeyTakeaway(text=f"Takeaway {i}", citations=[c]) for i in range(3)]
        with pytest.raises(ValidationError):
            DocumentSummaries(
                document_id="d1",
                executive_summary="x" * 1001,  # max 1000
                search_descriptor="x" * 50,
                key_takeaways=takeaways,
                citations=[c],
                confidence=0.5,
            )

    def test_key_takeaways_min_count(self) -> None:
        c = Citation(chunk_id="c1", page=1)
        takeaways = [KeyTakeaway(text=f"Takeaway {i}", citations=[c]) for i in range(2)]
        with pytest.raises(ValidationError):
            DocumentSummaries(
                document_id="d1",
                executive_summary="x" * 100,
                search_descriptor="x" * 50,
                key_takeaways=takeaways,  # min 3
                citations=[c],
                confidence=0.5,
            )

    def test_key_takeaways_max_count(self) -> None:
        c = Citation(chunk_id="c1", page=1)
        takeaways = [KeyTakeaway(text=f"Takeaway {i}", citations=[c]) for i in range(6)]
        with pytest.raises(ValidationError):
            DocumentSummaries(
                document_id="d1",
                executive_summary="x" * 100,
                search_descriptor="x" * 50,
                key_takeaways=takeaways,  # max 5
                citations=[c],
                confidence=0.5,
            )

    def test_citations_required(self) -> None:
        c = Citation(chunk_id="c1", page=1)
        takeaways = [KeyTakeaway(text=f"Takeaway {i}", citations=[c]) for i in range(3)]
        with pytest.raises(ValidationError):
            DocumentSummaries(
                document_id="d1",
                executive_summary="x" * 100,
                search_descriptor="x" * 50,
                key_takeaways=takeaways,
                citations=[],  # min 1
                confidence=0.5,
            )
