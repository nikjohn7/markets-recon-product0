"""Stage 6: Allocation call extraction.

Extracts structured allocation calls with taxonomy mapping, rationale, sentiment,
and citations from candidate passages.
"""

from __future__ import annotations

import logging
from datetime import UTC, datetime

from pydantic import BaseModel, ConfigDict, Field
from pydantic import ValidationError as PydanticValidationError

from src.exceptions import ExtractionError, ValidationError
from src.llm.client import LLMClient, PipelineStage
from src.llm.contracts import validate_llm_output
from src.llm.prompts.calls import build_call_extraction_prompt
from src.models.calls import AllocationCall, CallExtractionOutput, KeyIndicator
from src.models.core import Citation
from src.models.enums import CallDirection, Conviction, IndicatorDirection, Sentiment
from src.models.pipeline import CandidateSet
from src.models.profile import DocumentProfile

logger = logging.getLogger(__name__)


class CallLLM(BaseModel):
    """LLM output schema for a single allocation call."""

    model_config = ConfigDict(extra="forbid")

    asset_class_category: str
    sub_asset_class: str
    call: CallDirection
    conviction: Conviction | None = None
    time_horizon: str | None = None
    rationale_bullets: list[str] = Field(..., min_length=1, max_length=4)
    key_indicators: list[dict[str, str]] = Field(default_factory=list, max_length=5)
    key_risks: list[str] = Field(default_factory=list, max_length=3)
    citations: list[dict[str, str | int]] = Field(..., min_length=1, max_length=3)
    confidence: float = Field(..., ge=0, le=1)
    needs_analyst_review: bool = False
    review_reason: str | None = None


class CallExtractionLLM(BaseModel):
    """LLM output schema for call extraction."""

    model_config = ConfigDict(extra="forbid")

    allocation_calls: list[CallLLM]
    overall_sentiment: Sentiment
    sentiment_rationale: list[str] = Field(..., min_length=1, max_length=3)
    sentiment_citations: list[dict[str, str | int]] = Field(..., min_length=1, max_length=3)
    sentiment_confidence: float = Field(..., ge=0, le=1)


def _parse_citation(citation_dict: dict[str, str | int]) -> Citation:
    """Parse citation from LLM output dict.

    Args:
        citation_dict: Dict with chunk_id, page, optional text_span

    Returns:
        Citation object

    Raises:
        ValidationError: If citation is invalid
    """
    try:
        return Citation(
            chunk_id=str(citation_dict["chunk_id"]),
            page=int(citation_dict["page"]),
            text_span=str(citation_dict.get("text_span", "")) if "text_span" in citation_dict else None,
        )
    except (KeyError, ValueError, PydanticValidationError) as exc:
        raise ValidationError(f"Invalid citation format: {citation_dict}") from exc


def _parse_key_indicator(indicator_dict: dict[str, str]) -> KeyIndicator:
    """Parse key indicator from LLM output dict.

    Args:
        indicator_dict: Dict with name, direction, why_it_matters

    Returns:
        KeyIndicator object

    Raises:
        ValidationError: If indicator is invalid
    """
    try:
        return KeyIndicator(
            name=indicator_dict["name"],
            direction=IndicatorDirection(indicator_dict["direction"]),
            why_it_matters=indicator_dict["why_it_matters"],
        )
    except (KeyError, ValueError, PydanticValidationError) as exc:
        raise ValidationError(f"Invalid key indicator format: {indicator_dict}") from exc


def _parse_allocation_call(call_llm: CallLLM) -> AllocationCall:
    """Convert LLM output to AllocationCall model.

    Args:
        call_llm: LLM output for a single call

    Returns:
        AllocationCall object

    Raises:
        ValidationError: If conversion fails
    """
    citations = [_parse_citation(c) for c in call_llm.citations]
    key_indicators = [_parse_key_indicator(ind) for ind in call_llm.key_indicators]

    return AllocationCall(
        asset_class_category=call_llm.asset_class_category,
        sub_asset_class=call_llm.sub_asset_class,
        call=call_llm.call,
        conviction=call_llm.conviction,
        time_horizon=call_llm.time_horizon,
        rationale_bullets=call_llm.rationale_bullets,
        key_indicators=key_indicators,
        key_risks=call_llm.key_risks,
        actionable_takeaways=[],  # Generated in later stages
        tooltip_text=None,  # Generated in Stage 8
        citations=citations,
        confidence=call_llm.confidence,
        needs_analyst_review=call_llm.needs_analyst_review,
        review_reason=call_llm.review_reason,
    )


def _check_duplicate_calls(calls: list[AllocationCall]) -> None:
    """Verify no duplicate (category, sub_asset) pairs exist.

    Args:
        calls: List of allocation calls

    Raises:
        ValidationError: If duplicate calls detected
    """
    seen: set[tuple[str, str]] = set()
    for call in calls:
        key = (call.asset_class_category, call.sub_asset_class)
        if key in seen:
            raise ValidationError(
                f"Duplicate call detected: {call.asset_class_category} / {call.sub_asset_class}"
            )
        seen.add(key)


def _build_call_extraction_output(
    document_id: str,
    llm_output: CallExtractionLLM,
    total_candidates: int,
    model_version: str,
) -> CallExtractionOutput:
    """Build CallExtractionOutput from validated LLM output.

    Args:
        document_id: Document ID
        llm_output: Validated LLM output
        total_candidates: Number of candidate chunks reviewed
        model_version: LLM model version string

    Returns:
        CallExtractionOutput object

    Raises:
        ValidationError: If output construction fails
    """
    # Parse all allocation calls
    allocation_calls = [_parse_allocation_call(call_llm) for call_llm in llm_output.allocation_calls]

    # Check for duplicate calls
    _check_duplicate_calls(allocation_calls)

    # Parse sentiment citations
    sentiment_citations = [_parse_citation(c) for c in llm_output.sentiment_citations]

    return CallExtractionOutput(
        document_id=document_id,
        allocation_calls=allocation_calls,
        overall_sentiment=llm_output.overall_sentiment,
        sentiment_rationale=llm_output.sentiment_rationale,
        sentiment_citations=sentiment_citations,
        sentiment_confidence=llm_output.sentiment_confidence,
        extraction_timestamp=datetime.now(UTC),
        model_version=model_version,
        total_candidates_reviewed=total_candidates,
    )


async def stage_calls(
    profile: DocumentProfile,
    candidate_set: CandidateSet,
    llm_client: LLMClient | None = None,
) -> CallExtractionOutput:
    """Extract allocation calls and sentiment from candidate passages.

    Args:
        profile: Document profile from Stage 4
        candidate_set: Candidate passages from Stage 5
        llm_client: Optional LLM client for dependency injection

    Returns:
        CallExtractionOutput with extracted calls and sentiment

    Raises:
        ExtractionError: If no candidates available or extraction fails
        ValidationError: If LLM output violates guardrails
    """
    logger.info(f"Starting Stage 6 call extraction for document {profile.document_id}")

    if llm_client is None:
        llm_client = LLMClient()

    if not candidate_set.candidates:
        raise ExtractionError("No candidate chunks available for call extraction")

    # Build prompt with candidate chunks and profile metadata
    prompt = build_call_extraction_prompt(candidate_set.candidates, profile)

    # Call LLM with JSON schema
    llm_output = await llm_client.complete_json(
        prompt=prompt,
        response_model=CallExtractionLLM,
        stage=PipelineStage.CALLS,
    )

    # Validate against guardrails (citations, taxonomy, hallucination)
    try:
        validate_llm_output(llm_output, candidate_set.candidates)
    except ValidationError:
        logger.exception("Call extraction output failed validation")
        raise

    # Build final output model
    provider = llm_client.get_provider_for_stage(PipelineStage.CALLS)
    config = llm_client.get_config(provider)
    output = _build_call_extraction_output(
        document_id=profile.document_id,
        llm_output=llm_output,
        total_candidates=len(candidate_set.candidates),
        model_version=config.model_name,
    )

    logger.info(
        "Stage 6 complete",
        extra={
            "document_id": profile.document_id,
            "calls_extracted": len(output.allocation_calls),
            "overall_sentiment": output.overall_sentiment.value,
            "needs_review": sum(1 for call in output.allocation_calls if call.needs_analyst_review),
        },
    )

    return output
