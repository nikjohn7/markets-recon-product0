"""Stage 8: Tooltip generation.

Generates concise hover text (≤25 words, ≤150 chars) for each allocation call.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from pydantic import BaseModel, ConfigDict, Field
from pydantic import ValidationError as PydanticValidationError

from src.exceptions import ExtractionError, ValidationError
from src.llm.client import LLMClient, PipelineStage
from src.llm.prompts.tooltips import build_tooltip_generation_prompt

if TYPE_CHECKING:
    from src.models.calls import CallExtractionOutput

logger = logging.getLogger(__name__)


class TooltipItem(BaseModel):
    """LLM output schema for a single tooltip."""

    model_config = ConfigDict(extra="forbid")

    sub_asset_class: str = Field(..., description="Sub-asset code from the call")
    tooltip_text: str = Field(..., max_length=150, description="Concise tooltip (≤25 words)")


class TooltipGenerationLLM(BaseModel):
    """LLM output schema for tooltip generation."""

    model_config = ConfigDict(extra="forbid")

    tooltips: list[TooltipItem] = Field(..., min_length=1)


def _validate_tooltip_quality(tooltip_text: str, sub_asset_class: str) -> None:
    """Validate tooltip meets quality requirements.

    Args:
        tooltip_text: The tooltip text to validate.
        sub_asset_class: The asset class this tooltip is for.

    Raises:
        ValidationError: If tooltip fails validation.
    """
    # Check word count (≤25 words)
    word_count = len(tooltip_text.split())
    if word_count > 25:
        msg = f"Tooltip for {sub_asset_class} exceeds 25 words: {word_count} words"
        logger.warning(msg)

    # Check character count (≤150 chars) - hard requirement
    if len(tooltip_text) > 150:
        msg = f"Tooltip for {sub_asset_class} exceeds 150 characters: {len(tooltip_text)} chars"
        raise ValidationError(msg)

    # Check for generic/uninformative patterns
    generic_patterns = [
        "positive on",
        "negative on",
        "cautious on",
        "bullish on",
        "bearish on",
        "due to macro factors",
        "we like",
        "the manager recommends",
    ]
    lower_tooltip = tooltip_text.lower()
    for pattern in generic_patterns:
        if pattern in lower_tooltip and len(tooltip_text.split()) < 15:
            # Only warn if it's both generic AND short (likely uninformative)
            logger.warning(
                f"Tooltip for {sub_asset_class} may be too generic: contains '{pattern}'"
            )


async def stage_tooltips(
    call_extraction: CallExtractionOutput,
    llm_client: LLMClient | None = None,
) -> CallExtractionOutput:
    """Stage 8: Generate tooltips for allocation calls.

    Generates concise hover text (≤25 words, ≤150 chars) for each call,
    summarizing the positioning and key rationale. Mutates the CallExtractionOutput
    in place by updating each AllocationCall.tooltip_text field.

    Args:
        call_extraction: Call extraction output from Stage 6.
        llm_client: Optional LLM client (for testing).

    Returns:
        CallExtractionOutput with tooltip_text populated for all calls.

    Raises:
        ExtractionError: If tooltip generation fails.
        ValidationError: If LLM output is invalid or tooltips fail validation.
    """
    document_id = call_extraction.document_id
    logger.info(
        f"[Stage 8] Starting tooltip generation for document {document_id} "
        f"({len(call_extraction.allocation_calls)} calls)"
    )

    # Handle edge case: no calls to process
    if not call_extraction.allocation_calls:
        logger.warning(f"[Stage 8] No allocation calls to generate tooltips for: {document_id}")
        return call_extraction

    # Initialize LLM client
    if llm_client is None:
        llm_client = LLMClient()

    try:
        # Step 1: Build LLM prompt
        prompt = build_tooltip_generation_prompt(call_extraction.allocation_calls)

        # Step 2: Call LLM
        logger.debug("Calling LLM for tooltip generation")
        llm_response = await llm_client.complete_json(
            prompt=prompt,
            response_model=TooltipGenerationLLM,
            stage=PipelineStage.TOOLTIPS,
        )
        logger.info(f"LLM tooltip generation completed: {len(llm_response.tooltips)} tooltips")

        # Step 3: Validate tooltip count matches call count
        if len(llm_response.tooltips) != len(call_extraction.allocation_calls):
            msg = (
                f"Tooltip count mismatch: expected {len(call_extraction.allocation_calls)}, "
                f"got {len(llm_response.tooltips)}"
            )
            raise ValidationError(msg)

        # Step 4: Build lookup map by sub_asset_class
        tooltip_map = {item.sub_asset_class: item.tooltip_text for item in llm_response.tooltips}

        # Step 5: Update each call's tooltip_text
        updated_count = 0
        for call in call_extraction.allocation_calls:
            if call.sub_asset_class in tooltip_map:
                tooltip_text = tooltip_map[call.sub_asset_class]

                # Validate tooltip quality
                _validate_tooltip_quality(tooltip_text, call.sub_asset_class)

                # Update call (mutate in place)
                call.tooltip_text = tooltip_text
                updated_count += 1
            else:
                msg = f"Missing tooltip for sub_asset_class: {call.sub_asset_class}"
                raise ValidationError(msg)

        logger.info(
            f"[Stage 8] Tooltip generation completed: "
            f"{updated_count}/{len(call_extraction.allocation_calls)} calls updated"
        )
        return call_extraction

    except PydanticValidationError as e:
        msg = f"Invalid LLM output for tooltip generation: {e}"
        logger.error(msg)
        raise ValidationError(msg) from e
    except ValidationError:
        # Re-raise ValidationError as-is
        raise
    except Exception as e:
        msg = f"Tooltip generation failed: {e}"
        logger.error(msg)
        raise ExtractionError(msg) from e
