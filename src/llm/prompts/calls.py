"""Stage 6: Allocation call extraction prompt.

This prompt extracts allocation calls (overweight/neutral/underweight positions)
with taxonomy mapping, rationale, and sentiment from retrieved document excerpts.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from src.models.enums import CallDirection, Conviction, IndicatorDirection, Sentiment

if TYPE_CHECKING:
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


def format_taxonomy_summary() -> str:
    """Get a condensed taxonomy reference for the prompt.

    Returns:
        Formatted string with main categories and examples.
    """
    return """Categories (use exact codes):
- EQ_DM: EQ_US, EQ_EUROPE, EQ_UK, EQ_JAPAN, EQ_AUSTRALIA, EQ_CANADA
- EQ_EM: EQ_EM_BROAD, EQ_CHINA, EQ_INDIA, EQ_LATAM, EQ_EM_ASIA_EX_CHINA
- EQ_SECTORS: EQ_TECH, EQ_HEALTHCARE, EQ_FINANCIALS, EQ_ENERGY, EQ_INDUSTRIALS, EQ_MATERIALS
- EQ_FACTORS: EQ_VALUE, EQ_GROWTH, EQ_QUALITY, EQ_MOMENTUM, EQ_LOW_VOL, EQ_DIVIDEND
- FI_SOV_US: UST_2Y, UST_5Y, UST_10Y, UST_30Y, TIPS
- FI_SOV_EUROPE: GERMAN_BUNDS, UK_GILTS, FRENCH_OATS, ITALIAN_BTPS, SPANISH_BONOS, EU_PERIPHERY
- FI_IG: IG_US, IG_EUROPE, IG_GLOBAL, IG_FINANCIALS
- FI_HY: HY_US, HY_EUROPE, HY_GLOBAL, HY_EM
- FI_EM: EM_SOVEREIGN_HARD, EM_SOVEREIGN_LOCAL, EM_CORPORATE
- ALT_COMMODITIES: GOLD, SILVER, OIL_CRUDE, NATURAL_GAS, COPPER, AGRICULTURE
- CURR: USD, EUR, GBP, JPY, CHF, CNY, EM_FX
- ALT_REAL_ESTATE_*: RE_OFFICE, RE_RETAIL, RE_INDUSTRIAL, RE_RESIDENTIAL, RE_DATA_CENTERS"""


def get_call_extraction_schema() -> dict[str, object]:
    """Get JSON schema for call extraction output.

    Returns a schema that maps to CallExtractionOutput model.
    """
    return {
        "type": "object",
        "required": [
            "allocation_calls",
            "overall_sentiment",
            "sentiment_rationale",
            "sentiment_citations",
        ],
        "properties": {
            "allocation_calls": {
                "type": "array",
                "items": {
                    "type": "object",
                    "required": [
                        "asset_class_category",
                        "sub_asset_class",
                        "call",
                        "rationale_bullets",
                        "citations",
                        "confidence",
                    ],
                    "properties": {
                        "asset_class_category": {
                            "type": "string",
                            "description": "Taxonomy category code (e.g., 'FI_SOV_EUROPE')",
                        },
                        "sub_asset_class": {
                            "type": "string",
                            "description": "Taxonomy sub-asset code (e.g., 'GERMAN_BUNDS')",
                        },
                        "call": {
                            "type": "string",
                            "enum": [d.value for d in CallDirection],
                            "description": "Position direction",
                        },
                        "conviction": {
                            "type": ["string", "null"],
                            "enum": [c.value for c in Conviction] + [None],
                            "description": "Conviction level if inferable",
                        },
                        "time_horizon": {
                            "type": ["string", "null"],
                            "description": "Time horizon if stated (e.g., '6-12M')",
                        },
                        "rationale_bullets": {
                            "type": "array",
                            "minItems": 1,
                            "maxItems": 4,
                            "items": {"type": "string", "minLength": 1},
                            "description": "2-4 bullets explaining the call",
                        },
                        "key_indicators": {
                            "type": "array",
                            "maxItems": 5,
                            "items": {
                                "type": "object",
                                "required": ["name", "direction", "why_it_matters"],
                                "properties": {
                                    "name": {"type": "string"},
                                    "direction": {
                                        "type": "string",
                                        "enum": [d.value for d in IndicatorDirection],
                                    },
                                    "why_it_matters": {
                                        "type": "string",
                                        "maxLength": 200,
                                    },
                                },
                            },
                            "description": "Key economic/market indicators referenced",
                        },
                        "key_risks": {
                            "type": "array",
                            "maxItems": 3,
                            "items": {"type": "string"},
                            "description": "Key risks to the call",
                        },
                        "citations": {
                            "type": "array",
                            "minItems": 1,
                            "maxItems": 3,
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
                        "confidence": {
                            "type": "number",
                            "minimum": 0,
                            "maximum": 1,
                            "description": "Extraction confidence (0-1)",
                        },
                        "needs_analyst_review": {
                            "type": "boolean",
                            "default": False,
                            "description": "Flag for unclear extractions",
                        },
                        "review_reason": {
                            "type": ["string", "null"],
                            "description": "Reason for review if flagged",
                        },
                    },
                },
            },
            "overall_sentiment": {
                "type": "string",
                "enum": [s.value for s in Sentiment],
                "description": "Document's overall market sentiment",
            },
            "sentiment_rationale": {
                "type": "array",
                "minItems": 1,
                "maxItems": 3,
                "items": {"type": "string", "minLength": 1},
                "description": "2-3 bullets explaining sentiment",
            },
            "sentiment_citations": {
                "type": "array",
                "minItems": 1,
                "maxItems": 3,
                "items": {
                    "type": "object",
                    "required": ["chunk_id", "page"],
                    "properties": {
                        "chunk_id": {"type": "string"},
                        "page": {"type": "integer", "minimum": 1},
                        "text_span": {"type": "string", "maxLength": 200},
                    },
                },
            },
            "sentiment_confidence": {
                "type": "number",
                "minimum": 0,
                "maximum": 1,
                "description": "Sentiment extraction confidence (0-1)",
            },
        },
    }


CALL_EXTRACTION_PROMPT = """You are extracting allocation calls from fund manager research.

## Manager Context
Manager: {manager_name}
Document Type: {document_type}
Publication Date: {publication_date}

## Retrieved Excerpts (containing positioning language)
{chunks}

## Asset Taxonomy
{taxonomy}

## Task
Extract ALL allocation calls from the excerpts. An allocation call is an explicit positioning statement (overweight, neutral, underweight) on an asset class.

## Extraction Rules

### Call Direction
- OVERWEIGHT: "overweight", "prefer", "favor", "constructive", "bullish", "positive", "increase allocation", "add", "like"
- UNDERWEIGHT: "underweight", "avoid", "cautious on", "bearish", "negative", "reduce allocation", "trim", "dislike"
- NEUTRAL: "neutral", "benchmark weight", "hold", "no strong view", "market weight"
- UNCERTAIN: Use when language is ambiguous or conflicting

### Conviction (only if stated)
- HIGH: "high conviction", "strong preference", "very constructive", "strongly"
- MEDIUM: implied or moderate language
- LOW: "slight preference", "marginally", "modest"
- null: if not inferable from text

### Taxonomy Mapping
1. Map each asset mention to taxonomy category + sub-asset code
2. If exact match not found, use closest category
3. If unmappable, set asset_class_category="UNMAPPED", sub_asset_class="UNMAPPED"

### Rationale Bullets
- 2-4 bullets per call
- Must be supported by excerpt text
- Include: drivers, catalysts, risks considered

### Key Indicators
- Extract specific indicators mentioned (inflation, growth, policy)
- Note direction: RISING, FALLING, STABLE, VOLATILE

### Citations
- MANDATORY: Every call needs at least 1 citation
- Include chunk_id, page, and relevant text_span (≤200 chars)

## Overall Sentiment
Also extract the document's overall sentiment:
- NET_POSITIVE: Generally optimistic, constructive outlook
- NEUTRAL: Balanced, mixed signals
- NET_NEGATIVE: Cautious, bearish outlook

Provide:
- overall_sentiment: One of the above
- sentiment_rationale: 2-3 bullets explaining why
- sentiment_citations: References supporting sentiment assessment

## Critical Guardrails

1. NO HALLUCINATION: If a call direction is unclear, output:
   {{
     "call": "UNCERTAIN",
     "needs_analyst_review": true,
     "review_reason": "Ambiguous positioning language"
   }}

2. NO DUPLICATE CALLS: One call per (category, sub_asset) pair

3. NO UNSUPPORTED RATIONALE: Every bullet must trace to excerpt text

4. RESPECT TAXONOMY: Use exact taxonomy codes, not free text

5. CONFIDENCE SCORING:
   - 0.9-1.0: Explicit positioning language ("we are overweight")
   - 0.7-0.9: Clear implied positioning ("we prefer", "we favor")
   - 0.5-0.7: Implied but less certain
   - <0.5: Weak or ambiguous - flag for review

## Output (JSON only, no explanation)
"""


def build_call_extraction_prompt(
    chunks: list[RetrievedChunk],
    profile: DocumentProfile,
) -> str:
    """Build the complete call extraction prompt.

    Args:
        chunks: Retrieved chunks containing positioning language.
        profile: Document profile with metadata.

    Returns:
        Complete prompt string ready for LLM.
    """
    pub_date = profile.publication_date.isoformat() if profile.publication_date else "Unknown"

    return CALL_EXTRACTION_PROMPT.format(
        manager_name=profile.manager_name,
        document_type=profile.document_type.value,
        publication_date=pub_date,
        chunks=format_chunks_for_prompt(chunks),
        taxonomy=format_taxonomy_summary(),
    )


# Alias for consistency with LLM_CONTRACTS.md
def get_call_extraction_prompt_template() -> str:
    """Get the raw prompt template string.

    Returns:
        The prompt template with placeholders.
    """
    return CALL_EXTRACTION_PROMPT
