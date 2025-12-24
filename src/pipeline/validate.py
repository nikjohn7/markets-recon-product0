"""Output validation utility.

Validates ProcessedDocument JSON output for schema compliance,
citation validity, and taxonomy codes.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

from pydantic import ValidationError as PydanticValidationError

from src.models.output import ProcessedDocument
from src.taxonomy.hierarchy import is_valid_category, is_valid_sub_asset
from src.taxonomy.tags import (
    MACRO_REGIME_TAGS,
    REGION_TAGS,
    RISK_TAGS,
    THEME_TAGS,
)


def validate_schema(data: dict[str, Any]) -> list[str]:
    """Validate JSON against ProcessedDocument schema."""
    errors: list[str] = []
    try:
        ProcessedDocument.model_validate(data)
    except PydanticValidationError as e:
        for err in e.errors():
            loc = ".".join(str(x) for x in err["loc"])
            errors.append(f"Schema error at {loc}: {err['msg']}")
    return errors


def validate_taxonomy(data: dict[str, Any]) -> list[str]:
    """Validate taxonomy codes in allocation calls."""
    errors: list[str] = []
    for i, call in enumerate(data.get("allocation_calls", [])):
        cat = call.get("asset_class_category", "")
        sub = call.get("sub_asset_class", "")
        if not is_valid_category(cat):
            errors.append(f"Call {i}: invalid category '{cat}'")
        if not is_valid_sub_asset(sub):
            errors.append(f"Call {i}: invalid sub_asset '{sub}'")
    return errors


def validate_tags(data: dict[str, Any]) -> list[str]:
    """Validate tag values against allowed vocabularies."""
    errors: list[str] = []
    tags = data.get("tags", {})

    allowed = {
        "theme_tags": {t.lower() for t in THEME_TAGS},
        "risk_tags": {t.lower() for t in RISK_TAGS},
        "region_tags": {t.lower() for t in REGION_TAGS},
        "macro_regime_tags": {t.lower() for t in MACRO_REGIME_TAGS},
    }

    for tag_type, allowed_set in allowed.items():
        for tag in tags.get(tag_type, []):
            if tag.lower() not in allowed_set:
                errors.append(f"Invalid {tag_type} value: '{tag}'")

    return errors


def validate_citations(data: dict[str, Any]) -> list[str]:
    """Validate citation structure."""
    errors: list[str] = []

    # Check calls have citations
    for i, call in enumerate(data.get("allocation_calls", [])):
        citations = call.get("citations", [])
        if not citations:
            errors.append(f"Call {i}: missing citations")
        for j, cit in enumerate(citations):
            if not cit.get("chunk_id"):
                errors.append(f"Call {i} citation {j}: missing chunk_id")
            if not cit.get("page") or cit.get("page", 0) < 1:
                errors.append(f"Call {i} citation {j}: invalid page")

    # Check summaries have citations
    summaries = data.get("summaries", {})
    if not summaries.get("citations"):
        errors.append("Summaries: missing citations")

    return errors


def validate_output(data: dict[str, Any]) -> list[str]:
    """Run all validations and return list of errors."""
    errors: list[str] = []
    errors.extend(validate_schema(data))
    if not errors:  # Only check details if schema is valid
        errors.extend(validate_taxonomy(data))
        errors.extend(validate_tags(data))
        errors.extend(validate_citations(data))
    return errors


def _build_parser() -> argparse.ArgumentParser:
    """Build CLI argument parser."""
    parser = argparse.ArgumentParser(
        prog="python -m pipeline.validate",
        description="Validate pipeline output JSON",
    )
    parser.add_argument(
        "--output",
        type=Path,
        required=True,
        help="Path to output JSON file to validate",
    )
    return parser


def main() -> None:
    """CLI entrypoint for validator."""
    parser = _build_parser()
    args = parser.parse_args()

    if not args.output.exists():
        print(f"Error: File not found: {args.output}", file=sys.stderr)
        sys.exit(1)

    try:
        data = json.loads(args.output.read_text())
    except json.JSONDecodeError as e:
        print(f"Error: Invalid JSON: {e}", file=sys.stderr)
        sys.exit(1)

    errors = validate_output(data)

    if errors:
        print(f"Validation failed with {len(errors)} error(s):", file=sys.stderr)
        for err in errors:
            print(f"  - {err}", file=sys.stderr)
        sys.exit(1)
    else:
        print("Validation passed")
        sys.exit(0)


if __name__ == "__main__":
    main()
