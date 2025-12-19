"""Tests for Stage 2: Text cleaning and section detection."""

import pytest
from src.models.document import DocumentBlock, DocumentJSON
from src.models.enums import BlockType
from src.models.pipeline import CleanedDocument
from src.pipeline.stages.s2_clean import (
    _classify_section,
    _detect_boilerplate,
    _detect_sections,
    _is_disclaimer,
    _normalize_text,
    stage_clean,
)


class TestNormalizeText:
    """Test text normalization."""

    def test_fix_hyphenation(self) -> None:
        """Test fixing hyphenation across line breaks."""
        text = "invest-\nment strategy"
        result = _normalize_text(text)
        assert result == "investment strategy"

    def test_normalize_whitespace(self) -> None:
        """Test normalizing multiple spaces."""
        text = "multiple   spaces   here"
        result = _normalize_text(text)
        assert result == "multiple spaces here"

    def test_strip_whitespace(self) -> None:
        """Test stripping leading/trailing whitespace."""
        text = "  leading and trailing  "
        result = _normalize_text(text)
        assert result == "leading and trailing"

    def test_combined_normalization(self) -> None:
        """Test combined normalization."""
        text = "  invest-\nment   with  spaces  "
        result = _normalize_text(text)
        assert result == "investment with spaces"


class TestDisclaimerDetection:
    """Test disclaimer pattern detection."""

    def test_detect_informational_disclaimer(self) -> None:
        """Test detecting 'for informational purposes' disclaimer."""
        text = "This document is for informational purposes only."
        assert _is_disclaimer(text) is True

    def test_detect_past_performance_disclaimer(self) -> None:
        """Test detecting 'past performance' disclaimer."""
        text = "Past performance is not indicative of future results."
        assert _is_disclaimer(text) is True

    def test_detect_forward_looking_disclaimer(self) -> None:
        """Test detecting forward-looking statements disclaimer."""
        text = "Forward-looking statements involve risks."
        assert _is_disclaimer(text) is True

    def test_no_disclaimer(self) -> None:
        """Test text without disclaimer patterns."""
        text = "This is a regular paragraph about market outlook."
        assert _is_disclaimer(text) is False

    def test_case_insensitive_detection(self) -> None:
        """Test case-insensitive disclaimer detection."""
        text = "DISCLAIMER: This is important."
        assert _is_disclaimer(text) is True


class TestBoilerplateDetection:
    """Test boilerplate removal."""

    def test_detect_repeated_header(self) -> None:
        """Test detecting repeated headers across pages."""
        blocks = [
            DocumentBlock(
                block_id="1_0",
                page=1,
                text="Company Header",
                block_type=BlockType.HEADING,
                confidence=1.0,
            ),
            DocumentBlock(
                block_id="1_1",
                page=1,
                text="Content page 1",
                block_type=BlockType.PARAGRAPH,
                confidence=1.0,
            ),
            DocumentBlock(
                block_id="2_0",
                page=2,
                text="Company Header",
                block_type=BlockType.HEADING,
                confidence=1.0,
            ),
            DocumentBlock(
                block_id="2_1",
                page=2,
                text="Content page 2",
                block_type=BlockType.PARAGRAPH,
                confidence=1.0,
            ),
            DocumentBlock(
                block_id="3_0",
                page=3,
                text="Company Header",
                block_type=BlockType.HEADING,
                confidence=1.0,
            ),
            DocumentBlock(
                block_id="3_1",
                page=3,
                text="Content page 3",
                block_type=BlockType.PARAGRAPH,
                confidence=1.0,
            ),
        ]

        removed = _detect_boilerplate(blocks)
        # Should remove duplicates from pages 2 and 3
        assert len(removed) > 0

    def test_no_boilerplate_unique_content(self) -> None:
        """Test no boilerplate when all content is unique."""
        blocks = [
            DocumentBlock(
                block_id="1_0",
                page=1,
                text="Unique content 1",
                block_type=BlockType.PARAGRAPH,
                confidence=1.0,
            ),
            DocumentBlock(
                block_id="2_0",
                page=2,
                text="Unique content 2",
                block_type=BlockType.PARAGRAPH,
                confidence=1.0,
            ),
            DocumentBlock(
                block_id="3_0",
                page=3,
                text="Unique content 3",
                block_type=BlockType.PARAGRAPH,
                confidence=1.0,
            ),
        ]

        removed = _detect_boilerplate(blocks)
        assert len(removed) == 0


class TestSectionClassification:
    """Test section type classification."""

    def test_classify_macro_section(self) -> None:
        """Test classifying macro section."""
        text = "Macro Outlook"
        result = _classify_section(text)
        assert result == "macro"

    def test_classify_equities_section(self) -> None:
        """Test classifying equities section."""
        text = "Equities Outlook"
        result = _classify_section(text)
        assert result == "equities"

    def test_classify_fixed_income_section(self) -> None:
        """Test classifying fixed income section."""
        text = "Fixed Income Strategy"
        result = _classify_section(text)
        assert result == "fixed_income"

    def test_classify_risks_section(self) -> None:
        """Test classifying risks section."""
        text = "Risk Factors"
        result = _classify_section(text)
        assert result == "risks"

    def test_classify_appendix_section(self) -> None:
        """Test classifying appendix section."""
        text = "Appendix"
        result = _classify_section(text)
        assert result == "appendix"

    def test_unclassified_section(self) -> None:
        """Test unclassified section."""
        text = "Random Section Title"
        result = _classify_section(text)
        assert result is None


class TestSectionDetection:
    """Test section boundary detection."""

    def test_detect_sections_with_headings(self) -> None:
        """Test detecting sections with clear headings."""
        blocks = [
            DocumentBlock(
                block_id="1_0",
                page=1,
                text="Macro Outlook",
                block_type=BlockType.HEADING,
                confidence=1.0,
            ),
            DocumentBlock(
                block_id="1_1",
                page=1,
                text="Market conditions are favorable.",
                block_type=BlockType.PARAGRAPH,
                confidence=1.0,
            ),
            DocumentBlock(
                block_id="2_0",
                page=2,
                text="Equities",
                block_type=BlockType.HEADING,
                confidence=1.0,
            ),
            DocumentBlock(
                block_id="2_1",
                page=2,
                text="We are overweight equities.",
                block_type=BlockType.PARAGRAPH,
                confidence=1.0,
            ),
        ]

        sections = _detect_sections("test_doc", blocks)
        assert len(sections) == 2
        assert sections[0].title == "Macro Outlook"
        assert sections[0].section_type == "macro"
        assert sections[0].section_id == "test_doc_sec_0"
        assert sections[1].title == "Equities"
        assert sections[1].section_type == "equities"
        assert sections[1].section_id == "test_doc_sec_1"

    def test_detect_sections_no_headings(self) -> None:
        """Test detecting sections when no clear headings exist."""
        blocks = [
            DocumentBlock(
                block_id="1_0",
                page=1,
                text="Some content",
                block_type=BlockType.PARAGRAPH,
                confidence=1.0,
            ),
            DocumentBlock(
                block_id="1_1",
                page=1,
                text="More content",
                block_type=BlockType.PARAGRAPH,
                confidence=1.0,
            ),
        ]

        sections = _detect_sections("test_doc", blocks)
        assert len(sections) == 1
        assert sections[0].title is None
        assert sections[0].start_block_id == "1_0"
        assert sections[0].end_block_id == "1_1"
        assert sections[0].section_id == "test_doc_sec_0"

    def test_section_ids_unique(self) -> None:
        """Test that section IDs are unique."""
        blocks = [
            DocumentBlock(
                block_id="doc1_0",
                page=1,
                text="Section 1",
                block_type=BlockType.HEADING,
                confidence=1.0,
            ),
            DocumentBlock(
                block_id="doc1_1",
                page=1,
                text="Content",
                block_type=BlockType.PARAGRAPH,
                confidence=1.0,
            ),
            DocumentBlock(
                block_id="doc1_2",
                page=2,
                text="Section 2",
                block_type=BlockType.HEADING,
                confidence=1.0,
            ),
        ]

        sections = _detect_sections("doc1", blocks)
        section_ids = [s.section_id for s in sections]
        assert len(section_ids) == len(set(section_ids))


@pytest.mark.asyncio
async def test_stage_clean_full_pipeline() -> None:
    """Test full Stage 2 cleaning pipeline."""
    blocks = [
        DocumentBlock(
            block_id="1_0",
            page=1,
            text="  Company Header  ",
            block_type=BlockType.HEADING,
            confidence=1.0,
        ),
        DocumentBlock(
            block_id="1_1",
            page=1,
            text="Macro Outlook",
            block_type=BlockType.HEADING,
            confidence=1.0,
        ),
        DocumentBlock(
            block_id="1_2",
            page=1,
            text="Market conditions are favor-\nable.",
            block_type=BlockType.PARAGRAPH,
            confidence=1.0,
        ),
        DocumentBlock(
            block_id="2_0",
            page=2,
            text="Company Header",
            block_type=BlockType.HEADING,
            confidence=1.0,
        ),
        DocumentBlock(
            block_id="2_1",
            page=2,
            text="This document is for informational purposes.",
            block_type=BlockType.PARAGRAPH,
            confidence=1.0,
        ),
        DocumentBlock(
            block_id="3_0",
            page=3,
            text="Company Header",
            block_type=BlockType.HEADING,
            confidence=1.0,
        ),
        DocumentBlock(
            block_id="3_1",
            page=3,
            text="Equities",
            block_type=BlockType.HEADING,
            confidence=1.0,
        ),
    ]

    doc_json = DocumentJSON(
        document_id="test_doc",
        blob_id="blob_123",
        file_hash="hash_123",
        blocks=blocks,
        tables=[],
        page_count=3,
        extraction_coverage=0.95,
    )

    result = await stage_clean(doc_json)

    assert isinstance(result, CleanedDocument)
    assert result.document_id == "test_doc"
    assert len(result.blocks) > 0
    assert len(result.sections) > 0
    assert result.removed_boilerplate_count >= 0
    # Check that text was normalized
    for block in result.blocks:
        assert block.text == block.text.strip()
        assert "  " not in block.text


@pytest.mark.asyncio
async def test_stage_clean_disclaimer_detection() -> None:
    """Test disclaimer detection in Stage 2."""
    blocks = [
        DocumentBlock(
            block_id="1_0",
            page=1,
            text="This document is for informational purposes only.",
            block_type=BlockType.PARAGRAPH,
            confidence=1.0,
        ),
        DocumentBlock(
            block_id="1_1",
            page=1,
            text="Regular content",
            block_type=BlockType.PARAGRAPH,
            confidence=1.0,
        ),
    ]

    doc_json = DocumentJSON(
        document_id="test_doc",
        blob_id="blob_123",
        file_hash="hash_123",
        blocks=blocks,
        tables=[],
        page_count=1,
        extraction_coverage=1.0,
    )

    result = await stage_clean(doc_json)

    assert result.disclaimer_block_id is not None
    # Find the disclaimer block
    disclaimer_block = next(
        (b for b in result.blocks if b.block_id == result.disclaimer_block_id),
        None,
    )
    assert disclaimer_block is not None
    assert disclaimer_block.block_type == BlockType.DISCLAIMER


@pytest.mark.asyncio
async def test_stage_clean_empty_blocks() -> None:
    """Test Stage 2 with empty block list."""
    doc_json = DocumentJSON(
        document_id="test_doc",
        blob_id="blob_123",
        file_hash="hash_123",
        blocks=[],
        tables=[],
        page_count=1,
        extraction_coverage=0.0,
    )

    result = await stage_clean(doc_json)

    assert result.document_id == "test_doc"
    assert len(result.blocks) == 0
    assert len(result.sections) == 0
    assert result.removed_boilerplate_count == 0


@pytest.mark.asyncio
async def test_stage_clean_preserves_block_ids() -> None:
    """Test that Stage 2 preserves original block IDs."""
    blocks = [
        DocumentBlock(
            block_id="1_0",
            page=1,
            text="Content 1",
            block_type=BlockType.PARAGRAPH,
            confidence=1.0,
        ),
        DocumentBlock(
            block_id="1_1",
            page=1,
            text="Content 2",
            block_type=BlockType.PARAGRAPH,
            confidence=1.0,
        ),
    ]

    doc_json = DocumentJSON(
        document_id="test_doc",
        blob_id="blob_123",
        file_hash="hash_123",
        blocks=blocks,
        tables=[],
        page_count=1,
        extraction_coverage=1.0,
    )

    result = await stage_clean(doc_json)

    result_ids = [b.block_id for b in result.blocks]
    original_ids = [b.block_id for b in blocks]

    # All remaining blocks should have original IDs
    for block_id in result_ids:
        assert block_id in original_ids
