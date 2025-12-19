"""Unit tests for synonym resolution."""


from src.taxonomy import synonyms


class TestResolveAsset:
    """Test the resolve_asset function."""

    def test_resolve_bunds(self) -> None:
        """'bunds' should resolve to FI_SOV_EUROPE, GERMAN_BUNDS."""
        result = synonyms.resolve_asset("bunds")
        assert result == ("FI_SOV_EUROPE", "GERMAN_BUNDS")

    def test_resolve_case_insensitive(self) -> None:
        """Resolution should be case-insensitive."""
        assert synonyms.resolve_asset("BUNDS") == ("FI_SOV_EUROPE", "GERMAN_BUNDS")
        assert synonyms.resolve_asset("Bunds") == ("FI_SOV_EUROPE", "GERMAN_BUNDS")
        assert synonyms.resolve_asset("bUnDs") == ("FI_SOV_EUROPE", "GERMAN_BUNDS")

    def test_resolve_with_whitespace(self) -> None:
        """Should strip leading/trailing whitespace."""
        assert synonyms.resolve_asset("  bunds  ") == ("FI_SOV_EUROPE", "GERMAN_BUNDS")
        assert synonyms.resolve_asset("\tbunds\n") == ("FI_SOV_EUROPE", "GERMAN_BUNDS")

    def test_resolve_multi_word_synonym(self) -> None:
        """Should resolve multi-word synonyms."""
        assert synonyms.resolve_asset("us treasuries") == ("FI_SOV_NA", "US_TREASURIES")
        assert synonyms.resolve_asset("emerging markets") == ("EQ_EM", "EQ_EM_BROAD")
        assert synonyms.resolve_asset("s&p 500") == ("EQ_DM", "EQ_US")

    def test_resolve_unknown_term(self) -> None:
        """Unknown terms should return None."""
        assert synonyms.resolve_asset("unknown asset class") is None
        assert synonyms.resolve_asset("xyz123") is None

    def test_resolve_empty_string(self) -> None:
        """Empty string should return None."""
        assert synonyms.resolve_asset("") is None
        assert synonyms.resolve_asset("   ") is None

    def test_resolve_various_asset_classes(self) -> None:
        """Test resolution across different asset classes."""
        # Equities
        assert synonyms.resolve_asset("us stocks") == ("EQ_DM", "EQ_US")
        assert synonyms.resolve_asset("china equities") == ("EQ_EM", "EQ_CHINA")

        # Fixed Income
        assert synonyms.resolve_asset("gilts") == ("FI_SOV_EUROPE", "UK_GILTS")
        assert synonyms.resolve_asset("jgbs") == ("FI_SOV_APAC", "JGB")
        assert synonyms.resolve_asset("junk bonds") == ("FI_HY", "HY_US")

        # Commodities
        assert synonyms.resolve_asset("gold") == ("ALT_COMMODITIES", "GOLD")
        assert synonyms.resolve_asset("crude") == ("ALT_COMMODITIES", "OIL_CRUDE")

        # Currencies
        assert synonyms.resolve_asset("dollar") == ("FX_CURRENCIES", "USD")
        assert synonyms.resolve_asset("yen") == ("FX_CURRENCIES", "JPY")


class TestSynonymCoverage:
    """Test synonym coverage for key sub-assets."""

    def test_european_sovereigns_coverage(self) -> None:
        """European sovereign synonyms should all resolve correctly."""
        european_tests = [
            ("bunds", "GERMAN_BUNDS"),
            ("gilts", "UK_GILTS"),
            ("oats", "FRENCH_OATS"),
            ("btps", "ITALIAN_BTPS"),
        ]

        for synonym, expected_sub_asset in european_tests:
            result = synonyms.resolve_asset(synonym)
            assert result is not None
            assert result[1] == expected_sub_asset

    def test_us_asset_synonyms(self) -> None:
        """US asset synonyms should resolve correctly."""
        us_tests = [
            ("treasuries", "US_TREASURIES"),
            ("tips", "US_TIPS"),
            ("us stocks", "EQ_US"),
            ("nasdaq", "EQ_US"),
            ("s&p 500", "EQ_US"),
        ]

        for synonym, expected_sub_asset in us_tests:
            result = synonyms.resolve_asset(synonym)
            assert result is not None
            assert result[1] == expected_sub_asset

    def test_em_synonyms(self) -> None:
        """Emerging market synonyms should resolve correctly."""
        em_tests = [
            ("emerging markets", "EQ_EM_BROAD"),
            ("em stocks", "EQ_EM_BROAD"),
            ("em fx", "EM_FX_BASKET"),
        ]

        for synonym, expected_sub_asset in em_tests:
            result = synonyms.resolve_asset(synonym)
            assert result is not None
            assert result[1] == expected_sub_asset


class TestGetAllSynonymsForSubAsset:
    """Test retrieving all synonyms for a sub-asset."""

    def test_get_synonyms_for_german_bunds(self) -> None:
        """GERMAN_BUNDS should have multiple synonyms."""
        synonyms_list = synonyms.get_all_synonyms_for_sub_asset("GERMAN_BUNDS")
        assert "bunds" in synonyms_list
        assert "german bunds" in synonyms_list
        assert "germany" in synonyms_list
        assert len(synonyms_list) >= 3

    def test_get_synonyms_for_us_treasuries(self) -> None:
        """US_TREASURIES should have multiple synonyms."""
        synonyms_list = synonyms.get_all_synonyms_for_sub_asset("US_TREASURIES")
        assert "treasuries" in synonyms_list
        assert "us treasuries" in synonyms_list
        assert "ust" in synonyms_list

    def test_get_synonyms_for_nonexistent_sub_asset(self) -> None:
        """Non-existent sub-asset should return empty list."""
        synonyms_list = synonyms.get_all_synonyms_for_sub_asset("NONEXISTENT")
        assert synonyms_list == []


class TestIsValidSynonym:
    """Test synonym validation."""

    def test_valid_synonyms(self) -> None:
        """Valid synonyms should return True."""
        assert synonyms.is_valid_synonym("bunds") is True
        assert synonyms.is_valid_synonym("treasuries") is True
        assert synonyms.is_valid_synonym("gold") is True

    def test_valid_synonym_case_insensitive(self) -> None:
        """Validation should be case-insensitive."""
        assert synonyms.is_valid_synonym("BUNDS") is True
        assert synonyms.is_valid_synonym("Bunds") is True

    def test_valid_synonym_with_whitespace(self) -> None:
        """Should handle whitespace."""
        assert synonyms.is_valid_synonym("  bunds  ") is True

    def test_invalid_synonyms(self) -> None:
        """Invalid synonyms should return False."""
        assert synonyms.is_valid_synonym("unknown") is False
        assert synonyms.is_valid_synonym("xyz123") is False
        assert synonyms.is_valid_synonym("") is False


class TestSynonymMapping:
    """Test the SYNONYMS dict structure."""

    def test_all_synonyms_map_to_valid_sub_assets(self) -> None:
        """Every synonym should map to a valid sub-asset in the hierarchy."""
        from src.taxonomy.hierarchy import is_valid_sub_asset

        for synonym, sub_asset_code in synonyms.SYNONYMS.items():
            assert is_valid_sub_asset(sub_asset_code), (
                f"Synonym '{synonym}' maps to invalid sub-asset '{sub_asset_code}'"
            )

    def test_all_synonyms_are_lowercase(self) -> None:
        """All synonym keys should be lowercase for consistency."""
        for synonym in synonyms.SYNONYMS.keys():
            assert synonym == synonym.lower(), f"Synonym '{synonym}' should be lowercase"

    def test_no_duplicate_synonyms(self) -> None:
        """No synonym should appear twice in the dict."""
        # This is automatically enforced by dict, but we test the intention
        assert len(synonyms.SYNONYMS) == len(set(synonyms.SYNONYMS.keys()))


class TestEdgeCases:
    """Test edge cases and corner scenarios."""

    def test_special_characters_in_synonyms(self) -> None:
        """Synonyms with special characters should work."""
        # Test synonyms with special characters that exist
        assert synonyms.resolve_asset("s&p 500") == ("EQ_DM", "EQ_US")
        assert synonyms.resolve_asset("oil & gas") == ("EQ_SECTORS", "EQ_ENERGY")

    def test_abbreviations(self) -> None:
        """Common abbreviations should resolve correctly."""
        abbreviation_tests = [
            ("ig", None),  # Too ambiguous, likely not in synonyms
            ("hy", None),  # Too ambiguous
            ("em", None),  # Too ambiguous alone
            ("ust", ("FI_SOV_NA", "US_TREASURIES")),
            ("jgbs", ("FI_SOV_APAC", "JGB")),
        ]

        for abbrev, expected in abbreviation_tests:
            result = synonyms.resolve_asset(abbrev)
            assert result == expected

    def test_regional_variations(self) -> None:
        """Regional variations should resolve correctly."""
        # US vs American
        assert synonyms.resolve_asset("us equities") == ("EQ_DM", "EQ_US")
        assert synonyms.resolve_asset("american equities") == ("EQ_DM", "EQ_US")

        # UK variations
        assert synonyms.resolve_asset("uk stocks") == ("EQ_DM", "EQ_UK")
        assert synonyms.resolve_asset("uk gilts") == ("FI_SOV_EUROPE", "UK_GILTS")


class TestComprehensiveCoverage:
    """Test comprehensive coverage of taxonomy."""

    def test_commodities_coverage(self) -> None:
        """All major commodities should have synonyms."""
        commodity_synonyms = ["gold", "silver", "oil", "copper", "natural gas"]
        for synonym in commodity_synonyms:
            result = synonyms.resolve_asset(synonym)
            assert result is not None
            assert result[0] == "ALT_COMMODITIES"

    def test_equity_sectors_coverage(self) -> None:
        """Major equity sectors should have synonyms."""
        sector_synonyms = ["tech", "healthcare", "financials", "energy"]
        for synonym in sector_synonyms:
            result = synonyms.resolve_asset(synonym)
            assert result is not None
            assert result[0] == "EQ_SECTORS"

    def test_major_currencies_coverage(self) -> None:
        """Major currencies should have synonyms."""
        currency_synonyms = ["dollar", "euro", "yen", "pound"]
        for synonym in currency_synonyms:
            result = synonyms.resolve_asset(synonym)
            assert result is not None
            assert result[0] == "FX_CURRENCIES"
