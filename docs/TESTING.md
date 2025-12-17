# Testing Strategy

This document defines testing requirements, fixtures, and acceptance criteria for the pipeline.

---

## Testing Principles

1. **Every PR must include tests** for changed code
2. **Unit tests for all Pydantic models** (validation edge cases)
3. **Integration tests for each pipeline stage** (input → output)
4. **E2E tests with real PDFs** (golden output comparison)
5. **Confidence scoring tests** (calibration verification)

---

## Test Categories

### Unit Tests

Test individual functions and classes in isolation.

```
tests/unit/
├── models/
│   ├── test_document.py
│   ├── test_calls.py
│   ├── test_summaries.py
│   └── test_confidence.py
├── taxonomy/
│   ├── test_hierarchy.py
│   └── test_synonyms.py
├── extraction/
│   ├── test_parser.py
│   └── test_ocr.py
└── llm/
    └── test_contracts.py
```

### Integration Tests

Test pipeline stages with real (but controlled) inputs.

```
tests/integration/
├── test_stage_ingest.py
├── test_stage_extract.py
├── test_stage_clean.py
├── test_stage_index.py
├── test_stage_metadata.py
├── test_stage_candidates.py
├── test_stage_calls.py
├── test_stage_summaries.py
├── test_stage_tooltips.py
├── test_stage_tags.py
└── test_stage_confidence.py
```

### E2E Tests

Test full pipeline with real PDFs and expected outputs.

```
tests/e2e/
├── test_full_pipeline.py
└── golden_outputs/
    ├── blackrock_midyear_2025.json
    ├── pimco_quarterly_q2_2025.json
    └── ...
```

---

## Fixtures

### Sample PDFs

Maintain a set of representative PDFs for testing:

```
tests/fixtures/pdfs/
├── standard/
│   ├── blackrock_midyear_2025.pdf      # Clean, text-based
│   ├── pimco_quarterly_q2_2025.pdf     # Tables + charts
│   └── jpmorgan_annual_2025.pdf        # Multi-asset
├── edge_cases/
│   ├── scanned_low_quality.pdf         # Requires OCR
│   ├── heatmap_only.pdf                # Requires vision
│   ├── no_explicit_calls.pdf           # Thematic piece
│   ├── multiple_managers.pdf           # Multi-manager note
│   └── non_english.pdf                 # Localization
└── expected_outputs/
    ├── blackrock_midyear_2025.json
    └── ...
```

### Mock LLM Responses

For deterministic testing without API calls:

```python
# tests/fixtures/llm_responses.py

MOCK_METADATA_RESPONSE = {
    "manager_name": "BlackRock",
    "title": "Mid-Year Investment Outlook 2025",
    "publication_date": "2025-07-15",
    "document_type": "MID_YEAR_OUTLOOK",
    "asset_classes_covered": ["EQUITIES", "FIXED_INCOME"],
    "citations": [{"chunk_id": "1_3", "page": 1}]
}

MOCK_CALLS_RESPONSE = {
    "allocation_calls": [
        {
            "asset_class_category": "FI_SOV_EUROPE",
            "sub_asset_class": "GERMAN_BUNDS",
            "call": "OVERWEIGHT",
            "conviction": "MEDIUM",
            "rationale_bullets": ["ECB easing cycle supportive", "Safe-haven demand"],
            "citations": [{"chunk_id": "4_7", "page": 4}],
            "confidence": 0.85
        }
    ],
    "overall_sentiment": "NEUTRAL",
    "sentiment_rationale": ["Balanced outlook"],
    "sentiment_citations": [{"chunk_id": "2_1", "page": 2}]
}
```

---

## Unit Test Examples

### Model Validation Tests

```python
# tests/unit/models/test_calls.py

import pytest
from src.models.calls import AllocationCall, CallDirection

class TestAllocationCall:
    def test_valid_call(self):
        call = AllocationCall(
            asset_class_category="FI_SOV_EUROPE",
            sub_asset_class="GERMAN_BUNDS",
            call=CallDirection.OVERWEIGHT,
            rationale_bullets=["ECB policy supportive"],
            citations=[{"chunk_id": "4_7", "page": 4}],
            confidence=0.85
        )
        assert call.call == CallDirection.OVERWEIGHT
    
    def test_empty_rationale_rejected(self):
        with pytest.raises(ValidationError):
            AllocationCall(
                asset_class_category="FI_SOV_EUROPE",
                sub_asset_class="GERMAN_BUNDS",
                call=CallDirection.OVERWEIGHT,
                rationale_bullets=[],  # Empty not allowed
                citations=[{"chunk_id": "4_7", "page": 4}],
                confidence=0.85
            )
    
    def test_missing_citations_rejected(self):
        with pytest.raises(ValidationError):
            AllocationCall(
                asset_class_category="FI_SOV_EUROPE",
                sub_asset_class="GERMAN_BUNDS",
                call=CallDirection.OVERWEIGHT,
                rationale_bullets=["Reason"],
                citations=[],  # Must have at least 1
                confidence=0.85
            )
    
    def test_confidence_bounds(self):
        with pytest.raises(ValidationError):
            AllocationCall(
                asset_class_category="FI_SOV_EUROPE",
                sub_asset_class="GERMAN_BUNDS",
                call=CallDirection.OVERWEIGHT,
                rationale_bullets=["Reason"],
                citations=[{"chunk_id": "4_7", "page": 4}],
                confidence=1.5  # Out of bounds
            )
    
    def test_uncertain_call_requires_review_flag(self):
        """UNCERTAIN call should be valid and require review flag."""
        call = AllocationCall(
            asset_class_category="FI_SOV_EUROPE",
            sub_asset_class="GERMAN_BUNDS",
            call=CallDirection.UNCERTAIN,
            rationale_bullets=["Unclear positioning"],
            citations=[{"chunk_id": "4_7", "page": 4}],
            confidence=0.3,
            needs_analyst_review=True,
            review_reason="Ambiguous language"
        )
        assert call.call == CallDirection.UNCERTAIN
        assert call.needs_analyst_review is True
```

### Taxonomy Tests

```python
# tests/unit/taxonomy/test_synonyms.py

from src.taxonomy.synonyms import resolve_asset, SYNONYMS

class TestSynonymResolution:
    def test_exact_match(self):
        result = resolve_asset("Bunds")
        assert result == ("FI_SOV_EUROPE", "GERMAN_BUNDS")
    
    def test_case_insensitive(self):
        result = resolve_asset("GERMAN BUNDS")
        assert result == ("FI_SOV_EUROPE", "GERMAN_BUNDS")
    
    def test_common_variant(self):
        result = resolve_asset("US Treasuries")
        assert result == ("FI_SOV_NA", "US_TREASURIES")
    
    def test_unknown_returns_none(self):
        result = resolve_asset("Nonexistent Asset XYZ")
        assert result is None
    
    def test_all_synonyms_resolve(self):
        """Every synonym in the map should resolve to valid taxonomy."""
        for synonym, code in SYNONYMS.items():
            result = resolve_asset(synonym)
            assert result is not None, f"Synonym '{synonym}' failed to resolve"
```

---

## Integration Test Examples

### Stage Tests

```python
# tests/integration/test_stage_extract.py

import pytest
from pathlib import Path
from src.pipeline.stages.s1_extract import stage_extract
from src.models.document import DocumentJSON

@pytest.fixture
def sample_pdf():
    return Path("tests/fixtures/pdfs/standard/blackrock_midyear_2025.pdf")

@pytest.fixture
def scanned_pdf():
    return Path("tests/fixtures/pdfs/edge_cases/scanned_low_quality.pdf")

class TestStageExtract:
    async def test_extracts_text_from_clean_pdf(self, sample_pdf):
        """Clean PDFs should have high extraction coverage."""
        result = await stage_extract(sample_pdf)
        
        assert isinstance(result, DocumentJSON)
        assert result.extraction_coverage >= 0.90
        assert len(result.blocks) > 50
        assert result.page_count > 0
    
    async def test_triggers_ocr_for_scanned(self, scanned_pdf):
        """Scanned PDFs should trigger OCR."""
        result = await stage_extract(scanned_pdf)
        
        assert len(result.ocr_pages) > 0
        assert result.extraction_coverage >= 0.50  # Lower threshold for OCR
    
    async def test_detects_tables(self, sample_pdf):
        """Should detect and extract tables."""
        result = await stage_extract(sample_pdf)
        
        assert len(result.tables) > 0
        for table in result.tables:
            assert table.row_count > 0
            assert table.col_count > 0
    
    async def test_block_ids_unique(self, sample_pdf):
        """Every block should have unique ID."""
        result = await stage_extract(sample_pdf)
        
        block_ids = [b.block_id for b in result.blocks]
        assert len(block_ids) == len(set(block_ids))
    
    async def test_pages_sequential(self, sample_pdf):
        """Block pages should be sequential, 1-indexed."""
        result = await stage_extract(sample_pdf)
        
        pages = sorted(set(b.page for b in result.blocks))
        assert pages[0] == 1
        assert pages[-1] == result.page_count
```

### LLM Stage Tests (with mocks)

```python
# tests/integration/test_stage_calls.py

import pytest
from unittest.mock import AsyncMock, patch
from src.pipeline.stages.s6_calls import stage_calls
from src.models.calls import CallExtractionOutput

@pytest.fixture
def mock_llm_client():
    client = AsyncMock()
    client.complete.return_value = MOCK_CALLS_RESPONSE
    return client

@pytest.fixture
def sample_document():
    # Load pre-extracted document fixture
    return load_fixture("document_json/blackrock_midyear_2025.json")

@pytest.fixture
def sample_index():
    # Load pre-built retrieval index
    return load_fixture("retrieval_index/blackrock_midyear_2025.pkl")

class TestStageCalls:
    @patch("src.llm.client.LLMClient")
    async def test_extracts_calls_from_document(
        self, mock_client_class, mock_llm_client, sample_document, sample_index
    ):
        mock_client_class.return_value = mock_llm_client
        
        result = await stage_calls(sample_document, sample_index)
        
        assert isinstance(result, CallExtractionOutput)
        assert len(result.allocation_calls) > 0
    
    @patch("src.llm.client.LLMClient")
    async def test_all_calls_have_citations(
        self, mock_client_class, mock_llm_client, sample_document, sample_index
    ):
        mock_client_class.return_value = mock_llm_client
        
        result = await stage_calls(sample_document, sample_index)
        
        for call in result.allocation_calls:
            assert len(call.citations) >= 1
    
    @patch("src.llm.client.LLMClient")
    async def test_taxonomy_mapping_valid(
        self, mock_client_class, mock_llm_client, sample_document, sample_index
    ):
        mock_client_class.return_value = mock_llm_client
        
        result = await stage_calls(sample_document, sample_index)
        
        for call in result.allocation_calls:
            assert is_valid_taxonomy_code(call.asset_class_category)
            assert is_valid_taxonomy_code(call.sub_asset_class)
```

---

## E2E Test Examples

### Golden Output Tests

```python
# tests/e2e/test_full_pipeline.py

import pytest
import json
from pathlib import Path
from src.pipeline.run import process_pdf
from src.models.output import ProcessedDocument

GOLDEN_OUTPUTS = Path("tests/e2e/golden_outputs")

class TestFullPipeline:
    @pytest.mark.parametrize("pdf_name", [
        "blackrock_midyear_2025",
        "pimco_quarterly_q2_2025",
        "jpmorgan_annual_2025",
    ])
    async def test_pipeline_matches_golden_output(self, pdf_name):
        """
        Full pipeline output should match golden reference.
        
        Note: This test may need tolerance for non-deterministic LLM outputs.
        We compare structure and key fields, not exact text.
        """
        pdf_path = Path(f"tests/fixtures/pdfs/standard/{pdf_name}.pdf")
        golden_path = GOLDEN_OUTPUTS / f"{pdf_name}.json"
        
        # Run pipeline
        result = await process_pdf(pdf_path.read_bytes(), {})
        
        # Load golden output
        with open(golden_path) as f:
            golden = json.load(f)
        
        # Compare structure
        assert result.profile.manager_name == golden["profile"]["manager_name"]
        assert result.profile.document_type == golden["profile"]["document_type"]
        
        # Compare call count (tolerance for minor differences)
        assert abs(len(result.allocation_calls) - len(golden["allocation_calls"])) <= 2
        
        # Compare asset classes covered
        result_assets = {c.asset_class_category for c in result.allocation_calls}
        golden_assets = {c["asset_class_category"] for c in golden["allocation_calls"]}
        assert result_assets == golden_assets
        
        # Compare sentiment
        assert result.overall_sentiment == golden["overall_sentiment"]
    
    async def test_pipeline_handles_no_calls_gracefully(self):
        """Thematic pieces without explicit calls should still process."""
        pdf_path = Path("tests/fixtures/pdfs/edge_cases/no_explicit_calls.pdf")
        
        result = await process_pdf(pdf_path.read_bytes(), {})
        
        # Should complete without error
        assert result is not None
        
        # May have zero calls
        assert len(result.allocation_calls) >= 0
        
        # Should still have summaries and tags
        assert result.summaries.executive_summary is not None
        assert len(result.tags.theme_tags) > 0
    
    async def test_pipeline_flags_low_quality_extraction(self):
        """Poor quality PDFs should be flagged for review."""
        pdf_path = Path("tests/fixtures/pdfs/edge_cases/scanned_low_quality.pdf")
        
        result = await process_pdf(pdf_path.read_bytes(), {})
        
        # Should flag for attention
        assert result.confidence.analyst_attention_required is True
        assert result.confidence.confidence_band in ["LOW", "MEDIUM"]
```

---

## Confidence Scoring Tests

```python
# tests/unit/test_confidence.py

import pytest
from src.pipeline.stages.s10_confidence import (
    score_evidence_strength,
    score_extraction_quality,
    compute_call_confidence,
)

class TestConfidenceScoring:
    def test_explicit_language_high_confidence(self):
        """Explicit call language should yield high confidence."""
        evidence_text = "We are overweight German Bunds due to ECB easing."
        
        score = score_evidence_strength(
            field_value="OVERWEIGHT",
            citations=[{"chunk_id": "4_7", "page": 4, "text_span": evidence_text}],
            source_chunks=[{"chunk_id": "4_7", "text": evidence_text}]
        )
        
        assert score >= 0.80
    
    def test_implicit_language_medium_confidence(self):
        """Implicit preference should yield medium confidence."""
        evidence_text = "We see attractive risk-reward in German Bunds."
        
        score = score_evidence_strength(
            field_value="OVERWEIGHT",  # Inferred, not explicit
            citations=[{"chunk_id": "4_7", "page": 4, "text_span": evidence_text}],
            source_chunks=[{"chunk_id": "4_7", "text": evidence_text}]
        )
        
        assert 0.50 <= score < 0.80
    
    def test_no_evidence_low_confidence(self):
        """Missing evidence should yield low confidence."""
        score = score_evidence_strength(
            field_value="OVERWEIGHT",
            citations=[],
            source_chunks=[]
        )
        
        assert score < 0.50
    
    def test_extraction_coverage_impacts_score(self):
        """Low extraction coverage should lower overall score."""
        doc = create_mock_document(extraction_coverage=0.40)
        
        score = score_extraction_quality(doc)
        
        assert score < 0.60


class TestConfidenceCalibration:
    def test_high_threshold_at_80(self):
        """HIGH band should require >= 0.80."""
        result = compute_document_confidence(score=0.79)
        assert result.confidence_band == "MEDIUM"
        
        result = compute_document_confidence(score=0.80)
        assert result.confidence_band == "HIGH"
    
    def test_low_threshold_at_60(self):
        """LOW band should be < 0.60."""
        result = compute_document_confidence(score=0.60)
        assert result.confidence_band == "MEDIUM"
        
        result = compute_document_confidence(score=0.59)
        assert result.confidence_band == "LOW"
```

---

## Test Running

### Commands

```bash
# Run all tests
pytest tests/ -v

# Run unit tests only
pytest tests/unit/ -v

# Run integration tests only
pytest tests/integration/ -v

# Run E2E tests only
pytest tests/e2e/ -v

# Run with coverage
pytest tests/ --cov=src --cov-report=html

# Run specific test file
pytest tests/unit/models/test_calls.py -v

# Run tests matching pattern
pytest -k "taxonomy" -v

# Run tests with LLM mocks only (no API calls)
pytest tests/ -v -m "not requires_llm_api"
```

### CI Configuration

```yaml
# .github/workflows/test.yml
name: Tests

on: [push, pull_request]

jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3
      
      - name: Set up Python
        uses: actions/setup-python@v4
        with:
          python-version: '3.11'
      
      - name: Install dependencies
        run: |
          pip install -r requirements.txt
          pip install -r requirements-dev.txt
      
      - name: Run type checking
        run: mypy src/ --strict
      
      - name: Run linting
        run: ruff check src/ tests/
      
      - name: Run unit tests
        run: pytest tests/unit/ -v --cov=src
      
      - name: Run integration tests
        run: pytest tests/integration/ -v
      
      - name: Upload coverage
        uses: codecov/codecov-action@v3
```

---

## Acceptance Criteria Summary

| Component | Metric | Target |
|-----------|--------|--------|
| Unit test coverage | Line coverage | ≥ 80% |
| Model validation | Edge cases covered | 100% |
| Pipeline stages | Each stage tested | 100% |
| Golden output tests | Documents tested | ≥ 5 |
| Confidence tests | Threshold calibration | Verified |
| E2E success rate | Pipeline completion | ≥ 95% |
