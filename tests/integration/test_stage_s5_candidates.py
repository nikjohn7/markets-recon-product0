"""Integration tests for Stage 5 - Candidate retrieval."""

from __future__ import annotations

from unittest.mock import AsyncMock
from uuid import uuid4

import pytest

from src.exceptions import ExtractionError
from src.models.document import DocumentBlock
from src.models.enums import BlockType
from src.models.pipeline import Chunk, CleanedDocument, Section
from src.pipeline.stages.s5_candidates import stage_candidates
from src.retrieval.indexer import DocumentIndex


@pytest.mark.asyncio
async def test_stage_candidates_with_keyword_and_llm_expansion(mock_llm_client):
    """Stage 5 should combine keyword and LLM-expanded candidates."""
    blocks = [
        DocumentBlock(
            block_id="block_1",
            page=1,
            text="We are overweight German Bunds due to policy easing.",
            block_type=BlockType.PARAGRAPH,
            bbox=None,
            confidence=1.0,
        ),
        DocumentBlock(
            block_id="block_2",
            page=2,
            text="US equities remain neutral given valuations.",
            block_type=BlockType.PARAGRAPH,
            bbox=None,
            confidence=1.0,
        ),
        DocumentBlock(
            block_id="block_3",
            page=3,
            text="Inflation risks remain elevated.",
            block_type=BlockType.PARAGRAPH,
            bbox=None,
            confidence=1.0,
        ),
    ]
    sections = [
        Section(
            section_id="doc_candidates_sec_0",
            title="Strategy",
            start_block_id="block_1",
            end_block_id="block_3",
            section_type=None,
        )
    ]
    cleaned_doc = CleanedDocument(
        document_id="doc_candidates",
        blocks=blocks,
        sections=sections,
        removed_boilerplate_count=0,
        disclaimer_block_id=None,
    )

    index = DocumentIndex(document_id="doc_candidates")
    index.chunks = [
        Chunk(
            chunk_id="chunk_4",
            block_ids=["block_1"],
            page=1,
            text=blocks[0].text,
            section="Strategy",
        ),
        Chunk(
            chunk_id="chunk_5",
            block_ids=["block_2"],
            page=2,
            text=blocks[1].text,
            section="Strategy",
        ),
        Chunk(
            chunk_id="chunk_8",
            block_ids=["block_3"],
            page=3,
            text=blocks[2].text,
            section="Strategy",
        ),
    ]
    index.query = AsyncMock(return_value=[])

    candidates = await stage_candidates(cleaned_doc, index, llm_client=mock_llm_client)

    candidate_ids = {chunk.chunk_id for chunk in candidates.candidates}
    assert candidates.document_id == "doc_candidates"
    assert candidates.total_chunks_reviewed == len(index.chunks)
    assert {"chunk_4", "chunk_5", "chunk_8"}.issubset(candidate_ids)
    assert candidates.keyword_matches


@pytest.mark.asyncio
async def test_stage_candidates_requires_index_chunks(mock_llm_client):
    """Stage 5 should fail when the index is empty."""
    document_id = f"doc_empty_{uuid4().hex}"
    cleaned_doc = CleanedDocument(
        document_id=document_id,
        blocks=[],
        sections=[],
        removed_boilerplate_count=0,
        disclaimer_block_id=None,
    )
    index = DocumentIndex(document_id=document_id)
    index.chunks = []

    with pytest.raises(ExtractionError, match="No chunks available"):
        await stage_candidates(cleaned_doc, index, llm_client=mock_llm_client)
