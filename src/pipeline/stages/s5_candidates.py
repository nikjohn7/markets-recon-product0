"""Stage 5: Signal candidate retrieval.

Identifies passages likely containing allocation calls using keyword mining
and LLM-assisted retrieval expansion.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from pydantic import BaseModel, ConfigDict, Field

from src.exceptions import ExtractionError
from src.llm.client import LLMClient, PipelineStage
from src.llm.prompts.candidates import build_candidate_expansion_prompt
from src.models.pipeline import CandidateSet, CleanedDocument, RetrievedChunk
from src.taxonomy.synonyms import SYNONYMS

if TYPE_CHECKING:
    from src.retrieval.indexer import DocumentIndex

logger = logging.getLogger(__name__)

# =============================================================================
# Positioning Keywords
# =============================================================================

POSITIONING_KEYWORDS = {
    # Explicit directional signals
    "overweight",
    "underweight",
    "neutral weight",
    "equal weight",
    "market weight",
    "ow",
    "uw",
    "n",
    # Preference signals
    "prefer",
    "favour",
    "favor",
    "avoid",
    "like",
    # Sentiment signals
    "bullish",
    "bearish",
    "constructive",
    "cautious",
    "positive",
    "negative",
    # Conviction signals
    "high conviction",
    "strong conviction",
    "conviction",
    # Action signals
    "upgrade",
    "downgrade",
    "increase",
    "decrease",
    "reduce",
    "trim",
    "add",
    "adding",
    "reducing",
    "increasing",
    "decreasing",
    "exposure",
    "allocation",
    "allocate",
    # Tactical signals
    "tactical",
    "strategic",
    "overweight to",
    "underweight to",
    "shift to",
    "rotate into",
    "rotate out of",
    # Comparative signals
    "attractive",
    "unattractive",
    "expensive",
    "cheap",
    "value",
    "overvalued",
    "undervalued",
}

# Asset class keywords from taxonomy
ASSET_CLASS_KEYWORDS = set(SYNONYMS.keys())

# Combined signal keywords
SIGNAL_KEYWORDS = POSITIONING_KEYWORDS | ASSET_CLASS_KEYWORDS

# Retrieval expansion settings
MAX_KEYWORD_CHUNKS = 20
MAX_EXPANSION_CHUNKS = 10
MIN_CANDIDATE_CHUNKS = 3
TOP_K_QUERY = 50


class ExpansionOutput(BaseModel):
    """LLM output for candidate expansion."""

    model_config = ConfigDict(extra="forbid")

    additional_chunk_ids: list[str] = Field(default_factory=list)
    reasoning: str


def _search_keywords_in_blocks(cleaned_doc: CleanedDocument) -> dict[str, list[str]]:
    """Search for signal keywords in document blocks.

    Args:
        cleaned_doc: Cleaned document with blocks

    Returns:
        Dict mapping keyword → block_ids where it appears
    """
    keyword_matches: dict[str, list[str]] = {}

    for block in cleaned_doc.blocks:
        # Skip disclaimer blocks
        if block.block_type.value == "DISCLAIMER":
            continue

        text_lower = block.text.lower()

        # Check each keyword
        for keyword in SIGNAL_KEYWORDS:
            if keyword in text_lower:
                if keyword not in keyword_matches:
                    keyword_matches[keyword] = []
                keyword_matches[keyword].append(block.block_id)

    logger.info(
        f"Found {len(keyword_matches)} unique keywords across {sum(len(ids) for ids in keyword_matches.values())} block matches"
    )
    return keyword_matches


def _retrieve_chunks_by_blocks(
    index: DocumentIndex,
    block_ids: set[str],
) -> list[RetrievedChunk]:
    """Retrieve chunks containing the specified block IDs.

    Args:
        index: Document index with chunks
        block_ids: Set of block IDs to find

    Returns:
        List of chunks containing any of the block IDs
    """
    matching_chunks: list[RetrievedChunk] = []

    for chunk in index.chunks:
        # Check if chunk contains any of the target block IDs
        if any(block_id in chunk.block_ids for block_id in block_ids):
            matching_chunks.append(
                RetrievedChunk(
                    chunk_id=chunk.chunk_id,
                    block_ids=chunk.block_ids,
                    page=chunk.page,
                    text=chunk.text,
                    score=1.0,  # Keyword match gets max score
                    section=chunk.section,
                )
            )

    return matching_chunks


def _rank_by_signal_density(chunks: list[RetrievedChunk]) -> list[RetrievedChunk]:
    """Rank chunks by density of signal keywords.

    Args:
        chunks: List of retrieved chunks

    Returns:
        Chunks sorted by signal density (descending)
    """

    def count_signals(chunk: RetrievedChunk) -> int:
        """Count signal keywords in chunk."""
        text_lower = chunk.text.lower()
        return sum(1 for keyword in SIGNAL_KEYWORDS if keyword in text_lower)

    # Create list with signal counts
    scored_chunks = [(chunk, count_signals(chunk)) for chunk in chunks]

    # Sort by count (descending), then by page (ascending)
    scored_chunks.sort(key=lambda x: (-x[1], x[0].page))

    return [chunk for chunk, _count in scored_chunks]


def _deduplicate_chunks(chunks: list[RetrievedChunk]) -> list[RetrievedChunk]:
    """Remove duplicate chunks based on chunk_id.

    Args:
        chunks: List of retrieved chunks (may contain duplicates)

    Returns:
        Deduplicated list preserving order
    """
    seen: set[str] = set()
    deduplicated: list[RetrievedChunk] = []

    for chunk in chunks:
        if chunk.chunk_id not in seen:
            seen.add(chunk.chunk_id)
            deduplicated.append(chunk)

    return deduplicated


async def _expand_with_llm(
    keyword_chunks: list[RetrievedChunk],
    all_chunks: list[RetrievedChunk],
    llm_client: LLMClient,
) -> list[RetrievedChunk]:
    """Use LLM to find additional candidate chunks not caught by keywords.

    Args:
        keyword_chunks: Chunks found via keyword search
        all_chunks: All available chunks
        llm_client: LLM client for expansion

    Returns:
        Additional chunks identified by LLM
    """
    if not keyword_chunks:
        logger.info("No keyword chunks to expand from, skipping LLM expansion")
        return []

    if len(keyword_chunks) == len(all_chunks):
        logger.info("All chunks already matched keywords, skipping expansion")
        return []

    prompt = build_candidate_expansion_prompt(keyword_chunks, all_chunks)

    try:
        llm_output = await llm_client.complete_json(
            prompt=prompt,
            response_model=ExpansionOutput,
            stage=PipelineStage.CANDIDATES,
        )

        logger.info(
            f"LLM expansion identified {len(llm_output.additional_chunk_ids)} additional chunks: {llm_output.reasoning}"
        )

        # Retrieve the additional chunks
        chunk_id_to_chunk = {chunk.chunk_id: chunk for chunk in all_chunks}
        additional_chunks = [
            chunk_id_to_chunk[chunk_id]
            for chunk_id in llm_output.additional_chunk_ids
            if chunk_id in chunk_id_to_chunk
        ]

        # Limit to MAX_EXPANSION_CHUNKS
        return additional_chunks[:MAX_EXPANSION_CHUNKS]

    except Exception:
        logger.exception("LLM expansion failed, continuing with keyword matches only")
        return []


async def stage_candidates(
    cleaned_doc: CleanedDocument,
    index: DocumentIndex,
    llm_client: LLMClient | None = None,
) -> CandidateSet:
    """Identify signal-containing passages for extraction.

    Strategy:
    1. Keyword mining: Search for positioning keywords and asset class mentions
    2. Retrieval expansion: Use LLM to find additional passages with indirect signals
    3. Deduplication and ranking: Merge and rank by signal density

    Args:
        cleaned_doc: Cleaned document from Stage 2
        index: Retrieval index from Stage 3
        llm_client: Optional LLM client for dependency injection

    Returns:
        CandidateSet with candidate chunks for extraction

    Raises:
        ExtractionError: If index has no chunks available
    """
    logger.info(f"Starting Stage 5 candidate retrieval for document {cleaned_doc.document_id}")

    if llm_client is None:
        llm_client = LLMClient()

    if not index.chunks:
        raise ExtractionError("No chunks available in index for candidate retrieval")

    # Step 1: Keyword mining
    keyword_matches = _search_keywords_in_blocks(cleaned_doc)

    if not keyword_matches:
        logger.warning("No keywords found in document, returning all chunks as candidates")
        # Return all chunks if no keywords found
        all_chunks = [
            RetrievedChunk(
                chunk_id=chunk.chunk_id,
                block_ids=chunk.block_ids,
                page=chunk.page,
                text=chunk.text,
                score=0.5,  # Lower score for non-keyword matches
                section=chunk.section,
            )
            for chunk in index.chunks
        ]
        return CandidateSet(
            document_id=cleaned_doc.document_id,
            candidates=all_chunks[:TOP_K_QUERY],
            keyword_matches={},
            total_chunks_reviewed=len(index.chunks),
        )

    # Get block IDs from keyword matches
    matched_block_ids = set()
    for block_ids in keyword_matches.values():
        matched_block_ids.update(block_ids)

    # Retrieve chunks containing matched blocks
    keyword_chunks = _retrieve_chunks_by_blocks(index, matched_block_ids)

    logger.info(f"Keyword mining found {len(keyword_chunks)} candidate chunks")

    # Step 2: Retrieval expansion via LLM
    all_chunks_for_expansion = [
        RetrievedChunk(
            chunk_id=chunk.chunk_id,
            block_ids=chunk.block_ids,
            page=chunk.page,
            text=chunk.text,
            score=0.5,
            section=chunk.section,
        )
        for chunk in index.chunks
    ]

    expansion_chunks = await _expand_with_llm(
        keyword_chunks=keyword_chunks[:8],  # Limit to avoid prompt bloat
        all_chunks=all_chunks_for_expansion,
        llm_client=llm_client,
    )

    # Step 3: Merge, deduplicate, and rank
    all_candidates = keyword_chunks + expansion_chunks
    deduplicated = _deduplicate_chunks(all_candidates)
    ranked = _rank_by_signal_density(deduplicated)

    # Limit to top candidates
    final_candidates = ranked[: MAX_KEYWORD_CHUNKS + MAX_EXPANSION_CHUNKS]

    logger.info(
        "Stage 5 complete",
        extra={
            "document_id": cleaned_doc.document_id,
            "keyword_chunks": len(keyword_chunks),
            "expansion_chunks": len(expansion_chunks),
            "final_candidates": len(final_candidates),
        },
    )

    return CandidateSet(
        document_id=cleaned_doc.document_id,
        candidates=final_candidates,
        keyword_matches=keyword_matches,
        total_chunks_reviewed=len(index.chunks),
    )
