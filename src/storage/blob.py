"""Local filesystem-based blob storage for PDF documents.

This module provides a simple file-based storage implementation for MVP.
PDFs are stored in ./data/pdfs/ with SHA-256 hash as the blob_id.

For production, this would be replaced with S3/GCS/Azure Blob storage
while maintaining the same interface.
"""

import hashlib
import json
from pathlib import Path
from typing import Any

from src.exceptions import StorageError


class LocalBlobStorage:
    """File-based blob storage for PDF documents.

    Stores PDF content and metadata in the local filesystem using
    SHA-256 hash as a deterministic blob identifier.

    Directory structure:
        ./data/pdfs/{blob_id}.pdf     # PDF content
        ./data/pdfs/{blob_id}.json    # Metadata

    Attributes:
        storage_dir: Base directory for PDF storage (default: ./data/pdfs/)
    """

    def __init__(self, storage_dir: str | Path = "./data/pdfs") -> None:
        """Initialize blob storage.

        Args:
            storage_dir: Directory path for storing PDFs
        """
        self.storage_dir = Path(storage_dir)
        self._ensure_storage_dir()

    def _ensure_storage_dir(self) -> None:
        """Create storage directory if it doesn't exist."""
        try:
            self.storage_dir.mkdir(parents=True, exist_ok=True)
        except OSError as e:
            raise StorageError(f"Failed to create storage directory {self.storage_dir}: {e}") from e

    def _compute_blob_id(self, content: bytes) -> str:
        """Compute deterministic blob_id from content.

        Args:
            content: PDF content bytes

        Returns:
            SHA-256 hash of content as hex string
        """
        return hashlib.sha256(content).hexdigest()

    def _validate_blob_id(self, blob_id: str) -> None:
        """Validate that blob_id is a valid SHA-256 hex string.

        Args:
            blob_id: The blob ID to validate

        Raises:
            StorageError: If blob_id is not a valid SHA-256 hex string
        """
        if not blob_id:
            raise StorageError("blob_id cannot be empty")
        
        # SHA-256 hex string should be exactly 64 characters and contain only hex digits
        if len(blob_id) != 64 or not all(c in '0123456789abcdefABCDEF' for c in blob_id):
            raise StorageError(f"Invalid blob_id format: must be 64-character SHA-256 hex string")

    def store(self, content: bytes, metadata: dict[str, Any]) -> str:
        """Store PDF content and metadata.

        If the same content (by hash) is stored multiple times, this is
        idempotent - it overwrites the existing files with the same blob_id.

        Args:
            content: PDF content as bytes
            metadata: Metadata dictionary (must be JSON-serializable)

        Returns:
            Blob ID (SHA-256 hash of content)

        Raises:
            StorageError: If storage operation fails
        """
        if not content:
            raise StorageError("Cannot store empty content")

        blob_id = self._compute_blob_id(content)
        pdf_path = self.storage_dir / f"{blob_id}.pdf"
        metadata_path = self.storage_dir / f"{blob_id}.json"

        try:
            # Write PDF content
            pdf_path.write_bytes(content)

            # Write metadata
            metadata_json = json.dumps(metadata, indent=2, sort_keys=True)
            metadata_path.write_text(metadata_json, encoding="utf-8")

            return blob_id

        except OSError as e:
            raise StorageError(f"Failed to store blob {blob_id}: {e}") from e
        except (TypeError, ValueError) as e:
            raise StorageError(f"Failed to serialize metadata for blob {blob_id}: {e}") from e

    def retrieve(self, blob_id: str) -> bytes:
        """Retrieve PDF content by blob_id.

        Args:
            blob_id: SHA-256 hash identifying the blob

        Returns:
            PDF content as bytes

        Raises:
            StorageError: If blob not found or retrieval fails
        """
        self._validate_blob_id(blob_id)

        pdf_path = self.storage_dir / f"{blob_id}.pdf"

        try:
            if not pdf_path.exists():
                raise StorageError(f"Blob not found: {blob_id}")

            return pdf_path.read_bytes()

        except OSError as e:
            raise StorageError(f"Failed to retrieve blob {blob_id}: {e}") from e

    def retrieve_metadata(self, blob_id: str) -> dict[str, Any]:
        """Retrieve metadata by blob_id.

        Args:
            blob_id: SHA-256 hash identifying the blob

        Returns:
            Metadata dictionary

        Raises:
            StorageError: If metadata not found or retrieval fails
        """
        self._validate_blob_id(blob_id)

        metadata_path = self.storage_dir / f"{blob_id}.json"

        try:
            if not metadata_path.exists():
                raise StorageError(f"Metadata not found for blob: {blob_id}")

            metadata_json = metadata_path.read_text(encoding="utf-8")
            metadata: dict[str, Any] = json.loads(metadata_json)
            return metadata

        except OSError as e:
            raise StorageError(f"Failed to retrieve metadata for blob {blob_id}: {e}") from e
        except json.JSONDecodeError as e:
            raise StorageError(f"Failed to parse metadata for blob {blob_id}: {e}") from e

    def exists(self, blob_id: str) -> bool:
        """Check if a blob exists.

        Args:
            blob_id: SHA-256 hash identifying the blob

        Returns:
            True if blob exists, False otherwise

        Raises:
            StorageError: If blob_id is empty or invalid
        """
        self._validate_blob_id(blob_id)

        pdf_path = self.storage_dir / f"{blob_id}.pdf"
        return pdf_path.exists()

    def delete(self, blob_id: str) -> None:
        """Delete a blob and its metadata.

        Args:
            blob_id: SHA-256 hash identifying the blob

        Raises:
            StorageError: If deletion fails or blob_id is invalid
        """
        self._validate_blob_id(blob_id)

        pdf_path = self.storage_dir / f"{blob_id}.pdf"
        metadata_path = self.storage_dir / f"{blob_id}.json"

        try:
            if pdf_path.exists():
                pdf_path.unlink()

            if metadata_path.exists():
                metadata_path.unlink()

        except OSError as e:
            raise StorageError(f"Failed to delete blob {blob_id}: {e}") from e
