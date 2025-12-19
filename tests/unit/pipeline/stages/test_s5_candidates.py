"""Unit tests for Stage 5: Candidate retrieval."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from src.models.document import DocumentBlock
from src.models.enums import BlockType
from src.models.pipeline import CandidateSet, Chunk, CleanedDocument, RetrievedChunk, Section
from src.pipeline.stages.s5_candidates import (
    ExpansionOutput,
    _deduplicate_chunks,
    _rank_by_signal_density,
    _retrieve_chunks_by_blocks,
    _search_keywords_in_blocks,
    stage_candidates,
)
from src.retrieval.indexer import DocumentIndex

# =============================================================================
# Fixtures
# =============================================================================


@pytest.fixture
def sample_blocks() -> list[DocumentBlock]:
    """Create sample blocks with various signal keywords."""
    return [
        DocumentBlock(
            block_id="block_1",
            page=1,
            block_type=BlockType.PARAGRAPH,
            text="We are overweight US equities given strong earnings momentum.",
            confidence=0.95,
        ),
        DocumentBlock(
            block_id="block_2",
            page=1,
            block_type=BlockType.PARAGRAPH,
            text="Prefer European bonds over emerging market debt.",
            confidence=0.95,
        ),
        DocumentBlock(
            block_id="block_3",
            page=2,
            block_type=BlockType.PARAGRAPH,
            text="Market commentary on general economic conditions.",
            confidence=0.95,
        ),
        DocumentBlock(
            block_id="block_4",
            page=2,
            block_type=BlockType.PARAGRAPH,
            text="Underweight commodities with cautious stance on gold.",
            confidence=0.95,
        ),
        DocumentBlock(
            block_id="block_5",
            page=2,
            block_type=BlockType.DISCLAIMER,
            text="This document contains forward-looking statements.",
            confidence=0.95,
        ),
    ]


@pytest.fixture
def sample_cleaned_doc(sample_blocks: list[DocumentBlock]) -> CleanedDocument:
    """Create a sample cleaned document."""
    return CleanedDocument(
        document_id="doc_123",
        blocks=sample_blocks,
        sections=[
            Section(
                section_id="doc_123_sec_0",
                title="Market Outlook",
                start_block_id="block_1",
                end_block_id="block_4",
                section_type="macro",
            )
        ],
        removed_boilerplate_count=0,
    )


@pytest.fixture
def sample_chunks() -> list[Chunk]:
    """Create sample chunks."""
    return [
        Chunk(
            chunk_id="doc_123_0",
            block_ids=["block_1"],
            page=1,
            text="We are overweight US equities given strong earnings momentum.",
            section="Market Outlook",
        ),
        Chunk(
            chunk_id="doc_123_1",
            block_ids=["block_2"],
            page=1,
            text="Prefer European bonds over emerging market debt.",
            section="Market Outlook",
        ),
        Chunk(
            chunk_id="doc_123_2",
            block_ids=["block_3"],
            page=2,
            text="Market commentary on general economic conditions.",
            section="Market Outlook",
        ),
        Chunk(
            chunk_id="doc_123_3",
            block_ids=["block_4"],
            page=2,
            text="Underweight commodities with cautious stance on gold.",
            section="Market Outlook",
        ),
    ]


@pytest.fixture
def mock_index(sample_chunks: list[Chunk]) -> DocumentIndex:
    """Create a mock document index."""
    index = MagicMock(spec=DocumentIndex)
    index.document_id = "doc_123"
    index.chunks = sample_chunks
    return index


# =============================================================================
# Test Keyword Mining
# =============================================================================


def test_search_keywords_finds_positioning_signals(sample_cleaned_doc: CleanedDocument) -> None:
    """Test that keyword search finds positioning signals."""
    keyword_matches = _search_keywords_in_blocks(sample_cleaned_doc)

    assert "overweight" in keyword_matches
    assert "block_1" in keyword_matches["overweight"]

    assert "prefer" in keyword_matches
    assert "block_2" in keyword_matches["prefer"]

    assert "underweight" in keyword_matches
    assert "block_4" in keyword_matches["underweight"]


def test_search_keywords_finds_asset_classes(sample_cleaned_doc: CleanedDocument) -> None:
    """Test that keyword search finds asset class mentions."""
    keyword_matches = _search_keywords_in_blocks(sample_cleaned_doc)

    # "US equities" contains "equities"
    assert any("equit" in kw for kw in keyword_matches)

    # "gold" should be found
    assert "gold" in keyword_matches
    assert "block_4" in keyword_matches["gold"]


def test_search_keywords_skips_disclaimers(sample_cleaned_doc: CleanedDocument) -> None:
    """Test that disclaimer blocks are skipped."""
    keyword_matches = _search_keywords_in_blocks(sample_cleaned_doc)

    # block_5 is a disclaimer and should not appear in matches
    for block_ids in keyword_matches.values():
        assert "block_5" not in block_ids


def test_search_keywords_empty_document() -> None:
    """Test keyword search on empty document."""
    cleaned_doc = CleanedDocument(
        document_id="doc_empty",
        blocks=[],
        sections=[],
        removed_boilerplate_count=0,
    )

    keyword_matches = _search_keywords_in_blocks(cleaned_doc)
    assert keyword_matches == {}


# =============================================================================
# Test Chunk Retrieval
# =============================================================================


def test_retrieve_chunks_by_blocks(mock_index: DocumentIndex) -> None:
    """Test retrieving chunks by block IDs."""
    block_ids = {"block_1", "block_4"}
    chunks = _retrieve_chunks_by_blocks(mock_index, block_ids)

    assert len(chunks) == 2
    assert chunks[0].chunk_id == "doc_123_0"
    assert chunks[1].chunk_id == "doc_123_3"
    assert all(chunk.score == 1.0 for chunk in chunks)


def test_retrieve_chunks_no_matches(mock_index: DocumentIndex) -> None:
    """Test retrieving chunks when no blocks match."""
    block_ids = {"block_99", "block_100"}
    chunks = _retrieve_chunks_by_blocks(mock_index, block_ids)

    assert len(chunks) == 0


# =============================================================================
# Test Ranking
# =============================================================================


def test_rank_by_signal_density() -> None:
    """Test ranking chunks by signal keyword density."""
    chunks = [
        RetrievedChunk(
            chunk_id="chunk_1",
            block_ids=["block_1"],
            page=1,
            text="Market commentary without signals.",
            score=1.0,
        ),
        RetrievedChunk(
            chunk_id="chunk_2",
            block_ids=["block_2"],
            page=2,
            text="Overweight US equities, underweight bonds, prefer gold.",
            score=1.0,
        ),
        RetrievedChunk(
            chunk_id="chunk_3",
            block_ids=["block_3"],
            page=1,
            text="Cautious on emerging markets.",
            score=1.0,
        ),
    ]

    ranked = _rank_by_signal_density(chunks)

    # chunk_2 has most signals (overweight, underweight, prefer, gold)
    assert ranked[0].chunk_id == "chunk_2"
    # chunk_3 has one signal (cautious)
    assert ranked[1].chunk_id == "chunk_3"
    # chunk_1 has no signals
    assert ranked[2].chunk_id == "chunk_1"


def test_rank_by_signal_density_ties_use_page() -> None:
    """Test that ties in signal density are broken by page number."""
    chunks = [
        RetrievedChunk(
            chunk_id="chunk_1",
            block_ids=["block_1"],
            page=2,
            text="Overweight equities.",
            score=1.0,
        ),
        RetrievedChunk(
            chunk_id="chunk_2",
            block_ids=["block_2"],
            page=1,
            text="Underweight bonds.",
            score=1.0,
        ),
    ]

    ranked = _rank_by_signal_density(chunks)

    # Both have similar signal count, but chunk_2 is on earlier page
    assert ranked[0].chunk_id == "chunk_2"
    assert ranked[1].chunk_id == "chunk_1"


# =============================================================================
# Test Deduplication
# =============================================================================


def test_deduplicate_chunks() -> None:
    """Test chunk deduplication."""
    chunks = [
        RetrievedChunk(
            chunk_id="chunk_1",
            block_ids=["block_1"],
            page=1,
            text="Text 1",
            score=1.0,
        ),
        RetrievedChunk(
            chunk_id="chunk_2",
            block_ids=["block_2"],
            page=2,
            text="Text 2",
            score=1.0,
        ),
        RetrievedChunk(
            chunk_id="chunk_1",
            block_ids=["block_1"],
            page=1,
            text="Text 1",
            score=0.8,
        ),
    ]

    deduplicated = _deduplicate_chunks(chunks)

    assert len(deduplicated) == 2
    assert deduplicated[0].chunk_id == "chunk_1"
    assert deduplicated[1].chunk_id == "chunk_2"


def test_deduplicate_preserves_order() -> None:
    """Test that deduplication preserves first occurrence."""
    chunks = [
        RetrievedChunk(
            chunk_id="chunk_2",
            block_ids=["block_2"],
            page=2,
            text="Text 2",
            score=1.0,
        ),
        RetrievedChunk(
            chunk_id="chunk_1",
            block_ids=["block_1"],
            page=1,
            text="Text 1",
            score=1.0,
        ),
        RetrievedChunk(
            chunk_id="chunk_2",
            block_ids=["block_2"],
            page=2,
            text="Text 2",
            score=0.5,
        ),
    ]

    deduplicated = _deduplicate_chunks(chunks)

    assert len(deduplicated) == 2
    assert deduplicated[0].chunk_id == "chunk_2"
    assert deduplicated[1].chunk_id == "chunk_1"


# =============================================================================
# Test Full Pipeline
# =============================================================================


@pytest.mark.asyncio
async def test_stage_candidates_success(
    sample_cleaned_doc: CleanedDocument,
    mock_index: DocumentIndex,
) -> None:
    """Test successful candidate retrieval."""
    mock_llm = AsyncMock()
    mock_llm.complete_json = AsyncMock(
        return_value=ExpansionOutput(
            additional_chunk_ids=["doc_123_2"],
            reasoning="Found additional market commentary",
        )
    )

    result = await stage_candidates(sample_cleaned_doc, mock_index, mock_llm)

    assert isinstance(result, CandidateSet)
    assert result.document_id == "doc_123"
    assert len(result.candidates) >= 3  # Should have at least 3 candidates
    assert result.total_chunks_reviewed == 4

    # Should have keyword matches
    assert len(result.keyword_matches) > 0


@pytest.mark.asyncio
async def test_stage_candidates_no_keywords(
    mock_index: DocumentIndex,
) -> None:
    """Test candidate retrieval when very few keywords found."""
    # Document with minimal signal keywords
    cleaned_doc = CleanedDocument(
        document_id="doc_123",
        blocks=[
            DocumentBlock(
                block_id="block_1",
                page=1,
                block_type=BlockType.PARAGRAPH,
                text="The Federal Reserve released data yesterday.",
                confidence=0.95,
            )
        ],
        sections=[
            Section(
                section_id="doc_123_sec_0",
                title="Overview",
                start_block_id="block_1",
                end_block_id="block_1",
                section_type="other",
            )
        ],
        removed_boilerplate_count=0,
    )

    mock_llm = AsyncMock()

    result = await stage_candidates(cleaned_doc, mock_index, mock_llm)

    # Should return all chunks when few keywords found
    assert len(result.candidates) > 0
    # May have some incidental keyword matches from short acronyms, but should be minimal
    assert len(result.keyword_matches) < 5


@pytest.mark.asyncio
async def test_stage_candidates_llm_expansion_fails(
    sample_cleaned_doc: CleanedDocument,
    mock_index: DocumentIndex,
) -> None:
    """Test that LLM expansion failure doesn't break the pipeline."""
    mock_llm = AsyncMock()
    mock_llm.complete_json = AsyncMock(side_effect=Exception("LLM API error"))

    result = await stage_candidates(sample_cleaned_doc, mock_index, mock_llm)

    # Should still return keyword-based candidates
    assert isinstance(result, CandidateSet)
    assert len(result.candidates) >= 1  # At least keyword matches


@pytest.mark.asyncio
async def test_stage_candidates_empty_index(
    sample_cleaned_doc: CleanedDocument,
) -> None:
    """Test that empty index raises error."""
    mock_index = MagicMock(spec=DocumentIndex)
    mock_index.chunks = []

    mock_llm = AsyncMock()

    with pytest.raises(Exception, match="No chunks available"):
        await stage_candidates(sample_cleaned_doc, mock_index, mock_llm)


@pytest.mark.asyncio
async def test_stage_candidates_default_llm_client(
    sample_cleaned_doc: CleanedDocument,
    mock_index: DocumentIndex,
) -> None:
    """Test that stage creates default LLM client when not provided."""
    with patch("src.pipeline.stages.s5_candidates.LLMClient") as mock_llm_class:
        mock_llm_instance = AsyncMock()
        mock_llm_instance.complete_json = AsyncMock(
            return_value=ExpansionOutput(
                additional_chunk_ids=[],
                reasoning="No additional chunks needed",
            )
        )
        mock_llm_class.return_value = mock_llm_instance

        result = await stage_candidates(sample_cleaned_doc, mock_index)

        assert isinstance(result, CandidateSet)
        mock_llm_class.assert_called_once()


@pytest.mark.asyncio
async def test_stage_candidates_limits_output_size(
    sample_cleaned_doc: CleanedDocument,
    mock_index: DocumentIndex,
) -> None:
    """Test that candidate set is limited to reasonable size."""
    # Create many keyword matches
    mock_index.chunks = [
        Chunk(
            chunk_id=f"doc_123_{i}",
            block_ids=[f"block_{i}"],
            page=i // 5 + 1,
            text=f"Overweight equities {i} with strong conviction.",
            section="Market Outlook",
        )
        for i in range(50)
    ]

    mock_llm = AsyncMock()
    mock_llm.complete_json = AsyncMock(
        return_value=ExpansionOutput(
            additional_chunk_ids=[],
            reasoning="No expansion needed",
        )
    )

    result = await stage_candidates(sample_cleaned_doc, mock_index, mock_llm)

    # Should be limited to MAX_KEYWORD_CHUNKS + MAX_EXPANSION_CHUNKS (30 total)
    assert len(result.candidates) <= 30
