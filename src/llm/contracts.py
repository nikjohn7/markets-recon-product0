"""LLM output validation and guardrails.

Validation functions for citations, taxonomy integrity, and hallucination markers.
"""

from __future__ import annotations

import re
from collections.abc import Iterable, Sequence
from typing import TypeVar

from pydantic import BaseModel

from src.exceptions import ValidationError
from src.models.calls import AllocationCall
from src.models.core import Citation
from src.models.pipeline import Chunk, RetrievedChunk
from src.taxonomy.hierarchy import (
    get_category_for_sub_asset,
    is_valid_category,
    is_valid_sub_asset,
)

T = TypeVar("T", bound=BaseModel)

HALLUCINATION_MARKERS: tuple[re.Pattern[str], ...] = (
    re.compile(r"\d{4}-\d{2}-\d{2}"),
    re.compile(r"\d+(?:\.\d+)?%"),
    re.compile(r'\\"(?:[^"\\]|\\.){50,}\\"'),
)


def validate_llm_output(
    output: BaseModel,
    source_chunks: Sequence[Chunk | RetrievedChunk],
) -> BaseModel:
    """Validate LLM output against guardrails.

    Args:
        output: Validated Pydantic output from LLM.
        source_chunks: Retrieved chunks used to build the prompt.

    Returns:
        The output if it passes all checks.

    Raises:
        ValidationError: If citations, taxonomy, or hallucination checks fail.
    """
    allowed_chunk_ids = {chunk.chunk_id for chunk in source_chunks}
    validate_citations(output, allowed_chunk_ids)
    validate_taxonomy(output)

    hallucinations = find_hallucination_markers(output, source_chunks)
    if hallucinations:
        raise ValidationError(
            "Potential hallucination detected: " + ", ".join(sorted(hallucinations))
        )

    return output


def validate_citations(output: BaseModel, allowed_chunk_ids: set[str]) -> None:
    """Validate that all citations reference known chunk IDs.

    Args:
        output: LLM output model.
        allowed_chunk_ids: Set of valid chunk IDs from retrieval.

    Raises:
        ValidationError: If any citation references an unknown chunk_id.
    """
    citations = extract_citations(output)
    for citation in citations:
        if citation.chunk_id not in allowed_chunk_ids:
            raise ValidationError(f"Invalid citation chunk_id: {citation.chunk_id}")


def validate_taxonomy(output: BaseModel) -> None:
    """Validate allocation calls against taxonomy hierarchy.

    Args:
        output: LLM output model.

    Raises:
        ValidationError: If taxonomy category or sub-asset is invalid.
    """
    calls = extract_allocation_calls(output)
    for call in calls:
        if not is_valid_category(call.asset_class_category):
            raise ValidationError(f"Invalid asset_class_category: {call.asset_class_category}")
        if not is_valid_sub_asset(call.sub_asset_class):
            raise ValidationError(f"Invalid sub_asset_class: {call.sub_asset_class}")
        expected_category = get_category_for_sub_asset(call.sub_asset_class)
        if expected_category != call.asset_class_category:
            raise ValidationError(
                "Mismatched taxonomy: "
                f"{call.sub_asset_class} belongs to {expected_category}, "
                f"not {call.asset_class_category}"
            )


def find_hallucination_markers(
    output: BaseModel,
    source_chunks: Sequence[Chunk | RetrievedChunk],
) -> set[str]:
    """Identify hallucination markers not present in source text.

    Args:
        output: LLM output model.
        source_chunks: Retrieved chunks used to build the prompt.

    Returns:
        Set of hallucinated markers found in output.
    """
    output_text = output.model_dump_json()
    source_text = " ".join(chunk.text for chunk in source_chunks)
    hallucinations: set[str] = set()

    for pattern in HALLUCINATION_MARKERS:
        for match in pattern.findall(output_text):
            # Strip surrounding escaped quotes and unescape JSON escape sequences
            normalized = match
            if match.startswith('\\"') and match.endswith('\\"'):
                # Remove surrounding escaped quotes (\" ... \")
                normalized = match[2:-2]
                # Unescape JSON escape sequences
                normalized = normalized.replace('\\"', '"').replace("\\\\", "\\")
            if normalized not in source_text:
                hallucinations.add(match)

    return hallucinations


def extract_instances(output: BaseModel, target_type: type[T]) -> list[T]:
    """Recursively extract instances of a target type from a Pydantic model.

    Args:
        output: The root Pydantic model to traverse.
        target_type: The type to extract instances of.

    Returns:
        List of instances matching the target type.
    """
    instances: list[T] = []

    def visit(value: object) -> None:
        if isinstance(value, target_type):
            instances.append(value)
            return
        if isinstance(value, BaseModel):
            for field_name in value.__class__.model_fields:
                visit(getattr(value, field_name))
            return
        if isinstance(value, dict):
            for item in value.values():
                visit(item)
            return
        if isinstance(value, Iterable) and not isinstance(value, (str, bytes)):
            for item in value:
                visit(item)

    visit(output)
    return instances


def extract_citations(output: BaseModel) -> list[Citation]:
    """Recursively extract citations from a Pydantic model."""
    return extract_instances(output, Citation)


def extract_allocation_calls(output: BaseModel) -> list[AllocationCall]:
    """Recursively extract AllocationCall instances from output."""
    return extract_instances(output, AllocationCall)
