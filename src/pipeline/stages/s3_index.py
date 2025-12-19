"""Stage 3: Per-document retrieval index.

This stage builds a vector index from the cleaned document for retrieval-grounded extraction.
"""

import logging

from src.models.pipeline import CleanedDocument
from src.retrieval.indexer import DocumentIndex

logger = logging.getLogger(__name__)


async def stage_index(cleaned_doc: CleanedDocument) -> DocumentIndex:
    """Build per-document vector index from cleaned document.

    Args:
        cleaned_doc: Cleaned document from Stage 2

    Returns:
        DocumentIndex ready for querying

    Raises:
        ExtractionError: If index building fails
    """
    logger.info(f"Starting Stage 3 indexing for document {cleaned_doc.document_id}")

    # Create index
    index = DocumentIndex(document_id=cleaned_doc.document_id)

    # Build index from cleaned document
    await index.build(cleaned_doc)

    logger.info(f"Stage 3 complete: index built with {len(index.chunks)} chunks")

    return index
