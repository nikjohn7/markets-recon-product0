# Implementation Tasks

Sequential tasks for building the Markets Recon Document Intelligence Pipeline. Complete one task at a time in order.

This task list targets the **MVP (v0)** described in `CLAUDE.md`. Anything explicitly labeled **v1+ / deferred** should be skipped for MVP unless you are intentionally expanding scope.

---

## Phase 0: Spec Alignment (Hard Choices)

### Task 0.1: Resolve Spec Gaps and Contradictions
Make the minimum clarifying decisions required for an agent to implement without guessing.

**Deliverables:**
- Add a short `docs/DECISIONS.md` capturing MVP choices (libraries, versions, interfaces)
- Align `tasks.md` vs `CLAUDE.md` scope conflicts (e.g., verification pass is v1+ per `CLAUDE.md`)
- Clarify where pipeline stage I/O models live (recommended: `src/models/pipeline.py`)
- Clarify the missing `Section` model referenced by `CleanedDocument` in `docs/PIPELINE.md` (either define it there or explicitly define it in code and mirror into docs)

**Acceptance:** A new contributor can follow `tasks.md` without needing to infer major architectural choices or missing types

---

### Task 0.2: Pin MVP Tech Decisions
Reduce “choose one” ambiguity so an agent doesn’t fork the architecture.

**Deliverables (MVP defaults):**
- **Pydantic v2** (+ `pydantic-settings`) for settings/models
- **SQLite** for persistence (schema designed to be Postgres-portable later)
- **Embeddings provider:** pick one for MVP (OpenAI or local) and write it into `docs/DECISIONS.md`
- **DB access:** pick one (SQLAlchemy Core recommended, or raw SQL) and write it into `docs/DECISIONS.md`
- **Logging:** standard `logging` with JSON option; define what gets redacted (API keys, full prompts, full document text)

**Acceptance:** There are no remaining “SQLAlchemy or raw SQL / OpenAI or local” decisions left implicit for MVP implementation

---

## Phase 1: Project Foundation

### Task 1.1: Initialize Python Project Structure
Create the base project structure with `pyproject.toml`, `requirements.txt`, and directory scaffolding.

**Deliverables:**
- `pyproject.toml` with project metadata, Python 3.11+ requirement
- `requirements.txt` with core dependencies (per Phase 0 decisions), including at minimum: pydantic, pydantic-settings, anthropic, pymupdf, pdfplumber, chromadb, openai, pytest, mypy, ruff
- Empty `__init__.py` files in all package directories per CLAUDE.md directory structure
- `.env.example` with required environment variables
- `.gitignore` that excludes runtime artifacts (`.env`, `data/`, caches, `__pycache__/`)

**Acceptance:** `pip install -e .` succeeds, `mypy src/ --strict` runs (even if empty)

---

### Task 1.2: Create Core Enums
Implement all enums from SCHEMAS.md in `src/models/enums.py`.

**Deliverables:**
- `CallDirection`, `Conviction`, `Sentiment`, `DocumentType`, `BlockType`, `ConfidenceBand`, `DocumentStatus`, `TagType`, `IndicatorDirection` enums
- All enums inherit from `(str, Enum)` for JSON serialization

**Acceptance:** All enums importable, `mypy` passes

---

### Task 1.3: Create Citation and BoundingBox Models
Implement the universal Citation model and BoundingBox model.

**Deliverables:**
- `src/models/core.py` with `Citation` and `BoundingBox` Pydantic models
- Citation is frozen (immutable)
- Field validations per SCHEMAS.md

**Acceptance:** Unit tests for validation edge cases pass

---

### Task 1.4: Create Document Extraction Models
Implement DocumentBlock, ExtractedTable, and DocumentJSON models.

**Deliverables:**
- `src/models/document.py` with `DocumentBlock`, `TableCell`, `ExtractedTable`, `DocumentJSON`
- Proper field constraints (page >= 1, confidence 0-1, etc.)

**Acceptance:** Can create valid DocumentJSON instances, validation rejects invalid data

---

### Task 1.5: Create DocumentProfile Model (Stage 4 Output)
Implement the metadata extraction output model.

**Deliverables:**
- `src/models/profile.py` with `DocumentProfile`
- Includes uncertainty flags (`manager_name_uncertain`, `publication_date_uncertain`)
- Requires at least 1 citation

**Acceptance:** Validation enforces min_length=1 for manager_name and citations

---

### Task 1.6: Create Allocation Call Models (Stage 6 Output)
Implement AllocationCall, KeyIndicator, and CallExtractionOutput models.

**Deliverables:**
- `src/models/calls.py` with `KeyIndicator`, `AllocationCall`, `CallExtractionOutput`
- Custom validator ensuring rationale_bullets are non-empty strings
- Proper constraints: rationale 1-4 items, tooltip <=150 chars, citations 1-3 items

**Acceptance:** Rejects empty rationale bullets, empty citations, confidence > 1

---

### Task 1.7: Create Summary Models (Stage 7 Output)
Implement KeyTakeaway and DocumentSummaries models.

**Deliverables:**
- `src/models/summaries.py` with `KeyTakeaway`, `DocumentSummaries`
- Word/character limits enforced

**Acceptance:** Validates executive_summary length, requires citations on takeaways

---

### Task 1.8: Create Tag Models (Stage 9 Output)
Implement Tag and TagSet models.

**Deliverables:**
- `src/models/tags.py` with `Tag`, `TagSet`

**Acceptance:** All tag categories represented, confidence in 0-1 range

---

### Task 1.9: Create Confidence Models (Stage 10 Output)
Implement FieldConfidence and ConfidenceResult models.

**Deliverables:**
- `src/models/confidence.py` with `FieldConfidence`, `ConfidenceResult`
- Band computation based on thresholds

**Acceptance:** Confidence band correctly assigned per thresholds (HIGH >= 0.80, LOW < 0.60)

---

### Task 1.10: Create ProcessedDocument Model (Final Output)
Implement the complete pipeline output model with helper methods.

**Deliverables:**
- `src/models/output.py` with `ProcessedDocument`
- Implement `to_allocator_pro_calls()` method
- Implement `to_search_document()` method

**Acceptance:** Can serialize to JSON, helper methods return expected structure

---

### Task 1.11: Create Pipeline Stage I/O Models (From PIPELINE.md)
Implement the stage interface models used by the pipeline (so stages don’t pass raw dicts).

**Deliverables:**
- `src/models/pipeline.py` with Pydantic models matching `docs/PIPELINE.md`:
  - `IngestResult`
  - `RetrievedChunk`
  - `CandidateSet`
  - `CleanedDocument`
- A concrete `Section` model (or equivalent) used by `CleanedDocument.sections`, with an explicit definition captured in `docs/DECISIONS.md` (and ideally mirrored into `docs/PIPELINE.md`)

**Acceptance:** Stage modules can type their inputs/outputs without using `dict`/`Any`, and unit tests cover basic validation (e.g., required IDs, non-empty candidates when present)

---

## Phase 2: Taxonomy System

### Task 2.1: Implement Asset Class Hierarchy
Create the taxonomy hierarchy structure from TAXONOMY.md.

**Deliverables:**
- `src/taxonomy/hierarchy.py` with category codes and sub-asset mappings
- Data structure: `CATEGORIES: dict[str, list[str]]` mapping category to sub-assets
- Display name mappings

**Acceptance:** All categories from TAXONOMY.md present, can look up category for any sub-asset

---

### Task 2.2: Implement Synonym Resolution
Create synonym mapping and resolution logic.

**Deliverables:**
- `src/taxonomy/synonyms.py` with `SYNONYMS` dict and `resolve_asset()` function
- Case-insensitive matching
- Returns `(category_code, sub_asset_code)` or `None`

**Acceptance:** "bunds" resolves to ("FI_SOV_EUROPE", "GERMAN_BUNDS"), unknown terms return None

---

### Task 2.3: Implement Tag Vocabularies
Create allowed tag value lists from TAXONOMY.md.

**Deliverables:**
- `src/taxonomy/tags.py` with `THEME_TAGS`, `RISK_TAGS`, `REGION_TAGS`, `MACRO_REGIME_TAGS` lists
- Validation function `is_valid_tag(tag_type, value) -> bool`

**Acceptance:** All tags from TAXONOMY.md present, validation works correctly

---

## Phase 3: Infrastructure Layer

### Task 3.1: Create Configuration System
Implement settings management.

**Deliverables:**
- `src/config/settings.py` with Pydantic Settings class
- Load from environment variables
- Settings for: DATABASE_URL, BLOB_STORAGE_PATH, ANTHROPIC_API_KEY, OPENAI_API_KEY, LOG_LEVEL

**Acceptance:** Settings load from .env file, required fields raise error if missing

---

### Task 3.2: Create Logging Configuration
Set up structured logging.

**Deliverables:**
- `src/config/logging.py` with logging setup
- JSON-formatted logs for production
- Console output for development
- Redaction rules for secrets and oversized payloads (API keys, full prompts, full document text); allow opt-in verbose logging via `LOG_LEVEL=DEBUG`

**Acceptance:** Logs include timestamp, level, module, message

---

### Task 3.3: Create Exception Hierarchy
Define domain-specific exceptions.

**Deliverables:**
- `src/exceptions.py` with exception classes:
  - `PipelineError` (base)
  - `ExtractionError`, `WeakEvidenceError`, `TaxonomyMappingError`
  - `ValidationError`, `LLMError`, `StorageError`

**Acceptance:** All exceptions properly inherit, can be caught by base class

---

### Task 3.4: Implement Local Blob Storage
Create file-based blob storage for MVP.

**Deliverables:**
- `src/storage/blob.py` with `LocalBlobStorage` class
- Methods: `store(content: bytes, metadata: dict) -> str`, `retrieve(blob_id: str) -> bytes`
- Store in `./data/pdfs/` directory

**Acceptance:** Can store and retrieve PDF bytes, blob_id is deterministic (hash-based)

---

### Task 3.5: Implement SQLite Database Layer
Create SQLite storage for MVP (PostgreSQL-compatible schema).

**Deliverables:**
- `src/storage/database.py` with SQLite connection and table creation
- Tables: `managers`, `documents`, `allocation_calls`, `summaries`, `document_tags`, `evidence_blocks`
- A `pipeline_runs` (or equivalent) table capturing run metadata: pipeline version, start/end timestamps, total runtime, and (at minimum) the LLM model/provider used for the run
- Use SQLAlchemy or raw SQL with type safety

**Acceptance:** Tables created on init, can insert and query documents

---

## Phase 4: PDF Extraction (Stages 0-3)

### Task 4.1: Implement Stage 0 - Ingest
Create PDF ingestion with deduplication.

**Deliverables:**
- `src/pipeline/stages/s0_ingest.py` with `stage_ingest()` function
- Compute SHA-256 hash, check for duplicates
- Store PDF in blob storage, create document record
- Return `IngestResult` model

**Acceptance:** Same PDF returns same document_id (idempotent), new PDF creates new record

---

### Task 4.2: Implement Stage 1 - Text Extraction
Extract text and layout from PDF using PyMuPDF/pdfplumber.

**Deliverables:**
- `src/extraction/parser.py` with PDF parsing logic
- `src/pipeline/stages/s1_extract.py` with `stage_extract()` function
- Detect block types (heading, paragraph, bullet, table)
- Compute extraction_coverage

**Acceptance:** Extracts text from clean PDFs, coverage computed correctly; add at least one deterministic test PDF fixture (or programmatically generated PDF) where expected `extraction_coverage` is asserted

---

### Task 4.3: Implement Table Extraction
Extract structured tables from PDFs.

**Deliverables:**
- Add table extraction to `src/extraction/parser.py`
- Create `ExtractedTable` instances with cell positions
- Detect headers

**Acceptance:** Tables detected and cells extracted with row/col positions

---

### Task 4.4: Implement Stage 2 - Cleaning
Clean extracted text and detect sections.

**Deliverables:**
- `src/pipeline/stages/s2_clean.py` with `stage_clean()` function
- Remove repeated headers/footers
- Detect disclaimer blocks
- Normalize text (fix hyphenation, whitespace)
- Detect section boundaries

**Acceptance:** Boilerplate removed, sections identified, output is `CleanedDocument`

---

### Task 4.5: Implement Stage 3 - Retrieval Index
Build per-document vector index.

**Deliverables:**
- `src/retrieval/indexer.py` with chunking and embedding logic
- `src/pipeline/stages/s3_index.py` with `stage_index()` function
- Use OpenAI embeddings or local model (configurable)
- ChromaDB for in-memory vector storage

**Acceptance:** Can query index and retrieve relevant chunks with scores

---

## Phase 5: LLM Interaction Layer

### Task 5.1: Create LLM Client Wrapper
Implement Claude API client with retry logic.

**Deliverables:**
- `src/llm/client.py` with `LLMClient` class
- Support for Claude 3.5 Sonnet and Haiku
- JSON output mode
- Retry with exponential backoff on rate limits
- Token counting
- Safe logging: never log raw API keys; do not log full prompts/responses by default (log hashes + sizes, and optionally truncated previews in DEBUG)

**Acceptance:** Can call Claude API, returns validated JSON

---

### Task 5.2: Create Prompt Templates
Implement all prompt templates from LLM_CONTRACTS.md.

**Deliverables:**
- `src/llm/prompts/metadata.py` - Stage 4 prompt
- `src/llm/prompts/calls.py` - Stage 6 prompt
- `src/llm/prompts/summaries.py` - Stage 7 prompt
- `src/llm/prompts/tooltips.py` - Stage 8 prompt
- `src/llm/prompts/tags.py` - Stage 9 prompt
- `src/llm/prompts/verification.py` - Verification pass prompt

**Acceptance:** All prompts include schema, rules, and guardrails from LLM_CONTRACTS.md

---

### Task 5.3: Create LLM Output Validation
Implement output validation and guardrails.

**Deliverables:**
- `src/llm/contracts.py` with validation functions
- Citation verification (chunk_ids exist)
- Taxonomy verification
- Hallucination detection (dates/percentages not in source)

**Acceptance:** Invalid citations rejected, unmapped taxonomy flagged, hallucination patterns detected

---

## Phase 6: LLM Pipeline Stages (Stages 4-9)

### Task 6.1: Implement Stage 4 - Metadata Extraction
Extract document metadata using LLM.

**Deliverables:**
- `src/pipeline/stages/s4_metadata.py` with `stage_metadata()` function
- Retrieve likely metadata sections (first 2 pages, headers)
- Call LLM with metadata prompt
- Validate and return `DocumentProfile`

**Acceptance:** Extracts manager_name, document_type, handles missing fields with uncertainty flags

---

### Task 6.2: Implement Stage 5 - Candidate Retrieval
Identify signal-containing passages.

**Deliverables:**
- `src/pipeline/stages/s5_candidates.py` with `stage_candidates()` function
- Keyword mining: overweight, underweight, neutral, prefer, avoid, etc.
- Retrieval expansion via embeddings
- Return `CandidateSet`

**Acceptance:** Returns at least 3 candidate chunks for typical outlook documents

---

### Task 6.3: Implement Stage 6 - Call Extraction (Core)
Extract allocation calls with taxonomy mapping.

**Deliverables:**
- `src/pipeline/stages/s6_calls.py` with `stage_calls()` function
- Asset mention detection
- Call classification (OW/N/UW/UNCERTAIN)
- Rationale extraction
- Sentiment extraction
- Return `CallExtractionOutput`

**Acceptance:** All calls have valid taxonomy, citations, non-empty rationale

---

### Task 6.4: Implement Stage 6 - Verification Pass (v1+ Deferred)
Add a verification pass for high-stakes extractions. **Skip for MVP** per `CLAUDE.md`.

**Deliverables:**
- Add verification logic to `s6_calls.py`
- Re-run extraction with different prompt
- Compare call directions
- Flag disagreements

**Acceptance:** Verification pass runs, agreement rate computed

---

### Task 6.5: Implement Stage 7 - Summary Generation
Generate executive summary and key takeaways.

**Deliverables:**
- `src/pipeline/stages/s7_summaries.py` with `stage_summaries()` function
- Executive summary (120-180 words)
- Search descriptor (20-35 words)
- Key takeaways (3-5 bullets with citations)

**Acceptance:** Word counts within bounds, all takeaways have citations

---

### Task 6.6: Implement Stage 8 - Tooltip Generation
Generate hover text for each call.

**Deliverables:**
- `src/pipeline/stages/s8_tooltips.py` with `stage_tooltips()` function
- Generate <= 25 word tooltips
- Specific to call rationale (not generic)

**Acceptance:** All calls have tooltip_text populated, <= 150 characters

---

### Task 6.7: Implement Stage 9 - Tag Generation
Generate normalized tags.

**Deliverables:**
- `src/pipeline/stages/s9_tags.py` with `stage_tags()` function
- Deterministic tags from taxonomy (asset_class, region)
- LLM tags for themes, risks, macro regime
- Normalize to allowed vocabulary

**Acceptance:** At least 5 tags total, all tags in allowed vocabularies

---

## Phase 7: Confidence & Validation (Stage 10)

### Task 7.1: Implement Extraction Quality Scoring
Score PDF extraction quality.

**Deliverables:**
- `src/pipeline/stages/s10_confidence.py` with scoring functions
- Text coverage scoring
- OCR quality scoring (if applicable)
- Table extraction success
- Block structure quality

**Acceptance:** Score in 0-1 range, weights per CONFIDENCE.md

---

### Task 7.2: Implement Evidence Strength Scoring
Score evidence support for claims.

**Deliverables:**
- Add evidence scoring to `s10_confidence.py`
- Explicit mention detection
- Semantic similarity scoring
- Entailment scoring

**Acceptance:** Explicit "overweight" language yields high score, missing evidence yields low

---

### Task 7.3: Implement Document-Level Confidence
Aggregate component scores into overall confidence.

**Deliverables:**
- Complete `stage_confidence()` function
- Weighted aggregation per CONFIDENCE.md
- Band assignment (HIGH/MEDIUM/LOW)
- Attention flagging logic

**Acceptance:** Overall confidence computed, band assigned correctly, attention flags set

---

### Task 7.4: Implement Review Routing
Route documents based on confidence.

**Deliverables:**
- Add routing logic to confidence module
- Auto-publish criteria (HIGH + no flags)
- Spot-check sampling (20% of MEDIUM)
- Must-review queue (LOW)

**Acceptance:** Documents routed correctly based on confidence band

---

## Phase 8: Pipeline Orchestration

### Task 8.1: Create Pipeline Orchestrator
Implement the main pipeline runner.

**Deliverables:**
- `src/pipeline/run.py` with `process_pdf()` async function
- Execute stages 0-10 in sequence
- Handle stage failures gracefully
- Persist results to database
- Return `ProcessedDocument`

**Acceptance:** Full pipeline runs on clean PDF, outputs valid ProcessedDocument

---

### Task 8.2: Create CLI Interface
Implement command-line interface.

**Deliverables:**
- Update `src/pipeline/run.py` with CLI using argparse or click
- `python -m pipeline.run --pdf <path>` runs full pipeline
- `python -m pipeline.stages.<stage> --pdf <path>` runs single stage
- JSON output to stdout or file

**Acceptance:** CLI commands work as documented in CLAUDE.md

---

### Task 8.3: Create Output Validator
Implement output validation utility.

**Deliverables:**
- `src/pipeline/validate.py` with validation logic
- `python -m pipeline.validate --output <json>` validates output file
- Check schema compliance, citation validity, taxonomy codes

**Acceptance:** Validates correct outputs, reports issues on invalid outputs

---

## Phase 9: Testing

### Task 9.1: Create Test Fixtures
Set up test infrastructure.

**Deliverables:**
- `tests/conftest.py` with pytest fixtures
- `tests/fixtures/` directory structure
- Mock LLM responses per TESTING.md
- Deterministic PDF fixtures: either committed small PDFs or programmatically generated PDFs (recommended: generate via PyMuPDF during tests to avoid binary fixtures)

**Acceptance:** Fixtures load correctly, mock LLM returns expected data

---

### Task 9.2: Write Model Unit Tests
Test all Pydantic model validations.

**Deliverables:**
- `tests/unit/models/` test files for each model module
- Test valid construction
- Test rejection of invalid data
- Test edge cases (empty lists, boundary values)

**Acceptance:** >= 80% coverage on models, all edge cases from TESTING.md covered

---

### Task 9.3: Write Taxonomy Unit Tests
Test taxonomy resolution.

**Deliverables:**
- `tests/unit/taxonomy/test_hierarchy.py`
- `tests/unit/taxonomy/test_synonyms.py`
- Test all synonym resolutions
- Test unknown term handling

**Acceptance:** All synonyms from TAXONOMY.md resolve correctly

---

### Task 9.4: Write Stage Integration Tests
Test each pipeline stage.

**Deliverables:**
- `tests/integration/test_stage_*.py` for each stage
- Use mock LLM for LLM stages
- Test input/output contracts

**Acceptance:** Each stage passes with valid input, fails gracefully on invalid

---

### Task 9.5: Write E2E Pipeline Tests
Test full pipeline with sample PDFs.

**Deliverables:**
- `tests/e2e/test_full_pipeline.py`
- Golden output tests
- Edge case handling (no calls, low quality)

**Acceptance:** Pipeline completes on test PDFs, output structure matches golden

---

### Task 9.6: Write Confidence Scoring Tests
Test confidence calibration.

**Deliverables:**
- `tests/unit/test_confidence.py`
- Test threshold boundaries
- Test component scoring

**Acceptance:** Confidence bands assigned correctly at boundary values

---

## Phase 10: Polish & Documentation

### Task 10.1: Add Type Annotations Check
Ensure full type coverage.

**Deliverables:**
- Run `mypy src/ --strict` and fix all errors
- No `Any` types unless absolutely necessary

**Acceptance:** `mypy src/ --strict` passes with zero errors

---

### Task 10.2: Add Linting and Formatting
Set up code quality tools.

**Deliverables:**
- `ruff.toml` configuration
- Run `ruff check src/ tests/` and fix issues
- Run `ruff format src/ tests/`

**Acceptance:** `ruff check` passes, code is formatted

---

### Task 10.3: Create Sample Run Script
Provide example usage.

**Deliverables:**
- `scripts/run_sample.py` demonstrating full pipeline
- Include logging output
- Show how to inspect results

**Acceptance:** Script runs successfully with sample PDF

---

### Task 10.4: Final Integration Test
Verify complete system.

**Deliverables:**
- Run full pipeline on 3-5 real PDFs
- Verify outputs manually
- Document any issues found
- Prefer a repeatable evaluation command (script) that prints MVP success metrics from `CLAUDE.md`

**Acceptance:** >= 90% of test PDFs process without crash, >= 3 calls extracted per PDF

---

### Task 10.5: Add MVP Evaluation Script
Make it easy for an agent (and you) to measure “done” against MVP success metrics.

**Deliverables:**
- `scripts/eval_mvp.py` (or similar) that runs the pipeline on a folder of PDFs and prints:
  - crash rate
  - calls extracted per PDF (avg)
  - % calls with citations present
  - processing time per PDF (p50/p95)
- Output a short machine-readable summary (JSON) alongside console output

**Acceptance:** Running the script on the evaluation set produces the metrics table referenced in `CLAUDE.md` without manual calculation

---

## Phase 11: Performance & Cost Controls

### Task 11.1: Add Page Triage Tasks
Add a lightweight, heuristic page triage step to reduce chunking/embedding work on large clean PDFs.

**Deliverables:**
- Add Phase 11 tasks to `tasks.md` and `PROGRESS.md`
- Define defaults and constraints (max pages, guardrails)

**Acceptance:** Phase 11 tasks are tracked in `PROGRESS.md` and ready for sequential execution

---

### Task 11.2: Implement Page Scoring (Stage 2)
Compute a cheap per-page score from extracted text/layout signals (no embeddings, no API calls).

**Deliverables:**
- Page scoring utilities in `src/pipeline/stages/s2_clean.py`:
  - signal keyword counts/density
  - high-value header detection (e.g., Executive Summary / Outlook / Allocation)
  - structural signals (bullets, tables)
  - light position prior (front + mid-doc boost)
- Reason codes available for logging/debugging

**Acceptance:** Unit tests verify scoring features and deterministic ordering on a synthetic document

---

### Task 11.3: Implement Page Filtering (Stage 2)
Filter pages before section detection and downstream chunking/embedding, using guardrails and a hard cap.

**Deliverables:**
- Keep rules:
  - always keep first 5 pages
  - always keep pages with strong signal (>=3 unique signal keywords)
  - always keep pages with high-value headers (Outlook/Allocation/etc.)
  - keep neighbors (±1) of kept pages for context
- Cap selected pages at 40 (configurable)
- Only apply triage when document page_count exceeds a minimum threshold (configurable)

**Acceptance:** Stage 2 integration tests confirm large documents are reduced while small docs remain unchanged

---

### Task 11.4: Add Tests for Page Triage Behavior
Add unit and integration tests that cover page selection guardrails and edge cases.

**Deliverables:**
- Unit tests for selection behavior (caps, must-keep, neighbor expansion)
- Integration test that ensures Stage 3 receives fewer pages/chunks for large inputs

**Acceptance:** `pytest tests/` passes and triage behavior is covered by tests

---

### Task 11.5: Document Triage Defaults and Logging
Make it easy to inspect triage outcomes and tune defaults from real PDFs.

**Deliverables:**
- Update `docs/PIPELINE.md` Stage 2 to describe triage sub-steps and defaults
- Add Stage 2 logs: pages kept/total, top reasons, and cap/threshold settings

**Acceptance:** Running on a sample PDF produces clear logs explaining which pages were kept and why

---

## Task Dependencies

```
Phase 0 (Spec Alignment) → Phase 1 (Foundation) → Phase 2 (Taxonomy) → Phase 3 (Infrastructure)
                                                    ↓
                        Phase 4 (PDF Extraction) ← ─┘
                                    ↓
                        Phase 5 (LLM Layer)
                                    ↓
                        Phase 6 (LLM Stages)
                                    ↓
                        Phase 7 (Confidence)
                                    ↓
                        Phase 8 (Orchestration)
                                    ↓
                        Phase 9 (Testing)
                                    ↓
                        Phase 10 (Polish)
                                    ↓
                        Phase 11 (Performance)
```

---

## Quick Reference

| Phase | Tasks | Focus Area |
|-------|-------|------------|
| 0 | 0.1-0.2 | Decisions, spec alignment |
| 1 | 1.1-1.11 | Pydantic models, project setup |
| 2 | 2.1-2.3 | Asset taxonomy system |
| 3 | 3.1-3.5 | Config, storage, exceptions |
| 4 | 4.1-4.5 | PDF parsing, indexing |
| 5 | 5.1-5.3 | LLM client, prompts, validation |
| 6 | 6.1-6.7 | LLM pipeline stages |
| 7 | 7.1-7.4 | Confidence scoring, routing |
| 8 | 8.1-8.3 | Pipeline orchestration, CLI |
| 9 | 9.1-9.6 | Tests |
| 10 | 10.1-10.5 | Type checking, linting, polish |
| 11 | 11.1-11.5 | Page triage, cost controls |
