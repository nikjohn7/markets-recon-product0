# Confidence Scoring

This document defines how confidence is computed, thresholds for routing, and flagging logic.

---

## Confidence Model

Confidence is computed at multiple levels:

1. **Field-level:** Each extracted field has its own confidence
2. **Call-level:** Each allocation call has aggregate confidence
3. **Document-level:** Overall extraction confidence

Final routing is based on document-level confidence.

---

## Scoring Components

### 1. Extraction Quality Score (0-1)

Measures the quality of PDF text extraction.

```python
def score_extraction_quality(doc: DocumentJSON) -> float:
    scores = []
    
    # Text coverage (most important)
    coverage = doc.extraction_coverage
    scores.append(coverage * 0.4)
    
    # OCR quality (if OCR was used)
    if doc.ocr_pages:
        ocr_quality = compute_ocr_quality(doc)
        scores.append(ocr_quality * 0.2)
    else:
        scores.append(0.2)  # Full credit if no OCR needed
    
    # Table extraction success
    table_success = compute_table_success(doc)
    scores.append(table_success * 0.2)
    
    # Block structure quality
    structure_quality = compute_structure_quality(doc)
    scores.append(structure_quality * 0.2)
    
    return sum(scores)
```

#### Sub-components

| Component | Weight | Calculation |
|-----------|--------|-------------|
| Text coverage | 40% | `pages_with_text / total_pages` |
| OCR quality | 20% | `1 - (garbled_chars / total_chars)` |
| Table success | 20% | `tables_with_content / tables_detected` |
| Structure quality | 20% | Heading/section detection success |

### 2. Evidence Strength Score (0-1)

Measures how well evidence supports extracted claims.

```python
def score_evidence_strength(
    field_value: Any,
    citations: list[Citation],
    source_chunks: list[Chunk],
) -> float:
    if not citations:
        return 0.0
    
    scores = []
    
    for citation in citations:
        chunk = get_chunk(citation.chunk_id, source_chunks)
        
        # Explicit mention score
        explicit = has_explicit_mention(field_value, chunk.text)
        scores.append(explicit * 0.5)
        
        # Semantic similarity score
        similarity = compute_similarity(str(field_value), chunk.text)
        scores.append(similarity * 0.3)
        
        # Entailment score
        entailment = compute_entailment(str(field_value), chunk.text)
        scores.append(entailment * 0.2)
    
    return max(scores)  # Best supporting evidence
```

#### Call Direction Evidence

For allocation calls, specific patterns boost confidence:

```python
EXPLICIT_CALL_PATTERNS = {
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
    # UNCERTAIN is a valid direction but should not receive an "explicit language" bonus.
    CallDirection.UNCERTAIN: [],
}

def has_explicit_call_language(
    call: CallDirection,
    evidence_text: str,
) -> float:
    patterns = EXPLICIT_CALL_PATTERNS.get(call, [])
    if call == CallDirection.UNCERTAIN:
        return 0.0
    text_lower = evidence_text.lower()
    
    for pattern in patterns:
        if re.search(pattern, text_lower):
            return 1.0  # Explicit language found
    
    return 0.0  # No explicit language
```

### Summary Evidence Score (0-1)

Summaries are **synthetic** (paraphrased) and generally will not appear verbatim in the
source document. Scoring the full executive summary using "explicit mention" heuristics
causes systematically low scores.

Instead, the summary evidence score is computed from:
- **Takeaway alignment**: word overlap between each `key_takeaway.text` and its cited evidence
- **Citation count**: do we have enough top-level citations supporting the executive summary?
- **Page diversity**: are citations spread across multiple pages (less reliance on a single spot)?

```python
def score_summary_evidence(
    summaries: DocumentSummaries,
    source_chunks: list[Chunk],
) -> float:
    takeaway_scores = [
        max(word_overlap(t.text, cited_text(c, source_chunks)) for c in t.citations)
        for t in summaries.key_takeaways
    ]
    alignment = mean(takeaway_scores) if takeaway_scores else 0.0

    citation_count = min(1.0, len(summaries.citations) / 4.0)
    page_diversity = min(1.0, unique_pages(summaries) / 4.0)

    return 0.60 * alignment + 0.20 * citation_count + 0.20 * page_diversity
```

### 3. Cross-Pass Agreement Score (0-1)

Measures agreement between independent extraction passes.

```python
def score_cross_pass_agreement(
    primary_calls: list[AllocationCall],
    verification_calls: list[VerifiedCall],
) -> float:
    if not verification_calls:
        return None  # Verification not run
    
    agreements = 0
    total = len(primary_calls)
    
    for primary, verified in zip(primary_calls, verification_calls):
        if verified.call_verified:
            agreements += 1
    
    return agreements / total if total > 0 else 1.0
```

### 4. Schema Compliance Score (0-1)

Measures adherence to expected output structure.

```python
def score_schema_compliance(output: ProcessedDocument) -> float:
    checks = []
    
    # Required fields present
    checks.append(has_required_fields(output))
    
    # Enum values valid
    checks.append(has_valid_enums(output))
    
    # Citations reference valid chunks
    checks.append(has_valid_citations(output))
    
    # Dates are plausible
    checks.append(has_plausible_dates(output))
    
    # Taxonomy codes are valid
    checks.append(has_valid_taxonomy(output))
    
    return sum(checks) / len(checks)
```

---

## Confidence Aggregation

### Call-Level Confidence

```python
def compute_call_confidence(
    call: AllocationCall,
    source_chunks: list[Chunk],
    verification: VerifiedCall | None,
) -> float:
    scores = []
    weights = []
    
    # Evidence strength (highest weight)
    evidence_score = score_evidence_strength(
        call.call, call.citations, source_chunks
    )
    scores.append(evidence_score)
    weights.append(0.5)
    
    # Explicit language bonus
    explicit_score = has_explicit_call_language(
        call.call,
        " ".join(c.text_span or "" for c in call.citations)
    )
    scores.append(explicit_score)
    weights.append(0.25)
    
    # Verification agreement (if available)
    if verification:
        agreement = 1.0 if verification.call_verified else 0.0
        scores.append(agreement)
        weights.append(0.25)
    else:
        # Redistribute weight to evidence
        weights[0] += 0.25
    
    return sum(s * w for s, w in zip(scores, weights))
```

### Document-Level Confidence

```python
def compute_document_confidence(
    doc: DocumentJSON,
    profile: DocumentProfile,
    calls: list[AllocationCall],
    summaries: DocumentSummaries,
) -> ConfidenceResult:
    
    # Component scores
    extraction_score = score_extraction_quality(doc)
    
    profile_score = score_evidence_strength(
        profile.manager_name, profile.citations, get_chunks(doc)
    )
    
    call_scores = [call.confidence for call in calls]
    avg_call_score = statistics.mean(call_scores) if call_scores else 0.5
    
    # NOTE: Summary text is synthetic (paraphrased) and usually won't appear verbatim
    # in the source chunks. Scoring it with "explicit mention" tends to under-score.
    summary_score = score_summary_evidence(
        summaries, get_chunks(doc)
    )
    
    # Weighted aggregate
    weights = {
        "extraction": 0.15,
        "profile": 0.15,
        "calls": 0.50,  # Calls are the core value
        "summary": 0.20,
    }
    
    overall = (
        extraction_score * weights["extraction"] +
        profile_score * weights["profile"] +
        avg_call_score * weights["calls"] +
        summary_score * weights["summary"]
    )
    
    # Determine band
    band = (
        ConfidenceBand.HIGH if overall >= 0.80
        else ConfidenceBand.MEDIUM if overall >= 0.60
        else ConfidenceBand.LOW
    )
    
    # Determine if review needed
    attention_required = (
        band == ConfidenceBand.LOW or
        any(c.needs_analyst_review for c in calls) or
        profile.manager_name_uncertain or
        len([c for c in call_scores if c < 0.60]) > len(calls) * 0.3
    )
    
    return ConfidenceResult(
        document_id=doc.document_id,
        extraction_coverage=doc.extraction_coverage,
        overall_confidence=overall,
        confidence_band=band,
        analyst_attention_required=attention_required,
        ...
    )
```

---

## Thresholds and Routing

| Band | Confidence Range | Routing Action |
|------|------------------|----------------|
| HIGH | ≥ 0.80 | Auto-publish to Allocator Pro |
| MEDIUM | 0.60 – 0.79 | Spot-check queue (sampled) |
| LOW | < 0.60 | Must-review queue |

### Auto-Publish Criteria (HIGH band only)

All must be true:
- `overall_confidence >= 0.80`
- `extraction_coverage >= 0.70`
- No calls with `needs_analyst_review = true`
- `manager_name_uncertain = false`
- `publication_date_uncertain = false`

```python
def can_auto_publish(result: ConfidenceResult, profile: DocumentProfile) -> bool:
    return (
        result.overall_confidence >= 0.80 and
        result.extraction_coverage >= 0.70 and
        not result.analyst_attention_required and
        not profile.manager_name_uncertain and
        not profile.publication_date_uncertain
    )
```

### Spot-Check Sampling (MEDIUM band)

```python
SPOT_CHECK_SAMPLE_RATE = 0.20  # 20% of MEDIUM confidence docs

def should_spot_check(result: ConfidenceResult) -> bool:
    if result.confidence_band != ConfidenceBand.MEDIUM:
        return False
    
    # Sample 20%
    return random.random() < SPOT_CHECK_SAMPLE_RATE
```

---

## Attention Flags

### Flag: `ANALYST_ATTENTION_REQUIRED`

Triggered when:

```python
ATTENTION_TRIGGERS = [
    # Extraction issues
    ("extraction_coverage < 0.50", "Low text extraction coverage"),
    ("ocr_quality < 0.70", "Poor OCR quality"),
    
    # Profile issues
    ("manager_name_uncertain", "Manager name unclear"),
    ("publication_date_uncertain", "Publication date unclear"),
    ("document_type == OTHER", "Document type unclassified"),
    
    # Call issues
    ("any(call.needs_analyst_review)", "One or more calls need review"),
    ("any(call.confidence < 0.50)", "Low confidence calls detected"),
    ("sum(call.call is None) > 0", "Unable to determine call direction"),
    ("unmapped_taxonomy_codes > 0", "Unmapped asset classes"),
    
    # Cross-pass issues
    ("verification_agreement < 0.80", "Low verification agreement"),
    
    # Anomalies
    ("zero_calls_extracted", "No allocation calls found"),
    ("calls_from_single_page", "All calls from one page (suspicious)"),
]
```

### Attention Reason Codes

```python
class AttentionReason(str, Enum):
    LOW_EXTRACTION = "low_extraction_coverage"
    POOR_OCR = "poor_ocr_quality"
    MANAGER_UNCLEAR = "manager_name_unclear"
    DATE_UNCLEAR = "publication_date_unclear"
    CALL_AMBIGUOUS = "call_direction_ambiguous"
    WEAK_EVIDENCE = "weak_evidence_for_call"
    UNMAPPED_ASSET = "unmapped_asset_class"
    VERIFICATION_DISAGREE = "verification_pass_disagreement"
    NO_CALLS = "no_calls_extracted"
    SUSPICIOUS_PATTERN = "suspicious_extraction_pattern"
```

---

## Confidence Calibration

### Quality Metrics to Track

```python
CALIBRATION_METRICS = {
    # Should correlate with actual quality
    "confidence_vs_analyst_approval": "% of HIGH confidence docs approved without changes",
    "confidence_vs_analyst_edits": "% of LOW confidence docs requiring edits",
    
    # False negatives (missed issues)
    "high_confidence_analyst_rejections": "HIGH confidence docs rejected by analyst",
    
    # False positives (unnecessary reviews)
    "low_confidence_no_change": "LOW confidence docs approved without changes",
}
```

### Calibration Targets

| Metric | Target |
|--------|--------|
| HIGH confidence approval rate | ≥ 95% |
| LOW confidence edit rate | ≥ 70% |
| HIGH confidence rejection rate | ≤ 2% |
| LOW confidence no-change rate | ≤ 30% |

### Threshold Adjustment

```python
def adjust_thresholds(calibration_data: CalibrationData):
    """
    Periodically adjust thresholds based on analyst feedback.
    """
    
    # If too many HIGH confidence docs get rejected
    if calibration_data.high_rejection_rate > 0.02:
        # Raise HIGH threshold
        THRESHOLDS["HIGH"] = min(THRESHOLDS["HIGH"] + 0.02, 0.90)
    
    # If too many LOW confidence docs have no changes
    if calibration_data.low_no_change_rate > 0.30:
        # Lower LOW threshold
        THRESHOLDS["LOW"] = max(THRESHOLDS["LOW"] - 0.02, 0.50)
```

---

## Implementation

### Confidence Scorer Class

```python
class ConfidenceScorer:
    def __init__(
        self,
        taxonomy: AssetTaxonomy,
        thresholds: dict[str, float] = None,
    ):
        self.taxonomy = taxonomy
        self.thresholds = thresholds or {
            "HIGH": 0.80,
            "LOW": 0.60,
        }
    
    def score_document(
        self,
        doc: DocumentJSON,
        profile: DocumentProfile,
        calls: CallExtractionOutput,
        summaries: DocumentSummaries,
        tags: TagSet,
        verification: VerificationResult | None = None,
    ) -> ConfidenceResult:
        # Implementation as described above
        ...
    
    def score_call(
        self,
        call: AllocationCall,
        source_chunks: list[Chunk],
        verification: VerifiedCall | None = None,
    ) -> float:
        # Implementation as described above
        ...
    
    def determine_routing(
        self,
        result: ConfidenceResult,
    ) -> DocumentRouting:
        if self.can_auto_publish(result):
            return DocumentRouting.AUTO_PUBLISH
        elif result.confidence_band == ConfidenceBand.MEDIUM:
            if self.should_spot_check(result):
                return DocumentRouting.SPOT_CHECK
            else:
                return DocumentRouting.AUTO_PUBLISH
        else:
            return DocumentRouting.MUST_REVIEW
```

---

## Debugging Low Confidence

When investigating low confidence scores:

```python
def explain_confidence(result: ConfidenceResult) -> str:
    """Generate human-readable explanation of confidence score."""
    
    explanations = []
    
    # Extraction issues
    if result.extraction_coverage < 0.70:
        explanations.append(
            f"⚠️ Low extraction coverage: {result.extraction_coverage:.0%}"
        )
    
    # Field-level issues
    for field in result.field_confidences:
        if field.confidence < 0.60:
            explanations.append(
                f"⚠️ Low confidence for {field.field_name}: {field.confidence:.0%}"
                f" - {', '.join(field.reasons)}"
            )
    
    # Call-level issues
    low_calls = [c for c in result.call_confidences if c < 0.60]
    if low_calls:
        explanations.append(
            f"⚠️ {len(low_calls)} calls have low confidence"
        )
    
    return "\n".join(explanations)
```
