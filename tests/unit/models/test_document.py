"""Unit tests for document extraction models."""

import pytest
from pydantic import ValidationError

from models.document import DocumentBlock, DocumentJSON, ExtractedTable, TableCell
from models.enums import BlockType


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

    def test_cell_row_bounds(self) -> None:
        # Valid: cell row within bounds (0-indexed, so row=1 is valid for row_count=2)
        ExtractedTable(
            table_id="t1",
            page=1,
            cells=[TableCell(row=0, col=0, text="A"), TableCell(row=1, col=0, text="B")],
            row_count=2,
            col_count=1,
        )
        # Invalid: cell row exceeds row_count
        with pytest.raises(ValidationError, match="Cell at row=100.*exceeds table row_count=2"):
            ExtractedTable(
                table_id="t1",
                page=1,
                cells=[TableCell(row=100, col=0, text="Bad")],
                row_count=2,
                col_count=1,
            )

    def test_cell_col_bounds(self) -> None:
        # Valid: cell col within bounds
        ExtractedTable(
            table_id="t1",
            page=1,
            cells=[TableCell(row=0, col=0, text="A"), TableCell(row=0, col=1, text="B")],
            row_count=1,
            col_count=2,
        )
        # Invalid: cell col exceeds col_count
        with pytest.raises(ValidationError, match="Cell at row=0, col=50.*exceeds table col_count=3"):
            ExtractedTable(
                table_id="t1",
                page=1,
                cells=[TableCell(row=0, col=50, text="Bad")],
                row_count=1,
                col_count=3,
            )

    def test_duplicate_cell_positions(self) -> None:
        # Invalid: duplicate cell at same (row, col)
        with pytest.raises(ValidationError, match="Duplicate cell at position.*row=0, col=0"):
            ExtractedTable(
                table_id="t1",
                page=1,
                cells=[
                    TableCell(row=0, col=0, text="First"),
                    TableCell(row=0, col=0, text="Duplicate"),
                ],
                row_count=1,
                col_count=1,
            )

    def test_tight_bounds_validation(self) -> None:
        # Valid: tight bounds (max row=1, row_count=2; max col=1, col_count=2)
        ExtractedTable(
            table_id="t1",
            page=1,
            cells=[
                TableCell(row=0, col=0, text="A"),
                TableCell(row=1, col=1, text="B"),
            ],
            row_count=2,
            col_count=2,
        )
        # Note: The tight bounds validation is already covered by the existing
        # row/col bounds checks, which ensure max_row < row_count and max_col < col_count


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

    def test_ocr_pages_bounds(self) -> None:
        # Valid: within bounds
        DocumentJSON(
            document_id="d1", blob_id="b1", file_hash="h",
            blocks=[], tables=[], page_count=10, extraction_coverage=0.8,
            ocr_pages=[1, 5, 10]
        )
        # Invalid: page 0
        with pytest.raises(ValidationError, match="ocr_pages contains invalid page 0"):
            DocumentJSON(
                document_id="d1", blob_id="b1", file_hash="h",
                blocks=[], tables=[], page_count=10, extraction_coverage=0.8,
                ocr_pages=[0]
            )
        # Invalid: page > page_count
        with pytest.raises(ValidationError, match="ocr_pages contains invalid page 11"):
            DocumentJSON(
                document_id="d1", blob_id="b1", file_hash="h",
                blocks=[], tables=[], page_count=10, extraction_coverage=0.8,
                ocr_pages=[11]
            )

    def test_vision_pages_bounds(self) -> None:
        # Valid: within bounds
        DocumentJSON(
            document_id="d1", blob_id="b1", file_hash="h",
            blocks=[], tables=[], page_count=10, extraction_coverage=0.8,
            vision_pages=[1, 5, 10]
        )
        # Invalid: page 0
        with pytest.raises(ValidationError, match="vision_pages contains invalid page 0"):
            DocumentJSON(
                document_id="d1", blob_id="b1", file_hash="h",
                blocks=[], tables=[], page_count=10, extraction_coverage=0.8,
                vision_pages=[0]
            )
        # Invalid: page > page_count
        with pytest.raises(ValidationError, match="vision_pages contains invalid page 15"):
            DocumentJSON(
                document_id="d1", blob_id="b1", file_hash="h",
                blocks=[], tables=[], page_count=10, extraction_coverage=0.8,
                vision_pages=[15]
            )

    def test_block_page_bounds(self) -> None:
        # Valid: block page within bounds
        block = DocumentBlock(
            block_id="5_0", page=5, text="Text", block_type=BlockType.PARAGRAPH, confidence=0.9
        )
        DocumentJSON(
            document_id="d1", blob_id="b1", file_hash="h",
            blocks=[block], tables=[], page_count=10, extraction_coverage=0.8
        )
        # Invalid: block page > page_count
        block_invalid = DocumentBlock(
            block_id="999_0", page=999, text="Text", block_type=BlockType.PARAGRAPH, confidence=0.9
        )
        with pytest.raises(
            ValidationError,
            match="Block 999_0 references page 999 but document only has 10 pages"
        ):
            DocumentJSON(
                document_id="d1", blob_id="b1", file_hash="h",
                blocks=[block_invalid], tables=[], page_count=10, extraction_coverage=0.8
            )

    def test_table_page_bounds(self) -> None:
        # Valid: table page within bounds
        table = ExtractedTable(
            table_id="t5", page=5, cells=[], row_count=0, col_count=0
        )
        DocumentJSON(
            document_id="d1", blob_id="b1", file_hash="h",
            blocks=[], tables=[table], page_count=10, extraction_coverage=0.8
        )
        # Invalid: table page > page_count
        table_invalid = ExtractedTable(
            table_id="t999", page=999, cells=[], row_count=0, col_count=0
        )
        with pytest.raises(
            ValidationError,
            match="Table t999 references page 999 but document only has 10 pages"
        ):
            DocumentJSON(
                document_id="d1", blob_id="b1", file_hash="h",
                blocks=[], tables=[table_invalid], page_count=10, extraction_coverage=0.8
            )

    def test_duplicate_block_ids(self) -> None:
        # Valid: unique block IDs
        block1 = DocumentBlock(
            block_id="1_0", page=1, text="Text1", block_type=BlockType.PARAGRAPH, confidence=0.9
        )
        block2 = DocumentBlock(
            block_id="1_1", page=1, text="Text2", block_type=BlockType.PARAGRAPH, confidence=0.9
        )
        DocumentJSON(
            document_id="d1", blob_id="b1", file_hash="h",
            blocks=[block1, block2], tables=[], page_count=10, extraction_coverage=0.8
        )
        # Invalid: duplicate block_id
        block_dup = DocumentBlock(
            block_id="1_0", page=1, text="Duplicate", block_type=BlockType.PARAGRAPH, confidence=0.9
        )
        with pytest.raises(ValidationError, match="Duplicate block_id found: 1_0"):
            DocumentJSON(
                document_id="d1", blob_id="b1", file_hash="h",
                blocks=[block1, block_dup], tables=[], page_count=10, extraction_coverage=0.8
            )

    def test_duplicate_table_ids(self) -> None:
        # Valid: unique table IDs
        table1 = ExtractedTable(table_id="t1", page=1, cells=[], row_count=0, col_count=0)
        table2 = ExtractedTable(table_id="t2", page=1, cells=[], row_count=0, col_count=0)
        DocumentJSON(
            document_id="d1", blob_id="b1", file_hash="h",
            blocks=[], tables=[table1, table2], page_count=10, extraction_coverage=0.8
        )
        # Invalid: duplicate table_id
        table_dup = ExtractedTable(table_id="t1", page=1, cells=[], row_count=0, col_count=0)
        with pytest.raises(ValidationError, match="Duplicate table_id found: t1"):
            DocumentJSON(
                document_id="d1", blob_id="b1", file_hash="h",
                blocks=[], tables=[table1, table_dup], page_count=10, extraction_coverage=0.8
            )
