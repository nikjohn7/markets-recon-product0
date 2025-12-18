"""Asset class synonym resolution.

This module provides synonym mapping for natural language asset class mentions
to canonical taxonomy codes. Enables fuzzy matching of common alternative names.

Source: docs/TAXONOMY.md
"""

from typing import Optional

from .hierarchy import get_category_for_sub_asset

# =============================================================================
# Synonym Mappings: lowercase synonym → canonical sub-asset code
# =============================================================================

SYNONYMS: dict[str, str] = {
    # Commodities
    "gold": "GOLD",
    "xau": "GOLD",
    "silver": "SILVER",
    "xag": "SILVER",
    "crude": "OIL_CRUDE",
    "wti": "OIL_CRUDE",
    "brent": "OIL_CRUDE",
    "oil": "OIL_CRUDE",
    "crude oil": "OIL_CRUDE",
    "nat gas": "NATURAL_GAS",
    "ng": "NATURAL_GAS",
    "natural gas": "NATURAL_GAS",
    "copper": "COPPER",
    "agri": "AGRICULTURE",
    "soft commodities": "AGRICULTURE",
    "agriculture": "AGRICULTURE",
    "commodities basket": "COMMODITIES_BROAD",
    "broad commodities": "COMMODITIES_BROAD",
    # Real Estate
    "office real estate": "RE_OFFICE",
    "office": "RE_OFFICE",
    "retail real estate": "RE_RETAIL",
    "retail": "RE_RETAIL",
    "logistics": "RE_INDUSTRIAL",
    "warehouses": "RE_INDUSTRIAL",
    "industrial real estate": "RE_INDUSTRIAL",
    "industrial/logistics": "RE_INDUSTRIAL",
    "housing": "RE_RESIDENTIAL",
    "residential": "RE_RESIDENTIAL",
    "data centers": "RE_DATA_CENTERS",
    "hotels": "RE_HOSPITALITY",
    "hospitality": "RE_HOSPITALITY",
    # Developed Markets Equities
    "us stocks": "EQ_US",
    "american equities": "EQ_US",
    "s&p 500": "EQ_US",
    "s&p500": "EQ_US",
    "sp500": "EQ_US",
    "nasdaq": "EQ_US",
    "us equities": "EQ_US",
    "europe stocks": "EQ_EUROPE",
    "stoxx": "EQ_EUROPE",
    "european equities": "EQ_EUROPE",
    "uk stocks": "EQ_UK",
    "ftse": "EQ_UK",
    "uk equities": "EQ_UK",
    "japan stocks": "EQ_JAPAN",
    "nikkei": "EQ_JAPAN",
    "topix": "EQ_JAPAN",
    "japan equities": "EQ_JAPAN",
    "asx": "EQ_AUSTRALIA",
    "australia equities": "EQ_AUSTRALIA",
    "tsx": "EQ_CANADA",
    "canada equities": "EQ_CANADA",
    # Emerging Markets Equities
    "emerging markets": "EQ_EM_BROAD",
    "em stocks": "EQ_EM_BROAD",
    "em equities": "EQ_EM_BROAD",
    "china stocks": "EQ_CHINA",
    "csi": "EQ_CHINA",
    "msci china": "EQ_CHINA",
    "china equities": "EQ_CHINA",
    "india stocks": "EQ_INDIA",
    "nifty": "EQ_INDIA",
    "india equities": "EQ_INDIA",
    "latin america": "EQ_LATAM",
    "latam equities": "EQ_LATAM",
    "asia ex-china": "EQ_EM_ASIA_EX_CHINA",
    "em asia ex-china": "EQ_EM_ASIA_EX_CHINA",
    "eastern europe": "EQ_EMEA",
    "middle east": "EQ_EMEA",
    "africa": "EQ_EMEA",
    "emea equities": "EQ_EMEA",
    # Equity Factors
    "value stocks": "EQ_VALUE",
    "cheap": "EQ_VALUE",
    "value": "EQ_VALUE",
    "growth stocks": "EQ_GROWTH",
    "growth": "EQ_GROWTH",
    "quality factor": "EQ_QUALITY",
    "quality": "EQ_QUALITY",
    "momentum factor": "EQ_MOMENTUM",
    "momentum": "EQ_MOMENTUM",
    "min vol": "EQ_LOW_VOL",
    "defensive": "EQ_LOW_VOL",
    "low volatility": "EQ_LOW_VOL",
    "small caps": "EQ_SIZE_SMALL",
    "small cap": "EQ_SIZE_SMALL",
    "mid caps": "EQ_SIZE_MID",
    "mid cap": "EQ_SIZE_MID",
    "large caps": "EQ_SIZE_LARGE",
    "mega cap": "EQ_SIZE_LARGE",
    "large cap": "EQ_SIZE_LARGE",
    "high dividend": "EQ_DIVIDEND",
    "income": "EQ_DIVIDEND",
    "dividend": "EQ_DIVIDEND",
    "dividend/income": "EQ_DIVIDEND",
    # Equity Sectors
    "tech": "EQ_TECH",
    "it": "EQ_TECH",
    "technology": "EQ_TECH",
    "health care": "EQ_HEALTHCARE",
    "pharma": "EQ_HEALTHCARE",
    "healthcare": "EQ_HEALTHCARE",
    "banks": "EQ_FINANCIALS",
    "insurance": "EQ_FINANCIALS",
    "financials": "EQ_FINANCIALS",
    "oil & gas": "EQ_ENERGY",
    "energy sector": "EQ_ENERGY",
    "energy": "EQ_ENERGY",
    "industrial": "EQ_INDUSTRIALS",
    "industrials": "EQ_INDUSTRIALS",
    "basic materials": "EQ_MATERIALS",
    "materials": "EQ_MATERIALS",
    "cyclical consumer": "EQ_CONSUMER_DISC",
    "consumer discretionary": "EQ_CONSUMER_DISC",
    "defensive consumer": "EQ_CONSUMER_STAPLES",
    "consumer staples": "EQ_CONSUMER_STAPLES",
    "utilities sector": "EQ_UTILITIES",
    "utilities": "EQ_UTILITIES",
    "reits": "EQ_REAL_ESTATE",
    "real estate": "EQ_REAL_ESTATE",
    "telecoms": "EQ_COMMUNICATION",
    "media": "EQ_COMMUNICATION",
    "communication services": "EQ_COMMUNICATION",
    # Fixed Income: Sovereigns Europe
    "eurozone govies": "EURO_GOVT_BONDS",
    "eur govies": "EURO_GOVT_BONDS",
    "euro government bonds": "EURO_GOVT_BONDS",
    "bunds": "GERMAN_BUNDS",
    "german bunds": "GERMAN_BUNDS",
    "germany": "GERMAN_BUNDS",
    "oats": "FRENCH_OATS",
    "france": "FRENCH_OATS",
    "french government bonds": "FRENCH_OATS",
    "btps": "ITALIAN_BTPS",
    "italy": "ITALIAN_BTPS",
    "italian btps": "ITALIAN_BTPS",
    "spain": "SPANISH_BONOS",
    "spanish bonos": "SPANISH_BONOS",
    "gilts": "UK_GILTS",
    "uk government": "UK_GILTS",
    "uk gilts": "UK_GILTS",
    "switzerland": "SWISS_GOVT",
    "swiss government bonds": "SWISS_GOVT",
    "giips": "EUROPE_PERIPHERY",
    "periphery": "EUROPE_PERIPHERY",
    "european periphery": "EUROPE_PERIPHERY",
    "core europe": "EUROPE_CORE",
    "european core": "EUROPE_CORE",
    "european duration": "EUROPE_DURATION",
    "europe duration": "EUROPE_DURATION",
    "poland": "POLISH_BONDS",
    "polish government bonds": "POLISH_BONDS",
    # Fixed Income: Sovereigns APAC
    "jgbs": "JGB",
    "japanese government bonds": "JGB",
    "japan": "JGB",
    "japanese duration": "JAPAN_DURATION",
    "japan duration": "JAPAN_DURATION",
    "agbs": "AUSTRALIA_GOVT",
    "australia": "AUSTRALIA_GOVT",
    "australian government bonds": "AUSTRALIA_GOVT",
    "cgbs": "CHINA_GOVT",
    "china onshore": "CHINA_GOVT",
    "chinese government bonds": "CHINA_GOVT",
    # Fixed Income: Sovereigns North America
    "treasuries": "US_TREASURIES",
    "ust": "US_TREASURIES",
    "us treasuries": "US_TREASURIES",
    "tips": "US_TIPS",
    "inflation-linked": "US_TIPS",
    "us tips": "US_TIPS",
    "american duration": "US_DURATION",
    "us duration": "US_DURATION",
    "canada": "CANADA_GOVT",
    "canadian government bonds": "CANADA_GOVT",
    # Fixed Income: Investment Grade
    "us ig": "IG_US",
    "us corporate ig": "IG_US",
    "us investment grade": "IG_US",
    "eur ig": "IG_EUROPE",
    "european ig": "IG_EUROPE",
    "european investment grade": "IG_EUROPE",
    "global ig": "IG_GLOBAL",
    "global investment grade": "IG_GLOBAL",
    "investment grade financials": "IG_FINANCIALS",
    "ig financials": "IG_FINANCIALS",
    "ig corporates ex-financials": "IG_NON_FIN",
    "ig non-financials": "IG_NON_FIN",
    # Fixed Income: High Yield
    "us hy": "HY_US",
    "junk bonds": "HY_US",
    "us high yield": "HY_US",
    "eur hy": "HY_EUROPE",
    "european high yield": "HY_EUROPE",
    "global hy": "HY_GLOBAL",
    "global high yield": "HY_GLOBAL",
    "emerging market hy": "HY_EM",
    "em high yield": "HY_EM",
    # Fixed Income: Specialty
    "em hc": "EM_SOVEREIGN_HARD",
    "em usd": "EM_SOVEREIGN_HARD",
    "em sovereign (hard currency)": "EM_SOVEREIGN_HARD",
    "em lc": "EM_SOVEREIGN_LOCAL",
    "em local": "EM_SOVEREIGN_LOCAL",
    "em sovereign (local currency)": "EM_SOVEREIGN_LOCAL",
    "em corporates": "EM_CORPORATE",
    "em corporate bonds": "EM_CORPORATE",
    "mbs": "MBS",
    "agency mbs": "MBS",
    "mortgage-backed securities": "MBS",
    "abs": "ABS",
    "asset-backed securities": "ABS",
    "clos": "CLO",
    "collateralized loan obligations": "CLO",
    "converts": "CONVERTIBLES",
    "convertible bonds": "CONVERTIBLES",
    "linkers": "INFLATION_LINKED",
    "ilbs": "INFLATION_LINKED",
    "inflation-linked bonds": "INFLATION_LINKED",
    # Currencies
    "dollar": "USD",
    "greenback": "USD",
    "us dollar": "USD",
    "euro": "EUR",
    "pound": "GBP",
    "sterling": "GBP",
    "british pound": "GBP",
    "yen": "JPY",
    "japanese yen": "JPY",
    "franc": "CHF",
    "swiss franc": "CHF",
    "aussie": "AUD",
    "australian dollar": "AUD",
    "loonie": "CAD",
    "canadian dollar": "CAD",
    "yuan": "CNY",
    "renminbi": "CNY",
    "rmb": "CNY",
    "chinese yuan": "CNY",
    "em fx": "EM_FX_BASKET",
    "em currency basket": "EM_FX_BASKET",
    "asia fx": "ASIA_FX_BASKET",
    "asia currency basket": "ASIA_FX_BASKET",
    "bitcoin": "DIGITAL_ASSETS",
    "crypto": "DIGITAL_ASSETS",
    "digital assets": "DIGITAL_ASSETS",
}

# =============================================================================
# Resolution Function
# =============================================================================


def resolve_asset(raw_text: str) -> Optional[tuple[str, str]]:
    """Resolve a raw asset mention to (category_code, sub_asset_code).

    Performs case-insensitive synonym matching. Returns None if the asset
    cannot be resolved to the taxonomy.

    Args:
        raw_text: Raw asset mention from document (e.g., "Bunds", "US stocks")

    Returns:
        Tuple of (category_code, sub_asset_code) if resolved, None otherwise

    Examples:
        >>> resolve_asset("bunds")
        ('FI_SOV_EUROPE', 'GERMAN_BUNDS')
        >>> resolve_asset("US Treasuries")
        ('FI_SOV_NA', 'US_TREASURIES')
        >>> resolve_asset("unknown asset")
        None
    """
    # Normalize input: lowercase and strip whitespace
    normalized = raw_text.lower().strip()

    if not normalized:
        return None

    # Exact match in synonyms
    if normalized in SYNONYMS:
        sub_asset_code = SYNONYMS[normalized]
        category_code = get_category_for_sub_asset(sub_asset_code)

        if category_code is None:
            # This should never happen if SYNONYMS is correctly maintained,
            # but we handle it defensively
            return None

        return (category_code, sub_asset_code)

    # No match found
    return None


def get_all_synonyms_for_sub_asset(sub_asset_code: str) -> list[str]:
    """Get all synonyms that map to a given sub-asset code.

    Args:
        sub_asset_code: The canonical sub-asset code (e.g., "GERMAN_BUNDS")

    Returns:
        List of all synonym strings (lowercase) that resolve to this sub-asset
    """
    return [
        synonym
        for synonym, code in SYNONYMS.items()
        if code == sub_asset_code
    ]


def is_valid_synonym(synonym: str) -> bool:
    """Check if a synonym exists in the mapping.

    Args:
        synonym: The synonym to check (case-insensitive)

    Returns:
        True if the synonym maps to a valid sub-asset
    """
    normalized = synonym.lower().strip()
    return normalized in SYNONYMS
