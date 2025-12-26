"""PDF text and layout extraction using PyMuPDF and pdfplumber.

This module provides functionality to extract structured text content from PDFs,
including block type detection, bounding box capture, table extraction, and confidence scoring.
"""

import io
import logging
from typing import Any

import fitz  # PyMuPDF
import pdfplumber

from src.exceptions import ExtractionError
from src.models.core import BoundingBox
from src.models.document import DocumentBlock, DocumentJSON, ExtractedTable, TableCell
from src.models.enums import BlockType

logger = logging.getLogger(__name__)


class PDFParser:
    """PDF text and layout extraction using PyMuPDF."""

    def __init__(self) -> None:
        """Initialize the PDF parser."""
        self.heading_font_sizes: set[float] = set()
        self.avg_font_size = 0.0

    def _normalize_bbox(
        self, bbox: fitz.Rect, page_width: float, page_height: float
    ) -> BoundingBox:
        """Normalize bounding box coordinates to 0-1 range.

        Args:
            bbox: PyMuPDF rectangle
            page_width: Page width in points
            page_height: Page height in points

        Returns:
            Normalized BoundingBox
        """

        def clamp(value: float) -> float:
            return max(0.0, min(1.0, value))

        return BoundingBox(
            x0=clamp(bbox.x0 / page_width),
            y0=clamp(bbox.y0 / page_height),
            x1=clamp(bbox.x1 / page_width),
            y1=clamp(bbox.y1 / page_height),
        )

    def _detect_block_type(
        self, block: dict[str, Any], page_num: int, block_index: int
    ) -> BlockType:
        """Detect block type based on text characteristics.

        Args:
            block: PyMuPDF block dictionary
            page_num: Page number (1-indexed)
            block_index: Block index on page

        Returns:
            Detected BlockType
        """
        text = block.get("text", "").strip()
        if not text:
            return BlockType.PARAGRAPH

        # Check for bullet patterns
        bullet_patterns = ["•", "-", "*", "·", "■", "□"]
        if any(text.startswith(pattern) for pattern in bullet_patterns):
            return BlockType.BULLET

        # Check for numbered patterns (1., 2., a), b), etc.)
        lines = text.split("\n")
        if lines and any(lines[0].startswith(f"{i}.") for i in range(1, 10)):
            return BlockType.BULLET

        # Extract font information from spans
        font_size = 0
        flags = 0

        # Try to get font info from the first span in the first line
        lines = block.get("lines", [])
        if lines:
            first_line = lines[0]
            spans = first_line.get("spans", [])
            if spans:
                first_span = spans[0]
                font_size = first_span.get("size", 0)
                flags = first_span.get("flags", 0)

        # If we didn't get font info from spans, try block level as fallback
        if font_size == 0:
            font_size = block.get("size", 0)
        if flags == 0:
            flags = block.get("flags", 0)

        # Check for heading characteristics
        # Headings are typically: larger font, bold, or appears at top of page

        # Check for bold text (common in headings)
        if flags & 2:  # Bold flag
            return BlockType.HEADING

        # Check if font size is significantly larger than average
        if self.avg_font_size > 0 and font_size > self.avg_font_size * 1.2:
            return BlockType.HEADING

        # For the first few blocks on the first page, treat as headings
        # This is a simple heuristic that works for typical documents
        if block_index < 3 and page_num == 1:
            return BlockType.HEADING

        # Absolute font size threshold for headings (14pt and above)
        if font_size >= 14:
            return BlockType.HEADING

        return BlockType.PARAGRAPH

    def _compute_block_confidence(self, block: dict[str, Any]) -> float:
        """Compute confidence score for a block based on extraction quality.

        Args:
            block: PyMuPDF block dictionary

        Returns:
            Confidence score between 0 and 1
        """
        # Start with base confidence
        confidence = 0.8

        # Penalize very short text (might be noise)
        text = block.get("text", "").strip()
        if len(text) < 5:
            confidence -= 0.3

        # Penalize blocks with many special characters (might be garbled)
        special_char_ratio = sum(1 for c in text if not c.isalnum() and not c.isspace()) / max(
            len(text), 1
        )
        if special_char_ratio > 0.5:
            confidence -= 0.2

        # Boost confidence for well-structured text
        if len(text) > 20 and special_char_ratio < 0.3:
            confidence += 0.1

        # Ensure confidence stays in valid range
        return max(0.0, min(1.0, confidence))

    def _extract_tables_from_page(
        self, page: fitz.Page, page_num: int, page_width: float, page_height: float
    ) -> tuple[list[ExtractedTable], list[DocumentBlock]]:
        """Extract tables from a page using pdfplumber.

        Args:
            page: PyMuPDF page object
            page_num: Page number (1-indexed)
            page_width: Page width in points
            page_height: Page height in points

        Returns:
            Tuple of (ExtractedTable list, TABLE_CELL blocks list)
        """
        tables: list[ExtractedTable] = []
        table_cell_blocks: list[DocumentBlock] = []

        try:
            # Save page as temporary PDF for pdfplumber
            temp_doc = fitz.open()
            temp_doc.insert_pdf(page.parent, from_page=page.number, to_page=page.number)
            pdf_bytes = temp_doc.write()
            temp_doc.close()

            # Use pdfplumber to extract tables from the page
            with pdfplumber.open(io.BytesIO(pdf_bytes)) as pdf:
                if len(pdf.pages) > 0:
                    plumber_page = pdf.pages[0]

                    # Extract tables
                    extracted_tables = plumber_page.extract_tables()

                    for table_index, table_data in enumerate(extracted_tables):
                        if not table_data or len(table_data) == 0:
                            continue

                        # Create table ID
                        table_id = f"{page_num}_tbl_{table_index}"

                        # Extract cells and create TABLE_CELL blocks
                        cells: list[TableCell] = []
                        block_index = 0

                        for row_idx, row in enumerate(table_data):
                            for col_idx, cell_text in enumerate(row):
                                if cell_text is None:
                                    cell_text = ""

                                # Clean up cell text
                                cell_text = str(cell_text).strip()

                                # Determine if this is a header cell
                                # Heuristic: first row is header, or check for bold/larger font
                                is_header = row_idx == 0

                                # Create TableCell
                                table_cell = TableCell(
                                    row=row_idx, col=col_idx, text=cell_text, is_header=is_header
                                )
                                cells.append(table_cell)

                                # Create TABLE_CELL block for searchable text
                                if cell_text:  # Only create block for non-empty cells
                                    # Estimate bounding box (pdfplumber doesn't provide exact positions)
                                    # Use relative positioning based on row/column
                                    cell_bbox = self._estimate_cell_bbox(
                                        row_idx,
                                        col_idx,
                                        len(table_data),
                                        len(row),
                                        page_width,
                                        page_height,
                                    )

                                    block_id = f"{page_num}_{table_index}_{row_idx}_{col_idx}"
                                    table_cell_block = DocumentBlock(
                                        block_id=block_id,
                                        page=page_num,
                                        text=cell_text,
                                        block_type=BlockType.TABLE_CELL,
                                        bbox=cell_bbox,
                                        confidence=0.9,  # High confidence for table cells
                                    )
                                    table_cell_blocks.append(table_cell_block)
                                    block_index += 1

                        # Determine table dimensions
                        row_count = len(table_data)
                        col_count = max(len(row) for row in table_data) if table_data else 0

                        # Create ExtractedTable
                        extracted_table = ExtractedTable(
                            table_id=table_id,
                            page=page_num,
                            cells=cells,
                            row_count=row_count,
                            col_count=col_count,
                            caption=None,  # Could be extracted from surrounding text
                        )
                        tables.append(extracted_table)

        except Exception as e:
            # Log error but continue - table extraction is best-effort
            logger.warning(f"Table extraction failed for page {page_num}: {e}")

        return tables, table_cell_blocks

    def _estimate_cell_bbox(
        self,
        row_idx: int,
        col_idx: int,
        total_rows: int,
        total_cols: int,
        page_width: float,
        page_height: float,
    ) -> BoundingBox:
        """Estimate bounding box for a table cell based on grid position.

        This is a fallback when exact cell positions aren't available.

        Args:
            row_idx: Row index (0-indexed)
            col_idx: Column index (0-indexed)
            total_rows: Total number of rows
            total_cols: Total number of columns
            page_width: Page width in points
            page_height: Page height in points

        Returns:
            Estimated BoundingBox for the cell
        """
        # Estimate table occupies 80% of page width and 60% of page height
        # centered on the page
        table_width = page_width * 0.8
        table_height = page_height * 0.6
        table_x0 = page_width * 0.1
        table_y0 = page_height * 0.2

        # Calculate cell dimensions
        cell_width = table_width / total_cols if total_cols > 0 else table_width
        cell_height = table_height / total_rows if total_rows > 0 else table_height

        # Calculate cell position
        cell_x0 = table_x0 + (col_idx * cell_width)
        cell_y0 = table_y0 + (row_idx * cell_height)
        cell_x1 = cell_x0 + cell_width
        cell_y1 = cell_y0 + cell_height

        # Normalize to 0-1 range
        return BoundingBox(
            x0=cell_x0 / page_width,
            y0=cell_y0 / page_height,
            x1=cell_x1 / page_width,
            y1=cell_y1 / page_height,
        )

    def _analyze_font_sizes(self, doc: fitz.Document) -> None:
        """Analyze font sizes across the document to detect headings.

        Args:
            doc: PyMuPDF document
        """
        font_sizes = []

        for page in doc:
            blocks = page.get_text("dict", flags=fitz.TEXTFLAGS_TEXT)["blocks"]
            for block in blocks:
                if block.get("type") == 0:  # Text block
                    for line in block.get("lines", []):
                        for span in line.get("spans", []):
                            size = span.get("size", 0)
                            if size > 0:
                                font_sizes.append(size)

        if font_sizes:
            self.avg_font_size = sum(font_sizes) / len(font_sizes)
            # Consider top 10% of font sizes as potential headings
            font_sizes_sorted = sorted(font_sizes, reverse=True)
            heading_count = max(1, len(font_sizes_sorted) // 10)
            self.heading_font_sizes = set(font_sizes_sorted[:heading_count])

    def parse_pdf(
        self, pdf_bytes: bytes, document_id: str, blob_id: str, file_hash: str
    ) -> DocumentJSON:
        """Parse PDF and extract text with layout preservation.

        Args:
            pdf_bytes: PDF content as bytes
            document_id: Unique document identifier
            blob_id: Blob storage identifier
            file_hash: SHA-256 hash of PDF content

        Returns:
            DocumentJSON with extracted content

        Raises:
            ExtractionError: If PDF parsing fails
        """
        try:
            # Open PDF from bytes
            doc = fitz.open(stream=pdf_bytes, filetype="pdf")
        except Exception as e:
            raise ExtractionError(f"Failed to open PDF: {e}") from e

        try:
            # Analyze font sizes for heading detection
            self._analyze_font_sizes(doc)

            blocks: list[DocumentBlock] = []
            tables: list[ExtractedTable] = []
            pages_with_text = 0
            page_count = len(doc)

            # Process each page
            for page_num, page in enumerate(doc, 1):
                # Tracks whether the page yielded any extracted content (text or tables)
                page_has_text = False

                # Get page dimensions
                page_width = page.rect.width
                page_height = page.rect.height

                # Extract tables first (before text blocks to avoid duplication)
                page_tables, table_cell_blocks = self._extract_tables_from_page(
                    page, page_num, page_width, page_height
                )
                tables.extend(page_tables)
                blocks.extend(table_cell_blocks)
                if page_tables or table_cell_blocks:
                    page_has_text = True

                # Extract text blocks
                text_dict = page.get_text("dict", flags=fitz.TEXTFLAGS_TEXT)

                block_index = 0
                for block in text_dict["blocks"]:
                    if block.get("type") != 0:  # Skip non-text blocks
                        continue

                    # Extract text from block
                    block_text = ""
                    for line in block.get("lines", []):
                        for span in line.get("spans", []):
                            block_text += span.get("text", "") + " "

                    block_text = block_text.strip()
                    if not block_text:  # Skip empty blocks
                        continue

                    page_has_text = True

                    # Detect block type
                    block_type = self._detect_block_type(block, page_num, block_index)

                    # Get bounding box
                    bbox = self._normalize_bbox(fitz.Rect(block["bbox"]), page_width, page_height)

                    # Compute confidence
                    confidence = self._compute_block_confidence(block)

                    # Create block ID (start after table cell blocks)
                    block_id = f"{page_num}_{block_index}"

                    # Create DocumentBlock
                    document_block = DocumentBlock(
                        block_id=block_id,
                        page=page_num,
                        text=block_text,
                        block_type=block_type,
                        bbox=bbox,
                        confidence=confidence,
                    )
                    blocks.append(document_block)
                    block_index += 1

                # Count pages with text
                if page_has_text:
                    pages_with_text += 1

            # Compute extraction coverage
            extraction_coverage = pages_with_text / page_count if page_count > 0 else 0.0

            # Create DocumentJSON
            document_json = DocumentJSON(
                document_id=document_id,
                blob_id=blob_id,
                file_hash=file_hash,
                blocks=blocks,
                tables=tables,
                page_count=page_count,
                extraction_coverage=extraction_coverage,
                ocr_pages=[],  # Empty for now - OCR will be added later
                vision_pages=[],  # Empty for now - vision will be added later
            )

            return document_json

        finally:
            doc.close()


def parse_pdf(pdf_bytes: bytes, document_id: str, blob_id: str, file_hash: str) -> DocumentJSON:
    """Convenience function to parse PDF using the PDFParser class.

    Args:
        pdf_bytes: PDF content as bytes
        document_id: Unique document identifier
        blob_id: Blob storage identifier
        file_hash: SHA-256 hash of PDF content

    Returns:
        DocumentJSON with extracted content

    Raises:
        ExtractionError: If PDF parsing fails
    """
    parser: PDFParser = PDFParser()
    return parser.parse_pdf(pdf_bytes, document_id, blob_id, file_hash)
