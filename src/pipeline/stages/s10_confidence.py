"""Stage 10: Confidence scoring and review routing.

Computes extraction quality, evidence strength, and document-level confidence.
"""

import re
from src.models.document import DocumentJSON
from src.models.enums import BlockType, ConfidenceBand, CallDirection


# Explicit call language patterns per CONFIDENCE.md
EXPLICIT_CALL_PATTERNS: dict[CallDirection, list[str]] = {
    CallDirection.OVERWEIGHT: [
        r"\boverweight\b",
        r"\bprefer\b",
        r"\bfavor\b",
        r"\bconstructive\b",
        r"\bbullish\b",
        r"\bincrease (allocation|exposure)\b",
    ],
    CallDirection.UNDERWEIGHT: [
        r"\bunderweight\b",
        r"\bavoid\b",
        r"\bcautious\b",
        r"\bbearish\b",
        r"\breduce (allocation|exposure)\b",
    ],
    CallDirection.NEUTRAL: [
        r"\bneutral\b",
        r"\bbenchmark weight\b",
        r"\bhold\b",
    ],
    CallDirection.UNCERTAIN: [],
}


def score_text_coverage(doc: DocumentJSON) -> float:
    """Score text extraction coverage (40% weight)."""
    return doc.extraction_coverage


def score_ocr_quality(doc: DocumentJSON) -> float:
    """Score OCR quality if OCR was used (20% weight).
    
    Returns 1.0 if no OCR was needed.
    Estimates quality by checking for garbled character patterns.
    """
    if not doc.ocr_pages:
        return 1.0  # Full credit if no OCR needed
    
    # Get text from OCR pages
    ocr_text = ""
    for block in doc.blocks:
        if block.page in doc.ocr_pages:
            ocr_text += block.text + " "
    
    if not ocr_text.strip():
        return 0.0
    
    # Count garbled characters (non-printable, excessive special chars)
    garbled = sum(1 for c in ocr_text if not c.isprintable() or c in "□■▪▫●○◆◇")
    total = len(ocr_text)
    
    return max(0.0, 1.0 - (garbled / total)) if total > 0 else 0.0


def score_table_success(doc: DocumentJSON) -> float:
    """Score table extraction success (20% weight).
    
    Returns 1.0 if no tables detected or all tables have content.
    """
    if not doc.tables:
        return 1.0  # Full credit if no tables to extract
    
    tables_with_content = sum(1 for t in doc.tables if t.cells)
    return tables_with_content / len(doc.tables)


def score_structure_quality(doc: DocumentJSON) -> float:
    """Score block structure quality (20% weight).
    
    Measures heading/section detection success.
    """
    if not doc.blocks:
        return 0.0
    
    # Check for heading detection
    headings = [b for b in doc.blocks if b.block_type == BlockType.HEADING]
    paragraphs = [b for b in doc.blocks if b.block_type == BlockType.PARAGRAPH]
    bullets = [b for b in doc.blocks if b.block_type == BlockType.BULLET]
    
    # Good structure: has headings, paragraphs, and varied block types
    score = 0.0
    
    # Has headings (expected in structured docs)
    if headings:
        score += 0.4
    
    # Has paragraphs (main content)
    if paragraphs:
        score += 0.3
    
    # Has varied block types (not all same type)
    block_types = {b.block_type for b in doc.blocks}
    if len(block_types) >= 3:
        score += 0.3
    elif len(block_types) >= 2:
        score += 0.15
    
    return score


def score_extraction_quality(doc: DocumentJSON) -> float:
    """Compute overall extraction quality score (0-1).
    
    Weights per CONFIDENCE.md:
    - Text coverage: 40%
    - OCR quality: 20%
    - Table success: 20%
    - Structure quality: 20%
    """
    coverage = score_text_coverage(doc) * 0.4
    ocr = score_ocr_quality(doc) * 0.2
    tables = score_table_success(doc) * 0.2
    structure = score_structure_quality(doc) * 0.2
    
    return coverage + ocr + tables + structure


def has_explicit_call_language(call: CallDirection, evidence_text: str) -> float:
    """Check if evidence contains explicit call language.
    
    Returns 1.0 if explicit pattern found, 0.0 otherwise.
    UNCERTAIN calls always return 0.0.
    """
    if call == CallDirection.UNCERTAIN:
        return 0.0
    
    patterns = EXPLICIT_CALL_PATTERNS.get(call, [])
    text_lower = evidence_text.lower()
    
    for pattern in patterns:
        if re.search(pattern, text_lower):
            return 1.0
    
    return 0.0


def compute_confidence_band(confidence: float) -> ConfidenceBand:
    """Compute confidence band from score."""
    if confidence >= 0.80:
        return ConfidenceBand.HIGH
    elif confidence >= 0.60:
        return ConfidenceBand.MEDIUM
    return ConfidenceBand.LOW
