"""Integration tests for Stage 4 - Metadata extraction."""

from __future__ import annotations

from datetime import date
from unittest.mock import AsyncMock

import pytest
from src.exceptions import ExtractionError
from src.models.document import DocumentBlock
from src.models.enums import BlockType, DocumentType
from src.models.pipeline import Chunk, CleanedDocument, RetrievedChunk, Section
from src.pipeline.stages.s4_metadata import stage_metadata
from src.retrieval.indexer import DocumentIndex


@pytest.mark.asyncio
async def test_stage_metadata_with_mock_llm(mock_llm_client):
    """Stage 4 should return a validated DocumentProfile."""
    blocks = [
        DocumentBlock(
            block_id="1_0",
            page=1,
            text="Mid-Year Investment Outlook 2025",
            block_type=BlockType.HEADING,
            bbox=None,
            confidence=1.0,
        )
    ]
    sections = [
        Section(
            section_id="doc_meta_sec_0",
            title="Overview",
            start_block_id="1_0",
            end_block_id="1_0",
            section_type=None,
        )
    ]
    cleaned_doc = CleanedDocument(
        document_id="doc_meta",
        blocks=blocks,
        sections=sections,
        removed_boilerplate_count=0,
        disclaimer_block_id=None,
    )

    index = DocumentIndex(document_id="doc_meta")
    index.chunks = [
        Chunk(
            chunk_id="chunk_1",
            block_ids=["1_0"],
            page=1,
            text=(
                "BlackRock Mid-Year Investment Outlook 2025. "
                "Publication date 2025-07-15. As of 2025-06-30."
            ),
            section="Overview",
        ),
        Chunk(
            chunk_id="chunk_2",
            block_ids=["1_0"],
            page=1,
            text="Institutional investors focus on equities and fixed income.",
            section="Overview",
        ),
    ]
    index.query = AsyncMock(
        return_value=[
            RetrievedChunk(
                chunk_id="chunk_2",
                block_ids=["1_0"],
                page=1,
                text="Institutional investors focus on equities and fixed income.",
                score=0.9,
                section="Overview",
            )
        ]
    )

    profile = await stage_metadata(cleaned_doc, index, llm_client=mock_llm_client)

    assert profile.document_id == "doc_meta"
    assert profile.manager_name == "BlackRock"
    assert profile.document_type == DocumentType.MID_YEAR_OUTLOOK
    assert profile.publication_date == date(2025, 7, 15)
    assert profile.as_of_date == date(2025, 6, 30)
    assert profile.manager_name_uncertain is False
    assert profile.publication_date_uncertain is False


@pytest.mark.asyncio
async def test_stage_metadata_requires_chunks(mock_llm_client):
    """Stage 4 should fail when no chunks are available."""
    cleaned_doc = CleanedDocument(
        document_id="doc_empty",
        blocks=[],
        sections=[],
        removed_boilerplate_count=0,
        disclaimer_block_id=None,
    )
    index = DocumentIndex(document_id="doc_empty")
    index.chunks = []

    with pytest.raises(ExtractionError, match="No chunks available"):
        await stage_metadata(cleaned_doc, index, llm_client=mock_llm_client)
