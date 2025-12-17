# Pipeline Specification

The pipeline processes one PDF at a time through 11 stages (0-10). Each stage has defined inputs, outputs, acceptance criteria, and error conditions.

---

## Pipeline Overview

```
S0 (Ingest) → S1 (Extract) → S2 (Clean) → S3 (Index) → S4 (Metadata) →
S5 (Candidates) → S6 (Calls) → S7 (Summaries) → S8 (Tooltips) → 
S9 (Tags) → S10 (Confidence) → [Publish/Review]
```

**Key Principles:**
1. Each stage is idempotent (same input = same output)
2. Each stage validates its output before passing to next
3. Failures at any stage halt the pipeline and flag for review
4. All LLM stages use retrieval grounding—never full document reads

---

## Stage 0: Pre-Ingestion Checks

**Purpose:** Receive PDF, deduplicate, assign IDs, store immutably.

### Input
- Raw PDF bytes
- Source metadata (channel, timestamp, filename)

### Process
1. Compute SHA-256 hash of PDF content
2. Check if hash exists in document registry
   - If exists: Return existing `document_id` (idempotent)
   - If new: Continue
3. Generate `document_id` (UUID)
4. Store PDF in blob storage
5. Create document record in PostgreSQL (status: `pending`)

### Output
```python
class IngestResult(BaseModel):
    document_id: str
    blob_id: str
    file_hash: str
    is_duplicate: bool
    source_metadata: dict
```

### Acceptance Criteria
- `document_id` is valid UUID
- PDF retrievable from blob storage
- Document record exists in database

### Error Conditions
- Invalid PDF (corrupted, password-protected) → FAIL with `InvalidPDFError`
- Storage failure → RETRY with exponential backoff

---

## Stage 1: Text + Layout Extraction

**Purpose:** Convert PDF to structured `DocumentJSON` with page-anchored blocks.

### Input
- `IngestResult` from S0
- PDF bytes from blob storage

### Process
1. **Primary extraction** (PyMuPDF/pdfplumber):
   - Extract text with layout preservation
   - Detect block types (heading, paragraph, bullet, table)
   - Capture bounding boxes
   
2. **Table extraction**:
   - Detect table structures
   - Extract cells with row/column positions
   
3. **OCR decision + page selection** (per page, scalable for large PDFs):
   - If `len(text) < 100 chars` → Mark as OCR candidate
   - If PDF metadata indicates image-based → Mark all pages as OCR candidates
   - For large documents, rank OCR-candidate pages using cheap triage so we don’t OCR everything:
     - Render low-DPI thumbnails and score signal likelihood (text density, table-like line structure, chart/heatmap structure)
     - Optionally run thumbnail OCR to detect call-keywords/numeric density (triage only)
   - Select the top `K` ranked candidate pages plus neighbors (e.g., `±1`), with a hard cap per document (e.g., `K=5`)
   - If the document is mostly image-based (very low pre-OCR coverage), route to a “full OCR” path on a larger worker or flag for analyst attention
   
4. **OCR execution** (selected pages only):
   - Run Tesseract/Cloud Vision
   - Merge OCR results into block structure
 
5. **Vision decision** (per page):
   - If `graphics_area > 50%` AND `text_area < 20%` → Flag for vision
   - If table detected but cells empty → Flag for vision
   
6. **Vision execution** (flagged pages only):
   - Send page image to vision LLM
   - Extract chart text, heatmap values
   - Create `CHART_TEXT` blocks

7. **Compute extraction coverage**:
   - `coverage = pages_with_text / total_pages`

### Output
```python
DocumentJSON  # See SCHEMAS.md
```

### Acceptance Criteria
- `extraction_coverage >= 0.70` (at least 70% of pages have text)
- Every block has valid `block_id`, `page`, `text`
- No duplicate `block_id` values

### Error Conditions
- `extraction_coverage < 0.50` → Flag `ANALYST_ATTENTION_REQUIRED`
- OCR failure → Log warning, continue with available text
- Vision failure → Log warning, continue without chart text

---

## Stage 2: Cleaning + Canonicalization

**Purpose:** Remove noise, standardize structure, detect sections.

### Input
- `DocumentJSON` from S1

### Process
1. **Remove boilerplate**:
   - Detect repeated headers/footers across pages
   - Remove but keep one instance
   
2. **Handle disclaimers**:
   - Detect standard disclaimer patterns
   - Mark as `BlockType.DISCLAIMER`
   - Keep one canonical instance
   
3. **Normalize text**:
   - Fix hyphenation across line breaks
   - Normalize whitespace
   - Fix common OCR errors (if OCR was used)
   
4. **Detect sections**:
   - Use heading patterns to identify sections
   - Assign section labels to blocks
   
5. **Optional LLM classification** (if sections unclear):
   - Classify major sections: Macro, Equities, Fixed Income, Risks, Appendix

### Output
```python
class CleanedDocument(BaseModel):
    document_id: str
    blocks: list[DocumentBlock]  # Cleaned
    sections: list[Section]
    removed_boilerplate_count: int
    disclaimer_block_id: str | None
```

### Acceptance Criteria
- No duplicate consecutive blocks with identical text
- Section boundaries identified
- Boilerplate ratio < 30% of total blocks

### Error Conditions
- Unable to detect any sections → Continue with flat structure (warning)

---

## Stage 3: Per-Document Retrieval Index

**Purpose:** Enable evidence-first extraction by building searchable index.

### Input
- `CleanedDocument` from S2

### Process
1. **Chunk document**:
   - Split by section + paragraph boundaries
   - Each chunk keeps `block_id`, `page` references
   - Chunk size: 200-400 tokens
   
2. **Generate embeddings**:
   - Use embedding model (e.g., `text-embedding-3-small`)
   - Store embeddings with chunk metadata
   
3. **Build vector index**:
   - In-memory for single PDF processing
   - Supports similarity search

### Output
```python
class RetrievalIndex(Protocol):
    async def query(
        self, 
        query: str, 
        top_k: int = 10,
        filters: dict | None = None
    ) -> list[RetrievedChunk]:
        ...

class RetrievedChunk(BaseModel):
    chunk_id: str  # Unique chunk identifier (e.g., "{doc_id}_{chunk_index}")
    block_ids: list[str]  # Block IDs from DocumentJSON that comprise this chunk
    page: int  # Page of first block
    text: str
    score: float
    section: str | None
```

### Acceptance Criteria
- All non-disclaimer blocks indexed
- Query returns results within 100ms

### Error Conditions
- Embedding API failure → RETRY with backoff
- Too few chunks (<5) → Warning, but continue

---

## Stage 4: Document Metadata Extraction

**Purpose:** Extract manager name, date, document type—the "header facts."

### Input
- `CleanedDocument` from S2
- `RetrievalIndex` from S3

### Process
1. **Retrieve likely metadata sections**:
   - Query: "document title author publication date"
   - Focus on first 2 pages, headers, cover
   
2. **LLM extraction**:
   - Prompt with retrieved chunks
   - Request `DocumentProfile` JSON
   - Require citations for each field
   
3. **Validation**:
   - Manager name must be non-empty
   - Date must be parseable and plausible (not future, not >5 years old)
   - Document type must be valid enum

### Output
```python
DocumentProfile  # See SCHEMAS.md
```

### Acceptance Criteria
- `manager_name` non-empty and not "Unknown"
- At least one citation provided
- If `publication_date` found, it's within valid range

### Error Conditions
- `manager_name` not found → Set `manager_name_uncertain=True`, flag for review
- Date unparseable → Set `publication_date=None`, `publication_date_uncertain=True`

---

## Stage 5: Signal Candidate Retrieval

**Purpose:** Identify passages likely containing allocation calls, without asking LLM to read everything.

### Input
- `CleanedDocument` from S2
- `RetrievalIndex` from S3
- `DocumentProfile` from S4

### Process
1. **Keyword mining** (deterministic):
   - Search for: "overweight", "underweight", "neutral", "prefer", "avoid", "bullish", "bearish", "conviction", "upgrade", "downgrade"
   - Search for taxonomy terms (asset class names)
   
2. **Retrieval expansion** (LLM-assisted):
   - Ask: "Given these candidate passages, are there other sections with positioning language not captured?"
   - Retrieve additional chunks via embeddings
   
3. **Deduplication**:
   - Merge overlapping chunks
   - Rank by signal density

### Output
```python
class CandidateSet(BaseModel):
    document_id: str
    candidates: list[RetrievedChunk]
    keyword_matches: dict[str, list[str]]  # keyword → block_ids
    total_chunks_reviewed: int
```

### Acceptance Criteria
- At least 3 candidate chunks identified
- Coverage of major sections (not all from one page)

### Error Conditions
- Zero candidates found → Flag for review, but continue with all sections

---

## Stage 6: Structured Call Extraction (CRITICAL)

**Purpose:** Extract allocation calls with taxonomy mapping, rationale, and citations.

**This is the core value-producing stage. Read carefully.**

### Input
- `CleanedDocument` from S2
- `RetrievalIndex` from S3
- `CandidateSet` from S5
- Asset taxonomy (see [`TAXONOMY.md`](TAXONOMY.md))

### Process

#### 6.1 Asset Mention Detection
For each candidate chunk:
1. LLM identifies asset class mentions
2. Maps to taxonomy (category + sub-asset class)
3. Collects evidence chunks

#### 6.2 Call Classification
For each identified asset:
1. Determine call direction: `OVERWEIGHT`, `NEUTRAL`, `UNDERWEIGHT`
2. Extract conviction level (if stated)
3. Extract rationale (2-4 bullets)
4. Identify key indicators and risks
5. Cite evidence (chunk_id + page)

#### 6.3 Sentiment Extraction
1. Determine overall document sentiment
2. Extract sentiment rationale
3. Cite evidence

#### 6.4 Verification Pass (Optional but recommended)
1. Re-run extraction with different prompt
2. Compare call directions
3. Flag disagreements for review

### LLM Contract

```
Input: Candidate chunks + taxonomy
Output: CallExtractionOutput (validated Pydantic)

CRITICAL RULES:
- If call direction unclear from evidence → output call=UNCERTAIN, needs_analyst_review=true
- If asset not in taxonomy → output asset_class_category="UNMAPPED", flag for review
- Every call MUST have at least one citation
- Rationale must be supported by cited evidence
```

See [`LLM_CONTRACTS.md`](LLM_CONTRACTS.md) for full prompt template.

### Output
```python
CallExtractionOutput  # See SCHEMAS.md
```

### Acceptance Criteria
- Every `AllocationCall` has valid taxonomy mapping
- Every `AllocationCall` has ≥1 citation
- Rationale bullets are non-empty
- No duplicate (asset_class_category, sub_asset_class) pairs

### Error Conditions
- Zero calls extracted → Flag for review (might be thematic piece with no explicit calls)
- >50% calls have `needs_analyst_review=True` → Flag entire document
- Taxonomy mapping failure → Log unmapped term, use "UNMAPPED" category

---

## Stage 7: Summary Generation

**Purpose:** Generate client-facing executive summary, search descriptor, and key takeaways.

### Input
- `CleanedDocument` from S2
- `RetrievalIndex` from S3
- `CallExtractionOutput` from S6
- `DocumentProfile` from S4

### Process
1. **Executive Summary**:
   - Retrieve top signal passages
   - Generate 120-180 word summary
   - Include: top macro drivers, top 3 calls, 2 key risks
   - Must preserve attribution ("The manager argues...")
   
2. **Search Descriptor**:
   - Generate 20-35 word descriptor
   - Format: "what this is" + "what it implies" + "main asset focus"
   
3. **Key Takeaways**:
   - Generate 3-5 bullets
   - Each must have citation

### LLM Contract
```
Constraints:
- executive_summary: 120-180 words, max 6 bullets
- search_descriptor: 20-35 words
- key_takeaways: 3-5 items, each with citation

DO NOT include information not supported by document.
DO NOT make up statistics or dates.
```

### Output
```python
DocumentSummaries  # See SCHEMAS.md
```

### Acceptance Criteria
- Word counts within specified ranges
- All takeaways have citations
- No hallucinated content

### Error Conditions
- Summary exceeds length limits → Truncate and flag
- Missing citations → Flag for review

---

## Stage 8: Tooltip Generation

**Purpose:** Generate hover text for each allocation call (for Allocator Pro UI).

### Input
- `CallExtractionOutput` from S6

### Process
For each `AllocationCall`:
1. Generate tooltip ≤25 words
2. Include key rationale point
3. Optionally include "watch item"

### LLM Contract
```
For each call, generate:
- tooltip_text: ≤25 words, concise summary of positioning and why
- Must reference rationale, not be generic

Example: "Overweight Bunds as quality hedge; expects easing inflation and flight-to-safety if risk rises."
```

### Output
```python
# Updates each AllocationCall.tooltip_text in place
```

### Acceptance Criteria
- All calls have non-empty tooltip
- Tooltips ≤150 characters
- Tooltips are specific to the call (not generic)

### Error Conditions
- Generic tooltip detected → Re-generate with more context

---

## Stage 9: Tag Generation

**Purpose:** Generate normalized tags for filtering and search.

### Input
- `CleanedDocument` from S2
- `CallExtractionOutput` from S6
- `DocumentProfile` from S4

### Process
1. **Deterministic tagging**:
   - Asset class tags from taxonomy mapping
   - Region tags from explicit mentions
   - Instrument tags from asset names
   
2. **LLM tagging**:
   - Theme tags (inflation, AI capex, energy transition, etc.)
   - Risk tags
   - Macro regime tags
   
3. **Normalization**:
   - Map to allowed tag values
   - Deduplicate
   - Remove low-confidence tags

### Tag Taxonomy
See [`TAXONOMY.md`](TAXONOMY.md) for allowed tag values.

### Output
```python
TagSet  # See SCHEMAS.md
```

### Acceptance Criteria
- At least 5 tags total
- At least 1 asset class tag
- All tags in allowed vocabulary

### Error Conditions
- Novel tag not in vocabulary → Add with low confidence, flag for taxonomy expansion

---

## Stage 10: Confidence Scoring + Flagging

**Purpose:** Compute confidence scores and determine review routing.

### Input
- All outputs from S1-S9
- `DocumentJSON` from S1

### Process
1. **Extraction quality scoring**:
   - Extraction coverage
   - OCR quality (if used)
   - Table extraction success
   
2. **Evidence strength scoring** (per call):
   - Does evidence contain explicit call language?
   - Entailment score between claim and evidence
   
3. **Cross-pass agreement** (if verification run):
   - Agreement rate on call directions
   
4. **Schema validation**:
   - All required fields present
   - All citations valid
   - Dates plausible
   
5. **Compute overall confidence**:
   - Weighted average of component scores
   - Map to confidence band

6. **Flag for review**:
   - If any core field is LOW → `analyst_attention_required = True`
   - If >30% calls are LOW → `analyst_attention_required = True`

### Output
```python
ConfidenceResult  # See SCHEMAS.md
```

### Acceptance Criteria
- Confidence score in [0, 1]
- Band correctly assigned per thresholds
- Attention reasons populated if flagged

### Routing
```
HIGH (≥0.80)     → Auto-publish to Allocator Pro
MEDIUM (0.60-0.79) → Spot-check queue (sampled)
LOW (<0.60)      → Must-review queue
```

---

## Pipeline Orchestration

```python
async def process_pdf(pdf_bytes: bytes, metadata: dict) -> ProcessedDocument:
    # S0: Ingest
    ingest = await stage_ingest(pdf_bytes, metadata)
    if ingest.is_duplicate:
        return await get_existing_document(ingest.document_id)
    
    # S1: Extract
    doc_json = await stage_extract(ingest)
    
    # S2: Clean
    cleaned = await stage_clean(doc_json)
    
    # S3: Index
    index = await stage_index(cleaned)
    
    # S4: Metadata
    profile = await stage_metadata(cleaned, index)
    
    # S5: Candidates
    candidates = await stage_candidates(cleaned, index, profile)
    
    # S6: Calls (CRITICAL)
    calls = await stage_calls(cleaned, index, candidates)
    
    # S7: Summaries
    summaries = await stage_summaries(cleaned, index, calls, profile)
    
    # S8: Tooltips
    calls = await stage_tooltips(calls)  # Mutates in place
    
    # S9: Tags
    tags = await stage_tags(cleaned, calls, profile)
    
    # S10: Confidence
    confidence = await stage_confidence(
        doc_json, cleaned, profile, calls, summaries, tags
    )
    
    # Assemble final output
    result = ProcessedDocument(
        document_id=ingest.document_id,
        profile=profile,
        allocation_calls=calls.allocation_calls,
        overall_sentiment=calls.overall_sentiment,
        sentiment_rationale=calls.sentiment_rationale,
        sentiment_citations=calls.sentiment_citations,
        summaries=summaries,
        tags=tags,
        confidence=confidence,
        processing_timestamp=datetime.utcnow(),
        pipeline_version=PIPELINE_VERSION,
        total_processing_time_seconds=elapsed,
    )
    
    # Persist and route
    await persist_to_database(result)
    await index_for_search(result)
    await route_for_review(result)
    
    return result
```

---

## Stage Dependencies

```
S0 ─► S1 ─► S2 ─► S3 ─┬─► S4 ─┬─► S5 ─► S6 ─┬─► S7
                      │       │              │
                      │       └──────────────┼─► S8
                      │                      │
                      └──────────────────────┴─► S9 ─► S10
```

- S4, S5, S6 all require S3 (retrieval index)
- S6 requires S4 (manager name for context) and S5 (candidates)
- S7, S8, S9 require S6 (calls)
- S10 requires all previous outputs
