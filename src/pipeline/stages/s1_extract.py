"""Stage 1: Text and layout extraction from PDFs.

This stage retrieves PDF from blob storage and extracts structured text content
using the PDF parser. It computes extraction coverage and returns a DocumentJSON model.
"""

import logging
from typing import Any

from src.models.pipeline import IngestResult
from src.models.document import DocumentJSON
from src.extraction.parser import parse_pdf
from src.storage.blob import LocalBlobStorage
from src.exceptions import ExtractionError, StorageError

logger = logging.getLogger(__name__)


async def stage_extract(ingest_result: IngestResult, storage: LocalBlobStorage | None = None) -> DocumentJSON:
    """Extract text and layout from PDF.
    
    Args:
        ingest_result: Output from Stage 0 (Ingest) containing document metadata
        storage: Optional LocalBlobStorage instance (for testing)
        
    Returns:
        DocumentJSON with extracted content and layout information
        
    Raises:
        ExtractionError: If PDF extraction fails
        StorageError: If PDF retrieval from blob storage fails
    """
    logger.info(
        f"Starting Stage 1 extraction for document {ingest_result.document_id}"
    )
    
    # Initialize blob storage if not provided
    if storage is None:
        storage = LocalBlobStorage()
    
    try:
        # Retrieve PDF bytes from blob storage
        pdf_bytes = storage.retrieve(ingest_result.blob_id)
        logger.debug(f"Retrieved PDF bytes for blob {ingest_result.blob_id}")
        
    except StorageError as e:
        logger.error(f"Failed to retrieve PDF from blob storage: {e}")
        raise
    
    try:
        # Parse PDF and extract content
        document_json = parse_pdf(
            pdf_bytes=pdf_bytes,
            document_id=ingest_result.document_id,
            blob_id=ingest_result.blob_id,
            file_hash=ingest_result.file_hash
        )
        
        # Log extraction results
        logger.info(
            f"Extracted {len(document_json.blocks)} blocks from "
            f"{document_json.page_count} pages. Coverage: "
            f"{document_json.extraction_coverage:.2%}"
        )
        
        # Validate extraction coverage meets minimum threshold
        if document_json.extraction_coverage < 0.5:
            logger.warning(
                f"Low extraction coverage: {document_json.extraction_coverage:.2%}. "
                f"Document may require OCR or analyst attention."
            )
        
        return document_json
        
    except Exception as e:
        logger.error(f"PDF extraction failed: {e}")
        raise ExtractionError(f"Failed to extract text from PDF: {e}") from e