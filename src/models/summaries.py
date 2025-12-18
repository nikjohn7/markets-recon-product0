"""Summary models (Stage 7 output).

Models for document summaries and key takeaways.
"""

from pydantic import BaseModel, ConfigDict, Field

from models.core import Citation


class KeyTakeaway(BaseModel):
    """Single takeaway bullet with evidence."""

    model_config = ConfigDict(extra="forbid")

    text: str = Field(..., max_length=200)
    citations: list[Citation] = Field(..., min_length=1)


class DocumentSummaries(BaseModel):
    """All summaries for one document."""

    model_config = ConfigDict(extra="forbid")

    document_id: str

    executive_summary: str = Field(
        ...,
        min_length=100,
        max_length=1000,
        description="120-180 words, max 6 bullets",
    )

    search_descriptor: str = Field(
        ...,
        min_length=50,
        max_length=200,
        description="20-35 words: what + implication + focus",
    )

    key_takeaways: list[KeyTakeaway] = Field(..., min_length=3, max_length=5)

    citations: list[Citation]
    confidence: float = Field(..., ge=0, le=1)
