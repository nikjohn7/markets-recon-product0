"""Stage 4: Document metadata extraction.

Extracts manager name, document type, and dates from the document header sections.
"""

from __future__ import annotations

import logging
from datetime import date, timedelta

from pydantic import BaseModel, ConfigDict, Field

from src.exceptions import ExtractionError, ValidationError
from src.llm.client import LLMClient, PipelineStage
from src.llm.contracts import validate_llm_output
from src.llm.prompts.metadata import build_metadata_extraction_prompt
from src.models.core import Citation
from src.models.enums import DocumentType
from src.models.pipeline import CleanedDocument, RetrievedChunk
from src.models.profile import DocumentProfile
from src.retrieval.indexer import DocumentIndex

logger = logging.getLogger(__name__)

METADATA_QUERY = "document title author publication date manager name outlook report"
MAX_METADATA_CHUNKS = 12
FIRST_PAGES_MAX_CHUNKS = 6
QUERY_TOP_K = 8
MAX_PUBLICATION_AGE_DAYS = 365 * 5
UNKNOWN_MANAGER_VALUES = {"unknown", "n/a", "na", "not specified", "unspecified"}


class DocumentProfileLLM(BaseModel):
    """LLM output schema for metadata extraction."""

    model_config = ConfigDict(extra="forbid")

    manager_name: str = Field(..., min_length=1)
    title: str
    publication_date: str | None = Field(None, description="YYYY-MM-DD or null")
    as_of_date: str | None = Field(None, description="YYYY-MM-DD or null")
    document_type: DocumentType
    asset_classes_covered: list[str] = Field(..., min_length=1)
    regions: list[str] = Field(default_factory=list)
    time_horizon: str | None = None
    intended_audience: str | None = None
    citations: list[Citation] = Field(..., min_length=1)

    manager_name_uncertain: bool = False
    publication_date_uncertain: bool = False


def _parse_date(value: str | None) -> date | None:
    """Parse an ISO date string, returning None if invalid."""
    if value is None:
        return None
    try:
        return date.fromisoformat(value)
    except ValueError:
        return None


def _is_plausible_publication_date(value: date) -> bool:
    """Return True if date is not in the future and within 5 years."""
    today = date.today()
    if value > today:
        return False
    earliest = today - timedelta(days=MAX_PUBLICATION_AGE_DAYS)
    return value >= earliest


def _normalize_manager_name(name: str) -> tuple[str, bool]:
    """Normalize manager name and mark uncertainty if it's a placeholder."""
    normalized = name.strip()
    if not normalized:
        return "Unspecified", True
    if normalized.lower() in UNKNOWN_MANAGER_VALUES:
        return "Unspecified", True
    return normalized, False


def _chunk_to_retrieved(
    chunk_id: str,
    page: int,
    text: str,
    block_ids: list[str],
    section: str | None,
) -> RetrievedChunk:
    """Create a RetrievedChunk with a neutral score."""
    return RetrievedChunk(
        chunk_id=chunk_id,
        block_ids=block_ids,
        page=page,
        text=text,
        score=1.0,
        section=section,
    )


def _select_first_page_chunks(index: DocumentIndex) -> list[RetrievedChunk]:
    """Select chunks from the first two pages to prioritize metadata."""
    first_page_chunks = [chunk for chunk in index.chunks if chunk.page <= 2]
    first_page_chunks.sort(key=lambda chunk: (chunk.page, chunk.chunk_id))
    selected = first_page_chunks[:FIRST_PAGES_MAX_CHUNKS]

    return [
        _chunk_to_retrieved(
            chunk_id=chunk.chunk_id,
            page=chunk.page,
            text=chunk.text,
            block_ids=chunk.block_ids,
            section=chunk.section,
        )
        for chunk in selected
    ]


def _merge_chunks(primary: list[RetrievedChunk], secondary: list[RetrievedChunk]) -> list[RetrievedChunk]:
    """Merge retrieved chunks, preserving order and uniqueness."""
    seen: set[str] = set()
    merged: list[RetrievedChunk] = []

    for chunk in primary + secondary:
        if chunk.chunk_id in seen:
            continue
        seen.add(chunk.chunk_id)
        merged.append(chunk)
        if len(merged) >= MAX_METADATA_CHUNKS:
            break

    return merged


def _build_document_profile(
    cleaned_doc: CleanedDocument,
    llm_output: DocumentProfileLLM,
) -> DocumentProfile:
    """Construct DocumentProfile with validation and uncertainty handling."""
    manager_name, manager_uncertain = _normalize_manager_name(llm_output.manager_name)
    manager_name_uncertain = llm_output.manager_name_uncertain or manager_uncertain

    publication_date = _parse_date(llm_output.publication_date)
    if publication_date is None or not _is_plausible_publication_date(publication_date):
        publication_date = None
        publication_date_uncertain = True
    else:
        publication_date_uncertain = llm_output.publication_date_uncertain

    as_of_date = _parse_date(llm_output.as_of_date)

    profile = DocumentProfile(
        document_id=cleaned_doc.document_id,
        manager_name=manager_name,
        title=llm_output.title,
        publication_date=publication_date,
        as_of_date=as_of_date,
        document_type=llm_output.document_type,
        asset_classes_covered=llm_output.asset_classes_covered,
        regions=llm_output.regions,
        time_horizon=llm_output.time_horizon,
        intended_audience=llm_output.intended_audience,
        citations=llm_output.citations,
        manager_name_uncertain=manager_name_uncertain,
        publication_date_uncertain=publication_date_uncertain,
    )
    return profile


async def stage_metadata(
    cleaned_doc: CleanedDocument,
    index: DocumentIndex,
    llm_client: LLMClient | None = None,
) -> DocumentProfile:
    """Extract document metadata with retrieval-grounded LLM.

    Args:
        cleaned_doc: Cleaned document from Stage 2
        index: Retrieval index from Stage 3
        llm_client: Optional LLM client for dependency injection

    Returns:
        DocumentProfile extracted from the document

    Raises:
        ExtractionError: If no chunks are available for metadata extraction
        LLMError: If the LLM call fails or output validation fails
        ValidationError: If LLM output violates guardrails
    """
    logger.info(f"Starting Stage 4 metadata extraction for document {cleaned_doc.document_id}")

    if llm_client is None:
        llm_client = LLMClient()

    if not index.chunks:
        raise ExtractionError("No chunks available for metadata extraction")

    query_chunks = await index.query(METADATA_QUERY, top_k=QUERY_TOP_K)
    first_page_chunks = _select_first_page_chunks(index)
    retrieved_chunks = _merge_chunks(first_page_chunks, query_chunks)

    if not retrieved_chunks:
        raise ExtractionError("No metadata chunks retrieved")

    prompt = build_metadata_extraction_prompt(retrieved_chunks)
    llm_output = await llm_client.complete_json(
        prompt=prompt,
        response_model=DocumentProfileLLM,
        stage=PipelineStage.METADATA,
    )

    try:
        validate_llm_output(llm_output, retrieved_chunks)
    except ValidationError:
        logger.exception("Metadata output failed validation")
        raise

    profile = _build_document_profile(cleaned_doc, llm_output)

    logger.info(
        "Stage 4 complete",
        extra={
            "document_id": cleaned_doc.document_id,
            "manager_name_uncertain": profile.manager_name_uncertain,
            "publication_date_uncertain": profile.publication_date_uncertain,
        },
    )

    return profile
