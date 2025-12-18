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
- [ ] `2.3` Implement Tag Vocabularies

### Phase 3: Infrastructure Layer
- [ ] `3.1` Create Configuration System
- [ ] `3.2` Create Logging Configuration
- [ ] `3.3` Create Exception Hierarchy
- [ ] `3.4` Implement Local Blob Storage
- [ ] `3.5` Implement SQLite Database Layer

### Phase 4: PDF Extraction (Stages 0–3)
- [ ] `4.1` Implement Stage 0 - Ingest
- [ ] `4.2` Implement Stage 1 - Text Extraction
- [ ] `4.3` Implement Table Extraction
- [ ] `4.4` Implement Stage 2 - Cleaning
- [ ] `4.5` Implement Stage 3 - Retrieval Index

### Phase 5: LLM Interaction Layer
- [ ] `5.1` Create LLM Client Wrapper
- [ ] `5.2` Create Prompt Templates
- [ ] `5.3` Create LLM Output Validation

### Phase 6: LLM Pipeline Stages (Stages 4–9)
- [ ] `6.1` Implement Stage 4 - Metadata Extraction
- [ ] `6.2` Implement Stage 5 - Candidate Retrieval
- [ ] `6.3` Implement Stage 6 - Call Extraction (Core)
- [ ] `6.4` Implement Stage 6 - Verification Pass (v1+ deferred)
- [ ] `6.5` Implement Stage 7 - Summary Generation
- [ ] `6.6` Implement Stage 8 - Tooltip Generation
- [ ] `6.7` Implement Stage 9 - Tag Generation

### Phase 7: Confidence & Validation (Stage 10)
- [ ] `7.1` Implement Extraction Quality Scoring
- [ ] `7.2` Implement Evidence Strength Scoring
- [ ] `7.3` Implement Document-Level Confidence
- [ ] `7.4` Implement Review Routing

### Phase 8: Pipeline Orchestration
- [ ] `8.1` Create Pipeline Orchestrator
- [ ] `8.2` Create CLI Interface
- [ ] `8.3` Create Output Validator

### Phase 9: Testing
- [ ] `9.1` Create Test Fixtures
- [ ] `9.2` Write Model Unit Tests
- [ ] `9.3` Write Taxonomy Unit Tests
- [ ] `9.4` Write Stage Integration Tests
- [ ] `9.5` Write E2E Pipeline Tests
- [ ] `9.6` Write Confidence Scoring Tests

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

---
