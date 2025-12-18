"""Allocation call models (Stage 6 output).

Models for representing extracted allocation calls and sentiment.
"""

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, field_validator

from models.core import Citation
from models.enums import CallDirection, Conviction, IndicatorDirection, Sentiment


class KeyIndicator(BaseModel):
    """Economic/market indicator referenced in rationale."""

    model_config = ConfigDict(extra="forbid")

    name: str = Field(..., description="e.g., 'Inflation trend', 'Fed policy'")
    direction: IndicatorDirection
    why_it_matters: str = Field(..., max_length=200)


class AllocationCall(BaseModel):
    """Single asset class positioning call."""

    model_config = ConfigDict(extra="forbid")

    asset_class_category: str = Field(
        ..., description="From taxonomy, e.g., 'FIXED_INCOME_SOVEREIGNS_EUROPE'"
    )
    sub_asset_class: str = Field(
        ..., description="From taxonomy, e.g., 'GERMAN_BUNDS'"
    )

    call: CallDirection
    conviction: Conviction | None = Field(
        None, description="Only if inferable from language"
    )
    time_horizon: str | None = Field(
        None, description="Explicit if stated; else inherit from doc"
    )

    rationale_bullets: list[str] = Field(..., min_length=1, max_length=4)
    key_indicators: list[KeyIndicator] = Field(default_factory=list, max_length=5)
    key_risks: list[str] = Field(default_factory=list, max_length=3)
    actionable_takeaways: list[str] = Field(default_factory=list, max_length=3)

    tooltip_text: str | None = Field(
        None, max_length=150, description="Generated in Stage 8"
    )

    citations: list[Citation] = Field(..., min_length=1, max_length=3)
    confidence: float = Field(..., ge=0, le=1)
    needs_analyst_review: bool = False
    review_reason: str | None = None

    @field_validator("rationale_bullets")
    @classmethod
    def bullets_not_empty(cls, v: list[str]) -> list[str]:
        if any(len(b.strip()) == 0 for b in v):
            raise ValueError("Rationale bullets cannot be empty strings")
        return v


class CallExtractionOutput(BaseModel):
    """Output of Stage 6: all calls from one document."""

    model_config = ConfigDict(extra="forbid")

    document_id: str
    allocation_calls: list[AllocationCall]
    overall_sentiment: Sentiment
    sentiment_rationale: list[str] = Field(..., min_length=1, max_length=3)
    sentiment_citations: list[Citation] = Field(..., min_length=1, max_length=3)
    sentiment_confidence: float = Field(..., ge=0, le=1)

    # Metadata
    extraction_timestamp: datetime
    model_version: str
    total_candidates_reviewed: int = Field(..., ge=0)
