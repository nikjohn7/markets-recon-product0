---
name: code-quality
description: Code standards and style requirements for this project (typing, mypy --strict, lint/ruff, Pydantic). Use when writing new code, reviewing code, or refactoring.
---

# Code Quality Standards

## When to Use

- You are implementing or refactoring code and want the project’s standards (typing, Pydantic boundaries, error handling)
- You are fixing `mypy`/typing issues or addressing lint/ruff feedback

## When Not to Use

- You only need the canonical “what to run before commit” command set (use `.claude/skills/pre-commit/SKILL.md` instead)

## Absolute Requirements

1. **Type everything.** No `Any` unless unavoidable. Type-check in strict mode (see `.claude/skills/pre-commit/SKILL.md` for the exact `mypy` command).
2. **Pydantic for all data.** No raw dicts crossing function boundaries.
3. **Every LLM output validated** against schema before use.
4. **Citations mandatory.** If a field comes from the document, include `citations: list[Citation]`.
5. **Fail loud.** Raise exceptions for invalid states; never silently continue.
6. **Idempotent stages.** Re-running a stage with same input = same output.

## Style Guide

### Good: Explicit, Typed, Validated

```python
async def extract_calls(
    doc: DocumentJSON,
    taxonomy: AssetTaxonomy,
) -> list[AllocationCall]:
    ...
```

### Bad: Vague, Untyped, Implicit

```python
def process(data, config):
    ...
```

## Error Handling

Use domain-specific exceptions from `src/exceptions.py`:

```python
from src.exceptions import (
    ExtractionError,
    WeakEvidenceError,
    TaxonomyMappingError,
    ValidationError,
    LLMError,
    StorageError,
)

# Raise specific exceptions
if not citations:
    raise WeakEvidenceError("No evidence found for claim")

if not resolve_asset(raw_asset):
    raise TaxonomyMappingError(f"Unknown asset: {raw_asset}")
```

### Exception Hierarchy

```
PipelineError (base)
├── ExtractionError
│   ├── WeakEvidenceError
│   └── TaxonomyMappingError
├── ValidationError
├── LLMError
└── StorageError
```

## Function Signatures

### Required Elements

- Type hints for all parameters
- Return type annotation
- Docstring for public functions

```python
async def stage_extract(
    ingest_result: IngestResult,
    storage: LocalBlobStorage | None = None,
) -> DocumentJSON:
    """Extract text and tables from PDF.

    Args:
        ingest_result: Result from Stage 0 ingest
        storage: Optional blob storage (uses default if None)

    Returns:
        DocumentJSON with extracted blocks and tables

    Raises:
        StorageError: If PDF cannot be retrieved
        ExtractionError: If extraction fails
    """
    ...
```

## Pydantic Model Conventions

```python
from pydantic import BaseModel, Field

class AllocationCall(BaseModel):
    """A single allocation call extracted from the document."""

    asset_class: str = Field(
        ...,
        description="Taxonomy sub-asset code",
        min_length=1,
    )
    direction: CallDirection
    conviction: Conviction
    citations: list[Citation] = Field(
        ...,
        min_length=1,
        max_length=3,
    )

    model_config = {"frozen": True}
```

## Avoid Over-Engineering

- Don't add features beyond what's asked
- Don't refactor surrounding code unless necessary
- Don't add error handling for scenarios that can't happen
- Don't create abstractions for one-time operations
