"""Stage 8: Tooltip generation prompt.

This prompt generates concise hover text for each allocation call,
summarizing the positioning and key rationale.
"""

from __future__ import annotations

import json
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from src.models.calls import AllocationCall


def format_calls_for_tooltip_prompt(calls: list[AllocationCall]) -> str:
    """Format allocation calls for tooltip generation.

    Args:
        calls: List of allocation calls needing tooltips.

    Returns:
        Formatted string with call details for tooltip generation.
    """
    formatted_parts: list[str] = []

    for i, call in enumerate(calls):
        direction = call.call.value
        conviction = f" ({call.conviction.value} conviction)" if call.conviction else ""
        rationale = "; ".join(call.rationale_bullets[:2])  # First 2 bullets
        risks = ", ".join(call.key_risks[:2]) if call.key_risks else "None specified"

        formatted_parts.append(
            f"[Call {i}]\n"
            f"Asset: {call.sub_asset_class} ({call.asset_class_category})\n"
            f"Direction: {direction}{conviction}\n"
            f"Rationale: {rationale}\n"
            f"Risks: {risks}"
        )

    return "\n\n".join(formatted_parts)


def get_tooltip_generation_schema() -> dict[str, object]:
    """Get JSON schema for tooltip generation output.

    Returns:
        Schema for tooltip output.
    """
    return {
        "type": "object",
        "required": ["tooltips"],
        "properties": {
            "tooltips": {
                "type": "array",
                "items": {
                    "type": "object",
                    "required": ["sub_asset_class", "tooltip_text"],
                    "properties": {
                        "sub_asset_class": {
                            "type": "string",
                            "description": "The sub-asset code from the call",
                        },
                        "tooltip_text": {
                            "type": "string",
                            "maxLength": 150,
                            "description": "Concise hover text (≤25 words, ≤150 chars)",
                        },
                    },
                },
            },
        },
    }


TOOLTIP_GENERATION_PROMPT = """Generate concise hover text for each allocation call.

## Calls
{calls}

## Task
For each call, generate a tooltip that:
- Is ≤25 words (max 150 characters)
- Summarizes the positioning and key reason
- Is specific (not generic)
- Optionally includes a "watch item" for key risks/catalysts

## Format
Combine these elements concisely:
1. Direction + asset (e.g., "Overweight Bunds")
2. Primary reason (e.g., "as quality hedge")
3. Key driver or catalyst (e.g., "expects easing inflation")
4. Optional watch item (e.g., "watch ECB policy")

## Examples

Good tooltips:
- "Overweight Bunds as quality hedge; expects easing inflation and flight-to-safety if risk rises."
- "Underweight US HY on tight spreads; watch Fed policy pivot and recession signals."
- "Neutral on EM equities; balanced China recovery optimism against geopolitical headwinds."
- "Overweight US large-cap tech on AI capex tailwinds; stretched valuations warrant selectivity."

Bad tooltips (avoid):
- "Positive on European bonds due to macro factors." (too generic)
- "Cautious on high yield." (no rationale)
- "We like this asset class." (uninformative)
- "The manager recommends..." (don't start with "The manager")

## Output Schema
{schema}

## Rules
1. One tooltip per call, in same order as input
2. Match sub_asset_class exactly as provided
3. Be specific - mention the actual drivers, not vague "macro factors"
4. Use active voice: "Favors X on Y" not "X is favored due to Y"

## Output (JSON only, no explanation)
"""


def build_tooltip_generation_prompt(calls: list[AllocationCall]) -> str:
    """Build the complete tooltip generation prompt.

    Args:
        calls: Allocation calls needing tooltip text.

    Returns:
        Complete prompt string ready for LLM.
    """
    return TOOLTIP_GENERATION_PROMPT.format(
        calls=format_calls_for_tooltip_prompt(calls),
        schema=json.dumps(get_tooltip_generation_schema(), indent=2),
    )


def get_tooltip_generation_prompt_template() -> str:
    """Get the raw prompt template string.

    Returns:
        The prompt template with placeholders.
    """
    return TOOLTIP_GENERATION_PROMPT
