---
name: pre-commit
description: Pre-commit checklist for code validation before committing. Use before staging files for commit to verify type checking, linting, tests, and code quality requirements pass.
---

# Pre-Commit Checklist

Run these checks **before committing code** to ensure quality standards are met.

## Required Checks

### 1. Type Checking
```bash
mypy src/ --strict
```
Must pass with zero errors.

### 2. Linting
```bash
ruff check src/ tests/ --select=E9,F63,F7,F82
```
Must pass with zero errors.

### 3. Tests
```bash
pytest tests/
```
All tests must pass.


## Code Quality Verification

Before committing, verify:

- [ ] New code has corresponding tests
- [ ] Pydantic models match `docs/SCHEMAS.md`
- [ ] LLM prompts follow `docs/LLM_CONTRACTS.md`
- [ ] No raw dicts crossing function boundaries
- [ ] All type annotations are present (no `Any` unless unavoidable)

## Quick All-in-One Check

Run all checks in sequence:

```bash
mypy src/ --strict && ruff check src/ tests/ --select=E9,F63,F7,F82 && pytest tests/
```

If any check fails, fix the issues before committing.

## Common Issues

### Type Errors
- Missing return type annotations
- Using `Any` when specific types are available
- Incompatible types in function arguments

### Lint Errors (with --select=E9,F63,F7,F82)
- Syntax errors preventing module import (E9)
- Invalid print statements, e.g., `print >>` syntax (F63)
- Syntax errors in type comments (F7)
- Undefined names (F82)

### Test Failures
- Check test output for specific failures
- Run individual test: `pytest tests/path/to/test.py::test_function -v`
