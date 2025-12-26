# Markets Recon

**AI-powered document intelligence pipeline for processing fund manager outlook PDFs into structured allocation intelligence.**

Markets Recon transforms unstructured fund manager documents into evidence-anchored, confidence-scored investment signals that integrate directly with Allocator Pro. Every extracted allocation call is traceable back to specific passages in the source document.

## Key Features

- **Evidence-Anchored Extraction**: Every allocation call includes citations with chunk IDs, page numbers, and text spans
- **Retrieval-Grounded LLM**: Never asks the LLM to read full documents—always retrieves candidate chunks first
- **Multi-Provider LLM Routing**: Stage-specific model selection for optimal cost/quality tradeoffs
- **Confidence Scoring**: Automated quality assessment with review routing (HIGH→auto-publish, MEDIUM→spot-check, LOW→must-review)
- **Asset Class Taxonomy**: 31 categories, 100+ sub-assets, 200+ synonym mappings
- **Hallucination Prevention**: Explicit uncertainty handling—outputs `UNCERTAIN` with reason rather than guessing

## Project Status

| Metric | Status |
|--------|--------|
| Implementation | **Phase 9 Complete** (10 of 10 pipeline stages) |
| Tests | **585 passing** across 60 test files |
| Type Safety | `mypy --strict` ✓ |
| Source Files | 53 Python files |

**Current Stage**: Ready for MVP evaluation with real fund manager PDFs.

## Quick Start

### Installation

```bash
# Clone and setup
git clone <repository-url>
cd marketsrecon

# Create virtual environment
python -m venv .venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate

# Install with development dependencies
pip install -e ".[dev]"

# Configure environment
cp .env.example .env
# Edit .env with your API keys (see Configuration section)
```

### Running the Pipeline

```bash
# Process a single PDF
python -m pipeline.run --pdf /path/to/document.pdf

# Output to JSON file
python -m pipeline.run --pdf /path/to/document.pdf -o results.json

# Verbose mode (DEBUG logging)
python -m pipeline.run --pdf /path/to/document.pdf -v

# Validate pipeline output
python -m pipeline.validate --output results.json
```

### Running Tests

```bash
# Run all tests
pytest tests/ -v

# Run specific test categories
pytest tests/unit/ -v        # Unit tests
pytest tests/integration/ -v  # Integration tests
pytest tests/e2e/ -v          # End-to-end tests

# Type checking
mypy src/ --strict

# Linting and formatting
ruff check src/ tests/
ruff format src/ tests/
```

## Configuration

Create a `.env` file with the following API keys:

```bash
# LLM Providers (stage-specific routing)
OHMYGPT_API_KEY=...      # Claude Haiku 4.5 (Metadata & Calls)
MEGALLM_API_KEY=...      # GPT-OSS-120b (Candidates)
NEBIUS_API_KEY=...       # GLM-4.5-Air (Summaries)
DEEPINFRA_API_KEY=...    # Qwen3-235B (Tooltips & Tags)

# Embeddings
OPENAI_API_KEY=...       # text-embedding-3-small

# Storage (defaults work for local development)
DATABASE_URL=sqlite:///./data/marketsrecon.db
BLOB_STORAGE_PATH=./data/pdfs

# Logging
LOG_LEVEL=INFO
```

## Pipeline Architecture

The system processes documents through **11 stages (0-10)**, each with defined input/output schemas:

```
┌─────────┐   ┌─────────┐   ┌─────────┐   ┌─────────┐   ┌──────────┐
│ Ingest  │──▶│ Extract │──▶│  Clean  │──▶│  Index  │──▶│ Metadata │
│  (S0)   │   │  (S1)   │   │  (S2)   │   │  (S3)   │   │   (S4)   │
└─────────┘   └─────────┘   └─────────┘   └─────────┘   └──────────┘
                                                              │
     ┌────────────────────────────────────────────────────────┘
     ▼
┌────────────┐   ┌─────────┐   ┌──────────┐   ┌──────────┐   ┌─────────┐
│ Candidates │──▶│  Calls  │──▶│ Summaries│──▶│ Tooltips │──▶│  Tags   │
│    (S5)    │   │  (S6)   │   │   (S7)   │   │   (S8)   │   │  (S9)   │
└────────────┘   └─────────┘   └──────────┘   └──────────┘   └─────────┘
                                                                   │
                                                                   ▼
                                                          ┌────────────┐
                                                          │ Confidence │
                                                          │   (S10)    │
                                                          └────────────┘
```

| Stage | Purpose | Output |
|-------|---------|--------|
| **S0** | SHA-256 deduplication, blob storage | `IngestResult` |
| **S1** | PyMuPDF text/layout extraction | `DocumentJSON` |
| **S2** | Boilerplate removal, section detection | `CleanedDocument` |
| **S3** | Chunking + OpenAI embeddings → ChromaDB | `DocumentIndex` |
| **S4** | Manager name, dates, regions (LLM) | `DocumentProfile` |
| **S5** | Keyword mining + LLM expansion | `CandidateSet` |
| **S6** | Allocation calls with taxonomy mapping | `CallExtractionOutput` |
| **S7** | Executive summary, takeaways (LLM) | `DocumentSummaries` |
| **S8** | Hover text per call (≤25 words) | Updated calls with tooltips |
| **S9** | Hybrid rule + LLM tagging | `TagSet` |
| **S10** | Quality scoring, review routing | `ConfidenceResult` |

## Output Schema

The pipeline produces `ProcessedDocument` with:

```python
ProcessedDocument(
    document_id="...",
    profile=DocumentProfile(
        manager_name="BlackRock Investment Institute",
        document_date="2024-Q4",
        document_type="QUARTERLY_OUTLOOK",
        regions=["GLOBAL", "US"],
        ...
    ),
    calls=CallExtractionOutput(
        allocation_calls=[
            AllocationCall(
                category="EQ_DM",
                sub_asset_class="US_LARGE_CAP",
                direction="OVERWEIGHT",
                conviction="HIGH",
                rationale_bullets=["...", "..."],
                tooltip_text="Overweight US large caps on earnings resilience",
                citations=[Citation(chunk_id="...", page=3, text_span="...")]
            ),
            ...
        ],
        overall_sentiment="NET_POSITIVE",
        key_risks=["..."],
    ),
    summaries=DocumentSummaries(
        executive_summary="...",
        search_descriptor="...",
        key_takeaways=[...],
    ),
    tags=TagSet(tags=[...]),
    confidence=ConfidenceResult(
        overall_score=0.85,
        band="HIGH",
        routing="AUTO_PUBLISH",
        ...
    ),
)
```

## Confidence & Review Routing

| Band | Score Range | Routing |
|------|-------------|---------|
| **HIGH** | ≥0.80 | Auto-publish (if no attention flags) |
| **MEDIUM** | 0.60–0.79 | Spot-check queue (20% sampling) |
| **LOW** | <0.60 | Must-review queue |

Attention flags that trigger review:
- Low text coverage (<50%)
- Uncertain manager name or document date
- Calls with evidence score <0.60
- No allocation calls extracted

## Tech Stack

| Component | Technology |
|-----------|------------|
| Language | Python 3.11+ |
| Data Validation | Pydantic v2 |
| PDF Extraction | PyMuPDF + pdfplumber |
| Vector Index | ChromaDB (in-memory) |
| Embeddings | OpenAI text-embedding-3-small |
| Database | SQLite (MVP) / PostgreSQL (production) |
| LLM Providers | OhMyGPT, MegaLLM, Nebius, DeepInfra |
| Type Checking | mypy (strict mode) |
| Linting | Ruff |
| Testing | pytest + pytest-asyncio |

## Project Structure

```
marketsrecon/
├── src/
│   ├── pipeline/
│   │   ├── run.py              # Orchestrator + CLI
│   │   ├── validate.py         # Output validator
│   │   └── stages/             # S0-S10 implementations
│   ├── models/                 # Pydantic schemas
│   ├── taxonomy/               # Asset class hierarchy + synonyms
│   ├── llm/                    # Multi-provider client + prompts
│   ├── extraction/             # PDF parsing
│   ├── retrieval/              # Chunking + vector indexing
│   ├── storage/                # Blob storage + database
│   └── config/                 # Settings + logging
├── tests/
│   ├── unit/                   # Model, taxonomy, LLM tests
│   ├── integration/            # Stage pipeline tests
│   ├── e2e/                    # End-to-end golden output tests
│   └── fixtures/               # Mock responses + test data
├── docs/                       # Specifications (read-only reference)
│   ├── ARCHITECTURE.md
│   ├── PIPELINE.md
│   ├── SCHEMAS.md
│   ├── TAXONOMY.md
│   ├── LLM_CONTRACTS.md
│   ├── CONFIDENCE.md
│   └── TESTING.md
├── CLAUDE.md                   # Mission + coding guidelines
├── PROGRESS.md                 # Task execution log
└── pyproject.toml              # Project configuration
```

## Documentation

| Document | Purpose |
|----------|---------|
| [`CLAUDE.md`](CLAUDE.md) | Project mission, constraints, quick reference |
| [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md) | System design and data flow |
| [`docs/PIPELINE.md`](docs/PIPELINE.md) | Stage-by-stage specification |
| [`docs/SCHEMAS.md`](docs/SCHEMAS.md) | Pydantic models and enums |
| [`docs/TAXONOMY.md`](docs/TAXONOMY.md) | Asset class hierarchy |
| [`docs/LLM_CONTRACTS.md`](docs/LLM_CONTRACTS.md) | Prompt templates and guardrails |
| [`docs/CONFIDENCE.md`](docs/CONFIDENCE.md) | Scoring logic and thresholds |
| [`docs/TESTING.md`](docs/TESTING.md) | Test strategy and fixtures |

## MVP Success Criteria

| Metric | Target | Status |
|--------|--------|--------|
| PDFs processed without crash | ≥90% | Pending evaluation |
| Calls extracted per PDF (avg) | ≥3 | Pending evaluation |
| Citations present per call | 100% | Enforced by schema |
| Processing time per PDF | <3 min | Pending evaluation |
| Test coverage | Comprehensive | 585 tests passing |

## Deferred to v1+

- OCR for scanned PDFs
- Vision-based chart/heatmap analysis
- Stage 6 verification pass (two-pass extraction)
- Review UI (currently manual JSON inspection)
- OpenSearch/Elasticsearch integration
- Queue-based batch processing

## License

MIT
