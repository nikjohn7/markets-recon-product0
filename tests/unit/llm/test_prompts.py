"""Unit tests for LLM prompt templates.

Tests verify that:
1. Prompts include required schema, rules, and guardrails from LLM_CONTRACTS.md
2. Build functions produce valid prompts with proper formatting
3. Schemas match expected structure for Pydantic model validation
"""

from datetime import date

import pytest

from src.llm.prompts import (
    build_call_extraction_prompt,
    build_metadata_extraction_prompt,
    build_summary_generation_prompt,
    build_tag_generation_prompt,
    build_tooltip_generation_prompt,
    build_verification_prompt,
    format_calls_summary,
    format_chunks_for_prompt,
    format_taxonomy_summary,
    get_call_extraction_schema,
    get_document_types_list,
    get_metadata_extraction_schema,
    get_summary_generation_schema,
    get_tag_generation_schema,
    get_tooltip_generation_schema,
    get_verification_schema,
)
from src.models.calls import AllocationCall
from src.models.core import Citation
from src.models.enums import CallDirection, Conviction, DocumentType
from src.models.pipeline import RetrievedChunk
from src.models.profile import DocumentProfile


# ============================================================================
# Fixtures
# ============================================================================


@pytest.fixture
def sample_chunks() -> list[RetrievedChunk]:
    """Create sample retrieved chunks for testing."""
    return [
        RetrievedChunk(
            chunk_id="doc1_0",
            block_ids=["1_0", "1_1"],
            page=1,
            text="We are overweight European equities given improving growth dynamics.",
            score=0.92,
            section="macro",
        ),
        RetrievedChunk(
            chunk_id="doc1_1",
            block_ids=["2_0"],
            page=2,
            text="US duration is attractive as the Fed signals easing.",
            score=0.88,
            section="fixed_income",
        ),
    ]


@pytest.fixture
def sample_profile() -> DocumentProfile:
    """Create sample document profile for testing."""
    return DocumentProfile(
        document_id="doc1",
        manager_name="BlackRock",
        title="Q3 2025 Investment Outlook",
        publication_date=date(2025, 7, 15),
        as_of_date=None,
        document_type=DocumentType.QUARTERLY_OUTLOOK,
        asset_classes_covered=["EQUITIES", "FIXED_INCOME"],
        regions=["US", "EUROPE"],
        time_horizon="6-12M",
        citations=[
            Citation(chunk_id="doc1_0", page=1, text_span="Q3 2025 Investment Outlook")
        ],
    )


@pytest.fixture
def sample_calls() -> list[AllocationCall]:
    """Create sample allocation calls for testing."""
    return [
        AllocationCall(
            asset_class_category="EQ_DM",
            sub_asset_class="EQ_EUROPE",
            call=CallDirection.OVERWEIGHT,
            conviction=Conviction.HIGH,
            rationale_bullets=[
                "Improving growth dynamics in eurozone",
                "Valuation discount to US equities",
            ],
            citations=[
                Citation(chunk_id="doc1_0", page=1, text_span="overweight European equities")
            ],
            confidence=0.9,
        ),
        AllocationCall(
            asset_class_category="FI_SOV_US",
            sub_asset_class="UST_10Y",
            call=CallDirection.OVERWEIGHT,
            conviction=Conviction.MEDIUM,
            rationale_bullets=["Fed signals easing", "Attractive yield levels"],
            citations=[
                Citation(chunk_id="doc1_1", page=2, text_span="US duration is attractive")
            ],
            confidence=0.85,
        ),
    ]


# ============================================================================
# Metadata Prompt Tests (Stage 4)
# ============================================================================


class TestMetadataPrompt:
    """Tests for Stage 4 metadata extraction prompt."""

    def test_schema_has_required_fields(self) -> None:
        """Schema should include all DocumentProfile fields."""
        schema = get_metadata_extraction_schema()
        props = schema["properties"]

        assert "manager_name" in props
        assert "publication_date" in props
        assert "document_type" in props
        assert "asset_classes_covered" in props
        assert "citations" in props
        assert "manager_name_uncertain" in props
        assert "publication_date_uncertain" in props

    def test_schema_requires_citations(self) -> None:
        """Schema should require at least one citation."""
        schema = get_metadata_extraction_schema()
        citations = schema["properties"]["citations"]

        assert citations["type"] == "array"
        assert citations["minItems"] == 1

    def test_document_types_list_complete(self) -> None:
        """Document types list should include all DocumentType enum values."""
        doc_types_str = get_document_types_list()

        for doc_type in DocumentType:
            assert doc_type.value in doc_types_str

    def test_build_prompt_includes_chunks(
        self, sample_chunks: list[RetrievedChunk]
    ) -> None:
        """Built prompt should include formatted chunks."""
        prompt = build_metadata_extraction_prompt(sample_chunks)

        assert "doc1_0" in prompt
        assert "Page 1" in prompt
        assert "overweight European equities" in prompt

    def test_build_prompt_includes_schema(
        self, sample_chunks: list[RetrievedChunk]
    ) -> None:
        """Built prompt should include the JSON schema."""
        prompt = build_metadata_extraction_prompt(sample_chunks)

        assert '"manager_name"' in prompt
        assert '"document_type"' in prompt
        assert '"citations"' in prompt

    def test_build_prompt_includes_guardrails(
        self, sample_chunks: list[RetrievedChunk]
    ) -> None:
        """Built prompt should include critical guardrails."""
        prompt = build_metadata_extraction_prompt(sample_chunks)

        assert "Do NOT invent" in prompt or "Never guess" in prompt
        assert "uncertain" in prompt.lower()


# ============================================================================
# Call Extraction Prompt Tests (Stage 6)
# ============================================================================


class TestCallExtractionPrompt:
    """Tests for Stage 6 call extraction prompt."""

    def test_schema_has_required_fields(self) -> None:
        """Schema should include all call extraction fields."""
        schema = get_call_extraction_schema()
        props = schema["properties"]

        assert "allocation_calls" in props
        assert "overall_sentiment" in props
        assert "sentiment_rationale" in props
        assert "sentiment_citations" in props

    def test_call_schema_includes_taxonomy(self) -> None:
        """Call items should require taxonomy codes."""
        schema = get_call_extraction_schema()
        call_props = schema["properties"]["allocation_calls"]["items"]["properties"]

        assert "asset_class_category" in call_props
        assert "sub_asset_class" in call_props

    def test_taxonomy_summary_includes_categories(self) -> None:
        """Taxonomy summary should include major categories."""
        taxonomy = format_taxonomy_summary()

        assert "EQ_DM" in taxonomy
        assert "FI_SOV_EUROPE" in taxonomy
        assert "GERMAN_BUNDS" in taxonomy
        assert "ALT_COMMODITIES" in taxonomy
        assert "GOLD" in taxonomy

    def test_build_prompt_includes_context(
        self, sample_chunks: list[RetrievedChunk], sample_profile: DocumentProfile
    ) -> None:
        """Built prompt should include manager context."""
        prompt = build_call_extraction_prompt(sample_chunks, sample_profile)

        assert "BlackRock" in prompt
        assert "QUARTERLY_OUTLOOK" in prompt
        assert "2025-07-15" in prompt

    def test_build_prompt_includes_extraction_rules(
        self, sample_chunks: list[RetrievedChunk], sample_profile: DocumentProfile
    ) -> None:
        """Built prompt should include extraction rules."""
        prompt = build_call_extraction_prompt(sample_chunks, sample_profile)

        assert "OVERWEIGHT" in prompt
        assert "UNDERWEIGHT" in prompt
        assert "NEUTRAL" in prompt
        assert "UNCERTAIN" in prompt

    def test_build_prompt_includes_guardrails(
        self, sample_chunks: list[RetrievedChunk], sample_profile: DocumentProfile
    ) -> None:
        """Built prompt should include critical guardrails."""
        prompt = build_call_extraction_prompt(sample_chunks, sample_profile)

        assert "NO HALLUCINATION" in prompt
        assert "NO DUPLICATE CALLS" in prompt
        assert "needs_analyst_review" in prompt


# ============================================================================
# Summary Prompt Tests (Stage 7)
# ============================================================================


class TestSummaryPrompt:
    """Tests for Stage 7 summary generation prompt."""

    def test_schema_has_required_fields(self) -> None:
        """Schema should include all summary fields."""
        schema = get_summary_generation_schema()
        props = schema["properties"]

        assert "executive_summary" in props
        assert "search_descriptor" in props
        assert "key_takeaways" in props
        assert "citations" in props

    def test_schema_enforces_length_constraints(self) -> None:
        """Schema should enforce word/character limits."""
        schema = get_summary_generation_schema()

        exec_summary = schema["properties"]["executive_summary"]
        assert exec_summary["minLength"] == 100
        assert exec_summary["maxLength"] == 1000

        search_desc = schema["properties"]["search_descriptor"]
        assert search_desc["minLength"] == 50
        assert search_desc["maxLength"] == 200

    def test_format_calls_summary(self, sample_calls: list[AllocationCall]) -> None:
        """Calls should be formatted correctly for summary context."""
        summary = format_calls_summary(sample_calls)

        assert "EQ_EUROPE" in summary
        assert "OVERWEIGHT" in summary
        assert "UST_10Y" in summary

    def test_format_calls_summary_empty(self) -> None:
        """Empty calls list should return appropriate message."""
        summary = format_calls_summary([])

        assert "No allocation calls" in summary

    def test_build_prompt_includes_word_count_requirements(
        self,
        sample_chunks: list[RetrievedChunk],
        sample_calls: list[AllocationCall],
        sample_profile: DocumentProfile,
    ) -> None:
        """Built prompt should specify word count requirements."""
        prompt = build_summary_generation_prompt(
            sample_chunks, sample_calls, sample_profile
        )

        assert "120-180 words" in prompt
        assert "20-35 words" in prompt
        assert "≤200 characters" in prompt


# ============================================================================
# Tooltip Prompt Tests (Stage 8)
# ============================================================================


class TestTooltipPrompt:
    """Tests for Stage 8 tooltip generation prompt."""

    def test_schema_has_tooltips_array(self) -> None:
        """Schema should include tooltips array."""
        schema = get_tooltip_generation_schema()
        props = schema["properties"]

        assert "tooltips" in props
        assert props["tooltips"]["type"] == "array"

    def test_tooltip_schema_enforces_length(self) -> None:
        """Tooltip schema should enforce character limit."""
        schema = get_tooltip_generation_schema()
        tooltip_props = schema["properties"]["tooltips"]["items"]["properties"]

        assert tooltip_props["tooltip_text"]["maxLength"] == 150

    def test_build_prompt_includes_examples(
        self, sample_calls: list[AllocationCall]
    ) -> None:
        """Built prompt should include good and bad examples."""
        prompt = build_tooltip_generation_prompt(sample_calls)

        assert "Good tooltip" in prompt or "Good:" in prompt
        assert "Bad tooltip" in prompt or "Bad:" in prompt

    def test_build_prompt_formats_calls(
        self, sample_calls: list[AllocationCall]
    ) -> None:
        """Built prompt should format calls correctly."""
        prompt = build_tooltip_generation_prompt(sample_calls)

        assert "EQ_EUROPE" in prompt
        assert "OVERWEIGHT" in prompt
        assert "Improving growth dynamics" in prompt


# ============================================================================
# Tag Prompt Tests (Stage 9)
# ============================================================================


class TestTagPrompt:
    """Tests for Stage 9 tag generation prompt."""

    def test_schema_has_tag_categories(self) -> None:
        """Schema should include all tag categories."""
        schema = get_tag_generation_schema()
        props = schema["properties"]

        assert "theme_tags" in props
        assert "risk_tags" in props
        assert "macro_regime_tags" in props
        assert "novel_themes" in props

    def test_schema_includes_allowed_values(self) -> None:
        """Schema should enumerate allowed tag values."""
        schema = get_tag_generation_schema()

        theme_tags = schema["properties"]["theme_tags"]["items"]
        assert "enum" in theme_tags
        assert "inflation" in theme_tags["enum"]
        assert "fed_policy" in theme_tags["enum"]

        risk_tags = schema["properties"]["risk_tags"]["items"]
        assert "enum" in risk_tags
        assert "duration_risk" in risk_tags["enum"]

    def test_build_prompt_includes_vocabularies(
        self,
        sample_profile: DocumentProfile,
        sample_calls: list[AllocationCall],
        sample_chunks: list[RetrievedChunk],
    ) -> None:
        """Built prompt should include allowed vocabularies."""
        prompt = build_tag_generation_prompt(sample_profile, sample_calls, sample_chunks)

        assert "inflation" in prompt
        assert "recession_risk" in prompt
        assert "soft_landing" in prompt
        assert "duration_risk" in prompt

    def test_build_prompt_includes_mapping_guidance(
        self,
        sample_profile: DocumentProfile,
        sample_calls: list[AllocationCall],
        sample_chunks: list[RetrievedChunk],
    ) -> None:
        """Built prompt should include mapping guidance."""
        prompt = build_tag_generation_prompt(sample_profile, sample_calls, sample_chunks)

        assert "Mapping Guidance" in prompt or "Common" in prompt


# ============================================================================
# Verification Prompt Tests (Stage 6)
# ============================================================================


class TestVerificationPrompt:
    """Tests for Stage 6 verification pass prompt."""

    def test_schema_has_verification_fields(self) -> None:
        """Schema should include verification result fields."""
        schema = get_verification_schema()
        props = schema["properties"]

        assert "verified_calls" in props
        assert "agreement_rate" in props

    def test_verified_call_schema_includes_checks(self) -> None:
        """Verified call items should include all verification checks."""
        schema = get_verification_schema()
        call_props = schema["properties"]["verified_calls"]["items"]["properties"]

        assert "call_verified" in call_props
        assert "direction_correct" in call_props
        assert "taxonomy_correct" in call_props
        assert "rationale_accurate" in call_props
        assert "evidence_strength" in call_props

    def test_build_prompt_includes_calls(
        self,
        sample_calls: list[AllocationCall],
        sample_chunks: list[RetrievedChunk],
    ) -> None:
        """Built prompt should include original calls."""
        prompt = build_verification_prompt(sample_calls, sample_chunks)

        assert "EQ_EUROPE" in prompt
        assert "OVERWEIGHT" in prompt
        assert "Improving growth dynamics" in prompt

    def test_build_prompt_includes_verification_criteria(
        self,
        sample_calls: list[AllocationCall],
        sample_chunks: list[RetrievedChunk],
    ) -> None:
        """Built prompt should include verification criteria."""
        prompt = build_verification_prompt(sample_calls, sample_chunks)

        assert "verified" in prompt.lower()
        assert "Direction" in prompt
        assert "Taxonomy" in prompt
        assert "Rationale" in prompt


# ============================================================================
# Helper Function Tests
# ============================================================================


class TestHelperFunctions:
    """Tests for prompt helper functions."""

    def test_format_chunks_for_prompt(
        self, sample_chunks: list[RetrievedChunk]
    ) -> None:
        """Chunks should be formatted with headers and separators."""
        formatted = format_chunks_for_prompt(sample_chunks)

        assert "[Chunk doc1_0 | Page 1]" in formatted
        assert "[Chunk doc1_1 | Page 2]" in formatted
        assert "---" in formatted

    def test_format_chunks_preserves_text(
        self, sample_chunks: list[RetrievedChunk]
    ) -> None:
        """Formatted chunks should preserve original text."""
        formatted = format_chunks_for_prompt(sample_chunks)

        for chunk in sample_chunks:
            assert chunk.text in formatted


# ============================================================================
# Integration Tests
# ============================================================================


class TestPromptIntegration:
    """Integration tests for prompt templates."""

    def test_all_prompts_are_exportable(self) -> None:
        """All prompt functions should be importable from __init__."""
        from src.llm.prompts import (
            build_call_extraction_prompt,
            build_metadata_extraction_prompt,
            build_summary_generation_prompt,
            build_tag_generation_prompt,
            build_tooltip_generation_prompt,
            build_verification_prompt,
        )

        # Just verify they're callable
        assert callable(build_metadata_extraction_prompt)
        assert callable(build_call_extraction_prompt)
        assert callable(build_summary_generation_prompt)
        assert callable(build_tooltip_generation_prompt)
        assert callable(build_tag_generation_prompt)
        assert callable(build_verification_prompt)

    def test_all_schemas_are_valid_json_schema(self) -> None:
        """All schemas should be valid JSON schema format."""
        import json

        schemas = [
            get_metadata_extraction_schema(),
            get_call_extraction_schema(),
            get_summary_generation_schema(),
            get_tooltip_generation_schema(),
            get_tag_generation_schema(),
            get_verification_schema(),
        ]

        for schema in schemas:
            # Should be serializable to JSON
            json_str = json.dumps(schema)
            assert len(json_str) > 0

            # Should have type field
            assert "type" in schema
            assert schema["type"] == "object"

            # Should have properties
            assert "properties" in schema
