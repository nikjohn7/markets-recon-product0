"""Asset class taxonomy hierarchy.

This module defines the canonical taxonomy structure used for classifying
allocation calls. All LLM extractions must map to this taxonomy.

Source: docs/TAXONOMY.md
"""


# =============================================================================
# Category → Sub-Asset Mappings
# =============================================================================

CATEGORIES: dict[str, list[str]] = {
    # Alternatives
    "ALT_COMMODITIES": [
        "GOLD",
        "SILVER",
        "OIL_CRUDE",
        "NATURAL_GAS",
        "COPPER",
        "AGRICULTURE",
        "COMMODITIES_BROAD",
    ],
    "ALT_HEDGE_FUNDS": [],  # No sub-assets defined in TAXONOMY.md
    "ALT_INFRASTRUCTURE": [],  # No sub-assets defined in TAXONOMY.md
    "ALT_PRIVATE_CREDIT": [],  # No sub-assets defined in TAXONOMY.md
    "ALT_PRIVATE_EQUITY": [],  # No sub-assets defined in TAXONOMY.md
    "ALT_REAL_ESTATE_GLOBAL": [
        "RE_OFFICE",
        "RE_RETAIL",
        "RE_INDUSTRIAL",
        "RE_RESIDENTIAL",
        "RE_DATA_CENTERS",
        "RE_HOSPITALITY",
    ],
    "ALT_REAL_ESTATE_APAC": [],  # Regional grouping, shares sub-assets with GLOBAL
    "ALT_REAL_ESTATE_NA": [],  # Regional grouping, shares sub-assets with GLOBAL
    "ALT_REAL_ESTATE_UK": [],  # Regional grouping, shares sub-assets with GLOBAL
    "ALT_REAL_ESTATE_EU": [],  # Regional grouping, shares sub-assets with GLOBAL
    "ALT_RE_INFRA": [],  # No sub-assets defined in TAXONOMY.md
    # Equities
    "EQ_DM_CAPS": [],  # No sub-assets defined in TAXONOMY.md
    "EQ_DM": [
        "EQ_US",
        "EQ_EUROPE",
        "EQ_UK",
        "EQ_JAPAN",
        "EQ_AUSTRALIA",
        "EQ_CANADA",
    ],
    "EQ_EM": [
        "EQ_EM_BROAD",
        "EQ_CHINA",
        "EQ_INDIA",
        "EQ_LATAM",
        "EQ_EM_ASIA_EX_CHINA",
        "EQ_EMEA",
    ],
    "EQ_FACTORS": [
        "EQ_VALUE",
        "EQ_GROWTH",
        "EQ_QUALITY",
        "EQ_MOMENTUM",
        "EQ_LOW_VOL",
        "EQ_SIZE_SMALL",
        "EQ_SIZE_MID",
        "EQ_SIZE_LARGE",
        "EQ_DIVIDEND",
    ],
    "EQ_GEOS": [],  # Geographic breakdown handled via EQ_DM/EQ_EM
    "EQ_SECTORS": [
        "EQ_TECH",
        "EQ_HEALTHCARE",
        "EQ_FINANCIALS",
        "EQ_ENERGY",
        "EQ_INDUSTRIALS",
        "EQ_MATERIALS",
        "EQ_CONSUMER_DISC",
        "EQ_CONSUMER_STAPLES",
        "EQ_UTILITIES",
        "EQ_REAL_ESTATE",
        "EQ_COMMUNICATION",
    ],
    "EQ_THEMATICS": [],  # No sub-assets defined in TAXONOMY.md
    # Fixed Income
    "FI_DURATION": [],  # No sub-assets defined in TAXONOMY.md
    "FI_GEO": [],  # Geographic breakdown handled via FI_SOV_*
    "FI_HY": [
        "HY_US",
        "HY_EUROPE",
        "HY_GLOBAL",
        "HY_EM",
    ],
    "FI_IG": [
        "IG_US",
        "IG_EUROPE",
        "IG_GLOBAL",
        "IG_FINANCIALS",
        "IG_NON_FIN",
    ],
    "FI_SOV_GLOBAL": [],  # No sub-assets defined in TAXONOMY.md
    "FI_SOV_APAC": [
        "JGB",
        "JAPAN_DURATION",
        "AUSTRALIA_GOVT",
        "CHINA_GOVT",
    ],
    "FI_SOV_EUROPE": [
        "EURO_GOVT_BONDS",
        "GERMAN_BUNDS",
        "FRENCH_OATS",
        "ITALIAN_BTPS",
        "SPANISH_BONOS",
        "UK_GILTS",
        "SWISS_GOVT",
        "EUROPE_PERIPHERY",
        "EUROPE_CORE",
        "EUROPE_DURATION",
        "POLISH_BONDS",
    ],
    "FI_SOV_NA": [
        "US_TREASURIES",
        "US_TIPS",
        "US_DURATION",
        "CANADA_GOVT",
    ],
    "FI_SPECIALTY": [
        "EM_SOVEREIGN_HARD",
        "EM_SOVEREIGN_LOCAL",
        "EM_CORPORATE",
        "MBS",
        "ABS",
        "CLO",
        "CONVERTIBLES",
        "INFLATION_LINKED",
    ],
    # Currencies
    "FX_CURRENCIES": [
        "USD",
        "EUR",
        "GBP",
        "JPY",
        "CHF",
        "AUD",
        "CAD",
        "CNY",
        "EM_FX_BASKET",
        "ASIA_FX_BASKET",
        "DIGITAL_ASSETS",
    ],
    # Asset Allocation
    "AA_BROAD": [],  # No sub-assets defined in TAXONOMY.md
}

# =============================================================================
# Display Name Mappings
# =============================================================================

CATEGORY_DISPLAY_NAMES: dict[str, str] = {
    # Alternatives
    "ALT_COMMODITIES": "Alternatives: Commodities",
    "ALT_HEDGE_FUNDS": "Alternatives: Hedge Funds",
    "ALT_INFRASTRUCTURE": "Alternatives: Infrastructure",
    "ALT_PRIVATE_CREDIT": "Alternatives: Private Credit",
    "ALT_PRIVATE_EQUITY": "Alternatives: Private Equity",
    "ALT_REAL_ESTATE_GLOBAL": "Alternatives: Real Estate",
    "ALT_REAL_ESTATE_APAC": "Alternatives: Real Estate (APAC)",
    "ALT_REAL_ESTATE_NA": "Alternatives: Real Estate (North America)",
    "ALT_REAL_ESTATE_UK": "Alternatives: Real Estate (UK)",
    "ALT_REAL_ESTATE_EU": "Alternatives: Real Estate (EU)",
    "ALT_RE_INFRA": "Alternatives: Real Estate/Infrastructure",
    # Equities
    "EQ_DM_CAPS": "Equities: Developed Market Caps",
    "EQ_DM": "Equities: Developed Markets",
    "EQ_EM": "Equities: Emerging Markets",
    "EQ_FACTORS": "Equities: Factors",
    "EQ_GEOS": "Equities: Geographies",
    "EQ_SECTORS": "Equities: Sectors",
    "EQ_THEMATICS": "Equities: Thematics",
    # Fixed Income
    "FI_DURATION": "Fixed Income: Duration",
    "FI_GEO": "Fixed Income: Geography",
    "FI_HY": "Fixed Income: High Yield",
    "FI_IG": "Fixed Income: Investment Grade",
    "FI_SOV_GLOBAL": "Fixed Income: Sovereigns",
    "FI_SOV_APAC": "Fixed Income: Sovereigns (APAC)",
    "FI_SOV_EUROPE": "Fixed Income: Sovereigns (Europe)",
    "FI_SOV_NA": "Fixed Income: Sovereigns (North America)",
    "FI_SPECIALTY": "Fixed Income: Specialty",
    # Currencies
    "FX_CURRENCIES": "Currencies",
    # Asset Allocation
    "AA_BROAD": "Asset Allocation",
}

SUB_ASSET_DISPLAY_NAMES: dict[str, str] = {
    # Commodities
    "GOLD": "Gold",
    "SILVER": "Silver",
    "OIL_CRUDE": "Crude Oil",
    "NATURAL_GAS": "Natural Gas",
    "COPPER": "Copper",
    "AGRICULTURE": "Agriculture",
    "COMMODITIES_BROAD": "Broad Commodities",
    # Real Estate
    "RE_OFFICE": "Office",
    "RE_RETAIL": "Retail",
    "RE_INDUSTRIAL": "Industrial/Logistics",
    "RE_RESIDENTIAL": "Residential",
    "RE_DATA_CENTERS": "Data Centers",
    "RE_HOSPITALITY": "Hospitality",
    # Developed Markets Equities
    "EQ_US": "US Equities",
    "EQ_EUROPE": "European Equities",
    "EQ_UK": "UK Equities",
    "EQ_JAPAN": "Japan Equities",
    "EQ_AUSTRALIA": "Australia Equities",
    "EQ_CANADA": "Canada Equities",
    # Emerging Markets Equities
    "EQ_EM_BROAD": "EM Equities (Broad)",
    "EQ_CHINA": "China Equities",
    "EQ_INDIA": "India Equities",
    "EQ_LATAM": "LatAm Equities",
    "EQ_EM_ASIA_EX_CHINA": "EM Asia ex-China",
    "EQ_EMEA": "EMEA Equities",
    # Equity Factors
    "EQ_VALUE": "Value",
    "EQ_GROWTH": "Growth",
    "EQ_QUALITY": "Quality",
    "EQ_MOMENTUM": "Momentum",
    "EQ_LOW_VOL": "Low Volatility",
    "EQ_SIZE_SMALL": "Small Cap",
    "EQ_SIZE_MID": "Mid Cap",
    "EQ_SIZE_LARGE": "Large Cap",
    "EQ_DIVIDEND": "Dividend/Income",
    # Equity Sectors
    "EQ_TECH": "Technology",
    "EQ_HEALTHCARE": "Healthcare",
    "EQ_FINANCIALS": "Financials",
    "EQ_ENERGY": "Energy",
    "EQ_INDUSTRIALS": "Industrials",
    "EQ_MATERIALS": "Materials",
    "EQ_CONSUMER_DISC": "Consumer Discretionary",
    "EQ_CONSUMER_STAPLES": "Consumer Staples",
    "EQ_UTILITIES": "Utilities",
    "EQ_REAL_ESTATE": "Real Estate (Equities)",
    "EQ_COMMUNICATION": "Communication Services",
    # Fixed Income: Sovereigns Europe
    "EURO_GOVT_BONDS": "Euro Government Bonds",
    "GERMAN_BUNDS": "German Bunds",
    "FRENCH_OATS": "French Government Bonds",
    "ITALIAN_BTPS": "Italian BTPs",
    "SPANISH_BONOS": "Spanish Bonos",
    "UK_GILTS": "UK Gilts",
    "SWISS_GOVT": "Swiss Government Bonds",
    "EUROPE_PERIPHERY": "European Periphery",
    "EUROPE_CORE": "European Core",
    "EUROPE_DURATION": "Europe Duration",
    "POLISH_BONDS": "Polish Government Bonds",
    # Fixed Income: Sovereigns APAC
    "JGB": "Japanese Government Bonds",
    "JAPAN_DURATION": "Japan Duration",
    "AUSTRALIA_GOVT": "Australian Government Bonds",
    "CHINA_GOVT": "Chinese Government Bonds",
    # Fixed Income: Sovereigns North America
    "US_TREASURIES": "US Treasuries",
    "US_TIPS": "US TIPS",
    "US_DURATION": "US Duration",
    "CANADA_GOVT": "Canadian Government Bonds",
    # Fixed Income: Investment Grade
    "IG_US": "US Investment Grade",
    "IG_EUROPE": "European Investment Grade",
    "IG_GLOBAL": "Global Investment Grade",
    "IG_FINANCIALS": "IG Financials",
    "IG_NON_FIN": "IG Non-Financials",
    # Fixed Income: High Yield
    "HY_US": "US High Yield",
    "HY_EUROPE": "European High Yield",
    "HY_GLOBAL": "Global High Yield",
    "HY_EM": "EM High Yield",
    # Fixed Income: Specialty
    "EM_SOVEREIGN_HARD": "EM Sovereign (Hard Currency)",
    "EM_SOVEREIGN_LOCAL": "EM Sovereign (Local Currency)",
    "EM_CORPORATE": "EM Corporate Bonds",
    "MBS": "Mortgage-Backed Securities",
    "ABS": "Asset-Backed Securities",
    "CLO": "Collateralized Loan Obligations",
    "CONVERTIBLES": "Convertible Bonds",
    "INFLATION_LINKED": "Inflation-Linked Bonds",
    # Currencies
    "USD": "US Dollar",
    "EUR": "Euro",
    "GBP": "British Pound",
    "JPY": "Japanese Yen",
    "CHF": "Swiss Franc",
    "AUD": "Australian Dollar",
    "CAD": "Canadian Dollar",
    "CNY": "Chinese Yuan",
    "EM_FX_BASKET": "EM Currency Basket",
    "ASIA_FX_BASKET": "Asia Currency Basket",
    "DIGITAL_ASSETS": "Digital Assets/Bitcoin",
}

# =============================================================================
# Reverse Index: Sub-Asset → Category
# =============================================================================

# Build reverse index for O(1) lookups
_SUB_ASSET_TO_CATEGORY: dict[str, str] = {}
for category, sub_assets in CATEGORIES.items():
    for sub_asset in sub_assets:
        if sub_asset in _SUB_ASSET_TO_CATEGORY:
            raise ValueError(
                f"Duplicate sub-asset {sub_asset} in categories "
                f"{_SUB_ASSET_TO_CATEGORY[sub_asset]} and {category}"
            )
        _SUB_ASSET_TO_CATEGORY[sub_asset] = category

# =============================================================================
# Lookup Functions
# =============================================================================


def get_category_for_sub_asset(sub_asset_code: str) -> str | None:
    """Get the category code for a given sub-asset code.

    Args:
        sub_asset_code: The sub-asset code to look up (e.g., "GERMAN_BUNDS")

    Returns:
        The category code (e.g., "FI_SOV_EUROPE") or None if not found
    """
    return _SUB_ASSET_TO_CATEGORY.get(sub_asset_code)


def get_sub_assets_for_category(category_code: str) -> list[str]:
    """Get all sub-asset codes for a given category.

    Args:
        category_code: The category code (e.g., "FI_SOV_EUROPE")

    Returns:
        List of sub-asset codes, or empty list if category not found
    """
    return CATEGORIES.get(category_code, [])


def get_category_display_name(category_code: str) -> str | None:
    """Get the display name for a category code.

    Args:
        category_code: The category code (e.g., "FI_SOV_EUROPE")

    Returns:
        The display name (e.g., "Fixed Income: Sovereigns (Europe)") or None
    """
    return CATEGORY_DISPLAY_NAMES.get(category_code)


def get_sub_asset_display_name(sub_asset_code: str) -> str | None:
    """Get the display name for a sub-asset code.

    Args:
        sub_asset_code: The sub-asset code (e.g., "GERMAN_BUNDS")

    Returns:
        The display name (e.g., "German Bunds") or None
    """
    return SUB_ASSET_DISPLAY_NAMES.get(sub_asset_code)


def is_valid_category(category_code: str) -> bool:
    """Check if a category code is valid.

    Args:
        category_code: The category code to validate

    Returns:
        True if the category exists in the taxonomy
    """
    return category_code in CATEGORIES


def is_valid_sub_asset(sub_asset_code: str) -> bool:
    """Check if a sub-asset code is valid.

    Args:
        sub_asset_code: The sub-asset code to validate

    Returns:
        True if the sub-asset exists in the taxonomy
    """
    return sub_asset_code in _SUB_ASSET_TO_CATEGORY


def get_all_categories() -> list[str]:
    """Get all category codes.

    Returns:
        List of all category codes
    """
    return list(CATEGORIES.keys())


def get_all_sub_assets() -> list[str]:
    """Get all sub-asset codes.

    Returns:
        List of all sub-asset codes
    """
    return list(_SUB_ASSET_TO_CATEGORY.keys())
