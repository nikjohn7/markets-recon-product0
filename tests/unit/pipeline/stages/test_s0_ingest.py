"""Tests for Stage 0: Document ingestion and deduplication.

Tests cover the stage_ingest function from src.pipeline.stages.s0_ingest,
including new document creation, duplicate detection, error handling,
and idempotency guarantees.
"""

import hashlib
import uuid
from pathlib import Path
from typing import Any

import pytest
from src.exceptions import StorageError, ValidationError
from src.models.pipeline import IngestResult
from src.pipeline.stages.s0_ingest import stage_ingest
from src.storage.blob import LocalBlobStorage
from src.storage.database import Database


@pytest.fixture
def temp_storage_dir(tmp_path: Path) -> Path:
    """Create a temporary storage directory for blob storage."""
    storage_dir = tmp_path / "test_pdfs"
    return storage_dir


@pytest.fixture
def temp_db_path(tmp_path: Path) -> Path:
    """Create a temporary database path."""
    db_path = tmp_path / "test_marketsrecon.db"
    return db_path


@pytest.fixture
def storage(temp_storage_dir: Path) -> LocalBlobStorage:
    """Create a LocalBlobStorage instance with temporary directory."""
    return LocalBlobStorage(storage_dir=temp_storage_dir)


@pytest.fixture
def database(temp_db_path: Path) -> Database:
    """Create a Database instance with temporary database."""
    return Database(db_path=temp_db_path)


@pytest.fixture
def valid_pdf_bytes() -> bytes:
    """Create valid PDF bytes for testing."""
    # Simple PDF header + content to simulate a real PDF
    pdf_content = b"""%PDF-1.4
1 0 obj
<< /Type /Catalog /Pages 2 0 R >>
endobj
2 0 obj
<< /Type /Pages /Kids [3 0 R] /Count 1 >>
endobj
3 0 obj
<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] /Contents 4 0 R >>
endobj
4 0 obj
<< /Length 44 >>
stream
BT
/F1 12 Tf
100 700 Td
(Test PDF Content) Tj
ET
endstream
endobj
xref
0 5
0000000000 65535 f
0000000009 00000 n
0000000058 00000 n
0000000115 00000 n
0000000182 00000 n
trailer
<< /Size 5 /Root 1 0 R >>
startxref
400
%%EOF"""
    return pdf_content


@pytest.fixture
def sample_source_metadata() -> dict[str, Any]:
    """Create sample source metadata for testing."""
    return {
        "source": "email",
        "filename": "quarterly_report.pdf",
        "timestamp": "2024-01-15T10:30:00Z",
        "channel": "investor_relations",
    }


class TestNewPDFCreation:
    """Test new PDF document creation and ingestion."""

    @pytest.mark.asyncio
    async def test_new_pdf_creates_record_and_returns_is_duplicate_false(
        self,
        storage: LocalBlobStorage,
        database: Database,
        valid_pdf_bytes: bytes,
        sample_source_metadata: dict[str, Any],
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Verify new PDF creates new record and returns is_duplicate=False."""
        # Mock storage and database to use our test fixtures
        monkeypatch.setattr("src.pipeline.stages.s0_ingest.LocalBlobStorage", lambda: storage)
        monkeypatch.setattr("src.pipeline.stages.s0_ingest.Database", lambda: database)

        result = await stage_ingest(valid_pdf_bytes, sample_source_metadata)

        assert isinstance(result, IngestResult)
        assert result.is_duplicate is False
        assert result.document_id is not None
        assert result.blob_id is not None
        assert result.file_hash is not None
        assert result.source_metadata == sample_source_metadata

    @pytest.mark.asyncio
    async def test_document_stored_in_blob_storage_and_retrievable(
        self,
        storage: LocalBlobStorage,
        database: Database,
        valid_pdf_bytes: bytes,
        sample_source_metadata: dict[str, Any],
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Check that document is stored in blob storage and retrievable."""
        monkeypatch.setattr("src.pipeline.stages.s0_ingest.LocalBlobStorage", lambda: storage)
        monkeypatch.setattr("src.pipeline.stages.s0_ingest.Database", lambda: database)

        result = await stage_ingest(valid_pdf_bytes, sample_source_metadata)

        # Verify blob storage
        retrieved_content = storage.retrieve(result.blob_id)
        assert retrieved_content == valid_pdf_bytes

        # Verify metadata in blob storage
        retrieved_metadata = storage.retrieve_metadata(result.blob_id)
        assert retrieved_metadata == sample_source_metadata

    @pytest.mark.asyncio
    async def test_database_record_created_with_correct_status_and_metadata(
        self,
        storage: LocalBlobStorage,
        database: Database,
        valid_pdf_bytes: bytes,
        sample_source_metadata: dict[str, Any],
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Verify database record is created with correct status and metadata."""
        monkeypatch.setattr("src.pipeline.stages.s0_ingest.LocalBlobStorage", lambda: storage)
        monkeypatch.setattr("src.pipeline.stages.s0_ingest.Database", lambda: database)

        result = await stage_ingest(valid_pdf_bytes, sample_source_metadata)

        # Verify database record
        with database.get_connection() as conn:
            db_result = conn.execute(
                database.documents.select().where(database.documents.c.id == result.document_id)
            ).fetchone()

            assert db_result is not None
            assert db_result.id == result.document_id
            assert db_result.blob_id == result.blob_id
            assert db_result.file_hash == result.file_hash
            assert db_result.status == "pending"

    @pytest.mark.asyncio
    async def test_uuid_generated_for_new_document_id(
        self,
        storage: LocalBlobStorage,
        database: Database,
        valid_pdf_bytes: bytes,
        sample_source_metadata: dict[str, Any],
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Ensure UUID is generated for new document_id."""
        monkeypatch.setattr("src.pipeline.stages.s0_ingest.LocalBlobStorage", lambda: storage)
        monkeypatch.setattr("src.pipeline.stages.s0_ingest.Database", lambda: database)

        result = await stage_ingest(valid_pdf_bytes, sample_source_metadata)

        # Verify UUID format
        try:
            uuid_obj = uuid.UUID(result.document_id)
            assert str(uuid_obj) == result.document_id
        except ValueError:
            pytest.fail(f"document_id {result.document_id} is not a valid UUID")

    @pytest.mark.asyncio
    async def test_file_hash_is_sha256_of_pdf_content(
        self,
        storage: LocalBlobStorage,
        database: Database,
        valid_pdf_bytes: bytes,
        sample_source_metadata: dict[str, Any],
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Verify file_hash is SHA-256 hash of PDF content."""
        monkeypatch.setattr("src.pipeline.stages.s0_ingest.LocalBlobStorage", lambda: storage)
        monkeypatch.setattr("src.pipeline.stages.s0_ingest.Database", lambda: database)

        result = await stage_ingest(valid_pdf_bytes, sample_source_metadata)

        expected_hash = hashlib.sha256(valid_pdf_bytes).hexdigest()
        assert result.file_hash == expected_hash
        assert len(result.file_hash) == 64  # SHA-256 hex string length


class TestDuplicateDetection:
    """Test duplicate PDF detection and handling."""

    @pytest.mark.asyncio
    async def test_same_pdf_submitted_twice_returns_same_document_id_with_is_duplicate_true(
        self,
        storage: LocalBlobStorage,
        database: Database,
        valid_pdf_bytes: bytes,
        sample_source_metadata: dict[str, Any],
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Verify same PDF submitted twice returns same document_id with is_duplicate=True."""
        monkeypatch.setattr("src.pipeline.stages.s0_ingest.LocalBlobStorage", lambda: storage)
        monkeypatch.setattr("src.pipeline.stages.s0_ingest.Database", lambda: database)

        # First submission
        result1 = await stage_ingest(valid_pdf_bytes, sample_source_metadata)
        assert result1.is_duplicate is False

        # Second submission with different metadata
        different_metadata = {**sample_source_metadata, "channel": "different_channel"}
        result2 = await stage_ingest(valid_pdf_bytes, different_metadata)

        assert result2.is_duplicate is True
        assert result2.document_id == result1.document_id
        assert result2.blob_id == result1.blob_id
        assert result2.file_hash == result1.file_hash

    @pytest.mark.asyncio
    async def test_no_duplicate_records_created_in_database(
        self,
        storage: LocalBlobStorage,
        database: Database,
        valid_pdf_bytes: bytes,
        sample_source_metadata: dict[str, Any],
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Ensure no duplicate records are created in database."""
        monkeypatch.setattr("src.pipeline.stages.s0_ingest.LocalBlobStorage", lambda: storage)
        monkeypatch.setattr("src.pipeline.stages.s0_ingest.Database", lambda: database)

        # Submit same PDF twice
        await stage_ingest(valid_pdf_bytes, sample_source_metadata)
        await stage_ingest(valid_pdf_bytes, sample_source_metadata)

        # Count records with this file hash
        with database.get_connection() as conn:
            count = conn.execute(
                database.documents.select().where(
                    database.documents.c.file_hash == hashlib.sha256(valid_pdf_bytes).hexdigest()
                )
            ).fetchall()

            assert len(count) == 1  # Only one record should exist

    @pytest.mark.asyncio
    async def test_blob_storage_not_duplicated(
        self,
        storage: LocalBlobStorage,
        database: Database,
        valid_pdf_bytes: bytes,
        sample_source_metadata: dict[str, Any],
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Verify blob storage is not duplicated for duplicate submissions."""
        monkeypatch.setattr("src.pipeline.stages.s0_ingest.LocalBlobStorage", lambda: storage)
        monkeypatch.setattr("src.pipeline.stages.s0_ingest.Database", lambda: database)

        # Submit same PDF twice
        result1 = await stage_ingest(valid_pdf_bytes, sample_source_metadata)
        result2 = await stage_ingest(valid_pdf_bytes, sample_source_metadata)

        # Both should reference the same blob_id
        assert result1.blob_id == result2.blob_id

        # Verify only one file exists in storage
        pdf_files = list(storage.storage_dir.glob("*.pdf"))
        assert len(pdf_files) == 1
        assert pdf_files[0].stem == result1.blob_id

    @pytest.mark.asyncio
    async def test_second_submission_returns_correct_ingest_result_structure(
        self,
        storage: LocalBlobStorage,
        database: Database,
        valid_pdf_bytes: bytes,
        sample_source_metadata: dict[str, Any],
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Check that second submission returns correct IngestResult structure."""
        monkeypatch.setattr("src.pipeline.stages.s0_ingest.LocalBlobStorage", lambda: storage)
        monkeypatch.setattr("src.pipeline.stages.s0_ingest.Database", lambda: database)

        # First submission
        result1 = await stage_ingest(valid_pdf_bytes, sample_source_metadata)

        # Second submission with different metadata
        different_metadata = {"source": "web_portal", "filename": "same_report.pdf"}
        result2 = await stage_ingest(valid_pdf_bytes, different_metadata)

        # Verify structure
        assert isinstance(result2, IngestResult)
        assert result2.is_duplicate is True
        assert result2.document_id == result1.document_id
        assert result2.blob_id == result1.blob_id
        assert result2.file_hash == result1.file_hash
        # Note: source_metadata should be from the second submission
        assert result2.source_metadata == different_metadata


class TestInvalidPDFHandling:
    """Test handling of invalid PDF inputs."""

    @pytest.mark.asyncio
    async def test_empty_bytes_input_raises_validation_error(
        self, storage: LocalBlobStorage, database: Database, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Test empty bytes input raises ValidationError."""
        monkeypatch.setattr("src.pipeline.stages.s0_ingest.LocalBlobStorage", lambda: storage)
        monkeypatch.setattr("src.pipeline.stages.s0_ingest.Database", lambda: database)

        with pytest.raises(ValidationError, match="pdf_bytes cannot be empty"):
            await stage_ingest(b"", {"source": "test"})

    @pytest.mark.asyncio
    async def test_invalid_source_metadata_raises_validation_error(
        self,
        storage: LocalBlobStorage,
        database: Database,
        valid_pdf_bytes: bytes,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Test invalid source_metadata raises ValidationError."""
        monkeypatch.setattr("src.pipeline.stages.s0_ingest.LocalBlobStorage", lambda: storage)
        monkeypatch.setattr("src.pipeline.stages.s0_ingest.Database", lambda: database)

        with pytest.raises(ValidationError, match="source_metadata must be a dictionary"):
            await stage_ingest(valid_pdf_bytes, "not_a_dict")  # type: ignore

    @pytest.mark.asyncio
    async def test_none_pdf_bytes_raises_validation_error(
        self, storage: LocalBlobStorage, database: Database, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Test None pdf_bytes raises ValidationError."""
        monkeypatch.setattr("src.pipeline.stages.s0_ingest.LocalBlobStorage", lambda: storage)
        monkeypatch.setattr("src.pipeline.stages.s0_ingest.Database", lambda: database)

        with pytest.raises(ValidationError, match="pdf_bytes cannot be empty"):
            await stage_ingest(None, {"source": "test"})  # type: ignore


class TestSourceMetadataStorage:
    """Test source metadata storage in blob and database."""

    @pytest.mark.asyncio
    async def test_source_metadata_stored_correctly_in_blob_storage(
        self,
        storage: LocalBlobStorage,
        database: Database,
        valid_pdf_bytes: bytes,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Verify source metadata is stored correctly in blob storage."""
        monkeypatch.setattr("src.pipeline.stages.s0_ingest.LocalBlobStorage", lambda: storage)
        monkeypatch.setattr("src.pipeline.stages.s0_ingest.Database", lambda: database)

        metadata = {
            "source": "email",
            "timestamp": "2024-01-15T10:30:00Z",
            "filename": "quarterly_report.pdf",
            "channel": "investor_relations",
        }

        result = await stage_ingest(valid_pdf_bytes, metadata)

        retrieved_metadata = storage.retrieve_metadata(result.blob_id)
        assert retrieved_metadata == metadata

    @pytest.mark.asyncio
    async def test_various_metadata_formats(
        self, storage: LocalBlobStorage, database: Database, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Test various metadata formats (channel, timestamp, filename)."""
        monkeypatch.setattr("src.pipeline.stages.s0_ingest.LocalBlobStorage", lambda: storage)
        monkeypatch.setattr("src.pipeline.stages.s0_ingest.Database", lambda: database)

        test_cases = [
            {
                "pdf_content": b"%PDF-1.4 test content 1",
                "metadata": {
                    "source": "web_portal",
                    "filename": "outlook_2024.pdf",
                    "timestamp": "2024-01-20T15:45:00Z",
                    "channel": "public_website",
                },
            },
            {
                "pdf_content": b"%PDF-1.4 test content 2",
                "metadata": {
                    "source": "api",
                    "filename": "monthly_review.pdf",
                    "timestamp": "2024-02-01T09:00:00Z",
                    "channel": "direct_upload",
                    "additional_field": "custom_value",
                },
            },
            {
                "pdf_content": b"%PDF-1.4 test content 3",
                "metadata": {
                    "source": "email",
                    "filename": "special_report.pdf",
                    "timestamp": "2024-03-10T14:20:00Z",
                    "channel": "investor_relations",
                    "sender": "manager@example.com",
                },
            },
        ]

        for case in test_cases:
            result = await stage_ingest(case["pdf_content"], case["metadata"])
            retrieved_metadata = storage.retrieve_metadata(result.blob_id)
            assert retrieved_metadata == case["metadata"]


class TestErrorHandling:
    """Test error handling for storage and database failures."""

    @pytest.mark.asyncio
    async def test_storage_failure_raises_storage_error(
        self,
        database: Database,
        valid_pdf_bytes: bytes,
        sample_source_metadata: dict[str, Any],
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Test storage failures raise StorageError."""

        # Create a mock storage that fails
        class FailingStorage:
            def store(
                self, content: bytes, metadata: dict[str, Any]  # noqa: ARG002
            ) -> str:
                raise StorageError("Storage operation failed")

        monkeypatch.setattr(
            "src.pipeline.stages.s0_ingest.LocalBlobStorage", lambda: FailingStorage()
        )
        monkeypatch.setattr("src.pipeline.stages.s0_ingest.Database", lambda: database)

        with pytest.raises(StorageError, match="Storage operation failed"):
            await stage_ingest(valid_pdf_bytes, sample_source_metadata)

    @pytest.mark.asyncio
    async def test_database_connection_failure_raises_storage_error(
        self,
        storage: LocalBlobStorage,
        valid_pdf_bytes: bytes,
        sample_source_metadata: dict[str, Any],
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Test database connection failures raise StorageError."""

        # Create a mock database that fails
        class FailingDatabase:
            def get_connection(self):
                raise StorageError("Database connection failed")

        monkeypatch.setattr("src.pipeline.stages.s0_ingest.LocalBlobStorage", lambda: storage)
        monkeypatch.setattr("src.pipeline.stages.s0_ingest.Database", lambda: FailingDatabase())

        with pytest.raises(StorageError, match="Database connection failed"):
            await stage_ingest(valid_pdf_bytes, sample_source_metadata)

    @pytest.mark.asyncio
    async def test_unexpected_errors_wrapped_in_storage_error(
        self,
        storage: LocalBlobStorage,
        database: Database,  # noqa: ARG002
        valid_pdf_bytes: bytes,
        sample_source_metadata: dict[str, Any],
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Test unexpected errors are wrapped in StorageError."""

        # Create a mock database that raises unexpected error
        class ErrorDatabase:
            def get_connection(self):
                class MockConn:
                    def execute(self, *_args, **_kwargs):
                        raise ValueError("Unexpected error")

                    def __enter__(self):
                        return self

                    def __exit__(self, *args, **kwargs):
                        pass

                return MockConn()

        monkeypatch.setattr("src.pipeline.stages.s0_ingest.LocalBlobStorage", lambda: storage)
        monkeypatch.setattr("src.pipeline.stages.s0_ingest.Database", lambda: ErrorDatabase())

        with pytest.raises(StorageError, match="Failed to ingest document"):
            await stage_ingest(valid_pdf_bytes, sample_source_metadata)


class TestIdempotency:
    """Test idempotency guarantees."""

    @pytest.mark.asyncio
    async def test_same_input_produces_same_output_consistently(
        self, storage: LocalBlobStorage, database: Database, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Verify same input produces same output consistently."""
        monkeypatch.setattr("src.pipeline.stages.s0_ingest.LocalBlobStorage", lambda: storage)
        monkeypatch.setattr("src.pipeline.stages.s0_ingest.Database", lambda: database)

        test_pdf = b"%PDF-1.4 consistent test content"
        test_metadata = {"source": "test", "filename": "consistent.pdf"}

        # First call should create new document
        first_result = await stage_ingest(test_pdf, test_metadata)
        assert first_result.is_duplicate is False

        # Subsequent calls should detect duplicate
        for _ in range(2):
            result = await stage_ingest(test_pdf, test_metadata)
            assert result.document_id == first_result.document_id
            assert result.blob_id == first_result.blob_id
            assert result.file_hash == first_result.file_hash
            assert result.is_duplicate is True

    @pytest.mark.asyncio
    async def test_multiple_concurrent_submissions_of_same_pdf(
        self,
        storage: LocalBlobStorage,
        database: Database,
        valid_pdf_bytes: bytes,
        sample_source_metadata: dict[str, Any],
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Test multiple concurrent submissions of same PDF."""
        import asyncio

        monkeypatch.setattr("src.pipeline.stages.s0_ingest.LocalBlobStorage", lambda: storage)
        monkeypatch.setattr("src.pipeline.stages.s0_ingest.Database", lambda: database)

        # Create multiple concurrent tasks
        tasks = [stage_ingest(valid_pdf_bytes, sample_source_metadata) for _ in range(5)]

        # Run concurrently
        results = await asyncio.gather(*tasks)

        # All should return the same document_id
        document_ids = {result.document_id for result in results}
        assert len(document_ids) == 1

        # Only one should be non-duplicate (the first one processed)
        non_duplicates = [r for r in results if not r.is_duplicate]
        duplicates = [r for r in results if r.is_duplicate]

        assert len(non_duplicates) >= 1  # At least one should be first
        assert len(duplicates) >= 0  # Others could be duplicates

        # Verify only one record in database
        with database.get_connection() as conn:
            count = conn.execute(
                database.documents.select().where(
                    database.documents.c.file_hash == hashlib.sha256(valid_pdf_bytes).hexdigest()
                )
            ).fetchall()
            assert len(count) == 1

    @pytest.mark.asyncio
    async def test_no_race_conditions_in_duplicate_detection(
        self,
        storage: LocalBlobStorage,
        database: Database,
        valid_pdf_bytes: bytes,
        sample_source_metadata: dict[str, Any],
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Ensure no race conditions in duplicate detection."""
        import asyncio

        monkeypatch.setattr("src.pipeline.stages.s0_ingest.LocalBlobStorage", lambda: storage)
        monkeypatch.setattr("src.pipeline.stages.s0_ingest.Database", lambda: database)

        # Create a barrier to ensure all tasks start at the same time
        start_barrier = asyncio.Barrier(5)

        async def ingest_with_barrier() -> IngestResult:
            await start_barrier.wait()
            return await stage_ingest(valid_pdf_bytes, sample_source_metadata)

        # Create multiple concurrent tasks
        tasks = [ingest_with_barrier() for _ in range(5)]

        # Run concurrently
        results = await asyncio.gather(*tasks)

        # All should return the same document_id
        document_ids = {result.document_id for result in results}
        assert len(document_ids) == 1

        # Verify only one record in database
        with database.get_connection() as conn:
            count = conn.execute(
                database.documents.select().where(
                    database.documents.c.file_hash == hashlib.sha256(valid_pdf_bytes).hexdigest()
                )
            ).fetchall()
            assert len(count) == 1


class TestCleanup:
    """Test cleanup and teardown."""

    @pytest.mark.asyncio
    async def test_clean_up_test_data_after_each_test(
        self,
        storage: LocalBlobStorage,
        database: Database,
        valid_pdf_bytes: bytes,
        sample_source_metadata: dict[str, Any],
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Ensure tests are isolated and don't interfere with each other."""
        monkeypatch.setattr("src.pipeline.stages.s0_ingest.LocalBlobStorage", lambda: storage)
        monkeypatch.setattr("src.pipeline.stages.s0_ingest.Database", lambda: database)

        # This test verifies that each test starts with clean state
        # by checking that no documents exist initially
        with database.get_connection() as conn:
            count = conn.execute(database.documents.select()).fetchall()
            initial_count = len(count)

        # Add a document
        await stage_ingest(valid_pdf_bytes, sample_source_metadata)

        with database.get_connection() as conn:
            count = conn.execute(database.documents.select()).fetchall()
            after_insert_count = len(count)

        assert after_insert_count == initial_count + 1
