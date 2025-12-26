"""Mock LLM responses for deterministic testing."""

from __future__ import annotations

from copy import deepcopy
from typing import TypeAlias, TypedDict

from src.llm.client import PipelineStage


class CitationDict(TypedDict, total=False):
    """Citation payload used in mock LLM responses."""

    chunk_id: str
    page: int
    text_span: str


class DocumentProfileResponse(TypedDict):
    """Mock response for Stage 4 metadata extraction."""

    manager_name: str
    title: str
    publication_date: str | None
    as_of_date: str | None
    document_type: str
    asset_classes_covered: list[str]
    regions: list[str]
    time_horizon: str | None
    intended_audience: str | None
    citations: list[CitationDict]
    manager_name_uncertain: bool
    publication_date_uncertain: bool


class CandidateExpansionResponse(TypedDict):
    """Mock response for Stage 5 candidate expansion."""

    additional_chunk_ids: list[str]
    reasoning: str


class KeyIndicatorDict(TypedDict):
    """Mock response entry for key indicators."""

    name: str
    direction: str
    why_it_matters: str


class CallLLMResponse(TypedDict):
    """Mock response for a single allocation call."""

    asset_class_category: str
    sub_asset_class: str
    call: str
    conviction: str | None
    time_horizon: str | None
    rationale_bullets: list[str]
    key_indicators: list[KeyIndicatorDict]
    key_risks: list[str]
    citations: list[CitationDict]
    confidence: float
    needs_analyst_review: bool
    review_reason: str | None


class CallExtractionResponse(TypedDict):
    """Mock response for Stage 6 call extraction."""

    allocation_calls: list[CallLLMResponse]
    overall_sentiment: str
    sentiment_rationale: list[str]
    sentiment_citations: list[CitationDict]
    sentiment_confidence: float


class KeyTakeawayResponse(TypedDict):
    """Mock response for a key takeaway."""

    text: str
    citations: list[CitationDict]


class SummaryGenerationResponse(TypedDict):
    """Mock response for Stage 7 summary generation."""

    executive_summary: str
    search_descriptor: str
    key_takeaways: list[KeyTakeawayResponse]
    citations: list[CitationDict]
    confidence: float


class TooltipItemResponse(TypedDict):
    """Mock response entry for Stage 8 tooltips."""

    sub_asset_class: str
    tooltip_text: str


class TooltipGenerationResponse(TypedDict):
    """Mock response for Stage 8 tooltip generation."""

    tooltips: list[TooltipItemResponse]


class TagGenerationResponse(TypedDict):
    """Mock response for Stage 9 tag generation."""

    theme_tags: list[str]
    risk_tags: list[str]
    macro_regime_tags: list[str]
    novel_themes: list[str]
    confidence: float


MockLLMResponse: TypeAlias = (
    DocumentProfileResponse
    | CandidateExpansionResponse
    | CallExtractionResponse
    | SummaryGenerationResponse
    | TooltipGenerationResponse
    | TagGenerationResponse
)


MOCK_METADATA_RESPONSE: DocumentProfileResponse = {
    "manager_name": "BlackRock",
    "title": "Mid-Year Investment Outlook 2025",
    "publication_date": "2025-07-15",
    "as_of_date": "2025-06-30",
    "document_type": "MID_YEAR_OUTLOOK",
    "asset_classes_covered": ["EQUITIES", "FIXED_INCOME"],
    "regions": ["US", "EUROPE"],
    "time_horizon": "6-12 months",
    "intended_audience": "Institutional investors",
    "citations": [{"chunk_id": "chunk_1", "page": 1}],
    "manager_name_uncertain": False,
    "publication_date_uncertain": False,
}

MOCK_CANDIDATE_EXPANSION_RESPONSE: CandidateExpansionResponse = {
    "additional_chunk_ids": ["chunk_5", "chunk_8"],
    "reasoning": "Found indirect preference language tied to duration and credit.",
}

MOCK_CALLS_RESPONSE: CallExtractionResponse = {
    "allocation_calls": [
        {
            "asset_class_category": "FI_SOV_EUROPE",
            "sub_asset_class": "GERMAN_BUNDS",
            "call": "OVERWEIGHT",
            "conviction": "MEDIUM",
            "time_horizon": "6-12 months",
            "rationale_bullets": [
                "ECB easing cycle supports duration demand.",
                "Bunds provide defensive carry in a soft landing.",
            ],
            "key_indicators": [
                {
                    "name": "ECB policy rate",
                    "direction": "FALLING",
                    "why_it_matters": "Lower rates improve Bund total returns.",
                }
            ],
            "key_risks": ["Inflation reacceleration"],
            "citations": [{"chunk_id": "chunk_4", "page": 4}],
            "confidence": 0.84,
            "needs_analyst_review": False,
            "review_reason": None,
        },
        {
            "asset_class_category": "EQ_DM",
            "sub_asset_class": "EQ_US",
            "call": "NEUTRAL",
            "conviction": "LOW",
            "time_horizon": None,
            "rationale_bullets": [
                "Valuations look full relative to earnings momentum.",
                "Policy easing may cushion downside risks.",
            ],
            "key_indicators": [
                {
                    "name": "Earnings revisions",
                    "direction": "STABLE",
                    "why_it_matters": "Stable revisions limit upside surprises.",
                }
            ],
            "key_risks": ["Valuation risk"],
            "citations": [{"chunk_id": "chunk_6", "page": 6}],
            "confidence": 0.62,
            "needs_analyst_review": False,
            "review_reason": None,
        },
    ],
    "overall_sentiment": "NEUTRAL",
    "sentiment_rationale": ["Balanced outlook with selective opportunities."],
    "sentiment_citations": [{"chunk_id": "chunk_2", "page": 2}],
    "sentiment_confidence": 0.73,
}

MOCK_SUMMARIES_RESPONSE: SummaryGenerationResponse = {
    "executive_summary": (
        "The mid-year outlook highlights a soft landing base case as inflation cools and "
        "central banks pivot toward easing. The manager expects policy rates to drift lower "
        "over the next two quarters, keeping duration demand firm while maintaining a "
        "measured stance on risk assets. Within fixed income, sovereign duration in Europe "
        "is favored for defensive carry and diversification benefits. US equities are held "
        "at neutral due to full valuations despite resilient earnings. The outlook flags "
        "inflation reacceleration and renewed volatility as key risks, while positioning "
        "stays balanced across regions. Overall, the strategy emphasizes selective risk-taking, "
        "consistent income, and readiness to add exposure if growth proves more durable."
    ),
    "search_descriptor": (
        "Mid-year outlook on a soft landing with selective fixed income duration exposure "
        "and neutral US equities amid easing policy and valuation discipline."
    ),
    "key_takeaways": [
        {
            "text": "European sovereign duration is overweight for carry and defensiveness.",
            "citations": [{"chunk_id": "chunk_4", "page": 4}],
        },
        {
            "text": "US equities stay neutral as valuations limit upside despite earnings stability.",
            "citations": [{"chunk_id": "chunk_6", "page": 6}],
        },
        {
            "text": "Macro risks include inflation surprises and renewed volatility.",
            "citations": [{"chunk_id": "chunk_3", "page": 3}],
        },
    ],
    "citations": [
        {"chunk_id": "chunk_1", "page": 1},
        {"chunk_id": "chunk_2", "page": 2},
    ],
    "confidence": 0.81,
}

MOCK_TOOLTIPS_RESPONSE: TooltipGenerationResponse = {
    "tooltips": [
        {
            "sub_asset_class": "GERMAN_BUNDS",
            "tooltip_text": "Overweight Bunds for defensive carry as ECB easing supports duration.",
        },
        {
            "sub_asset_class": "EQ_US",
            "tooltip_text": "Neutral US equities given full valuations despite stable earnings trends.",
        },
    ]
}

MOCK_TAGS_RESPONSE: TagGenerationResponse = {
    "theme_tags": ["inflation", "fed_policy", "rate_cuts"],
    "risk_tags": ["duration_risk", "valuation_risk"],
    "macro_regime_tags": ["soft_landing"],
    "novel_themes": ["ai_investment_cycle"],
    "confidence": 0.77,
}

MOCK_LLM_RESPONSES: dict[PipelineStage, MockLLMResponse] = {
    PipelineStage.METADATA: MOCK_METADATA_RESPONSE,
    PipelineStage.CANDIDATES: MOCK_CANDIDATE_EXPANSION_RESPONSE,
    PipelineStage.CALLS: MOCK_CALLS_RESPONSE,
    PipelineStage.SUMMARIES: MOCK_SUMMARIES_RESPONSE,
    PipelineStage.TOOLTIPS: MOCK_TOOLTIPS_RESPONSE,
    PipelineStage.TAGS: MOCK_TAGS_RESPONSE,
}


def get_mock_llm_response(stage: PipelineStage) -> MockLLMResponse:
    """Return a deep copy of the mock response for the requested stage."""
    if stage not in MOCK_LLM_RESPONSES:
        raise KeyError(f"No mock response configured for stage {stage}")
    return deepcopy(MOCK_LLM_RESPONSES[stage])
