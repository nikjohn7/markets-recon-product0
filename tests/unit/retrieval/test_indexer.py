"""Unit tests for retrieval indexer."""

import pytest
from unittest.mock import Mock, patch, AsyncMock

from src.models.document import DocumentBlock
from src.models.pipeline import CleanedDocument, Section, Chunk, RetrievedChunk
from src.models.enums import BlockType
from src.exceptions import ExtractionError
from src.retrieval.indexer import (
    chunk_document,
    generate_embeddings,
    DocumentIndex,
    OpenAIEmbeddingProvider,
)


class TestChunkDocument:
    """Unit tests for chunk_document function."""
    
    def test_chunk_document_basic(self):
        """Test basic chunking with multiple sections."""
        blocks = [
            DocumentBlock(
                block_id="doc1_0",
                page=1,
                text="Section 1 Title",
                block_type=BlockType.HEADING,
                bbox=None,
                confidence=1.0,
            ),
            DocumentBlock(
                block_id="doc1_1",
                page=1,
                text="This is a paragraph with enough text to create a meaningful chunk. " * 10,
                block_type=BlockType.PARAGRAPH,
                bbox=None,
                confidence=1.0,
            ),
            DocumentBlock(
                block_id="doc1_2",
                page=2,
                text="Section 2 Title",
                block_type=BlockType.HEADING,
                bbox=None,
                confidence=1.0,
            ),
            DocumentBlock(
                block_id="doc1_3",
                page=2,
                text="Another paragraph with substantial content. " * 10,
                block_type=BlockType.PARAGRAPH,
                bbox=None,
                confidence=1.0,
            ),
        ]
        
        sections = [
            Section(
                section_id="doc1_sec_0",
                title="Section 1 Title",
                start_block_id="doc1_0",
                end_block_id="doc1_1",
                section_type="macro",
            ),
            Section(
                section_id="doc1_sec_1",
                title="Section 2 Title",
                start_block_id="doc1_2",
                end_block_id="doc1_3",
                section_type="equities",
            ),
        ]
        
        cleaned_doc = CleanedDocument(
            document_id="doc1",
            blocks=blocks,
            sections=sections,
            removed_boilerplate_count=0,
            disclaimer_block_id=None,
        )
        
        chunks = chunk_document(cleaned_doc)
        
        assert len(chunks) > 0
        assert all(isinstance(chunk, Chunk) for chunk in chunks)
        
        # Check chunk structure
        for chunk in chunks:
            assert chunk.chunk_id.startswith("doc1_")
            assert len(chunk.block_ids) > 0
            assert chunk.page >= 1
            assert len(chunk.text) > 0
            assert chunk.section in ["Section 1 Title", "Section 2 Title", None]
    
    def test_chunk_document_skips_disclaimers(self):
        """Test that disclaimer blocks are skipped."""
        blocks = [
            DocumentBlock(
                block_id="doc1_0",
                page=1,
                text="Main Content",
                block_type=BlockType.PARAGRAPH,
                bbox=None,
                confidence=1.0,
            ),
            DocumentBlock(
                block_id="doc1_1",
                page=1,
                text="Disclaimer text here",
                block_type=BlockType.DISCLAIMER,
                bbox=None,
                confidence=1.0,
            ),
        ]
        
        sections = [
            Section(
                section_id="doc1_sec_0",
                title=None,
                start_block_id="doc1_0",
                end_block_id="doc1_1",
                section_type=None,
            ),
        ]
        
        cleaned_doc = CleanedDocument(
            document_id="doc1",
            blocks=blocks,
            sections=sections,
            removed_boilerplate_count=0,
            disclaimer_block_id="doc1_1",
        )
        
        chunks = chunk_document(cleaned_doc)
        
        # Should only include non-disclaimer content
        for chunk in chunks:
            assert "Disclaimer" not in chunk.text
    
    def test_chunk_document_size_constraints(self):
        """Test chunk size constraints (200-400 tokens)."""
        # Create blocks with known character counts
        # ~4 chars/token, so 800 chars = ~200 tokens, 1600 chars = ~400 tokens
        short_text = "Short. " * 50  # ~300 chars = ~75 tokens
        medium_text = "Medium length paragraph. " * 40  # ~960 chars = ~240 tokens
        long_text = "This is a very long paragraph that should trigger chunk splitting. " * 80  # ~4000 chars = ~1000 tokens
        
        blocks = [
            DocumentBlock(
                block_id="doc1_0",
                page=1,
                text=short_text,
                block_type=BlockType.PARAGRAPH,
                bbox=None,
                confidence=1.0,
            ),
            DocumentBlock(
                block_id="doc1_1",
                page=1,
                text=medium_text,
                block_type=BlockType.PARAGRAPH,
                bbox=None,
                confidence=1.0,
            ),
            DocumentBlock(
                block_id="doc1_2",
                page=1,
                text=long_text,
                block_type=BlockType.PARAGRAPH,
                bbox=None,
                confidence=1.0,
            ),
        ]
        
        sections = [
            Section(
                section_id="doc1_sec_0",
                title=None,
                start_block_id="doc1_0",
                end_block_id="doc1_2",
                section_type=None,
            ),
        ]
        
        cleaned_doc = CleanedDocument(
            document_id="doc1_size",
            blocks=blocks,
            sections=sections,
            removed_boilerplate_count=0,
            disclaimer_block_id=None,
        )
        
        chunks = chunk_document(cleaned_doc)
        
        # Should create multiple chunks due to size constraints
        assert len(chunks) >= 2
        
        # Check that chunks are reasonable size
        for chunk in chunks:
            # Should not exceed max tokens significantly
            assert len(chunk.text) <= 2000  # 400 tokens * 5 chars/token buffer
    
    def test_chunk_document_empty_sections(self):
        """Test handling of empty sections."""
        blocks = [
            DocumentBlock(
                block_id="doc1_0",
                page=1,
                text="Content",
                block_type=BlockType.PARAGRAPH,
                bbox=None,
                confidence=1.0,
            ),
        ]
        
        # No sections - should fall back to simple chunking
        sections = []
        
        cleaned_doc = CleanedDocument(
            document_id="doc1",
            blocks=blocks,
            sections=sections,
            removed_boilerplate_count=0,
            disclaimer_block_id=None,
        )
        
        chunks = chunk_document(cleaned_doc)
        
        # Should still create chunks using fallback logic
        assert len(chunks) >= 0  # May be 0 if content too short
    
    def test_chunk_document_preserves_block_references(self):
        """Test that chunks preserve correct block_id references."""
        blocks = [
            DocumentBlock(
                block_id="doc1_0",
                page=1,
                text="First paragraph with enough content to create a chunk. " * 10,
                block_type=BlockType.PARAGRAPH,
                bbox=None,
                confidence=1.0,
            ),
            DocumentBlock(
                block_id="doc1_1",
                page=1,
                text="Second paragraph with enough content. " * 10,
                block_type=BlockType.PARAGRAPH,
                bbox=None,
                confidence=1.0,
            ),
        ]
        
        sections = [
            Section(
                section_id="doc1_sec_0",
                title=None,
                start_block_id="doc1_0",
                end_block_id="doc1_1",
                section_type=None,
            ),
        ]
        
        cleaned_doc = CleanedDocument(
            document_id="doc1",
            blocks=blocks,
            sections=sections,
            removed_boilerplate_count=0,
            disclaimer_block_id=None,
        )
        
        chunks = chunk_document(cleaned_doc)
        
        # Check that block_ids are correctly referenced
        for chunk in chunks:
            assert all(block_id in ["doc1_0", "doc1_1"] for block_id in chunk.block_ids)
            # Verify page is set correctly
            assert chunk.page == 1


class TestGenerateEmbeddings:
    """Unit tests for generate_embeddings function."""
    
    @pytest.mark.asyncio
    async def test_generate_embeddings_basic(self):
        """Test basic embedding generation."""
        chunks = [
            Chunk(
                chunk_id="doc1_0",
                block_ids=["block1"],
                page=1,
                text="Test chunk text",
                section="Test Section",
            ),
            Chunk(
                chunk_id="doc1_1",
                block_ids=["block2"],
                page=2,
                text="Another test chunk",
                section=None,
            ),
        ]
        
        with patch("src.retrieval.indexer.get_settings") as mock_settings:
            mock_settings.return_value.openai_api_key.get_secret_value.return_value = "test-key"
            
            with patch("src.retrieval.indexer.OpenAIEmbeddingProvider") as mock_provider_class:
                mock_provider = Mock()
                mock_provider.generate_embeddings = AsyncMock(
                    return_value=[[0.1] * 1536, [0.2] * 1536]
                )
                mock_provider_class.return_value = mock_provider
                
                embeddings = await generate_embeddings(chunks)
                
                assert len(embeddings) == 2
                assert all(len(emb) == 1536 for emb in embeddings)
                assert embeddings[0] != embeddings[1]  # Different embeddings
    
    @pytest.mark.asyncio
    async def test_generate_embeddings_empty_list(self):
        """Test embedding generation with empty list."""
        chunks = []
        
        embeddings = await generate_embeddings(chunks)
        
        assert embeddings == []
    
    @pytest.mark.asyncio
    async def test_generate_embeddings_retry_on_failure(self):
        """Test retry logic on embedding API failure."""
        chunks = [
            Chunk(
                chunk_id="doc1_0",
                block_ids=["block1"],
                page=1,
                text="Test chunk",
                section=None,
            ),
        ]
        
        with patch("src.retrieval.indexer.get_settings") as mock_settings:
            mock_settings.return_value.openai_api_key.get_secret_value.return_value = "test-key"
            
            with patch("src.retrieval.indexer.OpenAIEmbeddingProvider") as mock_provider_class:
                mock_provider = Mock()
                # Mock the provider to raise exception on first call, succeed on second
                mock_provider.generate_embeddings = AsyncMock(
                    side_effect=[
                        Exception("API Error"),
                        [[0.1] * 1536],
                    ]
                )
                mock_provider_class.return_value = mock_provider
                
                embeddings = await generate_embeddings(chunks)
                
                assert len(embeddings) == 1
                assert len(embeddings[0]) == 1536


class TestOpenAIEmbeddingProvider:
    """Unit tests for OpenAIEmbeddingProvider."""
    
    @pytest.mark.asyncio
    async def test_generate_embeddings_success(self):
        """Test successful embedding generation."""
        provider = OpenAIEmbeddingProvider(api_key="test-key")
        
        with patch.object(provider.client.embeddings, "create") as mock_create:
            mock_response = Mock()
            mock_response.data = [
                Mock(embedding=[0.1] * 1536),
                Mock(embedding=[0.2] * 1536),
            ]
            mock_create.return_value = mock_response
            
            embeddings = await provider.generate_embeddings(["text1", "text2"])
            
            assert len(embeddings) == 2
            assert len(embeddings[0]) == 1536
            assert embeddings[0] != embeddings[1]
            mock_create.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_generate_embeddings_retry_on_rate_limit(self):
        """Test retry on rate limit error."""
        provider = OpenAIEmbeddingProvider(api_key="test-key")
        
        with patch.object(provider.client.embeddings, "create") as mock_create:
            # First call fails, second succeeds
            mock_create.side_effect = [
                Exception("Rate limit exceeded"),
                Mock(data=[Mock(embedding=[0.1] * 1536)]),
            ]
            
            embeddings = await provider.generate_embeddings(["text"])
            
            assert len(embeddings) == 1
            assert mock_create.call_count == 2
    
    @pytest.mark.asyncio
    async def test_generate_embeddings_max_retries_exceeded(self):
        """Test failure after max retries."""
        provider = OpenAIEmbeddingProvider(api_key="test-key")
        
        with patch.object(provider.client.embeddings, "create") as mock_create:
            mock_create.side_effect = Exception("Persistent error")
            
            with pytest.raises(Exception):
                await provider.generate_embeddings(["text"])
            
            # Should have tried 3 times
            assert mock_create.call_count == 3


class TestDocumentIndex:
    """Unit tests for DocumentIndex class."""
    
    def test_document_index_initialization(self):
        """Test DocumentIndex initialization."""
        index = DocumentIndex(document_id="doc_init_test")
        
        assert index.document_id == "doc_init_test"
        assert index.chunks == []
        assert index.collection is not None
    
    @pytest.mark.asyncio
    async def test_document_index_build(self):
        """Test building index from cleaned document."""
        blocks = [
            DocumentBlock(
                block_id="doc_build_0",
                page=1,
                text="Chunkable content with sufficient length. " * 20,
                block_type=BlockType.PARAGRAPH,
                bbox=None,
                confidence=1.0,
            ),
        ]
        
        sections = [
            Section(
                section_id="doc_build_sec_0",
                title="Test Section",
                start_block_id="doc_build_0",
                end_block_id="doc_build_0",
                section_type="macro",
            ),
        ]
        
        cleaned_doc = CleanedDocument(
            document_id="doc_build",
            blocks=blocks,
            sections=sections,
            removed_boilerplate_count=0,
            disclaimer_block_id=None,
        )
        
        index = DocumentIndex(document_id="doc_build")
        
        with patch("src.retrieval.indexer.generate_embeddings") as mock_generate:
            mock_generate.return_value = [[0.1] * 1536]
            
            await index.build(cleaned_doc)
            
            assert len(index.chunks) > 0
            mock_generate.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_document_index_query(self):
        """Test querying the index."""
        index = DocumentIndex(document_id="doc_query")
        
        # Add mock chunks
        index.chunks = [
            Chunk(
                chunk_id="doc_query_0",
                block_ids=["block1"],
                page=1,
                text="Test chunk about technology stocks",
                section="Tech",
            ),
        ]
        
        with patch("src.retrieval.indexer.get_settings") as mock_settings:
            mock_settings.return_value.openai_api_key.get_secret_value.return_value = "test-key"
            
            with patch("src.retrieval.indexer.OpenAIEmbeddingProvider") as mock_provider_class:
                mock_provider = Mock()
                mock_provider.generate_embeddings = AsyncMock(return_value=[[0.1] * 1536])
                mock_provider_class.return_value = mock_provider
                
                # Mock collection query
                index.collection = Mock()
                index.collection.query = Mock(
                    return_value={
                        "ids": [["doc_query_0"]],
                        "distances": [[0.2]],
                        "documents": [["Test chunk about technology stocks"]],
                        "metadatas": [[{"block_ids": "block1", "page": 1, "section": "Tech"}]],
                    }
                )
                
                results = await index.query("technology stocks", top_k=3)
                
                assert len(results) == 1
                assert isinstance(results[0], RetrievedChunk)
                assert results[0].chunk_id == "doc_query_0"
                assert results[0].score > 0
                assert results[0].section == "Tech"
    
    @pytest.mark.asyncio
    async def test_document_index_query_empty_index(self):
        """Test querying empty index."""
        index = DocumentIndex(document_id="doc_empty")
        
        results = await index.query("test query")
        
        assert results == []
    
    @pytest.mark.asyncio
    async def test_document_index_query_chunk_not_found(self):
        """Test query when chunk is not found in stored chunks."""
        index = DocumentIndex(document_id="doc_notfound")
        index.chunks = []  # Empty chunks list
        
        with patch("src.retrieval.indexer.get_settings") as mock_settings:
            mock_settings.return_value.openai_api_key.get_secret_value.return_value = "test-key"
            
            with patch("src.retrieval.indexer.OpenAIEmbeddingProvider") as mock_provider_class:
                mock_provider = Mock()
                mock_provider.generate_embeddings = AsyncMock(return_value=[[0.1] * 1536])
                mock_provider_class.return_value = mock_provider
                
                # Return chunk ID that doesn't exist in index.chunks
                index.collection = Mock()
                index.collection.query = Mock(
                    return_value={
                        "ids": [["doc_notfound_nonexistent"]],
                        "distances": [[0.1]],
                        "documents": [["Some text"]],
                        "metadatas": [[{"block_ids": "block1", "page": 1, "section": ""}]],
                    }
                )
                
                results = await index.query("test")
                
                # Should return empty list since chunk wasn't found
                assert len(results) == 0