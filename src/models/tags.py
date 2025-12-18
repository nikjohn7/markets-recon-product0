"""Tag models (Stage 9 output).

Models for document tags and categorization.
"""

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from models.enums import TagType


class Tag(BaseModel):
    """Single normalized tag."""

    model_config = ConfigDict(extra="forbid")

    tag_type: TagType
    value: str
    confidence: float = Field(..., ge=0, le=1)
    source: Literal["rule", "llm"] = Field(..., description="'rule' or 'llm'")


class TagSet(BaseModel):
    """All tags for one document."""

    model_config = ConfigDict(extra="forbid")

    document_id: str

    asset_class_tags: list[str]
    region_tags: list[str]
    theme_tags: list[str]
    risk_tags: list[str]
    instrument_tags: list[str]
    style_tags: list[str]
    macro_regime_tags: list[str]

    all_tags: list[Tag] = Field(
        default_factory=list, description="Denormalized for indexing"
    )

    confidence: float = Field(..., ge=0, le=1)
