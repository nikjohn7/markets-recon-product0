"""Stage 7: Summary generation prompt.

This prompt generates executive summary, search descriptor,
and key takeaways from extracted calls and document content.
"""

from __future__ import annotations

import json
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from src.models.calls import AllocationCall
    from src.models.pipeline import RetrievedChunk
    from src.models.profile import DocumentProfile


def format_chunks_for_prompt(chunks: list[RetrievedChunk]) -> str:
    """Format retrieved chunks for inclusion in prompt.

    Args:
        chunks: List of retrieved chunks with metadata.

    Returns:
        Formatted string with chunk text and metadata.
    """
    formatted_parts: list[str] = []
    for chunk in chunks:
        header = f"[Chunk {chunk.chunk_id} | Page {chunk.page}]"
        formatted_parts.append(f"{header}\n{chunk.text}")
    return "\n\n---\n\n".join(formatted_parts)


def format_calls_summary(calls: list[AllocationCall]) -> str:
    """Format extracted calls for summary context.

    Args:
        calls: List of allocation calls extracted from document.

    Returns:
        Formatted string summarizing the calls.
    """
    if not calls:
        return "No allocation calls extracted."

    lines: list[str] = []
    for call in calls:
        direction = call.call.value
        conviction = f" ({call.conviction.value})" if call.conviction else ""
        lines.append(f"- {call.sub_asset_class}: {direction}{conviction}")

    return "\n".join(lines)


def get_summary_generation_schema() -> dict[str, object]:
    """Get JSON schema for summary generation output.

    Returns a schema that maps to DocumentSummaries model.
    """
    return {
        "type": "object",
        "required": [
            "executive_summary",
            "search_descriptor",
            "key_takeaways",
            "citations",
        ],
        "properties": {
            "executive_summary": {
                "type": "string",
                "minLength": 100,
                "maxLength": 1000,
                "description": "120-180 words executive summary",
            },
            "search_descriptor": {
                "type": "string",
                "minLength": 50,
                "maxLength": 200,
                "description": "20-35 word search descriptor",
            },
            "key_takeaways": {
                "type": "array",
                "minItems": 3,
                "maxItems": 5,
                "items": {
                    "type": "object",
                    "required": ["text", "citations"],
                    "properties": {
                        "text": {
                            "type": "string",
                            "maxLength": 200,
                            "description": "Actionable insight (≤200 chars)",
                        },
                        "citations": {
                            "type": "array",
                            "minItems": 1,
                            "items": {
                                "type": "object",
                                "required": ["chunk_id", "page"],
                                "properties": {
                                    "chunk_id": {"type": "string"},
                                    "page": {"type": "integer", "minimum": 1},
                                    "text_span": {
                                        "type": "string",
                                        "maxLength": 200,
                                    },
                                },
                            },
                        },
                    },
                },
            },
            "citations": {
                "type": "array",
                "minItems": 1,
                "items": {
                    "type": "object",
                    "required": ["chunk_id", "page"],
                    "properties": {
                        "chunk_id": {"type": "string"},
                        "page": {"type": "integer", "minimum": 1},
                        "text_span": {"type": "string", "maxLength": 200},
                    },
                },
                "description": "Citations for executive summary",
            },
            "confidence": {
                "type": "number",
                "minimum": 0,
                "maximum": 1,
                "description": "Summary generation confidence (0-1)",
            },
        },
    }


SUMMARY_GENERATION_PROMPT = """You are generating summaries for an investment research document.

## Document Profile
Manager: {manager_name}
Type: {document_type}
Date: {publication_date}

## Extracted Calls (summarized)
{calls_summary}

## Retrieved Key Passages
{chunks}

## Task
Generate three summary types:

### 1. Executive Summary (120-180 words)
For time-constrained allocators. Must include:
- Top 2-3 macro drivers (economic themes)
- Top 3 allocation calls (with direction: OW/N/UW)
- 2 key risks
- Use attribution: "The manager argues...", "The note states..."

Format as flowing prose, not bullets. Be specific about asset classes and directions.

### 2. Search Descriptor (20-35 words)
One sentence combining:
- What this document is (type + focus)
- What it implies (main recommendation)
- Main asset focus

Example: "Mid-year outlook emphasizing easing inflation but sticky growth; prefers quality equities and core duration while cautious on HY spreads; highlights policy risk into year-end."

### 3. Key Takeaways (3-5 bullets)
Each bullet:
- ≤200 characters
- Actionable insight (not generic observation)
- Must have citation (chunk_id + page)

Good: "Favor IG credit over HY as spreads have compressed; quality bias warranted given late-cycle dynamics."
Bad: "Credit markets face challenges ahead." (too vague, no action)

## Output Schema
{schema}

## Rules
1. WORD COUNTS ARE MANDATORY - executive summary must be 120-180 words
2. Do NOT include information not in the excerpts
3. Do NOT invent statistics, dates, or quotes
4. Every key takeaway MUST have a citation
5. Use manager's voice: "The manager expects...", "The outlook suggests..."

## Critical Guardrails
- If the excerpts lack sufficient detail for a summary component, note the limitation
- Never fabricate views or calls not present in source text
- Attribution should be clear (who said what)

## Output (JSON only, no explanation)
"""


def build_summary_generation_prompt(
    chunks: list[RetrievedChunk],
    calls: list[AllocationCall],
    profile: DocumentProfile,
) -> str:
    """Build the complete summary generation prompt.

    Args:
        chunks: Retrieved key passages for context.
        calls: Extracted allocation calls to summarize.
        profile: Document profile with metadata.

    Returns:
        Complete prompt string ready for LLM.
    """
    pub_date = profile.publication_date.isoformat() if profile.publication_date else "Unknown"

    return SUMMARY_GENERATION_PROMPT.format(
        manager_name=profile.manager_name,
        document_type=profile.document_type.value,
        publication_date=pub_date,
        calls_summary=format_calls_summary(calls),
        chunks=format_chunks_for_prompt(chunks),
        schema=json.dumps(get_summary_generation_schema(), indent=2),
    )


def get_summary_generation_prompt_template() -> str:
    """Get the raw prompt template string.

    Returns:
        The prompt template with placeholders.
    """
    return SUMMARY_GENERATION_PROMPT
