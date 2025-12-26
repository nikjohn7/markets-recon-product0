"""Unit tests for taxonomy hierarchy."""

from src.taxonomy import hierarchy


class TestCategoryPresence:
    """Test that all expected categories are present."""

    def test_all_categories_present(self) -> None:
        """All categories from TAXONOMY.md should be present."""
        expected_categories = {
            # Alternatives
            "ALT_COMMODITIES",
            "ALT_HEDGE_FUNDS",
            "ALT_INFRASTRUCTURE",
            "ALT_PRIVATE_CREDIT",
            "ALT_PRIVATE_EQUITY",
            "ALT_REAL_ESTATE_GLOBAL",
            "ALT_REAL_ESTATE_APAC",
            "ALT_REAL_ESTATE_NA",
            "ALT_REAL_ESTATE_UK",
            "ALT_REAL_ESTATE_EU",
            "ALT_RE_INFRA",
            # Equities
            "EQ_DM_CAPS",
            "EQ_DM",
            "EQ_EM",
            "EQ_FACTORS",
            "EQ_GEOS",
            "EQ_SECTORS",
            "EQ_THEMATICS",
            # Fixed Income
            "FI_DURATION",
            "FI_GEO",
            "FI_HY",
            "FI_IG",
            "FI_SOV_GLOBAL",
            "FI_SOV_APAC",
            "FI_SOV_EUROPE",
            "FI_SOV_NA",
            "FI_SPECIALTY",
            # Currencies
            "FX_CURRENCIES",
            # Asset Allocation
            "AA_BROAD",
        }

        actual_categories = set(hierarchy.CATEGORIES.keys())
        assert actual_categories == expected_categories

    def test_all_categories_have_display_names(self) -> None:
        """Every category should have a display name."""
        for category_code in hierarchy.CATEGORIES:
            assert category_code in hierarchy.CATEGORY_DISPLAY_NAMES
            assert len(hierarchy.CATEGORY_DISPLAY_NAMES[category_code]) > 0


class TestSubAssetMappings:
    """Test sub-asset to category mappings."""

    def test_sub_asset_to_category_lookup(self) -> None:
        """Should be able to look up category for any sub-asset."""
        # Test a few specific cases
        assert hierarchy.get_category_for_sub_asset("GERMAN_BUNDS") == "FI_SOV_EUROPE"
        assert hierarchy.get_category_for_sub_asset("EQ_US") == "EQ_DM"
        assert hierarchy.get_category_for_sub_asset("GOLD") == "ALT_COMMODITIES"
        assert hierarchy.get_category_for_sub_asset("USD") == "FX_CURRENCIES"

    def test_category_to_sub_assets_lookup(self) -> None:
        """Should be able to get all sub-assets for a category."""
        # Test FI_SOV_EUROPE
        fi_sov_europe = hierarchy.get_sub_assets_for_category("FI_SOV_EUROPE")
        assert "GERMAN_BUNDS" in fi_sov_europe
        assert "UK_GILTS" in fi_sov_europe
        assert "EURO_GOVT_BONDS" in fi_sov_europe

        # Test EQ_DM
        eq_dm = hierarchy.get_sub_assets_for_category("EQ_DM")
        assert "EQ_US" in eq_dm
        assert "EQ_EUROPE" in eq_dm
        assert "EQ_JAPAN" in eq_dm

    def test_no_duplicate_sub_assets(self) -> None:
        """Each sub-asset should belong to exactly one category."""
        all_sub_assets: list[str] = []
        for sub_assets in hierarchy.CATEGORIES.values():
            all_sub_assets.extend(sub_assets)

        # Check for duplicates
        assert len(all_sub_assets) == len(set(all_sub_assets))

    def test_all_sub_assets_have_display_names(self) -> None:
        """Every sub-asset should have a display name."""
        for sub_assets in hierarchy.CATEGORIES.values():
            for sub_asset_code in sub_assets:
                assert sub_asset_code in hierarchy.SUB_ASSET_DISPLAY_NAMES
                assert len(hierarchy.SUB_ASSET_DISPLAY_NAMES[sub_asset_code]) > 0


class TestDisplayNames:
    """Test display name lookups."""

    def test_get_category_display_name(self) -> None:
        """Should return correct display names for categories."""
        assert (
            hierarchy.get_category_display_name("FI_SOV_EUROPE")
            == "Fixed Income: Sovereigns (Europe)"
        )
        assert hierarchy.get_category_display_name("EQ_DM") == "Equities: Developed Markets"
        assert hierarchy.get_category_display_name("ALT_COMMODITIES") == "Alternatives: Commodities"

    def test_get_sub_asset_display_name(self) -> None:
        """Should return correct display names for sub-assets."""
        assert hierarchy.get_sub_asset_display_name("GERMAN_BUNDS") == "German Bunds"
        assert hierarchy.get_sub_asset_display_name("EQ_US") == "US Equities"
        assert hierarchy.get_sub_asset_display_name("GOLD") == "Gold"

    def test_display_name_returns_none_for_invalid_code(self) -> None:
        """Should return None for codes that don't exist."""
        assert hierarchy.get_category_display_name("INVALID_CATEGORY") is None
        assert hierarchy.get_sub_asset_display_name("INVALID_SUB_ASSET") is None


class TestValidation:
    """Test validation functions."""

    def test_is_valid_category(self) -> None:
        """Should correctly validate category codes."""
        assert hierarchy.is_valid_category("FI_SOV_EUROPE") is True
        assert hierarchy.is_valid_category("EQ_DM") is True
        assert hierarchy.is_valid_category("INVALID_CATEGORY") is False
        assert hierarchy.is_valid_category("") is False

    def test_is_valid_sub_asset(self) -> None:
        """Should correctly validate sub-asset codes."""
        assert hierarchy.is_valid_sub_asset("GERMAN_BUNDS") is True
        assert hierarchy.is_valid_sub_asset("EQ_US") is True
        assert hierarchy.is_valid_sub_asset("INVALID_SUB_ASSET") is False
        assert hierarchy.is_valid_sub_asset("") is False


class TestGetAllFunctions:
    """Test functions that return all categories/sub-assets."""

    def test_get_all_categories(self) -> None:
        """Should return all category codes."""
        all_categories = hierarchy.get_all_categories()
        assert len(all_categories) > 0
        assert "FI_SOV_EUROPE" in all_categories
        assert "EQ_DM" in all_categories
        assert "ALT_COMMODITIES" in all_categories

    def test_get_all_sub_assets(self) -> None:
        """Should return all sub-asset codes."""
        all_sub_assets = hierarchy.get_all_sub_assets()
        assert len(all_sub_assets) > 0
        assert "GERMAN_BUNDS" in all_sub_assets
        assert "EQ_US" in all_sub_assets
        assert "GOLD" in all_sub_assets


class TestEdgeCases:
    """Test edge cases and error conditions."""

    def test_lookup_nonexistent_sub_asset(self) -> None:
        """Looking up nonexistent sub-asset should return None."""
        assert hierarchy.get_category_for_sub_asset("NONEXISTENT") is None

    def test_lookup_nonexistent_category(self) -> None:
        """Looking up nonexistent category should return empty list."""
        assert hierarchy.get_sub_assets_for_category("NONEXISTENT") == []

    def test_empty_string_lookups(self) -> None:
        """Empty strings should return None/empty list."""
        assert hierarchy.get_category_for_sub_asset("") is None
        assert hierarchy.get_sub_assets_for_category("") == []
        assert hierarchy.get_category_display_name("") is None
        assert hierarchy.get_sub_asset_display_name("") is None


class TestSpecificTaxonomyData:
    """Test specific taxonomy data points from TAXONOMY.md."""

    def test_commodities_sub_assets(self) -> None:
        """ALT_COMMODITIES should have all expected sub-assets."""
        commodities = hierarchy.get_sub_assets_for_category("ALT_COMMODITIES")
        expected = {
            "GOLD",
            "SILVER",
            "OIL_CRUDE",
            "NATURAL_GAS",
            "COPPER",
            "AGRICULTURE",
            "COMMODITIES_BROAD",
        }
        assert set(commodities) == expected

    def test_real_estate_sub_assets(self) -> None:
        """Real estate global category should have expected sub-assets."""
        re_sub_assets = hierarchy.get_sub_assets_for_category("ALT_REAL_ESTATE_GLOBAL")
        expected = {
            "RE_OFFICE",
            "RE_RETAIL",
            "RE_INDUSTRIAL",
            "RE_RESIDENTIAL",
            "RE_DATA_CENTERS",
            "RE_HOSPITALITY",
        }
        assert set(re_sub_assets) == expected

    def test_real_estate_regional_categories_empty(self) -> None:
        """Regional real estate categories are groupings without unique sub-assets."""
        assert hierarchy.get_sub_assets_for_category("ALT_REAL_ESTATE_APAC") == []
        assert hierarchy.get_sub_assets_for_category("ALT_REAL_ESTATE_NA") == []
        assert hierarchy.get_sub_assets_for_category("ALT_REAL_ESTATE_UK") == []
        assert hierarchy.get_sub_assets_for_category("ALT_REAL_ESTATE_EU") == []

    def test_equity_factors(self) -> None:
        """EQ_FACTORS should have all expected factor sub-assets."""
        factors = hierarchy.get_sub_assets_for_category("EQ_FACTORS")
        assert "EQ_VALUE" in factors
        assert "EQ_GROWTH" in factors
        assert "EQ_MOMENTUM" in factors
        assert "EQ_LOW_VOL" in factors
        assert "EQ_QUALITY" in factors

    def test_equity_sectors(self) -> None:
        """EQ_SECTORS should have all GICS-like sectors."""
        sectors = hierarchy.get_sub_assets_for_category("EQ_SECTORS")
        expected = {
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
        }
        assert set(sectors) == expected

    def test_fi_sov_europe_sub_assets(self) -> None:
        """FI_SOV_EUROPE should have all European sovereign sub-assets."""
        sov_europe = hierarchy.get_sub_assets_for_category("FI_SOV_EUROPE")
        assert "GERMAN_BUNDS" in sov_europe
        assert "UK_GILTS" in sov_europe
        assert "FRENCH_OATS" in sov_europe
        assert "ITALIAN_BTPS" in sov_europe
        assert "EURO_GOVT_BONDS" in sov_europe

    def test_currencies(self) -> None:
        """FX_CURRENCIES should have major currencies."""
        currencies = hierarchy.get_sub_assets_for_category("FX_CURRENCIES")
        assert "USD" in currencies
        assert "EUR" in currencies
        assert "GBP" in currencies
        assert "JPY" in currencies
        assert "DIGITAL_ASSETS" in currencies

    def test_categories_with_no_sub_assets(self) -> None:
        """Some categories have no sub-assets defined (placeholders)."""
        # These are valid categories but have no sub-assets in MVP
        assert hierarchy.get_sub_assets_for_category("ALT_HEDGE_FUNDS") == []
        assert hierarchy.get_sub_assets_for_category("ALT_INFRASTRUCTURE") == []
        assert hierarchy.get_sub_assets_for_category("EQ_THEMATICS") == []
        assert hierarchy.get_sub_assets_for_category("AA_BROAD") == []
