---
name: testing
description: Testing requirements and standards for this project. Use when writing tests, running test suites, creating fixtures, or validating test coverage. Requires pytest.
---

# Testing Requirements

**Full specification:** See [`docs/TESTING.md`](docs/TESTING.md)

## Test Commands

```bash
# Run all tests
pytest tests/ -v

# Run specific test categories
pytest tests/unit/ -v
pytest tests/integration/ -v
pytest tests/e2e/ -v

# Run with coverage
pytest tests/ --cov=src --cov-report=term-missing
```

## Minimum Coverage Requirements

### Unit Tests
- All Pydantic models (validation edge cases)
- Taxonomy mapping logic
- Exception hierarchy

### Integration Tests
- Each pipeline stage (0-10)
- Stage-to-stage data flow

### End-to-End Tests
- 5+ real PDFs covering different manager formats
- Golden output tests: known input -> expected output

## Test Structure

```
tests/
├── conftest.py          # Shared fixtures
├── fixtures/            # Sample PDFs, expected outputs
├── unit/                # Fast, isolated tests
├── integration/         # Stage-level tests
└── e2e/                 # Full pipeline tests
```

## Test Naming Conventions

```python
# Unit test file
tests/unit/models/test_calls.py

# Test function naming
def test_allocation_call_requires_citations():
    """Test that AllocationCall validation fails without citations."""
    ...

def test_taxonomy_mapping_with_synonym():
    """Test synonym resolution returns correct category and sub-asset."""
    ...
```

## PR Requirements

**Every PR must include tests for changed code.**

- New features: Add corresponding unit tests
- Bug fixes: Add regression tests
- Refactoring: Ensure existing tests still pass

## Golden Output Tests

For deterministic validation, maintain golden output files:

```python
def test_golden_output_blackrock_outlook():
    """Verify extraction matches expected output for BlackRock PDF."""
    pdf_path = "tests/fixtures/blackrock_outlook_2024.pdf"
    expected = load_json("tests/fixtures/expected/blackrock_outlook_2024.json")

    result = run_pipeline(pdf_path)
    assert result.model_dump() == expected
```

## Async Test Support

Use pytest-asyncio for async tests:

```python
import pytest

@pytest.mark.asyncio
async def test_stage_extract_async():
    result = await stage_extract(ingest_result)
    assert result.extraction_coverage > 0.5
```
