"""Tests for Stage 10: Extraction Quality Scoring."""

import pytest

from src.models.core import Citation
from src.models.document import DocumentBlock, DocumentJSON, ExtractedTable, TableCell
from src.models.enums import BlockType, CallDirection, ConfidenceBand
from src.models.pipeline import RetrievedChunk
from src.pipeline.stages.s10_confidence import (
    score_text_coverage,
    score_ocr_quality,
    score_table_success,
    score_structure_quality,
    score_extraction_quality,
    has_explicit_call_language,
    compute_confidence_band,
    has_explicit_mention,
    compute_word_overlap,
    compute_entailment_heuristic,
    score_evidence_strength,
    score_call_evidence,
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


# --- Evidence Strength Scoring Tests (Task 7.2) ---


def _make_chunk(chunk_id: str, text: str, page: int = 1) -> RetrievedChunk:
    return RetrievedChunk(
        chunk_id=chunk_id,
        block_ids=["1_0"],
        page=page,
        text=text,
        score=0.9,
    )


def _make_citation(chunk_id: str, page: int = 1, text_span: str | None = None) -> Citation:
    return Citation(chunk_id=chunk_id, page=page, text_span=text_span)


class TestExplicitMention:
    def test_direct_match(self):
        assert has_explicit_mention("BlackRock", "Report by BlackRock Asset Management") == 1.0

    def test_case_insensitive(self):
        assert has_explicit_mention("BLACKROCK", "report by blackrock") == 1.0

    def test_multi_word_all_present(self):
        score = has_explicit_mention("US Large Cap", "We favor US equities, especially large cap stocks")
        assert score == 0.8

    def test_no_match(self):
        assert has_explicit_mention("BlackRock", "Report by Vanguard") == 0.0

    def test_none_value(self):
        assert has_explicit_mention(None, "Some text") == 0.0


class TestWordOverlap:
    def test_full_overlap(self):
        assert compute_word_overlap("equities bonds", "We like equities and bonds") == 1.0

    def test_partial_overlap(self):
        score = compute_word_overlap("equities bonds commodities", "We like equities and bonds")
        assert 0.5 < score < 1.0

    def test_no_overlap(self):
        assert compute_word_overlap("equities", "fixed income only") == 0.0

    def test_empty_value(self):
        assert compute_word_overlap("", "some text") == 0.0


class TestEntailmentHeuristic:
    def test_supporting_context(self):
        assert compute_entailment_heuristic("equities", "We expect equities to outperform") == 1.0

    def test_assertive_pattern(self):
        assert compute_entailment_heuristic("bonds", "Our bonds allocation is increasing") == 1.0

    def test_partial_match(self):
        score = compute_entailment_heuristic("equities outlook", "equities look strong")
        assert score == 0.5

    def test_no_support(self):
        assert compute_entailment_heuristic("gold", "silver prices rising") == 0.0


class TestEvidenceStrength:
    def test_strong_evidence(self):
        chunks = [_make_chunk("c1", "BlackRock expects equities to outperform in 2024")]
        citations = [_make_citation("c1")]
        score = score_evidence_strength("BlackRock", citations, chunks)
        assert score >= 0.5

    def test_no_citations(self):
        assert score_evidence_strength("value", [], []) == 0.0

    def test_missing_chunk(self):
        citations = [_make_citation("missing")]
        assert score_evidence_strength("value", citations, []) == 0.0

    def test_best_citation_wins(self):
        chunks = [
            _make_chunk("c1", "Unrelated text about weather"),
            _make_chunk("c2", "BlackRock is overweight equities"),
        ]
        citations = [_make_citation("c1"), _make_citation("c2")]
        score = score_evidence_strength("BlackRock", citations, chunks)
        assert score >= 0.5


class TestCallEvidence:
    def test_explicit_overweight_high_score(self):
        chunks = [_make_chunk("c1", "We are overweight US equities")]
        citations = [_make_citation("c1")]
        score = score_call_evidence(CallDirection.OVERWEIGHT, citations, chunks)
        assert score >= 0.5

    def test_explicit_underweight(self):
        chunks = [_make_chunk("c1", "Underweight European bonds due to rate risk")]
        citations = [_make_citation("c1")]
        score = score_call_evidence(CallDirection.UNDERWEIGHT, citations, chunks)
        assert score >= 0.5

    def test_no_explicit_language_lower_score(self):
        chunks = [_make_chunk("c1", "Equities look attractive")]
        citations = [_make_citation("c1")]
        score = score_call_evidence(CallDirection.OVERWEIGHT, citations, chunks)
        assert score < 0.5

    def test_uncertain_no_bonus(self):
        chunks = [_make_chunk("c1", "We are overweight equities")]
        citations = [_make_citation("c1")]
        score = score_call_evidence(CallDirection.UNCERTAIN, citations, chunks)
        assert score < 0.5

    def test_no_citations_zero(self):
        assert score_call_evidence(CallDirection.OVERWEIGHT, [], []) == 0.0

    def test_text_span_included(self):
        chunks = [_make_chunk("c1", "General market commentary")]
        citations = [_make_citation("c1", text_span="overweight equities")]
        score = score_call_evidence(CallDirection.OVERWEIGHT, citations, chunks)
        assert score >= 0.5
