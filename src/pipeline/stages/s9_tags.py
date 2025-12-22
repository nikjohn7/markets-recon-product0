"""Stage 9: Tag generation.

Generates normalized tags for search and filtering, combining deterministic
rule-based tags (asset classes, regions) with LLM-generated tags (themes, risks, macro regime).
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from pydantic import BaseModel, ConfigDict, Field
from pydantic import ValidationError as PydanticValidationError

from src.exceptions import ExtractionError, ValidationError
from src.llm.client import LLMClient, PipelineStage
from src.llm.prompts.tags import build_tag_generation_prompt
from src.models.enums import TagType
from src.models.tags import Tag, TagSet
from src.taxonomy.tags import (
    MACRO_REGIME_TAGS,
    REGION_TAGS,
    RISK_TAGS,
    THEME_TAGS,
)

if TYPE_CHECKING:
    from src.models.calls import CallExtractionOutput
    from src.models.pipeline import CleanedDocument, RetrievedChunk
    from src.models.profile import DocumentProfile
    from src.retrieval.indexer import DocumentIndex

logger = logging.getLogger(__name__)


class TagGenerationLLM(BaseModel):
    """LLM output schema for tag generation."""

    model_config = ConfigDict(extra="forbid")

    theme_tags: list[str] = Field(default_factory=list, max_length=5)
    risk_tags: list[str] = Field(default_factory=list, max_length=5)
    macro_regime_tags: list[str] = Field(default_factory=list, max_length=3)
    novel_themes: list[str] = Field(
        default_factory=list,
        description="Novel themes not in allowed vocabulary",
    )
    confidence: float = Field(default=0.8, ge=0, le=1)


def _extract_deterministic_tags(
    profile: DocumentProfile,
    call_extraction: CallExtractionOutput,
) -> tuple[list[str], list[str], list[str]]:
    """Extract deterministic tags from profile and calls.

    Args:
        profile: Document profile with metadata.
        call_extraction: Extracted allocation calls.

    Returns:
        Tuple of (asset_class_tags, region_tags, instrument_tags).
    """
    # Asset class tags from calls (category codes)
    asset_class_tags = list({call.asset_class_category for call in call_extraction.allocation_calls})

    # Region tags from profile
    region_tags_raw = profile.regions if profile.regions else []
    # Normalize to lowercase and filter against allowed REGION_TAGS
    region_tags = [
        r.lower() for r in region_tags_raw if r.lower() in REGION_TAGS
    ]

    # Instrument tags from sub-asset codes
    # Extract unique sub-asset codes, normalized to lowercase
    instrument_tags = list({
        call.sub_asset_class.lower() for call in call_extraction.allocation_calls
    })

    logger.debug(
        f"Deterministic tags: {len(asset_class_tags)} asset classes, "
        f"{len(region_tags)} regions, {len(instrument_tags)} instruments"
    )

    return asset_class_tags, region_tags, instrument_tags


async def _retrieve_passages_for_tagging(
    index: DocumentIndex,
    profile: DocumentProfile,
    call_extraction: CallExtractionOutput,
    top_k: int = 15,
) -> list[RetrievedChunk]:
    """Retrieve key passages for tag generation.

    Uses queries focused on themes, risks, and macro outlook.

    Args:
        index: Document retrieval index.
        profile: Document profile with metadata.
        call_extraction: Extracted allocation calls.
        top_k: Number of chunks to retrieve per query.

    Returns:
        List of retrieved chunks (deduplicated).
    """
    queries = []

    # Query 1: Macro outlook and themes
    queries.append(f"{profile.document_type.value} macro outlook themes")

    # Query 2: Risks and uncertainties
    queries.append("risks uncertainties concerns")

    # Query 3: Sentiment and regime
    sentiment_str = call_extraction.overall_sentiment.value
    queries.append(f"{sentiment_str} sentiment macro regime")

    # Retrieve chunks for each query
    all_chunks: list[RetrievedChunk] = []
    seen_chunk_ids: set[str] = set()

    for query in queries:
        chunks = await index.query(query, top_k=top_k)
        for chunk in chunks:
            if chunk.chunk_id not in seen_chunk_ids:
                all_chunks.append(chunk)
                seen_chunk_ids.add(chunk.chunk_id)

    # Sort by score (descending)
    all_chunks.sort(key=lambda c: c.score, reverse=True)

    # Return top 20 chunks
    return all_chunks[:20]


def _validate_and_normalize_llm_tags(llm_output: TagGenerationLLM) -> TagGenerationLLM:
    """Validate LLM-generated tags against allowed vocabularies.

    Filters out any tags not in the allowed lists and logs warnings.

    Args:
        llm_output: Raw LLM output with tags.

    Returns:
        Validated and filtered LLM output.
    """
    # Validate theme tags
    valid_theme_tags = []
    for tag in llm_output.theme_tags:
        tag_lower = tag.lower().strip()
        if tag_lower in THEME_TAGS:
            valid_theme_tags.append(tag_lower)
        else:
            logger.warning(f"Invalid theme tag (not in vocabulary): {tag}")

    # Validate risk tags
    valid_risk_tags = []
    for tag in llm_output.risk_tags:
        tag_lower = tag.lower().strip()
        if tag_lower in RISK_TAGS:
            valid_risk_tags.append(tag_lower)
        else:
            logger.warning(f"Invalid risk tag (not in vocabulary): {tag}")

    # Validate macro regime tags
    valid_macro_tags = []
    for tag in llm_output.macro_regime_tags:
        tag_lower = tag.lower().strip()
        if tag_lower in MACRO_REGIME_TAGS:
            valid_macro_tags.append(tag_lower)
        else:
            logger.warning(f"Invalid macro regime tag (not in vocabulary): {tag}")

    # Return validated output
    return TagGenerationLLM(
        theme_tags=valid_theme_tags,
        risk_tags=valid_risk_tags,
        macro_regime_tags=valid_macro_tags,
        novel_themes=llm_output.novel_themes,
        confidence=llm_output.confidence,
    )


def _build_tag_objects(
    asset_class_tags: list[str],
    region_tags: list[str],
    instrument_tags: list[str],
    llm_output: TagGenerationLLM,
) -> list[Tag]:
    """Build Tag objects for all tags.

    Args:
        asset_class_tags: Asset class category codes.
        region_tags: Region tags.
        instrument_tags: Instrument/sub-asset tags.
        llm_output: Validated LLM output.

    Returns:
        List of Tag objects.
    """
    all_tags: list[Tag] = []

    # Asset class tags (rule-based, high confidence)
    for tag_value in asset_class_tags:
        all_tags.append(
            Tag(
                tag_type=TagType.ASSET_CLASS,
                value=tag_value,
                confidence=1.0,
                source="rule",
            )
        )

    # Region tags (rule-based, high confidence)
    for tag_value in region_tags:
        all_tags.append(
            Tag(
                tag_type=TagType.REGION,
                value=tag_value,
                confidence=1.0,
                source="rule",
            )
        )

    # Instrument tags (rule-based, high confidence)
    for tag_value in instrument_tags:
        all_tags.append(
            Tag(
                tag_type=TagType.INSTRUMENT,
                value=tag_value,
                confidence=1.0,
                source="rule",
            )
        )

    # Theme tags (LLM-based)
    for tag_value in llm_output.theme_tags:
        all_tags.append(
            Tag(
                tag_type=TagType.THEME,
                value=tag_value,
                confidence=llm_output.confidence,
                source="llm",
            )
        )

    # Risk tags (LLM-based)
    for tag_value in llm_output.risk_tags:
        all_tags.append(
            Tag(
                tag_type=TagType.RISK,
                value=tag_value,
                confidence=llm_output.confidence,
                source="llm",
            )
        )

    # Macro regime tags (LLM-based)
    for tag_value in llm_output.macro_regime_tags:
        all_tags.append(
            Tag(
                tag_type=TagType.MACRO_REGIME,
                value=tag_value,
                confidence=llm_output.confidence,
                source="llm",
            )
        )

    return all_tags


async def stage_tags(
    document_id: str,
    cleaned_document: CleanedDocument,  # noqa: ARG001
    call_extraction: CallExtractionOutput,
    profile: DocumentProfile,
    index: DocumentIndex,
    llm_client: LLMClient | None = None,
) -> TagSet:
    """Stage 9: Generate tags for search and filtering.

    Combines deterministic rule-based tags (asset classes, regions, instruments)
    with LLM-generated tags (themes, risks, macro regime).

    Args:
        document_id: Unique document identifier.
        cleaned_document: Cleaned document from Stage 2.
        call_extraction: Call extraction output from Stage 6.
        profile: Document profile from Stage 4.
        index: Document retrieval index.
        llm_client: Optional LLM client (for testing).

    Returns:
        TagSet with all tag categories populated.

    Raises:
        ExtractionError: If tag generation fails.
        ValidationError: If LLM output is invalid or insufficient tags.
    """
    logger.info(f"[Stage 9] Starting tag generation for document {document_id}")

    # Initialize LLM client
    if llm_client is None:
        llm_client = LLMClient()

    try:
        # Step 1: Extract deterministic tags
        logger.debug("Extracting deterministic tags")
        asset_class_tags, region_tags, instrument_tags = _extract_deterministic_tags(
            profile, call_extraction
        )

        # Step 2: Retrieve key passages for LLM tagging
        logger.debug("Retrieving passages for LLM tagging")
        key_passages = await _retrieve_passages_for_tagging(
            index=index,
            profile=profile,
            call_extraction=call_extraction,
            top_k=15,
        )
        logger.info(f"Retrieved {len(key_passages)} passages for tagging")

        # Step 3: Build LLM prompt
        prompt = build_tag_generation_prompt(
            profile=profile,
            calls=call_extraction.allocation_calls,
            chunks=key_passages,
        )

        # Step 4: Call LLM
        logger.debug("Calling LLM for tag generation")
        llm_response = await llm_client.complete_json(
            prompt=prompt,
            response_model=TagGenerationLLM,
            stage=PipelineStage.TAGS,
        )
        logger.info(
            f"LLM tag generation completed: "
            f"{len(llm_response.theme_tags)} themes, "
            f"{len(llm_response.risk_tags)} risks, "
            f"{len(llm_response.macro_regime_tags)} macro regimes"
        )

        # Step 5: Validate and normalize LLM tags
        validated_llm_output = _validate_and_normalize_llm_tags(llm_response)

        # Log novel themes if any
        if validated_llm_output.novel_themes:
            logger.info(
                f"Novel themes detected (for vocabulary expansion): "
                f"{', '.join(validated_llm_output.novel_themes)}"
            )

        # Step 6: Build Tag objects
        all_tag_objects = _build_tag_objects(
            asset_class_tags=asset_class_tags,
            region_tags=region_tags,
            instrument_tags=instrument_tags,
            llm_output=validated_llm_output,
        )

        # Step 7: Build TagSet
        # Style tags are empty for now (could be added in future: value/growth/quality)
        tagset = TagSet(
            document_id=document_id,
            asset_class_tags=asset_class_tags,
            region_tags=region_tags,
            theme_tags=validated_llm_output.theme_tags,
            risk_tags=validated_llm_output.risk_tags,
            instrument_tags=instrument_tags,
            style_tags=[],  # Not implemented in MVP
            macro_regime_tags=validated_llm_output.macro_regime_tags,
            all_tags=all_tag_objects,
            confidence=validated_llm_output.confidence,
        )

        # Step 8: Validate minimum tag count
        total_tags = (
            len(asset_class_tags)
            + len(region_tags)
            + len(instrument_tags)
            + len(validated_llm_output.theme_tags)
            + len(validated_llm_output.risk_tags)
            + len(validated_llm_output.macro_regime_tags)
        )

        if total_tags < 5:
            msg = f"Insufficient tags generated: {total_tags} < 5 minimum"
            logger.warning(msg)
            # Don't fail, just warn - this is acceptable for sparse documents

        # Validate at least 1 asset class tag
        if not asset_class_tags:
            msg = "No asset class tags generated - at least 1 required"
            raise ValidationError(msg)

        logger.info(
            f"[Stage 9] Tag generation completed: {total_tags} total tags "
            f"({len(asset_class_tags)} asset class, {len(region_tags)} region, "
            f"{len(validated_llm_output.theme_tags)} theme, "
            f"{len(validated_llm_output.risk_tags)} risk, "
            f"{len(validated_llm_output.macro_regime_tags)} macro regime)"
        )

        return tagset

    except PydanticValidationError as e:
        msg = f"Invalid LLM output for tag generation: {e}"
        logger.error(msg)
        raise ValidationError(msg) from e
    except ValidationError:
        # Re-raise ValidationError as-is
        raise
    except Exception as e:
        msg = f"Tag generation failed: {e}"
        logger.error(msg)
        raise ExtractionError(msg) from e
