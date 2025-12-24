"""Stage 10: Confidence scoring and review routing.

Computes extraction quality, evidence strength, and document-level confidence.
"""

import re
import statistics
from typing import Any

from src.models.calls import AllocationCall
from src.models.confidence import ConfidenceResult, FieldConfidence
from src.models.core import Citation
from src.models.document import DocumentJSON
from src.models.enums import BlockType, ConfidenceBand, CallDirection
from src.models.pipeline import RetrievedChunk
from src.models.profile import DocumentProfile
from src.models.summaries import DocumentSummaries


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


# --- Evidence Strength Scoring (Task 7.2) ---


def _get_chunk_by_id(
    chunk_id: str, chunks: list[RetrievedChunk]
) -> RetrievedChunk | None:
    """Find chunk by ID."""
    for chunk in chunks:
        if chunk.chunk_id == chunk_id:
            return chunk
    return None


def has_explicit_mention(field_value: Any, text: str) -> float:
    """Check if field value is explicitly mentioned in text.
    
    Returns 1.0 if found, 0.0 otherwise.
    """
    if field_value is None:
        return 0.0
    
    value_str = str(field_value).lower()
    text_lower = text.lower()
    
    # Direct substring match
    if value_str in text_lower:
        return 1.0
    
    # For multi-word values, check if all significant words present
    words = [w for w in value_str.split() if len(w) > 2]
    if words and all(w in text_lower for w in words):
        return 0.8
    
    return 0.0


def compute_word_overlap(value: str, text: str) -> float:
    """Compute word overlap as proxy for semantic similarity.
    
    Returns score 0-1 based on shared words.
    """
    value_words = set(w.lower() for w in re.findall(r'\b\w+\b', value) if len(w) > 2)
    text_words = set(w.lower() for w in re.findall(r'\b\w+\b', text) if len(w) > 2)
    
    if not value_words:
        return 0.0
    
    overlap = len(value_words & text_words)
    return min(1.0, overlap / len(value_words))


def compute_entailment_heuristic(value: str, text: str) -> float:
    """Heuristic entailment score based on contextual indicators.
    
    Checks for supporting language patterns around the value.
    """
    text_lower = text.lower()
    value_lower = value.lower()
    
    # Check if value appears with supporting context
    support_patterns = [
        rf"(we|our|the)\s+\w*\s*{re.escape(value_lower[:20])}",
        rf"{re.escape(value_lower[:20])}\s+(is|are|will|should)",
        rf"(expect|believe|view|see)\s+.*{re.escape(value_lower[:20])}",
    ]
    
    for pattern in support_patterns:
        if re.search(pattern, text_lower):
            return 1.0
    
    # Partial credit if value words appear in assertive sentences
    if any(w in text_lower for w in value_lower.split()[:3]):
        return 0.5
    
    return 0.0


def score_evidence_strength(
    field_value: Any,
    citations: list[Citation],
    source_chunks: list[RetrievedChunk],
) -> float:
    """Score how well evidence supports a claim.
    
    Weights per CONFIDENCE.md:
    - Explicit mention: 50%
    - Semantic similarity: 30%
    - Entailment: 20%
    
    Returns best score across all citations.
    """
    if not citations:
        return 0.0
    
    best_score = 0.0
    value_str = str(field_value) if field_value is not None else ""
    
    for citation in citations:
        chunk = _get_chunk_by_id(citation.chunk_id, source_chunks)
        if not chunk:
            continue
        
        text = chunk.text
        
        # Explicit mention (50% weight)
        explicit = has_explicit_mention(field_value, text) * 0.5
        
        # Semantic similarity via word overlap (30% weight)
        similarity = compute_word_overlap(value_str, text) * 0.3
        
        # Entailment heuristic (20% weight)
        entailment = compute_entailment_heuristic(value_str, text) * 0.2
        
        score = explicit + similarity + entailment
        best_score = max(best_score, score)
    
    return best_score


def score_call_evidence(
    call_direction: CallDirection,
    citations: list[Citation],
    source_chunks: list[RetrievedChunk],
) -> float:
    """Score evidence strength for an allocation call.
    
    Combines explicit call language detection with general evidence scoring.
    
    Weights:
    - Evidence strength: 50%
    - Explicit call language: 50%
    """
    if not citations:
        return 0.0
    
    # Gather evidence text from citations
    evidence_text = ""
    for citation in citations:
        chunk = _get_chunk_by_id(citation.chunk_id, source_chunks)
        if chunk:
            evidence_text += chunk.text + " "
        if citation.text_span:
            evidence_text += citation.text_span + " "
    
    # Explicit call language score
    explicit_score = has_explicit_call_language(call_direction, evidence_text)
    
    # General evidence strength
    evidence_score = score_evidence_strength(
        call_direction.value, citations, source_chunks
    )
    
    return (evidence_score * 0.5) + (explicit_score * 0.5)



# --- Document-Level Confidence (Task 7.3) ---

# Weights per CONFIDENCE.md
CONFIDENCE_WEIGHTS = {
    "extraction": 0.15,
    "profile": 0.15,
    "calls": 0.50,
    "summary": 0.20,
}


def _compute_attention_reasons(
    doc: DocumentJSON,
    profile: DocumentProfile,
    calls: list[AllocationCall],
    call_scores: list[float],
) -> list[str]:
    """Determine reasons for analyst attention."""
    reasons: list[str] = []
    
    if doc.extraction_coverage < 0.50:
        reasons.append("low_extraction_coverage")
    
    if profile.manager_name_uncertain:
        reasons.append("manager_name_unclear")
    
    if profile.publication_date_uncertain:
        reasons.append("publication_date_unclear")
    
    if any(c.needs_analyst_review for c in calls):
        reasons.append("call_needs_review")
    
    if any(s < 0.50 for s in call_scores):
        reasons.append("low_confidence_call")
    
    if not calls:
        reasons.append("no_calls_extracted")
    
    # Check if >30% of calls have low confidence
    if calls and len([s for s in call_scores if s < 0.60]) > len(calls) * 0.3:
        reasons.append("many_low_confidence_calls")
    
    return reasons


def compute_document_confidence(
    doc: DocumentJSON,
    profile: DocumentProfile,
    calls: list[AllocationCall],
    summaries: DocumentSummaries,
    source_chunks: list[RetrievedChunk],
) -> ConfidenceResult:
    """Compute document-level confidence with weighted aggregation.
    
    Weights per CONFIDENCE.md:
    - Extraction: 15%
    - Profile: 15%
    - Calls: 50%
    - Summary: 20%
    """
    # Component scores
    extraction_score = score_extraction_quality(doc)
    
    profile_score = score_evidence_strength(
        profile.manager_name, profile.citations, source_chunks
    )
    
    call_scores = [c.confidence for c in calls]
    avg_call_score = statistics.mean(call_scores) if call_scores else 0.5
    
    summary_score = score_evidence_strength(
        summaries.executive_summary, summaries.citations, source_chunks
    )
    
    # Weighted aggregate
    overall = (
        extraction_score * CONFIDENCE_WEIGHTS["extraction"]
        + profile_score * CONFIDENCE_WEIGHTS["profile"]
        + avg_call_score * CONFIDENCE_WEIGHTS["calls"]
        + summary_score * CONFIDENCE_WEIGHTS["summary"]
    )
    
    band = compute_confidence_band(overall)
    
    # Attention reasons
    attention_reasons = _compute_attention_reasons(doc, profile, calls, call_scores)
    attention_required = bool(attention_reasons) or band == ConfidenceBand.LOW
    
    # Build field confidences
    field_confidences = [
        FieldConfidence(
            field_name="extraction_quality",
            confidence=extraction_score,
            reasons=["text_coverage", "structure_quality"],
            has_explicit_evidence=True,
            evidence_strength=extraction_score,
        ),
        FieldConfidence(
            field_name="profile",
            confidence=profile_score,
            reasons=["manager_name_evidence"],
            has_explicit_evidence=profile_score > 0.5,
            evidence_strength=profile_score,
        ),
        FieldConfidence(
            field_name="calls",
            confidence=avg_call_score,
            reasons=[f"{len(calls)} calls extracted"],
            has_explicit_evidence=avg_call_score > 0.5,
            evidence_strength=avg_call_score,
        ),
        FieldConfidence(
            field_name="summary",
            confidence=summary_score,
            reasons=["summary_evidence"],
            has_explicit_evidence=summary_score > 0.5,
            evidence_strength=summary_score,
        ),
    ]
    
    return ConfidenceResult(
        document_id=doc.document_id,
        extraction_coverage=doc.extraction_coverage,
        overall_confidence=overall,
        confidence_band=band,
        field_confidences=field_confidences,
        analyst_attention_required=attention_required,
        attention_reasons=attention_reasons,
        verification_agreement=None,
        disagreed_fields=[],
    )


async def stage_confidence(
    doc: DocumentJSON,
    profile: DocumentProfile,
    calls: list[AllocationCall],
    summaries: DocumentSummaries,
    source_chunks: list[RetrievedChunk],
) -> ConfidenceResult:
    """Stage 10: Compute confidence scores and determine review routing."""
    return compute_document_confidence(doc, profile, calls, summaries, source_chunks)
