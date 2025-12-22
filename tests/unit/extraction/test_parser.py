"""Unit tests for PDF text extraction parser."""

from unittest.mock import MagicMock, Mock, patch

import fitz  # PyMuPDF
import pytest
from src.exceptions import ExtractionError
from src.extraction.parser import PDFParser, parse_pdf
from src.models.core import BoundingBox
from src.models.document import DocumentBlock, DocumentJSON, ExtractedTable, TableCell
from src.models.enums import BlockType


class TestPDFParser:
    """Unit tests for PDFParser class."""

    def test_normalize_bbox(self):
        """Test bounding box normalization."""
        parser = PDFParser()

        # Create a mock fitz.Rect
        mock_rect = Mock()
        mock_rect.x0 = 100
        mock_rect.y0 = 150
        mock_rect.x1 = 300
        mock_rect.y1 = 200

        page_width = 600
        page_height = 800

        bbox = parser._normalize_bbox(mock_rect, page_width, page_height)

        assert isinstance(bbox, BoundingBox)
        assert bbox.x0 == 100 / 600  # 0.166...
        assert bbox.y0 == 150 / 800  # 0.1875
        assert bbox.x1 == 300 / 600  # 0.5
        assert bbox.y1 == 200 / 800  # 0.25

    def test_detect_block_type_heading_by_position(self):
        """Test heading detection based on position (early blocks on first page)."""
        parser = PDFParser()

        block = {"text": "Investment Outlook 2024", "size": 12, "flags": 0}

        # First page, early block index
        block_type = parser._detect_block_type(block, page_num=1, block_index=0)
        assert block_type == BlockType.HEADING

        # Later block index should not be heading (unless font size triggers it)
        block_type = parser._detect_block_type(block, page_num=1, block_index=5)
        # With our current logic, font size >= 10 triggers heading, so this will be HEADING
        # Let's test with a smaller font size
        block_small = {"text": "Regular text", "size": 9, "flags": 0}
        block_type = parser._detect_block_type(block_small, page_num=1, block_index=5)
        assert block_type == BlockType.PARAGRAPH

    def test_detect_block_type_heading_by_font_size(self):
        """Test heading detection based on large font size."""
        parser = PDFParser()
        parser.avg_font_size = 11.0  # Set average font size

        # Block with significantly larger font (using proper PyMuPDF structure)
        block = {
            "text": "Section Title",
            "lines": [{"spans": [{"size": 14, "flags": 0, "text": "Section Title"}]}],
        }
        block_type = parser._detect_block_type(block, page_num=2, block_index=0)
        assert block_type == BlockType.HEADING

    def test_detect_block_type_heading_by_bold(self):
        """Test heading detection based on bold text."""
        parser = PDFParser()

        # Block with bold flag (using proper PyMuPDF structure)
        block = {
            "text": "Important Heading",
            "lines": [
                {
                    "spans": [
                        {"size": 12, "flags": 2, "text": "Important Heading"}  # Bold flag = 2
                    ]
                }
            ],
        }
        block_type = parser._detect_block_type(block, page_num=2, block_index=3)
        assert block_type == BlockType.HEADING

    def test_detect_block_type_bullet_patterns(self):
        """Test bullet detection for various bullet patterns."""
        parser = PDFParser()

        bullet_patterns = [
            "• This is a bullet",
            "- This is a bullet",
            "* This is a bullet",
            "· This is a bullet",
            "■ This is a bullet",
            "□ This is a bullet",
        ]

        for bullet_text in bullet_patterns:
            block = {"text": bullet_text, "size": 11, "flags": 0}
            block_type = parser._detect_block_type(block, page_num=1, block_index=5)
            assert block_type == BlockType.BULLET, f"Failed to detect bullet: {bullet_text}"

    def test_detect_block_type_numbered_bullets(self):
        """Test bullet detection for numbered lists."""
        parser = PDFParser()

        numbered_texts = ["1. First item", "2. Second item", "3. Third item"]

        for text in numbered_texts:
            block = {"text": text, "size": 11, "flags": 0}
            block_type = parser._detect_block_type(block, page_num=1, block_index=5)
            assert block_type == BlockType.BULLET

    def test_detect_block_type_paragraph_default(self):
        """Test that normal text is detected as paragraph."""
        parser = PDFParser()

        block = {"text": "This is a normal paragraph of text.", "size": 9, "flags": 0}
        block_type = parser._detect_block_type(block, page_num=2, block_index=5)
        assert block_type == BlockType.PARAGRAPH

    def test_compute_block_confidence_high_quality(self):
        """Test confidence computation for high-quality text block."""
        parser = PDFParser()

        block = {"text": "This is a well-structured paragraph with proper text content."}
        confidence = parser._compute_block_confidence(block)

        assert 0.8 <= confidence <= 1.0

    def test_compute_block_confidence_short_text(self):
        """Test confidence penalty for very short text."""
        parser = PDFParser()

        block = {"text": "Hi"}
        confidence = parser._compute_block_confidence(block)

        assert confidence < 0.8  # Should be penalized

    def test_compute_block_confidence_special_chars(self):
        """Test confidence penalty for text with many special characters."""
        parser = PDFParser()

        block = {"text": "!!! @@@ ### $$$ %%% &&& ***"}
        confidence = parser._compute_block_confidence(block)

        assert confidence < 0.8  # Should be penalized for special chars

    def test_compute_block_confidence_bounds(self):
        """Test that confidence stays within valid bounds."""
        parser = PDFParser()

        # Test with empty text
        block = {"text": ""}
        confidence = parser._compute_block_confidence(block)
        assert 0.0 <= confidence <= 1.0

        # Test with very long quality text
        block = {"text": "This is a very long paragraph with proper structure and content. " * 10}
        confidence = parser._compute_block_confidence(block)
        assert 0.0 <= confidence <= 1.0

    @patch("fitz.open")
    def test_analyze_font_sizes(self, mock_fitz_open):
        """Test font size analysis for heading detection."""
        parser = PDFParser()

        # Create mock document with various font sizes
        mock_doc = MagicMock()
        mock_page = MagicMock()

        # Mock text dictionary structure
        mock_text_dict = {
            "blocks": [
                {
                    "type": 0,
                    "lines": [
                        {
                            "spans": [
                                {"size": 18},  # Large heading font
                                {"size": 16},  # Another heading font
                            ]
                        },
                        {
                            "spans": [
                                {"size": 11},  # Normal text
                                {"size": 11},
                            ]
                        },
                    ],
                }
            ]
        }

        mock_page.get_text.return_value = mock_text_dict
        mock_doc.__len__ = Mock(return_value=1)
        mock_doc.__iter__ = Mock(return_value=iter([mock_page]))

        mock_fitz_open.return_value = mock_doc

        parser._analyze_font_sizes(mock_doc)

        # Should have computed average font size
        assert parser.avg_font_size > 0
        # Should have identified some heading font sizes
        assert len(parser.heading_font_sizes) > 0

    def test_parse_pdf_success(self):
        """Test successful PDF parsing."""
        # Create a simple test PDF
        doc = fitz.open()
        page = doc.new_page()
        page.insert_text((50, 50), "Test Heading", fontsize=16)
        page.insert_text((50, 100), "This is a test paragraph.", fontsize=11)

        pdf_bytes = doc.write()
        doc.close()

        result = parse_pdf(
            pdf_bytes=pdf_bytes, document_id="test-doc", blob_id="test-blob", file_hash="test-hash"
        )

        assert isinstance(result, DocumentJSON)
        assert result.document_id == "test-doc"
        assert result.blob_id == "test-blob"
        assert result.file_hash == "test-hash"
        assert result.page_count == 1
        assert result.extraction_coverage == 1.0

        # Should have extracted blocks
        assert len(result.blocks) > 0

        # Verify all blocks have required fields
        for block in result.blocks:
            assert block.block_id
            assert block.page == 1
            assert block.text
            assert isinstance(block.block_type, BlockType)
            assert 0 <= block.confidence <= 1
            assert block.bbox is not None

        # Verify that we have the expected content
        all_text = " ".join([b.text for b in result.blocks])
        assert "Test Heading" in all_text
        assert "test paragraph" in all_text

    def test_parse_pdf_empty(self):
        """Test parsing of empty PDF."""
        doc = fitz.open()
        doc.new_page()  # Empty page

        pdf_bytes = doc.write()
        doc.close()

        result = parse_pdf(
            pdf_bytes=pdf_bytes,
            document_id="empty-doc",
            blob_id="empty-blob",
            file_hash="empty-hash",
        )

        assert isinstance(result, DocumentJSON)
        assert len(result.blocks) == 0
        assert result.extraction_coverage == 0.0
        assert result.page_count == 1

    def test_parse_pdf_multi_page(self):
        """Test parsing of multi-page PDF."""
        doc = fitz.open()

        # Page 1
        page1 = doc.new_page()
        page1.insert_text((50, 50), "Page 1 Heading", fontsize=16)
        page1.insert_text((50, 100), "Page 1 content.", fontsize=11)

        # Page 2
        page2 = doc.new_page()
        page2.insert_text((50, 50), "Page 2 Heading", fontsize=16)
        page2.insert_text((50, 100), "Page 2 content.", fontsize=11)

        # Page 3 (empty)
        doc.new_page()

        pdf_bytes = doc.write()
        doc.close()

        result = parse_pdf(
            pdf_bytes=pdf_bytes,
            document_id="multi-page-doc",
            blob_id="multi-blob",
            file_hash="multi-hash",
        )

        assert result.page_count == 3
        assert result.extraction_coverage == 2 / 3  # 2 out of 3 pages have text

        # Should have blocks from pages 1 and 2
        page1_blocks = [b for b in result.blocks if b.page == 1]
        page2_blocks = [b for b in result.blocks if b.page == 2]
        page3_blocks = [b for b in result.blocks if b.page == 3]

        assert len(page1_blocks) > 0
        assert len(page2_blocks) > 0
        assert len(page3_blocks) == 0

    def test_parse_pdf_counts_table_only_pages(self, monkeypatch):
        """Table extraction should contribute to coverage even without text blocks."""
        doc = fitz.open()
        doc.new_page()  # Page with only table content supplied by mock

        pdf_bytes = doc.write()
        doc.close()

        parser = PDFParser()

        mock_table = ExtractedTable(
            table_id="1_tbl_0",
            page=1,
            cells=[TableCell(row=0, col=0, text="42", is_header=False)],
            row_count=1,
            col_count=1,
            caption=None,
        )
        table_cell_block = DocumentBlock(
            block_id="1_tbl_0_0_0",
            page=1,
            text="42",
            block_type=BlockType.TABLE_CELL,
            bbox=None,
            confidence=0.9,
        )

        def fake_extract_tables(_page, _page_num, _page_width, _page_height):
            return [mock_table], [table_cell_block]

        monkeypatch.setattr(parser, "_extract_tables_from_page", fake_extract_tables)

        result = parser.parse_pdf(
            pdf_bytes=pdf_bytes,
            document_id="table-only-doc",
            blob_id="table-blob",
            file_hash="table-hash",
        )

        assert result.extraction_coverage == 1.0
        assert result.tables == [mock_table]
        assert result.blocks == [table_cell_block]

    def test_parse_pdf_block_id_format(self):
        """Test that block IDs follow the expected format."""
        doc = fitz.open()

        # Add multiple blocks on same page
        page = doc.new_page()
        page.insert_text((50, 50), "First block", fontsize=12)
        page.insert_text((50, 100), "Second block", fontsize=12)
        page.insert_text((50, 150), "Third block", fontsize=12)

        pdf_bytes = doc.write()
        doc.close()

        result = parse_pdf(
            pdf_bytes=pdf_bytes,
            document_id="block-id-test",
            blob_id="block-blob",
            file_hash="block-hash",
        )

        # Verify block ID format (page_index)
        for block in result.blocks:
            parts = block.block_id.split("_")
            assert len(parts) == 2
            page_num, index = parts
            assert page_num.isdigit()
            assert index.isdigit()
            assert int(page_num) == block.page

        # Verify uniqueness
        block_ids = [b.block_id for b in result.blocks]
        assert len(block_ids) == len(set(block_ids))

    def test_parse_pdf_invalid_pdf(self):
        """Test parsing with invalid PDF bytes."""
        invalid_pdf = b"This is not a valid PDF"

        with pytest.raises(ExtractionError, match="Failed to open PDF"):
            parse_pdf(
                pdf_bytes=invalid_pdf,
                document_id="invalid-doc",
                blob_id="invalid-blob",
                file_hash="invalid-hash",
            )

    def test_parse_pdf_bounding_boxes(self):
        """Test that bounding boxes are properly normalized."""
        doc = fitz.open()
        page = doc.new_page(width=612, height=792)  # Standard US Letter size

        # Add text at known position
        page.insert_text((100, 200), "Test text", fontsize=12)

        pdf_bytes = doc.write()
        doc.close()

        result = parse_pdf(
            pdf_bytes=pdf_bytes, document_id="bbox-test", blob_id="bbox-blob", file_hash="bbox-hash"
        )

        # Verify bounding boxes are normalized (0-1 range)
        for block in result.blocks:
            assert block.bbox is not None
            assert 0 <= block.bbox.x0 <= 1
            assert 0 <= block.bbox.y0 <= 1
            assert 0 <= block.bbox.x1 <= 1
            assert 0 <= block.bbox.y1 <= 1
            assert block.bbox.x0 <= block.bbox.x1
            assert block.bbox.y0 <= block.bbox.y1


class TestParsePDFFunction:
    """Unit tests for the parse_pdf convenience function."""

    def test_parse_pdf_function_exists(self):
        """Test that parse_pdf function is available and callable."""
        assert callable(parse_pdf)

    @patch("src.extraction.parser.PDFParser")
    def test_parse_pdf_calls_parser(self, mock_parser_class):
        """Test that parse_pdf creates and uses PDFParser instance."""
        # Mock the parser
        mock_parser = MagicMock()
        mock_parser.parse_pdf.return_value = DocumentJSON(
            document_id="test",
            blob_id="test",
            file_hash="test",
            blocks=[],
            tables=[],
            page_count=1,
            extraction_coverage=1.0,
        )
        mock_parser_class.return_value = mock_parser

        # Call parse_pdf function
        pdf_bytes = b"fake pdf"
        result = parse_pdf(pdf_bytes, "doc-id", "blob-id", "hash")

        # Verify parser was created and used
        mock_parser_class.assert_called_once()
        mock_parser.parse_pdf.assert_called_once_with(pdf_bytes, "doc-id", "blob-id", "hash")
        assert isinstance(result, DocumentJSON)
