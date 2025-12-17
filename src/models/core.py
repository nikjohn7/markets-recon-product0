"""Core models used across the pipeline.

Citation and BoundingBox are foundational models referenced by many other schemas.
"""

from pydantic import BaseModel, Field, field_validator


class Citation(BaseModel, frozen=True):
    """Evidence reference back to source document."""

    chunk_id: str = Field(..., description="Retrieval chunk ID from Stage 3 index")
    block_ids: list[str] = Field(
        default_factory=list, description="Source block IDs for UI highlighting"
    )
    page: int = Field(..., ge=1, description="1-indexed page number")
    text_span: str | None = Field(
        None, description="Relevant text excerpt (≤200 chars)"
    )

    @field_validator("text_span")
    @classmethod
    def text_span_max_length(cls, v: str | None) -> str | None:
        if v is not None and len(v) > 200:
            raise ValueError("text_span must be ≤200 characters")
        return v


class BoundingBox(BaseModel):
    """Coordinates on page (normalized 0-1)."""

    x0: float = Field(..., ge=0, le=1)
    y0: float = Field(..., ge=0, le=1)
    x1: float = Field(..., ge=0, le=1)
    y1: float = Field(..., ge=0, le=1)
