"""Tests for local blob storage in src/storage/blob.py."""

import json
from pathlib import Path

import pytest

from src.exceptions import StorageError
from src.storage.blob import LocalBlobStorage


@pytest.fixture
def temp_storage_dir(tmp_path: Path) -> Path:
    """Create a temporary storage directory."""
    storage_dir = tmp_path / "test_pdfs"
    return storage_dir


@pytest.fixture
def storage(temp_storage_dir: Path) -> LocalBlobStorage:
    """Create a LocalBlobStorage instance with temporary directory."""
    return LocalBlobStorage(storage_dir=temp_storage_dir)


class TestLocalBlobStorage:
    """Test LocalBlobStorage basic functionality."""

    def test_storage_dir_created_on_init(self, temp_storage_dir: Path) -> None:
        """Storage directory is created on initialization."""
        assert not temp_storage_dir.exists()
        LocalBlobStorage(storage_dir=temp_storage_dir)
        assert temp_storage_dir.exists()
        assert temp_storage_dir.is_dir()

    def test_store_and_retrieve_pdf(self, storage: LocalBlobStorage) -> None:
        """Can store and retrieve PDF content."""
        content = b"fake PDF content"
        metadata = {"filename": "test.pdf", "size": len(content)}

        blob_id = storage.store(content, metadata)
        retrieved = storage.retrieve(blob_id)

        assert retrieved == content

    def test_blob_id_is_deterministic(self, storage: LocalBlobStorage) -> None:
        """Same content produces same blob_id (SHA-256 hash)."""
        content = b"test content"
        metadata1 = {"filename": "first.pdf"}
        metadata2 = {"filename": "second.pdf"}

        blob_id1 = storage.store(content, metadata1)
        blob_id2 = storage.store(content, metadata2)

        assert blob_id1 == blob_id2

    def test_blob_id_is_sha256_hash(self, storage: LocalBlobStorage) -> None:
        """Blob ID is SHA-256 hash of content."""
        import hashlib

        content = b"test PDF"
        expected_hash = hashlib.sha256(content).hexdigest()

        blob_id = storage.store(content, {"test": "metadata"})

        assert blob_id == expected_hash
        assert len(blob_id) == 64  # SHA-256 hex string length

    def test_store_creates_pdf_and_metadata_files(
        self, storage: LocalBlobStorage, temp_storage_dir: Path
    ) -> None:
        """Store creates both .pdf and .json files."""
        content = b"test content"
        metadata = {"key": "value"}

        blob_id = storage.store(content, metadata)

        pdf_path = temp_storage_dir / f"{blob_id}.pdf"
        json_path = temp_storage_dir / f"{blob_id}.json"

        assert pdf_path.exists()
        assert json_path.exists()

    def test_retrieve_metadata(self, storage: LocalBlobStorage) -> None:
        """Can retrieve metadata for a blob."""
        content = b"test content"
        metadata = {"filename": "test.pdf", "size": 100}

        blob_id = storage.store(content, metadata)
        retrieved_metadata = storage.retrieve_metadata(blob_id)

        assert retrieved_metadata == metadata

    def test_store_is_idempotent(self, storage: LocalBlobStorage) -> None:
        """Storing same content multiple times is idempotent."""
        content = b"test content"
        metadata1 = {"attempt": 1}
        metadata2 = {"attempt": 2}

        blob_id1 = storage.store(content, metadata1)
        blob_id2 = storage.store(content, metadata2)

        assert blob_id1 == blob_id2
        # Latest metadata wins
        assert storage.retrieve_metadata(blob_id2) == metadata2


class TestBlobStorageExists:
    """Test exists() method."""

    def test_exists_returns_true_for_stored_blob(self, storage: LocalBlobStorage) -> None:
        """exists() returns True for stored blobs."""
        content = b"test content"
        blob_id = storage.store(content, {})

        assert storage.exists(blob_id) is True

    def test_exists_returns_false_for_missing_blob(self, storage: LocalBlobStorage) -> None:
        """exists() returns False for non-existent blobs."""
        assert storage.exists("nonexistent_blob_id") is False

    def test_exists_empty_blob_id_raises(self, storage: LocalBlobStorage) -> None:
        """exists() with empty blob_id raises StorageError."""
        with pytest.raises(StorageError, match="blob_id cannot be empty"):
            storage.exists("")


class TestBlobStorageDelete:
    """Test delete() method."""

    def test_delete_removes_blob_and_metadata(
        self, storage: LocalBlobStorage, temp_storage_dir: Path
    ) -> None:
        """delete() removes both PDF and metadata files."""
        content = b"test content"
        blob_id = storage.store(content, {"key": "value"})

        pdf_path = temp_storage_dir / f"{blob_id}.pdf"
        json_path = temp_storage_dir / f"{blob_id}.json"

        assert pdf_path.exists()
        assert json_path.exists()

        storage.delete(blob_id)

        assert not pdf_path.exists()
        assert not json_path.exists()

    def test_delete_nonexistent_blob_succeeds(self, storage: LocalBlobStorage) -> None:
        """Deleting non-existent blob doesn't raise error."""
        storage.delete("nonexistent_blob_id")  # Should not raise


class TestBlobStorageErrorHandling:
    """Test error handling."""

    def test_store_empty_content_raises(self, storage: LocalBlobStorage) -> None:
        """Storing empty content raises StorageError."""
        with pytest.raises(StorageError, match="Cannot store empty content"):
            storage.store(b"", {"test": "metadata"})

    def test_store_non_serializable_metadata_raises(self, storage: LocalBlobStorage) -> None:
        """Storing non-JSON-serializable metadata raises StorageError."""

        class NonSerializable:
            pass

        with pytest.raises(StorageError, match="Failed to serialize metadata"):
            storage.store(b"content", {"obj": NonSerializable()})

    def test_retrieve_missing_blob_raises(self, storage: LocalBlobStorage) -> None:
        """Retrieving non-existent blob raises StorageError."""
        with pytest.raises(StorageError, match="Blob not found"):
            storage.retrieve("nonexistent_blob_id")

    def test_retrieve_empty_blob_id_raises(self, storage: LocalBlobStorage) -> None:
        """Retrieving with empty blob_id raises StorageError."""
        with pytest.raises(StorageError, match="blob_id cannot be empty"):
            storage.retrieve("")

    def test_retrieve_metadata_missing_blob_raises(self, storage: LocalBlobStorage) -> None:
        """Retrieving metadata for non-existent blob raises StorageError."""
        with pytest.raises(StorageError, match="Metadata not found"):
            storage.retrieve_metadata("nonexistent_blob_id")

    def test_retrieve_metadata_empty_blob_id_raises(self, storage: LocalBlobStorage) -> None:
        """Retrieving metadata with empty blob_id raises StorageError."""
        with pytest.raises(StorageError, match="blob_id cannot be empty"):
            storage.retrieve_metadata("")

    def test_delete_empty_blob_id_raises(self, storage: LocalBlobStorage) -> None:
        """Deleting with empty blob_id raises StorageError."""
        with pytest.raises(StorageError, match="blob_id cannot be empty"):
            storage.delete("")

    def test_retrieve_corrupted_metadata_raises(
        self, storage: LocalBlobStorage, temp_storage_dir: Path
    ) -> None:
        """Retrieving corrupted metadata JSON raises StorageError."""
        content = b"test content"
        blob_id = storage.store(content, {"valid": "metadata"})

        # Corrupt the metadata file
        metadata_path = temp_storage_dir / f"{blob_id}.json"
        metadata_path.write_text("invalid json {{{", encoding="utf-8")

        with pytest.raises(StorageError, match="Failed to parse metadata"):
            storage.retrieve_metadata(blob_id)


class TestBlobStorageMetadata:
    """Test metadata storage format."""

    def test_metadata_is_pretty_printed(
        self, storage: LocalBlobStorage, temp_storage_dir: Path
    ) -> None:
        """Metadata JSON is formatted with indentation."""
        content = b"test content"
        metadata = {"key1": "value1", "key2": "value2"}

        blob_id = storage.store(content, metadata)
        metadata_path = temp_storage_dir / f"{blob_id}.json"
        metadata_text = metadata_path.read_text(encoding="utf-8")

        # Should be pretty-printed (contains newlines)
        assert "\n" in metadata_text
        # Should be valid JSON
        assert json.loads(metadata_text) == metadata

    def test_metadata_keys_are_sorted(
        self, storage: LocalBlobStorage, temp_storage_dir: Path
    ) -> None:
        """Metadata JSON has sorted keys for consistency."""
        content = b"test content"
        metadata = {"z_last": 3, "a_first": 1, "m_middle": 2}

        blob_id = storage.store(content, metadata)
        metadata_path = temp_storage_dir / f"{blob_id}.json"
        metadata_text = metadata_path.read_text(encoding="utf-8")

        # Keys should appear in alphabetical order
        lines = metadata_text.strip().split("\n")
        assert '"a_first"' in lines[1]  # First key after opening brace
        assert '"m_middle"' in lines[2]
        assert '"z_last"' in lines[3]
