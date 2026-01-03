"""Core models used across the pipeline.

Citation and BoundingBox are foundational models referenced by many other schemas.
"""

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


class Citation(BaseModel, frozen=True):
    """Evidence reference back to source document."""

    model_config = ConfigDict(extra="forbid")

    chunk_id: str = Field(..., description="Retrieval chunk ID from Stage 3 index")
    block_ids: list[str] = Field(
        default_factory=list, description="Source block IDs for UI highlighting"
    )
    page: int = Field(..., ge=1, description="1-indexed page number")
    text_span: str | None = Field(
        None, max_length=200, description="Relevant text excerpt (≤200 chars)"
    )

    @field_validator("text_span", mode="before")
    @classmethod
    def truncate_text_span(cls, value: object) -> object:
        if isinstance(value, str) and len(value) > 200:
            return value[:200]
        return value


class BoundingBox(BaseModel):
    """Coordinates on page (normalized 0-1)."""

    model_config = ConfigDict(extra="forbid")

    x0: float = Field(..., ge=0, le=1)
    y0: float = Field(..., ge=0, le=1)
    x1: float = Field(..., ge=0, le=1)
    y1: float = Field(..., ge=0, le=1)

    @model_validator(mode="after")
    def check_bounds_order(self) -> "BoundingBox":
        if self.x0 > self.x1:
            raise ValueError("x0 must be <= x1")
        if self.y0 > self.y1:
            raise ValueError("y0 must be <= y1")
        return self
