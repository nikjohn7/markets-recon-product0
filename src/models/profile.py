"""Document profile model (Stage 4 output).

Extracted document metadata including manager info, dates, and document type.
"""

from datetime import date

from pydantic import BaseModel, Field

from src.models.core import Citation
from src.models.enums import DocumentType


class DocumentProfile(BaseModel):
    """Extracted document metadata."""

    document_id: str
    manager_name: str = Field(..., min_length=1)
    title: str
    publication_date: date | None = Field(None, description="Publication date if found")
    as_of_date: date | None = Field(None, description="'As of' date if different")
    document_type: DocumentType
    asset_classes_covered: list[str] = Field(..., min_length=1)
    regions: list[str] = Field(default_factory=list)
    time_horizon: str | None = Field(None, description="e.g., '6-12M', '3-6M'")
    intended_audience: str | None = None
    citations: list[Citation] = Field(..., min_length=1)

    # Null handling
    manager_name_uncertain: bool = False
    publication_date_uncertain: bool = False
