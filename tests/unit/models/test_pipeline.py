"""Unit tests for pipeline stage I/O models."""

import pytest
from pydantic import ValidationError

from src.models.document import DocumentBlock
from src.models.enums import BlockType
from src.models.pipeline import (
    CandidateSet,
    CleanedDocument,
    IngestResult,
    RetrievedChunk,
    Section,
)


class TestIngestResult:
    def test_valid_ingest(self) -> None:
        r = IngestResult(
            document_id="d1",
            blob_id="b1",
            file_hash="abc123",
            is_duplicate=False,
            source_metadata={"filename": "test.pdf"},
        )
        assert r.document_id == "d1"
        assert r.is_duplicate is False


class TestSection:
    def test_valid_section(self) -> None:
        s = Section(
            section_id="d1_sec_0",
            title="Market Overview",
            start_block_id="1_0",
            end_block_id="1_5",
            section_type="macro",
        )
        assert s.title == "Market Overview"

    def test_section_optional_fields(self) -> None:
        s = Section(
            section_id="d1_sec_1",
            start_block_id="2_0",
            end_block_id="2_3",
        )
        assert s.title is None
        assert s.section_type is None


class TestCleanedDocument:
    def test_valid_cleaned_doc(self) -> None:
        block = DocumentBlock(
            block_id="1_0", page=1, text="Test", block_type=BlockType.PARAGRAPH, confidence=0.9
        )
        s = Section(section_id="s1", start_block_id="1_0", end_block_id="1_5")
        cd = CleanedDocument(
            document_id="d1",
            blocks=[block],
            sections=[s],
            removed_boilerplate_count=5,
        )
        assert len(cd.blocks) == 1
        assert cd.removed_boilerplate_count == 5


class TestRetrievedChunk:
    def test_valid_chunk(self) -> None:
        c = RetrievedChunk(
            chunk_id="d1_0",
            text="Some relevant text",
            block_ids=["1_0", "1_1"],
            page=1,
            score=0.85,
            section="macro",
        )
        assert c.score == 0.85
        assert c.section == "macro"

    def test_page_must_be_positive(self) -> None:
        with pytest.raises(ValidationError):
            RetrievedChunk(chunk_id="c1", text="x", block_ids=[], page=0, score=0.5)

    def test_section_optional(self) -> None:
        c = RetrievedChunk(chunk_id="c1", text="x", block_ids=[], page=1, score=0.5)
        assert c.section is None


class TestCandidateSet:
    def test_valid_candidate_set(self) -> None:
        chunk = RetrievedChunk(chunk_id="d1_0", text="x", block_ids=["1_0"], page=1, score=0.9)
        cs = CandidateSet(
            document_id="d1",
            candidates=[chunk],
            keyword_matches={"overweight": ["1_0", "1_1"]},
            total_chunks_reviewed=10,
        )
        assert len(cs.candidates) == 1
        assert "overweight" in cs.keyword_matches

    def test_empty_candidates_allowed(self) -> None:
        cs = CandidateSet(document_id="d1", candidates=[], total_chunks_reviewed=0)
        assert len(cs.candidates) == 0
