from models.enums import TagType
from taxonomy import tags


class TestVocabularyContents:
    """Validate tag vocabulary contents against TAXONOMY.md."""

    def test_theme_tags_match_spec(self) -> None:
        expected = {
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
        }

        assert set(tags.THEME_TAGS) == expected

    def test_risk_tags_match_spec(self) -> None:
        expected = {
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
        }

        assert set(tags.RISK_TAGS) == expected

    def test_region_tags_match_spec(self) -> None:
        expected = {
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
        }

        assert set(tags.REGION_TAGS) == expected

    def test_macro_regime_tags_match_spec(self) -> None:
        expected = {
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
        }

        assert set(tags.MACRO_REGIME_TAGS) == expected


class TestValidation:
    """Test is_valid_tag helper."""

    def test_valid_tags(self) -> None:
        assert tags.is_valid_tag(TagType.THEME, "inflation") is True
        assert tags.is_valid_tag(TagType.RISK, "valuation_risk") is True
        assert tags.is_valid_tag(TagType.REGION, "europe") is True
        assert tags.is_valid_tag(TagType.MACRO_REGIME, "late_cycle") is True

    def test_validation_is_case_insensitive(self) -> None:
        assert tags.is_valid_tag(TagType.THEME, "Inflation") is True
        assert tags.is_valid_tag(TagType.RISK, " VALUATION_RISK ") is True

    def test_invalid_values(self) -> None:
        assert tags.is_valid_tag(TagType.THEME, "unknown") is False
        assert tags.is_valid_tag(TagType.RISK, "inflation") is False
        assert tags.is_valid_tag(TagType.REGION, "") is False

    def test_invalid_types(self) -> None:
        assert tags.is_valid_tag("INVALID", "inflation") is False
        assert tags.is_valid_tag(TagType.ASSET_CLASS, "us") is False

    def test_string_tag_type(self) -> None:
        assert tags.is_valid_tag("THEME", "inflation") is True
        assert tags.is_valid_tag("MACRO_REGIME", "goldilocks") is True
