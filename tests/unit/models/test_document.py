"""Unit tests for document extraction models."""

import pytest
from pydantic import ValidationError

from src.models.document import DocumentBlock, DocumentJSON, ExtractedTable, TableCell
from src.models.enums import BlockType


class TestDocumentBlock:
    def test_valid_block(self) -> None:
        b = DocumentBlock(
            block_id="1_0", page=1, text="Hello", block_type=BlockType.PARAGRAPH, confidence=0.95
        )
        assert b.block_id == "1_0"
        assert b.page == 1

    def test_page_must_be_positive(self) -> None:
        with pytest.raises(ValidationError):
            DocumentBlock(block_id="0_0", page=0, text="x", block_type=BlockType.PARAGRAPH, confidence=0.9)

    def test_confidence_bounds(self) -> None:
        DocumentBlock(block_id="1_0", page=1, text="x", block_type=BlockType.PARAGRAPH, confidence=0.0)
        DocumentBlock(block_id="1_0", page=1, text="x", block_type=BlockType.PARAGRAPH, confidence=1.0)
        with pytest.raises(ValidationError):
            DocumentBlock(block_id="1_0", page=1, text="x", block_type=BlockType.PARAGRAPH, confidence=1.1)
        with pytest.raises(ValidationError):
            DocumentBlock(block_id="1_0", page=1, text="x", block_type=BlockType.PARAGRAPH, confidence=-0.1)


class TestExtractedTable:
    def test_valid_table(self) -> None:
        t = ExtractedTable(
            table_id="t1", page=1, cells=[TableCell(row=0, col=0, text="A")], row_count=1, col_count=1
        )
        assert t.table_id == "t1"

    def test_page_must_be_positive(self) -> None:
        with pytest.raises(ValidationError):
            ExtractedTable(table_id="t1", page=0, cells=[], row_count=0, col_count=0)


class TestDocumentJSON:
    def test_valid_document(self) -> None:
        d = DocumentJSON(
            document_id="d1", blob_id="b1", file_hash="abc123",
            blocks=[], tables=[], page_count=5, extraction_coverage=0.8
        )
        assert d.document_id == "d1"
        assert d.ocr_pages == []

    def test_page_count_must_be_positive(self) -> None:
        with pytest.raises(ValidationError):
            DocumentJSON(
                document_id="d1", blob_id="b1", file_hash="h",
                blocks=[], tables=[], page_count=0, extraction_coverage=0.5
            )

    def test_extraction_coverage_bounds(self) -> None:
        DocumentJSON(document_id="d1", blob_id="b1", file_hash="h", blocks=[], tables=[], page_count=1, extraction_coverage=0.0)
        DocumentJSON(document_id="d1", blob_id="b1", file_hash="h", blocks=[], tables=[], page_count=1, extraction_coverage=1.0)
        with pytest.raises(ValidationError):
            DocumentJSON(document_id="d1", blob_id="b1", file_hash="h", blocks=[], tables=[], page_count=1, extraction_coverage=1.1)
