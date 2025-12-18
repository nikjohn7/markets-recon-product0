"""ProcessedDocument model (final pipeline output).

Complete output for one processed PDF.
"""

from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from src.models.calls import AllocationCall
from src.models.confidence import ConfidenceResult
from src.models.core import Citation
from src.models.enums import Sentiment
from src.models.profile import DocumentProfile
from src.models.summaries import DocumentSummaries
from src.models.tags import TagSet


class ProcessedDocument(BaseModel):
    """Complete output for one PDF."""

    model_config = ConfigDict(extra="forbid")

    document_id: str

    # From Stage 4
    profile: DocumentProfile

    # From Stage 6
    allocation_calls: list[AllocationCall]
    overall_sentiment: Sentiment
    sentiment_rationale: list[str]
    sentiment_citations: list[Citation]

    # From Stage 7
    summaries: DocumentSummaries

    # From Stage 9
    tags: TagSet

    # From Stage 10
    confidence: ConfidenceResult

    # Metadata
    processing_timestamp: datetime
    pipeline_version: str
    total_processing_time_seconds: float = Field(..., ge=0)

    def to_allocator_pro_calls(self) -> list[dict[str, Any]]:
        """Format calls for Allocator Pro Module 1/2."""
        as_of = self.profile.as_of_date or self.profile.publication_date
        return [
            {
                "manager_name": self.profile.manager_name,
                "document_id": self.document_id,
                "as_of_date": as_of.isoformat() if as_of else None,
                "asset_class_category": call.asset_class_category,
                "sub_asset_class": call.sub_asset_class,
                "call": call.call.value,
                "rationale": call.rationale_bullets,
                "tooltip": call.tooltip_text,
            }
            for call in self.allocation_calls
        ]

    def to_search_document(self) -> dict[str, Any]:
        """Format for search index."""
        return {
            "document_id": self.document_id,
            "manager_name": self.profile.manager_name,
            "title": self.profile.title,
            "publication_date": self.profile.publication_date.isoformat()
            if self.profile.publication_date
            else None,
            "document_type": self.profile.document_type.value,
            "executive_summary": self.summaries.executive_summary,
            "search_descriptor": self.summaries.search_descriptor,
            "key_takeaways": [t.text for t in self.summaries.key_takeaways],
            "overall_sentiment": self.overall_sentiment.value,
            "asset_class_tags": self.tags.asset_class_tags,
            "region_tags": self.tags.region_tags,
            "theme_tags": self.tags.theme_tags,
            "risk_tags": self.tags.risk_tags,
            "calls": [
                {
                    "asset_class_category": c.asset_class_category,
                    "sub_asset_class": c.sub_asset_class,
                    "call": c.call.value,
                    "tooltip_text": c.tooltip_text,
                }
                for c in self.allocation_calls
            ],
        }
