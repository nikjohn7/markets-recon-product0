"""Unit tests for confidence scoring calibration."""

import pytest

from src.models.confidence import compute_confidence_band as compute_model_band
from src.models.document import DocumentBlock, DocumentJSON, ExtractedTable, TableCell
from src.models.enums import BlockType, ConfidenceBand
from src.pipeline.stages.s10_confidence import (
    compute_confidence_band as compute_stage_band,
    score_extraction_quality,
)


def _make_block(block_id: str, page: int, text: str) -> DocumentBlock:
    return DocumentBlock(
        block_id=block_id,
        page=page,
        text=text,
        block_type=BlockType.PARAGRAPH,
        confidence=0.9,
    )


def _make_doc(
    blocks: list[DocumentBlock],
    tables: list[ExtractedTable],
    extraction_coverage: float,
    ocr_pages: list[int],
) -> DocumentJSON:
    return DocumentJSON(
        document_id="doc_1",
        blob_id="blob_1",
        file_hash="hash_1",
        blocks=blocks,
        tables=tables,
        page_count=2,
        extraction_coverage=extraction_coverage,
        ocr_pages=ocr_pages,
    )


class TestConfidenceBandBoundaries:
    @pytest.mark.parametrize(
        ("score", "expected"),
        [
            (0.80, ConfidenceBand.HIGH),
            (0.60, ConfidenceBand.MEDIUM),
            (0.59, ConfidenceBand.LOW),
        ],
    )
    def test_boundary_values_match(self, score: float, expected: ConfidenceBand) -> None:
        assert compute_model_band(score) == expected
        assert compute_stage_band(score) == expected


class TestExtractionQualityWeights:
    def test_includes_ocr_tables_and_structure_components(self) -> None:
        blocks = [_make_block("1_0", 1, "AA\x00\x01")]
        tables = [
            ExtractedTable(
                table_id="1_tbl_0",
                page=1,
                cells=[TableCell(row=0, col=0, text="Data")],
                row_count=1,
                col_count=1,
            ),
            ExtractedTable(table_id="1_tbl_1", page=1, cells=[], row_count=0, col_count=0),
        ]
        doc = _make_doc(
            blocks=blocks,
            tables=tables,
            extraction_coverage=0.5,
            ocr_pages=[1],
        )

        score = score_extraction_quality(doc)
        expected = (0.5 * 0.4) + (0.6 * 0.2) + (0.5 * 0.2) + (0.3 * 0.2)
        assert score == pytest.approx(expected, abs=1e-6)
