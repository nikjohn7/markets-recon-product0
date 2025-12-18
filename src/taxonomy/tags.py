"""Tag vocabularies and validation helpers for stage 9 tagging.

Source: docs/TAXONOMY.md
"""

from collections.abc import Mapping

from models.enums import TagType

# =============================================================================
# Tag Vocabularies
# =============================================================================

THEME_TAGS: list[str] = [
    "inflation",
    "disinflation",
    "deflation",
    "growth",
    "recession_risk",
    "soft_landing",
    "hard_landing",
    "stagflation",
    "fed_policy",
    "ecb_policy",
    "boj_policy",
    "pboc_policy",
    "rate_cuts",
    "rate_hikes",
    "quantitative_tightening",
    "fiscal_policy",
    "election_risk",
    "geopolitical_risk",
    "china_risk",
    "energy_transition",
    "ai_capex",
    "deglobalization",
    "nearshoring",
    "sustainability",
    "demographics",
]

RISK_TAGS: list[str] = [
    "duration_risk",
    "credit_spreads",
    "fx_volatility",
    "equity_volatility",
    "liquidity_risk",
    "political_risk",
    "regulatory_risk",
    "concentration_risk",
    "valuation_risk",
    "crowded_trade",
]

REGION_TAGS: list[str] = [
    "us",
    "europe",
    "uk",
    "japan",
    "china",
    "em_asia",
    "em_latam",
    "em_emea",
    "apac",
    "global",
]

MACRO_REGIME_TAGS: list[str] = [
    "soft_landing",
    "hard_landing",
    "no_landing",
    "stagflation",
    "goldilocks",
    "reflation",
    "disinflation",
    "late_cycle",
    "mid_cycle",
    "early_cycle",
]

_TAG_VALUES_BY_TYPE: Mapping[TagType, set[str]] = {
    TagType.THEME: set(THEME_TAGS),
    TagType.RISK: set(RISK_TAGS),
    TagType.REGION: set(REGION_TAGS),
    TagType.MACRO_REGIME: set(MACRO_REGIME_TAGS),
}


def _coerce_tag_type(tag_type: TagType | str) -> TagType | None:
    """Safely convert a tag type input into a TagType enum.

    Args:
        tag_type: TagType enum or string representation.

    Returns:
        TagType instance if valid, otherwise None.
    """

    if isinstance(tag_type, TagType):
        return tag_type

    try:
        return TagType(tag_type)
    except ValueError:
        return None


def is_valid_tag(tag_type: TagType | str, value: str) -> bool:
    """Validate that a tag value is allowed for the given tag type.

    Args:
        tag_type: TagType enum or its string value.
        value: Tag value to validate.

    Returns:
        True if the tag is valid for the type, False otherwise.
    """

    if not value:
        return False

    resolved_type = _coerce_tag_type(tag_type)
    if resolved_type is None:
        return False

    allowed_values = _TAG_VALUES_BY_TYPE.get(resolved_type)
    if allowed_values is None:
        return False

    normalized_value = value.strip().lower()
    return normalized_value in allowed_values
