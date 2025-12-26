---
progress_format_version: 2
scope: "MVP (v0)"
execution_mode: "sequential"
deferred_tasks:
  - "6.4"
---

# Markets Recon Pipeline — Progress

This file is a minimal execution log for `tasks.md`.

## How To Update (Keep Diffs Small)

After finishing a task:
1. Change exactly one checkbox from `[ ]` → `[x]` in **Task Checklist**.
2. Append a short entry under **Task Notes** with key files changed.

Do **not** maintain derived dashboards here (totals, percentages, per-phase progress, “blocked/available” lists). In sequential mode, the *current task* is simply the first unchecked item.

## Deferred (v1+)

- `6.4` Stage 6 verification pass (explicitly deferred in `tasks.md` / `CLAUDE.md`)

## Task Checklist (Source Of Truth)

### Phase 0: Spec Alignment
- [x] `0.1` Resolve Spec Gaps and Contradictions
- [x] `0.2` Pin MVP Tech Decisions

### Phase 1: Project Foundation
- [x] `1.1` Initialize Python Project Structure
- [x] `1.2` Create Core Enums
- [x] `1.3` Create Citation and BoundingBox Models
- [x] `1.4` Create Document Extraction Models
- [x] `1.5` Create DocumentProfile Model (Stage 4 Output)
- [x] `1.6` Create Allocation Call Models (Stage 6 Output)
- [x] `1.7` Create Summary Models (Stage 7 Output)
- [x] `1.8` Create Tag Models (Stage 9 Output)
- [x] `1.9` Create Confidence Models (Stage 10 Output)
- [x] `1.10` Create ProcessedDocument Model (Final Output)
- [x] `1.11` Create Pipeline Stage I/O Models (From PIPELINE.md)

### Phase 2: Taxonomy System
- [x] `2.1` Implement Asset Class Hierarchy
- [x] `2.2` Implement Synonym Resolution
- [x] `2.3` Implement Tag Vocabularies

### Phase 3: Infrastructure Layer
- [x] `3.1` Create Configuration System
- [x] `3.2` Create Logging Configuration
- [x] `3.3` Create Exception Hierarchy
- [x] `3.4` Implement Local Blob Storage
- [x] `3.5` Implement SQLite Database Layer

### Phase 4: PDF Extraction (Stages 0–3)
- [x] `4.1` Implement Stage 0 - Ingest
- [x] `4.2` Implement Stage 1 - Text Extraction
- [x] `4.3` Implement Table Extraction
- [x] `4.4` Implement Stage 2 - Cleaning
- [x] `4.5` Implement Stage 3 - Retrieval Index

### Phase 5: LLM Interaction Layer
- [x] `5.1` Create LLM Client Wrapper
- [x] `5.2` Create Prompt Templates
- [x] `5.3` Create LLM Output Validation

### Phase 6: LLM Pipeline Stages (Stages 4–9)
- [x] `6.1` Implement Stage 4 - Metadata Extraction
- [x] `6.2` Implement Stage 5 - Candidate Retrieval
- [x] `6.3` Implement Stage 6 - Call Extraction (Core)
- [ ] `6.4` Implement Stage 6 - Verification Pass (v1+ deferred)
- [x] `6.5` Implement Stage 7 - Summary Generation
- [x] `6.6` Implement Stage 8 - Tooltip Generation
- [x] `6.7` Implement Stage 9 - Tag Generation

### Phase 7: Confidence & Validation (Stage 10)
- [x] `7.1` Implement Extraction Quality Scoring
- [x] `7.2` Implement Evidence Strength Scoring
- [x] `7.3` Implement Document-Level Confidence
- [x] `7.4` Implement Review Routing

### Phase 8: Pipeline Orchestration
- [x] `8.1` Create Pipeline Orchestrator
- [x] `8.2` Create CLI Interface
- [x] `8.3` Create Output Validator

### Phase 9: Testing
- [x] `9.1` Create Test Fixtures
- [x] `9.2` Write Model Unit Tests
- [x] `9.3` Write Taxonomy Unit Tests
- [x] `9.4` Write Stage Integration Tests
- [x] `9.5` Write E2E Pipeline Tests
- [x] `9.6` Write Confidence Scoring Tests

### Phase 10: Polish & Documentation
- [ ] `10.1` Add Type Annotations Check
- [ ] `10.2` Add Linting and Formatting
- [ ] `10.3` Create Sample Run Script
- [ ] `10.4` Final Integration Test
- [ ] `10.5` Add MVP Evaluation Script

## Task Notes

### Task 0.1 — Complete (2025-12-16)
- Created `docs/DECISIONS.md` with MVP tech stack decisions
- Defined `Section` model for `CleanedDocument.sections`
- Clarified pipeline I/O models location: `src/models/pipeline.py`
- Documented scope alignment (verification pass deferred to v1+)
- Resolved all "choose one" ambiguities (SQLAlchemy Core, OpenAI embeddings)

### Task 0.2 — Complete (2025-12-17)
- Verified all deliverables already satisfied by Task 0.1 work in `docs/DECISIONS.md`
- Confirmed: Pydantic v2, SQLite, OpenAI embeddings, SQLAlchemy Core, logging redaction rules
- No additional changes required — `docs/DECISIONS.md` is comprehensive

### Task 1.1 — Complete (2025-12-17)
- Created `pyproject.toml` with Python 3.11+, Pydantic v2, all core dependencies
- Created `requirements.txt` with pinned versions
- Created full directory structure: `src/{pipeline,models,taxonomy,llm,extraction,retrieval,storage,config}`, `tests/{unit,integration,e2e,fixtures}`, `scripts/`, `data/`
- Added `__init__.py` files to all packages (11 source + 4 test packages)
- Created `.env.example` with DATABASE_URL, BLOB_STORAGE_PATH, API keys, LOG_LEVEL
- Updated `.gitignore` with project-specific exclusions (data/, chroma_data/, .ruff_cache/)
- Verified: `pip install -e ".[dev]"` succeeds, `mypy src/ --strict` passes

### Task 1.2 — Complete (2025-12-18)
- Created `src/models/enums.py` with all 9 enums from SCHEMAS.md
- Enums: `CallDirection`, `Conviction`, `Sentiment`, `DocumentType`, `BlockType`, `ConfidenceBand`, `DocumentStatus`, `TagType`, `IndicatorDirection`
- All enums inherit from `(str, Enum)` for JSON serialization
- Verified: all enums importable, `mypy --strict` passes

### Task 1.3 — Complete (2025-12-18)
- Created `src/models/core.py` with `Citation` and `BoundingBox` Pydantic models
- Citation is frozen (immutable), page >= 1, text_span <= 200 chars
- BoundingBox coordinates normalized 0-1
- Created `tests/unit/models/test_core.py` with 9 validation edge case tests
- Verified: all tests pass, `mypy --strict` passes

### Task 1.4 — Complete (2025-12-18)
- Created `src/models/document.py` with `DocumentBlock`, `TableCell`, `ExtractedTable`, `DocumentJSON`
- Field constraints: page >= 1, confidence 0-1, extraction_coverage 0-1
- Created `tests/unit/models/test_document.py` with 8 validation tests
- Verified: all tests pass, `mypy --strict` passes

### Task 1.5 — Complete (2025-12-18)
- Created `src/models/profile.py` with `DocumentProfile`
- Includes uncertainty flags, min_length=1 for manager_name and citations
- Created `tests/unit/models/test_profile.py` with 5 validation tests
- Verified: all tests pass, `mypy --strict` passes

### Task 1.6 — Complete (2025-12-18)
- Created `src/models/calls.py` with `KeyIndicator`, `AllocationCall`, `CallExtractionOutput`
- Validator for non-empty rationale_bullets, constraints: 1-4 bullets, 1-3 citations, tooltip ≤150 chars
- Created `tests/unit/models/test_calls.py` with 10 validation tests
- Verified: all tests pass, `mypy --strict` passes

### Task 1.7 — Complete (2025-12-18)
- Created `src/models/summaries.py` with `KeyTakeaway`, `DocumentSummaries`
- Constraints: executive_summary 100-1000 chars, search_descriptor 50-200 chars, 3-5 takeaways
- Created `tests/unit/models/test_summaries.py` with 8 validation tests
- Verified: all tests pass, `mypy --strict` passes

### Task 1.8 — Complete (2025-12-18)
- Created `src/models/tags.py` with `Tag`, `TagSet`
- All 7 tag categories represented, confidence 0-1 range
- Created `tests/unit/models/test_tags.py` with 5 validation tests
- Verified: all tests pass, `mypy --strict` passes

### Task 1.9 — Complete (2025-12-18)
- Created `src/models/confidence.py` with `FieldConfidence`, `ConfidenceResult`, `compute_confidence_band`
- Band validation: HIGH >= 0.80, MEDIUM 0.60-0.79, LOW < 0.60
- Created `tests/unit/models/test_confidence.py` with 10 validation tests
- Verified: all tests pass, `mypy --strict` passes

### Task 1.10 — Complete (2025-12-18)
- Created `src/models/output.py` with `ProcessedDocument`
- Implemented `to_allocator_pro_calls()` and `to_search_document()` helper methods
- Created `tests/unit/models/test_output.py` with 4 tests (serialization + helpers)
- Verified: all tests pass, `mypy --strict` passes

### Task 1.11 — Complete (2025-12-18)
- Created `src/models/pipeline.py` with `IngestResult`, `Section`, `CleanedDocument`, `RetrievedChunk`, `CandidateSet`
- Section model defined per docs/DECISIONS.md
- Created `tests/unit/models/test_pipeline.py` with 9 validation tests
- Verified: all tests pass, `mypy --strict` passes

### Task 2.1 — Complete (2025-12-18)
- Created `src/taxonomy/hierarchy.py` with all categories and sub-assets from TAXONOMY.md
- Implemented CATEGORIES dict mapping category codes to sub-asset lists (31 categories, 100+ sub-assets)
- Implemented CATEGORY_DISPLAY_NAMES and SUB_ASSET_DISPLAY_NAMES dicts
- Built reverse index (_SUB_ASSET_TO_CATEGORY) for O(1) lookups
- Implemented 8 lookup functions: get_category_for_sub_asset, get_sub_assets_for_category, get_category_display_name, get_sub_asset_display_name, is_valid_category, is_valid_sub_asset, get_all_categories, get_all_sub_assets
- Regional real estate categories (APAC, NA, UK, EU) are empty - they're groupings that share sub-assets with ALT_REAL_ESTATE_GLOBAL
- Created `tests/unit/taxonomy/test_hierarchy.py` with 24 comprehensive tests
- Verified: all tests pass (24/24), `mypy --strict` passes

### Task 2.2 — Complete (2025-12-18)
- Created `src/taxonomy/synonyms.py` with comprehensive synonym mappings
- Implemented SYNONYMS dict with 200+ lowercase synonym → sub-asset code mappings
- Covers all major asset classes: commodities, equities (DM/EM), fixed income (sovereigns/IG/HY), currencies
- Implemented resolve_asset() function with case-insensitive matching, returns (category_code, sub_asset_code) or None
- Implemented helper functions: get_all_synonyms_for_sub_asset(), is_valid_synonym()
- All synonym keys are lowercase for consistency
- Created `tests/unit/taxonomy/test_synonyms.py` with 26 comprehensive tests
- Verified: all tests pass (26/26), acceptance criteria met ("bunds" → ("FI_SOV_EUROPE", "GERMAN_BUNDS"))

### Task 2.3 — Complete (2025-12-19)
- Added `src/taxonomy/tags.py` with theme, risk, region, and macro regime vocabularies plus validation helper
- Added `tests/unit/taxonomy/test_tags.py` to enforce vocabulary coverage and validation behavior

### Task 3.1 — Complete (2025-12-19)
- Added `src/config/settings.py` with Pydantic-powered Settings model and cached accessor
- Implemented validation for required environment variables and logging level normalization
- Added `tests/unit/config/test_settings.py` covering env file loading and validation failures

### Task 3.2 — Complete (2025-12-19)
- Added `src/config/logging.py` with configurable console/JSON handlers and redaction for secrets and oversized payloads
- Exported `configure_logging` via `src/config/__init__.py`
- Added `tests/unit/config/test_logging.py` covering formatting, redaction, and truncation behavior

### Task 3.3 — Complete (2025-12-18)
- Created `src/exceptions.py` with 7 exception classes in hierarchical structure
- Base: `PipelineError` → inherits from `Exception`
- Direct children: `ExtractionError`, `ValidationError`, `LLMError`, `StorageError`
- Extraction children: `WeakEvidenceError`, `TaxonomyMappingError` (inherit from `ExtractionError`)
- All exceptions include docstrings explaining their purpose and when to use them
- Created `tests/unit/test_exceptions.py` with 19 comprehensive tests covering inheritance, instantiation, and catching behavior
- Verified: all tests pass (19/19), `mypy --strict` passes

### Task 3.4 — Complete (2025-12-18)
- Created `src/storage/blob.py` with `LocalBlobStorage` class for file-based PDF storage
- Implements SHA-256 hash-based deterministic blob_id generation
- Methods: `store()`, `retrieve()`, `retrieve_metadata()`, `exists()`, `delete()`
- Stores PDFs as `{blob_id}.pdf` and metadata as `{blob_id}.json` in `./data/pdfs/`
- Metadata JSON is pretty-printed with sorted keys for readability and consistency
- Idempotent storage: same content = same blob_id (overwrites existing)
- Comprehensive error handling using `StorageError` exception
- Created `tests/unit/storage/test_blob.py` with 21 tests covering storage, retrieval, deduplication, error cases, and metadata handling
- Verified: all tests pass (21/21), `mypy --strict` passes

### Task 3.5 — Complete (2025-12-18)
- Created `src/storage/database.py` with SQLAlchemy Core-based database layer
- Implemented 7 tables: `managers`, `documents`, `allocation_calls`, `summaries`, `document_tags`, `evidence_blocks`, `pipeline_runs`
- PostgreSQL-portable schema design:
  - UUID as TEXT (will map to UUID type in Postgres)
  - JSON/JSONB as TEXT (will map to JSONB in Postgres)
  - CHECK constraints for enum validation (will map to enum types in Postgres)
  - TIMESTAMPTZ as TEXT with ISO 8601 format
- `Database` class with methods: `get_connection()`, `execute()`, `close()`, `reset_database()`
- Factory function `get_database()` for creating database instances
- All tables include foreign key relationships, unique constraints, and check constraints
- pipeline_runs table tracks: pipeline version, LLM model/provider, runtime, status
- Created `tests/unit/storage/test_database.py` with 18 comprehensive tests
  - Table creation and initialization
  - Insert and query operations for all tables
  - Foreign key relationships and unique constraints
  - CHECK constraint validation (enum values)
  - Connection management and utility methods
- Verified: all tests pass (18/18), `mypy --strict` passes

### Task 4.1 — Complete (2025-12-18)
- Implemented [`src/pipeline/stages/s0_ingest.py`](src/pipeline/stages/s0_ingest.py) with SHA-256 hash-based deduplication, metadata extraction, and blob storage integration
- Created comprehensive test suite in [`tests/unit/pipeline/stages/test_s0_ingest.py`](tests/unit/pipeline/stages/test_s0_ingest.py)
- Key features: idempotent storage, automatic metadata generation, error handling with StorageError exceptions
- Verified: all tests pass (8/8), `mypy --strict` passes

### Task 4.2 — Complete (2025-12-18)
- Implemented [`src/extraction/parser.py`](src/extraction/parser.py) with PyMuPDF-based PDF text extraction
  - `PDFParser` class with methods: `normalize_bbox()`, `detect_block_type()`, `compute_block_confidence()`, `analyze_font_sizes()`, `parse_pdf()`
  - Block type detection heuristics: bullet patterns, font size (≥14pt), bold text flag, position-based (first 3 blocks on page 1)
  - Bounding box normalization to 0-1 coordinates
  - Stable block_id generation in format `{page}_{index}`
  - Per-block confidence scoring (0-1 range)
- Implemented [`src/pipeline/stages/s1_extract.py`](src/pipeline/stages/s1_extract.py) with async `stage_extract()` function
  - Retrieves PDF from blob storage
  - Calls parser to extract content
  - Computes `extraction_coverage = pages_with_text / total_pages`
  - Error handling for storage and extraction failures
  - Supports dependency injection of storage for testability
- Created [`tests/unit/extraction/test_parser.py`](tests/unit/extraction/test_parser.py) with 20 comprehensive unit tests
  - Tests for bbox normalization, block type detection (all heuristics), confidence computation, font analysis
  - Multi-page PDF handling, block ID formatting, invalid PDF handling
- Created [`tests/integration/test_s1_extract.py`](tests/integration/test_s1_extract.py) with 7 integration tests
  - Full pipeline tests with real PDF creation
  - Coverage computation validation
  - Deterministic PDF fixture test validating extraction_coverage = 2/3
  - Block ID uniqueness verification
- All code passes `mypy --strict` (no Stage 1 code errors)
- Verified: all tests pass (27/27), type safety confirmed

### Task 4.3 — Complete (2025-12-18)
- Extended [`src/extraction/parser.py`](src/extraction/parser.py) with table extraction using pdfplumber
  - Added `_extract_tables_from_page()` method for table detection and cell extraction
  - Added `_estimate_cell_bbox()` method for cell bounding box estimation
  - Table ID generation in format `{page}_tbl_{index}`
  - Cell extraction with 0-indexed row/column positions
  - Header detection heuristic: first row marked as header
  - TABLE_CELL block creation for searchable table content
  - Graceful error handling with warnings for extraction failures
  - Fixed type annotation: `self.heading_font_sizes: set[float] = set()`
- Updated [`src/pipeline/stages/s1_extract.py`](src/pipeline/stages/s1_extract.py)
  - Automatically includes extracted tables in `DocumentJSON.tables`
  - Creates TABLE_CELL blocks for table content searchability
- Created comprehensive test suite in [`tests/unit/extraction/test_table_extraction.py`](tests/unit/extraction/test_table_extraction.py)
  - 9 test cases covering: table detection, cell positions, header detection, text content, blocks, validation, edge cases
  - All tests use mocked pdfplumber for deterministic behavior
- Verified: all tests pass (36/36 total: 20 parser + 9 table + 7 integration), `mypy --strict` passes, no existing tests broken

---

### Task 4.4 — Complete (2025-12-19)
- Implemented [`src/pipeline/stages/s2_clean.py`](src/pipeline/stages/s2_clean.py) with async `stage_clean()` function
   - Text normalization: fixes hyphenation across line breaks, normalizes whitespace, strips leading/trailing spaces
   - Boilerplate detection: identifies repeated headers/footers across 3+ consecutive pages, removes duplicates while keeping first instance
   - Disclaimer detection: matches standard disclaimer patterns (informational, past performance, forward-looking, etc.), marks as `BlockType.DISCLAIMER`
   - Section detection: identifies section boundaries using heading patterns, classifies sections (macro, equities, fixed_income, risks, appendix, other)
   - Fallback: creates single section covering all blocks if no clear sections detected
   - Boilerplate ratio warning: logs warning if > 30% of blocks removed
   - Preserves original block IDs (no regeneration)
- Created comprehensive test suite in [`tests/unit/pipeline/stages/test_s2_clean.py`](tests/unit/pipeline/stages/test_s2_clean.py)
   - 24 test cases covering: text normalization (4), disclaimer detection (5), boilerplate removal (2), section classification (6), section detection (3), full pipeline (4)
   - Tests validate: hyphenation fixes, whitespace normalization, disclaimer patterns, repeated header detection, section boundaries, block ID preservation
   - All async tests use pytest-asyncio
- Verified: all tests pass (24/24), `mypy --strict` passes, no existing tests broken

### Task 4.5 — Complete (2025-12-18)
- Implemented [`src/retrieval/indexer.py`](src/retrieval/indexer.py) with per-document vector indexing for retrieval-grounded extraction
   - **Chunking logic**: `chunk_document()` splits by section + paragraph boundaries with 200-400 token target size (~4 chars/token)
     - Skips disclaimer blocks
     - Preserves block_id references and page numbers
     - Handles large blocks exceeding max token size via `_split_large_block()`
     - Falls back to simple chunking if section-aware splitting fails
   - **Embedding generation**: `generate_embeddings()` uses OpenAI `text-embedding-3-small` (1536 dimensions)
     - Batch API calls for efficiency
     - 3-attempt retry with exponential backoff (1s, 2s, 4s)
     - Handles rate limits and transient failures
   - **Vector index class**: `DocumentIndex` with ChromaDB in-memory storage
     - `build()`: chunks document, generates embeddings, stores in ChromaDB with metadata (block_ids, page, section)
     - `query()`: retrieves top-k relevant chunks via cosine similarity, returns `RetrievedChunk` objects with normalized scores (0-1)
     - Metadata preservation: chunk_id format `{doc_id}_{chunk_index}`, block_ids list, page number, section name
- Implemented [`src/pipeline/stages/s3_index.py`](src/pipeline/stages/s3_index.py) with async `stage_index()` function
   - Orchestrates chunking, embedding generation, and index building
   - Returns fully built `DocumentIndex` ready for querying
- Created comprehensive test suite in [`tests/unit/retrieval/test_indexer.py`](tests/unit/retrieval/test_indexer.py)
   - 16 unit tests covering: chunking (5), embedding generation (3), OpenAI provider retry logic (3), DocumentIndex (5)
   - Tests validate: chunk size constraints, disclaimer skipping, block reference preservation, embedding mocking, retry behavior, query functionality
- Created integration test suite in [`tests/integration/test_s3_index.py`](tests/integration/test_s3_index.py)
   - 5 integration tests covering: full pipeline, querying, empty documents, minimal content, query relevance
   - Tests validate: end-to-end Stage 3 functionality, realistic document structures, query result quality
- Verified: all tests pass (21/21), type safety confirmed with explicit type annotations, no existing tests broken

---

### Task 5.1 — Complete (2025-12-19)
- Implemented **multi-provider LLM client** in [`src/llm/client.py`](src/llm/client.py)
- Supports 4 providers via OpenAI-compatible API:
  - **OhMyGPT** (Claude Haiku 4.5) → Metadata & Call Extraction
  - **MegaLLM** (GPT-OSS-120b) → Candidate Retrieval
  - **Nebius** (GLM-4.5-Air) → Verification & Summary Generation
  - **DeepInfra** (Qwen3-235B) → Tooltip & Tag Generation
- **Stage-to-provider routing**: `STAGE_PROVIDER_MAP` automatically selects the right provider per pipeline stage
- **Features implemented**:
  - `LLMProvider` enum for provider selection
  - `PipelineStage` enum for stage-based routing
  - `ProviderConfig` dataclass for provider configuration
  - JSON output mode with Pydantic validation via `complete_json()`
  - Automatic markdown code block cleaning for JSON responses
  - Retry logic with exponential backoff (3 retries, 1s/2s/4s delays)
  - Safe logging: prompts/responses hashed, truncated previews in DEBUG mode
- Updated [`src/config/settings.py`](src/config/settings.py) with new API key settings:
  - `OHMYGPT_API_KEY`, `MEGALLM_API_KEY`, `NEBIUS_API_KEY`, `DEEPINFRA_API_KEY`
- Updated [`.env.example`](.env.example) with all required API keys
- Created comprehensive test suite in [`tests/unit/llm/test_client.py`](tests/unit/llm/test_client.py)
  - 18 test cases covering: initialization, provider config, stage routing, completion, JSON parsing, helper methods, logging
- Verified: all tests pass (18/18), `mypy --strict` passes

### Task 5.2 — Complete (2025-12-19)
- Created [`src/llm/prompts/metadata.py`](src/llm/prompts/metadata.py) — Stage 4 metadata extraction prompt
  - Schema with DocumentProfile fields, uncertainty flags, citation requirements
  - `build_metadata_extraction_prompt()` function for chunk formatting and prompt assembly
- Created [`src/llm/prompts/calls.py`](src/llm/prompts/calls.py) — Stage 6 call extraction prompt
  - Schema with AllocationCall fields, taxonomy codes, sentiment extraction
  - Taxonomy summary helper, call direction rules, conviction mapping
  - Critical guardrails: NO HALLUCINATION, NO DUPLICATE CALLS, confidence scoring
- Created [`src/llm/prompts/summaries.py`](src/llm/prompts/summaries.py) — Stage 7 summary generation prompt
  - Executive summary (120-180 words), search descriptor (20-35 words), key takeaways (3-5 bullets)
  - Word count enforcement, attribution guidance
- Created [`src/llm/prompts/tooltips.py`](src/llm/prompts/tooltips.py) — Stage 8 tooltip generation prompt
  - ≤25 word hover text per call with positioning and key reason
  - Good/bad examples from LLM_CONTRACTS.md
- Created [`src/llm/prompts/tags.py`](src/llm/prompts/tags.py) — Stage 9 tag generation prompt
  - Uses allowed vocabularies from `src/taxonomy/tags.py`
  - Theme, risk, macro regime tag categories with mapping guidance
- Created [`src/llm/prompts/verification.py`](src/llm/prompts/verification.py) — Stage 6 verification pass prompt (v1+ deferred)
  - Direction, taxonomy, rationale verification with evidence strength scoring
- Updated [`src/llm/prompts/__init__.py`](src/llm/prompts/__init__.py) with all exports
- Fixed mypy configuration in `pyproject.toml` (removed `mypy_path`, added `namespace_packages = true`)
- Created comprehensive test suite in [`tests/unit/llm/test_prompts.py`](tests/unit/llm/test_prompts.py)
  - 33 test cases covering: schema validation, prompt building, guardrails, helper functions
- Verified: all tests pass (51/51 in llm module), mypy passes on prompts module

### Task 5.3 — Complete (2025-12-19)
- Added `src/llm/contracts.py` with citation, taxonomy, and hallucination guardrail validation
- Exported validation helpers via `src/llm/__init__.py`
- Added `tests/unit/llm/test_contracts.py` covering citations, taxonomy mismatch, hallucination detection

### Task 6.1 — Complete (2025-12-20)
- Added `src/pipeline/stages/s4_metadata.py` with retrieval-assisted metadata extraction and date plausibility checks
- Implemented chunk selection for first two pages plus metadata query to build the LLM prompt
- Added `tests/unit/pipeline/stages/test_s4_metadata.py` covering successful extraction, uncertainty handling, and fallback behavior

### Task 6.2 — Complete (2025-12-20)
- Implemented **Stage 5: Candidate Retrieval** in `src/pipeline/stages/s5_candidates.py`
  - **Keyword mining**: Searches for positioning keywords (overweight, underweight, prefer, avoid, etc.) and asset class mentions from taxonomy
  - **Block-to-chunk retrieval**: Maps keyword-matched blocks to chunks from the document index
  - **LLM expansion**: Uses LLM to identify additional passages with indirect/implied positioning language not caught by keywords
  - **Signal density ranking**: Ranks chunks by density of signal keywords
  - **Deduplication**: Removes duplicate chunks while preserving order
  - Returns `CandidateSet` with up to 30 candidate chunks (20 keyword + 10 expansion)
- Created `src/llm/prompts/candidates.py` with expansion prompt template
  - Asks LLM to find passages with indirect signals (e.g., "find value in", "reducing exposure")
  - Includes guardrails against selecting pure macro commentary or disclaimers
- Updated `src/llm/prompts/__init__.py` to export candidate expansion prompt
- Created comprehensive test suite in `tests/unit/pipeline/stages/test_s5_candidates.py`
  - 16 test cases covering: keyword mining, chunk retrieval, ranking, deduplication, LLM expansion, edge cases
  - Tests validate: positioning keyword detection, asset class keyword detection, disclaimer skipping, signal density ranking, empty index handling
- Verified: all 16 Stage 5 tests pass, all 76 pipeline/integration tests pass, `mypy --strict` passes

### Task 6.3 — Complete (2025-12-20)
- Implemented **Stage 6: Call Extraction** in `src/pipeline/stages/s6_calls.py`
  - **Asset mention detection**: Extracts allocation calls (OVERWEIGHT/NEUTRAL/UNDERWEIGHT/UNCERTAIN) with taxonomy mapping
  - **Rationale extraction**: 1-4 bullet points per call with supporting evidence
  - **Key indicators**: Parses economic/market indicators with direction (RISING/FALLING/STABLE/VOLATILE)
  - **Sentiment extraction**: Overall document sentiment (NET_POSITIVE/NEUTRAL/NET_NEGATIVE) with rationale and citations
  - **Citation parsing**: Converts LLM output dicts to Citation objects, handles optional text_span field
  - **Duplicate detection**: Validates no duplicate (category, sub_asset) pairs exist
  - **Validation**: Uses `validate_llm_output()` to check citations, taxonomy, and hallucination markers
  - **Model version tracking**: Captures LLM provider model name in output metadata
- Helper functions: `_parse_citation()`, `_parse_key_indicator()`, `_parse_allocation_call()`, `_check_duplicate_calls()`, `_build_call_extraction_output()`
- LLM models: `CallLLM` (single call schema), `CallExtractionLLM` (full extraction output schema)
- Uses `PipelineStage.CALLS` with OhMyGPT provider (Claude Haiku 4.5) for call extraction
- Created comprehensive test suite in `tests/unit/pipeline/stages/test_s6_calls.py`
  - 10 test cases covering: successful extraction, uncertain calls, duplicate detection, multiple calls, empty candidates, citation parsing, key risks, model version, prompt building
  - Tests validate: CallExtractionOutput structure, sentiment extraction, review flags, UNCERTAIN handling, duplicate call rejection
- Verified: all 10 Stage 6 tests pass, all 86 pipeline/integration tests pass, `mypy --strict` passes

### Task 6.5 — Complete (2025-12-20)
- Implemented **Stage 7: Summary Generation** in `src/pipeline/stages/s7_summaries.py`
  - **Executive summary generation**: 120-180 words with top macro drivers, top 3 calls, 2 key risks
  - **Search descriptor**: 20-35 words combining document type, implications, and asset focus
  - **Key takeaways**: 3-5 actionable bullets with citations
  - **Smart chunk retrieval**: Multi-query retrieval using document metadata, sentiment themes, and top asset classes
  - **Citation parsing**: Handles citations with optional text_span field
  - **Word count validation**: Logs warnings for out-of-bounds word counts (non-blocking)
  - **Model version tracking**: Captures LLM provider model name (Nebius GLM-4.5-Air)
- LLM models: `KeyTakeawayLLM` (single takeaway schema), `SummaryGenerationLLM` (full output schema)
- Uses `PipelineStage.SUMMARIES` with Nebius provider (GLM-4.5-Air) for summary generation
- Helper functions: `_parse_citation()`, `_parse_key_takeaway()`, `_retrieve_key_passages()`, `_validate_word_count()`
- Chunk retrieval strategy: Deduplicates across multiple queries, ranks by relevance score, returns top 30 chunks
- Created comprehensive test suite in `tests/unit/pipeline/stages/test_s7_summaries.py`
  - 10 test cases covering: complete output generation, word count validation, citation parsing, multiple takeaways, chunk retrieval, no-calls handling, prompt building, error handling
  - Tests validate: DocumentSummaries structure, citation parsing (with/without text_span), takeaway validation, LLM failure handling
- Verified: all 10 Stage 7 tests pass, all 84 pipeline stage tests pass, `mypy --strict` passes on all pipeline stages

### Task 6.6 — Complete (2025-12-22)
- Implemented **Stage 8: Tooltip Generation** in `src/pipeline/stages/s8_tooltips.py`
  - **Tooltip generation**: Generates concise hover text (≤25 words, ≤150 chars) for each allocation call
  - **Quality validation**: Enforces character limit (≤150 chars, hard requirement), word count (≤25 words, warning), generic pattern detection (warnings)
  - **In-place mutation**: Updates `CallExtractionOutput.allocation_calls[].tooltip_text` field directly
  - **Asset mapping**: Maps LLM-generated tooltips to calls via `sub_asset_class` identifier
  - **Comprehensive validation**: Count mismatch detection, missing tooltip detection, quality checks
- LLM models: `TooltipItem` (single tooltip schema), `TooltipGenerationLLM` (full output schema)
- Uses `PipelineStage.TOOLTIPS` with DeepInfra provider (Qwen3-235B) for tooltip generation
- Helper functions: `_validate_tooltip_quality()` for quality validation (word count, char count, generic pattern detection)
- Quality checks: Character limit enforcement (raises ValidationError), word count warning (logs only), generic pattern detection (logs warning)
- Created comprehensive test suite in `tests/unit/pipeline/stages/test_s8_tooltips.py`
  - 11 test cases covering: successful generation, empty calls handling, count mismatch, missing asset, quality validation (char/word limits), generic patterns, in-place mutation, prompt building, multiple calls
  - Tests validate: TooltipGenerationLLM output parsing, validation logic, error handling, in-place mutation behavior
- Verified: all 11 Stage 8 tests pass, all 95 pipeline stage tests pass, `mypy --strict` passes

### Task 6.7 — Complete (2025-12-22)
- Implemented **Stage 9: Tag Generation** in `src/pipeline/stages/s9_tags.py`
  - **Hybrid tagging approach**: Combines deterministic rule-based tags with LLM-generated tags
  - **Deterministic tagging** (`_extract_deterministic_tags()`):
    - Asset class tags: Extracted from call categories (e.g., EQUITIES_DM, FIXED_INCOME_SOVEREIGNS_EUROPE)
    - Region tags: Extracted from profile.regions, normalized to lowercase, filtered against allowed REGION_TAGS
    - Instrument tags: Extracted from sub-asset codes (e.g., german_bunds, us_large_cap), normalized to lowercase
  - **LLM tagging** (`_retrieve_passages_for_tagging()` + LLM call):
    - Theme tags: Key themes (inflation, fed_policy, recession_risk, etc.) from THEME_TAGS vocabulary
    - Risk tags: Key risks (duration_risk, credit_spreads, etc.) from RISK_TAGS vocabulary
    - Macro regime tags: Economic regime view (soft_landing, stagflation, etc.) from MACRO_REGIME_TAGS vocabulary
    - Retrieves top 20 chunks using multi-query strategy (macro outlook, risks, sentiment)
  - **Tag validation & normalization** (`_validate_and_normalize_llm_tags()`):
    - Validates all LLM tags against allowed vocabularies
    - Normalizes to lowercase
    - Filters out invalid tags with warnings
    - Detects novel themes for vocabulary expansion
  - **Tag object construction** (`_build_tag_objects()`):
    - Creates Tag objects with type, value, confidence, source
    - Rule-based tags: confidence=1.0, source="rule"
    - LLM-based tags: confidence from LLM output, source="llm"
  - **Acceptance validation**: Ensures ≥1 asset class tag (hard requirement), warns if <5 total tags
- LLM model: `TagGenerationLLM` with theme_tags, risk_tags, macro_regime_tags, novel_themes fields
- Uses `PipelineStage.TAGS` with DeepInfra provider (Qwen3-235B) for tag generation
- Helper functions: `_extract_deterministic_tags()`, `_retrieve_passages_for_tagging()`, `_validate_and_normalize_llm_tags()`, `_build_tag_objects()`
- Chunk retrieval strategy: Multi-query (macro outlook, risks, sentiment) + deduplication + top 20 chunks
- Created comprehensive test suite in `tests/unit/pipeline/stages/test_s9_tags.py`
  - 12 test cases covering: deterministic extraction, deduplication, LLM validation, tag normalization, case-insensitive validation, tag object construction, full pipeline, empty calls handling, insufficient tags warning, novel themes logging, prompt building, invalid region filtering
  - Tests validate: TagSet structure, deterministic tag extraction, LLM tag validation, vocabulary enforcement, novel theme detection, minimum tag requirements
- Verified: all 12 Stage 9 tests pass, all 107 pipeline stage tests pass, `mypy --strict` passes

### Task 7.1 — Complete (2025-12-25)
- Implemented `src/pipeline/stages/s10_confidence.py` with extraction quality scoring functions
- **Text coverage scoring** (`score_text_coverage`): Uses `extraction_coverage` directly (40% weight)
- **OCR quality scoring** (`score_ocr_quality`): Detects garbled characters in OCR pages, returns 1.0 if no OCR needed (20% weight)
- **Table extraction success** (`score_table_success`): Ratio of tables with content vs total tables (20% weight)
- **Block structure quality** (`score_structure_quality`): Measures heading/paragraph/bullet detection and block type variety (20% weight)
- **Aggregate scoring** (`score_extraction_quality`): Weighted combination per CONFIDENCE.md
- **Explicit call language detection** (`has_explicit_call_language`): Pattern matching for OW/UW/N language
- **Confidence band computation** (`compute_confidence_band`): HIGH ≥0.80, MEDIUM 0.60-0.79, LOW <0.60
- Created comprehensive test suite in `tests/unit/pipeline/stages/test_s10_confidence.py` with 27 tests
- Verified: all tests pass (27/27), `mypy --strict` passes

### Task 7.2 — Complete (2025-12-25)
- Added evidence strength scoring to `src/pipeline/stages/s10_confidence.py`
- **Explicit mention detection** (`has_explicit_mention`): Direct substring match (1.0) or multi-word presence (0.8)
- **Semantic similarity** (`compute_word_overlap`): Word overlap ratio as proxy for similarity (30% weight)
- **Entailment heuristic** (`compute_entailment_heuristic`): Pattern matching for supporting context (20% weight)
- **Evidence strength scoring** (`score_evidence_strength`): Weighted combination (50%/30%/20%), returns best score across citations
- **Call evidence scoring** (`score_call_evidence`): Combines evidence strength (50%) with explicit call language (50%)
- Added 23 new tests covering all evidence scoring functions
- Verified: all 50 tests pass, `mypy --strict` passes

### Task 7.3 — Complete (2025-12-25)
- Added document-level confidence computation to `src/pipeline/stages/s10_confidence.py`
- **Weighted aggregation** per CONFIDENCE.md: extraction (15%), profile (15%), calls (50%), summary (20%)
- **Attention flagging** (`_compute_attention_reasons`): low coverage, uncertain manager/date, calls needing review, no calls, many low-confidence calls
- **Field confidences**: Populates FieldConfidence for extraction, profile, calls, summary
- **Stage function** (`stage_confidence`): Async wrapper for pipeline integration
- Added 10 new tests covering document confidence and attention reasons
- Verified: all 60 tests pass, `mypy --strict` passes

### Task 7.4 — Complete (2025-12-25)
- Added review routing to `src/pipeline/stages/s10_confidence.py`
- **DocumentRouting enum**: AUTO_PUBLISH, SPOT_CHECK, MUST_REVIEW
- **can_auto_publish**: Checks HIGH band + coverage ≥0.70 + no attention flags + no uncertain fields
- **should_spot_check**: 20% sampling of MEDIUM confidence docs
- **determine_routing**: Routes based on band and criteria (HIGH→auto/review, MEDIUM→auto/spot, LOW→review)
- Added 13 new tests covering all routing scenarios with mocked randomness
- Verified: all 73 tests pass, `mypy --strict` passes

### Task 8.1 — Complete (2025-12-25)
- Implemented `src/pipeline/run.py` with `process_pdf()` async function
- **Stage execution**: Runs stages 0-10 in sequence with proper error handling
- **Graceful failure handling**: Catches ExtractionError, ValidationError, LLMError, StorageError and wraps in PipelineError
- **Database persistence**: Records pipeline run start/completion, updates document record, inserts allocation calls, summaries, and tags
- **Run tracking**: Creates pipeline_runs record with LLM model/provider, runtime, status, stages completed
- **ProcessedDocument output**: Returns complete output with all extracted data and metadata
- Created comprehensive test suite in `tests/unit/pipeline/test_orchestrator.py` with 5 tests
- Verified: all tests pass (5/5), `mypy --strict` passes on run.py

### Task 8.2 — Complete (2025-12-25)
- Added CLI interface to `src/pipeline/run.py` using argparse
- Commands: `python -m pipeline.run --pdf <path>` runs full pipeline
- Options: `--output/-o` for JSON file output, `--verbose/-v` for debug logging, `--version`
- Graceful error handling: file not found, pipeline errors, unexpected errors
- Added 4 CLI tests to `tests/unit/pipeline/test_orchestrator.py`
- Verified: all tests pass (9/9), `mypy --strict` passes

### Task 8.3 — Complete (2025-12-25)
- Created `src/pipeline/validate.py` with output validation utility
- Validates: schema compliance, taxonomy codes, tag vocabularies, citation structure
- CLI: `python -m pipeline.validate --output <json>`
- Created 11 tests in `tests/unit/pipeline/test_validate.py`
- Verified: all tests pass (11/11), `mypy --strict` passes

### Task 9.1 — Complete (2025-12-26)
- Expanded `tests/conftest.py` with deterministic PDF helpers and mock LLM client fixtures
- Added `tests/fixtures/llm_responses.py` with stage-specific mock payloads
- Created fixture package init and placeholder directories for PDF/expected output fixtures
- Added `tests/unit/fixtures/test_llm_fixtures.py` to validate fixture schemas

### Task 9.2 — Complete (2025-12-26)
- Added `tests/unit/models/test_enums.py` to validate enum values and invalid inputs

### Task 9.3 — Complete (2025-12-26)
- Added full synonym resolution coverage in `tests/unit/taxonomy/test_synonyms.py`

### Task 9.4 — Complete (2025-12-26)
- Added integration tests for stages 0, 2, and 4–10 in `tests/integration/test_stage_s0_ingest.py`, `tests/integration/test_stage_s2_clean.py`, `tests/integration/test_stage_s4_metadata.py`, `tests/integration/test_stage_s5_candidates.py`, `tests/integration/test_stage_s6_calls.py`, `tests/integration/test_stage_s7_summaries.py`, `tests/integration/test_stage_s8_tooltips.py`, `tests/integration/test_stage_s9_tags.py`, `tests/integration/test_stage_s10_confidence.py`
- Renamed integration tests for Stage 1 and 3 to `tests/integration/test_stage_s1_extract.py` and `tests/integration/test_stage_s3_index.py`

### Task 9.5 — Complete (2025-12-27)
- Added deterministic end-to-end pipeline coverage with golden output checks and edge-case assertions in `tests/e2e/test_full_pipeline.py`
- Added golden output fixture `tests/fixtures/expected_outputs/full_pipeline.json`

### Task 9.6 — Complete (2025-12-26)
- Added confidence calibration tests covering boundary bands and weighted extraction scoring in `tests/unit/test_confidence.py`
