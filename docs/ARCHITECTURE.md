# Architecture

## System Overview

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                           DOCUMENT PLANE (per PDF)                          │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  ┌─────────┐   ┌──────────┐   ┌─────────┐   ┌─────────┐   ┌─────────────┐  │
│  │ Ingest  │ → │ Extract  │ → │  Clean  │ → │  Index  │ → │ LLM Stages  │  │
│  │ (S0)    │   │ (S1)     │   │ (S2)    │   │ (S3)    │   │ (S4-S9)     │  │
│  └─────────┘   └──────────┘   └─────────┘   └─────────┘   └─────────────┘  │
│       │                                           │               │         │
│       ▼                                           ▼               ▼         │
│  ┌─────────┐                                ┌──────────┐   ┌─────────────┐  │
│  │  Blob   │                                │ Per-Doc  │   │ Confidence  │  │
│  │ Storage │                                │ Vector   │   │ Scoring     │  │
│  │ (PDFs)  │                                │ Index    │   │ (S10)       │  │
│  └─────────┘                                └──────────┘   └─────────────┘  │
│                                                                    │        │
└────────────────────────────────────────────────────────────────────┼────────┘
                                                                     │
                                                                     ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                              PRODUCT PLANE                                  │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  ┌──────────────┐        ┌───────────────┐        ┌─────────────────────┐  │
│  │  PostgreSQL  │        │  Search Index │        │   Allocator Pro     │  │
│  │              │        │  (OpenSearch/ │        │   API               │  │
│  │  - Managers  │◄──────►│   pgvector)   │◄──────►│                     │  │
│  │  - Documents │        │               │        │   - Module 1-5      │  │
│  │  - Calls     │        │  - Summaries  │        │   - Charts          │  │
│  │  - Tags      │        │  - Tags       │        │   - Grids           │  │
│  │  - Evidence  │        │  - Embeddings │        │   - Hover/Tooltips  │  │
│  └──────────────┘        └───────────────┘        └─────────────────────┘  │
│         │                                                                   │
│         ▼                                                                   │
│  ┌──────────────┐                                                          │
│  │  Review UI   │                                                          │
│  │  (Analyst)   │                                                          │
│  └──────────────┘                                                          │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## Core Components

### A. Ingestion + Storage

**Responsibility:** Receive PDFs, dedupe, assign IDs, store immutably.

```python
# Key interfaces
class BlobStorage(Protocol):
    async def store(self, content: bytes, metadata: dict) -> str:
        """Store PDF, return blob_id."""
        ...
    
    async def retrieve(self, blob_id: str) -> bytes:
        """Retrieve PDF content."""
        ...

class DocumentRegistry(Protocol):
    async def register(self, blob_id: str, file_hash: str, metadata: IngestMetadata) -> str:
        """Register document, return document_id. Idempotent on file_hash."""
        ...
```

**Storage:**
- Raw PDFs: S3/GCS/Azure Blob (immutable)
- Metadata: PostgreSQL `documents` table

**Deduplication:** SHA-256 hash of PDF content. Same hash = same document_id returned.

---

### B. Document Understanding Service

**Responsibility:** Convert PDF → structured `DocumentJSON` with page-anchored blocks.

```python
@dataclass
class DocumentBlock:
    block_id: str           # Stable ID: f"{page}_{index}"
    page: int
    text: str
    block_type: BlockType   # HEADING, PARAGRAPH, BULLET, TABLE_CELL, CHART_TEXT
    bbox: BoundingBox | None
    confidence: float       # Extraction confidence

@dataclass  
class DocumentJSON:
    document_id: str
    blocks: list[DocumentBlock]
    tables: list[ExtractedTable]
    page_count: int
    extraction_coverage: float  # % pages with usable text
```

**Components:**
1. **PDF Parser** (PyMuPDF/pdfplumber): Text + layout extraction
2. **OCR Engine** (Tesseract/Cloud Vision): Fallback for scanned pages
3. **Chart Extractor** (Vision LLM): For heatmaps, quadrant charts

**OCR Trigger Heuristics:**
- Extracted text/page < 100 chars
- PDF flagged as image-based
- Known manager templates that are scan-heavy

**Selective OCR Page Selection (MVP):**
- Run the PDF parser on every page first and compute per-page text stats (e.g., `char_count`).
- Mark pages as **OCR candidates** when the text layer is weak (e.g., `char_count < 100`) or the PDF is image-based.
- Rank OCR-candidate pages using **cheap triage** so we don’t OCR the whole deck:
  - Render low-DPI thumbnails and score “signal likelihood” (text density, table-like line structure, chart/heatmap structure).
  - Optionally run a *thumbnail* OCR pass to detect call-keywords/numeric density (triage only; not the final extraction).
- OCR only the top `K` ranked pages **plus neighbors** (e.g., `±1` page), with a hard cap per document (e.g., `K=5`).
- If the document is mostly image-based (very low text coverage), route to a “full OCR” path on a larger worker or flag for analyst attention (selective OCR won’t be sufficient).

**Chart/Vision Trigger Heuristics:**
- Page has >50% vector graphics, <20% text
- Legend/label keywords detected but call terms missing
- Table structure detected but cells empty

---

### C. LLM Orchestrator

**Responsibility:** Run multi-stage extraction pipeline, enforce JSON contracts.

```python
class LLMOrchestrator:
    """Coordinates LLM stages with retrieval grounding."""
    
    async def run_stage(
        self,
        stage: ExtractionStage,
        doc: DocumentJSON,
        retrieval_index: RetrievalIndex,
        previous_outputs: dict[str, Any],
    ) -> StageOutput:
        # 1. Retrieve relevant chunks
        chunks = await retrieval_index.query(stage.retrieval_query)
        
        # 2. Build grounded prompt
        prompt = stage.build_prompt(chunks, previous_outputs)
        
        # 3. Call LLM with JSON schema
        raw_output = await self.llm.complete(prompt, schema=stage.output_schema)
        
        # 4. Validate output
        validated = stage.output_schema.model_validate(raw_output)
        
        # 5. Verify citations exist
        self._verify_citations(validated, doc)
        
        return validated
```

**Key principle:** LLMs never see full documents. They see retrieved chunks + previous stage outputs.

---

### D. Validation + Confidence Service

**Responsibility:** Score confidence, flag items for review.

```python
class ConfidenceScorer:
    def score(
        self,
        extracted: ExtractedOutput,
        doc: DocumentJSON,
        evidence_chunks: list[DocumentBlock],
    ) -> ConfidenceResult:
        scores = []
        reasons = []
        
        # 1. Extraction quality
        scores.append(self._score_extraction_quality(doc))
        
        # 2. Evidence strength per field
        for field, citations in extracted.iter_cited_fields():
            strength = self._score_evidence_strength(field, citations, evidence_chunks)
            scores.append(strength)
            if strength < 0.6:
                reasons.append(f"Weak evidence for {field.name}")
        
        # 3. Cross-pass agreement (if available)
        if extracted.verification_pass:
            agreement = self._score_agreement(extracted, extracted.verification_pass)
            scores.append(agreement)
        
        return ConfidenceResult(
            score=statistics.mean(scores),
            band=self._to_band(statistics.mean(scores)),
            reasons=reasons,
        )
```

---

### E. Data Stores

#### PostgreSQL Schema (Core Tables)

```sql
-- Managers (asset management firms)
CREATE TABLE managers (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name TEXT NOT NULL UNIQUE,
    aliases TEXT[],
    created_at TIMESTAMPTZ DEFAULT now()
);

-- Documents (outlook papers)
CREATE TABLE documents (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    manager_id UUID REFERENCES managers(id),
    blob_id TEXT NOT NULL,
    file_hash TEXT NOT NULL UNIQUE,
    title TEXT,
    publication_date DATE,
    as_of_date DATE,
    document_type document_type_enum,
    time_snapshot TEXT,  -- '2025', '2025_MID_YEAR', 'H2_2025'
    extraction_coverage FLOAT,
    overall_confidence FLOAT,
    analyst_attention_required BOOLEAN DEFAULT false,
    status document_status_enum DEFAULT 'pending',
    created_at TIMESTAMPTZ DEFAULT now(),
    reviewed_at TIMESTAMPTZ,
    reviewed_by UUID
);

-- Allocation Calls (core Allocator Pro data)
CREATE TABLE allocation_calls (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    document_id UUID REFERENCES documents(id),
    asset_class_category TEXT NOT NULL,
    sub_asset_class TEXT NOT NULL,
    call call_enum NOT NULL,  -- OVERWEIGHT, NEUTRAL, UNDERWEIGHT, UNCERTAIN
    conviction conviction_enum,
    time_horizon TEXT,
    rationale_bullets JSONB,  -- ["bullet1", "bullet2"]
    key_indicators JSONB,
    key_risks JSONB,
    tooltip_text TEXT,
    citations JSONB NOT NULL,  -- [{chunk_id, block_ids, page, text_span}]
    confidence FLOAT NOT NULL,
    needs_analyst_review BOOLEAN DEFAULT false,
    created_at TIMESTAMPTZ DEFAULT now()
);

-- Document Summaries
CREATE TABLE summaries (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    document_id UUID REFERENCES documents(id) UNIQUE,
    executive_summary TEXT,
    search_descriptor TEXT,
    key_takeaways JSONB,
    overall_sentiment sentiment_enum,
    sentiment_rationale JSONB,
    sentiment_citations JSONB,
    created_at TIMESTAMPTZ DEFAULT now()
);

-- Tags (normalized, for filtering)
CREATE TABLE document_tags (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    document_id UUID REFERENCES documents(id),
    tag_type tag_type_enum,  -- ASSET_CLASS, REGION, THEME, RISK, etc.
    tag_value TEXT NOT NULL,
    confidence FLOAT,
    UNIQUE(document_id, tag_type, tag_value)
);

-- Evidence Store (for audit trail)
CREATE TABLE evidence_blocks (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    document_id UUID REFERENCES documents(id),
    chunk_id TEXT NOT NULL,
    page INT NOT NULL,
    text TEXT NOT NULL,
    block_type block_type_enum,
    bbox JSONB,
    UNIQUE(document_id, chunk_id)
);

-- Analyst Review Audit Log
CREATE TABLE review_log (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    document_id UUID REFERENCES documents(id),
    call_id UUID REFERENCES allocation_calls(id),
    reviewer_id UUID NOT NULL,
    action review_action_enum,  -- APPROVED, EDITED, REJECTED
    field_changed TEXT,
    old_value JSONB,
    new_value JSONB,
    reason TEXT,
    created_at TIMESTAMPTZ DEFAULT now()
);
```

#### Search Index (OpenSearch/Elasticsearch)

```json
{
  "mappings": {
    "properties": {
      "document_id": { "type": "keyword" },
      "manager_name": { "type": "text", "fields": { "keyword": { "type": "keyword" }}},
      "title": { "type": "text" },
      "publication_date": { "type": "date" },
      "document_type": { "type": "keyword" },
      "time_snapshot": { "type": "keyword" },
      
      "executive_summary": { "type": "text" },
      "search_descriptor": { "type": "text" },
      "key_takeaways": { "type": "text" },
      
      "asset_class_tags": { "type": "keyword" },
      "region_tags": { "type": "keyword" },
      "theme_tags": { "type": "keyword" },
      "risk_tags": { "type": "keyword" },
      
      "overall_sentiment": { "type": "keyword" },
      
      "calls": {
        "type": "nested",
        "properties": {
          "asset_class_category": { "type": "keyword" },
          "sub_asset_class": { "type": "keyword" },
          "call": { "type": "keyword" },
          "tooltip_text": { "type": "text" }
        }
      },
      
      "summary_embedding": { "type": "dense_vector", "dims": 1536 }
    }
  }
}
```

---

### F. Review UI (Analyst Interface)

See [`REVIEW_UI.md`](REVIEW_UI.md) for full specification.

**Core principle:** Evidence-first editing. Analyst sees:
- Left pane: Original PDF viewer, scrolled to cited page
- Right pane: Extracted data with highlighted evidence
- Edit controls: Change call, edit rationale, add/remove tags

---

## Data Flow Example

```
1. PDF uploaded via API/email/SFTP
                ↓
2. S0: Assign document_id, compute hash, store in blob storage
                ↓
3. S1: Extract text/layout → DocumentJSON with blocks
                ↓
4. S2: Clean boilerplate, detect sections
                ↓
5. S3: Build per-document vector index for retrieval
                ↓
6. S4: LLM extracts document metadata (manager, date, type)
                ↓
7. S5: Retrieve candidate signal passages (OW/UW/N keywords)
                ↓
8. S6: LLM extracts AllocationCalls with citations
                ↓
9. S7: LLM generates summaries (executive, search descriptor)
                ↓
10. S8: LLM generates tooltips per call
                ↓
11. S9: LLM + rules generate normalized tags
                ↓
12. S10: Score confidence, flag for review if LOW
                ↓
13. Write to PostgreSQL + Search Index
                ↓
14. If HIGH confidence: Auto-publish to Allocator Pro
    If MEDIUM: Add to spot-check queue
    If LOW: Add to must-review queue
```

---

## Scaling Considerations (2,000–3,000 PDFs/month)

### Throughput Math

- 3,000 PDFs/month ≈ 100 PDFs/day
- Average processing time per PDF: 2–5 minutes
- Single worker throughput: ~200–400 PDFs/day
- **Comfortable headroom with 2–3 workers**

### Queue Architecture

```
┌─────────────┐     ┌──────────────┐     ┌─────────────┐
│ pdf_ingested│ ──► │ pdf_extracted│ ──► │ pdf_indexed │
└─────────────┘     └──────────────┘     └─────────────┘
                           │
                           ▼
                    ┌──────────────┐     ┌─────────────┐
                    │ llm_processed│ ──► │ pdf_complete│
                    └──────────────┘     └─────────────┘
```

- Use message queue (SQS/PubSub/Redis Streams)
- Stateless workers, horizontal scaling
- Idempotent stages (re-run safe on failure)

### Cost Controls

1. **Selective OCR:** Only run on pages with low text coverage
2. **Retrieve-then-read:** Never send full documents to LLM
3. **Cache embeddings:** By document hash
4. **Batch similar operations:** Where possible without breaking per-PDF isolation

---

## MVP Infrastructure

### Local Development
- **Database:** SQLite (`pipeline.db`) — upgrade to PostgreSQL when needed
- **Blob storage:** Local filesystem (`./data/pdfs/`)
- **Vector index:** In-memory FAISS or ChromaDB (persisted to disk)
- **Embeddings:** OpenAI `text-embedding-3-small` or local `all-MiniLM-L6-v2`

### Optional GCP Instance (2 vCPU, 6GB RAM, 22GB storage)
- PostgreSQL 15 (containerized, ~500MB RAM)
- ChromaDB for embeddings (~1GB for 1000 docs)
- PDF storage: ~10MB/PDF × 500 PDFs = 5GB
- Headroom for processing: ~3-4GB

### Cost Optimization
- Use Claude Haiku for simple stages (S5, S8, S9)
- Cache embeddings by file hash
- Keep **selective OCR** in MVP (capped per document); use vision only for flagged chart/heatmap/table pages

---

## Security & Compliance

- **Data at rest:** Encrypted blob storage, encrypted database
- **Data in transit:** TLS everywhere
- **Access control:** Role-based (analyst, admin, API consumer)
- **Audit logging:** All extractions, edits, and reviews logged with timestamp + user
- **Retention:** Raw PDFs retained per client policy; processed data subject to TTL

---

## Monitoring & Observability

### Key Metrics

**Pipeline Health:**
- Throughput: PDFs processed/hour
- Latency: P50/P95 processing time per stage
- Error rate: Failed extractions by stage
- Queue depth: Pending PDFs

**Quality:**
- Extraction coverage: % pages with usable text
- Confidence distribution: % HIGH/MEDIUM/LOW
- Review queue size
- Analyst correction rate (% of reviewed items changed)

**Cost:**
- LLM tokens consumed/PDF
- OCR pages processed
- Storage usage

### Alerting Thresholds

| Metric | Warning | Critical |
|--------|---------|----------|
| Error rate | >5% | >15% |
| Queue depth | >500 | >1000 |
| P95 latency | >10 min | >30 min |
| LOW confidence rate | >30% | >50% |
