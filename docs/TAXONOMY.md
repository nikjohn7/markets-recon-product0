# Asset Class Taxonomy

This document defines the canonical taxonomy used for classifying allocation calls. All LLM extractions must map to this taxonomy.

---

## Taxonomy Principles

1. **Hierarchical:** Category → Sub-asset class
2. **Canonical:** One correct way to refer to each item
3. **Extensible:** New items can be added with review
4. **Synonym-aware:** Common variants map to canonical names

---

## Asset Class Categories

### Alternatives

| Category Code | Display Name |
|---------------|--------------|
| `ALT_COMMODITIES` | Alternatives: Commodities |
| `ALT_HEDGE_FUNDS` | Alternatives: Hedge Funds |
| `ALT_INFRASTRUCTURE` | Alternatives: Infrastructure |
| `ALT_PRIVATE_CREDIT` | Alternatives: Private Credit |
| `ALT_PRIVATE_EQUITY` | Alternatives: Private Equity |
| `ALT_REAL_ESTATE_GLOBAL` | Alternatives: Real Estate |
| `ALT_REAL_ESTATE_APAC` | Alternatives: Real Estate (APAC) |
| `ALT_REAL_ESTATE_NA` | Alternatives: Real Estate (North America) |
| `ALT_REAL_ESTATE_UK` | Alternatives: Real Estate (UK) |
| `ALT_REAL_ESTATE_EU` | Alternatives: Real Estate (EU) |
| `ALT_RE_INFRA` | Alternatives: Real Estate/Infrastructure |

### Equities

| Category Code | Display Name |
|---------------|--------------|
| `EQ_DM_CAPS` | Equities: Developed Market Caps |
| `EQ_DM` | Equities: Developed Markets |
| `EQ_EM` | Equities: Emerging Markets |
| `EQ_FACTORS` | Equities: Factors |
| `EQ_GEOS` | Equities: Geographies |
| `EQ_SECTORS` | Equities: Sectors |
| `EQ_THEMATICS` | Equities: Thematics |

### Fixed Income

| Category Code | Display Name |
|---------------|--------------|
| `FI_DURATION` | Fixed Income: Duration |
| `FI_GEO` | Fixed Income: Geography |
| `FI_HY` | Fixed Income: High Yield |
| `FI_IG` | Fixed Income: Investment Grade |
| `FI_SOV_GLOBAL` | Fixed Income: Sovereigns |
| `FI_SOV_APAC` | Fixed Income: Sovereigns (APAC) |
| `FI_SOV_EUROPE` | Fixed Income: Sovereigns (Europe) |
| `FI_SOV_NA` | Fixed Income: Sovereigns (North America) |
| `FI_SPECIALTY` | Fixed Income: Specialty |

### Currencies

| Category Code | Display Name |
|---------------|--------------|
| `FX_CURRENCIES` | Currencies |

### Asset Allocation (Multi-Asset)

| Category Code | Display Name |
|---------------|--------------|
| `AA_BROAD` | Asset Allocation |

---

## Sub-Asset Classes

### Alternatives: Commodities (`ALT_COMMODITIES`)

| Code | Display Name | Synonyms |
|------|--------------|----------|
| `GOLD` | Gold | gold, XAU |
| `SILVER` | Silver | silver, XAG |
| `OIL_CRUDE` | Crude Oil | crude, WTI, Brent, oil |
| `NATURAL_GAS` | Natural Gas | nat gas, NG |
| `COPPER` | Copper | copper |
| `AGRICULTURE` | Agriculture | agri, soft commodities |
| `COMMODITIES_BROAD` | Broad Commodities | commodities basket |

### Alternatives: Real Estate (`ALT_REAL_ESTATE_*`)

| Code | Display Name | Synonyms |
|------|--------------|----------|
| `RE_OFFICE` | Office | office real estate |
| `RE_RETAIL` | Retail | retail real estate |
| `RE_INDUSTRIAL` | Industrial/Logistics | logistics, warehouses |
| `RE_RESIDENTIAL` | Residential | housing |
| `RE_DATA_CENTERS` | Data Centers | data centers |
| `RE_HOSPITALITY` | Hospitality | hotels |

### Equities: Developed Markets (`EQ_DM`)

| Code | Display Name | Synonyms |
|------|--------------|----------|
| `EQ_US` | US Equities | US stocks, American equities, S&P 500 |
| `EQ_EUROPE` | European Equities | Europe stocks, STOXX |
| `EQ_UK` | UK Equities | UK stocks, FTSE |
| `EQ_JAPAN` | Japan Equities | Japan stocks, Nikkei, TOPIX |
| `EQ_AUSTRALIA` | Australia Equities | ASX |
| `EQ_CANADA` | Canada Equities | TSX |

### Equities: Emerging Markets (`EQ_EM`)

| Code | Display Name | Synonyms |
|------|--------------|----------|
| `EQ_EM_BROAD` | EM Equities (Broad) | emerging markets, EM stocks |
| `EQ_CHINA` | China Equities | China stocks, CSI, MSCI China |
| `EQ_INDIA` | India Equities | India stocks, Nifty |
| `EQ_LATAM` | LatAm Equities | Latin America |
| `EQ_EM_ASIA_EX_CHINA` | EM Asia ex-China | Asia ex-China |
| `EQ_EMEA` | EMEA Equities | Eastern Europe, Middle East, Africa |

### Equities: Factors (`EQ_FACTORS`)

| Code | Display Name | Synonyms |
|------|--------------|----------|
| `EQ_VALUE` | Value | value stocks, cheap |
| `EQ_GROWTH` | Growth | growth stocks |
| `EQ_QUALITY` | Quality | quality factor |
| `EQ_MOMENTUM` | Momentum | momentum factor |
| `EQ_LOW_VOL` | Low Volatility | min vol, defensive |
| `EQ_SIZE_SMALL` | Small Cap | small caps |
| `EQ_SIZE_MID` | Mid Cap | mid caps |
| `EQ_SIZE_LARGE` | Large Cap | large caps, mega cap |
| `EQ_DIVIDEND` | Dividend/Income | high dividend, income |

### Equities: Sectors (`EQ_SECTORS`)

| Code | Display Name | Synonyms |
|------|--------------|----------|
| `EQ_TECH` | Technology | tech, IT |
| `EQ_HEALTHCARE` | Healthcare | health care, pharma |
| `EQ_FINANCIALS` | Financials | banks, insurance |
| `EQ_ENERGY` | Energy | oil & gas, energy sector |
| `EQ_INDUSTRIALS` | Industrials | industrial |
| `EQ_MATERIALS` | Materials | basic materials |
| `EQ_CONSUMER_DISC` | Consumer Discretionary | cyclical consumer |
| `EQ_CONSUMER_STAPLES` | Consumer Staples | defensive consumer |
| `EQ_UTILITIES` | Utilities | utilities sector |
| `EQ_REAL_ESTATE` | Real Estate (Equities) | REITs |
| `EQ_COMMUNICATION` | Communication Services | telecoms, media |

### Fixed Income: Sovereigns Europe (`FI_SOV_EUROPE`)

| Code | Display Name | Synonyms |
|------|--------------|----------|
| `EURO_GOVT_BONDS` | Euro Government Bonds | eurozone govies, EUR govies |
| `GERMAN_BUNDS` | German Bunds | Bunds, Germany |
| `FRENCH_OATS` | French Government Bonds | OATs, France |
| `ITALIAN_BTPS` | Italian BTPs | BTPs, Italy |
| `SPANISH_BONOS` | Spanish Bonos | Spain |
| `UK_GILTS` | UK Gilts | Gilts, UK government |
| `SWISS_GOVT` | Swiss Government Bonds | Switzerland |
| `EUROPE_PERIPHERY` | European Periphery | GIIPS, periphery |
| `EUROPE_CORE` | European Core | core Europe |
| `EUROPE_DURATION` | Europe Duration | European duration |
| `POLISH_BONDS` | Polish Government Bonds | Poland |

### Fixed Income: Sovereigns APAC (`FI_SOV_APAC`)

| Code | Display Name | Synonyms |
|------|--------------|----------|
| `JGB` | Japanese Government Bonds | JGBs, Japan |
| `JAPAN_DURATION` | Japan Duration | Japanese duration |
| `AUSTRALIA_GOVT` | Australian Government Bonds | AGBs, Australia |
| `CHINA_GOVT` | Chinese Government Bonds | CGBs, China onshore |

### Fixed Income: Sovereigns North America (`FI_SOV_NA`)

| Code | Display Name | Synonyms |
|------|--------------|----------|
| `US_TREASURIES` | US Treasuries | Treasuries, UST |
| `US_TIPS` | US TIPS | TIPS, inflation-linked |
| `US_DURATION` | US Duration | American duration |
| `CANADA_GOVT` | Canadian Government Bonds | Canada |

### Fixed Income: Investment Grade (`FI_IG`)

| Code | Display Name | Synonyms |
|------|--------------|----------|
| `IG_US` | US Investment Grade | US IG, US corporate IG |
| `IG_EUROPE` | European Investment Grade | EUR IG, European IG |
| `IG_GLOBAL` | Global Investment Grade | global IG |
| `IG_FINANCIALS` | IG Financials | investment grade financials |
| `IG_NON_FIN` | IG Non-Financials | IG corporates ex-financials |

### Fixed Income: High Yield (`FI_HY`)

| Code | Display Name | Synonyms |
|------|--------------|----------|
| `HY_US` | US High Yield | US HY, junk bonds |
| `HY_EUROPE` | European High Yield | EUR HY |
| `HY_GLOBAL` | Global High Yield | global HY |
| `HY_EM` | EM High Yield | emerging market HY |

### Fixed Income: Specialty (`FI_SPECIALTY`)

| Code | Display Name | Synonyms |
|------|--------------|----------|
| `EM_SOVEREIGN_HARD` | EM Sovereign (Hard Currency) | EM HC, EM USD |
| `EM_SOVEREIGN_LOCAL` | EM Sovereign (Local Currency) | EM LC, EM local |
| `EM_CORPORATE` | EM Corporate Bonds | EM corporates |
| `MBS` | Mortgage-Backed Securities | MBS, agency MBS |
| `ABS` | Asset-Backed Securities | ABS |
| `CLO` | Collateralized Loan Obligations | CLOs |
| `CONVERTIBLES` | Convertible Bonds | converts |
| `INFLATION_LINKED` | Inflation-Linked Bonds | linkers, ILBs |

### Currencies (`FX_CURRENCIES`)

| Code | Display Name | Synonyms |
|------|--------------|----------|
| `USD` | US Dollar | dollar, greenback |
| `EUR` | Euro | euro |
| `GBP` | British Pound | pound, sterling |
| `JPY` | Japanese Yen | yen |
| `CHF` | Swiss Franc | franc |
| `AUD` | Australian Dollar | aussie |
| `CAD` | Canadian Dollar | loonie |
| `CNY` | Chinese Yuan | yuan, renminbi, RMB |
| `EM_FX_BASKET` | EM Currency Basket | EM FX |
| `ASIA_FX_BASKET` | Asia Currency Basket | Asia FX |
| `DIGITAL_ASSETS` | Digital Assets/Bitcoin | Bitcoin, crypto |

---

## Synonym Resolution

The system maintains a synonym map for fuzzy matching:

```python
SYNONYMS: dict[str, str] = {
    # Exact lowercase → canonical code
    "bunds": "GERMAN_BUNDS",
    "german bunds": "GERMAN_BUNDS",
    "gilts": "UK_GILTS",
    "uk gilts": "UK_GILTS",
    "treasuries": "US_TREASURIES",
    "us treasuries": "US_TREASURIES",
    "jgbs": "JGB",
    "japanese government bonds": "JGB",
    "tips": "US_TIPS",
    "s&p 500": "EQ_US",
    "nasdaq": "EQ_US",
    "euro government bonds": "EURO_GOVT_BONDS",
    "eurozone govies": "EURO_GOVT_BONDS",
    # ... extensive list
}
```

### Resolution Algorithm

```python
def resolve_asset(raw_text: str, taxonomy: Taxonomy) -> tuple[str, str] | None:
    """
    Returns (category_code, sub_asset_code) or None if unmapped.
    """
    normalized = raw_text.lower().strip()
    
    # 1. Exact match in synonyms
    if normalized in SYNONYMS:
        code = SYNONYMS[normalized]
        return taxonomy.get_category_for_code(code), code
    
    # 2. Partial match (LLM-assisted)
    candidates = taxonomy.fuzzy_search(normalized, threshold=0.8)
    if len(candidates) == 1:
        return candidates[0]
    
    # 3. Unable to resolve
    return None
```

---

## Tag Vocabularies

### Theme Tags (Allowed Values)

```python
THEME_TAGS = [
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
```

### Risk Tags (Allowed Values)

```python
RISK_TAGS = [
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
```

### Region Tags (Allowed Values)

```python
REGION_TAGS = [
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
```

### Macro Regime Tags (Allowed Values)

```python
MACRO_REGIME_TAGS = [
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
```

---

## Adding New Taxonomy Items

1. **Propose** new item with:
   - Category placement
   - Display name
   - Code (uppercase, underscores)
   - Synonyms
   
2. **Review** for:
   - Duplicate/overlap with existing
   - Appropriate category
   - Comprehensive synonyms
   
3. **Add** to this document and code
4. **Backfill** existing documents if needed

---

## Usage in LLM Prompts

When prompting LLMs for asset classification:

```
You must map asset mentions to this taxonomy:

Categories:
- FI_SOV_EUROPE: Fixed Income Sovereigns Europe
  Sub-assets: EURO_GOVT_BONDS, GERMAN_BUNDS, FRENCH_OATS, ...
- EQ_DM: Equities Developed Markets
  Sub-assets: EQ_US, EQ_EUROPE, EQ_UK, ...
[... full taxonomy ...]

For each asset mentioned:
1. Identify the category (e.g., FI_SOV_EUROPE)
2. Identify the sub-asset (e.g., GERMAN_BUNDS)
3. If no exact match, use closest or flag as UNMAPPED

Output format:
{
  "asset_class_category": "FI_SOV_EUROPE",
  "sub_asset_class": "GERMAN_BUNDS"
}
```
