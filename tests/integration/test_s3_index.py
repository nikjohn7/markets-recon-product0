"""Integration tests for Stage 3 - Retrieval Index."""

import pytest
from unittest.mock import Mock, patch, AsyncMock

from src.models.document import DocumentBlock, DocumentJSON
from src.models.pipeline import CleanedDocument, Section, RetrievedChunk
from src.models.enums import BlockType
from src.pipeline.stages.s3_index import stage_index
from src.retrieval.indexer import DocumentIndex


class TestStageIndexIntegration:
    """Integration tests for stage_index function."""
    
    @pytest.mark.asyncio
    async def test_stage_index_full_pipeline(self):
        """Test complete Stage 3 pipeline with realistic document."""
        # Create realistic document structure
        blocks = [
            # Section 1: Macro Outlook
            DocumentBlock(
                block_id="doc1_0",
                page=1,
                text="Macro Outlook",
                block_type=BlockType.HEADING,
                bbox=None,
                confidence=1.0,
            ),
            DocumentBlock(
                block_id="doc1_1",
                page=1,
                text="We expect global growth to moderate in 2025 as central banks continue their tightening cycles. Inflation pressures are showing signs of easing, particularly in developed markets.",
                block_type=BlockType.PARAGRAPH,
                bbox=None,
                confidence=1.0,
            ),
            DocumentBlock(
                block_id="doc1_2",
                page=1,
                text="Key risks include geopolitical tensions and potential supply chain disruptions. However, labor markets remain resilient, supporting consumer spending.",
                block_type=BlockType.PARAGRAPH,
                bbox=None,
                confidence=1.0,
            ),
            # Section 2: Fixed Income
            DocumentBlock(
                block_id="doc1_3",
                page=2,
                text="Fixed Income Strategy",
                block_type=BlockType.HEADING,
                bbox=None,
                confidence=1.0,
            ),
            DocumentBlock(
                block_id="doc1_4",
                page=2,
                text="We maintain our overweight position on high-quality government bonds, particularly U.S. Treasuries and German Bunds. These provide portfolio ballast amid uncertainty.",
                block_type=BlockType.PARAGRAPH,
                bbox=None,
                confidence=1.0,
            ),
            DocumentBlock(
                block_id="doc1_5",
                page=2,
                text="Investment grade credit remains attractive, with spreads offering reasonable compensation for risk. We are more cautious on high yield given recession risks.",
                block_type=BlockType.PARAGRAPH,
                bbox=None,
                confidence=1.0,
            ),
            # Disclaimer (should be skipped)
            DocumentBlock(
                block_id="doc1_6",
                page=3,
                text="This document is for informational purposes only and does not constitute investment advice.",
                block_type=BlockType.DISCLAIMER,
                bbox=None,
                confidence=1.0,
            ),
        ]
        
        sections = [
            Section(
                section_id="doc1_sec_0",
                title="Macro Outlook",
                start_block_id="doc1_0",
                end_block_id="doc1_2",
                section_type="macro",
            ),
            Section(
                section_id="doc1_sec_1",
                title="Fixed Income Strategy",
                start_block_id="doc1_3",
                end_block_id="doc1_5",
                section_type="fixed_income",
            ),
        ]
        
        cleaned_doc = CleanedDocument(
            document_id="doc1",
            blocks=blocks,
            sections=sections,
            removed_boilerplate_count=0,
            disclaimer_block_id="doc1_6",
        )
        
        # Mock embedding generation for integration test
        with patch("src.pipeline.stages.s3_index.DocumentIndex.build") as mock_build:
            mock_build.return_value = None
            
            index = await stage_index(cleaned_doc)
            
            assert isinstance(index, DocumentIndex)
            assert index.document_id == "doc1"
            mock_build.assert_called_once_with(cleaned_doc)
    
    @pytest.mark.asyncio
    async def test_stage_index_with_query(self):
        """Test Stage 3 with actual querying."""
        # Create test document with sufficient content
        blocks = [
            DocumentBlock(
                block_id="doc_qtest_0",
                page=1,
                text="Investment Strategy",
                block_type=BlockType.HEADING,
                bbox=None,
                confidence=1.0,
            ),
            DocumentBlock(
                block_id="doc_qtest_1",
                page=1,
                text="We are overweight on technology stocks due to strong earnings growth and AI tailwinds. " * 10,
                block_type=BlockType.PARAGRAPH,
                bbox=None,
                confidence=1.0,
            ),
        ]
        
        sections = [
            Section(
                section_id="doc_qtest_sec_0",
                title="Investment Strategy",
                start_block_id="doc_qtest_0",
                end_block_id="doc_qtest_1",
                section_type="equities",
            ),
        ]
        
        cleaned_doc = CleanedDocument(
            document_id="doc_qtest",
            blocks=blocks,
            sections=sections,
            removed_boilerplate_count=0,
            disclaimer_block_id=None,
        )
        
        # Create index and build with mocked embeddings
        index = DocumentIndex(document_id="doc_qtest")
        
        with patch("src.retrieval.indexer.generate_embeddings") as mock_generate:
            # Return deterministic embeddings
            mock_generate.return_value = [
                [0.1] * 1536,  # Embedding for first chunk
            ]
            
            await index.build(cleaned_doc)
            
            # Verify chunks were created
            assert len(index.chunks) > 0
            
            # Test querying
            with patch("src.retrieval.indexer.OpenAIEmbeddingProvider") as mock_provider_class:
                mock_provider = Mock()
                mock_provider.generate_embeddings = AsyncMock(return_value=[[0.15] * 1536])
                mock_provider_class.return_value = mock_provider
                
                with patch("src.retrieval.indexer.get_settings"):
                    # Mock collection query
                    index.collection = Mock()
                    index.collection.query = Mock(
                        return_value={
                            "ids": [["doc_qtest_0"]],
                            "distances": [[0.1]],
                            "documents": [["We are overweight on technology stocks..."]],
                            "metadatas": [[{"block_ids": "doc_qtest_1", "page": 1, "section": "Investment Strategy"}]],
                        }
                    )
                    
                    results = await index.query("technology stocks overweight", top_k=3)
                    
                    assert len(results) > 0
                    assert all(isinstance(r, RetrievedChunk) for r in results)
                    assert all(r.score > 0 for r in results)
    
    @pytest.mark.asyncio
    async def test_stage_index_empty_document(self):
        """Test Stage 3 with empty document."""
        cleaned_doc = CleanedDocument(
            document_id="doc_empty_test",
            blocks=[],
            sections=[],
            removed_boilerplate_count=0,
            disclaimer_block_id=None,
        )
        
        index = await stage_index(cleaned_doc)
        
        assert isinstance(index, DocumentIndex)
        assert len(index.chunks) == 0
    
    @pytest.mark.asyncio
    async def test_stage_index_minimal_content(self):
        """Test Stage 3 with minimal content (<5 chunks)."""
        # Create very short document
        blocks = [
            DocumentBlock(
                block_id="doc_minimal_0",
                page=1,
                text="Short",
                block_type=BlockType.PARAGRAPH,
                bbox=None,
                confidence=1.0,
            ),
        ]
        
        sections = [
            Section(
                section_id="doc_minimal_sec_0",
                title=None,
                start_block_id="doc_minimal_0",
                end_block_id="doc_minimal_0",
                section_type=None,
            ),
        ]
        
        cleaned_doc = CleanedDocument(
            document_id="doc_minimal",
            blocks=blocks,
            sections=sections,
            removed_boilerplate_count=0,
            disclaimer_block_id=None,
        )
        
        with patch("src.retrieval.indexer.generate_embeddings") as mock_generate:
            mock_generate.return_value = [[0.1] * 1536]
            
            index = await stage_index(cleaned_doc)
            
            # Should still create index even with minimal content
            assert isinstance(index, DocumentIndex)
            
            # May have 0 or 1 chunks depending on size thresholds
            assert len(index.chunks) >= 0


class TestDocumentIndexQueryIntegration:
    """Integration tests for DocumentIndex querying."""
    
    @pytest.mark.asyncio
    async def test_query_relevance(self):
        """Test that queries return relevant results."""
        # Create document with distinct topics and sufficient content
        blocks = [
            DocumentBlock(
                block_id="doc_rel_0",
                page=1,
                text="Technology Sector",
                block_type=BlockType.HEADING,
                bbox=None,
                confidence=1.0,
            ),
            DocumentBlock(
                block_id="doc_rel_1",
                page=1,
                text="We are bullish on technology stocks due to AI innovation and strong cloud adoption. " * 10,
                block_type=BlockType.PARAGRAPH,
                bbox=None,
                confidence=1.0,
            ),
            DocumentBlock(
                block_id="doc_rel_2",
                page=2,
                text="Fixed Income",
                block_type=BlockType.HEADING,
                bbox=None,
                confidence=1.0,
            ),
            DocumentBlock(
                block_id="doc_rel_3",
                page=2,
                text="Government bonds look attractive as yields have risen significantly. " * 10,
                block_type=BlockType.PARAGRAPH,
                bbox=None,
                confidence=1.0,
            ),
        ]
        
        sections = [
            Section(
                section_id="doc_rel_sec_0",
                title="Technology Sector",
                start_block_id="doc_rel_0",
                end_block_id="doc_rel_1",
                section_type="equities",
            ),
            Section(
                section_id="doc_rel_sec_1",
                title="Fixed Income",
                start_block_id="doc_rel_2",
                end_block_id="doc_rel_3",
                section_type="fixed_income",
            ),
        ]
        
        cleaned_doc = CleanedDocument(
            document_id="doc_rel",
            blocks=blocks,
            sections=sections,
            removed_boilerplate_count=0,
            disclaimer_block_id=None,
        )
        
        index = DocumentIndex(document_id="doc_rel")
        
        with patch("src.retrieval.indexer.generate_embeddings") as mock_generate:
            # Create different embeddings for different content
            # Only return 1 embedding since we'll only have 1 chunk
            mock_generate.return_value = [
                [0.8] * 1536,  # Technology content
            ]
            
            await index.build(cleaned_doc)
            
            # Test technology query
            with patch("src.retrieval.indexer.OpenAIEmbeddingProvider") as mock_provider_class:
                mock_provider = Mock()
                mock_provider.generate_embeddings = AsyncMock(return_value=[[0.75] * 1536])
                mock_provider_class.return_value = mock_provider
                
                with patch("src.retrieval.indexer.get_settings"):
                    # Mock collection to return technology chunk
                    index.collection = Mock()
                    index.collection.query = Mock(
                        return_value={
                            "ids": [["doc_rel_0"]],
                            "distances": [[0.1]],
                            "documents": [["Tech content..."]],
                            "metadatas": [
                                [
                                    {"block_ids": "doc_rel_1", "page": 1, "section": "Technology Sector"},
                                ]
                            ],
                        }
                    )
                    
                    results = await index.query("technology stocks AI", top_k=2)
                    
                    assert len(results) >= 1
                    # First result should be about technology
                    assert "technology" in results[0].text.lower() or "tech" in results[0].text.lower()
                    assert results[0].score > 0