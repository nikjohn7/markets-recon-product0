"""PDF text and layout extraction using PyMuPDF.

This module provides functionality to extract structured text content from PDFs,
including block type detection, bounding box capture, and confidence scoring.
"""

import fitz  # PyMuPDF
from typing import List, Tuple

from src.models.document import DocumentBlock, ExtractedTable, DocumentJSON
from src.models.core import BoundingBox
from src.models.enums import BlockType
from src.exceptions import ExtractionError


class PDFParser:
    """PDF text and layout extraction using PyMuPDF."""
    
    def __init__(self):
        """Initialize the PDF parser."""
        self.heading_font_sizes = set()
        self.avg_font_size = 0.0
    
    def _normalize_bbox(self, bbox: fitz.Rect, page_width: float, page_height: float) -> BoundingBox:
        """Normalize bounding box coordinates to 0-1 range.
        
        Args:
            bbox: PyMuPDF rectangle
            page_width: Page width in points
            page_height: Page height in points
            
        Returns:
            Normalized BoundingBox
        """
        return BoundingBox(
            x0=bbox.x0 / page_width,
            y0=bbox.y0 / page_height,
            x1=bbox.x1 / page_width,
            y1=bbox.y1 / page_height
        )
    
    def _detect_block_type(self, block: dict, page_num: int, block_index: int) -> BlockType:
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
        lines = text.split('\n')
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
    
    def _compute_block_confidence(self, block: dict) -> float:
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
        special_char_ratio = sum(1 for c in text if not c.isalnum() and not c.isspace()) / max(len(text), 1)
        if special_char_ratio > 0.5:
            confidence -= 0.2
        
        # Boost confidence for well-structured text
        if len(text) > 20 and special_char_ratio < 0.3:
            confidence += 0.1
        
        # Ensure confidence stays in valid range
        return max(0.0, min(1.0, confidence))
    
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
    
    def parse_pdf(self, pdf_bytes: bytes, document_id: str, blob_id: str, file_hash: str) -> DocumentJSON:
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
            
            blocks: List[DocumentBlock] = []
            tables: List[ExtractedTable] = []
            pages_with_text = 0
            page_count = len(doc)
            
            # Process each page
            for page_num, page in enumerate(doc, 1):
                page_has_text = False
                
                # Get page dimensions
                page_width = page.rect.width
                page_height = page.rect.height
                
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
                    bbox = self._normalize_bbox(
                        fitz.Rect(block["bbox"]), page_width, page_height
                    )
                    
                    # Compute confidence
                    confidence = self._compute_block_confidence(block)
                    
                    # Create block ID
                    block_id = f"{page_num}_{block_index}"
                    
                    # Create DocumentBlock
                    document_block = DocumentBlock(
                        block_id=block_id,
                        page=page_num,
                        text=block_text,
                        block_type=block_type,
                        bbox=bbox,
                        confidence=confidence
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
                tables=tables,  # Empty for now - table extraction will be added later
                page_count=page_count,
                extraction_coverage=extraction_coverage,
                ocr_pages=[],  # Empty for now - OCR will be added later
                vision_pages=[]  # Empty for now - vision will be added later
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
    parser = PDFParser()
    return parser.parse_pdf(pdf_bytes, document_id, blob_id, file_hash)