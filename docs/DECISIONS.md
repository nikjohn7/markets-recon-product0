# MVP Decisions

Architectural and technology decisions for MVP (v0). This document resolves ambiguities in the spec so implementers don't need to guess.

---

## Technology Stack (MVP)

| Component | Decision | Notes |
|-----------|----------|-------|
| Python | 3.11+ | Required for modern typing features |
| Models/Settings | Pydantic v2 + pydantic-settings | All data structures |
| Database | SQLite | Schema designed for Postgres portability |
| DB Access | SQLAlchemy Core | Type-safe, no ORM overhead |
| Embeddings | OpenAI `text-embedding-3-small` | Simplest for MVP; local model deferred |
| Vector Store | ChromaDB (in-memory) | Per-document index, ephemeral |
| LLM | Claude 3.5 Sonnet (primary), Haiku (fallback) | Via Anthropic API |
| PDF Extraction | PyMuPDF + pdfplumber | Clean PDFs only for MVP |
| Logging | Python `logging` with JSON formatter | Redact API keys, truncate large payloads |

---

## Scope Alignment

### Deferred to v1+
Per `CLAUDE.md`, these are explicitly **out of scope** for MVP:

- OCR for scanned PDFs (Stage 1 OCR paths)
- Vision for charts/heatmaps (Stage 1 vision paths)
- Verification pass (Task 6.4 / Stage 6.4)
- Review UI
- Search index (OpenSearch/Elasticsearch)
- Queue-based batch processing

### MVP Simplifications
- Stage 1: Text extraction only (skip OCR decision, vision decision)
- Stage 6: Single-pass extraction only (no verification pass)
- Stage 10: No cross-pass agreement scoring (since no verification)

---

## Model Locations

| Model Type | Location | Purpose |
|------------|----------|---------|
| Core enums | `src/models/enums.py` | Shared enums |
| Core models | `src/models/core.py` | Citation, BoundingBox |
| Document models | `src/models/document.py` | DocumentBlock, ExtractedTable, DocumentJSON |
| Profile models | `src/models/profile.py` | DocumentProfile (Stage 4 output) |
| Call models | `src/models/calls.py` | AllocationCall, CallExtractionOutput (Stage 6 output) |
| Summary models | `src/models/summaries.py` | DocumentSummaries (Stage 7 output) |
| Tag models | `src/models/tags.py` | Tag, TagSet (Stage 9 output) |
| Confidence models | `src/models/confidence.py` | ConfidenceResult (Stage 10 output) |
| Output models | `src/models/output.py` | ProcessedDocument (final output) |
| **Pipeline I/O** | `src/models/pipeline.py` | Stage interface models (IngestResult, CleanedDocument, CandidateSet, RetrievedChunk, Section) |

---

## Missing Type Definitions

### Section Model

Referenced by `CleanedDocument.sections` in `docs/PIPELINE.md` but not defined. Definition:

```python
class Section(BaseModel):
    """A detected section within a document."""
    section_id: str  # Unique identifier (e.g., "{doc_id}_sec_{index}")
    title: str | None  # Section heading text, if detected
    start_block_id: str  # First block in section
    end_block_id: str  # Last block in section
    section_type: str | None  # Optional classification: "macro", "equities", "fixed_income", "risks", "appendix", "other"
```

This model lives in `src/models/pipeline.py`.

### RetrievalIndex

`RetrievalIndex` in `docs/PIPELINE.md` is a Protocol (interface), not a Pydantic model. Implementation lives in `src/retrieval/indexer.py`.

---

## Database Schema Notes

SQLite schema must be Postgres-portable:
- Use `TEXT` instead of `VARCHAR` (SQLite ignores length)
- Use `INTEGER PRIMARY KEY` for auto-increment (maps to `SERIAL` in Postgres)
- Avoid SQLite-specific features (e.g., `ROWID` tricks)
- Store JSON as `TEXT` with application-level serialization

---

## Logging Redaction Rules

**Always redact:**
- API keys (ANTHROPIC_API_KEY, OPENAI_API_KEY)
- Full prompt text (log hash + token count instead)
- Full LLM responses (log hash + size instead)
- Full document text

**Allowed in DEBUG mode:**
- Truncated prompt previews (first 200 chars)
- Truncated response previews (first 200 chars)

---

## Open Questions (Resolved)

| Question | Decision |
|----------|----------|
| SQLAlchemy or raw SQL? | SQLAlchemy Core |
| OpenAI or local embeddings? | OpenAI for MVP |
| Where do pipeline I/O models live? | `src/models/pipeline.py` |
| What is the Section model? | Defined above |

---

**Last Updated:** 2025-12-16
