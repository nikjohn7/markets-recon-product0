"""Stage 0: Document ingestion and deduplication.

This stage handles the initial ingestion of PDF documents, computing hashes for
deduplication, storing PDFs in blob storage, and creating database records.
"""

import hashlib
import uuid
from typing import Any

from src.exceptions import StorageError, ValidationError
from src.models.pipeline import IngestResult
from src.storage.blob import LocalBlobStorage
from src.storage.database import Database


async def stage_ingest(pdf_bytes: bytes, source_metadata: dict[str, Any]) -> IngestResult:
    """Ingest a PDF document and handle deduplication.

    This function implements the Stage 0 pipeline logic:
    1. Validates input PDF bytes
    2. Computes SHA-256 hash for deduplication
    3. Checks for existing documents with same hash
    4. If duplicate: returns existing document_id
    5. If new: stores PDF in blob storage and creates database record

    Args:
        pdf_bytes: PDF document content as bytes
        source_metadata: Metadata about the document source (must be JSON-serializable)

    Returns:
        IngestResult containing document_id, blob_id, file_hash, is_duplicate flag,
        and source_metadata

    Raises:
        ValidationError: If pdf_bytes is empty or source_metadata is invalid
        StorageError: If blob storage or database operations fail

    Example:
        >>> result = await stage_ingest(pdf_content, {"source": "email", "filename": "report.pdf"})
        >>> if result.is_duplicate:
        ...     print(f"Document already exists: {result.document_id}")
        ... else:
        ...     print(f"New document ingested: {result.document_id}")
    """
    # Validate input
    if not pdf_bytes:
        raise ValidationError("pdf_bytes cannot be empty")
    if not isinstance(source_metadata, dict):
        raise ValidationError("source_metadata must be a dictionary")

    # Compute SHA-256 hash for deduplication
    file_hash = hashlib.sha256(pdf_bytes).hexdigest()

    # Initialize storage and database
    blob_storage = LocalBlobStorage()
    database = Database()

    try:
        # Check for duplicate documents
        with database.get_connection() as conn:
            result = conn.execute(
                database.documents.select().where(database.documents.c.file_hash == file_hash)
            ).fetchone()

            if result:
                # Duplicate found - return existing document info
                return IngestResult(
                    document_id=str(result.id),
                    blob_id=str(result.blob_id),
                    file_hash=file_hash,
                    is_duplicate=True,
                    source_metadata=source_metadata,
                )

        # New document - store in blob storage
        blob_id = blob_storage.store(pdf_bytes, source_metadata)

        try:
            # Generate new document ID and create database record
            document_id = str(uuid.uuid4())

            # Prepare document record
            document_data = {
                "id": document_id,
                "blob_id": blob_id,
                "file_hash": file_hash,
                "status": "pending",
            }

            # Insert document record
            with database.get_connection() as conn:
                conn.execute(database.documents.insert(), document_data)
                conn.commit()

            return IngestResult(
                document_id=document_id,
                blob_id=blob_id,
                file_hash=file_hash,
                is_duplicate=False,
                source_metadata=source_metadata,
            )
        except Exception as db_error:
            # Database insert failed - clean up orphaned blob
            try:
                blob_storage.delete(blob_id)
            except Exception as cleanup_error:
                # Log cleanup failure but raise original error
                raise StorageError(
                    f"Failed to insert document record (blob {blob_id} may be orphaned): {db_error}"
                ) from db_error

            # Re-raise the original database error
            raise

    except Exception as e:
        # Re-raise StorageError and ValidationError as-is
        if isinstance(e, (StorageError, ValidationError)):
            raise
        
        # Wrap other exceptions in StorageError
        raise StorageError(f"Failed to ingest document: {e}") from e