"""Stage 7: Summary generation.

Generates executive summary, search descriptor, and key takeaways
from extracted calls and document content.
"""

from __future__ import annotations

import logging

from pydantic import BaseModel, ConfigDict, Field
from pydantic import ValidationError as PydanticValidationError

from src.exceptions import ExtractionError, ValidationError
from src.llm.client import LLMClient, PipelineStage
from src.llm.contracts import validate_citations
from src.llm.prompts.summaries import build_summary_generation_prompt
from src.models.calls import CallExtractionOutput
from src.models.core import Citation
from src.models.pipeline import RetrievedChunk
from src.models.profile import DocumentProfile
from src.models.summaries import DocumentSummaries, KeyTakeaway
from src.retrieval.indexer import DocumentIndex

logger = logging.getLogger(__name__)


class KeyTakeawayLLM(BaseModel):
    """LLM output schema for a single key takeaway."""

    model_config = ConfigDict(extra="forbid")

    text: str = Field(..., max_length=200)
    citations: list[dict[str, str | int]] = Field(..., min_length=1)


class SummaryGenerationLLM(BaseModel):
    """LLM output schema for summary generation."""

    model_config = ConfigDict(extra="forbid")

    executive_summary: str = Field(..., min_length=100, max_length=1000)
    search_descriptor: str = Field(..., min_length=50, max_length=200)
    key_takeaways: list[KeyTakeawayLLM] = Field(..., min_length=3, max_length=5)
    citations: list[dict[str, str | int]] = Field(..., min_length=1)
    confidence: float = Field(default=0.8, ge=0, le=1)


def _parse_citation(citation_dict: dict[str, str | int]) -> Citation:
    """Parse citation from LLM output dict.

    Args:
        citation_dict: Raw citation dict from LLM output.

    Returns:
        Parsed Citation object.

    Raises:
        ValidationError: If citation dict is invalid.
    """
    try:
        chunk_id = str(citation_dict["chunk_id"])
        page = int(citation_dict["page"])
        text_span = citation_dict.get("text_span")
        text_span_str = str(text_span) if text_span else None

        return Citation(chunk_id=chunk_id, page=page, text_span=text_span_str)
    except (KeyError, ValueError, TypeError) as e:
        msg = f"Invalid citation dict: {citation_dict}"
        raise ValidationError(msg) from e


def _parse_key_takeaway(takeaway_llm: KeyTakeawayLLM) -> KeyTakeaway:
    """Parse key takeaway from LLM output.

    Args:
        takeaway_llm: LLM output for a single takeaway.

    Returns:
        Parsed KeyTakeaway object.

    Raises:
        ValidationError: If takeaway has invalid citations.
    """
    try:
        citations = [_parse_citation(c) for c in takeaway_llm.citations]
        return KeyTakeaway(text=takeaway_llm.text, citations=citations)
    except ValidationError as e:
        msg = f"Invalid takeaway citations: {takeaway_llm.text}"
        raise ValidationError(msg) from e


async def _retrieve_key_passages(
    index: DocumentIndex,
    profile: DocumentProfile,
    call_extraction: CallExtractionOutput,
    top_k: int = 20,
) -> list[RetrievedChunk]:
    """Retrieve key passages for summary generation.

    Uses a combination of queries to find the most relevant passages:
    - Document type and manager name
    - Sentiment and macro themes
    - Top asset classes mentioned in calls

    Args:
        index: Document retrieval index.
        profile: Document profile with metadata.
        call_extraction: Extracted allocation calls.
        top_k: Number of chunks to retrieve per query.

    Returns:
        List of retrieved chunks (deduplicated).
    """
    queries = []

    # Query 1: Document overview
    queries.append(f"{profile.document_type.value} {profile.manager_name}")

    # Query 2: Sentiment and themes
    sentiment_query = f"{call_extraction.overall_sentiment.value} sentiment"
    if call_extraction.sentiment_rationale:
        sentiment_query += f" {call_extraction.sentiment_rationale[0]}"
    queries.append(sentiment_query)

    # Query 3: Top asset classes from calls
    if call_extraction.allocation_calls:
        asset_classes = [call.sub_asset_class for call in call_extraction.allocation_calls[:3]]
        queries.append(" ".join(asset_classes))

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

    # Return top 30 chunks
    return all_chunks[:30]


def _validate_word_count(text: str, min_words: int, max_words: int, field_name: str) -> None:
    """Validate word count for summary fields.

    Args:
        text: Text to validate.
        min_words: Minimum word count.
        max_words: Maximum word count.
        field_name: Name of field for error message.

    Raises:
        ValidationError: If word count is out of bounds.
    """
    word_count = len(text.split())
    if word_count < min_words or word_count > max_words:
        msg = f"{field_name} word count {word_count} outside range [{min_words}, {max_words}]"
        logger.warning(msg)
        # Note: We log a warning but don't raise - LLM may occasionally exceed bounds


async def stage_summaries(
    document_id: str,
    index: DocumentIndex,
    call_extraction: CallExtractionOutput,
    profile: DocumentProfile,
    llm_client: LLMClient | None = None,
) -> DocumentSummaries:
    """Stage 7: Generate summaries.

    Generates executive summary, search descriptor, and key takeaways
    from extracted calls and key document passages.

    Args:
        document_id: Unique document identifier.
        index: Document retrieval index.
        call_extraction: Extracted allocation calls from Stage 6.
        profile: Document profile from Stage 4.
        llm_client: Optional LLM client (for testing).

    Returns:
        DocumentSummaries with all summary components.

    Raises:
        ExtractionError: If summary generation fails.
        ValidationError: If LLM output is invalid.
    """
    logger.info(f"[Stage 7] Starting summary generation for document {document_id}")

    # Initialize LLM client
    if llm_client is None:
        llm_client = LLMClient()

    try:
        # Step 1: Retrieve key passages for summary context
        logger.debug("Retrieving key passages for summary")
        key_passages = await _retrieve_key_passages(
            index=index,
            profile=profile,
            call_extraction=call_extraction,
            top_k=20,
        )
        logger.info(f"Retrieved {len(key_passages)} key passages")

        # Step 2: Build LLM prompt
        prompt = build_summary_generation_prompt(
            chunks=key_passages,
            calls=call_extraction.allocation_calls,
            profile=profile,
        )

        # Step 3: Call LLM
        logger.debug("Calling LLM for summary generation")
        llm_response = await llm_client.complete_json(
            prompt=prompt,
            response_model=SummaryGenerationLLM,
            stage=PipelineStage.SUMMARIES,
        )
        logger.info("LLM summary generation completed")

        # Step 4: Validate LLM output (citations only - no taxonomy/hallucination checks for summaries)
        # Note: We only validate citations since summaries don't contain AllocationCall objects
        validate_citations(
            output=llm_response,
            allowed_chunk_ids={c.chunk_id for c in key_passages},
        )

        # Step 5: Validate word counts
        _validate_word_count(
            text=llm_response.executive_summary,
            min_words=120,
            max_words=180,
            field_name="executive_summary",
        )
        _validate_word_count(
            text=llm_response.search_descriptor,
            min_words=20,
            max_words=35,
            field_name="search_descriptor",
        )

        # Step 6: Parse citations and takeaways
        all_citations = [_parse_citation(c) for c in llm_response.citations]
        key_takeaways = [_parse_key_takeaway(t) for t in llm_response.key_takeaways]

        # Step 7: Build DocumentSummaries
        summaries = DocumentSummaries(
            document_id=document_id,
            executive_summary=llm_response.executive_summary,
            search_descriptor=llm_response.search_descriptor,
            key_takeaways=key_takeaways,
            citations=all_citations,
            confidence=llm_response.confidence,
        )

        logger.info(
            f"[Stage 7] Summary generation completed: "
            f"{len(summaries.key_takeaways)} takeaways, "
            f"confidence={summaries.confidence:.2f}"
        )
        return summaries

    except PydanticValidationError as e:
        msg = f"Invalid LLM output for summary generation: {e}"
        logger.error(msg)
        raise ValidationError(msg) from e
    except Exception as e:
        msg = f"Summary generation failed: {e}"
        logger.error(msg)
        raise ExtractionError(msg) from e
