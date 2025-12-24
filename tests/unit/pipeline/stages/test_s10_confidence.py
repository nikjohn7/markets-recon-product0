"""Tests for Stage 10: Extraction Quality Scoring."""

import pytest

from src.models.document import DocumentBlock, DocumentJSON, ExtractedTable, TableCell
from src.models.enums import BlockType, CallDirection, ConfidenceBand
from src.pipeline.stages.s10_confidence import (
    score_text_coverage,
    score_ocr_quality,
    score_table_success,
    score_structure_quality,
    score_extraction_quality,
    has_explicit_call_language,
    compute_confidence_band,
)


def _make_block(block_id: str, page: int, block_type: BlockType, text: str = "Test") -> DocumentBlock:
    return DocumentBlock(
        block_id=block_id,
        page=page,
        text=text,
        block_type=block_type,
        confidence=0.9,
    )


def _make_doc(
    blocks: list[DocumentBlock] | None = None,
    tables: list[ExtractedTable] | None = None,
    extraction_coverage: float = 1.0,
    ocr_pages: list[int] | None = None,
) -> DocumentJSON:
    return DocumentJSON(
        document_id="doc_1",
        blob_id="blob_1",
        file_hash="hash_1",
        blocks=blocks or [],
        tables=tables or [],
        page_count=3,
        extraction_coverage=extraction_coverage,
        ocr_pages=ocr_pages or [],
    )


class TestTextCoverageScoring:
    def test_full_coverage(self):
        doc = _make_doc(extraction_coverage=1.0)
        assert score_text_coverage(doc) == 1.0

    def test_partial_coverage(self):
        doc = _make_doc(extraction_coverage=0.67)
        assert score_text_coverage(doc) == 0.67

    def test_zero_coverage(self):
        doc = _make_doc(extraction_coverage=0.0)
        assert score_text_coverage(doc) == 0.0


class TestOCRQualityScoring:
    def test_no_ocr_pages_full_credit(self):
        doc = _make_doc(ocr_pages=[])
        assert score_ocr_quality(doc) == 1.0

    def test_ocr_with_clean_text(self):
        blocks = [_make_block("1_0", 1, BlockType.PARAGRAPH, "Clean text without issues")]
        doc = _make_doc(blocks=blocks, ocr_pages=[1])
        assert score_ocr_quality(doc) == 1.0

    def test_ocr_with_garbled_chars(self):
        blocks = [_make_block("1_0", 1, BlockType.PARAGRAPH, "Text with □■● garbled")]
        doc = _make_doc(blocks=blocks, ocr_pages=[1])
        score = score_ocr_quality(doc)
        assert 0.0 < score < 1.0

    def test_ocr_empty_text(self):
        doc = _make_doc(blocks=[], ocr_pages=[1])
        assert score_ocr_quality(doc) == 0.0


class TestTableSuccessScoring:
    def test_no_tables_full_credit(self):
        doc = _make_doc(tables=[])
        assert score_table_success(doc) == 1.0

    def test_all_tables_have_content(self):
        tables = [
            ExtractedTable(
                table_id="1_tbl_0",
                page=1,
                cells=[TableCell(row=0, col=0, text="Data")],
                row_count=1,
                col_count=1,
            )
        ]
        doc = _make_doc(tables=tables)
        assert score_table_success(doc) == 1.0

    def test_some_tables_empty(self):
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
        doc = _make_doc(tables=tables)
        assert score_table_success(doc) == 0.5


class TestStructureQualityScoring:
    def test_empty_blocks(self):
        doc = _make_doc(blocks=[])
        assert score_structure_quality(doc) == 0.0

    def test_good_structure_varied_types(self):
        blocks = [
            _make_block("1_0", 1, BlockType.HEADING),
            _make_block("1_1", 1, BlockType.PARAGRAPH),
            _make_block("1_2", 1, BlockType.BULLET),
        ]
        doc = _make_doc(blocks=blocks)
        assert score_structure_quality(doc) == 1.0

    def test_headings_and_paragraphs_only(self):
        blocks = [
            _make_block("1_0", 1, BlockType.HEADING),
            _make_block("1_1", 1, BlockType.PARAGRAPH),
        ]
        doc = _make_doc(blocks=blocks)
        score = score_structure_quality(doc)
        assert 0.5 < score < 1.0

    def test_single_block_type(self):
        blocks = [_make_block("1_0", 1, BlockType.PARAGRAPH)]
        doc = _make_doc(blocks=blocks)
        score = score_structure_quality(doc)
        assert score == 0.3  # Only paragraph credit


class TestExtractionQualityScoring:
    def test_perfect_extraction(self):
        blocks = [
            _make_block("1_0", 1, BlockType.HEADING),
            _make_block("1_1", 1, BlockType.PARAGRAPH),
            _make_block("1_2", 1, BlockType.BULLET),
        ]
        doc = _make_doc(blocks=blocks, extraction_coverage=1.0)
        score = score_extraction_quality(doc)
        assert score == 1.0

    def test_weighted_aggregation(self):
        # 50% coverage, no OCR, no tables, good structure
        blocks = [
            _make_block("1_0", 1, BlockType.HEADING),
            _make_block("1_1", 1, BlockType.PARAGRAPH),
            _make_block("1_2", 1, BlockType.BULLET),
        ]
        doc = _make_doc(blocks=blocks, extraction_coverage=0.5)
        score = score_extraction_quality(doc)
        # 0.5 * 0.4 + 1.0 * 0.2 + 1.0 * 0.2 + 1.0 * 0.2 = 0.2 + 0.6 = 0.8
        assert score == pytest.approx(0.8, rel=0.01)


class TestExplicitCallLanguage:
    def test_overweight_explicit(self):
        assert has_explicit_call_language(CallDirection.OVERWEIGHT, "We are overweight equities") == 1.0

    def test_overweight_prefer(self):
        assert has_explicit_call_language(CallDirection.OVERWEIGHT, "We prefer US stocks") == 1.0

    def test_underweight_explicit(self):
        assert has_explicit_call_language(CallDirection.UNDERWEIGHT, "Underweight bonds") == 1.0

    def test_underweight_avoid(self):
        assert has_explicit_call_language(CallDirection.UNDERWEIGHT, "Avoid high yield") == 1.0

    def test_neutral_explicit(self):
        assert has_explicit_call_language(CallDirection.NEUTRAL, "Neutral on commodities") == 1.0

    def test_uncertain_always_zero(self):
        assert has_explicit_call_language(CallDirection.UNCERTAIN, "overweight equities") == 0.0

    def test_no_match(self):
        assert has_explicit_call_language(CallDirection.OVERWEIGHT, "Equities look good") == 0.0

    def test_case_insensitive(self):
        assert has_explicit_call_language(CallDirection.OVERWEIGHT, "OVERWEIGHT bonds") == 1.0


class TestConfidenceBand:
    def test_high_band(self):
        assert compute_confidence_band(0.80) == ConfidenceBand.HIGH
        assert compute_confidence_band(0.95) == ConfidenceBand.HIGH

    def test_medium_band(self):
        assert compute_confidence_band(0.60) == ConfidenceBand.MEDIUM
        assert compute_confidence_band(0.79) == ConfidenceBand.MEDIUM

    def test_low_band(self):
        assert compute_confidence_band(0.59) == ConfidenceBand.LOW
        assert compute_confidence_band(0.0) == ConfidenceBand.LOW
