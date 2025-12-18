# Markets Recon — Allocator Pro Document Intelligence Pipeline

## Mission

Build a production-grade AI pipeline that processes fund manager outlook PDFs into structured allocation intelligence for Allocator Pro. Every extraction must be evidence-anchored, confidence-scored, and audit-ready.

**Non-negotiable constraints:**
- One PDF at a time (MVP)
- Every claim requires citation (chunk_id + page)
- No hallucination—if evidence is weak, output `UNCERTAIN` + reason
- Human review for LOW confidence items
- Scale target: 2,000–3,000 PDFs/month

---

## Project Status

**Current state:** Specification only—no runnable code yet.  
**Target:** MVP for personal testing with publicly available fund manager PDFs.  
**Infrastructure:** Local SQLite or PostgreSQL on small GCP instance (2 vCPU, 6GB RAM, 22GB storage).

---

## MVP Scope (v0)

### In Scope
- Stages 0-10 (full pipeline, single PDF at a time)
- Text extraction via PyMuPDF/pdfplumber (clean PDFs only)
- Basic chunking + embeddings (OpenAI or local model)
- LLM extraction via Claude API
- SQLite for persistence (upgrade to Postgres later)
- CLI runner: `python -m pipeline.run --pdf <path>`
- Confidence scoring + JSON output
- Basic validation tests

### Deferred (v1+)
- OCR for scanned PDFs
- Vision for charts/heatmaps
- Verification pass (single-pass extraction only for MVP)
- Review UI (manual JSON inspection for now)
- Search index (OpenSearch/Elasticsearch)
- Queue-based batch processing

### Success Metrics (MVP)
| Metric | Target |
|--------|--------|
| PDFs processed without crash | ≥90% |
| Calls extracted per PDF (avg) | ≥3 |
| Citations present per call | 100% |
| Processing time per PDF | <3 min |

### Evaluation Set
- **Target:** 20-50 publicly available fund manager outlook PDFs
- **Sources:** BlackRock, Vanguard, JPMorgan AM, PIMCO, Fidelity (public outlooks)
- **Manual validation:** Spot-check call direction accuracy, citation validity

---

## Quick Reference

| Action | Command |
|--------|---------|
| Run full pipeline | `python -m pipeline.run --pdf <path>` |
| Run single stage | `python -m pipeline.stages.<stage> --pdf <path>` |
| Validate output | `python -m pipeline.validate --output <json>` |
| Run tests | `pytest tests/ -v` |
| Type check | `mypy src/ --strict` |
| Lint | `ruff check src/ tests/` |
| Format | `ruff format src/ tests/` |

> **Note:** Commands above are target interfaces. Code implementation does not exist yet.
---

## Documentation Index

**Read these BEFORE writing code for the relevant area:**

| Document | Purpose | Read when... |
|----------|---------|--------------|
| [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md) | System components, data flow, infrastructure | Starting any new component |
| [`docs/SCHEMAS.md`](docs/SCHEMAS.md) | All JSON schemas, Pydantic models, enums | Defining or consuming data structures |
| [`docs/PIPELINE.md`](docs/PIPELINE.md) | 10-stage pipeline specification | Implementing any pipeline stage |
| [`docs/TAXONOMY.md`](docs/TAXONOMY.md) | Asset class hierarchy, mappings, synonyms | Working with asset classification |
| [`docs/LLM_CONTRACTS.md`](docs/LLM_CONTRACTS.md) | Prompt templates, output contracts, guardrails | Writing any LLM interaction |
| [`docs/CONFIDENCE.md`](docs/CONFIDENCE.md) | Scoring logic, thresholds, flagging rules | Implementing validation/confidence |
| [`docs/REVIEW_UI.md`](docs/REVIEW_UI.md) | Human review interface specification | Building review workflows |
| [`docs/TESTING.md`](docs/TESTING.md) | Test strategy, fixtures, acceptance criteria | Writing tests |

---

## Directory Structure

```
marketsrecon/
├── CLAUDE.md                    # You are here
├── docs/                        # Specifications (read-only reference)
│   ├── ARCHITECTURE.md
│   ├── SCHEMAS.md
│   ├── PIPELINE.md
│   ├── TAXONOMY.md
│   ├── LLM_CONTRACTS.md
│   ├── CONFIDENCE.md
│   ├── REVIEW_UI.md
│   └── TESTING.md
├── src/
│   ├── pipeline/
│   │   ├── __init__.py
│   │   ├── run.py               # Orchestrator
│   │   ├── stages/              # Stage implementations (0-10)
│   │   │   ├── s0_ingest.py
│   │   │   ├── s1_extract.py
│   │   │   ├── s2_clean.py
│   │   │   ├── s3_index.py
│   │   │   ├── s4_metadata.py
│   │   │   ├── s5_candidates.py
│   │   │   ├── s6_calls.py
│   │   │   ├── s7_summaries.py
│   │   │   ├── s8_tooltips.py
│   │   │   ├── s9_tags.py
│   │   │   └── s10_confidence.py
│   │   └── validate.py
│   ├── models/                  # Pydantic schemas
│   │   ├── __init__.py
│   │   ├── document.py
│   │   ├── calls.py
│   │   ├── summaries.py
│   │   ├── tags.py
│   │   └── confidence.py
│   ├── taxonomy/                # Asset class taxonomy
│   │   ├── __init__.py
│   │   ├── hierarchy.py
│   │   └── synonyms.py
│   ├── llm/                     # LLM interaction layer
│   │   ├── __init__.py
│   │   ├── client.py
│   │   ├── prompts/             # Prompt templates
│   │   └── contracts.py
│   ├── extraction/              # PDF/OCR extraction
│   │   ├── __init__.py
│   │   ├── parser.py
│   │   └── ocr.py
│   ├── retrieval/               # Per-doc vector index
│   │   ├── __init__.py
│   │   └── indexer.py
│   └── storage/                 # Database + blob storage
│       ├── __init__.py
│       ├── postgres.py
│       └── blob.py
├── tests/
│   ├── conftest.py
│   ├── fixtures/                # Sample PDFs, expected outputs
│   ├── unit/
│   ├── integration/
│   └── e2e/
├── scripts/
│   ├── seed_taxonomy.py
│   └── run_batch.py
└── config/
    ├── settings.py
    └── logging.yaml
```

---

## Code Standards

### Absolute Requirements

1. **Type everything.** No `Any` unless unavoidable. Use `mypy --strict`.
2. **Pydantic for all data.** No raw dicts crossing function boundaries.
3. **Every LLM output validated** against schema before use.
4. **Citations mandatory.** If a field comes from the document, include `citations: list[Citation]`.
5. **Fail loud.** Raise exceptions for invalid states; never silently continue.
6. **Idempotent stages.** Re-running a stage with same input = same output.

### Style

```python
# YES: Explicit, typed, validated
async def extract_calls(
    doc: DocumentJSON,
    taxonomy: AssetTaxonomy,
) -> list[AllocationCall]:
    ...

# NO: Vague, untyped, implicit
def process(data, config):
    ...
```

### Error Handling

```python
# Use domain-specific exceptions
class ExtractionError(Exception):
    """Base for extraction failures."""

class WeakEvidenceError(ExtractionError):
    """LLM could not find sufficient evidence."""

class TaxonomyMappingError(ExtractionError):
    """Asset class could not be mapped to taxonomy."""
```

---

## Critical Rules for LLM Interactions

**Read [`docs/LLM_CONTRACTS.md`](docs/LLM_CONTRACTS.md) before writing ANY LLM code.**

Summary:
1. **Never ask LLM to read full documents.** Retrieve candidate chunks first.
2. **Every prompt returns JSON** matching a Pydantic model.
3. **Evidence-first:** LLM must cite chunk_id + page for every claim.
4. **If uncertain, output null + reason.** Never guess.
5. **Two-pass verification** for high-stakes extractions (calls, sentiment).

---

## Pipeline Stage Contracts

Each stage has:
- **Input schema** (Pydantic model)
- **Output schema** (Pydantic model)
- **Acceptance criteria** (what makes output valid)
- **Error conditions** (when to fail vs flag for review)

**Always check [`docs/PIPELINE.md`](docs/PIPELINE.md) for the contract before implementing.**

---

## Allocator Pro Output Mapping

Pipeline outputs feed directly into Allocator Pro modules:

| Pipeline Output | Allocator Pro Module |
|-----------------|---------------------|
| `AllocationCall[]` | Module 1: Asset Class Calls (bar charts) |
| `AllocationCall[]` | Module 2: Manager Allocation Analysis (grid) |
| `OverallSentiment` | Module 3: Bull/Bear Sentiment |
| Aggregated `AllocationCall[]` | Module 4: Most OW/UW Rankings |
| `ExecutiveSummary`, `Tags` | Search index |

---

## Testing Requirements

**Read [`docs/TESTING.md`](docs/TESTING.md) for full specification.**

Minimum coverage:
- Unit tests for all Pydantic models (validation edge cases)
- Unit tests for taxonomy mapping logic
- Integration tests for each pipeline stage
- E2E tests with 5+ real PDFs covering different manager formats
- Golden output tests: known input → expected output

**Every PR must include tests for changed code.**

---

## Confidence & Review Thresholds

| Confidence Band | Range | Action |
|-----------------|-------|--------|
| HIGH | ≥0.80 | Auto-publish |
| MEDIUM | 0.60–0.79 | Spot-check queue (sampled) |
| LOW | <0.60 | Must-review queue |

**Read [`docs/CONFIDENCE.md`](docs/CONFIDENCE.md) for scoring logic.**

---

## Environment Setup

```bash
# Python 3.11+
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

# Required services
# - PostgreSQL 15+ (structured data)
# - OpenSearch or pgvector (embeddings)
# - S3-compatible blob storage (PDFs)
# - Redis (task queue, optional for MVP)

# Environment variables (see .env.example)
export DATABASE_URL=postgresql://...
export BLOB_STORAGE_URL=s3://...
export ANTHROPIC_API_KEY=...
```

---

## Pre-Commit Checklist

Before committing code:

- [ ] `mypy src/ --strict` passes
- [ ] `ruff check src/ tests/` passes
- [ ] `pytest tests/` passes
- [ ] New code has corresponding tests
- [ ] Pydantic models match docs/SCHEMAS.md
- [ ] LLM prompts follow docs/LLM_CONTRACTS.md
- [ ] No raw dicts crossing function boundaries

---

## Git Workflow (Required)

### Branching Rule

- **One branch per phase in `PROGRESS.md`.** All work for tasks in that phase must happen on that phase branch (do not mix phases on a single branch).
- **No direct commits to `main`** for normal work. Integrate phase work via PR only.

**Branch naming convention:**
- `phase-<number>-<short-slug>` (example: `phase-1-foundation`)

### Task Commit Rule

After finishing **each task** in `PROGRESS.md`:
- Stage all files changed for that task.
- Commit with a clear, task-referenced message (example: `Task 1.2 — Create Core Enums`).
- Keep the working tree clean before starting the next task.
- **IMPORTANT:** Do NOT mention AI agents (Claude, GPT, etc.) anywhere in commit messages. Commit messages should be professional and focus on the technical changes made.

Prefer including the `PROGRESS.md` checkbox/status updates for that task in the same commit as the code/docs changes.

### Phase PR Rule

After completing **all tasks in a phase** (per `PROGRESS.md`):
- Open a PR from the phase branch into `main`.
- Request review and ensure the PR meets the pre-commit checklist/CI requirements before merge.

---

## When in Doubt

1. **Check the relevant doc** in `docs/` first.
2. **Fail explicitly** rather than guess.
3. **Add confidence reasons** when uncertain.
4. **Flag for human review** if evidence is weak.

The goal is **auditability**: anyone should be able to trace any output back to evidence in the source PDF.
