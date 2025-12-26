"""Unit tests for Stage 4 metadata extraction."""

from __future__ import annotations

from datetime import date

import pytest
from src.models.core import Citation
from src.models.document import DocumentBlock
from src.models.enums import BlockType, DocumentType
from src.models.pipeline import Chunk, CleanedDocument, RetrievedChunk, Section
from src.pipeline.stages.s4_metadata import DocumentProfileLLM, stage_metadata


class DummyIndex:
    """Simple stub for DocumentIndex with deterministic query results."""

    def __init__(self, chunks: list[Chunk], query_results: list[RetrievedChunk]):
        self.chunks = chunks
        self._query_results = query_results
        self.last_query: str | None = None

    async def query(self, query: str, top_k: int = 10):  # noqa: ARG002
        self.last_query = query
        return self._query_results


class DummyLLMClient:
    """Stub LLM client returning a preconfigured response."""

    def __init__(self, response: DocumentProfileLLM, expected_chunk_id: str | None = None):
        self.response = response
        self.expected_chunk_id = expected_chunk_id
        self.last_prompt: str | None = None

    async def complete_json(
        self,
        prompt: str,
        response_model,  # noqa: ARG002
        stage,  # noqa: ARG002
    ):
        self.last_prompt = prompt
        if self.expected_chunk_id is not None:
            assert self.expected_chunk_id in prompt
        return self.response


def _make_cleaned_doc(document_id: str, block_id: str, text: str) -> CleanedDocument:
    block = DocumentBlock(
        block_id=block_id,
        page=1,
        text=text,
        block_type=BlockType.PARAGRAPH,
        bbox=None,
        confidence=1.0,
    )
    section = Section(
        section_id=f"{document_id}_sec_0",
        title="Cover",
        start_block_id=block_id,
        end_block_id=block_id,
        section_type=None,
    )
    return CleanedDocument(
        document_id=document_id,
        blocks=[block],
        sections=[section],
        removed_boilerplate_count=0,
        disclaimer_block_id=None,
    )


@pytest.mark.asyncio
async def test_stage_metadata_builds_profile():
    """Stage 4 returns a DocumentProfile with validated fields."""
    chunk = Chunk(
        chunk_id="doc_meta_0",
        block_ids=["b1"],
        page=1,
        text="BlackRock 2024 Outlook Published: 2024-01-15",
        section="Cover",
    )
    retrieved = RetrievedChunk(
        chunk_id="doc_meta_0",
        block_ids=["b1"],
        page=1,
        text=chunk.text,
        score=0.9,
        section=chunk.section,
    )
    cleaned_doc = _make_cleaned_doc("doc_meta", "b1", chunk.text)

    llm_output = DocumentProfileLLM(
        manager_name="BlackRock",
        title="2024 Outlook",
        publication_date="2024-01-15",
        as_of_date=None,
        document_type=DocumentType.ANNUAL_OUTLOOK,
        asset_classes_covered=["EQUITIES"],
        regions=["GLOBAL"],
        time_horizon=None,
        intended_audience=None,
        citations=[
            Citation(
                chunk_id="doc_meta_0",
                page=1,
                text_span="Published: 2024-01-15",
            )
        ],
        manager_name_uncertain=False,
        publication_date_uncertain=False,
    )

    index = DummyIndex(chunks=[chunk], query_results=[retrieved])
    llm_client = DummyLLMClient(response=llm_output)

    profile = await stage_metadata(cleaned_doc, index, llm_client=llm_client)

    assert profile.document_id == "doc_meta"
    assert profile.manager_name == "BlackRock"
    assert profile.publication_date == date(2024, 1, 15)
    assert profile.publication_date_uncertain is False


@pytest.mark.asyncio
async def test_stage_metadata_handles_invalid_date_and_unknown_manager():
    """Stage 4 marks uncertainty for invalid dates or unknown manager names."""
    chunk = Chunk(
        chunk_id="doc_meta_1",
        block_ids=["b2"],
        page=1,
        text="Outlook Report Published: 2010-01-01",
        section="Cover",
    )
    retrieved = RetrievedChunk(
        chunk_id="doc_meta_1",
        block_ids=["b2"],
        page=1,
        text=chunk.text,
        score=0.85,
        section=chunk.section,
    )
    cleaned_doc = _make_cleaned_doc("doc_meta_old", "b2", chunk.text)

    llm_output = DocumentProfileLLM(
        manager_name="Unknown",
        title="Outlook Report",
        publication_date="2010-01-01",
        as_of_date=None,
        document_type=DocumentType.OTHER,
        asset_classes_covered=["FIXED_INCOME"],
        regions=["GLOBAL"],
        time_horizon=None,
        intended_audience=None,
        citations=[
            Citation(
                chunk_id="doc_meta_1",
                page=1,
                text_span="Published: 2010-01-01",
            )
        ],
        manager_name_uncertain=False,
        publication_date_uncertain=False,
    )

    index = DummyIndex(chunks=[chunk], query_results=[retrieved])
    llm_client = DummyLLMClient(response=llm_output)

    profile = await stage_metadata(cleaned_doc, index, llm_client=llm_client)

    assert profile.manager_name == "Unspecified"
    assert profile.manager_name_uncertain is True
    assert profile.publication_date is None
    assert profile.publication_date_uncertain is True


@pytest.mark.asyncio
async def test_stage_metadata_uses_first_page_fallback():
    """Stage 4 falls back to first-page chunks if query returns none."""
    chunk = Chunk(
        chunk_id="doc_meta_2",
        block_ids=["b3"],
        page=1,
        text="PIMCO Outlook Published: 2024-02-01",
        section="Cover",
    )
    cleaned_doc = _make_cleaned_doc("doc_meta_fallback", "b3", chunk.text)

    llm_output = DocumentProfileLLM(
        manager_name="PIMCO",
        title="Outlook",
        publication_date="2024-02-01",
        as_of_date=None,
        document_type=DocumentType.ANNUAL_OUTLOOK,
        asset_classes_covered=["EQUITIES"],
        regions=["GLOBAL"],
        time_horizon=None,
        intended_audience=None,
        citations=[
            Citation(
                chunk_id="doc_meta_2",
                page=1,
                text_span="Published: 2024-02-01",
            )
        ],
        manager_name_uncertain=False,
        publication_date_uncertain=False,
    )

    index = DummyIndex(chunks=[chunk], query_results=[])
    llm_client = DummyLLMClient(response=llm_output, expected_chunk_id="doc_meta_2")

    profile = await stage_metadata(cleaned_doc, index, llm_client=llm_client)

    assert profile.manager_name == "PIMCO"
    assert profile.publication_date == date(2024, 2, 1)
