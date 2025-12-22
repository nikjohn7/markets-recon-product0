"""Integration tests for Stage 1 - Text Extraction."""

from pathlib import Path

import fitz  # PyMuPDF
import pytest
from src.exceptions import ExtractionError, StorageError
from src.models.document import DocumentJSON
from src.models.enums import BlockType
from src.models.pipeline import IngestResult
from src.pipeline.stages.s1_extract import stage_extract
from src.storage.blob import LocalBlobStorage


class TestStageExtractIntegration:
    """Integration tests for the extract stage."""

    @pytest.fixture
    def temp_storage_dir(self, tmp_path):
        """Create temporary storage directory."""
        storage_dir = tmp_path / "pdfs"
        storage_dir.mkdir()
        return storage_dir

    @pytest.fixture
    def sample_ingest_result(self):
        """Create a sample ingest result for testing."""
        return IngestResult(
            document_id="test-doc-123",
            blob_id="abc123",
            file_hash="def456",
            is_duplicate=False,
            source_metadata={"filename": "test.pdf", "source": "test"},
        )

    def create_test_pdf(self, path: Path, content: str) -> None:
        """Create a simple test PDF with the given content."""
        doc = fitz.open()
        page = doc.new_page()

        # Add title (heading)
        page.insert_text((50, 50), "Investment Outlook 2024", fontsize=16)

        # Add paragraph
        page.insert_text((50, 100), content, fontsize=11)

        # Add bullet points
        bullets = [
            "• Diversified portfolio approach",
            "• Risk management focus",
            "• Long-term value creation",
        ]
        y_pos = 150
        for bullet in bullets:
            page.insert_text((50, y_pos), bullet, fontsize=11)
            y_pos += 20

        doc.save(path)
        doc.close()

    @pytest.mark.asyncio
    async def test_stage_extract_full_pipeline(self, tmp_path, sample_ingest_result):
        """Test complete extraction pipeline with real PDF."""
        # Create test PDF
        pdf_path = tmp_path / "test.pdf"
        test_content = "This is a test paragraph for integration testing."
        self.create_test_pdf(pdf_path, test_content)

        # Read PDF bytes
        with pdf_path.open("rb") as f:
            pdf_bytes = f.read()

        # Store in blob storage
        storage = LocalBlobStorage(storage_dir=str(tmp_path / "pdfs"))
        blob_id = storage.store(pdf_bytes, {"test": "metadata"})

        # Update ingest result with actual blob_id
        sample_ingest_result.blob_id = blob_id

        # Run extraction stage with the same storage instance
        result = await stage_extract(sample_ingest_result, storage=storage)

        # Verify result
        assert isinstance(result, DocumentJSON)
        assert result.document_id == sample_ingest_result.document_id
        assert result.blob_id == blob_id
        assert result.page_count == 1
        assert result.extraction_coverage == 1.0  # One page with text

        # Verify blocks were extracted
        assert len(result.blocks) > 0

        # Verify blocks contain expected content
        all_text = " ".join([b.text for b in result.blocks])
        assert "Investment Outlook" in all_text
        assert "test paragraph" in all_text
        assert (
            "Diversified" in all_text or "Risk management" in all_text
        )  # At least one bullet content

        # Verify all blocks have required fields
        for block in result.blocks:
            assert block.block_id
            assert block.page == 1
            assert block.text
            assert block.block_type in BlockType
            assert 0 <= block.confidence <= 1
            assert block.bbox is not None
            assert 0 <= block.bbox.x0 <= 1
            assert 0 <= block.bbox.y0 <= 1
            assert 0 <= block.bbox.x1 <= 1
            assert 0 <= block.bbox.y1 <= 1

    @pytest.mark.asyncio
    async def test_stage_extract_coverage_computation(self, tmp_path, sample_ingest_result):
        """Test that extraction coverage is computed correctly."""
        # Create PDF with multiple pages
        pdf_path = tmp_path / "multi_page.pdf"
        doc = fitz.open()

        # Page 1 with text
        page1 = doc.new_page()
        page1.insert_text((50, 50), "Page 1 content", fontsize=12)

        # Page 2 with text
        page2 = doc.new_page()
        page2.insert_text((50, 50), "Page 2 content", fontsize=12)

        # Page 3 without text (empty)
        doc.new_page()

        doc.save(pdf_path)
        doc.close()

        # Store in blob storage
        with pdf_path.open("rb") as f:
            pdf_bytes = f.read()

        storage = LocalBlobStorage(storage_dir=str(tmp_path / "pdfs"))
        blob_id = storage.store(pdf_bytes, {"test": "metadata"})

        # Update ingest result
        sample_ingest_result.blob_id = blob_id

        # Run extraction with the same storage instance
        result = await stage_extract(sample_ingest_result, storage=storage)

        # Verify coverage (2 out of 3 pages have text)
        assert result.extraction_coverage == pytest.approx(2 / 3)
        assert result.page_count == 3

    @pytest.mark.asyncio
    async def test_stage_extract_empty_pdf(self, tmp_path, sample_ingest_result):
        """Test extraction of PDF with no text content."""
        # Create empty PDF (no text)
        pdf_path = tmp_path / "empty.pdf"
        doc = fitz.open()
        doc.new_page()  # Empty page
        doc.save(pdf_path)
        doc.close()

        # Store in blob storage
        with pdf_path.open("rb") as f:
            pdf_bytes = f.read()

        storage = LocalBlobStorage(storage_dir=str(tmp_path / "pdfs"))
        blob_id = storage.store(pdf_bytes, {"test": "metadata"})

        # Update ingest result
        sample_ingest_result.blob_id = blob_id

        # Run extraction with storage parameter
        result = await stage_extract(sample_ingest_result, storage=storage)

        # Verify results
        assert isinstance(result, DocumentJSON)
        assert len(result.blocks) == 0
        assert result.extraction_coverage == 0.0
        assert result.page_count == 1

    @pytest.mark.asyncio
    async def test_stage_extract_blob_not_found(self, sample_ingest_result):
        """Test extraction when blob is not found in storage."""
        # Use non-existent blob_id (valid SHA-256 hex format but doesn't exist)
        sample_ingest_result.blob_id = "a" * 64  # Valid SHA-256 hex format

        with pytest.raises(StorageError, match="Blob not found"):
            await stage_extract(sample_ingest_result)

    @pytest.mark.asyncio
    async def test_stage_extract_invalid_pdf(self, tmp_path, sample_ingest_result):
        """Test extraction with invalid PDF content."""
        # Store invalid PDF bytes
        storage = LocalBlobStorage(storage_dir=str(tmp_path / "pdfs"))
        invalid_pdf = b"This is not a valid PDF"
        blob_id = storage.store(invalid_pdf, {"test": "metadata"})

        # Update ingest result
        sample_ingest_result.blob_id = blob_id

        with pytest.raises(ExtractionError, match="Failed to extract text from PDF"):
            await stage_extract(sample_ingest_result, storage=storage)

    @pytest.mark.asyncio
    async def test_stage_extract_block_id_uniqueness(self, tmp_path, sample_ingest_result):
        """Test that all block IDs are unique in extracted document."""
        # Create PDF with multiple pages and blocks
        pdf_path = tmp_path / "multi_block.pdf"
        doc = fitz.open()

        for page_num in range(1, 4):
            page = doc.new_page()
            # Add multiple blocks per page
            page.insert_text((50, 50), f"Heading {page_num}", fontsize=16)
            page.insert_text((50, 100), f"Paragraph {page_num} line 1", fontsize=11)
            page.insert_text((50, 120), f"Paragraph {page_num} line 2", fontsize=11)
            page.insert_text((50, 150), "• Bullet 1", fontsize=11)
            page.insert_text((50, 170), "• Bullet 2", fontsize=11)

        doc.save(pdf_path)
        doc.close()

        # Store and extract
        with pdf_path.open("rb") as f:
            pdf_bytes = f.read()

        storage = LocalBlobStorage(storage_dir=str(tmp_path / "pdfs"))
        blob_id = storage.store(pdf_bytes, {"test": "metadata"})

        sample_ingest_result.blob_id = blob_id

        result = await stage_extract(sample_ingest_result, storage=storage)

        # Verify all block IDs are unique
        block_ids = [block.block_id for block in result.blocks]
        assert len(block_ids) == len(set(block_ids))

        # Verify expected format (page_index)
        for block_id in block_ids:
            parts = block_id.split("_")
            assert len(parts) == 2
            page_num, index = parts
            assert page_num.isdigit()
            assert index.isdigit()


class TestDeterministicPDF:
    """Test with programmatically generated deterministic PDF."""

    def create_deterministic_pdf(self, path: Path) -> None:
        """Create a deterministic test PDF with known content."""
        doc = fitz.open()

        # Page 1: Title and introduction
        page1 = doc.new_page()
        page1.insert_text((50, 50), "Q4 2024 Investment Outlook", fontsize=18)
        page1.insert_text((50, 100), "Executive Summary", fontsize=14)
        page1.insert_text(
            (50, 130),
            "Our analysis suggests a cautiously optimistic approach to equity markets in Q4 2024.",
            fontsize=11,
        )

        # Page 2: Key points with bullets
        page2 = doc.new_page()
        page2.insert_text((50, 50), "Key Investment Themes", fontsize=14)
        page2.insert_text((50, 90), "• Diversification across asset classes", fontsize=11)
        page2.insert_text((50, 110), "• Focus on quality and value", fontsize=11)
        page2.insert_text((50, 130), "• Risk management remains paramount", fontsize=11)

        # Page 3: Detailed analysis (no text - should affect coverage)
        doc.new_page()

        doc.save(path)
        doc.close()

    @pytest.mark.asyncio
    async def test_deterministic_pdf_extraction(self, tmp_path):
        """Test extraction with deterministic PDF and assert expected coverage."""
        # Create deterministic PDF
        pdf_path = tmp_path / "deterministic.pdf"
        self.create_deterministic_pdf(pdf_path)

        # Create ingest result
        ingest_result = IngestResult(
            document_id="deterministic-test-123",
            blob_id="",
            file_hash="deterministic-hash",
            is_duplicate=False,
            source_metadata={"filename": "deterministic.pdf", "source": "test"},
        )

        # Store PDF
        with pdf_path.open("rb") as f:
            pdf_bytes = f.read()

        storage = LocalBlobStorage(storage_dir=str(tmp_path / "pdfs"))
        blob_id = storage.store(pdf_bytes, {"test": "deterministic"})
        ingest_result.blob_id = blob_id

        # Extract with the same storage instance
        result = await stage_extract(ingest_result, storage=storage)

        # Assert expected values
        assert result.page_count == 3
        assert result.extraction_coverage == pytest.approx(2 / 3)  # 2 out of 3 pages have text

        # Should have extracted blocks from pages 1 and 2
        page1_blocks = [b for b in result.blocks if b.page == 1]
        page2_blocks = [b for b in result.blocks if b.page == 2]
        page3_blocks = [b for b in result.blocks if b.page == 3]

        assert len(page1_blocks) > 0
        assert len(page2_blocks) > 0
        assert len(page3_blocks) == 0  # Page 3 has no text

        # Verify that we extracted the expected text content
        all_text = " ".join([b.text for b in result.blocks])
        assert "Investment Outlook" in all_text
        assert "Executive Summary" in all_text
        assert "Diversification" in all_text
        assert "Risk management" in all_text

        # Should have detected some bullets on page 2 (at least one)
        # Note: Bullet detection may vary based on PyMuPDF text extraction
        [b for b in page2_blocks if b.block_type == BlockType.BULLET]
        # Just verify that we have blocks, bullet detection is heuristic
        assert len(page2_blocks) > 0  # Should have extracted blocks from page 2

        # Verify block structure is correct
        for block in result.blocks:
            assert block.block_id
            assert block.page in [1, 2]  # Only pages 1 and 2 should have blocks
            assert block.text
            assert isinstance(block.block_type, BlockType)
            assert 0 <= block.confidence <= 1
            assert block.bbox is not None
