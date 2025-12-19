"""Stage 9: Tag generation prompt.

This prompt generates normalized tags for search and filtering,
using the allowed vocabularies from taxonomy/tags.py.
"""

from __future__ import annotations

import json
from typing import TYPE_CHECKING

from src.taxonomy.tags import MACRO_REGIME_TAGS, RISK_TAGS, THEME_TAGS

if TYPE_CHECKING:
    from src.models.calls import AllocationCall
    from src.models.pipeline import RetrievedChunk
    from src.models.profile import DocumentProfile


def format_profile_for_tags(profile: DocumentProfile) -> str:
    """Format document profile for tag generation context.

    Args:
        profile: Document profile with metadata.

    Returns:
        Formatted string with profile information.
    """
    pub_date = profile.publication_date.isoformat() if profile.publication_date else "Unknown"
    regions = ", ".join(profile.regions) if profile.regions else "Not specified"
    assets = ", ".join(profile.asset_classes_covered)

    return (
        f"Manager: {profile.manager_name}\n"
        f"Document Type: {profile.document_type.value}\n"
        f"Publication Date: {pub_date}\n"
        f"Asset Classes: {assets}\n"
        f"Regions: {regions}"
    )


def format_calls_for_tags(calls: list[AllocationCall]) -> str:
    """Format extracted calls for tag generation context.

    Args:
        calls: List of allocation calls.

    Returns:
        Formatted string summarizing calls.
    """
    if not calls:
        return "No allocation calls extracted."

    lines: list[str] = []
    for call in calls:
        direction = call.call.value
        risks = ", ".join(call.key_risks) if call.key_risks else "None"
        lines.append(
            f"- {call.sub_asset_class}: {direction} | Risks: {risks}"
        )

    return "\n".join(lines)


def format_chunks_for_tags(chunks: list[RetrievedChunk]) -> str:
    """Format retrieved chunks for tag generation.

    Args:
        chunks: List of retrieved chunks.

    Returns:
        Formatted string with chunk text.
    """
    formatted_parts: list[str] = []
    for chunk in chunks:
        formatted_parts.append(f"[Page {chunk.page}] {chunk.text}")
    return "\n\n".join(formatted_parts)


def get_tag_generation_schema() -> dict[str, object]:
    """Get JSON schema for tag generation output.

    Returns:
        Schema for tag output.
    """
    return {
        "type": "object",
        "required": ["theme_tags", "risk_tags", "macro_regime_tags"],
        "properties": {
            "theme_tags": {
                "type": "array",
                "maxItems": 5,
                "items": {
                    "type": "string",
                    "enum": THEME_TAGS,
                },
                "description": "Key themes discussed (from allowed list)",
            },
            "risk_tags": {
                "type": "array",
                "maxItems": 5,
                "items": {
                    "type": "string",
                    "enum": RISK_TAGS,
                },
                "description": "Key risks highlighted (from allowed list)",
            },
            "macro_regime_tags": {
                "type": "array",
                "maxItems": 3,
                "items": {
                    "type": "string",
                    "enum": MACRO_REGIME_TAGS,
                },
                "description": "Economic regime view (from allowed list)",
            },
            "novel_themes": {
                "type": "array",
                "items": {"type": "string"},
                "description": "Novel themes not in allowed list (for vocabulary expansion)",
            },
            "confidence": {
                "type": "number",
                "minimum": 0,
                "maximum": 1,
                "description": "Tag extraction confidence (0-1)",
            },
        },
    }


TAG_GENERATION_PROMPT = """Generate normalized tags for search and filtering.

## Document Profile
{profile}

## Extracted Calls
{calls}

## Key Passages
{chunks}

## Allowed Tag Vocabularies

### Theme Tags (max 5)
{theme_tags}

### Risk Tags (max 5)
{risk_tags}

### Macro Regime Tags (max 3)
{macro_regime_tags}

## Task
Generate tags in these categories:

1. **theme_tags**: Key themes discussed
   - Select from the allowed list above
   - Pick themes that are substantively discussed, not just mentioned
   - Max 5 tags

2. **risk_tags**: Key risks highlighted
   - Select from the allowed list above
   - Include risks explicitly mentioned in the document
   - Max 5 tags

3. **macro_regime_tags**: Economic regime view
   - Select from the allowed list above
   - Pick the regime(s) the manager believes we are in or heading toward
   - Max 3 tags

4. **novel_themes** (optional): If a significant theme appears that isn't in the allowed lists, flag it here for vocabulary expansion

## Output Schema
{schema}

## Rules
1. ONLY use tags from the allowed lists (except novel_themes)
2. If a theme/risk is not discussed, do not include it
3. Limit to most relevant tags per category
4. Tag names must be lowercase and match exactly as listed

## Mapping Guidance

### Common Theme Mappings
- "Inflation concerns" → inflation
- "Rate cut expectations" → rate_cuts, fed_policy (or ecb_policy, etc.)
- "AI spending" → ai_capex
- "Supply chain shifts" → deglobalization, nearshoring
- "Growth slowdown" → recession_risk or soft_landing (depending on severity)

### Common Risk Mappings
- "Spread widening risk" → credit_spreads
- "Interest rate risk" → duration_risk
- "Currency volatility" → fx_volatility
- "Crowded positioning" → crowded_trade

### Common Macro Regime Mappings
- "Soft landing scenario" → soft_landing
- "No landing" → no_landing
- "Goldilocks" → goldilocks
- "Late cycle" → late_cycle
- "Stagflation risk" → stagflation

## Output (JSON only, no explanation)
"""


def build_tag_generation_prompt(
    profile: DocumentProfile,
    calls: list[AllocationCall],
    chunks: list[RetrievedChunk],
) -> str:
    """Build the complete tag generation prompt.

    Args:
        profile: Document profile with metadata.
        calls: Extracted allocation calls.
        chunks: Retrieved passages for context.

    Returns:
        Complete prompt string ready for LLM.
    """
    return TAG_GENERATION_PROMPT.format(
        profile=format_profile_for_tags(profile),
        calls=format_calls_for_tags(calls),
        chunks=format_chunks_for_tags(chunks),
        theme_tags=", ".join(THEME_TAGS),
        risk_tags=", ".join(RISK_TAGS),
        macro_regime_tags=", ".join(MACRO_REGIME_TAGS),
        schema=json.dumps(get_tag_generation_schema(), indent=2),
    )


def get_tag_generation_prompt_template() -> str:
    """Get the raw prompt template string.

    Returns:
        The prompt template with placeholders.
    """
    return TAG_GENERATION_PROMPT
