"""Confidence models (Stage 10 output).

Models for confidence scoring and review routing.
"""

from pydantic import BaseModel, ConfigDict, Field, model_validator

from models.enums import ConfidenceBand


def compute_confidence_band(confidence: float) -> ConfidenceBand:
    """Compute confidence band from score. HIGH >= 0.80, MEDIUM 0.60-0.79, LOW < 0.60."""
    if confidence >= 0.80:
        return ConfidenceBand.HIGH
    elif confidence >= 0.60:
        return ConfidenceBand.MEDIUM
    else:
        return ConfidenceBand.LOW


class FieldConfidence(BaseModel):
    """Confidence for a single extracted field."""

    model_config = ConfigDict(extra="forbid")

    field_name: str
    confidence: float = Field(..., ge=0, le=1)
    reasons: list[str]
    has_explicit_evidence: bool
    evidence_strength: float = Field(..., ge=0, le=1)


class ConfidenceResult(BaseModel):
    """Overall confidence assessment for a document."""

    model_config = ConfigDict(extra="forbid")

    document_id: str

    extraction_coverage: float = Field(..., ge=0, le=1)
    overall_confidence: float = Field(..., ge=0, le=1)
    confidence_band: ConfidenceBand

    field_confidences: list[FieldConfidence]

    analyst_attention_required: bool
    attention_reasons: list[str]

    # Cross-pass agreement (if verification pass was run)
    verification_agreement: float | None = Field(None, ge=0, le=1)
    disagreed_fields: list[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def check_band_matches_confidence(self) -> "ConfidenceResult":
        expected = compute_confidence_band(self.overall_confidence)
        if self.confidence_band != expected:
            raise ValueError(
                f"confidence_band {self.confidence_band} doesn't match "
                f"overall_confidence {self.overall_confidence} (expected {expected})"
            )
        return self
