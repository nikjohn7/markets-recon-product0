"""Stage 6 Verification Pass: Call verification prompt.

This prompt verifies allocation call extractions by having an independent LLM
pass review the original extraction against the source excerpts.

Note: This is deferred to v1+ per CLAUDE.md, but the prompt template is
provided for completeness.
"""

from __future__ import annotations

import json
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from src.models.calls import AllocationCall
    from src.models.pipeline import RetrievedChunk


def format_chunks_for_verification(chunks: list[RetrievedChunk]) -> str:
    """Format retrieved chunks for verification prompt.

    Args:
        chunks: List of retrieved chunks used in original extraction.

    Returns:
        Formatted string with chunk text and metadata.
    """
    formatted_parts: list[str] = []
    for chunk in chunks:
        header = f"[Chunk {chunk.chunk_id} | Page {chunk.page}]"
        formatted_parts.append(f"{header}\n{chunk.text}")
    return "\n\n---\n\n".join(formatted_parts)


def format_calls_for_verification(calls: list[AllocationCall]) -> str:
    """Format extracted calls for verification review.

    Args:
        calls: List of allocation calls to verify.

    Returns:
        Formatted JSON string with call details.
    """
    call_list = []
    for i, call in enumerate(calls):
        call_data = {
            "index": i,
            "asset_class_category": call.asset_class_category,
            "sub_asset_class": call.sub_asset_class,
            "call": call.call.value,
            "conviction": call.conviction.value if call.conviction else None,
            "rationale_bullets": call.rationale_bullets,
            "citations": [
                {
                    "chunk_id": c.chunk_id,
                    "page": c.page,
                    "text_span": c.text_span,
                }
                for c in call.citations
            ],
        }
        call_list.append(call_data)

    return json.dumps(call_list, indent=2)


def get_verification_schema() -> dict[str, object]:
    """Get JSON schema for verification output.

    Returns:
        Schema for verification result.
    """
    return {
        "type": "object",
        "required": ["verified_calls", "agreement_rate"],
        "properties": {
            "verified_calls": {
                "type": "array",
                "items": {
                    "type": "object",
                    "required": ["original_index", "call_verified"],
                    "properties": {
                        "original_index": {
                            "type": "integer",
                            "minimum": 0,
                            "description": "Index of the call in original extraction",
                        },
                        "call_verified": {
                            "type": "boolean",
                            "description": "True if call direction is correctly supported",
                        },
                        "direction_correct": {
                            "type": "boolean",
                            "description": "True if OW/N/UW direction matches evidence",
                        },
                        "taxonomy_correct": {
                            "type": "boolean",
                            "description": "True if asset class mapping is correct",
                        },
                        "rationale_accurate": {
                            "type": "boolean",
                            "description": "True if rationale bullets match source",
                        },
                        "disagreement_reason": {
                            "type": ["string", "null"],
                            "description": "Explanation if not verified",
                        },
                        "suggested_call": {
                            "type": ["string", "null"],
                            "enum": ["OVERWEIGHT", "NEUTRAL", "UNDERWEIGHT", "UNCERTAIN", None],
                            "description": "Corrected direction if disagreement",
                        },
                        "evidence_strength": {
                            "type": "string",
                            "enum": ["STRONG", "MODERATE", "WEAK"],
                            "description": "How well the evidence supports the call",
                        },
                    },
                },
            },
            "agreement_rate": {
                "type": "number",
                "minimum": 0,
                "maximum": 1,
                "description": "Fraction of calls verified (0-1)",
            },
            "overall_quality": {
                "type": "string",
                "enum": ["HIGH", "MEDIUM", "LOW"],
                "description": "Overall extraction quality assessment",
            },
            "reviewer_notes": {
                "type": ["string", "null"],
                "description": "General notes about extraction quality",
            },
        },
    }


VERIFICATION_PROMPT = """You are verifying allocation call extractions.

## Original Extraction
{original_calls}

## Source Excerpts (same as original extraction)
{chunks}

## Task
For each call, independently verify:

1. **Direction (OW/N/UW)**: Is the call direction supported by the excerpt text?
   - Look for explicit positioning language
   - Consider context and qualifiers
   - If ambiguous, mark as not verified with reason

2. **Taxonomy Mapping**: Is the asset class category and sub-asset correct?
   - Verify the mentioned asset maps to the taxonomy code
   - Check for overly broad or narrow mappings

3. **Rationale Accuracy**: Do the rationale bullets accurately reflect the source?
   - Each bullet should trace to specific excerpt text
   - No fabricated reasoning or unsupported claims

4. **Evidence Strength**: How well does the evidence support the call?
   - STRONG: Explicit "we are overweight X" type language
   - MODERATE: Clear implied positioning ("we prefer", "we favor")
   - WEAK: Ambiguous or requires significant inference

## Verification Criteria

Mark a call as verified (call_verified=true) only if:
- Direction matches excerpt evidence
- Taxonomy mapping is reasonable
- Rationale is supported by text

Mark as not verified (call_verified=false) if:
- Direction is contradicted by evidence
- Direction requires significant inference not supported
- Major rationale claims are unsupported
- Taxonomy is clearly wrong

## Output Schema
{schema}

## Critical Instructions
- Be CRITICAL. If evidence is weak, flag it
- Cite specific text when disagreeing
- Provide corrected direction if you disagree
- Calculate agreement_rate as (verified_count / total_count)

## Output (JSON only, no explanation)
"""


def build_verification_prompt(
    calls: list[AllocationCall],
    chunks: list[RetrievedChunk],
) -> str:
    """Build the complete verification prompt.

    Args:
        calls: Original extracted allocation calls to verify.
        chunks: Source chunks used in original extraction.

    Returns:
        Complete prompt string ready for LLM.
    """
    return VERIFICATION_PROMPT.format(
        original_calls=format_calls_for_verification(calls),
        chunks=format_chunks_for_verification(chunks),
        schema=json.dumps(get_verification_schema(), indent=2),
    )


def get_verification_prompt_template() -> str:
    """Get the raw prompt template string.

    Returns:
        The prompt template with placeholders.
    """
    return VERIFICATION_PROMPT
